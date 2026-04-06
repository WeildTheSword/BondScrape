# parse_remote_pdfs.py
#
# POS (Preliminary Official Statement) extraction pipeline. Fetches PDF documents
# via HTTP using saved Playwright session cookies, extracts text with pypdf, and
# runs two extraction passes:
#   1. Heuristic regex extraction (tax status, dates, call features, par amount)
#   2. Optional LLM extraction via OpenAI-compatible API with multi-chunk consensus
#
# Writes per-document parsed JSON to POS/parsed/ and updates parse status in
# prospectus_json/scraper_output/issues_master.json in place.
#
# This script is for POS documents only. NOS extraction lives in NOS/nos_parsing/.
import io
import json
import os
import re
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

ISSUES_PATH = Path(os.getenv("ISSUES_PATH_OVERRIDE", "prospectus_json/scraper_output/issues_master.json"))
STATE_PATH = Path("prospectus_json/scraper_output/playwright_storage_state.json")
PARSED_ROOT_OVERRIDE = os.getenv("PARSED_ROOT_OVERRIDE")

REQUEST_TIMEOUT = 90

FAST_MODE = True
FAST_MODE_MAX_PAGES = 12

USE_LLM = True
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

LLM_MAX_CHUNKS = 3
LLM_TIMEOUT = 90


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Referer": "https://www.i-dealprospectus.com/Public",
    })

    if STATE_PATH.exists():
        state = load_json(STATE_PATH)
        for cookie in state.get("cookies", []):
            try:
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                )
            except Exception:
                pass

    return session


def fetch_pdf_bytes(session: requests.Session, pdf_url: str) -> bytes:
    resp = session.get(pdf_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: int | None) -> tuple[str, list[dict]]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    pages_to_read = min(total_pages, max_pages) if max_pages is not None else total_pages

    page_records = []
    for i in range(pages_to_read):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""

        page_records.append({
            "page_number": i + 1,
            "text": text
        })

    full_text = "\n\n".join(
        f"[PAGE {p['page_number']}]\n{p['text']}" for p in page_records
    )
    return full_text, page_records


def search_first(pattern: str, text: str, flags=0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


# =========================
# HEURISTICS
# =========================
def detect_tax_status(text: str) -> str | None:
    lower = text.lower()

    tax_exempt_signals = [
        "excluded from gross income for federal income tax purposes",
        "excludable from gross income for federal income tax purposes",
        "interest on the bonds will be excludable from gross income",
        "interest on the bonds is excludable from gross income",
        "tax-exempt",
    ]

    taxable_signals = [
        "federally taxable",
        "taxable bonds",
        "interest on the bonds is includable in gross income",
        "taxable",
    ]

    for s in tax_exempt_signals:
        if s in lower:
            return "tax-exempt"

    for s in taxable_signals:
        if s in lower:
            return "taxable"

    return None


def detect_offering_type(text: str) -> str | None:
    lower = text.lower()
    if "preliminary official statement" in lower:
        return "preliminary_official_statement"
    if "official statement" in lower:
        return "official_statement"
    if "notice of sale" in lower:
        return "notice_of_sale"
    if "ratings" in lower:
        return "rating_material"
    return None


def extract_par_amount(text: str) -> str | None:
    for pattern in [r"\$([0-9][0-9,]+\.\d{2})", r"\$([0-9][0-9,]+)"]:
        value = search_first(pattern, text)
        if value:
            return value
    return None


def extract_dated_date(text: str) -> str | None:
    for pattern in [
        r"Dated\s+Date[:\s]+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"Dated[:\s]+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]:
        value = search_first(pattern, text, flags=re.IGNORECASE)
        if value:
            return value
    return None


def extract_delivery_date(text: str) -> str | None:
    for pattern in [
        r"Delivery\s+Date[:\s]+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"Closing\s+Date[:\s]+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"expected.*delivery.*on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        r"available for delivery.*on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    ]:
        value = search_first(pattern, text, flags=re.IGNORECASE)
        if value:
            return value
    return None


def extract_call_features(text: str) -> list[str]:
    lower = text.lower()
    out = []
    if "subject to redemption prior to maturity" in lower:
        out.append("callable_prior_to_maturity")
    if "optional redemption" in lower:
        out.append("optional_redemption")
    if "mandatory sinking fund redemption" in lower:
        out.append("mandatory_sinking_fund_redemption")
    return out


def extract_underwriter_from_manager_fa(manager_fa: str | None) -> str | None:
    if not manager_fa:
        return None
    parts = [p.strip() for p in manager_fa.split("/") if p.strip()]
    non_fa_parts = [p for p in parts if "(FA)" not in p.upper()]
    return " / ".join(non_fa_parts) if non_fa_parts else None


def extract_financial_advisor_from_manager_fa(manager_fa: str | None) -> str | None:
    if not manager_fa:
        return None
    parts = [p.strip() for p in manager_fa.split("/") if p.strip()]
    fa_parts = [p.replace("(FA)", "").strip() for p in parts if "(FA)" in p.upper()]
    return " / ".join(fa_parts) if fa_parts else None


def build_heuristic_extraction(doc: dict, full_text: str) -> dict:
    manager_fa = doc.get("manager_fa")
    return {
        "issuer": doc.get("issue"),
        "offering_type": detect_offering_type(full_text),
        "sale_type": doc.get("type"),
        "par_amount_from_manifest": doc.get("par_amt_numeric"),
        "par_amount_from_text": extract_par_amount(full_text),
        "tax_status": detect_tax_status(full_text),
        "dated_date": extract_dated_date(full_text),
        "delivery_date": extract_delivery_date(full_text),
        "call_features": extract_call_features(full_text),
        "underwriter": extract_underwriter_from_manager_fa(manager_fa),
        "financial_advisor": extract_financial_advisor_from_manager_fa(manager_fa),
    }


# =========================
# LLM EXTRACTION
# =========================
def llm_enabled() -> bool:
    return USE_LLM and bool(LLM_API_KEY and LLM_MODEL)


def normalize_llm_json(raw: dict[str, Any]) -> dict[str, Any]:
    out = {
        "offering_type": raw.get("offering_type"),
        "tax_status": raw.get("tax_status"),
        "dated_date": raw.get("dated_date"),
        "delivery_date": raw.get("delivery_date"),
        "underwriter": raw.get("underwriter"),
        "financial_advisor": raw.get("financial_advisor"),
        "call_features": raw.get("call_features") or [],
    }

    if out["offering_type"] not in [None, "official_statement", "preliminary_official_statement", "notice_of_sale", "rating_material"]:
        out["offering_type"] = None

    if out["tax_status"] not in [None, "tax-exempt", "taxable"]:
        out["tax_status"] = None

    if not isinstance(out["call_features"], list):
        out["call_features"] = []

    valid_call_features = {
        "optional_redemption",
        "mandatory_sinking_fund_redemption",
        "callable_prior_to_maturity",
    }
    out["call_features"] = [x for x in out["call_features"] if x in valid_call_features]

    return out


def build_llm_chunks(page_records: list[dict]) -> list[str]:
    """
    Build a few high-value chunks:
    1. cover / first pages
    2. summary / table of contents / first pages
    3. targeted pages containing key words
    """
    chunks = []

    if not page_records:
        return chunks

    # Chunk 1: first 3 pages
    first_pages = [p for p in page_records[:3]]
    if first_pages:
        chunks.append("\n\n".join(f"[PAGE {p['page_number']}]\n{p['text']}" for p in first_pages))

    # Chunk 2: first 8 pages
    first_eight = [p for p in page_records[:8]]
    if first_eight:
        chunks.append("\n\n".join(f"[PAGE {p['page_number']}]\n{p['text']}" for p in first_eight))

    # Chunk 3: targeted keyword pages
    keywords = [
        "official statement",
        "preliminary official statement",
        "notice of sale",
        "dated date",
        "delivery",
        "optional redemption",
        "mandatory sinking fund redemption",
        "tax matters",
        "underwriter",
        "financial advisor",
    ]

    targeted = []
    for p in page_records:
        lower = (p.get("text") or "").lower()
        if any(k in lower for k in keywords):
            targeted.append(p)

    # de-dup by page number and cap
    seen = set()
    targeted_unique = []
    for p in targeted:
        if p["page_number"] not in seen:
            targeted_unique.append(p)
            seen.add(p["page_number"])
        if len(targeted_unique) >= 8:
            break

    if targeted_unique:
        chunks.append("\n\n".join(f"[PAGE {p['page_number']}]\n{p['text']}" for p in targeted_unique))

    return chunks[:LLM_MAX_CHUNKS]


def call_llm_extract(chunk_text: str, doc: dict) -> dict[str, Any] | None:
    prompt = f"""
You are extracting structured fields from a municipal bond document.

Return JSON only. No markdown. No explanation.

Allowed schema:
{{
  "offering_type": "official_statement" | "preliminary_official_statement" | "notice_of_sale" | "rating_material" | null,
  "tax_status": "tax-exempt" | "taxable" | null,
  "dated_date": string | null,
  "delivery_date": string | null,
  "underwriter": string | null,
  "financial_advisor": string | null,
  "call_features": string[]
}}

Rules:
- Be conservative. Use null if unclear.
- If the text says interest is excluded or excludable from gross income for federal income tax purposes, tax_status = "tax-exempt".
- If the text explicitly says taxable or federally taxable, tax_status = "taxable".
- call_features can only include:
  - "optional_redemption"
  - "mandatory_sinking_fund_redemption"
  - "callable_prior_to_maturity"
- Do not infer from issue metadata unless explicitly stated in the text chunk.

Document metadata:
issue = {doc.get("issue")}
doc_type = {doc.get("doc_type")}
manager_fa = {doc.get("manager_fa")}

TEXT:
{chunk_text[:30000]}
""".strip()

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a careful municipal bond document extraction engine."},
            {"role": "user", "content": prompt},
        ],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return normalize_llm_json(parsed)


def vote_scalar(values: list[str | None]) -> str | None:
    cleaned = [v for v in values if v not in [None, ""]]
    if not cleaned:
        return None
    counts = Counter(cleaned)
    return counts.most_common(1)[0][0]


def vote_list(values: list[list[str]]) -> list[str]:
    flat = []
    for arr in values:
        flat.extend(arr)
    if not flat:
        return []
    counts = Counter(flat)
    return [k for k, _ in counts.most_common()]


def run_llm_consensus(doc: dict, page_records: list[dict]) -> dict[str, Any]:
    chunks = build_llm_chunks(page_records)
    results = []

    for chunk in chunks:
        try:
            out = call_llm_extract(chunk, doc)
            if out:
                results.append(out)
        except Exception:
            continue

    if not results:
        return {
            "offering_type": None,
            "tax_status": None,
            "dated_date": None,
            "delivery_date": None,
            "underwriter": None,
            "financial_advisor": None,
            "call_features": [],
        }

    return {
        "offering_type": vote_scalar([r.get("offering_type") for r in results]),
        "tax_status": vote_scalar([r.get("tax_status") for r in results]),
        "dated_date": vote_scalar([r.get("dated_date") for r in results]),
        "delivery_date": vote_scalar([r.get("delivery_date") for r in results]),
        "underwriter": vote_scalar([r.get("underwriter") for r in results]),
        "financial_advisor": vote_scalar([r.get("financial_advisor") for r in results]),
        "call_features": vote_list([r.get("call_features", []) for r in results]),
    }


def merge_llm_with_heuristics(heuristic: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    merged = dict(heuristic)

    for field in [
        "offering_type",
        "tax_status",
        "dated_date",
        "delivery_date",
        "underwriter",
        "financial_advisor",
    ]:
        if llm.get(field) not in [None, ""]:
            merged[field] = llm[field]

    if llm.get("call_features"):
        merged["call_features"] = llm["call_features"]

    return merged


# =========================
# MAIN PAYLOAD BUILD
# =========================
def build_parsed_payload(doc: dict, full_text: str, page_records: list[dict]) -> dict:
    heuristic = build_heuristic_extraction(doc, full_text)

    llm_result = {
        "offering_type": None,
        "tax_status": None,
        "dated_date": None,
        "delivery_date": None,
        "underwriter": None,
        "financial_advisor": None,
        "call_features": [],
    }

    if llm_enabled() and page_records:
        llm_result = run_llm_consensus(doc, page_records)

    extracted = merge_llm_with_heuristics(heuristic, llm_result)

    payload = {
        "document_id": doc.get("document_id"),
        "issue": doc.get("issue"),
        "issue_slug": doc.get("issue_slug"),
        "doc_type": doc.get("doc_type"),
        "pdf_url": doc.get("pdf_url"),
        "parsed_at": now_iso(),
        "page_count_examined": len(page_records),
        "llm_used": llm_enabled(),
        "extracted": extracted,
        "heuristic_extracted": heuristic,
        "llm_extracted": llm_result,
        "source_excerpt": full_text[:4000],
        "pages": page_records,
        "notes": [],
    }

    if not full_text.strip():
        payload["notes"].append("No extractable text found.")

    return payload


def update_issue_counts(issue: dict) -> None:
    docs = issue.get("documents", [])

    issue["unparsed_document_count"] = sum(1 for d in docs if d.get("remote_parse_status") == "unparsed")
    issue["parsed_document_count"] = sum(1 for d in docs if d.get("remote_parse_status") == "parsed")
    issue["failed_document_count"] = sum(1 for d in docs if d.get("remote_parse_status") == "failed")
    issue["needs_review_document_count"] = sum(
        1 for d in docs if d.get("remote_parse_status") == "needs_review" or d.get("needs_review") is True
    )

    if issue["failed_document_count"] > 0:
        issue["issue_parse_status"] = "partial_failure"
    elif issue["needs_review_document_count"] > 0:
        issue["issue_parse_status"] = "needs_review"
    elif issue["parsed_document_count"] == len(docs) and len(docs) > 0:
        issue["issue_parse_status"] = "parsed"
    elif issue["unparsed_document_count"] == len(docs):
        issue["issue_parse_status"] = "unparsed"
    else:
        issue["issue_parse_status"] = "in_progress"


def should_parse(doc: dict) -> bool:
    return doc.get("remote_parse_status") == "unparsed" or doc.get("needs_reparse", False)


def main():
    session = build_session()
    data = load_json(ISSUES_PATH)

    total_docs = 0
    parsed_docs = 0
    failed_docs = 0

    max_pages = FAST_MODE_MAX_PAGES if FAST_MODE else None

    for issue in data.get("issues", []):
        for doc in issue.get("documents", []):
            total_docs += 1

            if not should_parse(doc):
                continue

            pdf_url = doc.get("pdf_url")
            parsed_output_path = Path(doc.get("parsed_output_path"))
            if PARSED_ROOT_OVERRIDE:
                parsed_output_path = Path(PARSED_ROOT_OVERRIDE) / f"{doc.get('document_id')}.json"

            print(f"Parsing: {doc.get('document_id')}")

            try:
                if not pdf_url:
                    raise ValueError("Missing pdf_url")

                pdf_bytes = fetch_pdf_bytes(session, pdf_url)
                full_text, page_records = extract_text_from_pdf_bytes(pdf_bytes, max_pages)
                parsed_payload = build_parsed_payload(doc, full_text, page_records)

                parsed_output_path.parent.mkdir(parents=True, exist_ok=True)
                save_json(parsed_output_path, parsed_payload)

                doc["remote_parse_status"] = "parsed"
                doc["last_parsed_at"] = now_iso()
                doc["parse_error"] = None
                doc["needs_reparse"] = False
                doc["needs_review"] = False if full_text.strip() else True

                if not full_text.strip():
                    doc["remote_parse_status"] = "needs_review"

                parsed_docs += 1
                print(f"  Success -> {parsed_output_path}")

            except Exception as e:
                doc["remote_parse_status"] = "failed"
                doc["last_parsed_at"] = now_iso()
                doc["parse_error"] = str(e)
                doc["needs_review"] = True
                failed_docs += 1
                print(f"  Failed -> {e}")

        update_issue_counts(issue)

    save_json(ISSUES_PATH, data)

    print("\nDone.")
    print(f"Total docs seen: {total_docs}")
    print(f"Parsed this run: {parsed_docs}")
    print(f"Failed this run: {failed_docs}")


if __name__ == "__main__":
    main()
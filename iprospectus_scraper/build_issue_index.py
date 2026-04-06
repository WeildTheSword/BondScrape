# build_issue_index.py
#
# Groups raw scraped rows (from scraper_linkpull.py) into issue-level records.
# Reads prospectus_json/scraper_output/scrape_output_raw.json, groups documents
# by issue name, assigns deterministic document IDs, merges parse status from
# prior runs, and outputs:
#   - prospectus_json/scraper_output/issues_master.json (issues with nested documents)
#   - prospectus_json/scraper_output/documents_master.json (flat document list)
#
# Re-running preserves workflow fields (parse status, timestamps) from previous runs.
import json
import re
from pathlib import Path
from urllib.parse import urljoin

# =========================
# CONFIG
# =========================
INPUT_FILE = Path("prospectus_json/scraper_output/scrape_output_raw.json")
OUTPUT_DIR = Path("prospectus_json/scraper_output")
GROUPED_OUTPUT_PATH = OUTPUT_DIR / "issues_master.json"
FLAT_OUTPUT_PATH = OUTPUT_DIR / "documents_master.json"

BASE_URL = "https://www.i-dealprospectus.com"
PARSED_ROOT = Path("POS/parsed")


# =========================
# HELPERS
# =========================
def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s\-&,()]+", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:180] if text else "unknown_issue"


def safe_float(value: str) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0


def normalize_pdf_url(href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(BASE_URL, href)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_date_for_id(date_str: str | None) -> str:
    if not date_str:
        return "unknown_date"

    parts = str(date_str).split("/")
    if len(parts) == 3:
        mm, dd, yyyy = parts
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"

    return "unknown_date"


def extract_pdf_numeric_id(pdf_url: str | None) -> str:
    if not pdf_url:
        return "no_pdf_id"

    match = re.search(r"/PdfDownload/(\d+)", pdf_url)
    if match:
        return match.group(1)

    return "no_pdf_id"


def build_document_id(issue_slug: str, date_str: str | None, doc_type: str | None, pdf_url: str | None) -> str:
    normalized_date = normalize_date_for_id(date_str)
    doc_type_slug = slugify(doc_type or "unknown_doc_type")
    pdf_numeric_id = extract_pdf_numeric_id(pdf_url)
    return f"{issue_slug}__{normalized_date}__{doc_type_slug}__{pdf_numeric_id}"


def build_parsed_output_path(document_id: str) -> str:
    return str(PARSED_ROOT / f"{document_id}.json")


def build_source_signature(row: dict, pdf_url: str | None) -> str:
    return "||".join(
        [
            str(row.get("date") or ""),
            str(row.get("issue") or ""),
            str(row.get("doc_type") or ""),
            str(pdf_url or ""),
            str(row.get("par_amt") or ""),
            str(row.get("manager_fa") or ""),
            str(row.get("type") or ""),
        ]
    )


def load_existing_state() -> dict[str, dict]:
    """
    Return old document state keyed by document_id.
    """
    if not GROUPED_OUTPUT_PATH.exists():
        return {}

    try:
        old = load_json(GROUPED_OUTPUT_PATH)
    except Exception:
        return {}

    existing = {}
    for issue in old.get("issues", []):
        for doc in issue.get("documents", []):
            doc_id = doc.get("document_id")
            if doc_id:
                existing[doc_id] = doc
    return existing


def merge_existing_state(new_doc: dict, old_doc: dict | None) -> dict:
    """
    Preserve workflow-related fields from prior runs if they exist.
    """
    if not old_doc:
        return new_doc

    fields_to_preserve = [
        "remote_parse_status",
        "last_parsed_at",
        "parse_error",
        "needs_review",
        "needs_reparse",
        "content_fingerprint",
        "parse_priority",
        "schema_version",
        "parsed_output_path",
        "remote_source_type",
        "source_signature",
    ]

    for field in fields_to_preserve:
        if field in old_doc:
            new_doc[field] = old_doc[field]

    return new_doc


def update_issue_counts(issue: dict) -> None:
    docs = issue.get("documents", [])

    issue["unparsed_document_count"] = sum(
        1 for d in docs if d.get("remote_parse_status") == "unparsed"
    )
    issue["parsed_document_count"] = sum(
        1 for d in docs if d.get("remote_parse_status") == "parsed"
    )
    issue["failed_document_count"] = sum(
        1 for d in docs if d.get("remote_parse_status") == "failed"
    )
    issue["needs_review_document_count"] = sum(
        1 for d in docs
        if d.get("remote_parse_status") == "needs_review" or d.get("needs_review") is True
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


# =========================
# CONSOLIDATION
# =========================
def consolidate_rows(rows: list[dict]) -> tuple[dict, dict]:
    grouped: dict[str, dict] = {}
    flat_documents: list[dict] = []
    existing_state = load_existing_state()

    for row in rows:
        issue = row.get("issue", "").strip()
        if not issue:
            continue

        issue_slug = slugify(issue)
        pdf_url = normalize_pdf_url(row.get("href"))

        document_id = build_document_id(
            issue_slug=issue_slug,
            date_str=row.get("date"),
            doc_type=row.get("doc_type"),
            pdf_url=pdf_url,
        )

        parsed_output_path = build_parsed_output_path(document_id)
        source_signature = build_source_signature(row, pdf_url)

        doc_record = {
            "date": row.get("date"),
            "issue": issue,
            "issue_slug": issue_slug,
            "manager_fa": row.get("manager_fa"),
            "par_amt": row.get("par_amt"),
            "par_amt_numeric": safe_float(row.get("par_amt", "0")),
            "doc_type": row.get("doc_type"),
            "type": row.get("type"),
            "size_mb": row.get("size_mb"),
            "size_mb_numeric": safe_float(row.get("size_mb", "0")),
            "pdf_url": pdf_url,
            "href": row.get("href"),
            "batch": row.get("batch"),
            "visible_row_index": row.get("visible_row_index"),
            "success_row_number": row.get("success_row_number"),

            "document_id": document_id,
            "remote_source_type": "pdf_url",
            "parsed_output_path": parsed_output_path,
            "source_signature": source_signature,

            "remote_parse_status": "unparsed",
            "last_parsed_at": None,
            "parse_error": None,
            "needs_review": False,
            "needs_reparse": False,
            "content_fingerprint": None,
            "parse_priority": "normal",
            "schema_version": 1,
        }

        doc_record = merge_existing_state(doc_record, existing_state.get(document_id))
        flat_documents.append(doc_record)

        if issue not in grouped:
            grouped[issue] = {
                "issue": issue,
                "issue_slug": issue_slug,
                "manager_fa": row.get("manager_fa"),
                "par_amt": row.get("par_amt"),
                "par_amt_numeric": safe_float(row.get("par_amt", "0")),
                "type": row.get("type"),
                "documents": [],
                "issue_parse_status": "not_started",
                "unparsed_document_count": 0,
                "parsed_document_count": 0,
                "failed_document_count": 0,
                "needs_review_document_count": 0,
            }

        grouped[issue]["documents"].append(doc_record)

    grouped_issues = []
    for _, issue_data in grouped.items():
        docs = issue_data["documents"]

        docs.sort(
            key=lambda d: ((d.get("date") or ""), (d.get("doc_type") or "")),
            reverse=True
        )

        issue_data["document_count"] = len(docs)
        issue_data["doc_types"] = [d.get("doc_type") for d in docs]
        issue_data["doc_types_concatenated"] = " | ".join(
            [d.get("doc_type") for d in docs if d.get("doc_type")]
        )

        update_issue_counts(issue_data)
        grouped_issues.append(issue_data)

    grouped_issues.sort(key=lambda x: x["issue"].lower())
    flat_documents.sort(
        key=lambda x: (x["issue"].lower(), -(x["par_amt_numeric"] or 0), x.get("date") or "")
    )

    grouped_output = {
        "issue_count": len(grouped_issues),
        "issues": grouped_issues,
    }

    flat_output = {
        "document_count": len(flat_documents),
        "documents": flat_documents,
    }

    return grouped_output, flat_output


def main():
    print("Loading rows JSON...")
    rows = load_json(INPUT_FILE)
    print(f"Loaded {len(rows)} rows.")

    print("Consolidating rows by issue...")
    grouped_output, flat_output = consolidate_rows(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Writing grouped output -> {GROUPED_OUTPUT_PATH}")
    with open(GROUPED_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(grouped_output, f, indent=2)

    print(f"Writing flat output -> {FLAT_OUTPUT_PATH}")
    with open(FLAT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(flat_output, f, indent=2)

    print("Done.")


if __name__ == "__main__":
    main()
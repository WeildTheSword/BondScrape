import json
import re
from pathlib import Path
from urllib.parse import urljoin

# =========================
# CONFIG
# =========================
INPUT_FILE = Path("prospectus_json/rows_raw.json")
OUTPUT_DIR = Path("prospectus_json/processed")
BASE_URL = "https://www.i-dealprospectus.com"
PARSED_ROOT = Path("prospectus_json/parsed")


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


def load_rows(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_date_for_id(date_str: str | None) -> str:
    """
    Convert MM/DD/YYYY -> YYYY-MM-DD
    """
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

    m = re.search(r"/PdfDownload/(\d+)", pdf_url)
    if m:
        return m.group(1)

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
        ]
    )


# =========================
# CONSOLIDATION
# =========================
def consolidate_rows(rows: list[dict]) -> tuple[dict, dict]:
    """
    Build:
    1. issues_grouped.json
    2. documents_flat.json

    This version assumes PDFs are accessed remotely via pdf_url
    and are NOT stored locally.
    """

    grouped: dict[str, dict] = {}
    flat_documents: list[dict] = []

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
            # original row metadata
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

            # remote parsing / workflow fields
            "document_id": document_id,
            "remote_source_type": "pdf_url",
            "parsed_output_path": parsed_output_path,
            "source_signature": source_signature,

            # parsing lifecycle
            "remote_parse_status": "unparsed",   # unparsed | parsed | failed | needs_review
            "last_parsed_at": None,
            "parse_error": None,
            "needs_review": False,
            "needs_reparse": False,

            # optional future fields
            "content_fingerprint": None,
            "parse_priority": "normal",
            "schema_version": 1,
        }

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

                # issue-level workflow state
                "issue_parse_status": "not_started",
                "unparsed_document_count": 0,
                "parsed_document_count": 0,
                "failed_document_count": 0,
            }

        grouped[issue]["documents"].append(doc_record)

    # finalize grouped records
    grouped_issues = []
    for issue_name, issue_data in grouped.items():
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

        issue_data["unparsed_document_count"] = sum(
            1 for d in docs if d.get("remote_parse_status") == "unparsed"
        )
        issue_data["parsed_document_count"] = sum(
            1 for d in docs if d.get("remote_parse_status") == "parsed"
        )
        issue_data["failed_document_count"] = sum(
            1 for d in docs if d.get("remote_parse_status") == "failed"
        )

        if issue_data["failed_document_count"] > 0:
            issue_data["issue_parse_status"] = "partial_failure"
        elif issue_data["parsed_document_count"] == len(docs) and len(docs) > 0:
            issue_data["issue_parse_status"] = "parsed"
        elif issue_data["unparsed_document_count"] == len(docs):
            issue_data["issue_parse_status"] = "unparsed"
        else:
            issue_data["issue_parse_status"] = "in_progress"

        grouped_issues.append(issue_data)

    grouped_issues.sort(key=lambda x: x["issue"].lower())
    flat_documents.sort(key=lambda x: (x["issue"].lower(), -(x["par_amt_numeric"] or 0)))

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
    rows = load_rows(INPUT_FILE)
    print(f"Loaded {len(rows)} rows.")

    print("Consolidating rows by issue...")
    grouped_output, flat_output = consolidate_rows(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grouped_path = OUTPUT_DIR / "issues_grouped.json"
    flat_path = OUTPUT_DIR / "documents_flat.json"

    print(f"Writing grouped output -> {grouped_path}")
    with open(grouped_path, "w", encoding="utf-8") as f:
        json.dump(grouped_output, f, indent=2)

    print(f"Writing flat output -> {flat_path}")
    with open(flat_path, "w", encoding="utf-8") as f:
        json.dump(flat_output, f, indent=2)

    print("Done.")


if __name__ == "__main__":
    main()
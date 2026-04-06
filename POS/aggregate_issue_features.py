# aggregate_issue_features.py
#
# Issue-level feature aggregation for POS documents. Reads parsed document JSONs
# from POS/parsed/, and for each issue selects the best field value across multiple
# documents (Final, Prelim, NOS, etc.) using a priority ordering defined in
# FIELD_DOC_PREFERENCE. Outputs POS/issues_enriched_pos.json.
#
# Example: if an issue has both a Final and a Prelim, the Final's dated_date wins.
import os
from pathlib import Path

ISSUES_PATH = Path(os.getenv("ISSUES_PATH_OVERRIDE", "prospectus_json/scraper_output/issues_master.json"))
AGG_OUTPUT_PATH = Path(os.getenv("AGG_OUTPUT_OVERRIDE", "POS/issues_enriched_pos.json"))


DOC_TYPE_PRIORITY = {
    "Final": 100,
    "Prelim": 90,
    "AMENDED": 85,
    "NOS": 80,
    "NOS_2": 79,
    "NOS_3": 78,
    "Proposal": 70,
    "RM": 60,
    "Moodys": 50,
    "S&PS": 50,
}


FIELD_DOC_PREFERENCE = {
    "tax_status": ["Final", "Prelim", "AMENDED", "NOS"],
    "dated_date": ["Final", "Prelim", "AMENDED", "NOS"],
    "delivery_date": ["Final", "Prelim", "AMENDED", "NOS"],
    "par_amount_from_text": ["Final", "Prelim", "AMENDED", "NOS"],
    "offering_type": ["Final", "Prelim", "AMENDED", "NOS", "Proposal"],
    "call_features": ["Final", "Prelim", "AMENDED", "NOS"],
    "underwriter": ["Final", "Prelim", "AMENDED", "NOS"],
    "financial_advisor": ["Final", "Prelim", "AMENDED", "NOS"],
}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def doc_priority(doc_type: str | None) -> int:
    return DOC_TYPE_PRIORITY.get(doc_type or "", 0)


def preferred_docs(parsed_docs: list[dict], field_name: str) -> list[dict]:
    preferred_types = FIELD_DOC_PREFERENCE.get(field_name)
    if not preferred_types:
        return sorted(parsed_docs, key=lambda d: doc_priority(d.get("doc_type")), reverse=True)

    ordered = []
    used = set()

    for doc_type in preferred_types:
        for doc in parsed_docs:
            if doc.get("doc_type") == doc_type and id(doc) not in used:
                ordered.append(doc)
                used.add(id(doc))

    for doc in sorted(parsed_docs, key=lambda d: doc_priority(d.get("doc_type")), reverse=True):
        if id(doc) not in used:
            ordered.append(doc)

    return ordered


def choose_field(parsed_docs: list[dict], field_name: str):
    for doc in preferred_docs(parsed_docs, field_name):
        extracted = doc.get("extracted", {})
        value = extracted.get(field_name)
        if value not in [None, "", [], {}]:
            return {
                "value": value,
                "source_document_id": doc.get("document_id"),
                "source_doc_type": doc.get("doc_type"),
            }
    return {
        "value": None,
        "source_document_id": None,
        "source_doc_type": None,
    }


def load_parsed_doc(path_str: str) -> dict | None:
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def main():
    grouped = load_json(ISSUES_PATH)
    enriched_issues = []

    for issue in grouped.get("issues", []):
        parsed_docs = []

        for doc in issue.get("documents", []):
            if doc.get("remote_parse_status") in ["parsed", "needs_review"]:
                parsed = load_parsed_doc(doc.get("parsed_output_path"))
                if parsed:
                    parsed_docs.append(parsed)

        issue_record = {
            "issue": issue.get("issue"),
            "issue_slug": issue.get("issue_slug"),
            "manager_fa": issue.get("manager_fa"),
            "par_amt_numeric_manifest": issue.get("par_amt_numeric"),
            "type_manifest": issue.get("type"),
            "document_count": issue.get("document_count"),
            "parsed_document_count": issue.get("parsed_document_count"),
            "failed_document_count": issue.get("failed_document_count"),
            "issue_parse_status": issue.get("issue_parse_status"),
            "available_parsed_doc_types": [d.get("doc_type") for d in parsed_docs],

            "aggregated": {
                "offering_type": choose_field(parsed_docs, "offering_type"),
                "sale_type": choose_field(parsed_docs, "sale_type"),
                "par_amount_from_text": choose_field(parsed_docs, "par_amount_from_text"),
                "tax_status": choose_field(parsed_docs, "tax_status"),
                "dated_date": choose_field(parsed_docs, "dated_date"),
                "delivery_date": choose_field(parsed_docs, "delivery_date"),
                "call_features": choose_field(parsed_docs, "call_features"),
                "underwriter": choose_field(parsed_docs, "underwriter"),
                "financial_advisor": choose_field(parsed_docs, "financial_advisor"),
            },
        }

        enriched_issues.append(issue_record)

    out = {
        "issue_count": len(enriched_issues),
        "issues": enriched_issues,
    }

    save_json(AGG_OUTPUT_PATH, out)
    print(f"Wrote issue-level enriched output -> {AGG_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
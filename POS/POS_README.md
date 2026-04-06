# POS — Preliminary Official Statement Extraction Pipeline

This folder contains all code and data related to parsing and extracting structured information from Preliminary Official Statements (POS) and Final Official Statements.

## What is a POS?

A Preliminary Official Statement is the 100+ page disclosure document for a municipal bond issue. It contains issuer financials, credit analysis, tax base data, legal opinions, and the full terms of the bonds. It is read after the NOS (Notice of Sale) during the credit analysis phase.

## Folder Structure

```
POS/
├── parse_remote_pdfs.py            # PDF fetch + text extraction + heuristic/LLM extraction
├── aggregate_issue_features.py     # Cross-document field aggregation per issue
└── parsed/                         # Per-document parsed output JSONs
    └── {document_id}.json
```

## Scripts

### parse_remote_pdfs.py

Fetches POS PDFs via HTTP (using saved Playwright session cookies for authentication), extracts text with `pypdf`, and runs two extraction passes:

1. **Heuristic regex extraction** — detects tax status, offering type, par amount, dated date, delivery date, call features, underwriter, and financial advisor using pattern matching.
2. **LLM extraction** (optional) — sends text chunks to an OpenAI-compatible API, runs multiple chunks through consensus voting to reduce hallucination.

Updates parse status in `prospectus_json/processed/issues_grouped.json` in place.

```bash
# Basic run (heuristics only):
python3 POS/parse_remote_pdfs.py

# With LLM extraction:
export LLM_API_KEY=sk-...
export LLM_MODEL=gpt-4o
python3 POS/parse_remote_pdfs.py
```

Environment variable overrides for sandbox mode:
- `ISSUES_PATH_OVERRIDE` — point to a different issues_grouped.json
- `PARSED_ROOT_OVERRIDE` — write parsed output to a different directory

### aggregate_issue_features.py

Reads parsed document JSONs and selects the best field value for each issue across all its documents. Uses `FIELD_DOC_PREFERENCE` priority ordering (Final > Prelim > AMENDED > NOS) to resolve conflicts when multiple documents contain the same field.

Outputs `prospectus_json/processed/issues_enriched.json`.

```bash
python3 POS/aggregate_issue_features.py
```

Environment variable overrides:
- `ISSUES_PATH_OVERRIDE` — point to a different issues_grouped.json
- `AGG_OUTPUT_OVERRIDE` — write enriched output to a different path

## Parsed Output Format

Each document in `parsed/` is a JSON file containing:
- Document metadata (ID, issue, doc type, PDF URL)
- `extracted` — merged best values from heuristic + LLM
- `heuristic_extracted` — regex-only extraction results
- `llm_extracted` — LLM-only extraction results
- `pages` — per-page text content
- `source_excerpt` — first 4000 chars of extracted text

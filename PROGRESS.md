# Progress Report — NOS Extraction & Multi-Agent Screening Pipeline

Branch: `claude-work`  
Commits: 15 local commits (not pushed)  
Lines added: ~12,000+ across 45+ files

## Completed

### 1. NOS Extraction Schema (`NOS/nos_extraction/schema.py`)
- Full JSON schema covering all 55 NOS features across 10 categories
- Categories: issuer, bond identification, sale logistics, maturity structure, coupon provisions, bid evaluation, redemption, registration/delivery, credit/enhancement, legal/advisory, bidder obligations
- Includes field-to-agent mapping (`FIELD_AGENT_MAP`) showing which agent consumes which fields
- Helper function `get_schema_for_prompt()` for LLM prompt inclusion

### 2. Text Extraction (`NOS/nos_extraction/extract_text.py`)
- Primary method: `pdftotext -layout` (captures stdout, no intermediate file)
- Fallback: `pypdf` when pdftotext is not installed (with warning)
- CLI: `python3 extract_text.py nos.pdf [--output file.txt]`
- `poppler-utils` installed and tested on all 10 PDFs

### 3. LLM Structured Extraction (`NOS/nos_extraction/llm_extract.py`)
- Sends full NOS text + JSON schema to Claude or OpenAI-compatible API
- System prompt with NOS-specific extraction rules (Texas net effective rate, bid form confusion, absent vs. not stated)
- Retry mechanism: on validation failure, re-sends with specific error messages
- Supports `ANTHROPIC_API_KEY` / `LLM_API_KEY` + `LLM_MODEL` env vars

### 4. Deterministic Validation (`NOS/nos_extraction/validate.py`)
- Par amount == sum of maturity schedule amounts
- Good faith deposit math, call date logic, sale date reasonableness
- Maturity count, bond years, average maturity cross-checks
- Required field presence, maturity entry validity
- All tests pass (3 scenarios verified)

### 5. Evaluation Harness (`NOS/nos_extraction/evaluate.py`)
- Field-level weighted accuracy comparison between extraction and ground truth
- 28+ comparison fields with exact, numeric, and string_contains matching
- Special evaluations: maturity schedule sum, count, per-amount accuracy
- Batch mode: evaluate entire directories of extractions vs ground truth
- Ground truth validator: `--validate-gt` checks internal consistency
- Tested: sample NOS vs ground truth = 100% accuracy (32/32 fields)

### 6. Ground Truth JSON Files (`NOS/nos_test_set/ground_truth/`)
All 10 test PDFs have validated ground truth JSON files:

| # | Issuer | State | Par | Maturities | Bond Type |
|---|--------|-------|-----|-----------|-----------|
| 01 | Harris County MUD 182 | TX | $2.93M | 25 | GO Unlimited Tax |
| 02 | Craig County ISD 6 | OK | $600K | 3 | GO Building |
| 03 | Dunellen Borough | NJ | $15.25M | 1 | Bond Anticipation Note |
| 04 | Gallatin City | TN | $22.52M | 20 | GO |
| 05 | Hurricane City | UT | $5.6M | 20 | Sales Tax Revenue |
| 06 | RSU No. 14 | ME | $50.79M | 20 | GO |
| 07 | SD No. 46 (Elgin) | IL | $51.67M | 15 | GO School |
| 08 | San Francisco | CA | $87.67M | 2 | Taxable GO |
| 09 | Virginia HDA | VA | $17.86M | 40 | Revenue (Housing) |
| 10 | Nashville Metro | TN | $204.57M | 9 | GO Improvement |

All pass validation (par sum, field presence, date logic).

### 7. Extracted Text Files (`NOS/nos_test_set/extracted_text/`)
- `pdftotext -layout` output for all 10 test PDFs (2,297-10,692 words each)
- Saved for reference, debugging, and offline extraction testing

### 8. Firm Profiles (`NOS/firm_profiles/`)
- **`texas_regional.json`** — Lone Star Municipal Partners: TX-focused, $25M max, retail-strong, 3 analysts
- **`northeast_institutional.json`** — Atlantic Capital Markets: NE/Mid-Atlantic, $100M max, institutional-strong, 5 analysts
- **`national_large.json`** ��� National Municipal Securities: 24-state coverage, $500M max, 12 analysts
- **`small_boutique.json`** — Magnolia Capital Advisors: TN-only, $10M max, 0 available analysts

### 9. Five Screening Agents (`NOS/nos_agents/agents.py`)
- **Sector Fit** — "Is this our kind of deal?" Reads issuer type, state, bond type vs. firm coverage
- **Size & Capital** — "Can we afford this commitment?" Reads par amount vs. capital limits
- **Structure** — "Are the bidding rules workable?" No firm context — purely technical
- **Distribution** — "Can we sell these bonds?" Reads maturity/rating/BQ vs. firm distribution
- **Calendar** — "Do we have time and people?" Reads sale date vs. pipeline
- Parallel execution via ThreadPoolExecutor, Anthropic + OpenAI support
- Confidence calibration guidance in all system prompts

### 10. Consensus Function (`NOS/nos_agents/consensus.py`)
- Rule 1: Any Pass >= 0.8 confidence → **PASS** (hard veto)
- Rule 2: All Interested → **INTERESTED**
- Rule 3: Mixed → **CONDITIONAL** with conditions
- Rule 4: Multiple low-confidence Pass → **CONDITIONAL** with escalation
- All 4 rules unit tested and verified

### 11. Pipeline Runner (`NOS/run_screening.py`)
- End-to-end: PDF → text → LLM extraction → validation → 5 agents → consensus
- Supports: PDF input, pre-extracted JSON, or dry-run with sample data
- Dry-run tested with both firm profiles

### 12. Demo Comparison (`NOS/demo_compare.py`)
- Single NOS mode: runs same NOS through two firms, shows consensus flip
  - TX MUD: INTERESTED for TX firm, PASS for NE firm (sector fit veto)
- Multi-scenario mode (`--multi`): runs 6 diverse NOS scenarios through both firms
  - 3/6 scenarios produce different decisions across firms
  - Grid output showing deal characteristics vs. firm decisions

### 13. Self-Test Suite (`NOS/run_tests.py`)
- 22 offline tests (no API key needed)
- Covers: schema, validation (3 cases), consensus (4 rules), ground truth (10 files), evaluation harness, agent definitions, demo comparison
- All pass

### 14. Batch Extraction (`NOS/batch_extract.py`)
- Batch text extraction: `--text-only` runs pdftotext on all 10 PDFs
- Batch LLM extraction: runs extraction + evaluation against ground truth
- Evaluate-only mode: `--evaluate-only` scores existing extractions

### 15. Documentation
- `NOS/NOS_FEATURE_TAXONOMY.md` — 55-feature taxonomy with color-coded value pills, reasoning mapping, agent-feature mapping
- `NOS/NOS_REASONING_CHAIN.md` — 10-step reasoning chain from NOS fields through screening to bid preparation
- `NOS/MAS_ARCHITECTURE.md` — Agent topology, consensus rules, anti-patterns, why MAS over single LLM
- `NOS/PRESENTATION_OUTLINE.md` — 14-slide capstone presentation plan with demo commands
- `NOS/NOS_README.md` — Comprehensive guide with quick start, folder structure, pipeline overview
- `NOS/sample_output.json` — Example screening output (5 votes → INTERESTED)
- `CLAUDE.md` — Updated with all new file paths, usage commands
- `requirements.txt` — All pip dependencies
- `.gitignore` — Updated to exclude extraction outputs and temp files

## Still Needs Work

### Live API Testing
- All code written but not tested with actual Claude/OpenAI API calls (no API key in environment)
- End-to-end extraction + agent screening pipeline needs live validation
- The consensus flip demo needs live LLM testing to verify agents produce expected votes

### Ground Truth Verification
- Ground truth JSON files were extracted by reading PDF text programmatically
- Ideally should be human-verified field-by-field against each PDF, especially:
  - Maturity schedules (exact amounts)
  - Good faith deposit calculations
  - Date fields
  - Fields marked null (confirm truly absent vs. missed)

### Additional Firm Profiles
- 4 firm profiles exist (TX regional, NE institutional, national, boutique)
- Could add more specialized profiles (e.g., housing finance specialist, Texas-only large firm)

### Extraction Accuracy Benchmarking
- No automated extraction-vs-ground-truth benchmark across all 10 documents
- Requires API key to run extractions, then `evaluate.py --extract-dir --gt-dir`

### NOS Test Set Coverage
- Could add more diverse NOS documents (housing authority with complex call provisions, very large state GO, tax increment financing, etc.)

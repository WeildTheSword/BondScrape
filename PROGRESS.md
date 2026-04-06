# Progress Report — NOS Extraction & Multi-Agent Screening Pipeline

Branch: `claude-work`

## Completed

### 1. NOS Extraction Schema (`NOS/nos_extraction/schema.py`)
- Full JSON schema covering all 55 NOS features across 10 categories
- Categories: issuer, bond identification, sale logistics, maturity structure, coupon provisions, bid evaluation, redemption, registration/delivery, credit/enhancement, legal/advisory, bidder obligations
- Includes field-to-agent mapping (`FIELD_AGENT_MAP`) showing which agent consumes which fields
- Helper function `get_schema_for_prompt()` for LLM prompt inclusion

### 2. Text Extraction (`NOS/nos_extraction/extract_text.py`)
- Primary method: `pdftotext -layout` (captures stdout, no intermediate file)
- Fallback: `pypdf` when pdftotext is not installed (with warning)
- CLI interface: `python3 extract_text.py nos.pdf [--output file.txt]`

### 3. LLM Structured Extraction (`NOS/nos_extraction/llm_extract.py`)
- Sends full NOS text + JSON schema to Claude or OpenAI-compatible API
- System prompt with NOS-specific extraction rules (Texas net effective rate, bid form confusion, absent vs. not stated, etc.)
- Retry mechanism: on validation failure, re-sends with specific error messages
- Supports `ANTHROPIC_API_KEY` / `LLM_API_KEY` + `LLM_MODEL` env vars
- CLI: `python3 llm_extract.py nos.pdf [--provider anthropic|openai] [--max-retries N]`

### 4. Deterministic Validation (`NOS/nos_extraction/validate.py`)
- Par amount == sum of maturity schedule amounts
- Good faith deposit amount == par_amount * percentage / 100
- First call date after dated date
- Sale date reasonableness (not >2 years old)
- Number of maturities matches maturity_schedule length
- Total bond years cross-check (if stated in document)
- Average maturity cross-check
- Required field presence checks
- Maturity schedule entry validity
- All tests pass

### 5. Firm Profiles (`NOS/firm_profiles/`)
- **`texas_regional.json`** — Lone Star Municipal Partners: TX-focused, $25M max commitment, $75M inventory cap, strong retail/BQ demand, 3 analysts
- **`northeast_institutional.json`** — Atlantic Capital Markets: NE/Mid-Atlantic, $100M max commitment, $250M inventory cap, strong institutional, 5 analysts
- Profiles designed so the same TX MUD NOS produces INTERESTED for the TX firm and PASS for the NE firm

### 6. Five Screening Agents (`NOS/nos_agents/agents.py`)
- **Sector Fit** — "Is this our kind of deal?" Reads issuer type, state, bond type vs. firm coverage
- **Size & Capital** — "Can we afford this commitment?" Reads par amount vs. capital limits
- **Structure** — "Are the bidding rules workable?" No firm context needed — purely technical
- **Distribution** — "Can we sell these bonds?" Reads maturity/rating/BQ vs. firm distribution strength
- **Calendar** — "Do we have time and people?" Reads sale date vs. pipeline and analyst availability
- All run in parallel via ThreadPoolExecutor (no anchoring bias)
- Support both Anthropic and OpenAI-compatible APIs
- Each agent gets only its relevant NOS fields and firm context (not the full JSON)

### 7. Consensus Function (`NOS/nos_agents/consensus.py`)
- Rule 1: Any Pass with confidence >= 0.8 -> **PASS** (hard veto)
- Rule 2: All five Interested -> **INTERESTED**
- Rule 3: Mix of Interested/Conditional -> **CONDITIONAL** with conditions listed
- Rule 4: Multiple low-confidence Pass (<0.8) -> **CONDITIONAL** with escalation flag
- All 4 rules tested and verified
- Includes `format_consensus_report()` for human-readable output

### 8. End-to-End Pipeline Runner (`NOS/run_screening.py`)
- Ties together: text extraction -> LLM extraction -> validation -> 5 agents -> consensus
- Supports: PDF input, pre-extracted JSON input, or dry-run with sample data
- Dry-run tested successfully with both firm profiles
- Outputs both human-readable report (stderr) and JSON (file + stdout summary)
- Sample NOS JSON embedded for testing (Harris County MUD 182 data from ground truth)

## Not Started / Still Needs Work

### Ground Truth Files
- Only 1 of 10 ground truth files started (Harris County MUD 182, and it needs the extracted fields section)
- The remaining 9 PDFs have reading scripts but no ground truth transcription or extracted fields
- This is a manual effort requiring human verification against each PDF

### Live LLM Testing
- All code is written but has not been tested with actual API calls (no API key in this environment)
- The extraction, agent, and consensus code needs end-to-end testing with real Claude/OpenAI calls
- The "consensus flip" demo (same NOS, two firm profiles) needs live testing

### pdftotext Installation
- `pdftotext` (from poppler-utils) is not installed in this environment
- The code falls back to pypdf, but pdftotext -layout is the recommended method
- Install with: `sudo apt-get install poppler-utils`

### CLAUDE.md Updates
- The CLAUDE.md file describes the NOS pipeline at a high level but could be updated with the specific file paths and usage commands for the new code

### Evaluation Harness
- No automated scoring of extraction accuracy against ground truth
- The INSTRUCTIONS.md describes a comparison workflow but no script exists to compute field-level accuracy across the 10 test documents

### Dependencies
- The extraction scripts import `anthropic` and `openai` packages which may need to be pip-installed
- `pypdfium2` is needed for vision_extract.py (existing code)
- `pypdf` is the fallback text extractor

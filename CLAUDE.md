# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BondScrape is a municipal bond prospectus scraper, structured extraction pipeline, and multi-agent screening system for competitive municipal bond sales. It scrapes document listings from i-dealprospectus.com, groups them by bond issue, extracts structured data from PDFs (via heuristics + LLM), and serves results through both a static browser UI and a FastAPI control panel.

### Research Context

This project is a capstone research project investigating how a Large Language Model Multi-Agent System (LLM-MAS) can be leveraged in public finance, specifically in the competitive sale workflow. The core research argument:

**The competitive sale is a pipeline of decision points, each with different data and different reasoning. The Notice of Sale (NOS) is the first filter — it determines whether analyst time gets committed to reviewing the full Preliminary Official Statement (POS), which is typically 100+ pages. A multi-agent consensus system can automate this screening gate.**

The presentation deadline is approximately April 24, 2026.

### Domain Background: Competitive Municipal Bond Sales

In a competitive sale, the issuer posts documents in this order:
1. **Notice of Sale (NOS)** — 7-15 page document establishing the auction rules, bond structure, bidding constraints, and sale logistics. This is the screening document.
2. **Preliminary Official Statement (POS)** — 100+ page disclosure document with issuer financials, credit analysis, tax base data, legal opinions. This is the credit analysis document.
3. **Final Official Statement (OS)** — Completed after the sale with final pricing terms.

The NOS is read BEFORE the POS. The screening decision the NOS enables is:
- **Interested** — Proceed to POS review, allocate analyst time, begin syndicate outreach
- **Conditional** — Interested if certain conditions are met (need syndicate partner, confirm BQ status, etc.)
- **Pass** — Not our sector, too large, timing conflict, constraints too restrictive

The potential underwriter purchases the securities only if selected in the bidding process. All competitive underwritings are firm commitment — the winning syndicate must purchase all bonds even if they can't resell them.

### Key NOS Features for Extraction

NOS documents have no standard format. They vary by financial advisor template (GMS Group, Rathmann & Associates, Moors & Cabot, etc.), by state (Texas has ~3 pages of compliance boilerplate; Maine does not), and by issuer type. However, they all contain the same core information mapped to this schema:

- **Issuer identification**: name, type (MUD, school district, city, county, authority), state, county
- **Bond identification**: series name, bond type (GO unlimited/limited, revenue), par amount, tax status, bank qualified (Section 265)
- **Sale logistics**: sale date/time, bidding platform (PARITY, Grant Street), bid formats accepted, financial advisor
- **Maturity structure**: serial/term/both, dated date, interest payment dates, maturity schedule (year + amount), bidder term bond option
- **Coupon and bidding constraints**: basis of award (NIC/TIC/net effective rate), min bid price, rate increment, max rate cap, max rate spread, premium/discount rules
- **Redemption**: optional redemption (callable/non-callable), first call date, call price, call protection years, mandatory sinking fund
- **Good faith deposit**: amount, percentage of par, form (cashier's check, wire, etc.)
- **Delivery**: expected and latest delivery dates, book entry (DTC), denomination, paying agent
- **Legal/compliance**: bond counsel, disclosure counsel, credit rating (or unrated), continuing disclosure, issue price requirements
- **Derived features**: total bond years, average maturity, number of maturities

### PDF Extraction Methodology

**`pdftotext -layout` is the only extraction method that works reliably across all NOS document types.**

Findings from testing 5 NOS documents (Brazoria County MUD 42, Harris County MUD 439, Harris County MUD 182, Maine Regional School Unit 14, Post Wood MUD):
- Raw `pdftotext` (no -layout flag) drops maturity table amounts entirely on PScript5-generated PDFs
- `pdfplumber` produces run-together words on PScript5 PDFs and finds zero formal PDF tables across all documents
- `pdftotext -layout` works on all 5: Word-native PDFs, PScript5 print-to-PDF, copy-protected PDFs (Maine)
- All maturity schedules are space-aligned text, not formal PDF tables
- Document sizes range from ~4K to ~11K words (~5K-18K tokens), fitting in a single LLM context window

The pipeline is: `pdftotext -layout` → full text to LLM with JSON schema → structured JSON output → deterministic validation checks.

**Validation checks to catch LLM extraction errors:**
- `par_amount` must equal sum of maturity schedule amounts
- `good_faith_deposit.amount` must equal `par_amount * good_faith_deposit.percentage_of_par / 100`
- `first_call_date` must be after `dated_date`
- `sale_date` should be a future date (or recent past)
- Number of maturities must match length of maturity schedule array
- If bond years table exists in document, `total_bond_years` and `average_maturity` must match

**Known LLM extraction risks:**
- Confusing the NOS body with the bid form or underwriter certificates (same PDF, repeated maturity tables)
- Absent vs. not stated: "explicitly unrated" is different from "rating not mentioned"
- Numerical transposition in maturity schedules ($155,000 vs $165,000) — caught by the par amount sum check
- Flattening conditional fields: issue price requirements are often conditional ("if insufficient bids, hold-the-offering-price applies")
- Texas "net effective interest rate" is functionally NIC but uses different terminology

### Multi-Agent System Architecture

Five agents, each answering one screening question. All receive the extracted NOS JSON plus a shared firm profile. Agents run in parallel and do not see each other's votes (prevents anchoring bias). Consensus rule is deterministic Python, not another LLM call.

**Agent 1: Sector Fit** — "Is this our kind of deal?"
- Reads: issuer type, state, bond type, tax status
- Evaluates against: firm coverage map (states, issuer types, bond types)
- Fast filter. If the firm doesn't cover this state, nothing else matters.

**Agent 2: Size and Capital** — "Can we afford this commitment?"
- Reads: par amount, good faith deposit, delivery dates
- Evaluates against: max single commitment, current inventory, inventory limit
- Math check. Enforces hard capital limits a single LLM tends to underweight.

**Agent 3: Structure and Constraints** — "Are the bidding rules workable?"
- Reads: all coupon/bidding constraints, maturity structure, redemption provisions
- No firm context needed — purely technical evaluation
- Catches edge cases: ascending-coupons-only + tight rate cap + par floor = hard optimization problem.

**Agent 4: Distribution Feasibility** — "Can we sell these bonds?"
- Reads: par amount, tax status, bank qualified, maturity range, rating, call structure
- Evaluates against: firm's retail/institutional strength, bank qualified demand, taxable demand
- Represents the people who actually sell the bonds.

**Agent 5: Calendar and Bandwidth** — "Do we have time and people?"
- Reads: sale date, delivery date
- Evaluates against: current pipeline, analyst availability, max concurrent bids
- Simplest agent. Hard veto — if sale is tomorrow and POS hasn't been reviewed, deal is dead.

**Consensus Rule:**
1. Any single Pass with confidence >= 0.8 → **PASS** (hard veto)
2. All five Interested → **INTERESTED**
3. Mix of Interested/Conditional (no high-confidence Pass) → **CONDITIONAL** with conditions listed
4. Multiple low-confidence Pass votes (< 0.8) → **CONDITIONAL** with escalation flag for human review

**Why MAS over a single LLM call:**
- Explainability at the dimension level (5 separate votes with 5 separate rationales, not one blended paragraph)
- Hard veto enforcement (a single LLM hedges and softens dealbreakers into caveats)
- Different context per agent (in production: distribution has order book, risk has inventory, calendar has pipeline)
- Mirrors real organizational structure (different humans on the desk already make these separate judgments)

**Demo approach:** Run the same NOS with two different firm profiles to show the consensus flips. A $4.2M Texas MUD might be Interested for a Texas-focused regional firm and Pass for a Northeast-only firm. The firm profile is the variable, not the agents.

### Evaluation Dataset

Target: 10 manually labeled NOS documents as ground truth.
- 5 currently in hand: Brazoria County MUD 42 (TX), Harris County MUD 439 (TX), Harris County MUD 182 (TX), Maine Regional School Unit 14 (ME), Post Wood MUD (TX)
- 5 more needed from EMMA (emma.msrb.org): 1 city GO, 1 county, 1 state authority, 2 non-TX states
- Covers variation in: financial advisor template (GMS Group, Rathmann, Moors & Cabot), state (TX, ME, + others), issuer type (MUD, school district, + others), par amount ($2.9M - $50.8M), rated vs unrated

Each document is manually verified field-by-field against the PDF. The ground truth JSON is used to measure field-level extraction accuracy and to validate that the agent consensus system produces reasonable screening decisions.

---

## Pipeline Architecture

The pipeline runs as a sequence of scripts, each producing JSON consumed by the next:

### Scraping (`iprospectus_scraper/`)

1. **`iprospectus_scraper/scraper_linkpull.py`** — Playwright-based scraper. Opens a browser, loads document batches from the prospectus site via "Load Documents" button pagination, and writes `prospectus_json/rows_raw.json`. Requires manual login when `WAIT_FOR_MANUAL_LOGIN=True`. Saves browser cookies to `prospectus_json/playwright_storage_state.json` for use by the PDF parser.

2. **`iprospectus_scraper/build_issue_index.py`** — Groups raw rows by issue name, assigns document IDs, merges state from prior runs (preserving parse status fields), and outputs `prospectus_json/processed/issues_grouped.json` and `documents_flat.json`.

### POS Extraction (`POS/`)

4. **`POS/parse_remote_pdfs.py`** — POS (Preliminary Official Statement) extraction only. Fetches PDFs via HTTP (using saved Playwright cookies for auth), extracts text with `pypdf`, runs heuristic regex extraction + optional LLM extraction (OpenAI-compatible API), uses multi-chunk consensus voting for LLM results, and writes per-document JSON to `POS/parsed/`. Updates parse status in `issues_grouped.json` in place.

5. **`POS/aggregate_issue_features.py`** — Reads parsed document JSONs from `POS/parsed/`, selects best field values across documents using `FIELD_DOC_PREFERENCE` priority ordering (Final > Prelim > AMENDED > NOS), and writes `prospectus_json/processed/issues_enriched.json`.

### UI & Control Panel (root level)

6. **`app.py`** — FastAPI control panel with sandbox workflow: select documents, generate CLI commands for parse/aggregate, manage sandbox vs production datasets. Serves Jinja2 templates from `templates/`.

7. **`index.html`** — Standalone static UI that loads `issues_grouped.json` and renders searchable, filterable issue cards color-coded by date (blue=upcoming, red=past).

### NOS Extraction Pipeline (code lives in `NOS/`)

Separate from the general PDF parsing pipeline above. All NOS-specific code and data lives under `NOS/`:

- `NOS/nos_parsing/generate_reading_script.py` — Structural analysis of PDFs. Detects headers (bold), tables (column gaps), paragraphs, footnotes, form fields. Generates a "reading script" used for page routing (deciding which pages to send to a model for each field).
- `NOS/nos_parsing/vision_extract.py` — Vision-based field extraction prototype. Uses reading scripts to route fields to relevant pages, renders pages as images, sends to a vision-capable LLM. Supports Anthropic and OpenAI-compatible APIs.

Test data and ground truth files are in `NOS/nos_test_set/` (10 diverse NOS PDFs, manifest, reading scripts, ground truth files). See `NOS/nos_test_set/INSTRUCTIONS.md` for the full validation plan and ground truth file format.

Pipeline:

1. **Input**: NOS PDF file
2. **Text extraction**: `pdftotext -layout input.pdf -` (stdout capture, no intermediate file needed)
3. **LLM structured extraction**: Send full text + JSON schema to Claude API, request JSON output
4. **Validation**: Deterministic checks (par amount sum, good faith deposit math, date logic, maturity count)
5. **Retry on validation failure**: Re-send with specific error message if checks fail
6. **Output**: Validated JSON matching the NOS extraction schema

### NOS Agent Screening Pipeline (new)

1. **Input**: Validated NOS JSON + Firm Profile JSON
2. **Parallel agent calls**: 5 independent Claude API calls, each with agent-specific system prompt + relevant NOS fields + relevant firm context
3. **Vote collection**: Each agent returns {vote, confidence, rationale}
4. **Consensus function**: Deterministic Python applying the veto/unanimous/conditional rules
5. **Output**: {decision, reason, conditions (if any), individual votes}

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install playwright requests pypdf fastapi jinja2 uvicorn
python3 -m playwright install

# Scraping pipeline
python3 iprospectus_scraper/scraper_linkpull.py    # Scrape metadata (needs browser/auth)
python3 iprospectus_scraper/build_issue_index.py   # Group by issue
# POS extraction
python3 POS/parse_remote_pdfs.py         # Parse POS PDFs (set LLM_API_KEY, LLM_MODEL env vars for LLM mode)
python3 POS/aggregate_issue_features.py  # Aggregate fields across docs

# Serve
python3 -m http.server 8000         # Static UI at localhost:8000
uvicorn app:app --reload             # FastAPI control panel
```

## Key Data Flow

- Raw scrape rows: `prospectus_json/scraper_output/scrape_output_raw.json`
- Issues master: `prospectus_json/scraper_output/issues_master.json` (the central state file — parse status is updated in place by POS/parse_remote_pdfs.py)
- Documents master: `prospectus_json/scraper_output/documents_master.json`
- Browser cookies: `prospectus_json/scraper_output/playwright_storage_state.json`
- Per-document POS parsed output: `POS/parsed/{document_id}.json`
- POS enriched aggregation: `POS/issues_enriched_pos.json`
- Sandbox copies: `prospectus_json/sandbox/` (mirrors scraper_output structure)

## Important Patterns

- **Document IDs** are deterministic composites: `{issue_slug}__{date}__{doc_type}__{pdf_numeric_id}`. The `slugify()` function (duplicated in scraper and build scripts) strips unsafe chars and replaces whitespace with underscores.
- **State preservation**: `build_issue_index.py` merges workflow fields (`remote_parse_status`, `last_parsed_at`, etc.) from prior runs so re-running doesn't lose parse progress.
- **LLM extraction** uses an OpenAI-compatible chat completions endpoint. Controlled by `USE_LLM`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` env vars. Sends multiple text chunks and uses majority voting across responses.
- **Environment variable overrides**: `ISSUES_PATH_OVERRIDE`, `PARSED_ROOT_OVERRIDE`, `AGG_OUTPUT_OVERRIDE` allow pointing scripts at sandbox data.
- There are no tests in this project.

## Reference: NOS Feature Taxonomy

For the complete taxonomy of 55 taggable NOS features across 10 categories (sale logistics, bond identification, maturity structure, coupon constraints, bid evaluation, redemption, registration/delivery, credit/enhancement, legal/advisory, bidder obligations), see the extraction schema used by the LLM extraction prompt. Each feature maps to a specific agent's input — the schema was designed so that each agent reads only the fields relevant to its screening question.

## Reference: Competitive Sale Workflow

```
NOS posted by issuer
  → Underwriter screening decision: Interested / Conditional / Pass  [THIS PROJECT]
    → If Interested: POS review (credit analysis, 100+ pages)        [Future work]
      → If credit approved: Write the scale, optimize coupons, submit bid  [Future work]
        → If winning bid: Purchase bonds on firm commitment, resell to investors
```

The NOS establishes the auction rules and bond structure. The POS establishes credit quality. The bid preparation stage combines both with real-time market data (MMD curve, Bond Buyer indexes). Each stage is a progressively more complex consensus problem. This project focuses exclusively on the NOS screening stage.

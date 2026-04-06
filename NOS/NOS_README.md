# NOS — Notice of Sale Extraction & Multi-Agent Screening Pipeline

This folder contains everything for the NOS screening system: extraction code, agent screening, firm profiles, test data, ground truth, and documentation.

## Quick Start

```bash
# Install dependencies
pip install anthropic pypdf
sudo apt-get install poppler-utils

# Run self-tests (no API key needed)
python3 NOS/run_tests.py

# Demo: consensus flip across firm profiles (no API key needed)
python3 NOS/demo_compare.py --dry-run

# Multi-scenario comparison grid (no API key needed)
python3 NOS/demo_compare.py --multi

# Full pipeline with API key
export ANTHROPIC_API_KEY=sk-...
python3 NOS/run_screening.py NOS/nos_test_set/NOS_Test_PDFs/01_Harris_County_MUD_No_182,_TX_Unlimited_Tax_Bonds,_Srs_2026.pdf --firm NOS/firm_profiles/texas_regional.json

# Screen a ground truth JSON (no PDF extraction needed)
python3 NOS/run_screening.py --nos-json NOS/nos_test_set/ground_truth/01_ground_truth.json --firm NOS/firm_profiles/texas_regional.json --dry-run
```

## What is an NOS?

A Notice of Sale is a 7-15 page document posted by a municipal bond issuer to solicit competitive bids from underwriters. It establishes the auction rules, bond structure, bidding constraints, and sale logistics. It is the first document an underwriter reads when deciding whether to bid on a deal.

The screening decision the NOS enables is:
- **Interested** — Proceed to POS review, allocate analyst time
- **Conditional** — Interested with caveats (need syndicate, confirm BQ status, etc.)
- **Pass** — Not our sector, too large, timing conflict, constraints too restrictive

## Folder Structure

```
NOS/
├── nos_extraction/                      # Extraction pipeline code
│   ├── schema.py                        # 55-feature JSON schema (10 categories)
│   ├── extract_text.py                  # pdftotext -layout extraction
│   ├── llm_extract.py                   # LLM structured extraction + retry
│   ├── validate.py                      # Deterministic validation checks
│   └── evaluate.py                      # Ground truth comparison harness
├── nos_agents/                          # Multi-agent screening system
│   ├── agents.py                        # 5 screening agents + parallel runner
│   └── consensus.py                     # Deterministic consensus function
├── nos_parsing/                         # Legacy parsing utilities
│   ├── generate_reading_script.py       # PDF structural analysis
│   └── vision_extract.py               # Vision-based extraction prototype
├── nos_test_set/                        # Test data
│   ├── NOS_Test_PDFs/                   # 10 diverse NOS PDFs
│   ├── ground_truth/                    # 10 validated ground truth JSONs
│   ├── extracted_text/                  # pdftotext output for all 10 PDFs
│   ├── reading_scripts/                 # Structural reading scripts
│   ├── manifest.json                    # Test PDF index
│   └── INSTRUCTIONS.md                  # Validation plan
├── firm_profiles/                       # Hypothetical firm profiles for demo
│   ├── texas_regional.json              # TX-focused, $25M max, retail
│   ├── northeast_institutional.json     # NE/Mid-Atlantic, $100M max, institutional
│   ├── national_large.json              # National, $500M max, full distribution
│   └── small_boutique.json              # TN-only, $10M max, no analysts
├── run_screening.py                     # End-to-end pipeline runner
├── demo_compare.py                      # Firm profile comparison demo
├── batch_extract.py                     # Batch extraction + evaluation
├── run_tests.py                         # Self-test suite (22 tests)
├── sample_output.json                   # Example screening output
├── NOS_FEATURE_TAXONOMY.md              # 55-feature taxonomy reference
├── NOS_REASONING_CHAIN.md               # 10-step NOS reasoning chain
├── MAS_ARCHITECTURE.md                  # Multi-agent system design docs
└── PRESENTATION_OUTLINE.md              # Capstone presentation outline
```

## Pipeline

### Extraction Pipeline
1. **Input**: NOS PDF file
2. **Text extraction**: `pdftotext -layout input.pdf -` (stdout, no temp file)
3. **LLM extraction**: Full text + JSON schema → Claude API → structured JSON
4. **Validation**: Deterministic checks (par sum, GFD math, dates, maturity count)
5. **Retry**: On validation failure, re-send with specific error messages
6. **Output**: Validated JSON matching the 55-feature schema

### Agent Screening Pipeline
1. **Input**: Validated NOS JSON + Firm Profile JSON
2. **Parallel agents**: 5 independent Claude API calls (no inter-agent communication)
3. **Vote collection**: Each agent returns {vote, confidence, rationale, conditions}
4. **Consensus**: Deterministic Python (veto/unanimous/conditional/escalation rules)
5. **Output**: {decision, reason, conditions, individual votes}

## Test Set

10 NOS PDFs selected for maximum diversity:

| # | Issuer | State | Par | Type |
|---|--------|-------|-----|------|
| 01 | Harris County MUD 182 | TX | $2.9M | GO Unlimited Tax |
| 02 | Craig County ISD 6 | OK | $600K | GO Building |
| 03 | Dunellen Borough | NJ | $15.2M | Bond Anticipation Note |
| 04 | Gallatin City | TN | $22.5M | GO |
| 05 | Hurricane City | UT | $5.6M | Sales Tax Revenue |
| 06 | RSU No. 14 | ME | $50.8M | GO |
| 07 | SD No. 46 (Elgin) | IL | $51.7M | GO School |
| 08 | San Francisco | CA | $87.7M | Taxable GO |
| 09 | Virginia HDA | VA | $17.9M | Revenue (Housing) |
| 10 | Nashville Metro | TN | $204.6M | GO Improvement |

All 10 have validated ground truth JSON files that pass deterministic checks.

## Documentation

- [Feature Taxonomy](NOS_FEATURE_TAXONOMY.md) — 55 features, 10 categories, color-coded values
- [Reasoning Chain](NOS_REASONING_CHAIN.md) — 10-step NOS reasoning chain
- [MAS Architecture](MAS_ARCHITECTURE.md) — Agent design, topology, consensus rules, anti-patterns
- [Presentation Outline](PRESENTATION_OUTLINE.md) — 14-slide capstone presentation plan

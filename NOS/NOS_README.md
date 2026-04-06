# NOS — Notice of Sale Extraction Pipeline

This folder contains all code and data related to parsing and extracting structured information from Notice of Sale (NOS) documents.

## What is an NOS?

A Notice of Sale is a 7-15 page document posted by a municipal bond issuer to solicit competitive bids from underwriters. It establishes the auction rules, bond structure, bidding constraints, and sale logistics. It is the first document an underwriter reads when deciding whether to bid on a deal.

## Folder Structure

```
NOS/
├── nos_parsing/                    # Extraction code
│   ├── __init__.py
│   ├── generate_reading_script.py  # PDF structural analysis (headers, tables, paragraphs)
│   └── vision_extract.py           # Vision-based field extraction prototype
└── nos_test_set/                   # Test data and ground truth
    ├── INSTRUCTIONS.md             # Full validation plan and ground truth format
    ├── test_ground_truth.txt       # Example ground truth file format
    ├── manifest.json               # Index of all 10 test PDFs
    ├── 01-10_*.pdf                 # 10 diverse NOS PDFs
    ├── 01-10_*_reading_script.txt  # Structural reading scripts (auto-generated)
    └── 01_*_ground_truth.txt       # Ground truth (started, needs completion)
```

## Scripts

### generate_reading_script.py

Analyzes a PDF's visual structure using `pdfplumber` — detects bold text (section headers), spatial column gaps (tables), paragraph groupings, footnotes, and form fields. Outputs a "reading script" that describes how the document is organized.

Used as a **routing layer**: the reading script tells the extraction system which pages contain which fields, so only relevant pages get sent to the model for each extraction target.

```bash
python3 NOS/nos_parsing/generate_reading_script.py <input.pdf> [output.txt]
```

### vision_extract.py

Prototype for vision-based field extraction. Renders PDF pages as images and sends them to a vision-capable LLM (Claude or GPT-4o) for extraction. Uses reading scripts to route each field to the most relevant pages, reducing token cost and noise.

```bash
# Dry run (show routing only, no LLM calls):
python3 NOS/nos_parsing/vision_extract.py <input.pdf> --dry-run

# With API key:
export ANTHROPIC_API_KEY=sk-ant-...
python3 NOS/nos_parsing/vision_extract.py <input.pdf>
```

## Test Set

10 NOS PDFs selected for maximum diversity across:
- 8 states (TX, OK, NJ, TN, UT, ME, IL, CA, VA)
- 8 issuer types (MUD, school district, borough, city GO, sales tax revenue, school GO, taxable GO, housing authority)
- Par range from $600K to $605M

See `nos_test_set/INSTRUCTIONS.md` for the full validation plan, ground truth file format, and next steps.

## Current Status

- Reading scripts generated for all 10 PDFs
- Ground truth file #01 (Harris County) started — needs extracted fields per page
- Ground truth files #02-10 not yet started
- Vision extraction concept validated manually but not yet automated
- No NOS-specific extraction pipeline built yet — ground truth files are the prerequisite

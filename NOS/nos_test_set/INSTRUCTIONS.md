# NOS Test Set — Extraction Validation Plan

## What This Is

A test set of 10 diverse Notice of Sale (NOS) PDFs from municipal bond issues, designed to benchmark different extraction approaches (text heuristics, LLM text extraction, vision-based extraction) against manually verified ground truth.

## The Problem We're Solving

PDF text extraction destroys visual layout information. The same dollar amount might be a par amount, a good faith deposit, or a maturity principal — and only the visual position on the page tells you which. Current extraction methods (regex heuristics + LLM on raw text) miss fields or misinterpret them because they can't see the document the way a human does.

## Proposed Architecture: Tiered Extraction

We're building toward a tiered extractor that uses the cheapest reliable method for each field:

1. **Tier 1 — Text heuristics** (regex, no model): For fields that are unambiguous in raw text (e.g., issuer name appears once in a clear pattern).
2. **Tier 2 — Vision model on targeted pages**: For fields where layout context matters (e.g., maturity schedule tables, distinguishing dollar amounts by position on the page).

The ground truth comparison tells us which tier each field belongs to. We don't guess — we measure.

## The 17 Fields We're Extracting

These are the target fields for each NOS document:

| Field | Description | Example (Harris County) |
|-------|-------------|------------------------|
| issuer | Full legal name of issuing entity | Harris County Municipal Utility District No. 182 |
| par_amount | Total par/principal amount | $2,930,000 |
| series | Series designation | Series 2026 |
| bond_type | Type of bonds | Unlimited Tax Bonds |
| dated_date | When interest begins accruing | May 1, 2026 |
| delivery_date | Expected delivery/closing date | May 14, 2026 |
| sale_date | Date bids are due / bonds sold | April 15, 2026 |
| tax_status | "tax-exempt" or "taxable" | tax-exempt |
| call_features | Redemption provisions (optional, mandatory sinking fund, callable prior to maturity) | optional_redemption, first call April 1, 2031 |
| maturity_schedule | Full table of year + principal amount | [{2029: $60,000}, {2030: $65,000}, ...] |
| financial_advisor | FA firm name | The GMS Group, L.L.C. |
| bond_counsel | Bond counsel law firm | Smith, Murdaugh, Little & Bonham, L.L.P. |
| paying_agent | Paying agent/registrar name and location | BOKF, N.A., Dallas, Texas |
| good_faith_deposit | Deposit amount and percentage | $58,600.00 (2% of par) |
| minimum_bid | Minimum bid as percentage of par | 97% of par value |
| max_interest_rate | Maximum net effective interest rate | 6.81% |
| rating | Bond rating or "None" | None — no application made |

## Ground Truth Files — How to Write Them

Each PDF gets a `_ground_truth.txt` file. The ground truth file has **two parts**:

### Part 1: Full Verbatim Text Transcription

The entire PDF rewritten as plain text, preserving every word, number, and table exactly as it appears in the document. This serves as the canonical reference for what the document actually says.

Guidelines:
- Transcribe every page, every paragraph, every table, every footnote
- Preserve the exact wording — don't paraphrase or summarize
- For tables, use consistent column-aligned formatting (spaces or tabs)
- Include blank form fields as they appear (e.g., `_______%`)
- Use page markers from the PDF: `'''PAGE 1:` etc. (as started in #01)
- Use section dividers between logical sections: `--------------------`
- If text crosses a page boundary mid-sentence, join it seamlessly

### Part 2: Extracted Field Values

At the **top or bottom** of the ground truth file (pick one and be consistent), add a structured block with the correct value for each of the 17 fields. This is what extraction output will be compared against.

Format:
```
=== EXTRACTED FIELDS (GROUND TRUTH) ===
issuer: Harris County Municipal Utility District No. 182
par_amount: $2,930,000
series: Series 2026
bond_type: Unlimited Tax Bonds
dated_date: May 1, 2026
delivery_date: May 14, 2026
sale_date: April 15, 2026
tax_status: tax-exempt
call_features: optional_redemption (first call April 1, 2031, bonds maturing on/after April 1, 2032, at par plus accrued); mandatory_sinking_fund_redemption (available at bidder election)
maturity_schedule: 2029:$60,000; 2030:$65,000; 2031:$65,000; 2032:$70,000; 2033:$75,000; 2034:$80,000; 2035:$80,000; 2036:$85,000; 2037:$90,000; 2038:$95,000; 2039:$100,000; 2040:$105,000; 2041:$110,000; 2042:$115,000; 2043:$120,000; 2044:$130,000; 2045:$135,000; 2046:$140,000; 2047:$150,000; 2048:$155,000; 2049:$165,000; 2050:$170,000; 2051:$180,000; 2052:$190,000; 2053:$200,000
financial_advisor: The GMS Group, L.L.C.
bond_counsel: Smith, Murdaugh, Little & Bonham, L.L.P.
paying_agent: BOKF, N.A., Dallas, Texas
good_faith_deposit: $58,600.00 (2%)
minimum_bid: 97%
max_interest_rate: 6.81%
rating: None
=== END EXTRACTED FIELDS ===
```

Rules for the extracted fields:
- Use `null` if the field is genuinely not present in the document
- Use the exact value as stated in the document — don't normalize dates or amounts
- For call_features, list each type separated by semicolons
- For maturity_schedule, use `year:amount` pairs separated by semicolons
- If a field is ambiguous, add a note in parentheses explaining the ambiguity

## What Exists So Far

### Files in nos_test_set/

| # | PDF | State | Par | Ground Truth | Reading Script |
|---|-----|-------|-----|-------------|----------------|
| 01 | Harris County MUD No. 182, TX | TX | $2.9M | Started (needs extracted fields section) | Done |
| 02 | Craig County ISD No. 6, OK | OK | $600K | Not started | Done |
| 03 | Dunellen Borough, NJ | NJ | $15.2M | Not started | Done |
| 04 | Gallatin City, TN | TN | $22.5M | Not started | Done |
| 05 | Hurricane City, UT | UT | $5.6M | Not started | Done |
| 06 | Regional School Unit No. 14, ME | ME | $50.8M | Not started | Done |
| 07 | SD No. 46 (Elgin), IL | IL | $81.1M | Not started | Done |
| 08 | San Francisco, CA | CA | $87.7M | Not started | Done |
| 09 | Virginia HDA, VA | VA | $17.9M | Not started | Done |
| 10 | Nashville Metro Gov't, TN | TN | $605M | Not started | Done |

### Scripts

- `NOS/nos_parsing/generate_reading_script.py` — Generates structural reading scripts from PDFs. Detects headers (bold text), tables (column gaps), paragraphs, footnotes, form fields. Used for page routing.
- `NOS/nos_parsing/vision_extract.py` — Vision-based field extraction prototype. Uses reading scripts to route fields to relevant pages, renders pages as images, sends to a vision-capable LLM. Supports Anthropic and OpenAI-compatible APIs. Currently requires an API key — local model support not yet built.
- `manifest.json` — Index of all 10 test PDFs with metadata and file paths.

## Next Steps (In Order)

1. **Complete ground truth files for all 10 PDFs** — both the full verbatim transcription and the extracted fields section. Claude can generate the initial transcription from each PDF; you review and correct it.

2. **Run text heuristic extraction on all 10** — use the existing `parse_remote_pdfs.py` logic (adapted to work on local PDFs) to extract what it can. Score each field against ground truth.

3. **Run vision extraction on all 10** — either via API, local model, or manually through Claude conversation. Score each field against ground truth.

4. **Compare results** — for each of the 17 fields, determine whether text heuristics or vision extraction is needed based on accuracy across the 10 documents.

5. **Build the tiered extractor** — a single script that uses text heuristics for fields that don't need vision, and vision for fields that do. The tier assignment comes from step 4, not from guessing.

## Key Design Decisions

- **Why 10 PDFs?** Enough diversity (8 states, 8 bond types, $600K-$605M par range) to catch formatting differences. Not so many that ground truth creation is impractical.
- **Why verbatim transcription + extracted fields?** The transcription lets you validate any extraction approach word-for-word. The extracted fields give a machine-comparable target for scoring.
- **Why reading scripts?** They serve as a chunking/routing layer — telling the extractor which pages to examine for each field. They reduce tokens sent to the model and improve accuracy by cutting noise. They are NOT sent alongside the text to the LLM (that was tested and found to dilute context rather than help).
- **Why vision?** Some fields (maturity schedules, table structures) require understanding visual layout that text extraction destroys. Vision models see what a human sees — column alignment, bold headers, table boundaries — and extract more accurately for those specific fields.

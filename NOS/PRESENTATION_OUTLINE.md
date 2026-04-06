# Capstone Presentation Outline

## Title
**LLM Multi-Agent Consensus for Municipal Bond Screening: Automating the Notice of Sale Gate**

## Target: ~20 minutes + Q&A

---

## Slide 1: The Problem
- Analysts receive dozens of NOS postings per week
- Each "Interested" decision triggers hours of POS review (100+ pages)
- No systematic triage — gut feel and manual reading
- *"The NOS is the first filter. If you can automate it, you save analysts from reading hundreds of pages they never should have opened."*

## Slide 2: The Competitive Sale Workflow
```
NOS → Screening Decision → POS Review → Credit Analysis → Bid Preparation → Auction
```
- This project focuses on the NOS screening stage
- The NOS establishes auction rules and bond structure (7-15 pages)
- The POS establishes credit quality (100+ pages)
- Screening = "Should we commit analyst time to this deal?"

## Slide 3: What's in a NOS?
- 55 features across 10 categories
- No standard format — varies by financial advisor template, state, issuer type
- Show taxonomy overview (NOS_FEATURE_TAXONOMY.md)
- Key point: despite format variation, the same core information is always present

## Slide 4: The Data Pipeline
1. NOS PDF → `pdftotext -layout` → raw text
2. Raw text + JSON schema → Claude API → structured JSON
3. Deterministic validation (par sum, GFD math, dates)
4. Retry on validation failure

Show: extraction accuracy across 10 diverse documents

## Slide 5: Why Multi-Agent?
Three honest reasons (not hand-wavy):
1. **Explainability at the dimension level** — 5 separate votes with 5 rationales, not one blended paragraph
2. **The veto problem** — single LLM hedges and softens dealbreakers into caveats. Hard veto rule solves this.
3. **Different context per agent** — in production, each agent has different proprietary data (order book, inventory, pipeline)

*"A single LLM could approximate this. MAS gives you decomposed reasoning, hard vetoes, and the architecture to plug in real firm data."*

## Slide 6: The Five Agents
| Agent | Question | Key NOS Fields | Firm Context |
|-------|----------|---------------|-------------|
| Sector Fit | "Our kind of deal?" | Issuer type, state, bond type | Coverage map |
| Size & Capital | "Can we afford it?" | Par amount, GFD | Capital limits |
| Structure | "Rules workable?" | Coupon constraints, basis of award | None (technical) |
| Distribution | "Can we sell it?" | Maturity, rating, BQ status | Investor demand |
| Calendar | "Have bandwidth?" | Sale date, delivery date | Pipeline, analysts |

## Slide 7: The Consensus Rule
- Rule 1: Any Pass ≥ 0.8 confidence → **PASS** (hard veto)
- Rule 2: All Interested → **INTERESTED**
- Rule 3: Mixed → **CONDITIONAL** with conditions
- Rule 4: Multiple low-confidence Pass → **CONDITIONAL** + escalation

*Deterministic Python, NOT another LLM call.*

## Slide 8: LIVE DEMO — Single NOS
Run Harris County MUD 182 ($2.9M TX GO) through both firm profiles.
Show the full output: 5 agent votes → consensus decision.

Texas firm: **INTERESTED** (unanimous)
Northeast firm: **PASS** (Sector Fit veto — TX not in coverage)

## Slide 9: LIVE DEMO — Multi-Scenario Grid
Show the 6-scenario × 4-firm grid:

| Deal | TX Regional | NE Institutional | National | Boutique |
|------|-------------|-----------------|----------|----------|
| TX MUD $2.9M | INTERESTED | PASS | INTERESTED | PASS |
| NJ BAN $15.2M | PASS | INTERESTED | INTERESTED | PASS |
| UT Revenue $5.6M | PASS | PASS | INTERESTED | PASS |
| CA Taxable $87.7M | PASS | PASS | INTERESTED | PASS |
| VA Housing $17.9M | PASS | INTERESTED | INTERESTED | PASS |
| TN Metro $204.6M | PASS | PASS | INTERESTED | PASS |

*"The same NOS gets different decisions because the firm profile is the variable."*

## Slide 10: Evaluation Results
- 10 diverse NOS documents (8 states, $600K-$605M)
- Field-level extraction accuracy against manually verified ground truth
- Validation checks catch LLM errors (par sum, GFD math)
- [Show accuracy numbers if live extraction has been run]

## Slide 11: Architecture Diagram
```
NOS PDF
  ↓
pdftotext -layout
  ↓
Claude API + JSON Schema → Validated NOS JSON
  ↓                              ↓
Sector Fit ─┐              Firm Profile JSON
Size & Cap ─┤
Structure  ─┤→ 5 Parallel Agent Calls
Distribution┤
Calendar   ─┘
  ↓
Deterministic Consensus Function
  ↓
INTERESTED / CONDITIONAL / PASS
```

## Slide 12: What This Project Demonstrates
1. NOS documents can be reliably extracted into structured data despite format variation
2. Five specialized agents each evaluate a different dimension, producing decomposed reasoning
3. The hard veto mechanism prevents false consensus that a single LLM would produce
4. The firm profile makes the system context-dependent — same deal, different firm, different answer
5. The architecture maps naturally to how real desks work (different people, different data, different judgments)

## Slide 13: Future Work
- **POS Stage**: Credit analysis consensus (different agents, different data, 100+ page documents)
- **Bid Preparation Stage**: Full adversarial debate (Market vs. Risk vs. Distribution converging on yields)
- **Real-Time Data**: Plug in actual MMD curves, order books, inventory positions
- **Backtesting**: MSRB competitive bidding dataset covers ~94% of competitive offerings

## Slide 14: Questions?

---

## Demo Commands (for presenter)

```bash
# Single NOS comparison (dry run):
python3 NOS/demo_compare.py --dry-run

# Multi-scenario grid:
python3 NOS/demo_compare.py --multi

# Full pipeline dry run:
python3 NOS/run_screening.py --dry-run --firm NOS/firm_profiles/texas_regional.json

# Live extraction (needs API key):
export ANTHROPIC_API_KEY=sk-...
python3 NOS/run_screening.py NOS/nos_test_set/NOS_Test_PDFs/01_Harris_County_MUD_No_182,_TX_Unlimited_Tax_Bonds,_Srs_2026.pdf --firm NOS/firm_profiles/texas_regional.json
```

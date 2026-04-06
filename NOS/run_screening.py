#!/usr/bin/env python3
"""
NOS Screening Pipeline — End-to-End Runner

Ties together:
  1. Text extraction (pdftotext -layout)
  2. LLM structured extraction (Claude/OpenAI)
  3. Deterministic validation
  4. 5-agent parallel screening
  5. Consensus decision

Usage:
    # Full pipeline from PDF:
    export ANTHROPIC_API_KEY=sk-...
    python3 run_screening.py nos.pdf --firm firm_profiles/texas_regional.json

    # From pre-extracted JSON (skip extraction steps):
    python3 run_screening.py --nos-json extracted.json --firm firm_profiles/texas_regional.json

    # Demo: run same NOS with two firm profiles to show consensus flip:
    python3 run_screening.py nos.pdf --firm firm_profiles/texas_regional.json
    python3 run_screening.py nos.pdf --firm firm_profiles/northeast_institutional.json

    # Dry run (no LLM calls) to test plumbing:
    python3 run_screening.py --nos-json sample.json --firm firm.json --dry-run
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))
sys.path.insert(0, str(Path(__file__).parent / "nos_agents"))


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(
    pdf_path: str | None = None,
    nos_json_path: str | None = None,
    firm_profile_path: str = None,
    provider: str = "anthropic",
    max_retries: int = 1,
    output_dir: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Run the full NOS screening pipeline.

    Either pdf_path OR nos_json_path must be provided.
    firm_profile_path is required.
    """
    from agents import run_all_agents, AGENT_DEFINITIONS
    from consensus import compute_consensus, format_consensus_report

    timestamp = datetime.now().isoformat(timespec="seconds")

    # ── Step 1: Get NOS extraction ──────────────────────────────
    if nos_json_path:
        print(f"Loading pre-extracted NOS JSON: {nos_json_path}", file=sys.stderr)
        nos_data = load_json(nos_json_path)
        # Handle both raw extraction and wrapped output from llm_extract
        nos_json = nos_data.get("extraction", nos_data)
        source = nos_json_path
    elif pdf_path:
        if dry_run:
            print("DRY RUN: Skipping PDF extraction (no LLM calls)", file=sys.stderr)
            nos_json = _sample_nos_json()
            source = "dry_run_sample"
        else:
            from llm_extract import extract_nos
            print(f"Extracting from PDF: {pdf_path}", file=sys.stderr)
            result = extract_nos(pdf_path, provider=provider, max_retries=max_retries)
            nos_json = result["extraction"]
            source = pdf_path

            if result["validation_errors"]:
                print(f"\nWARNING: Extraction has {len(result['validation_errors'])} validation errors",
                      file=sys.stderr)
    elif dry_run:
        print("DRY RUN: Using sample NOS data", file=sys.stderr)
        nos_json = _sample_nos_json()
        source = "dry_run_sample"
    else:
        raise ValueError("Either --pdf or --nos-json must be provided")

    # ── Step 2: Load firm profile ───────────────────────────────
    if not firm_profile_path:
        raise ValueError("--firm is required")
    firm_profile = load_json(firm_profile_path)
    firm_name = firm_profile.get("firm_name", "Unknown Firm")
    print(f"\nFirm profile: {firm_name}", file=sys.stderr)

    # ── Step 3: Run validation on NOS JSON ──────────────────────
    from validate import validate_nos
    validation_errors = validate_nos(nos_json)
    if validation_errors:
        print(f"\nNOS validation: {len(validation_errors)} issues", file=sys.stderr)
        for e in validation_errors:
            print(f"  - {e}", file=sys.stderr)
    else:
        print(f"\nNOS validation: all checks passed", file=sys.stderr)

    # ── Step 4: Run screening agents ────────────────────────────
    if dry_run:
        print("\nDRY RUN: Generating votes from NOS + firm profile", file=sys.stderr)
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from demo_compare import _generate_demo_votes
            votes = _generate_demo_votes(nos_json, firm_profile)
        except ImportError:
            print("  (demo_compare not available, using static sample)", file=sys.stderr)
            votes = _sample_votes()
    else:
        print(f"\n{'─' * 60}", file=sys.stderr)
        print("RUNNING SCREENING AGENTS", file=sys.stderr)
        print(f"{'─' * 60}", file=sys.stderr)
        votes = run_all_agents(nos_json, firm_profile, provider=provider)

    # ── Step 5: Compute consensus ───────────────────────────────
    consensus = compute_consensus(votes)

    # ── Step 6: Format and output results ───────────────────────
    print(f"\n{format_consensus_report(consensus)}", file=sys.stderr)

    # Build full output
    output = {
        "timestamp": timestamp,
        "source": str(source),
        "firm_profile": firm_name,
        "firm_profile_path": str(firm_profile_path),
        "provider": provider,
        "nos_summary": {
            "issuer": _safe_get(nos_json, "issuer.name"),
            "state": _safe_get(nos_json, "issuer.state"),
            "par_amount": _safe_get(nos_json, "bond_identification.par_amount"),
            "bond_type": _safe_get(nos_json, "bond_identification.bond_type_description",
                                   _safe_get(nos_json, "bond_identification.bond_type")),
            "sale_date": _safe_get(nos_json, "sale_logistics.sale_date"),
            "tax_status": _safe_get(nos_json, "bond_identification.tax_status"),
        },
        "validation_errors": validation_errors,
        "consensus": {
            "decision": consensus["decision"],
            "rule_applied": consensus["rule_applied"],
            "reason": consensus["reason"],
            "conditions": consensus["conditions"],
            "escalation": consensus["escalation"],
        },
        "agent_votes": votes,
        "nos_extraction": nos_json,
    }

    # Save output
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        safe_name = firm_name.replace(" ", "_").lower()[:30]
        out_path = os.path.join(output_dir, f"screening_{safe_name}_{timestamp.replace(':', '-')}.json")
    else:
        if pdf_path:
            stem = Path(pdf_path).stem
        elif nos_json_path:
            stem = Path(nos_json_path).stem.replace("_nos_extract", "")
        else:
            stem = "screening"
        safe_firm = firm_name.replace(" ", "_").lower()[:20]
        out_path = f"{stem}_screening_{safe_firm}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull results saved to: {out_path}", file=sys.stderr)

    return output


def _safe_get(obj, path, default=None):
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
        if current is None:
            return default
    return current


def _sample_nos_json() -> dict:
    """Sample NOS JSON for dry-run testing."""
    return {
        "issuer": {
            "name": "Harris County Municipal Utility District No. 182",
            "type": "municipal_utility_district",
            "state": "TX",
            "county": "Harris"
        },
        "bond_identification": {
            "series": "Series 2026",
            "bond_type": "go_unlimited_tax",
            "bond_type_description": "Unlimited Tax Bonds",
            "par_amount": 2930000,
            "tax_status": "tax_exempt",
            "bank_qualified": None,
            "purpose": "construction and improvements"
        },
        "sale_logistics": {
            "sale_date": "April 15, 2026",
            "sale_time": "11:00 AM CST",
            "bidding_platform": "parity",
            "bidding_platform_name": "PARITY Electronic Bid Submission System",
            "bid_format": "electronic_only",
            "right_to_reject": True,
            "pre_sale_adjustment": None,
            "financial_advisor": "The GMS Group, L.L.C."
        },
        "maturity_structure": {
            "maturity_type": "serial_only",
            "dated_date": "May 1, 2026",
            "interest_payment_dates": "April 1 and October 1",
            "first_interest_payment": "April 1, 2027",
            "maturity_schedule": [
                {"date": "2029", "amount": 60000, "type": "serial"},
                {"date": "2030", "amount": 65000, "type": "serial"},
                {"date": "2031", "amount": 65000, "type": "serial"},
                {"date": "2032", "amount": 70000, "type": "serial"},
                {"date": "2033", "amount": 75000, "type": "serial"},
                {"date": "2034", "amount": 80000, "type": "serial"},
                {"date": "2035", "amount": 80000, "type": "serial"},
                {"date": "2036", "amount": 85000, "type": "serial"},
                {"date": "2037", "amount": 90000, "type": "serial"},
                {"date": "2038", "amount": 95000, "type": "serial"},
                {"date": "2039", "amount": 100000, "type": "serial"},
                {"date": "2040", "amount": 105000, "type": "serial"},
                {"date": "2041", "amount": 110000, "type": "serial"},
                {"date": "2042", "amount": 115000, "type": "serial"},
                {"date": "2043", "amount": 120000, "type": "serial"},
                {"date": "2044", "amount": 130000, "type": "serial"},
                {"date": "2045", "amount": 135000, "type": "serial"},
                {"date": "2046", "amount": 140000, "type": "serial"},
                {"date": "2047", "amount": 150000, "type": "serial"},
                {"date": "2048", "amount": 155000, "type": "serial"},
                {"date": "2049", "amount": 165000, "type": "serial"},
                {"date": "2050", "amount": 170000, "type": "serial"},
                {"date": "2051", "amount": 180000, "type": "serial"},
                {"date": "2052", "amount": 190000, "type": "serial"},
                {"date": "2053", "amount": 200000, "type": "serial"}
            ],
            "final_maturity_date": "April 1, 2053",
            "bidder_term_bond_option": True,
            "mandatory_sinking_fund": None,
            "number_of_maturities": 25,
            "total_bond_years": None,
            "average_maturity": None
        },
        "coupon_provisions": {
            "interest_payment_frequency": "semiannual",
            "interest_calculation_basis": None,
            "coupon_rate_constraints": {
                "ascending_only": None,
                "no_zero_coupon": None,
                "max_rate_cap": None,
                "max_number_of_rates": None,
                "no_restrictions": None
            },
            "rate_increment": "1/8 of 1%",
            "uniform_rate_per_maturity": True
        },
        "bid_evaluation": {
            "basis_of_award": "net_effective_rate",
            "good_faith_deposit": {
                "amount": 58600.0,
                "percentage_of_par": 2.0,
                "form": "cashiers_check"
            },
            "premium_discount_permitted": None,
            "minimum_bid_price": 97.0,
            "maximum_bid_price": None,
            "max_interest_rate": 6.81,
            "issue_price_requirements": None
        },
        "redemption": {
            "optional_redemption": "callable",
            "first_call_date": "April 1, 2031",
            "call_price": 100,
            "call_protection_years": 5,
            "extraordinary_redemption": None
        },
        "registration_delivery": {
            "book_entry": "book_entry_only",
            "denomination": 5000,
            "paying_agent": "BOKF, N.A., Dallas, Texas",
            "delivery_date": "May 14, 2026",
            "latest_delivery_date": None,
            "delivery_method": "dtc_fast",
            "cusip": None
        },
        "credit_enhancement": {
            "credit_rating": "unrated",
            "bond_insurance": None,
            "insurance_provider_restrictions": None
        },
        "legal_advisory": {
            "bond_counsel": "Smith, Murdaugh, Little & Bonham, L.L.P.",
            "disclosure_counsel": None,
            "tax_counsel": None,
            "legal_opinion_type": None,
            "continuing_disclosure": None
        },
        "bidder_obligations": {
            "commitment_type": "firm_commitment",
            "reoffering_price_certification": None,
            "official_statement_responsibility": None,
            "technology_risk_allocation": None,
            "withdrawal_restrictions": None
        }
    }


def _sample_votes() -> list[dict]:
    """Sample agent votes for dry-run testing."""
    return [
        {
            "agent": "sector_fit",
            "vote": "interested",
            "confidence": 0.95,
            "rationale": "Texas MUD GO unlimited tax — core coverage area and issuer type.",
            "conditions": []
        },
        {
            "agent": "size_capital",
            "vote": "interested",
            "confidence": 0.9,
            "rationale": "$2.93M par well within $25M single commitment limit. Good faith deposit of $58,600 is trivial.",
            "conditions": []
        },
        {
            "agent": "structure",
            "vote": "interested",
            "confidence": 0.85,
            "rationale": "Standard serial structure, net effective rate basis (standard for Texas), 1/8% rate increment, 97% min bid — clean and workable.",
            "conditions": []
        },
        {
            "agent": "distribution",
            "vote": "interested",
            "confidence": 0.88,
            "rationale": "Small tax-exempt deal with 1-27yr serial range. Sweet spot for retail distribution. Unrated but typical for Texas MUDs.",
            "conditions": []
        },
        {
            "agent": "calendar",
            "vote": "interested",
            "confidence": 0.82,
            "rationale": "Sale April 15 — 9 days out, sufficient for POS review. Only 1 other bid that week. 2 analysts available.",
            "conditions": []
        }
    ]


def main():
    parser = argparse.ArgumentParser(
        description="NOS Screening Pipeline — End-to-End Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline from PDF:
  python3 run_screening.py nos.pdf --firm firm_profiles/texas_regional.json

  # From pre-extracted JSON:
  python3 run_screening.py --nos-json extracted.json --firm firm_profiles/texas_regional.json

  # Dry run (no LLM calls):
  python3 run_screening.py --dry-run --firm firm_profiles/texas_regional.json

  # Compare two firms on same NOS:
  python3 run_screening.py nos.pdf --firm firm_profiles/texas_regional.json
  python3 run_screening.py nos.pdf --firm firm_profiles/northeast_institutional.json
"""
    )
    parser.add_argument("pdf", nargs="?", help="Path to NOS PDF file")
    parser.add_argument("--nos-json", help="Path to pre-extracted NOS JSON (skip extraction)")
    parser.add_argument("--firm", required=True, help="Path to firm profile JSON")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--max-retries", type=int, default=1, help="Max LLM retry attempts")
    parser.add_argument("--output-dir", help="Directory for output files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use sample data instead of calling LLMs")
    args = parser.parse_args()

    if not args.pdf and not args.nos_json and not args.dry_run:
        parser.error("Either a PDF path, --nos-json, or --dry-run is required")

    result = run_pipeline(
        pdf_path=args.pdf,
        nos_json_path=args.nos_json,
        firm_profile_path=args.firm,
        provider=args.provider,
        max_retries=args.max_retries,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )

    # Print summary to stdout
    print(json.dumps({
        "decision": result["consensus"]["decision"],
        "firm": result["firm_profile"],
        "issuer": result["nos_summary"]["issuer"],
        "par_amount": result["nos_summary"]["par_amount"],
        "conditions": result["consensus"]["conditions"],
        "escalation": result["consensus"]["escalation"],
    }, indent=2))


if __name__ == "__main__":
    main()

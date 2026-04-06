#!/usr/bin/env python3
"""
NOS Screening Demo — Firm Profile Comparison

Runs the same NOS through two firm profiles side by side to demonstrate
how the multi-agent consensus flips based on who's evaluating the deal.

This is the key demo moment: a $2.9M Texas MUD is INTERESTED for a
Texas-focused regional firm and PASS for a Northeast-only firm.
The firm profile is the variable, not the agents.

Usage:
    # Dry run (no API calls, uses sample data):
    python3 demo_compare.py --dry-run

    # Live with API:
    export ANTHROPIC_API_KEY=sk-...
    python3 demo_compare.py path/to/nos.pdf

    # From pre-extracted JSON:
    python3 demo_compare.py --nos-json path/to/extracted.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))
sys.path.insert(0, str(Path(__file__).parent / "nos_agents"))


FIRM_PROFILES_DIR = Path(__file__).parent / "firm_profiles"

# Demo firm profiles
DEMO_PROFILES = [
    FIRM_PROFILES_DIR / "texas_regional.json",
    FIRM_PROFILES_DIR / "northeast_institutional.json",
]


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def run_demo(
    pdf_path: str | None = None,
    nos_json_path: str | None = None,
    firm_profiles: list[str] | None = None,
    provider: str = "anthropic",
    dry_run: bool = False,
):
    """Run side-by-side comparison of the same NOS with different firm profiles."""
    from consensus import compute_consensus, format_consensus_report

    # Load NOS data
    if nos_json_path:
        nos_data = load_json(nos_json_path)
        nos_json = nos_data.get("extraction", nos_data)
        source = nos_json_path
    elif pdf_path and not dry_run:
        from llm_extract import extract_nos
        result = extract_nos(pdf_path, provider=provider)
        nos_json = result["extraction"]
        source = pdf_path
    else:
        # Use embedded sample for dry run
        from run_screening import _sample_nos_json
        nos_json = _sample_nos_json()
        source = "sample (Harris County MUD 182)"

    # Resolve firm profiles
    if firm_profiles is None:
        firm_profiles = [str(p) for p in DEMO_PROFILES]

    # Print NOS summary
    issuer = _safe_get(nos_json, "issuer.name", "Unknown")
    state = _safe_get(nos_json, "issuer.state", "?")
    par = _safe_get(nos_json, "bond_identification.par_amount", 0)
    bond_type = _safe_get(nos_json, "bond_identification.bond_type_description",
                          _safe_get(nos_json, "bond_identification.bond_type", "?"))
    tax_status = _safe_get(nos_json, "bond_identification.tax_status", "?")
    sale_date = _safe_get(nos_json, "sale_logistics.sale_date", "?")

    print(f"""
{'#' * 70}
NOS SCREENING DEMO — FIRM PROFILE COMPARISON
{'#' * 70}

NOTICE OF SALE:
  Issuer:     {issuer}
  State:      {state}
  Par Amount: ${par:,.0f}
  Bond Type:  {bond_type}
  Tax Status: {tax_status}
  Sale Date:  {sale_date}
  Source:     {source}
""")

    results = []

    for i, profile_path in enumerate(firm_profiles):
        profile = load_json(profile_path)
        firm_name = profile.get("firm_name", f"Firm {i+1}")

        print(f"{'=' * 70}")
        print(f"FIRM {i+1}: {firm_name}")
        print(f"{'=' * 70}")

        if dry_run:
            # Generate realistic sample votes based on firm profile
            votes = _generate_demo_votes(nos_json, profile)
        else:
            from agents import run_all_agents
            votes = run_all_agents(nos_json, profile, provider=provider)

        consensus = compute_consensus(votes)
        print(format_consensus_report(consensus))
        print()

        results.append({
            "firm": firm_name,
            "profile_path": str(profile_path),
            "decision": consensus["decision"],
            "rule": consensus["rule_applied"],
            "reason": consensus["reason"],
            "escalation": consensus["escalation"],
            "votes": votes,
        })

    # Print comparison summary
    print(f"\n{'#' * 70}")
    print("COMPARISON SUMMARY")
    print(f"{'#' * 70}")
    print(f"\n  NOS: {issuer} ({state}, ${par:,.0f} {bond_type})\n")

    for r in results:
        decision = r["decision"]
        marker = {"INTERESTED": "[GREEN]", "CONDITIONAL": "[AMBER]", "PASS": "[RED]"}
        print(f"  {r['firm']:40s} → {marker.get(decision, '')} {decision}")
        if r.get("escalation"):
            print(f"  {'':40s}   (escalation flag)")

    decisions = [r["decision"] for r in results]
    if len(set(decisions)) > 1:
        print(f"\n  >>> CONSENSUS FLIPS across firm profiles <<<")
        print(f"  This demonstrates that the screening decision depends on the firm,")
        print(f"  not just the deal. The agents evaluate the same NOS differently")
        print(f"  because they have different firm context.")
    else:
        print(f"\n  >>> Same decision across all profiles: {decisions[0]}")

    print(f"\n{'#' * 70}")

    # Save output
    output = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "nos_summary": {
            "issuer": issuer, "state": state, "par_amount": par,
            "bond_type": bond_type, "tax_status": tax_status,
        },
        "comparisons": results,
        "consensus_flipped": len(set(decisions)) > 1,
    }

    out_path = "demo_comparison.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results: {out_path}")

    return output


def _generate_demo_votes(nos_json: dict, firm_profile: dict) -> list[dict]:
    """
    Generate realistic demo votes based on NOS fields + firm profile.
    Used for dry-run mode to show how the consensus would flip.
    """
    issuer_state = _safe_get(nos_json, "issuer.state", "")
    issuer_type = _safe_get(nos_json, "issuer.type", "")
    par_amount = _safe_get(nos_json, "bond_identification.par_amount", 0)
    tax_status = _safe_get(nos_json, "bond_identification.tax_status", "")

    covered_states = firm_profile.get("sector_coverage", {}).get("states", [])
    covered_types = firm_profile.get("sector_coverage", {}).get("issuer_types", [])
    max_commitment = firm_profile.get("capital_limits", {}).get("max_single_commitment_dollars", 0)
    distribution_strength = firm_profile.get("distribution_profile", {}).get("strength", "")
    taxable_demand = firm_profile.get("distribution_profile", {}).get("taxable_demand", "")

    votes = []

    # Agent 1: Sector Fit
    if issuer_state in covered_states and issuer_type in covered_types:
        votes.append({
            "agent": "sector_fit", "vote": "interested", "confidence": 0.95,
            "rationale": f"{issuer_state} {issuer_type} is core coverage.",
            "conditions": []
        })
    elif issuer_state in covered_states:
        votes.append({
            "agent": "sector_fit", "vote": "conditional", "confidence": 0.6,
            "rationale": f"State {issuer_state} is covered but {issuer_type} is not a primary issuer type.",
            "conditions": [f"Confirm appetite for {issuer_type} deals"]
        })
    else:
        votes.append({
            "agent": "sector_fit", "vote": "pass", "confidence": 0.95,
            "rationale": f"{issuer_state} is outside the firm's geographic coverage ({', '.join(covered_states[:5])}).",
            "conditions": []
        })

    # Agent 2: Size & Capital
    if par_amount <= max_commitment * 0.5:
        votes.append({
            "agent": "size_capital", "vote": "interested", "confidence": 0.9,
            "rationale": f"${par_amount:,.0f} well within ${max_commitment:,.0f} limit.",
            "conditions": []
        })
    elif par_amount <= max_commitment:
        votes.append({
            "agent": "size_capital", "vote": "conditional", "confidence": 0.7,
            "rationale": f"${par_amount:,.0f} is within limit but uses significant capacity.",
            "conditions": ["Monitor inventory levels through settlement"]
        })
    else:
        votes.append({
            "agent": "size_capital", "vote": "pass", "confidence": 0.85,
            "rationale": f"${par_amount:,.0f} exceeds ${max_commitment:,.0f} max commitment.",
            "conditions": []
        })

    # Agent 3: Structure (firm-independent)
    votes.append({
        "agent": "structure", "vote": "interested", "confidence": 0.85,
        "rationale": "Standard serial structure, workable constraints.",
        "conditions": []
    })

    # Agent 4: Distribution
    if tax_status == "taxable" and taxable_demand in ("Weak", "weak"):
        votes.append({
            "agent": "distribution", "vote": "pass", "confidence": 0.8,
            "rationale": "Taxable bonds with weak taxable investor base.",
            "conditions": []
        })
    elif distribution_strength == "retail" and par_amount < 20000000:
        votes.append({
            "agent": "distribution", "vote": "interested", "confidence": 0.88,
            "rationale": f"${par_amount:,.0f} fits retail distribution sweet spot.",
            "conditions": []
        })
    elif distribution_strength == "institutional" and par_amount < 10000000:
        votes.append({
            "agent": "distribution", "vote": "conditional", "confidence": 0.55,
            "rationale": f"${par_amount:,.0f} is below institutional sweet spot. Retail-heavy deal.",
            "conditions": ["May need retail distribution partner"]
        })
    else:
        votes.append({
            "agent": "distribution", "vote": "interested", "confidence": 0.75,
            "rationale": "Distribution feasible with current accounts.",
            "conditions": []
        })

    # Agent 5: Calendar
    votes.append({
        "agent": "calendar", "vote": "interested", "confidence": 0.82,
        "rationale": "Sufficient time and analyst availability.",
        "conditions": []
    })

    return votes


def main():
    parser = argparse.ArgumentParser(
        description="NOS Screening Demo — Firm Profile Comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf", nargs="?", help="Path to NOS PDF file")
    parser.add_argument("--nos-json", help="Pre-extracted NOS JSON")
    parser.add_argument("--firm", action="append", help="Firm profile JSON (can repeat)")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--dry-run", action="store_true", help="Use sample data")
    args = parser.parse_args()

    if not args.pdf and not args.nos_json and not args.dry_run:
        parser.error("Provide a PDF, --nos-json, or --dry-run")

    run_demo(
        pdf_path=args.pdf,
        nos_json_path=args.nos_json,
        firm_profiles=args.firm,
        provider=args.provider,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate a formatted screening report for a NOS document.

Produces a standalone text report suitable for presentation or review,
showing the NOS summary, all 5 agent votes, and the consensus decision.

Usage:
    # From ground truth JSON (dry-run, no API needed):
    python3 generate_report.py NOS/nos_test_set/ground_truth/01_ground_truth.json --firm NOS/firm_profiles/texas_regional.json

    # All ground truth files through all firm profiles:
    python3 generate_report.py --all

    # Live extraction:
    export ANTHROPIC_API_KEY=sk-...
    python3 generate_report.py nos.pdf --firm NOS/firm_profiles/texas_regional.json --live
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))
sys.path.insert(0, str(Path(__file__).parent / "nos_agents"))
sys.path.insert(0, str(Path(__file__).parent))


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


def generate_report(nos_json: dict, firm_profile: dict, votes: list[dict], consensus: dict) -> str:
    """Generate a formatted text report."""
    lines = []
    firm_name = firm_profile.get("firm_name", "Unknown")

    # Header
    issuer = _safe_get(nos_json, "issuer.name", "Unknown")
    state = _safe_get(nos_json, "issuer.state", "?")
    par = _safe_get(nos_json, "bond_identification.par_amount", 0)
    bond_type = _safe_get(nos_json, "bond_identification.bond_type_description",
                          _safe_get(nos_json, "bond_identification.bond_type", "?"))
    tax_status = _safe_get(nos_json, "bond_identification.tax_status", "?")
    sale_date = _safe_get(nos_json, "sale_logistics.sale_date", "?")
    maturity_type = _safe_get(nos_json, "maturity_structure.maturity_type", "?")
    n_mats = len(_safe_get(nos_json, "maturity_structure.maturity_schedule", []))
    basis = _safe_get(nos_json, "bid_evaluation.basis_of_award", "?")
    call = _safe_get(nos_json, "redemption.optional_redemption", "?")
    rating = _safe_get(nos_json, "credit_enhancement.credit_rating", "not stated")
    fa = _safe_get(nos_json, "sale_logistics.financial_advisor", "not stated")
    counsel = _safe_get(nos_json, "legal_advisory.bond_counsel", "not stated")

    decision = consensus["decision"]
    decision_mark = {"INTERESTED": "[+]", "CONDITIONAL": "[?]", "PASS": "[X]"}.get(decision, "[ ]")

    lines.append(f"{'=' * 72}")
    lines.append(f"NOS SCREENING REPORT")
    lines.append(f"{'=' * 72}")
    lines.append(f"")
    lines.append(f"Date:          {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Firm:          {firm_name}")
    lines.append(f"")
    lines.append(f"{'─' * 72}")
    lines.append(f"DEAL SUMMARY")
    lines.append(f"{'─' * 72}")
    lines.append(f"  Issuer:           {issuer}")
    lines.append(f"  State:            {state}")
    lines.append(f"  Par Amount:       ${par:,.0f}")
    lines.append(f"  Bond Type:        {bond_type}")
    lines.append(f"  Tax Status:       {tax_status}")
    lines.append(f"  Sale Date:        {sale_date}")
    lines.append(f"  Maturity Type:    {maturity_type} ({n_mats} maturities)")
    lines.append(f"  Basis of Award:   {basis}")
    lines.append(f"  Call Provisions:  {call}")
    lines.append(f"  Rating:           {rating}")
    lines.append(f"  Financial Advisor:{fa}")
    lines.append(f"  Bond Counsel:     {counsel}")
    lines.append(f"")

    # Maturity schedule summary
    schedule = _safe_get(nos_json, "maturity_structure.maturity_schedule", [])
    if schedule:
        first = schedule[0]
        last = schedule[-1]
        lines.append(f"  Maturity Range:   {first.get('date', '?')} to {last.get('date', '?')}")
        smallest = min(m.get("amount", 0) for m in schedule)
        largest = max(m.get("amount", 0) for m in schedule)
        lines.append(f"  Amount Range:     ${smallest:,.0f} to ${largest:,.0f}")

    # Decision
    lines.append(f"")
    lines.append(f"{'=' * 72}")
    lines.append(f"SCREENING DECISION: {decision_mark} {decision}")
    lines.append(f"{'=' * 72}")
    lines.append(f"  Rule:      {consensus.get('rule_applied', '?')}")
    lines.append(f"  Reason:    {consensus.get('reason', '?')}")
    if consensus.get("escalation"):
        lines.append(f"  *** ESCALATION: Human review recommended ***")
    if consensus.get("conditions"):
        lines.append(f"  Conditions:")
        for c in consensus["conditions"]:
            lines.append(f"    - {c}")

    # Agent votes
    lines.append(f"")
    lines.append(f"{'─' * 72}")
    lines.append(f"AGENT VOTES")
    lines.append(f"{'─' * 72}")

    agent_names = {
        "sector_fit": "Sector Fit",
        "size_capital": "Size & Capital",
        "structure": "Structure",
        "distribution": "Distribution",
        "calendar": "Calendar"
    }

    for v in votes:
        name = agent_names.get(v["agent"], v["agent"])
        vote = v["vote"].upper()
        conf = v["confidence"]
        vote_mark = {"INTERESTED": "+", "CONDITIONAL": "?", "PASS": "X"}.get(vote, " ")
        lines.append(f"")
        lines.append(f"  [{vote_mark}] {name:20s}  {vote:12s}  (confidence: {conf:.2f})")
        lines.append(f"      {v.get('rationale', '')}")
        for c in v.get("conditions", []):
            lines.append(f"      Condition: {c}")

    lines.append(f"")
    lines.append(f"{'=' * 72}")

    return "\n".join(lines)


def screen_nos(nos_json: dict, firm_profile: dict, live: bool = False, provider: str = "anthropic") -> str:
    """Screen a NOS and return formatted report."""
    from consensus import compute_consensus

    if live:
        from agents import run_all_agents
        votes = run_all_agents(nos_json, firm_profile, provider=provider)
    else:
        from demo_compare import _generate_demo_votes
        votes = _generate_demo_votes(nos_json, firm_profile)

    consensus = compute_consensus(votes)
    return generate_report(nos_json, firm_profile, votes, consensus)


def run_all_reports():
    """Generate reports for all ground truth files × all firm profiles."""
    gt_dir = Path(__file__).parent / "nos_test_set" / "ground_truth"
    firm_dir = Path(__file__).parent / "firm_profiles"

    gt_files = sorted(gt_dir.glob("*_ground_truth.json"))
    firm_files = sorted(firm_dir.glob("*.json"))

    for gt_file in gt_files:
        with open(gt_file) as f:
            nos = json.load(f)

        issuer = _safe_get(nos, "issuer.name", "?")
        state = _safe_get(nos, "issuer.state", "?")
        par = _safe_get(nos, "bond_identification.par_amount", 0)

        print(f"\n{'#' * 72}")
        print(f"# {issuer} ({state}, ${par:,.0f})")
        print(f"{'#' * 72}")

        for firm_file in firm_files:
            with open(firm_file) as f:
                firm = json.load(f)
            report = screen_nos(nos, firm)
            print(f"\n{report}")


def main():
    parser = argparse.ArgumentParser(description="Generate NOS Screening Report")
    parser.add_argument("nos_json", nargs="?", help="NOS JSON file (ground truth or extraction)")
    parser.add_argument("--firm", help="Firm profile JSON")
    parser.add_argument("--live", action="store_true", help="Use live LLM agents")
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--all", action="store_true", help="Run all GT × all firms")
    parser.add_argument("--output", "-o", help="Output file")
    args = parser.parse_args()

    if args.all:
        run_all_reports()
        return

    if not args.nos_json or not args.firm:
        parser.error("Provide NOS JSON + --firm, or use --all")

    with open(args.nos_json) as f:
        nos = json.load(f)
    nos = nos.get("extraction", nos)

    with open(args.firm) as f:
        firm = json.load(f)

    report = screen_nos(nos, firm, live=args.live, provider=args.provider)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()

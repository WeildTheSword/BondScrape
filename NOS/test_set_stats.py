#!/usr/bin/env python3
"""
NOS Test Set Statistics

Summarizes the diversity and coverage of the 10-document test set.
Useful for presentations to show the range of documents tested.

Usage:
    python3 test_set_stats.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))


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


def main():
    gt_dir = Path(__file__).parent / "nos_test_set" / "ground_truth"
    gt_files = sorted(gt_dir.glob("*_ground_truth.json"))

    if not gt_files:
        print("No ground truth files found.")
        return

    docs = []
    for f in gt_files:
        with open(f) as fh:
            docs.append(json.load(fh))

    print(f"{'=' * 72}")
    print(f"NOS TEST SET STATISTICS — {len(docs)} Documents")
    print(f"{'=' * 72}")

    # States
    states = [_safe_get(d, "issuer.state", "?") for d in docs]
    print(f"\nStates ({len(set(states))} unique): {', '.join(sorted(set(states)))}")

    # Issuer types
    types = [_safe_get(d, "issuer.type", "?") for d in docs]
    type_counts = Counter(types)
    print(f"\nIssuer Types ({len(set(types))} unique):")
    for t, c in type_counts.most_common():
        print(f"  {t:35s} {c}")

    # Bond types
    bond_types = [_safe_get(d, "bond_identification.bond_type", "?") for d in docs]
    bt_counts = Counter(bond_types)
    print(f"\nBond Types ({len(set(bond_types))} unique):")
    for t, c in bt_counts.most_common():
        print(f"  {t:35s} {c}")

    # Par amounts
    pars = [_safe_get(d, "bond_identification.par_amount", 0) for d in docs]
    print(f"\nPar Amount Range:")
    print(f"  Minimum:  ${min(pars):>15,.0f}")
    print(f"  Maximum:  ${max(pars):>15,.0f}")
    print(f"  Median:   ${sorted(pars)[len(pars)//2]:>15,.0f}")
    print(f"  Total:    ${sum(pars):>15,.0f}")

    # Tax status
    tax = [_safe_get(d, "bond_identification.tax_status", "?") for d in docs]
    tax_counts = Counter(tax)
    print(f"\nTax Status:")
    for t, c in tax_counts.most_common():
        print(f"  {t:35s} {c}")

    # Maturity structure
    mat_types = [_safe_get(d, "maturity_structure.maturity_type", "?") for d in docs]
    n_mats = [len(_safe_get(d, "maturity_structure.maturity_schedule", [])) for d in docs]
    print(f"\nMaturity Structure:")
    for t, c in Counter(mat_types).most_common():
        print(f"  {t:35s} {c}")
    print(f"  Maturity count range: {min(n_mats)} to {max(n_mats)}")

    # Basis of award
    basis = [_safe_get(d, "bid_evaluation.basis_of_award", "?") for d in docs]
    print(f"\nBasis of Award:")
    for t, c in Counter(basis).most_common():
        print(f"  {t:35s} {c}")

    # Call provisions
    calls = [_safe_get(d, "redemption.optional_redemption", "?") for d in docs]
    print(f"\nCall Provisions:")
    for t, c in Counter(calls).most_common():
        print(f"  {t:35s} {c}")

    # Ratings
    ratings = [_safe_get(d, "credit_enhancement.credit_rating") for d in docs]
    rated = sum(1 for r in ratings if r and r != "unrated" and "no application" not in str(r).lower())
    unrated = sum(1 for r in ratings if r and ("unrated" in str(r).lower() or "no application" in str(r).lower()))
    not_stated = sum(1 for r in ratings if r is None)
    print(f"\nRatings:")
    print(f"  Rated:      {rated}")
    print(f"  Unrated:    {unrated}")
    print(f"  Not stated: {not_stated}")

    # Financial advisors
    fas = [_safe_get(d, "sale_logistics.financial_advisor") for d in docs]
    fas_named = [f for f in fas if f]
    print(f"\nFinancial Advisors ({len(set(fas_named))} unique):")
    for fa in sorted(set(fas_named)):
        print(f"  {fa}")

    # Bidding platforms
    platforms = [_safe_get(d, "sale_logistics.bidding_platform", "?") for d in docs]
    print(f"\nBidding Platforms:")
    for t, c in Counter(platforms).most_common():
        print(f"  {t:35s} {c}")

    # Full table
    print(f"\n{'─' * 72}")
    print(f"DOCUMENT SUMMARY TABLE")
    print(f"{'─' * 72}")
    print(f"{'#':>3} {'State':>5} {'Par':>15} {'Mats':>5} {'Type':>25} {'Basis':>8} {'Call':>12}")
    print(f"{'─'*3} {'─'*5} {'─'*15} {'─'*5} {'─'*25} {'─'*8} {'─'*12}")

    for i, d in enumerate(docs):
        state = _safe_get(d, "issuer.state", "?")
        par = _safe_get(d, "bond_identification.par_amount", 0)
        n = len(_safe_get(d, "maturity_structure.maturity_schedule", []))
        bt = _safe_get(d, "bond_identification.bond_type", "?")[:25]
        basis = _safe_get(d, "bid_evaluation.basis_of_award", "?")
        call = _safe_get(d, "redemption.optional_redemption", "?")[:12]
        print(f"{i+1:3d} {state:>5} ${par:>14,.0f} {n:>5} {bt:>25} {basis:>8} {call:>12}")

    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()

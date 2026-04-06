#!/usr/bin/env python3
"""
Interactive NOS Screening Demo

Quick interactive interface for screening ground truth NOS documents
through firm profiles. No API key needed — uses demo vote generator.

Usage:
    python3 interactive_demo.py
"""

import json
import sys
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


def main():
    from demo_compare import _generate_demo_votes
    from consensus import compute_consensus
    from generate_report import generate_report

    gt_dir = Path(__file__).parent / "nos_test_set" / "ground_truth"
    firm_dir = Path(__file__).parent / "firm_profiles"

    # Load all available data
    gt_files = sorted(gt_dir.glob("*_ground_truth.json"))
    firm_files = sorted(firm_dir.glob("*.json"))

    if not gt_files:
        print("No ground truth files found.")
        return

    nos_docs = []
    for f in gt_files:
        with open(f) as fh:
            nos = json.load(fh)
        nos_docs.append({
            "path": f,
            "data": nos,
            "label": f"{_safe_get(nos, 'issuer.name', '?')} ({_safe_get(nos, 'issuer.state', '?')}, ${_safe_get(nos, 'bond_identification.par_amount', 0):,.0f})"
        })

    firms = []
    for f in firm_files:
        with open(f) as fh:
            firm = json.load(fh)
        firms.append({
            "path": f,
            "data": firm,
            "label": firm.get("firm_name", f.stem)
        })

    while True:
        print(f"\n{'=' * 60}")
        print("NOS SCREENING — SELECT A DEAL")
        print(f"{'=' * 60}")
        for i, doc in enumerate(nos_docs):
            print(f"  {i+1:2d}. {doc['label']}")
        print(f"  {len(nos_docs)+1:2d}. Run all deals × all firms (grid)")
        print(f"   0. Exit")

        try:
            choice = input(f"\nSelect deal (0-{len(nos_docs)+1}): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            break

        if choice == str(len(nos_docs) + 1):
            # Grid mode
            _run_grid(nos_docs, firms)
            continue

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(nos_docs):
                print("Invalid choice.")
                continue
        except ValueError:
            print("Invalid choice.")
            continue

        nos = nos_docs[idx]["data"]

        print(f"\n{'─' * 60}")
        print("SELECT A FIRM")
        print(f"{'─' * 60}")
        for i, firm in enumerate(firms):
            print(f"  {i+1:2d}. {firm['label']}")
        print(f"  {len(firms)+1:2d}. All firms")

        try:
            firm_choice = input(f"\nSelect firm (1-{len(firms)+1}): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if firm_choice == str(len(firms) + 1):
            for firm in firms:
                votes = _generate_demo_votes(nos, firm["data"])
                consensus = compute_consensus(votes)
                report = generate_report(nos, firm["data"], votes, consensus)
                print(f"\n{report}")
        else:
            try:
                fidx = int(firm_choice) - 1
                if fidx < 0 or fidx >= len(firms):
                    print("Invalid choice.")
                    continue
            except ValueError:
                print("Invalid choice.")
                continue

            firm = firms[fidx]["data"]
            votes = _generate_demo_votes(nos, firm)
            consensus = compute_consensus(votes)
            report = generate_report(nos, firm, votes, consensus)
            print(f"\n{report}")


def _run_grid(nos_docs, firms):
    """Run all deals through all firms and show grid."""
    from demo_compare import _generate_demo_votes
    from consensus import compute_consensus

    # Build headers
    firm_names = [f["label"] for f in firms]
    col1 = 35

    print(f"\n{'#' * 100}")
    print("ALL DEALS × ALL FIRMS")
    print(f"{'#' * 100}\n")

    header = f"{'Deal':<{col1}}"
    for fn in firm_names:
        header += f" {fn[:25]:>25}"
    print(header)
    print("-" * len(header))

    for doc in nos_docs:
        nos = doc["data"]
        issuer = _safe_get(nos, "issuer.name", "?")[:30]
        state = _safe_get(nos, "issuer.state", "?")

        line = f"{issuer} ({state})"
        line = f"{line:<{col1}}"

        for firm in firms:
            votes = _generate_demo_votes(nos, firm["data"])
            consensus = compute_consensus(votes)
            decision = consensus["decision"]
            line += f" {decision:>25}"

        print(line)

    print()


if __name__ == "__main__":
    main()

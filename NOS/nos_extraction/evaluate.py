"""
NOS Extraction Evaluation Harness

Compares LLM extraction output against ground truth JSON files.
Computes field-level accuracy across the test set.

Usage:
    # Evaluate a single extraction against ground truth:
    python3 evaluate.py extraction.json ground_truth.json

    # Evaluate all extractions in a directory:
    python3 evaluate.py --extract-dir extracted/ --gt-dir ground_truth/

    # Just validate ground truth files (par sum check, etc.):
    python3 evaluate.py --validate-gt ground_truth/
"""

import argparse
import json
import os
import sys
from pathlib import Path


# Fields to evaluate and their comparison method
EVAL_FIELDS = [
    # (json_path, comparison_type, weight)
    # comparison_type: "exact" | "numeric" | "enum" | "string_contains" | "array_length" | "array_sum"
    ("issuer.name", "string_contains", 1.0),
    ("issuer.type", "exact", 1.0),
    ("issuer.state", "exact", 1.0),
    ("bond_identification.series", "string_contains", 0.5),
    ("bond_identification.bond_type", "exact", 1.0),
    ("bond_identification.par_amount", "numeric", 2.0),
    ("bond_identification.tax_status", "exact", 1.0),
    ("bond_identification.bank_qualified", "exact", 0.5),
    ("sale_logistics.sale_date", "string_contains", 1.0),
    ("sale_logistics.bidding_platform", "exact", 0.5),
    ("sale_logistics.financial_advisor", "string_contains", 1.0),
    ("maturity_structure.maturity_type", "exact", 1.0),
    ("maturity_structure.dated_date", "string_contains", 1.0),
    ("maturity_structure.number_of_maturities", "numeric", 1.0),
    ("maturity_structure.final_maturity_date", "string_contains", 0.5),
    ("maturity_structure.bidder_term_bond_option", "exact", 0.5),
    ("bid_evaluation.basis_of_award", "exact", 1.0),
    ("bid_evaluation.minimum_bid_price", "numeric", 0.5),
    ("bid_evaluation.max_interest_rate", "numeric", 0.5),
    ("redemption.optional_redemption", "exact", 1.0),
    ("redemption.first_call_date", "string_contains", 0.5),
    ("redemption.call_price", "numeric", 0.5),
    ("registration_delivery.denomination", "numeric", 0.5),
    ("registration_delivery.delivery_date", "string_contains", 0.5),
    ("registration_delivery.paying_agent", "string_contains", 0.5),
    ("credit_enhancement.credit_rating", "string_contains", 0.5),
    ("legal_advisory.bond_counsel", "string_contains", 1.0),
    ("bidder_obligations.commitment_type", "exact", 0.5),
]

# Special evaluations (not simple field comparisons)
SPECIAL_EVALS = [
    "maturity_schedule_sum",      # sum of maturity amounts matches par
    "maturity_schedule_count",    # number of maturities matches
    "good_faith_deposit_amount",  # GFD amount correct
]


def _safe_get(obj: dict, path: str, default=None):
    """Navigate nested dict with dot-separated path."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
        if current is None:
            return default
    return current


def compare_field(extracted_val, truth_val, comparison_type: str) -> tuple[bool, str]:
    """
    Compare an extracted value against ground truth.
    Returns (match: bool, detail: str).
    """
    # Both null = match
    if extracted_val is None and truth_val is None:
        return True, "both null"

    # One null, other not = mismatch
    if extracted_val is None:
        return False, f"extracted=null, truth={truth_val}"
    if truth_val is None:
        return False, f"extracted={extracted_val}, truth=null"

    if comparison_type == "exact":
        match = str(extracted_val).lower().strip() == str(truth_val).lower().strip()
        return match, f"extracted={extracted_val}, truth={truth_val}"

    elif comparison_type == "numeric":
        try:
            e = float(extracted_val)
            t = float(truth_val)
            # Allow 0.1% tolerance for rounding
            if t == 0:
                match = e == 0
            else:
                match = abs(e - t) / abs(t) < 0.001
            return match, f"extracted={e}, truth={t}"
        except (ValueError, TypeError):
            return False, f"non-numeric: extracted={extracted_val}, truth={truth_val}"

    elif comparison_type == "string_contains":
        e_str = str(extracted_val).lower().strip()
        t_str = str(truth_val).lower().strip()
        # Check if one contains the other (handles slight variations)
        match = e_str in t_str or t_str in e_str
        if not match:
            # Also check word overlap
            e_words = set(e_str.split())
            t_words = set(t_str.split())
            if e_words and t_words:
                overlap = len(e_words & t_words) / max(len(e_words), len(t_words))
                match = overlap >= 0.6
        return match, f"extracted='{extracted_val}', truth='{truth_val}'"

    elif comparison_type == "enum":
        match = str(extracted_val).lower().strip() == str(truth_val).lower().strip()
        return match, f"extracted={extracted_val}, truth={truth_val}"

    return False, f"unknown comparison type: {comparison_type}"


def evaluate_maturity_schedule(extracted: dict, truth: dict) -> list[dict]:
    """Special evaluation for maturity schedule arrays."""
    results = []

    ext_schedule = _safe_get(extracted, "maturity_structure.maturity_schedule", [])
    gt_schedule = _safe_get(truth, "maturity_structure.maturity_schedule", [])

    if not ext_schedule and not gt_schedule:
        results.append({
            "field": "maturity_schedule",
            "match": True,
            "detail": "both empty",
            "weight": 2.0
        })
        return results

    # Count match
    ext_count = len(ext_schedule)
    gt_count = len(gt_schedule)
    count_match = ext_count == gt_count
    results.append({
        "field": "maturity_schedule_count",
        "match": count_match,
        "detail": f"extracted={ext_count}, truth={gt_count}",
        "weight": 1.0
    })

    # Sum match (should equal par amount)
    ext_sum = sum(m.get("amount", 0) for m in ext_schedule if isinstance(m, dict))
    gt_sum = sum(m.get("amount", 0) for m in gt_schedule if isinstance(m, dict))
    sum_match = abs(ext_sum - gt_sum) < 1.0 if gt_sum > 0 else ext_sum == 0
    results.append({
        "field": "maturity_schedule_sum",
        "match": sum_match,
        "detail": f"extracted_sum={ext_sum:,.0f}, truth_sum={gt_sum:,.0f}",
        "weight": 2.0
    })

    # Per-maturity match (if counts match)
    if count_match and gt_count > 0:
        correct = 0
        for i, (e, g) in enumerate(zip(ext_schedule, gt_schedule)):
            e_amt = e.get("amount", 0) if isinstance(e, dict) else 0
            g_amt = g.get("amount", 0) if isinstance(g, dict) else 0
            if abs(e_amt - g_amt) < 1.0:
                correct += 1
        pct = correct / gt_count
        results.append({
            "field": "maturity_schedule_amounts",
            "match": pct >= 0.95,
            "detail": f"{correct}/{gt_count} amounts match ({pct:.0%})",
            "weight": 2.0
        })

    return results


def evaluate_extraction(extracted: dict, truth: dict) -> dict:
    """
    Compare a single extraction against ground truth.
    Returns detailed results for each field.
    """
    # Handle wrapped output (from llm_extract.py)
    if "extraction" in extracted:
        extracted = extracted["extraction"]

    field_results = []
    total_weight = 0
    matched_weight = 0

    # Standard field comparisons
    for path, comp_type, weight in EVAL_FIELDS:
        ext_val = _safe_get(extracted, path)
        gt_val = _safe_get(truth, path)

        match, detail = compare_field(ext_val, gt_val, comp_type)

        field_results.append({
            "field": path,
            "match": match,
            "detail": detail,
            "weight": weight,
            "comparison": comp_type
        })
        total_weight += weight
        if match:
            matched_weight += weight

    # Maturity schedule special evaluation
    mat_results = evaluate_maturity_schedule(extracted, truth)
    for r in mat_results:
        field_results.append(r)
        total_weight += r["weight"]
        if r["match"]:
            matched_weight += r["weight"]

    # GFD special eval
    ext_gfd = _safe_get(extracted, "bid_evaluation.good_faith_deposit.amount")
    gt_gfd = _safe_get(truth, "bid_evaluation.good_faith_deposit.amount")
    if gt_gfd is not None:
        match, detail = compare_field(ext_gfd, gt_gfd, "numeric")
        field_results.append({
            "field": "good_faith_deposit.amount",
            "match": match,
            "detail": detail,
            "weight": 1.0
        })
        total_weight += 1.0
        if match:
            matched_weight += 1.0

    accuracy = matched_weight / total_weight if total_weight > 0 else 0

    return {
        "accuracy": accuracy,
        "matched_weight": matched_weight,
        "total_weight": total_weight,
        "fields_evaluated": len(field_results),
        "fields_matched": sum(1 for r in field_results if r["match"]),
        "fields_missed": sum(1 for r in field_results if not r["match"]),
        "results": field_results
    }


def format_evaluation_report(eval_result: dict, label: str = "") -> str:
    """Format evaluation results as a human-readable report."""
    lines = []
    lines.append(f"{'=' * 70}")
    if label:
        lines.append(f"EVALUATION: {label}")
    lines.append(f"Accuracy: {eval_result['accuracy']:.1%} "
                 f"({eval_result['fields_matched']}/{eval_result['fields_evaluated']} fields)")
    lines.append(f"Weighted: {eval_result['matched_weight']:.1f}/{eval_result['total_weight']:.1f}")
    lines.append(f"{'=' * 70}")

    # Group by match/miss
    matched = [r for r in eval_result["results"] if r["match"]]
    missed = [r for r in eval_result["results"] if not r["match"]]

    if missed:
        lines.append(f"\nMISSED ({len(missed)}):")
        for r in missed:
            lines.append(f"  X {r['field']:45s} {r['detail']}")

    if matched:
        lines.append(f"\nMATCHED ({len(matched)}):")
        for r in matched:
            lines.append(f"  + {r['field']:45s} {r['detail']}")

    return "\n".join(lines)


def evaluate_directory(extract_dir: str, gt_dir: str) -> dict:
    """
    Evaluate all extractions in a directory against ground truth.
    Matches files by numeric prefix (01_, 02_, etc.).
    """
    gt_files = {}
    for f in Path(gt_dir).glob("*_ground_truth.json"):
        # Extract numeric prefix
        prefix = f.name.split("_")[0]
        gt_files[prefix] = f

    results = {}
    overall_matched = 0
    overall_total = 0

    for f in sorted(Path(extract_dir).glob("*.json")):
        prefix = f.name.split("_")[0]
        if prefix not in gt_files:
            continue

        with open(f) as ef:
            extracted = json.load(ef)
        with open(gt_files[prefix]) as gf:
            truth = json.load(gf)

        eval_result = evaluate_extraction(extracted, truth)
        results[f.name] = eval_result
        overall_matched += eval_result["matched_weight"]
        overall_total += eval_result["total_weight"]

        print(format_evaluation_report(eval_result, f.name))
        print()

    if results:
        overall_acc = overall_matched / overall_total if overall_total > 0 else 0
        print(f"\n{'#' * 70}")
        print(f"OVERALL ACCURACY: {overall_acc:.1%}")
        print(f"Documents evaluated: {len(results)}")
        print(f"Total weighted score: {overall_matched:.1f}/{overall_total:.1f}")
        print(f"{'#' * 70}")

    return {
        "overall_accuracy": overall_matched / overall_total if overall_total > 0 else 0,
        "documents": len(results),
        "per_document": results
    }


def validate_ground_truth(gt_dir: str):
    """Validate all ground truth files for internal consistency."""
    from validate import validate_nos

    gt_files = sorted(Path(gt_dir).glob("*_ground_truth.json"))
    print(f"Validating {len(gt_files)} ground truth files...\n")

    all_pass = True
    for f in gt_files:
        with open(f) as gf:
            truth = json.load(gf)

        errors = validate_nos(truth)
        if errors:
            print(f"  X {f.name}: {len(errors)} errors")
            for e in errors:
                print(f"      - {e}")
            all_pass = False
        else:
            par = _safe_get(truth, "bond_identification.par_amount", 0)
            issuer = _safe_get(truth, "issuer.name", "?")
            n_mat = len(_safe_get(truth, "maturity_structure.maturity_schedule", []))
            print(f"  + {f.name}: OK ({issuer}, ${par:,.0f}, {n_mat} maturities)")

    print(f"\n{'All ground truth files valid!' if all_pass else 'Some files have errors.'}")
    return all_pass


def main():
    parser = argparse.ArgumentParser(description="NOS Extraction Evaluation")
    parser.add_argument("extraction", nargs="?", help="Extraction JSON file")
    parser.add_argument("ground_truth", nargs="?", help="Ground truth JSON file")
    parser.add_argument("--extract-dir", help="Directory of extraction JSONs")
    parser.add_argument("--gt-dir", help="Directory of ground truth JSONs")
    parser.add_argument("--validate-gt", help="Validate ground truth directory")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    args = parser.parse_args()

    if args.validate_gt:
        sys.exit(0 if validate_ground_truth(args.validate_gt) else 1)

    if args.extract_dir and args.gt_dir:
        result = evaluate_directory(args.extract_dir, args.gt_dir)
    elif args.extraction and args.ground_truth:
        with open(args.extraction) as f:
            extracted = json.load(f)
        with open(args.ground_truth) as f:
            truth = json.load(f)
        result = evaluate_extraction(extracted, truth)
        print(format_evaluation_report(result, Path(args.extraction).name))
    else:
        parser.error("Provide either (extraction + ground_truth) or (--extract-dir + --gt-dir) or --validate-gt")
        return

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nJSON report saved to: {args.output}")


if __name__ == "__main__":
    main()

"""
NOS Extraction Validation

Deterministic checks to catch LLM extraction errors.
These run after every extraction and drive the retry loop.

Checks:
  - par_amount == sum of maturity schedule amounts
  - good_faith_deposit.amount == par_amount * percentage_of_par / 100
  - first_call_date after dated_date
  - sale_date is reasonable (not far in the past)
  - number_of_maturities matches length of maturity_schedule
  - total_bond_years and average_maturity cross-check (if stated)
  - Required fields are present

Usage:
    from validate import validate_nos
    errors = validate_nos(nos_json)
    # errors is a list of strings; empty list = all checks passed
"""

from datetime import datetime, timedelta
import re


def _parse_date(date_str: str | None) -> datetime | None:
    """Try to parse a date string in common NOS formats."""
    if not date_str:
        return None

    # Common formats in NOS documents
    formats = [
        "%B %d, %Y",      # April 15, 2026
        "%b %d, %Y",      # Apr 15, 2026
        "%m/%d/%Y",        # 04/15/2026
        "%Y-%m-%d",        # 2026-04-15
        "%B %d,%Y",        # April 15,2026 (no space)
        "%B %dst, %Y",    # April 1st, 2026
    ]

    # Clean up ordinal suffixes
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", str(date_str).strip())

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _safe_get(obj: dict, path: str, default=None):
    """Safely navigate nested dict with dot-separated path."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
        if current is None:
            return default
    return current


def validate_nos(nos: dict) -> list[str]:
    """
    Run all validation checks on an extracted NOS JSON.
    Returns a list of error messages (empty = all passed).
    """
    errors = []

    # ── Required top-level sections ────────────────────────────
    required_sections = [
        "issuer", "bond_identification", "sale_logistics",
        "maturity_structure", "bid_evaluation"
    ]
    for section in required_sections:
        if section not in nos:
            errors.append(f"Missing required section: {section}")

    if errors:
        # Can't proceed with detailed checks if sections are missing
        return errors

    # ── Par amount vs maturity schedule sum ─────────────────────
    par_amount = _safe_get(nos, "bond_identification.par_amount")
    maturity_schedule = _safe_get(nos, "maturity_structure.maturity_schedule", [])

    if par_amount and maturity_schedule:
        schedule_sum = sum(
            m.get("amount", 0) for m in maturity_schedule
            if isinstance(m, dict) and m.get("amount") is not None
        )
        if schedule_sum > 0 and abs(par_amount - schedule_sum) > 1.0:
            errors.append(
                f"Par amount mismatch: par_amount={par_amount:,.0f} but "
                f"sum of maturity_schedule={schedule_sum:,.0f} "
                f"(difference={abs(par_amount - schedule_sum):,.0f})"
            )

    # ── Good faith deposit math ──────���─────────────────────────
    gfd = _safe_get(nos, "bid_evaluation.good_faith_deposit", {})
    if isinstance(gfd, dict) and par_amount:
        gfd_amount = gfd.get("amount")
        gfd_pct = gfd.get("percentage_of_par")

        if gfd_amount and gfd_pct and par_amount:
            expected = par_amount * gfd_pct / 100
            if abs(gfd_amount - expected) > 1.0:
                errors.append(
                    f"Good faith deposit mismatch: amount={gfd_amount:,.2f} but "
                    f"par_amount({par_amount:,.0f}) * percentage({gfd_pct}%) = {expected:,.2f}"
                )

    # ── Call date after dated date ──��──────────────────────────
    dated_date = _parse_date(_safe_get(nos, "maturity_structure.dated_date"))
    first_call = _parse_date(_safe_get(nos, "redemption.first_call_date"))

    if dated_date and first_call:
        if first_call <= dated_date:
            errors.append(
                f"first_call_date ({_safe_get(nos, 'redemption.first_call_date')}) "
                f"must be after dated_date ({_safe_get(nos, 'maturity_structure.dated_date')})"
            )

    # ── Sale date reasonableness ────────────��──────────────────
    sale_date = _parse_date(_safe_get(nos, "sale_logistics.sale_date"))
    if sale_date:
        # Sale date shouldn't be more than 2 years in the past
        if sale_date < datetime.now() - timedelta(days=730):
            errors.append(
                f"Sale date appears too old: {_safe_get(nos, 'sale_logistics.sale_date')}"
            )

    # ── Number of maturities ─────────��────────────────────────
    stated_count = _safe_get(nos, "maturity_structure.number_of_maturities")
    if stated_count and maturity_schedule:
        actual_count = len(maturity_schedule)
        if stated_count != actual_count:
            errors.append(
                f"Maturity count mismatch: number_of_maturities={stated_count} "
                f"but maturity_schedule has {actual_count} entries"
            )

    # ── Total bond years cross-check ──────────────────────────
    stated_tby = _safe_get(nos, "maturity_structure.total_bond_years")
    if stated_tby and maturity_schedule and dated_date:
        computed_tby = 0
        for m in maturity_schedule:
            mat_date = _parse_date(m.get("date"))
            if mat_date and m.get("amount"):
                years = (mat_date - dated_date).days / 365.25
                computed_tby += m["amount"] * years

        if computed_tby > 0:
            pct_diff = abs(stated_tby - computed_tby) / computed_tby
            if pct_diff > 0.05:  # 5% tolerance for rounding
                errors.append(
                    f"Total bond years mismatch: stated={stated_tby:,.2f} "
                    f"computed={computed_tby:,.2f} (diff={pct_diff:.1%})"
                )

    # ── Average maturity cross-check ──────���───────────────────
    stated_avg = _safe_get(nos, "maturity_structure.average_maturity")
    if stated_avg and stated_tby and par_amount:
        computed_avg = stated_tby / par_amount
        if abs(stated_avg - computed_avg) > 0.5:  # half-year tolerance
            errors.append(
                f"Average maturity mismatch: stated={stated_avg:.2f} "
                f"computed from TBY/par={computed_avg:.2f}"
            )

    # ── Required field presence ────────────���───────────────────
    required_fields = [
        ("issuer.name", "Issuer name"),
        ("bond_identification.par_amount", "Par amount"),
        ("bond_identification.bond_type", "Bond type"),
        ("sale_logistics.sale_date", "Sale date"),
        ("maturity_structure.dated_date", "Dated date"),
        ("maturity_structure.maturity_schedule", "Maturity schedule"),
    ]
    for path, label in required_fields:
        val = _safe_get(nos, path)
        if val is None or val == [] or val == "":
            errors.append(f"Required field missing: {label} ({path})")

    # ── Maturity schedule entries valid ────────────────────────
    if maturity_schedule:
        for i, m in enumerate(maturity_schedule):
            if not isinstance(m, dict):
                errors.append(f"maturity_schedule[{i}] is not an object")
                continue
            if not m.get("date"):
                errors.append(f"maturity_schedule[{i}] missing date")
            if not m.get("amount") and m.get("amount") != 0:
                errors.append(f"maturity_schedule[{i}] missing amount")
            elif isinstance(m.get("amount"), (int, float)) and m["amount"] < 0:
                errors.append(f"maturity_schedule[{i}] has negative amount: {m['amount']}")

    return errors


def main():
    """Validate a NOS extraction JSON file from the command line."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Validate NOS extraction JSON")
    parser.add_argument("json_file", help="Path to NOS extraction JSON")
    args = parser.parse_args()

    with open(args.json_file, "r") as f:
        data = json.load(f)

    # Handle both raw extraction and wrapped output
    nos = data.get("extraction", data)
    errors = validate_nos(nos)

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    else:
        print("VALIDATION PASSED — all checks OK")
        return 0


if __name__ == "__main__":
    exit(main())

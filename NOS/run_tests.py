#!/usr/bin/env python3
"""
Quick self-test for the NOS pipeline.
Runs all offline tests (no API key needed).

Usage:
    python3 run_tests.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))
sys.path.insert(0, str(Path(__file__).parent / "nos_agents"))

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  + {name}")
    else:
        FAIL += 1
        print(f"  X {name} — {detail}")


def run_all():
    global PASS, FAIL

    print("=" * 60)
    print("NOS PIPELINE SELF-TESTS")
    print("=" * 60)

    # ── Schema tests ──────────────────────────────────────
    print("\n--- Schema ---")
    from schema import NOS_EXTRACTION_SCHEMA, FIELD_AGENT_MAP, get_schema_for_prompt

    test("Schema has required sections",
         len(NOS_EXTRACTION_SCHEMA["required"]) >= 10)
    test("Schema is valid JSON string",
         len(get_schema_for_prompt()) > 1000)
    test("Field-agent map has entries",
         len(FIELD_AGENT_MAP) > 10)

    # ── Validation tests ──────────────────────────────────
    print("\n--- Validation ---")
    from validate import validate_nos

    valid_nos = {
        "issuer": {"name": "Test", "type": "city", "state": "TX"},
        "bond_identification": {"par_amount": 100000, "bond_type": "go_unlimited_tax",
                                "series": "2026", "tax_status": "tax_exempt"},
        "sale_logistics": {"sale_date": "April 15, 2026"},
        "maturity_structure": {
            "dated_date": "May 1, 2026", "maturity_type": "serial_only",
            "maturity_schedule": [
                {"date": "2027", "amount": 50000},
                {"date": "2028", "amount": 50000},
            ]
        },
        "bid_evaluation": {"basis_of_award": "nic"},
        "redemption": {}, "registration_delivery": {},
        "credit_enhancement": {}, "legal_advisory": {}, "bidder_obligations": {}
    }
    errors = validate_nos(valid_nos)
    test("Valid NOS passes validation", len(errors) == 0, f"errors: {errors}")

    bad_par = json.loads(json.dumps(valid_nos))
    bad_par["bond_identification"]["par_amount"] = 99000
    errors = validate_nos(bad_par)
    test("Par mismatch detected", any("Par amount" in e for e in errors))

    bad_gfd = json.loads(json.dumps(valid_nos))
    bad_gfd["bid_evaluation"]["good_faith_deposit"] = {"amount": 5000.0, "percentage_of_par": 2.0}
    errors = validate_nos(bad_gfd)
    test("GFD math error detected", any("Good faith deposit" in e for e in errors))

    # ── Consensus tests ───────────────────────────────────
    print("\n--- Consensus ---")
    from consensus import compute_consensus

    def make_votes(votes_spec):
        return [{"agent": f"agent_{i}", "vote": v, "confidence": c,
                 "rationale": "test", "conditions": conds}
                for i, (v, c, conds) in enumerate(votes_spec)]

    # Rule 1: Hard veto
    r = compute_consensus(make_votes([
        ("interested", 0.9, []), ("interested", 0.85, []),
        ("interested", 0.8, []), ("interested", 0.7, []),
        ("pass", 0.95, []),
    ]))
    test("Hard veto (Rule 1)", r["decision"] == "PASS" and r["rule_applied"] == "hard_veto")

    # Rule 2: Unanimous interested
    r = compute_consensus(make_votes([
        ("interested", 0.9, []), ("interested", 0.85, []),
        ("interested", 0.8, []), ("interested", 0.7, []),
        ("interested", 0.82, []),
    ]))
    test("Unanimous interested (Rule 2)", r["decision"] == "INTERESTED")

    # Rule 3: Mixed votes
    r = compute_consensus(make_votes([
        ("interested", 0.9, []), ("conditional", 0.7, ["cond1"]),
        ("interested", 0.8, []), ("conditional", 0.65, ["cond2"]),
        ("interested", 0.82, []),
    ]))
    test("Mixed → CONDITIONAL (Rule 3)",
         r["decision"] == "CONDITIONAL" and len(r["conditions"]) == 2)

    # Rule 4: Multiple low-confidence pass
    r = compute_consensus(make_votes([
        ("pass", 0.6, []), ("interested", 0.8, []),
        ("interested", 0.8, []), ("pass", 0.55, []),
        ("interested", 0.82, []),
    ]))
    test("Low-confidence Pass → escalation (Rule 4)",
         r["decision"] == "CONDITIONAL" and r["escalation"] is True)

    # ── Ground truth validation ───────────────────────────
    print("\n--- Ground Truth Files ---")
    gt_dir = Path(__file__).parent / "nos_test_set" / "ground_truth"
    gt_files = sorted(gt_dir.glob("*_ground_truth.json"))
    test(f"10 ground truth files exist", len(gt_files) == 10, f"found {len(gt_files)}")

    all_valid = True
    for f in gt_files:
        with open(f) as gf:
            gt = json.load(gf)
        errors = validate_nos(gt)
        if errors:
            test(f"{f.name} valid", False, f"{len(errors)} errors")
            all_valid = False
    if all_valid:
        test("All ground truth files pass validation", True)

    # ── Evaluation harness ────────────────────────────────
    print("\n--- Evaluation Harness ---")
    from evaluate import evaluate_extraction
    from run_screening import _sample_nos_json

    sample = _sample_nos_json()
    with open(gt_dir / "01_ground_truth.json") as f:
        truth = json.load(f)
    result = evaluate_extraction(sample, truth)
    test("Sample vs GT accuracy = 100%",
         result["accuracy"] >= 0.99,
         f"accuracy={result['accuracy']:.1%}")

    # ── Agent definitions ─────────────────────────────────
    print("\n--- Agent Definitions ---")
    from agents import AGENT_DEFINITIONS, extract_agent_nos_fields

    test("5 agents defined", len(AGENT_DEFINITIONS) == 5)
    for key, defn in AGENT_DEFINITIONS.items():
        test(f"Agent '{key}' has system prompt",
             len(defn.get("system_prompt", "")) > 100)

    # ── Demo comparison ───────────────────────────────────
    print("\n--- Demo Comparison ---")
    from demo_compare import _generate_demo_votes

    profile_tx = json.load(open(Path(__file__).parent / "firm_profiles" / "texas_regional.json"))
    profile_ne = json.load(open(Path(__file__).parent / "firm_profiles" / "northeast_institutional.json"))

    votes_tx = _generate_demo_votes(sample, profile_tx)
    votes_ne = _generate_demo_votes(sample, profile_ne)
    consensus_tx = compute_consensus(votes_tx)
    consensus_ne = compute_consensus(votes_ne)

    test("TX firm → INTERESTED on TX MUD", consensus_tx["decision"] == "INTERESTED")
    test("NE firm → PASS on TX MUD", consensus_ne["decision"] == "PASS")
    test("Consensus flips between firms",
         consensus_tx["decision"] != consensus_ne["decision"])

    # ── Additional firm profiles ──────────────────────────
    print("\n--- Multi-Firm Demo ---")
    profile_nat = json.load(open(Path(__file__).parent / "firm_profiles" / "national_large.json"))
    profile_bout = json.load(open(Path(__file__).parent / "firm_profiles" / "small_boutique.json"))

    test("4 firm profiles exist",
         len(list((Path(__file__).parent / "firm_profiles").glob("*.json"))) == 4)

    votes_nat = _generate_demo_votes(sample, profile_nat)
    consensus_nat = compute_consensus(votes_nat)
    test("National firm → INTERESTED on TX MUD", consensus_nat["decision"] == "INTERESTED")

    votes_bout = _generate_demo_votes(sample, profile_bout)
    consensus_bout = compute_consensus(votes_bout)
    test("Boutique firm → PASS on TX MUD", consensus_bout["decision"] == "PASS")

    # Test NJ deal through NE firm (should be INTERESTED)
    with open(gt_dir / "03_ground_truth.json") as f:
        nj_nos = json.load(f)
    votes_nj = _generate_demo_votes(nj_nos, profile_ne)
    consensus_nj = compute_consensus(votes_nj)
    test("NE firm → INTERESTED on NJ BAN", consensus_nj["decision"] == "INTERESTED")

    # Test large Nashville deal through national firm
    with open(gt_dir / "10_ground_truth.json") as f:
        tn_nos = json.load(f)
    votes_tn = _generate_demo_votes(tn_nos, profile_nat)
    consensus_tn = compute_consensus(votes_tn)
    test("National firm → INTERESTED on $204M Nashville GO", consensus_tn["decision"] == "INTERESTED")

    # ── Text extraction ──────────────────────────────────
    print("\n--- Text Extraction ---")
    test_pdf = Path(__file__).parent / "nos_test_set" / "NOS_Test_PDFs" / "01_Harris_County_MUD_No_182,_TX_Unlimited_Tax_Bonds,_Srs_2026.pdf"
    if test_pdf.exists():
        from extract_text import extract_text
        text = extract_text(str(test_pdf))
        test("Text extraction produces content", len(text) > 1000, f"got {len(text)} chars")
        test("Text contains issuer name", "Harris County" in text)
        test("Text contains par amount", "2,930,000" in text)
    else:
        test("Test PDF exists", False, f"not found: {test_pdf}")

    # ── Report generation ─────────────────────────────────
    print("\n--- Report Generation ---")
    from generate_report import generate_report
    report = generate_report(sample, profile_tx, votes_tx, consensus_tx)
    test("Report contains issuer name", "Harris County" in report)
    test("Report contains decision", "INTERESTED" in report)
    test("Report has 5 agent sections", report.count("confidence:") == 5)

    # ── Summary ───────────────────────────────────────────
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return FAIL == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

#!/bin/bash
# Run the complete NOS screening demo package.
# No API key needed — all demos use dry-run mode.

set -e
cd "$(dirname "$0")"

echo ""
echo "=============================================="
echo "  NOS Multi-Agent Screening — Full Demo"
echo "=============================================="
echo ""

# 1. Run self-tests
echo ">>> Step 1: Self-Tests"
echo "----------------------------------------------"
python3 run_tests.py
echo ""

# 2. Single NOS comparison (consensus flip)
echo ">>> Step 2: Consensus Flip Demo"
echo "----------------------------------------------"
python3 demo_compare.py --dry-run
echo ""

# 3. Multi-scenario grid (6 deals × 2 firms)
echo ">>> Step 3: Multi-Scenario Grid (6 deals)"
echo "----------------------------------------------"
python3 demo_compare.py --multi
echo ""

# 4. Full grid (10 deals × 4 firms)
echo ">>> Step 4: Full Grid (10 deals × 4 firms)"
echo "----------------------------------------------"
python3 demo_compare.py --all
echo ""

# 5. Detailed report for key scenarios
echo ">>> Step 5: Detailed Reports"
echo "----------------------------------------------"
echo ""
echo "--- TX MUD through TX Regional ---"
python3 generate_report.py nos_test_set/ground_truth/01_ground_truth.json --firm firm_profiles/texas_regional.json
echo ""
echo "--- TX MUD through NE Institutional ---"
python3 generate_report.py nos_test_set/ground_truth/01_ground_truth.json --firm firm_profiles/northeast_institutional.json
echo ""
echo "--- Nashville Metro through National ---"
python3 generate_report.py nos_test_set/ground_truth/10_ground_truth.json --firm firm_profiles/national_large.json
echo ""
echo "--- Nashville Metro through Boutique ---"
python3 generate_report.py nos_test_set/ground_truth/10_ground_truth.json --firm firm_profiles/small_boutique.json
echo ""

# 6. Validate all ground truth
echo ">>> Step 6: Ground Truth Validation"
echo "----------------------------------------------"
python3 nos_extraction/evaluate.py --validate-gt nos_test_set/ground_truth/
echo ""

echo "=============================================="
echo "  Demo Complete!"
echo "=============================================="

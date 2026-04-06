#!/usr/bin/env python3
"""
Batch NOS Extraction

Runs the LLM extraction pipeline on all test PDFs and evaluates results
against ground truth.

Usage:
    # Extract all test PDFs and evaluate:
    export ANTHROPIC_API_KEY=sk-...
    python3 batch_extract.py

    # Extract specific PDFs:
    python3 batch_extract.py --indices 1 3 5

    # Just text extraction (no LLM, no API key needed):
    python3 batch_extract.py --text-only

    # Evaluate existing extractions against ground truth:
    python3 batch_extract.py --evaluate-only
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "nos_extraction"))

TEST_PDF_DIR = Path(__file__).parent / "nos_test_set" / "NOS_Test_PDFs"
GT_DIR = Path(__file__).parent / "nos_test_set" / "ground_truth"
EXTRACT_DIR = Path(__file__).parent / "nos_test_set" / "extractions"
TEXT_DIR = Path(__file__).parent / "nos_test_set" / "extracted_text"


def get_test_pdfs(indices: list[int] | None = None) -> list[tuple[int, Path]]:
    """Get test PDF paths, optionally filtered by index."""
    pdfs = sorted(TEST_PDF_DIR.glob("*.pdf"))
    result = []
    for pdf in pdfs:
        prefix = pdf.name.split("_")[0]
        try:
            idx = int(prefix)
        except ValueError:
            continue
        if indices is None or idx in indices:
            result.append((idx, pdf))
    return result


def run_text_extraction():
    """Extract text from all test PDFs using pdftotext -layout."""
    from extract_text import extract_text

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = get_test_pdfs()

    print(f"Extracting text from {len(pdfs)} PDFs...\n")

    for idx, pdf in pdfs:
        text = extract_text(str(pdf))
        words = len(text.split())
        out_path = TEXT_DIR / f"{pdf.stem}.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"  [{idx:02d}] {pdf.name}: {words} words -> {out_path.name}")

    print(f"\nText extraction complete. Files in: {TEXT_DIR}")


def run_llm_extraction(indices: list[int] | None = None, provider: str = "anthropic", max_retries: int = 1):
    """Run LLM extraction on test PDFs."""
    from llm_extract import extract_nos

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = get_test_pdfs(indices)

    print(f"Running LLM extraction on {len(pdfs)} PDFs ({provider})...\n")

    results = []
    for idx, pdf in pdfs:
        print(f"\n{'=' * 60}")
        print(f"[{idx:02d}] {pdf.name}")
        print(f"{'=' * 60}")

        try:
            result = extract_nos(str(pdf), provider=provider, max_retries=max_retries)
            out_path = EXTRACT_DIR / f"{idx:02d}_extraction.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"  Saved: {out_path.name}")

            n_errors = len(result.get("validation_errors", []))
            if n_errors:
                print(f"  WARNING: {n_errors} validation errors")
            else:
                print(f"  Validation: PASS")

            results.append({"index": idx, "pdf": pdf.name, "errors": n_errors, "path": str(out_path)})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"index": idx, "pdf": pdf.name, "errors": -1, "error": str(e)})

    # Summary
    print(f"\n{'#' * 60}")
    print(f"BATCH EXTRACTION SUMMARY")
    print(f"{'#' * 60}")
    for r in results:
        status = "OK" if r["errors"] == 0 else f"{r['errors']} errors" if r["errors"] > 0 else "FAILED"
        print(f"  [{r['index']:02d}] {status:15s} {r['pdf']}")

    return results


def run_evaluation():
    """Evaluate existing extractions against ground truth."""
    from evaluate import evaluate_directory

    if not EXTRACT_DIR.exists() or not list(EXTRACT_DIR.glob("*.json")):
        print(f"No extractions found in {EXTRACT_DIR}")
        print("Run `python3 batch_extract.py` first to generate extractions.")
        return

    if not GT_DIR.exists() or not list(GT_DIR.glob("*.json")):
        print(f"No ground truth found in {GT_DIR}")
        return

    print(f"Evaluating extractions in {EXTRACT_DIR}")
    print(f"Against ground truth in {GT_DIR}\n")

    result = evaluate_directory(str(EXTRACT_DIR), str(GT_DIR))

    # Save report
    report_path = EXTRACT_DIR / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch NOS Extraction and Evaluation")
    parser.add_argument("--indices", nargs="+", type=int, help="PDF indices to process (e.g. 1 3 5)")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--text-only", action="store_true", help="Only extract text, no LLM")
    parser.add_argument("--evaluate-only", action="store_true", help="Only evaluate existing extractions")
    args = parser.parse_args()

    if args.text_only:
        run_text_extraction()
    elif args.evaluate_only:
        run_evaluation()
    else:
        run_llm_extraction(indices=args.indices, provider=args.provider, max_retries=args.max_retries)
        print("\n")
        run_evaluation()


if __name__ == "__main__":
    main()

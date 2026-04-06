"""
NOS Text Extraction

Extracts text from NOS PDF files using pdftotext -layout.
This is the only extraction method that works reliably across all NOS
document types (Word-native, PScript5 print-to-PDF, copy-protected).

Fallback: pypdf if pdftotext is not installed.

Usage:
    python3 extract_text.py path/to/nos.pdf
    python3 extract_text.py path/to/nos.pdf --output extracted.txt
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def extract_with_pdftotext(pdf_path: str) -> str:
    """
    Extract text using pdftotext -layout (preferred method).
    Captures stdout — no intermediate file needed.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def extract_with_pypdf(pdf_path: str) -> str:
    """
    Fallback extraction using pypdf.
    Less reliable for layout-dependent content like maturity tables,
    but works when pdftotext is not installed.
    """
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("Neither pdftotext nor pypdf is available. Install poppler-utils or pypdf.")

    reader = pypdf.PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(f"--- PAGE {i+1} of {len(reader.pages)} ---\n{text}")
    return "\n\n".join(pages)


def extract_text(pdf_path: str) -> str:
    """
    Extract text from a NOS PDF. Uses pdftotext -layout if available,
    falls back to pypdf otherwise.

    Returns the full text content.
    """
    pdf_path = str(Path(pdf_path).resolve())

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if shutil.which("pdftotext"):
        return extract_with_pdftotext(pdf_path)
    else:
        print("WARNING: pdftotext not found, using pypdf fallback. "
              "Install poppler-utils for better extraction: "
              "sudo apt-get install poppler-utils", file=sys.stderr)
        return extract_with_pypdf(pdf_path)


def main():
    parser = argparse.ArgumentParser(description="Extract text from NOS PDF")
    parser.add_argument("pdf", help="Path to NOS PDF file")
    parser.add_argument("--output", "-o", help="Output text file path (default: stdout)")
    args = parser.parse_args()

    text = extract_text(args.pdf)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Extracted {len(text)} chars to {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()

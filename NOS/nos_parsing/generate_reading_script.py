# generate_reading_script.py
#
# Generates a structural "reading script" from a PDF — the kind of narration
# a screen reader would provide to a blind lawyer navigating a legal document.
#
# The reading script describes:
#   - Page boundaries
#   - Section headers (detected via bold font)
#   - Body paragraphs (grouped by vertical proximity)
#   - Tables (detected via consistent column gaps across consecutive lines)
#   - Centered text blocks (titles, headers)
#   - Footnotes (detected via small font or bottom-of-page position)
#   - Blank form fields (detected via underscores)
#
# Usage:
#   python3 generate_reading_script.py <input.pdf> [output.txt]
#
# The output is a plain-text structural narration that can be paired with
# raw extracted text to give an LLM context about how to interpret the content.

import sys
import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

import pdfplumber


# ── Configuration ──────────────────────────────────────────────

# Vertical gap (in points) that separates paragraphs
PARAGRAPH_GAP = 15

# Horizontal gap (in points) that indicates a table column boundary
COLUMN_GAP = 25

# Minimum consecutive lines with matching column gaps to qualify as a table
MIN_TABLE_ROWS = 3

# How far from center a line's midpoint can be and still count as "centered"
CENTER_TOLERANCE = 80

# Font size threshold below which text is treated as a footnote
FOOTNOTE_SIZE_THRESHOLD = 7.5

# Y position (from top) below which isolated small text is a page number
PAGE_NUMBER_Y_THRESHOLD = 750


# ── Data Structures ────────────────────────────────────────────

@dataclass
class TextLine:
    y: float
    x_start: float
    x_end: float
    text: str
    is_bold: bool
    is_all_bold: bool
    avg_size: float
    char_count: int
    column_gaps: list = field(default_factory=list)
    is_centered: bool = False
    is_footnote: bool = False
    is_page_number: bool = False
    has_blanks: bool = False


@dataclass
class Block:
    block_type: str  # "header", "paragraph", "table", "centered", "footnote", "page_number", "form_field"
    lines: list = field(default_factory=list)
    table_columns: int = 0
    table_rows: int = 0


# ── PDF Analysis ───────────────────────────────────────────────

def extract_lines_from_page(page) -> list[TextLine]:
    """Group characters into lines, detect bold, gaps, centering."""
    if not page.chars:
        return []

    page_width = page.width
    page_center = page_width / 2

    # Group chars by y-position (rounded to nearest point)
    chars_by_y = defaultdict(list)
    for c in page.chars:
        y_key = round(c["top"], 0)
        chars_by_y[y_key].append(c)

    lines = []
    for y in sorted(chars_by_y.keys()):
        chars = sorted(chars_by_y[y], key=lambda c: c["x0"])
        text = "".join(c["text"] for c in chars).strip()
        if not text:
            continue

        # Bold detection
        non_space = [c for c in chars if c["text"].strip()]
        bold_chars = [c for c in non_space if "Bold" in c.get("fontname", "")]
        is_bold = len(bold_chars) > 0
        is_all_bold = len(bold_chars) == len(non_space) if non_space else False

        # Font size
        sizes = [c.get("size", 9) for c in non_space]
        avg_size = sum(sizes) / len(sizes) if sizes else 9.0

        # Column gaps
        column_gaps = []
        for i in range(1, len(chars)):
            gap = chars[i]["x0"] - (chars[i - 1]["x0"] + chars[i - 1].get("width", 5))
            if gap > COLUMN_GAP:
                column_gaps.append(round(chars[i]["x0"]))

        # Centering detection
        x_start = chars[0]["x0"]
        x_end = chars[-1]["x0"] + chars[-1].get("width", 5)
        text_center = (x_start + x_end) / 2
        is_centered = abs(text_center - page_center) < CENTER_TOLERANCE and x_start > 100

        # Footnote detection
        is_footnote = avg_size < FOOTNOTE_SIZE_THRESHOLD

        # Page number detection
        is_page_number = (
            y > PAGE_NUMBER_Y_THRESHOLD
            and len(text) < 10
            and (text.isdigit() or text.lower() in ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"])
        )

        # Blank form fields
        has_blanks = "___" in text or "______" in text

        lines.append(TextLine(
            y=y,
            x_start=x_start,
            x_end=x_end,
            text=text,
            is_bold=is_bold,
            is_all_bold=is_all_bold,
            avg_size=avg_size,
            char_count=len(non_space),
            column_gaps=column_gaps,
            is_centered=is_centered,
            is_footnote=is_footnote,
            is_page_number=is_page_number,
            has_blanks=has_blanks,
        ))

    return lines


def detect_tables(lines: list[TextLine]) -> list[tuple[int, int, int]]:
    """
    Find runs of consecutive lines that share the same column gap structure.
    Returns list of (start_index, end_index, num_columns).
    """
    tables = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if len(line.column_gaps) >= 1 and not line.is_all_bold:
            # Look ahead for consecutive lines with similar gap structure
            gap_signature = tuple(line.column_gaps)
            run_start = i
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.column_gaps:
                    break
                next_sig = tuple(next_line.column_gaps)
                # Allow some tolerance in gap positions
                if len(next_sig) == len(gap_signature):
                    diffs = [abs(a - b) for a, b in zip(gap_signature, next_sig)]
                    if all(d < 15 for d in diffs):
                        j += 1
                        continue
                break

            run_length = j - run_start
            if run_length >= MIN_TABLE_ROWS:
                # Check if the line before the run is a bold header with same gaps (table header)
                header_start = run_start
                if run_start > 0 and lines[run_start - 1].is_all_bold and lines[run_start - 1].column_gaps:
                    header_start = run_start - 1
                tables.append((header_start, j, len(gap_signature) + 1))
                i = j
                continue
        i += 1

    return tables


def group_into_blocks(lines: list[TextLine], page_width: float) -> list[Block]:
    """Classify lines into structural blocks."""
    if not lines:
        return []

    # First detect tables
    table_ranges = detect_tables(lines)
    table_line_indices = set()
    for start, end, _ in table_ranges:
        for idx in range(start, end):
            table_line_indices.add(idx)

    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip page numbers
        if line.is_page_number:
            blocks.append(Block(block_type="page_number", lines=[line]))
            i += 1
            continue

        # Check if this line is part of a table
        in_table = False
        for start, end, num_cols in table_ranges:
            if start <= i < end:
                # Emit the whole table as one block
                table_block = Block(
                    block_type="table",
                    lines=lines[start:end],
                    table_columns=num_cols,
                    table_rows=end - start,
                )
                blocks.append(table_block)
                i = end
                in_table = True
                # Remove this range so we don't re-emit
                table_ranges.remove((start, end, num_cols))
                break
        if in_table:
            continue

        # Footnotes
        if line.is_footnote:
            footnote_block = Block(block_type="footnote", lines=[line])
            i += 1
            while i < len(lines) and lines[i].is_footnote and i not in table_line_indices:
                footnote_block.lines.append(lines[i])
                i += 1
            blocks.append(footnote_block)
            continue

        # Bold-only lines: section headers
        if line.is_all_bold:
            # Check if multiple consecutive bold lines form a centered title block
            header_block = Block(block_type="header", lines=[line])
            i += 1
            while i < len(lines) and lines[i].is_all_bold and i not in table_line_indices:
                header_block.lines.append(lines[i])
                i += 1
            # Distinguish centered title blocks from section headers
            if all(l.is_centered for l in header_block.lines) and len(header_block.lines) >= 2:
                header_block.block_type = "centered_title"
            blocks.append(header_block)
            continue

        # Form fields (lines with blanks)
        if line.has_blanks and not line.is_bold:
            form_block = Block(block_type="form_field", lines=[line])
            i += 1
            while i < len(lines) and lines[i].has_blanks and i not in table_line_indices:
                form_block.lines.append(lines[i])
                i += 1
            blocks.append(form_block)
            continue

        # Regular paragraph: group consecutive non-bold, non-special lines
        para_block = Block(block_type="paragraph", lines=[line])
        i += 1
        while i < len(lines):
            next_line = lines[i]
            if (
                next_line.is_all_bold
                or next_line.is_footnote
                or next_line.is_page_number
                or i in table_line_indices
            ):
                break
            # Paragraph break on large vertical gap
            if next_line.y - para_block.lines[-1].y > PARAGRAPH_GAP:
                break
            # If the next line has blanks and current doesn't, that's a form field
            if next_line.has_blanks and not para_block.lines[-1].has_blanks:
                break
            para_block.lines.append(next_line)
            i += 1
        blocks.append(para_block)

    return blocks


# ── Reading Script Generation ──────────────────────────────────

def generate_reading_script(pdf_path: str) -> str:
    """Generate a structural reading script from a PDF."""
    pdf = pdfplumber.open(pdf_path)
    total_pages = len(pdf.pages)

    output = []
    output.append(f"READING SCRIPT FOR: {Path(pdf_path).name}")
    output.append(f"Total pages: {total_pages}")
    output.append("=" * 72)
    output.append("")

    for page_num, page in enumerate(pdf.pages, 1):
        output.append(f"--- PAGE {page_num} of {total_pages} ---")
        output.append("")

        lines = extract_lines_from_page(page)
        blocks = group_into_blocks(lines, page.width)

        for block in blocks:
            if block.block_type == "page_number":
                continue  # Skip page numbers in the script

            elif block.block_type == "centered_title":
                output.append("[CENTERED TITLE BLOCK]")
                for line in block.lines:
                    output.append(f"  {line.text}")
                output.append("[END CENTERED TITLE]")
                output.append("")

            elif block.block_type == "header":
                header_text = " ".join(l.text for l in block.lines)
                # Detect header hierarchy
                if all(l.text == l.text.upper() for l in block.lines if l.text.strip()):
                    output.append(f"[SECTION HEADING] {header_text}")
                else:
                    output.append(f"[SUBSECTION HEADING] {header_text}")
                output.append("")

            elif block.block_type == "table":
                # Reconstruct table with column info
                output.append(f"[TABLE: {block.table_rows} rows, {block.table_columns} columns]")
                for line in block.lines:
                    prefix = "  [HEADER] " if line.is_all_bold else "  [ROW]    "
                    output.append(f"{prefix}{line.text}")
                output.append("[END TABLE]")
                output.append("")

            elif block.block_type == "footnote":
                output.append("[FOOTNOTE]")
                footnote_text = " ".join(l.text for l in block.lines)
                output.append(f"  {footnote_text}")
                output.append("[END FOOTNOTE]")
                output.append("")

            elif block.block_type == "form_field":
                output.append("[FORM FIELDS]")
                for line in block.lines:
                    output.append(f"  {line.text}")
                output.append("[END FORM FIELDS]")
                output.append("")

            elif block.block_type == "paragraph":
                # Check if this paragraph contains inline bold (mixed bold)
                has_inline_bold = any(l.is_bold and not l.is_all_bold for l in block.lines)
                para_text = " ".join(l.text for l in block.lines)

                if has_inline_bold:
                    output.append("[PARAGRAPH with emphasized text]")
                else:
                    output.append("[PARAGRAPH]")
                output.append(f"  {para_text}")
                output.append("")

    pdf.close()

    return "\n".join(output)


# ── Main ───────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_reading_script.py <input.pdf> [output.txt]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = str(Path(pdf_path).with_suffix("")) + "_reading_script.txt"

    print(f"Generating reading script for: {pdf_path}")
    script = generate_reading_script(pdf_path)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"Reading script written to: {output_path}")

    # Print summary stats
    lines = script.split("\n")
    sections = sum(1 for l in lines if "[SECTION HEADING]" in l)
    subsections = sum(1 for l in lines if "[SUBSECTION HEADING]" in l)
    tables = sum(1 for l in lines if l.strip().startswith("[TABLE:"))
    paragraphs = sum(1 for l in lines if "[PARAGRAPH" in l)
    footnotes = sum(1 for l in lines if l.strip() == "[FOOTNOTE]")
    form_fields = sum(1 for l in lines if l.strip() == "[FORM FIELDS]")

    print(f"\nStructure summary:")
    print(f"  Section headings:    {sections}")
    print(f"  Subsection headings: {subsections}")
    print(f"  Tables:              {tables}")
    print(f"  Paragraphs:          {paragraphs}")
    print(f"  Footnotes:           {footnotes}")
    print(f"  Form field blocks:   {form_fields}")


if __name__ == "__main__":
    main()

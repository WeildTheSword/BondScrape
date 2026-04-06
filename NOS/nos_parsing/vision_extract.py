# vision_extract.py
#
# Vision-based NOS field extraction prototype.
#
# Strategy:
#   1. Use the reading script to identify which pages contain which fields
#      (chunking/routing layer)
#   2. Render those pages as images
#   3. Send page images to a vision-capable LLM for extraction
#   4. Compare output against ground truth
#
# Supports: Claude (Anthropic) or GPT-4o (OpenAI-compatible)
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-...
#   python3 vision_extract.py nos_test_set/01_Harris_County_MUD_No_182,...pdf
#
#   Or with OpenAI-compatible:
#   export LLM_API_KEY=sk-...
#   export LLM_MODEL=gpt-4o
#   python3 vision_extract.py nos_test_set/01_Harris_County_MUD_No_182,...pdf --provider openai

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

# ── Field Definitions ──────────────────────────────────────────
# Each field defines:
#   - name: field key in output
#   - description: what the LLM should look for
#   - page_hints: keywords in the reading script that indicate which pages to send
#   - max_pages: cap on how many pages to send for this field

FIELDS = [
    {
        "name": "issuer",
        "description": "The full legal name of the issuing entity (e.g. 'Harris County Municipal Utility District No. 182')",
        "page_hints": ["OFFICIAL NOTICE OF SALE", "NOTICE OF SALE"],
        "max_pages": 2,
    },
    {
        "name": "par_amount",
        "description": "The total par/principal amount of the bond offering as a dollar figure (e.g. '$2,930,000')",
        "page_hints": ["OFFICIAL NOTICE OF SALE", "NOTICE OF SALE"],
        "max_pages": 2,
    },
    {
        "name": "series",
        "description": "The series designation (e.g. 'Series 2026', 'Series 2026A&B')",
        "page_hints": ["OFFICIAL NOTICE OF SALE", "NOTICE OF SALE"],
        "max_pages": 2,
    },
    {
        "name": "bond_type",
        "description": "The type of bonds (e.g. 'Unlimited Tax Bonds', 'General Obligation Bonds', 'Revenue Bonds')",
        "page_hints": ["OFFICIAL NOTICE OF SALE", "NOTICE OF SALE"],
        "max_pages": 2,
    },
    {
        "name": "dated_date",
        "description": "The dated date of the bonds — when interest begins accruing (e.g. 'May 1, 2026'). Look for 'dated', 'accrue interest from', 'Dated Date'.",
        "page_hints": ["Description of", "Terms of the Bonds", "dated", "accrue interest"],
        "max_pages": 3,
    },
    {
        "name": "delivery_date",
        "description": "The expected/anticipated delivery date (e.g. 'May 14, 2026'). Look for 'delivery', 'closing', 'anticipated that initial delivery'.",
        "page_hints": ["Delivery", "delivery", "closing", "Initial Bond"],
        "max_pages": 3,
    },
    {
        "name": "sale_date",
        "description": "The date bids are due / bonds are sold (e.g. 'April 15, 2026'). Look for 'bid opening', 'sale date', 'bids will be received'.",
        "page_hints": ["Bid Opening", "bid opening", "sale date", "bids"],
        "max_pages": 2,
    },
    {
        "name": "tax_status",
        "description": "Whether bond interest is tax-exempt or taxable. Look for 'excludable from gross income', 'tax-exempt', 'taxable', 'federally taxable'. Return exactly 'tax-exempt' or 'taxable'.",
        "page_hints": ["Legal Opinion", "Tax", "tax", "excludable", "gross income", "Qualified Tax"],
        "max_pages": 3,
    },
    {
        "name": "call_features",
        "description": "Redemption/call provisions. List each type found: 'optional_redemption', 'mandatory_sinking_fund_redemption', 'callable_prior_to_maturity'. Include the first call date if stated.",
        "page_hints": ["redemption", "Redemption", "optional", "sinking fund", "callable", "prior to maturity"],
        "max_pages": 3,
    },
    {
        "name": "maturity_schedule",
        "description": "The full maturity schedule table. Return as a JSON array of objects with 'year' and 'amount' keys. Look for a table showing Year and Principal Amount.",
        "page_hints": ["mature serially", "Maturity", "maturity", "Principal Amount"],
        "max_pages": 3,
    },
    {
        "name": "financial_advisor",
        "description": "The financial advisor firm name (e.g. 'The GMS Group, L.L.C.'). Look for 'Financial Advisor', 'FA', or advisor references.",
        "page_hints": ["Financial Advisor", "financial advisor", "FA"],
        "max_pages": 3,
    },
    {
        "name": "bond_counsel",
        "description": "The bond counsel law firm name. Look for 'Bond Counsel' or 'Legal Opinion' sections.",
        "page_hints": ["Bond Counsel", "bond counsel", "Legal Opinion"],
        "max_pages": 3,
    },
    {
        "name": "paying_agent",
        "description": "The paying agent/registrar name and location. Look for 'Paying Agent', 'Registrar'.",
        "page_hints": ["Paying Agent", "Registrar", "paying agent"],
        "max_pages": 3,
    },
    {
        "name": "good_faith_deposit",
        "description": "The good faith deposit amount as a dollar figure and percentage. Look for 'Good Faith Deposit', 'bid security'.",
        "page_hints": ["Good Faith", "good faith", "deposit", "bid security"],
        "max_pages": 2,
    },
    {
        "name": "minimum_bid",
        "description": "The minimum bid price as a percentage of par (e.g. '97%', '99%'). Look for 'not less than', 'minimum price', 'par value'.",
        "page_hints": ["not less than", "minimum", "par value", "all or none"],
        "max_pages": 2,
    },
    {
        "name": "max_interest_rate",
        "description": "The maximum net effective interest rate if stated (e.g. '6.81%'). Look for 'may not exceed', 'maximum interest rate'.",
        "page_hints": ["may not exceed", "net effective interest rate", "maximum"],
        "max_pages": 2,
    },
    {
        "name": "rating",
        "description": "Bond rating or statement that no rating was sought. Look for 'Rating', 'Moody', 'S&P', 'Fitch', 'no application'.",
        "page_hints": ["Rating", "rating", "Moody", "S&P", "Fitch", "no application"],
        "max_pages": 2,
    },
]


# ── Page Routing ───────────────────────────────────────────────

def load_reading_script(pdf_path: str) -> str:
    """Load the reading script for a PDF if it exists."""
    script_path = Path(pdf_path).with_suffix("").as_posix() + "_reading_script.txt"
    if Path(script_path).exists():
        return Path(script_path).read_text(encoding="utf-8")
    return ""


def route_pages(reading_script: str, field: dict, total_pages: int) -> list[int]:
    """
    Use the reading script to determine which pages are most relevant
    for extracting a given field. Returns 1-indexed page numbers.
    """
    if not reading_script:
        # No reading script — fall back to first few pages
        return list(range(1, min(total_pages + 1, field["max_pages"] + 1)))

    # Split reading script by page markers
    page_sections = {}
    current_page = 0
    current_text = []

    for line in reading_script.split("\n"):
        page_match = re.match(r"--- PAGE (\d+) of \d+ ---", line)
        if page_match:
            if current_page > 0:
                page_sections[current_page] = "\n".join(current_text)
            current_page = int(page_match.group(1))
            current_text = []
        else:
            current_text.append(line)

    if current_page > 0:
        page_sections[current_page] = "\n".join(current_text)

    # Score each page by how many hint keywords it contains
    page_scores = {}
    for page_num, section_text in page_sections.items():
        score = 0
        section_lower = section_text.lower()
        for hint in field["page_hints"]:
            count = section_lower.count(hint.lower())
            score += count
        if score > 0:
            page_scores[page_num] = score

    if not page_scores:
        # No matches — default to first pages
        return list(range(1, min(total_pages + 1, field["max_pages"] + 1)))

    # Return top-scoring pages, capped at max_pages
    sorted_pages = sorted(page_scores.keys(), key=lambda p: page_scores[p], reverse=True)
    selected = sorted_pages[: field["max_pages"]]
    return sorted(selected)


# ── PDF to Image ───────────────────────────────────────────────

def render_page_to_base64(pdf_path: str, page_num: int, scale: float = 2.0) -> str:
    """Render a single PDF page to a base64-encoded PNG. page_num is 1-indexed."""
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_num - 1]
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()

    import io

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    pdf.close()
    return b64


# ── LLM Calls ─────────────────────────────────────────────────

def extract_field_anthropic(
    field: dict, page_images: list[tuple[int, str]], api_key: str, model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Extract a single field using Claude's vision API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    content = []

    # Add page images
    for page_num, b64_img in page_images:
        content.append({"type": "text", "text": f"[Page {page_num}]"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64_img,
                },
            }
        )

    # Add extraction instruction
    content.append(
        {
            "type": "text",
            "text": f"""Extract the following field from this municipal bond Notice of Sale document.

Field: {field['name']}
Description: {field['description']}

Return ONLY valid JSON in this exact format:
{{
  "field": "{field['name']}",
  "value": <extracted value — string, number, array, or null if not found>,
  "confidence": <"high", "medium", or "low">,
  "source_page": <page number where you found the information>,
  "evidence": <brief quote from the document that supports your extraction>
}}

Be precise. Extract exactly what the document states. Do not infer or guess. If the information is not present in these pages, set value to null and confidence to "low".""",
        }
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )

    # Parse response
    text = response.content[0].text
    # Try to extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        return json.loads(json_match.group())
    return {"field": field["name"], "value": None, "confidence": "low", "error": "Could not parse response"}


def extract_field_openai(
    field: dict, page_images: list[tuple[int, str]], api_key: str, model: str = "gpt-4o", base_url: str = "https://api.openai.com/v1"
) -> dict:
    """Extract a single field using OpenAI-compatible vision API."""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    content = []

    for page_num, b64_img in page_images:
        content.append({"type": "text", "text": f"[Page {page_num}]"})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_img}",
                    "detail": "high",
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": f"""Extract the following field from this municipal bond Notice of Sale document.

Field: {field['name']}
Description: {field['description']}

Return ONLY valid JSON in this exact format:
{{
  "field": "{field['name']}",
  "value": <extracted value — string, number, array, or null if not found>,
  "confidence": <"high", "medium", or "low">,
  "source_page": <page number where you found the information>,
  "evidence": <brief quote from the document that supports your extraction>
}}

Be precise. Extract exactly what the document states. Do not infer or guess. If the information is not present in these pages, set value to null and confidence to "low".""",
        }
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "You are a precise municipal bond document extraction engine. Return only JSON.",
            },
            {"role": "user", "content": content},
        ],
    )

    text = response.choices[0].message.content
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        return json.loads(json_match.group())
    return {"field": field["name"], "value": None, "confidence": "low", "error": "Could not parse response"}


# ── Batch Extraction with Routing ──────────────────────────────

def extract_all_fields(pdf_path: str, provider: str = "anthropic", fields: list = None) -> dict:
    """
    Extract all fields from a PDF using vision + reading script routing.

    1. Load reading script for page routing
    2. For each field, determine relevant pages
    3. Render only those pages as images
    4. Send to vision model for extraction
    """
    if fields is None:
        fields = FIELDS

    reading_script = load_reading_script(pdf_path)
    pdf = pdfium.PdfDocument(pdf_path)
    total_pages = len(pdf)
    pdf.close()

    # Determine API config
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("VISION_MODEL", "claude-sonnet-4-20250514")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        extract_fn = lambda field, images: extract_field_anthropic(field, images, api_key, model)
    else:
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL", "gpt-4o")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable not set")
        extract_fn = lambda field, images: extract_field_openai(field, images, api_key, model, base_url)

    # Cache rendered pages to avoid re-rendering
    rendered_pages = {}

    results = {}
    routing_info = {}

    for field in fields:
        # Route: which pages to look at
        pages = route_pages(reading_script, field, total_pages)
        routing_info[field["name"]] = pages

        print(f"  {field['name']:25s} -> pages {pages}")

        # Render needed pages
        page_images = []
        for p in pages:
            if p not in rendered_pages:
                rendered_pages[p] = render_page_to_base64(pdf_path, p)
            page_images.append((p, rendered_pages[p]))

        # Extract
        try:
            result = extract_fn(field, page_images)
            results[field["name"]] = result
        except Exception as e:
            print(f"    ERROR: {e}")
            results[field["name"]] = {
                "field": field["name"],
                "value": None,
                "confidence": "low",
                "error": str(e),
            }

    return {
        "pdf": pdf_path,
        "total_pages": total_pages,
        "provider": provider,
        "routing": routing_info,
        "extractions": results,
    }


# ── Comparison with Ground Truth ───────────────────────────────

def load_ground_truth(pdf_path: str) -> str | None:
    """Load the ground truth file if it exists."""
    gt_path = Path(pdf_path).with_suffix("").as_posix() + "_ground_truth.txt"
    if Path(gt_path).exists():
        return Path(gt_path).read_text(encoding="utf-8")
    return None


def print_results(output: dict):
    """Pretty-print extraction results."""
    print(f"\n{'=' * 72}")
    print(f"EXTRACTION RESULTS: {Path(output['pdf']).name}")
    print(f"Pages: {output['total_pages']}  |  Provider: {output['provider']}")
    print(f"{'=' * 72}\n")

    for field_name, result in output["extractions"].items():
        pages = output["routing"].get(field_name, [])
        confidence = result.get("confidence", "?")
        value = result.get("value")
        evidence = result.get("evidence", "")
        error = result.get("error", "")

        conf_marker = {"high": "+", "medium": "~", "low": "-"}.get(confidence, "?")

        print(f"[{conf_marker}] {field_name}")
        print(f"    Value: {json.dumps(value) if isinstance(value, (list, dict)) else value}")
        print(f"    Pages sent: {pages}  |  Source page: {result.get('source_page', '?')}")
        if evidence:
            print(f"    Evidence: \"{evidence[:120]}\"")
        if error:
            print(f"    Error: {error}")
        print()


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vision-based NOS field extraction")
    parser.add_argument("pdf", help="Path to NOS PDF file")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--output", help="Output JSON path (optional)")
    parser.add_argument("--fields", nargs="+", help="Extract only these fields (by name)")
    parser.add_argument("--dry-run", action="store_true", help="Show routing only, don't call LLM")
    args = parser.parse_args()

    pdf_path = args.pdf
    print(f"PDF: {pdf_path}")

    # Load reading script for routing info
    reading_script = load_reading_script(pdf_path)
    if reading_script:
        print(f"Reading script: found")
    else:
        print(f"Reading script: not found (will use default page routing)")
        print(f"  Run: python3 generate_reading_script.py \"{pdf_path}\"")

    pdf = pdfium.PdfDocument(pdf_path)
    total_pages = len(pdf)
    pdf.close()
    print(f"Total pages: {total_pages}")

    # Filter fields if requested
    fields = FIELDS
    if args.fields:
        fields = [f for f in FIELDS if f["name"] in args.fields]
        print(f"Extracting {len(fields)} fields: {[f['name'] for f in fields]}")
    else:
        print(f"Extracting all {len(fields)} fields")

    print(f"\nRouting plan:")
    for field in fields:
        pages = route_pages(reading_script, field, total_pages)
        print(f"  {field['name']:25s} -> pages {pages}")

    if args.dry_run:
        print("\n[Dry run — no LLM calls made]")
        return

    print(f"\nExtracting with {args.provider}...")
    output = extract_all_fields(pdf_path, provider=args.provider, fields=fields)
    print_results(output)

    # Save output
    output_path = args.output
    if not output_path:
        output_path = str(Path(pdf_path).with_suffix("")) + "_vision_extract.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Show ground truth comparison hint
    gt = load_ground_truth(pdf_path)
    if gt:
        print(f"Ground truth available — compare with: {Path(pdf_path).with_suffix('').as_posix()}_ground_truth.txt")


if __name__ == "__main__":
    main()

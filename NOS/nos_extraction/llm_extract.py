"""
NOS LLM Structured Extraction

Sends full NOS text + JSON schema to Claude API, requests structured JSON output.
Pipeline: pdftotext -layout → full text to LLM with JSON schema → structured JSON.

NOS documents are typically 5K-18K tokens, fitting in a single LLM context window.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python3 llm_extract.py path/to/nos.pdf

    # Or with OpenAI-compatible API:
    export LLM_API_KEY=sk-...
    export LLM_MODEL=gpt-4o
    python3 llm_extract.py path/to/nos.pdf --provider openai
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from schema import NOS_EXTRACTION_SCHEMA, get_schema_for_prompt
from extract_text import extract_text


SYSTEM_PROMPT = """You are a municipal bond Notice of Sale (NOS) extraction engine.
You will receive the full text of a NOS document and a JSON schema.
Extract every field from the document into the schema format.

GENERAL RULES:
- Extract EXACTLY what the document states. Do not infer or guess.
- Use null for any field genuinely not present in the document.
- Return ONLY valid JSON matching the schema. No markdown, no explanation, just JSON.

FIELD-SPECIFIC GUIDANCE:
- par_amount: Extract as a number with no $ or commas. Look at the top/header of the NOS. The par amount is often marked with * meaning "preliminary, subject to change" — extract the stated amount.
- maturity_schedule: Extract EVERY maturity date and amount from the maturity table. The table is usually space-aligned, not a formal PDF table. Watch for two-column layouts (year+amount | year+amount side by side). Include ALL rows.
- issuer.type: Map to the schema enum. MUD = municipal_utility_district. ISD = independent_school_district. Borough/Town = city. Metropolitan Government = city. Housing Development Authority = authority.
- basis_of_award: Texas "net effective interest rate" maps to "net_effective_rate". NIC = "nic". TIC = "tic". If the document says "lowest true interest cost" that is TIC.
- good_faith_deposit: Extract BOTH the dollar amount AND percentage if both are stated. Sometimes only one is given. If the deposit is "not required" or not mentioned, set the object to null.
- credit_rating: "Explicitly unrated" or "no application made" is different from "rating not mentioned." For the former, state it. For the latter, use null.
- optional_redemption: If the bonds are "not subject to redemption prior to maturity" that is "non_callable". If bonds are subject to optional redemption, that is "callable". If the NOS says "see POS for redemption provisions" use null.
- issue_price_requirements: These are often conditional ("if fewer than 3 bids, hold-the-offering-price applies"). Extract the primary/expected rule.
- dates: Use the format as stated in the document. Do not normalize.
- bank_qualified: Look for "qualified tax-exempt obligation" or "Section 265". If the document says "The Bonds will not be designated as qualified tax-exempt obligations" set to false. If not mentioned, set to null.
- bidding_platform: "PARITY" or "BiDCOMP/PARITY" = "parity". "Grant Street" or "MuniAuction" = "grant_street".

COMMON PITFALLS:
- Do NOT confuse the NOS body with the bid form or underwriter certificates (same PDF, repeated maturity tables). The bid form usually has blank lines for rates and amounts — skip it.
- NOS documents often have both a summary "Notice of Sale" (1 page) and a "Detailed Notice of Sale" (many pages). Extract from the detailed version.
- Some NOS documents list multiple bond series (e.g., Series A and B). Extract the primary series unless the schema indicates otherwise.
- For minimum_bid_price, extract as a percentage of par (e.g., 97.0 for "not less than 97%"). Some use dollar minimums instead — convert to percentage if par amount is known.
- For maximum_bid_price, some NOS documents cap the premium (e.g., "not more than 120% of par")."""


EXTRACTION_PROMPT_TEMPLATE = """Here is the full text of a municipal bond Notice of Sale document:

<nos_text>
{nos_text}
</nos_text>

Extract all fields into this JSON schema:

<schema>
{schema}
</schema>

Return ONLY the completed JSON object. Every field should be populated from the document or set to null if not found."""


RETRY_PROMPT_TEMPLATE = """Your previous extraction had validation errors:

{errors}

Here is the original NOS text again:

<nos_text>
{nos_text}
</nos_text>

Please fix the errors and return the corrected JSON. Common issues:
- par_amount must equal the sum of all maturity_schedule amounts
- good_faith_deposit.amount must equal par_amount * percentage_of_par / 100
- first_call_date must be after dated_date
- number_of_maturities must match the length of maturity_schedule array

Return ONLY the corrected JSON object."""


def extract_with_anthropic(nos_text: str, api_key: str, model: str = "claude-sonnet-4-20250514") -> dict:
    """Extract NOS fields using Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        nos_text=nos_text,
        schema=get_schema_for_prompt()
    )

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    return _parse_json_response(text)


def extract_with_openai(
    nos_text: str, api_key: str,
    model: str = "gpt-4o",
    base_url: str = "https://api.openai.com/v1"
) -> dict:
    """Extract NOS fields using OpenAI-compatible API."""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        nos_text=nos_text,
        schema=get_schema_for_prompt()
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


def retry_extraction_anthropic(
    nos_text: str, errors: list[str],
    api_key: str, model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Re-send extraction with specific validation error messages."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = RETRY_PROMPT_TEMPLATE.format(
        nos_text=nos_text,
        errors="\n".join(f"- {e}" for e in errors)
    )

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text
    return _parse_json_response(text)


def retry_extraction_openai(
    nos_text: str, errors: list[str],
    api_key: str, model: str = "gpt-4o",
    base_url: str = "https://api.openai.com/v1"
) -> dict:
    """Re-send extraction with specific validation error messages (OpenAI)."""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    prompt = RETRY_PROMPT_TEMPLATE.format(
        nos_text=nos_text,
        errors="\n".join(f"- {e}" for e in errors)
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse JSON from LLM response:\n{text[:500]}")


def extract_nos(pdf_path: str, provider: str = "anthropic", max_retries: int = 1) -> dict:
    """
    Full extraction pipeline: text extraction → LLM extraction → validation → retry.

    Returns the extracted NOS JSON and metadata.
    """
    from validate import validate_nos

    # Step 1: Extract text
    nos_text = extract_text(pdf_path)
    word_count = len(nos_text.split())
    print(f"Extracted {word_count} words from {Path(pdf_path).name}", file=sys.stderr)

    # Step 2: Configure provider
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("NOS_MODEL", "claude-sonnet-4-20250514")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        extract_fn = lambda text: extract_with_anthropic(text, api_key, model)
        retry_fn = lambda text, errors: retry_extraction_anthropic(text, errors, api_key, model)
    else:
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL", "gpt-4o")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable not set")
        extract_fn = lambda text: extract_with_openai(text, api_key, model, base_url)
        retry_fn = lambda text, errors: retry_extraction_openai(text, errors, api_key, model, base_url)

    # Step 3: Initial extraction
    print(f"Sending to {provider} ({model})...", file=sys.stderr)
    nos_json = extract_fn(nos_text)

    # Step 4: Validate
    errors = validate_nos(nos_json)

    # Step 5: Retry on validation failure
    attempt = 0
    while errors and attempt < max_retries:
        attempt += 1
        print(f"Validation errors (attempt {attempt}/{max_retries}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"Retrying extraction...", file=sys.stderr)

        nos_json = retry_fn(nos_text, errors)
        errors = validate_nos(nos_json)

    if errors:
        print(f"WARNING: {len(errors)} validation errors remain after {max_retries} retries:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)

    return {
        "source_pdf": str(pdf_path),
        "word_count": word_count,
        "provider": provider,
        "model": model,
        "validation_errors": errors,
        "extraction": nos_json
    }


def main():
    parser = argparse.ArgumentParser(description="LLM-based NOS structured extraction")
    parser.add_argument("pdf", help="Path to NOS PDF file")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--output", "-o", help="Output JSON path")
    parser.add_argument("--max-retries", type=int, default=1, help="Max retry attempts on validation failure")
    parser.add_argument("--text-only", action="store_true", help="Just extract text, don't call LLM")
    args = parser.parse_args()

    if args.text_only:
        text = extract_text(args.pdf)
        print(text)
        return

    result = extract_nos(args.pdf, provider=args.provider, max_retries=args.max_retries)

    output_path = args.output
    if not output_path:
        output_path = str(Path(args.pdf).with_suffix("")) + "_nos_extract.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {output_path}", file=sys.stderr)

    if result["validation_errors"]:
        print(f"WARNING: {len(result['validation_errors'])} validation errors", file=sys.stderr)
    else:
        print("All validation checks passed", file=sys.stderr)


if __name__ == "__main__":
    main()

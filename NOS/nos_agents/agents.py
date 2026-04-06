"""
NOS Screening Agents

Five specialized agents, each answering one screening question about a
Notice of Sale. All receive the extracted NOS JSON plus a shared firm profile.
Agents run in parallel and do not see each other's votes (prevents anchoring bias).

Agents:
  1. Sector Fit    — "Is this our kind of deal?"
  2. Size & Capital — "Can we afford this commitment?"
  3. Structure      — "Are the bidding rules workable?"
  4. Distribution   — "Can we sell these bonds?"
  5. Calendar       — "Do we have time and people?"

Each agent returns: {vote, confidence, rationale, conditions}
Vote: "interested" | "conditional" | "pass"
Confidence: 0.0 to 1.0
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Agent Definitions ──────────────────────────────────────────────

AGENT_DEFINITIONS = {
    "sector_fit": {
        "name": "Sector Fit",
        "question": "Is this our kind of deal?",
        "nos_fields": [
            "issuer", "bond_identification.bond_type",
            "bond_identification.bond_type_description",
            "bond_identification.tax_status", "bond_identification.purpose",
            "legal_advisory.bond_counsel"
        ],
        "firm_fields": ["sector_coverage"],
        "system_prompt": """You are the sector fit screener for a public finance desk at {firm_name}.

Your job: determine whether this deal falls within the firm's coverage areas and strategic priorities.

Consider:
- Does the firm actively cover this issuer type and state?
- Has the firm bid on similar bond types?
- Does the geography align with the firm's offices and coverage?
- Is this sector a growth priority or one the firm is exiting?
- Does the bond counsel or financial advisor suggest a relationship the firm has or wants?

A deal outside the firm's geographic footprint or sector coverage is a clear Pass.
A deal in an adjacent sector the firm is targeting could be Conditional.
A deal squarely in the firm's core coverage is Interested.

{firm_description}

You MUST respond with ONLY valid JSON in this exact format:
{{
  "agent": "sector_fit",
  "vote": "interested" | "conditional" | "pass",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one to three sentences explaining your vote>",
  "conditions": ["<condition string>"] or []
}}"""
    },

    "size_capital": {
        "name": "Size & Capital",
        "question": "Can we afford this commitment?",
        "nos_fields": [
            "bond_identification.par_amount", "bond_identification.bank_qualified",
            "bidder_obligations.commitment_type",
            "bid_evaluation.good_faith_deposit",
            "registration_delivery.delivery_date",
            "maturity_structure.final_maturity_date"
        ],
        "firm_fields": ["capital_limits"],
        "system_prompt": """You are the risk manager for {firm_name}'s public finance desk.

Your job: assess whether the firm can absorb the capital commitment this deal requires.

Consider:
- Is the par amount within the firm's max single commitment? If it exceeds the limit, this is a hard Pass.
- Does the good faith deposit fit within available capacity?
- What is the firm's current inventory position — how much room is left?
- Firm commitment means the firm must purchase ALL bonds even if they can't resell them.
- What is the duration risk if bonds go unsold? Longer final maturities = more risk.
- Would the firm need syndicate partners to share this commitment?

You are the conservative voice. Your job is to protect the firm's capital.
Vote Pass if risk exceeds thresholds. Vote Conditional if the deal is manageable
with syndicate partners or if it's close to limits.

{firm_description}

You MUST respond with ONLY valid JSON in this exact format:
{{
  "agent": "size_capital",
  "vote": "interested" | "conditional" | "pass",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one to three sentences explaining your vote>",
  "conditions": ["<condition string>"] or []
}}"""
    },

    "structure": {
        "name": "Structure & Constraints",
        "question": "Are the bidding rules workable?",
        "nos_fields": [
            "coupon_provisions", "bid_evaluation.basis_of_award",
            "bid_evaluation.premium_discount_permitted",
            "bid_evaluation.minimum_bid_price",
            "bid_evaluation.max_interest_rate",
            "bid_evaluation.issue_price_requirements",
            "maturity_structure.maturity_schedule",
            "maturity_structure.maturity_type",
            "maturity_structure.bidder_term_bond_option",
            "redemption"
        ],
        "firm_fields": [],  # Structure agent doesn't need firm context
        "system_prompt": """You are the structuring desk analyst.

Your job: assess whether the bidding constraints in this NOS leave enough room for a profitable bid.

Consider:
- Does "ascending coupons only" combined with a rate cap eliminate viable structures?
- Does the maturity schedule work with the coupon restrictions?
- Is the basis of award (NIC vs TIC) standard? NIC and TIC produce different optimal coupon strategies.
- Will issue price requirements (hold-the-offering-price vs 10% test vs competitive sale exception) create problematic post-sale obligations?
- Does the minimum bid price constraint leave room for a profitable bid?
- Is the call structure standard (10yr par call) or unusual?
- For serial+term structures with sinking fund provisions, are the terms workable?

You are the technical voice. You don't need to know anything about the firm — you're evaluating the constraints purely on whether they allow a workable bid structure.

Flag any constraint combination that narrows the feasible set dangerously.
A standard structure with no unusual constraints is Interested.
A complex but workable structure is Conditional.
Constraints that eliminate all profitable structures is a Pass.

You MUST respond with ONLY valid JSON in this exact format:
{{
  "agent": "structure",
  "vote": "interested" | "conditional" | "pass",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one to three sentences explaining your vote>",
  "conditions": ["<condition string>"] or []
}}"""
    },

    "distribution": {
        "name": "Distribution Feasibility",
        "question": "Can we sell these bonds?",
        "nos_fields": [
            "bond_identification.par_amount", "bond_identification.tax_status",
            "bond_identification.bank_qualified",
            "maturity_structure.maturity_type",
            "maturity_structure.final_maturity_date",
            "maturity_structure.maturity_schedule",
            "credit_enhancement.credit_rating",
            "redemption.optional_redemption",
            "registration_delivery.denomination"
        ],
        "firm_fields": ["distribution_profile"],
        "system_prompt": """You are the distribution desk's voice at {firm_name}.

Your job: assess whether the firm's investor base has appetite for this paper.

Consider:
- Do the firm's accounts buy this maturity range? Short maturities (1-10yr) are typically retail; long maturities (15-30yr) are institutional.
- Is the par amount something the firm can distribute, or will bonds sit in inventory?
- Is bank-qualified status a demand driver? BQ bonds attract community banks at tighter yields.
- Is this tax-exempt or taxable? Does the firm have the right investor base for the tax status?
- Will the call structure make investors hesitant? Non-callable bonds are easier to place.
- Is the credit rated or unrated? Unrated bonds are harder to distribute to institutional accounts.
- Flag specific maturity ranges that may be hard to place given the firm's distribution strength.

{firm_description}

You MUST respond with ONLY valid JSON in this exact format:
{{
  "agent": "distribution",
  "vote": "interested" | "conditional" | "pass",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one to three sentences explaining your vote>",
  "conditions": ["<condition string>"] or []
}}"""
    },

    "calendar": {
        "name": "Calendar & Bandwidth",
        "question": "Do we have time and people?",
        "nos_fields": [
            "sale_logistics.sale_date", "sale_logistics.sale_time",
            "sale_logistics.bidding_platform",
            "registration_delivery.delivery_date"
        ],
        "firm_fields": ["current_pipeline", "bidding_capabilities"],
        "system_prompt": """You are the operations scheduler at {firm_name}.

Your job: assess whether the team has capacity to review the POS, prepare a bid, and handle settlement for this deal.

Consider:
- How many days until the sale date? The firm needs time to review the POS (typically 2-5 business days), form a syndicate if needed, and prepare the bid.
- How many other deals is the firm bidding on the same day or same week? Each concurrent bid requires analyst time.
- Do available analysts have capacity given the current pipeline?
- Is the bidding platform one the firm is set up on?
- Will the settlement/delivery overlap with other closings?
- If the sale is within 3 days and the POS hasn't been reviewed, this is a hard Pass — there isn't time.

This is the simplest agent. Your Pass votes are rare but they are hard vetoes — if the desk is maxed out, it doesn't matter how good the deal is.

Today's date is {today}.

{firm_description}

You MUST respond with ONLY valid JSON in this exact format:
{{
  "agent": "calendar",
  "vote": "interested" | "conditional" | "pass",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one to three sentences explaining your vote>",
  "conditions": ["<condition string>"] or []
}}"""
    }
}


# ── Field Extraction Helpers ────────────────────────────────────────

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


def extract_agent_nos_fields(nos_json: dict, field_paths: list[str]) -> dict:
    """Extract only the NOS fields relevant to a specific agent."""
    fields = {}
    for path in field_paths:
        value = _safe_get(nos_json, path)
        # Use the leaf key name for readability
        key = path.split(".")[-1] if "." in path else path
        # Handle top-level sections (e.g. "coupon_provisions", "redemption")
        if "." not in path:
            value = nos_json.get(path, {})
            key = path
        fields[key] = value
    return fields


def extract_agent_firm_fields(firm_profile: dict, field_keys: list[str]) -> dict:
    """Extract only the firm fields relevant to a specific agent."""
    fields = {}
    for key in field_keys:
        if key in firm_profile:
            fields[key] = firm_profile[key]
    return fields


# ── Agent Execution ────────────────────────────────────────────────

def run_agent_anthropic(
    agent_key: str,
    nos_json: dict,
    firm_profile: dict,
    api_key: str,
    model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Run a single screening agent using Claude API."""
    import anthropic
    import re
    from datetime import date

    agent_def = AGENT_DEFINITIONS[agent_key]

    # Extract relevant fields
    nos_fields = extract_agent_nos_fields(nos_json, agent_def["nos_fields"])
    firm_fields = extract_agent_firm_fields(firm_profile, agent_def["firm_fields"])

    # Build system prompt
    system = agent_def["system_prompt"].format(
        firm_name=firm_profile.get("firm_name", "the firm"),
        firm_description=firm_profile.get("firm_description", ""),
        today=date.today().isoformat()
    )

    # Build user message
    user_msg = f"""Here are the relevant NOS fields for your evaluation:

{json.dumps(nos_fields, indent=2)}"""

    if firm_fields:
        user_msg += f"""

Here is the relevant firm context:

{json.dumps(firm_fields, indent=2)}"""

    user_msg += "\n\nProvide your screening vote as JSON."

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text
    return _parse_agent_response(text, agent_key)


def run_agent_openai(
    agent_key: str,
    nos_json: dict,
    firm_profile: dict,
    api_key: str,
    model: str = "gpt-4o",
    base_url: str = "https://api.openai.com/v1"
) -> dict:
    """Run a single screening agent using OpenAI-compatible API."""
    import openai
    from datetime import date

    agent_def = AGENT_DEFINITIONS[agent_key]

    nos_fields = extract_agent_nos_fields(nos_json, agent_def["nos_fields"])
    firm_fields = extract_agent_firm_fields(firm_profile, agent_def["firm_fields"])

    system = agent_def["system_prompt"].format(
        firm_name=firm_profile.get("firm_name", "the firm"),
        firm_description=firm_profile.get("firm_description", ""),
        today=date.today().isoformat()
    )

    user_msg = f"""Here are the relevant NOS fields for your evaluation:

{json.dumps(nos_fields, indent=2)}"""

    if firm_fields:
        user_msg += f"""

Here is the relevant firm context:

{json.dumps(firm_fields, indent=2)}"""

    user_msg += "\n\nProvide your screening vote as JSON."

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )

    text = response.choices[0].message.content
    return _parse_agent_response(text, agent_key)


def _parse_agent_response(text: str, agent_key: str) -> dict:
    """Parse JSON from agent LLM response."""
    import re

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            result = json.loads(match.group())
        else:
            return {
                "agent": agent_key,
                "vote": "pass",
                "confidence": 0.0,
                "rationale": f"Agent response could not be parsed: {text[:200]}",
                "conditions": [],
                "error": "parse_failure"
            }

    # Normalize vote
    vote = result.get("vote", "pass").lower().strip()
    if vote not in ("interested", "conditional", "pass"):
        vote = "pass"

    # Normalize confidence
    confidence = result.get("confidence", 0.5)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "agent": agent_key,
        "vote": vote,
        "confidence": confidence,
        "rationale": result.get("rationale", ""),
        "conditions": result.get("conditions", [])
    }


# ── Parallel Agent Runner ──────────────────────────────────────────

def run_all_agents(
    nos_json: dict,
    firm_profile: dict,
    provider: str = "anthropic",
    agent_keys: list[str] | None = None
) -> list[dict]:
    """
    Run all 5 screening agents in parallel.
    Agents do NOT see each other's votes (prevents anchoring bias).

    Returns list of agent vote dicts.
    """
    if agent_keys is None:
        agent_keys = list(AGENT_DEFINITIONS.keys())

    # Configure provider
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("NOS_AGENT_MODEL", os.getenv("NOS_MODEL", "claude-sonnet-4-20250514"))
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        run_fn = lambda key: run_agent_anthropic(key, nos_json, firm_profile, api_key, model)
    else:
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL", "gpt-4o")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable not set")
        run_fn = lambda key: run_agent_openai(key, nos_json, firm_profile, api_key, model, base_url)

    votes = []

    print(f"Running {len(agent_keys)} agents in parallel...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=len(agent_keys)) as executor:
        futures = {
            executor.submit(run_fn, key): key
            for key in agent_keys
        }

        for future in as_completed(futures):
            agent_key = futures[future]
            try:
                result = future.result()
                agent_name = AGENT_DEFINITIONS[agent_key]["name"]
                print(f"  {agent_name:25s} → {result['vote'].upper():12s} "
                      f"(confidence: {result['confidence']:.2f})", file=sys.stderr)
                votes.append(result)
            except Exception as e:
                print(f"  {agent_key:25s} → ERROR: {e}", file=sys.stderr)
                votes.append({
                    "agent": agent_key,
                    "vote": "pass",
                    "confidence": 0.0,
                    "rationale": f"Agent execution error: {e}",
                    "conditions": [],
                    "error": str(e)
                })

    return votes

"""
NOS Screening Consensus Function

Deterministic Python — NOT another LLM call.
Aggregates 5 agent votes into a final screening decision.

Consensus Rules:
  1. Any single Pass with confidence >= 0.8 → PASS (hard veto)
  2. All five Interested → INTERESTED
  3. Mix of Interested/Conditional (no high-confidence Pass) → CONDITIONAL
  4. Multiple low-confidence Pass votes (< 0.8) → CONDITIONAL with escalation flag

Usage:
    from consensus import compute_consensus
    result = compute_consensus(votes)
"""

import json
from typing import Any


# Confidence threshold for a hard veto
VETO_CONFIDENCE_THRESHOLD = 0.8

# Number of low-confidence Pass votes that trigger escalation
LOW_CONFIDENCE_PASS_ESCALATION = 2


def compute_consensus(votes: list[dict]) -> dict:
    """
    Apply deterministic consensus rules to agent votes.

    Args:
        votes: List of agent vote dicts, each with:
            - agent: str (agent key)
            - vote: "interested" | "conditional" | "pass"
            - confidence: float 0.0-1.0
            - rationale: str
            - conditions: list[str]

    Returns:
        {
            "decision": "INTERESTED" | "CONDITIONAL" | "PASS",
            "rule_applied": str (which consensus rule determined the outcome),
            "reason": str (human-readable explanation),
            "conditions": list[str] (aggregated conditions from all agents),
            "escalation": bool (whether human review is recommended),
            "veto_agents": list[str] (agents that triggered veto, if any),
            "votes": list[dict] (the input votes, for reference)
        }
    """
    if not votes:
        return {
            "decision": "PASS",
            "rule_applied": "no_votes",
            "reason": "No agent votes received.",
            "conditions": [],
            "escalation": True,
            "veto_agents": [],
            "votes": []
        }

    # Classify votes
    interested = [v for v in votes if v["vote"] == "interested"]
    conditional = [v for v in votes if v["vote"] == "conditional"]
    pass_votes = [v for v in votes if v["vote"] == "pass"]

    high_confidence_pass = [v for v in pass_votes if v["confidence"] >= VETO_CONFIDENCE_THRESHOLD]
    low_confidence_pass = [v for v in pass_votes if v["confidence"] < VETO_CONFIDENCE_THRESHOLD]

    # Collect all conditions from conditional and interested-with-conditions votes
    all_conditions = []
    for v in votes:
        for cond in v.get("conditions", []):
            if cond and cond not in all_conditions:
                all_conditions.append(cond)

    # ── Rule 1: Hard veto — any Pass with confidence >= 0.8 ────
    if high_confidence_pass:
        veto_agents = [v["agent"] for v in high_confidence_pass]
        veto_rationales = [
            f"{_agent_name(v['agent'])} (confidence {v['confidence']:.2f}): {v['rationale']}"
            for v in high_confidence_pass
        ]
        return {
            "decision": "PASS",
            "rule_applied": "hard_veto",
            "reason": (
                f"Hard veto by {len(high_confidence_pass)} agent(s). "
                + " | ".join(veto_rationales)
            ),
            "conditions": all_conditions,
            "escalation": False,
            "veto_agents": veto_agents,
            "votes": votes
        }

    # ── Rule 2: Unanimous interested ───────────────────────────
    if len(interested) == len(votes):
        return {
            "decision": "INTERESTED",
            "rule_applied": "unanimous_interested",
            "reason": "All agents voted Interested. Proceed to POS review.",
            "conditions": all_conditions,
            "escalation": False,
            "veto_agents": [],
            "votes": votes
        }

    # ── Rule 4: Multiple low-confidence Pass → escalation ──────
    # (Check before Rule 3 because this is a special case of mixed votes)
    if len(low_confidence_pass) >= LOW_CONFIDENCE_PASS_ESCALATION:
        concern_agents = [
            f"{_agent_name(v['agent'])} (confidence {v['confidence']:.2f}): {v['rationale']}"
            for v in low_confidence_pass
        ]
        return {
            "decision": "CONDITIONAL",
            "rule_applied": "escalation_multiple_low_pass",
            "reason": (
                f"{len(low_confidence_pass)} agents voted Pass with low confidence — "
                f"escalating for human review. Concerns: "
                + " | ".join(concern_agents)
            ),
            "conditions": all_conditions,
            "escalation": True,
            "veto_agents": [],
            "votes": votes
        }

    # ── Rule 3: Mix of Interested/Conditional (maybe 1 low Pass) ─
    condition_sources = []
    for v in conditional:
        condition_sources.append(
            f"{_agent_name(v['agent'])}: {v['rationale']}"
        )
    for v in low_confidence_pass:
        condition_sources.append(
            f"{_agent_name(v['agent'])} (low-confidence pass): {v['rationale']}"
        )

    return {
        "decision": "CONDITIONAL",
        "rule_applied": "mixed_votes",
        "reason": (
            f"{len(interested)} Interested, {len(conditional)} Conditional, "
            f"{len(low_confidence_pass)} low-confidence Pass. "
            + (" | ".join(condition_sources) if condition_sources else "Proceed with conditions.")
        ),
        "conditions": all_conditions,
        "escalation": len(low_confidence_pass) > 0,
        "veto_agents": [],
        "votes": votes
    }


def _agent_name(agent_key: str) -> str:
    """Map agent key to human-readable name."""
    names = {
        "sector_fit": "Sector Fit",
        "size_capital": "Size & Capital",
        "structure": "Structure",
        "distribution": "Distribution",
        "calendar": "Calendar"
    }
    return names.get(agent_key, agent_key)


def format_consensus_report(result: dict) -> str:
    """Format consensus result as a human-readable report."""
    lines = []

    # Header
    decision = result["decision"]
    emoji_map = {"INTERESTED": "[GREEN]", "CONDITIONAL": "[AMBER]", "PASS": "[RED]"}
    lines.append(f"{'=' * 60}")
    lines.append(f"SCREENING DECISION: {emoji_map.get(decision, '')} {decision}")
    lines.append(f"{'=' * 60}")
    lines.append(f"Rule: {result['rule_applied']}")
    lines.append(f"Reason: {result['reason']}")

    if result["escalation"]:
        lines.append(f"*** ESCALATION FLAG: Human review recommended ***")

    if result["veto_agents"]:
        lines.append(f"Veto by: {', '.join(_agent_name(a) for a in result['veto_agents'])}")

    if result["conditions"]:
        lines.append(f"\nConditions:")
        for c in result["conditions"]:
            lines.append(f"  - {c}")

    # Individual votes
    lines.append(f"\n{'─' * 60}")
    lines.append("INDIVIDUAL AGENT VOTES:")
    lines.append(f"{'─' * 60}")

    for v in result.get("votes", []):
        name = _agent_name(v["agent"])
        vote = v["vote"].upper()
        conf = v["confidence"]
        lines.append(f"\n  {name}")
        lines.append(f"    Vote: {vote}  (confidence: {conf:.2f})")
        lines.append(f"    Rationale: {v.get('rationale', 'N/A')}")
        if v.get("conditions"):
            for c in v["conditions"]:
                lines.append(f"    Condition: {c}")
        if v.get("error"):
            lines.append(f"    ERROR: {v['error']}")

    lines.append(f"\n{'=' * 60}")
    return "\n".join(lines)


def main():
    """Test consensus with example votes from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Compute NOS screening consensus")
    parser.add_argument("votes_json", help="Path to JSON file with agent votes array")
    args = parser.parse_args()

    with open(args.votes_json) as f:
        votes = json.load(f)

    result = compute_consensus(votes)
    print(format_consensus_report(result))

    # Also save JSON output
    output_path = args.votes_json.replace(".json", "_consensus.json")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nJSON saved to: {output_path}")


if __name__ == "__main__":
    main()

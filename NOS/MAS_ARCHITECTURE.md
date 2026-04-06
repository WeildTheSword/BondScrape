# Multi-Agent System Architecture

## Overview

Five agents, each answering one screening question. All receive the extracted NOS JSON plus a shared firm profile. Agents run in parallel and do not see each other's votes (prevents anchoring bias). Consensus rule is deterministic Python, not another LLM call.

## Why MAS Over a Single LLM Call?

The skeptic's question: *"Why not just give one LLM the NOS JSON and ask 'should we pursue this deal?'"* It would probably work. A single well-prompted Claude call could output Interested / Conditional / Pass with a rationale.

Three things MAS actually buys you:

### 1. Explainability at the Dimension Level
A single LLM gives you one answer with one rationale. If it says Pass, you don't know if it's because of size, sector, timing, or constraints — you get a blended paragraph. With 5 agents, you get 5 separate votes with 5 separate rationales. When Risk votes Pass and the other 4 vote Interested, that's actionable information. Maybe the desk overrides Risk because they have unusual capacity this week.

### 2. The Veto Problem
A single LLM optimizes for a coherent, balanced answer. It hedges. If 4 out of 5 dimensions look great but one is a dealbreaker (the sale is tomorrow and there's no time for POS review), a single LLM will often say "Conditional" with a caveat buried in paragraph three. Separate agents with a hard veto rule solve this — Calendar Agent says Pass at 0.95 confidence, the deal is dead, full stop. The architecture enforces a decision rule that a single LLM tends to soften.

### 3. Different Context Per Agent
In production, the Distribution Agent would be loaded with the firm's actual investor order book. The Risk Agent would have current inventory positions. The Calendar Agent would have the real pipeline. That's proprietary data you can't put in a single prompt — both because of context window limits and because different people on the desk own different data.

## Agent Topology

```
                    ┌─────────────────┐
                    │   NOS JSON      │
                    │   (extracted)   │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  Firm Profile   │
                    │     JSON        │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
         │Sector   │   │Size &   │   │Structure│
         │Fit      │   │Capital  │   │         │
         └────┬────┘   └────┬────┘   └────┬────┘
              │              │              │
         ┌────┴────┐   ┌────┴────┐         │
         │Distri-  │   │Calendar │         │
         │bution   │   │         │         │
         └────┬────┘   └────┬────┘         │
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────┴────────┐
                    │   Consensus     │
                    │   Function      │
                    │ (deterministic) │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  INTERESTED /   │
                    │  CONDITIONAL /  │
                    │  PASS           │
                    └─────────────────┘
```

**Key:** All 5 agents run in parallel. No agent sees another's output. The consensus function is pure Python with no LLM call.

## Agent Specifications

### Agent 1: Sector Fit
- **Question:** "Is this our kind of deal?"
- **NOS Fields:** issuer type, state, bond type, tax status, purpose, bond counsel
- **Firm Context:** sector coverage map (states, issuer types, bond types, strategic priorities)
- **No Firm Context Alternative:** Cannot function without firm context
- **Veto Power:** Yes — wrong sector/geography = hard Pass

### Agent 2: Size & Capital
- **Question:** "Can we afford this commitment?"
- **NOS Fields:** par amount, commitment type, good faith deposit, delivery date, final maturity
- **Firm Context:** capital limits (max commitment, inventory cap, current positions, GFD capacity)
- **Math Check:** par amount vs max commitment, GFD vs deposit capacity, current inventory headroom
- **Veto Power:** Yes — exceeds capital limits = hard Pass

### Agent 3: Structure & Constraints
- **Question:** "Are the bidding rules workable?"
- **NOS Fields:** coupon constraints, basis of award, rate increment, premium/discount, min bid price, maturity schedule, issue price requirements, redemption provisions
- **Firm Context:** None — this agent is purely technical
- **Evaluates:** Whether constraint combinations leave room for a profitable bid
- **Key Insight:** ascending-coupons-only + tight rate cap + par floor = hard optimization problem
- **Veto Power:** Yes — if constraints eliminate all profitable structures

### Agent 4: Distribution Feasibility
- **Question:** "Can we sell these bonds?"
- **NOS Fields:** par amount, tax status, bank qualified, maturity type/range, credit rating, call structure, denomination
- **Firm Context:** distribution profile (retail vs institutional strength, BQ demand, taxable demand, sweet spot maturity range)
- **Evaluates:** Whether the firm's investor base has appetite for this paper
- **Veto Power:** Yes — no buyers for this paper = hard Pass

### Agent 5: Calendar & Bandwidth
- **Question:** "Do we have time and people?"
- **NOS Fields:** sale date, delivery date, bidding platform
- **Firm Context:** current pipeline (upcoming bids, analyst availability, POS review turnaround)
- **Simplest Agent:** Basically a lookup against the pipeline calendar
- **Veto Power:** Yes — if sale is tomorrow and POS hasn't been reviewed, deal is dead

## Consensus Rules

```python
if any(vote.confidence >= 0.8 and vote.decision == "pass"):
    return "PASS"    # Rule 1: Hard veto

if all(vote.decision == "interested"):
    return "INTERESTED"  # Rule 2: Unanimous

if count(vote.confidence < 0.8 and vote.decision == "pass") >= 2:
    return "CONDITIONAL"  # Rule 4: Escalation (human review)
    # with escalation=True

return "CONDITIONAL"  # Rule 3: Mixed votes
# with conditions aggregated from all agents
```

### Why This Ordering Matters
- Rule 1 (veto) runs first because a strong objection kills the deal regardless
- Rule 2 (unanimous) runs second because clean green lights should be fast
- Rule 4 (escalation) runs before Rule 3 because multiple uncertain Pass votes are more concerning than a mix of Interested/Conditional
- Rule 3 (mixed) is the catch-all — most real deals land here

## The "Conditional" Output

This is where the real value lives. Most NOS deals won't be a clean Interested or Pass. The Conditional outcome with attached conditions ("need syndicate for size," "confirm BQ status in POS," "tight calendar — prioritize POS review") is what turns a screening tool into an actionable triage system for the desk.

## Demo Approach

Run the same NOS with two (or more) different firm profiles to show the consensus flips:
- A $2.9M Texas MUD → **INTERESTED** for a Texas-focused regional firm
- The same $2.9M Texas MUD → **PASS** for a Northeast-only firm (Sector Fit veto)

The firm profile is the variable, not the agents. This is the moment the audience gets it: the system isn't saying the deal is good or bad in the abstract — it's saying whether *this firm* should pursue *this deal* right now.

## Anti-Patterns We Avoid

1. **No "meta-agent" synthesizing votes** — consensus is deterministic Python, not another LLM call that could soften vetoes
2. **No agent sees other agents' votes** — prevents anchoring bias and sycophantic agreement
3. **No debate rounds** — at the screening stage, the question is simple enough that independent parallel votes work better than iterative debate
4. **No shared context window** — each agent sees only its relevant NOS fields and firm context, not the full dump

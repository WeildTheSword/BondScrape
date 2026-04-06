# NOS Reasoning Chain

The NOS drives 10 distinct reasoning steps before the banker ever reads the POS for credit analysis. Each step uses only NOS fields.

## The Key Insight

The NOS isn't just administrative metadata — it contains the structural constraints that frame the entire bid. The POS comes later to refine the credit spread, but the structural reasoning is all NOS-driven.

---

## Step 1: Go / No-Go Screen
**Question:** Do we even want this deal?

**NOS fields:** bond type, issuer type, par amount, tax status, sale date

**Reasoning:**
- Does this fit our sector expertise?
- Can our distribution handle this size?
- Do we have bandwidth before the sale date?
- Tax-exempt or taxable — which investor base does that map to?

**Output:** Pursue / Pass / Monitor

*This is what the multi-agent screening system automates.*

---

## Step 2: Competitive Landscape Estimate
**Question:** How many bidders will show up?

**NOS fields:** par amount, bond type, issuer type, bidding platform

**Reasoning:**
- A $5M bank-qualified GO from a small school district on PARITY: 3-5 bidders
- A $200M state GO: 8-12 bidders
- More competition = tighter spreads needed to win

**Output:** Expected number of competing bids, aggressiveness required

---

## Step 3: Syndicate Formation Decision
**Question:** Solo bid or build a syndicate?

**NOS fields:** par amount, commitment type (always firm), good faith deposit

**Reasoning:**
- $10M deal — many firms solo bid
- $100M deal on firm commitment = $100M inventory risk → recruit syndicate members
- Good faith deposit (typically 1-2%) ties up capital

**Output:** Solo vs. syndicate, number of members needed

---

## Step 4: Constraint Mapping for the Scale
**Question:** What are the rules of my bid?

**NOS fields:** coupon rate constraints, rate increment, premium/discount permitted, minimum bid price, basis of award (NIC vs TIC)

**Reasoning:**
- Ascending coupons only → can't use high short-term coupon
- No premium allowed → can't bid above par
- TIC-based → time value of money matters, long-end coupons weighted differently vs NIC

**Output:** Feasible set of coupon/price combinations

---

## Step 5: Writing the Scale (Preliminary)
**Question:** What yields do we offer investors at each maturity?

**NOS fields:** maturity schedule, maturity type, dated date

**Reasoning:**
- Map each maturity against current MMD curve and Bond Buyer indexes
- Longer maturities get higher yields
- The "scale" is the core of the bid — reoffering yield for every maturity
- At this point using market data + NOS structure (credit analysis from POS refines later)

**Output:** Preliminary reoffering yield for every maturity

---

## Step 6: Call Option Valuation
**Question:** How does the call feature affect pricing?

**NOS fields:** optional redemption, call protection period, call price

**Reasoning:**
- 10-year par call on a 20-year bond → investors face reinvestment risk → higher yield demanded
- Non-callable → prices tighter
- Mandatory sinking fund on term bonds also affects pricing
- Adjust long end of scale based on embedded call option value

**Output:** Yield adjustment for callable maturities

---

## Step 7: Coupon Optimization
**Question:** What coupon rates minimize our NIC/TIC?

**NOS fields:** basis of award, coupon rate constraints, premium/discount permitted

**Reasoning:**
- Under NIC: premium bond (coupon above reoffering yield) generates cash that reduces NIC
- Under TIC: time value weighting changes optimal strategy
- Constraints limit the search space
- This is a genuine mathematical optimization problem — driven entirely by NOS fields

**Output:** Optimal coupon rate(s) for each maturity

---

## Step 8: Spread / P&L Estimation
**Question:** How much can we make?

**NOS fields:** par amount, preliminary scale

**Reasoning:**
- Typical spread: $5-$8 per $1,000 bond
- $50M deal = $250K-$400K gross revenue, split across syndicate
- P&L estimate determines whether deal is worth the capital commitment

**Output:** Estimated gross spread, management fee, net P&L

---

## Step 9: Issue Price / Tax Compliance Check
**Question:** What IRS rules apply to our bid?

**NOS fields:** issue price requirements, tax status, bank qualified

**Reasoning:**
- Hold-the-offering-price → restricts secondary market sales
- Competitive sale safe harbor → simpler
- Bank-qualified → commercial banks get tax deduction → different demand dynamics
- These drive investor targeting strategy

**Output:** Compliance requirements, investor targeting strategy

---

## Step 10: Inventory Risk Assessment
**Question:** What if we can't sell them all?

**NOS fields:** par amount, maturity type, delivery date, withdrawal restrictions

**Reasoning:**
- Firm commitment = own every bond
- 30-day settlement window = time to sell, but rate spike → bonds lose value in inventory
- Longer final maturities → more duration risk
- Decide: how much cushion in spread vs. how aggressive to bid to win

**Output:** Risk-adjusted bid, inventory reserve calculation

---

## Feature → Reasoning Category Mapping

| Category | Steps | Key Features |
|----------|-------|-------------|
| **Screening** | 1-2 | Bond type, issuer type, par amount, tax status, sale date, platform |
| **Capital structure** | 3 | Par amount, commitment type, good faith deposit |
| **Bid constraints** | 4, 7 | Coupon restrictions, rate increment, premium/discount, min bid, basis of award |
| **Pricing** | 5-6 | Maturity schedule, maturity type, dated date, call provisions, sinking fund |
| **Risk** | 10 | Delivery date, withdrawal restrictions, technology risk |

## What the NOS Does NOT Establish (Needs the POS)

- **Credit quality** — financial condition, tax base, debt ratios
- **Spread determination** — how many bps over MMD this issuer should price at
- **The actual scale** — yield per maturity requires credit analysis + market data
- **Legal risk** — pending litigation, covenant quality, security pledge adequacy

## The Document Pipeline

```
NOS posted by issuer
  → Screening: Interested / Conditional / Pass     ← THIS PROJECT
    → POS review: Credit approved / Declined        ← Future work
      → Bid preparation: Scale + coupons + price    ← Future work
        → Winning bid → Purchase → Resell
```

The NOS screening gate is the highest-leverage automation point because the POS is 100+ pages. If agents can reliably filter deals based on the 7-15 page NOS, analysts are saved from reading hundreds of pages for deals they never should have opened.

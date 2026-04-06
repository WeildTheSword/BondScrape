# NOS Feature Taxonomy

55 taggable features across 10 categories for classifying a Notice of Sale.

## How to Read This

Each feature has:
- **Name** — the field
- **Description** — what it means to an underwriter
- **Values** — possible categories with semantic color coding:
  - `[green]` favorable/positive
  - `[teal]` standard/common
  - `[blue]` informational
  - `[purple]` complex/structured
  - `[coral]` caution/notable
  - `[amber]` conditional/variable
  - `[red]` risk/negative
  - `[gray]` neutral/unspecified

---

## 1. Sale Logistics (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Sale date & time | When bids are due | `[gray]` Specific date/time |
| Bidding platform | Electronic platform for bid submission | `[blue]` Parity/Ipreo · `[blue]` Grant Street · `[gray]` Other |
| Bid format | How bids must be submitted | `[teal]` Electronic only · `[coral]` Written/fax allowed |
| Right to reject | Whether issuer may reject all bids | `[green]` Yes · `[red]` No |
| Pre-sale adjustment | Whether issuer can modify par/maturities before bid opening | `[amber]` Adjustable · `[gray]` Fixed |
| Award notification | How/when winner is notified | `[teal]` Same day · `[gray]` Next day |

## 2. Bond Identification & Structure (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Bond type | Fundamental obligation type | `[purple]` GO unlimited · `[purple]` GO limited · `[coral]` Revenue · `[amber]` Assessment · `[pink]` Certificate of obligation · `[blue]` Tax increment |
| Tax status | Federal income tax treatment | `[green]` Tax-exempt · `[red]` Taxable · `[amber]` AMT subject |
| Bank qualified | Section 265 qualified tax-exempt obligation (≤$10M) | `[green]` Yes · `[gray]` No |
| Issuer type | Classification of issuing entity | `[purple]` State · `[blue]` County · `[teal]` City/town · `[coral]` School district · `[amber]` Special district · `[pink]` Authority |
| Purpose / use of proceeds | What bond proceeds finance | `[blue]` New construction · `[teal]` Refunding · `[gray]` Equipment · `[amber]` Working capital · `[pink]` Mixed |
| Par amount | Total principal amount | `[gray]` <$5M · `[teal]` $5M-$25M · `[blue]` $25M-$100M · `[purple]` $100M+ |

## 3. Maturity & Amortization Structure (5 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Maturity type | How principal repayment is scheduled | `[teal]` Serial only · `[coral]` Term only · `[purple]` Serial + term · `[gray]` Single maturity |
| Maturity schedule | Specific years and amounts due | `[teal]` Fixed schedule · `[amber]` Bidder's option |
| Final maturity | Last date any principal is due | `[green]` ≤10yr · `[teal]` 10-20yr · `[blue]` 20-30yr · `[purple]` 30+yr |
| Mandatory sinking fund | Whether term bonds have required periodic redemptions | `[coral]` Yes · `[gray]` No · `[gray]` N/A |
| Dated date | Date from which interest begins to accrue | `[gray]` Specific date |

## 4. Coupon & Interest Provisions (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Interest payment frequency | How often bondholders receive interest | `[teal]` Semiannual · `[gray]` Annual · `[amber]` Other |
| Interest payment dates | Specific months interest is paid | `[gray]` Specific dates |
| Interest calculation basis | Day-count convention | `[teal]` 30/360 · `[coral]` Actual/actual · `[amber]` Actual/360 |
| Coupon rate constraints | Bidding limitations on interest rates | `[purple]` Ascending only · `[coral]` No zero coupon · `[red]` Max rate cap · `[amber]` Max # of rates · `[green]` No restrictions |
| Rate increment | Minimum coupon rate increment | `[teal]` 1/8 of 1% · `[blue]` 1/20 of 1% · `[gray]` Any multiple |
| Uniform rate per maturity | Whether split coupons are allowed | `[teal]` Required · `[amber]` Split coupon allowed |

## 5. Bid Evaluation & Award Criteria (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Basis of award | Metric determining winning bid | `[blue]` NIC · `[purple]` TIC · `[gray]` Other |
| Good faith deposit | Amount required with bid | `[teal]` 1% of par · `[coral]` 2% of par · `[gray]` Fixed amount |
| Deposit form | How deposit must be submitted | `[teal]` Wire transfer · `[gray]` Certified check · `[amber]` Surety bond |
| Premium / discount permitted | Whether bidders may offer above/below par | `[green]` Premium allowed · `[amber]` Discount allowed · `[gray]` Par only · `[teal]` Both |
| Minimum bid price | Floor on dollar bid | `[coral]` Specified floor · `[gray]` No minimum |
| Issue price requirements | IRS issue price regulations | `[purple]` Hold-the-offering-price · `[blue]` 10% test · `[teal]` Competitive sale exception |

## 6. Redemption Provisions (4 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Optional redemption | Whether issuer may call bonds early | `[coral]` Callable · `[green]` Non-callable · `[purple]` Make-whole call |
| Call protection period | How long before first call | `[red]` No protection · `[amber]` 5yr · `[teal]` 10yr · `[gray]` Other |
| Call price / premium | Redemption price for called bonds | `[teal]` At par (100%) · `[coral]` With premium · `[purple]` Declining premium |
| Extraordinary redemption | Events triggering mandatory early redemption | `[coral]` Yes · `[gray]` No |

## 7. Registration, Delivery & Form (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Book entry / certificated | Form in which bonds are issued | `[teal]` Book-entry only (DTC) · `[gray]` Certificated · `[amber]` Both |
| Denomination | Minimum face value | `[teal]` $5,000 · `[gray]` $1,000 · `[purple]` $100,000 · `[amber]` Other |
| Registrar / paying agent | Entity processing payments | `[gray]` Named entity |
| Delivery date | Expected settlement date | `[gray]` Specific date · `[teal]` ~30 days after sale |
| Delivery method | How bonds are delivered | `[teal]` DTC FAST · `[gray]` Physical delivery |
| CUSIP | Whether CUSIP numbers assigned | `[teal]` Assigned · `[amber]` Pending · `[gray]` Not stated |

## 8. Credit & Enhancement (3 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Credit rating(s) | Ratings from agencies | `[green]` AAA/Aaa · `[teal]` AA/Aa · `[blue]` A · `[amber]` BBB/Baa · `[red]` Below IG · `[gray]` Unrated |
| Bond insurance | Credit enhancement through insurance | `[green]` Insured · `[amber]` Bidder's option · `[gray]` Uninsured |
| Insurance provider restrictions | Rules around who may insure | `[coral]` Issuer discretion · `[teal]` Pre-selected · `[gray]` None stated |

## 9. Legal & Advisory Team (6 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Bond counsel | Law firm rendering legal opinion | `[gray]` Named firm |
| Disclosure counsel | Firm responsible for offering document | `[gray]` Named firm · `[teal]` Same as bond counsel · `[amber]` Not stated |
| Municipal advisor | Financial advisory firm | `[gray]` Named firm |
| Tax counsel | Separate tax opinion firm | `[gray]` Named firm · `[gray]` N/A |
| Legal opinion type | Form of bond counsel opinion | `[green]` Unqualified · `[amber]` Qualified |
| Continuing disclosure | Ongoing disclosure commitment (SEC Rule 15c2-12) | `[green]` Full compliance · `[amber]` Exempt · `[gray]` Not stated |

## 10. Bidder Obligations & Risk Allocation (5 features)

| Feature | Description | Values |
|---------|-------------|--------|
| Commitment type | Nature of underwriting commitment | `[purple]` Firm commitment · `[gray]` Best efforts |
| Reoffering price certification | Whether winner must certify offering prices | `[coral]` Required · `[gray]` Not required |
| Official statement responsibility | Who finalizes the OS | `[teal]` Issuer prepares · `[coral]` Winning bidder completes |
| Technology risk allocation | Who bears electronic bid transmission risk | `[red]` Bidder assumes all · `[amber]` Shared · `[gray]` Not stated |
| Withdrawal restrictions | Conditions preventing withdrawal after award | `[red]` No withdrawal post-award · `[coral]` Insurance failure not grounds · `[coral]` Rating change not grounds |

---

## Feature → Reasoning Mapping

The first thing a banker looks at is **bond identification** — bond type, issuer type, par amount, tax status, purpose. These answer "is this a deal I even care about?"

The second pass is **maturity/amortization** and **coupon constraints** — these drive how the scale gets written.

**Award criteria** are critical — NIC vs TIC changes bidding behavior fundamentally.

**Redemption provisions** are a major value driver — a non-callable bond prices differently than one with a 10-year par call.

### Quick Classification (80% of the screening decision)

These 5 features alone tell a banker about 80% of what they need:
1. **Bond type** + **Issuer type** — sector fit
2. **Par amount** — size/capital fit
3. **Basis of award** — bidding complexity
4. **Maturity type** — structure complexity
5. **Call provisions** — pricing complexity

### Feature → Agent Mapping

| Agent | Primary Features |
|-------|-----------------|
| Sector Fit | Bond type, issuer type, state, tax status, purpose |
| Size & Capital | Par amount, commitment type, good faith deposit, delivery date |
| Structure | Coupon constraints, basis of award, rate increment, premium/discount, maturity schedule, redemption |
| Distribution | Par amount, tax status, bank qualified, maturity range, rating, call structure |
| Calendar | Sale date, delivery date, bidding platform |

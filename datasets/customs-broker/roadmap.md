# From list to viable service — the next 3 steps

We now have: a regulated-import map, per-category broker-value scores, a targeting
method, and a working lead engine (`tools/fda_refusal_rank.py`). A ranked list is
not yet a business. Here are the three steps that make it one.

## Step 1 — Quantify the pain per account (price the opportunity)

A lead list converts only when each row carries a **dollar number**, not just a
score. For each ranked firm, estimate annual recoverable value:

- **Delay/refusal cost** = refusals × (avg demurrage + per-diem + reship/destroy +
  lost-sales). FDA IRR gives the refusal count; the rest are per-category constants.
- **Duty leakage** = estimated import value × (paid rate − optimal rate). Size import
  value from bill-of-lading volume or USITC DataWeb HTS×country averages.
- **Tail risk** = probability-weighted cost of an AD/CVD/UFLPA/seizure event for the
  category.

Output: `opportunity_usd` per account, so outreach leads with "you're likely losing
~$X/yr," not "you got refused." This is the single biggest conversion lever and
turns the score into a sales-qualified list.

## Step 2 — Productize the wedge: the automated "Import Health Report"

Build one repeatable, auto-generated artifact per account that *is* the offer:

- Their refusal history + most common charges (from IRR).
- Likely HTS misclassification and a duty-savings estimate.
- AD/CVD / UFLPA / PGA exposure flags for their commodity.
- A headline recoverable-dollar figure (Step 1).

Free report → paid fix. Land via the audit, expand into recurring entry filing and
compliance retainer. This makes outreach scalable (template + data, not bespoke
consulting) and gives a crisp activation metric: report sent → audit booked → first
entry filed.

## Step 3 — Stand up compliant delivery (build vs. partner)

To actually clear entries you need things a dataset can't provide:

- A **licensed customs broker** (individual license via the CBP exam + a national
  permit), **ACE** filing capability, a **customs bond** facility, and **E&O
  insurance**.
- Documented **reasonable-care SOPs** and 5-year recordkeeping.

The license path is slow, so the pragmatic launch is **partner, then build**:
white-label or revenue-share with an existing licensed broker (or a software-broker
/ broker-as-an-API provider) to deliver filings now, while the data + lead engine
remain the moat and the customer relationship. Bring the license in-house once volume
justifies it.

### The loop that compounds

Filed-entry outcomes (holds avoided, duty saved, refusals cleared) feed back to
recalibrate `broker-value-scores.csv` and the `lead_score` weights from *measured*
results instead of judgment — each delivered account sharpens the targeting for the
next. That feedback loop, plus the public-data lead engine, is the defensible part.

---

*Sequencing:* Step 1 needs only data we can already source; Step 2 packages it; Step 3
is the regulated/operational lift and the main capital + timeline decision. Validate
demand with Steps 1–2 (and a partner broker) before investing in an in-house license.

# U.S. Regulated Imports & the Licensed Customs Broker

A dataset of import commodity categories that, in practice, require a **licensed
U.S. customs broker** to file the entry, together with the federal agency that
actually controls each item's **admissibility** and the permits/forms involved.

## Project map

This folder grew from a dataset into a working scaffold for a brokerage/compliance
service. The pieces:

| Component | What it is |
| --- | --- |
| `regulated-imports.csv` | The core dataset (29 categories → agency, permit, broker role) — documented below |
| `broker-value-scores.csv` | Per-category scoring: where a good broker delivers the most value |
| `underserved-targeting.md` | Method for ranking importers most underserved (no/bad broker) |
| `tools/fda_refusal_rank.py` | Public-data lead engine: ranks FDA-refused firms by broker-value score |
| `classifier/` | AI **HTS code + PGA** classifier (Claude) with evals, pricing, validation, audit log |
| `roadmap.md` | The three steps from list → viable service |
| `BLOCKERS.md` | Access/tooling gaps (no network/key/paid data) + prioritized backlog |

Everything runs **offline** (deterministic mocks/samples) so it's testable here;
each piece notes what it needs to go live (an API key, the USITC HTS, the FDA export,
a bill-of-lading vendor). Start with `BLOCKERS.md` for what to tackle next.

---


## Important framing (read first)

A **licensed customs broker does *not* "approve" goods to enter the United
States.** That is a common misconception. The legal picture is:

- **U.S. Customs and Border Protection (CBP)** and the relevant **Partner
  Government Agencies (PGAs)** — FDA, USDA, EPA, ATF, FWS, DEA, CPSC, etc. —
  decide whether a given item is **admissible**. They can examine, detain,
  refuse, or seize a shipment.
- A **licensed customs broker** is a private individual or firm licensed *by
  CBP* to conduct "customs business" on an importer's behalf: classifying goods
  under the HTS, valuing them, filing the entry in the **ACE** system,
  transmitting the required PGA data, and paying duties/taxes/fees.

So there is **no category of merchandise that only a customs broker can
authorize**. What *does* exist is a large set of goods for which a **formal
entry** is required, and for which importers almost always engage a licensed
broker because the filing is complex and the PGA data requirements are strict.

### When a licensed broker is effectively required

- **Formal entry (Entry Type 01)** is required for commercial shipments valued
  **over $2,500**, and for goods subject to other-agency regulation, quotas,
  or additional duties — regardless of value. These are filed in ACE, typically
  by a licensed broker (Forms **3461** and **7501**).
- The **$800 de minimis** exemption was **suspended/eliminated worldwide on
  August 29, 2025**, so many low-value shipments that previously entered
  duty-free now require a formal or informal entry.
- An importer may file their own entries, but most use a broker; brokers are the
  only non-importers legally permitted to transact customs business for others.

## Files

- [`regulated-imports.csv`](./regulated-imports.csv) — the dataset (29 rows).

### Columns

| Column | Meaning |
| --- | --- |
| `category` | Commodity grouping |
| `example_items` | Representative goods in the category |
| `controlling_agency` | Agency that controls admissibility (the real "approver") |
| `key_permit_or_form` | Principal permit, license, or CBP/PGA form |
| `broker_role` | What the licensed customs broker actually does |
| `notes` | Caveats, common refusal reasons, related programs |

## Caveats

- **Not legal advice.** Requirements change frequently (tariffs, AD/CVD orders,
  de minimis policy, UFLPA enforcement). Verify against current CBP and PGA
  guidance before acting.
- The list is **representative, not exhaustive** — many goods are regulated by
  more than one agency, and some categories overlap.
- "Broker role" describes the *typical* commercial workflow, not a legal
  monopoly on entry.

## Sources

- [CBP — Entry of merchandise / formal vs. informal entry](https://www.cbp.gov/trade/programs-administration/entry-summary)
- [CBP — De minimis suspension guidance](https://info.expeditors.com/newsflash/cbp-publishes-guidance-for-de-minimis-suspension)
- [CBP — Collections since end of de minimis (Aug 29, 2025)](https://www.cbp.gov/newsroom/national-media-release/cbp-collects-1-billion-end-de-minimis-loophole)
- [Overview of Partner Government Agencies (PGAs)](https://usacustomsclearance.com/process/partner-government-agencies/)
- [Flexport — What is a Partner Government Agency?](https://support.portal.flexport.com/hc/en-us/articles/16593165775383-What-is-a-Partner-Government-Agency-PGA)
- [CBP — Customs broker licensing](https://www.cbp.gov/trade/programs-administration/customs-brokers)

# Outcomes of a Good Broker, and Targeting the Underserved

This builds on [`regulated-imports.csv`](./regulated-imports.csv) and
[`broker-value-scores.csv`](./broker-value-scores.csv). It answers three things:
what changes when an importer uses a competent licensed broker vs. not, where
the leverage is *dramatic*, and how to build a ranked list of brands that are
most underserved (no broker, or a bad one).

## 1. Outcomes — good broker vs. none/bad (all else equal)

| Dimension | No broker / bad broker | Competent broker | Why it differs |
| --- | --- | --- | --- |
| Border holds & exams | Higher exam/detention rate from missing or wrong PGA data | Correct PGA message set up front → "may proceed" faster | Brokers know each agency's data requirements |
| Clearance time | Days–weeks lost to holds, demurrage, per-diem | Hours–days | Time = storage cost + stockouts |
| Duty paid | Often the default/highest HTS rate | Optimized to the correct, lowest lawful rate | Classification + valuation expertise |
| Penalties (19 USC 1592) | Negligence/gross-negligence exposure, back-duties + interest | Documented "reasonable care" defense | Records + ruling discipline |
| Seizure / refusal / destruction | Real for FDA, FWS, ATF, EPA goods | Rare | Right permit, right port, right paperwork |
| AD/CVD & UFLPA | Evasion liability, forced-labor detentions | Pre-screened supply chain & deposits | EAPA/UFLPA awareness |
| Cash flow | Pay-per-entry, no deferral | Periodic monthly statement, bonds | Broker infrastructure |

## 2. Where the license helps a brand *dramatically*

Two levers dominate, and both scale with the `broker_value_score`:

1. **Landed-cost / duty optimization** — the recurring margin lever. Legitimate
   tools a good broker captures and a self-filer usually misses:
   - Correct HTS classification (wrong code = chronic over- or under-payment)
   - First-sale valuation, USMCA/FTA origin, Chapter 98 (9801/9802) returns
   - Tariff engineering, Foreign-Trade Zones, duty drawback
   - This can move **single to double-digit percent of landed cost** on
     high-duty goods (textiles/apparel, footwear, electronics, AD/CVD goods).
2. **Catastrophic-event avoidance** — the tail-risk lever. A single seizure,
   multi-year 1592 penalty case, EAPA evasion finding, or UFLPA detention can
   dwarf years of broker fees. Highest for tobacco/nicotine, wildlife, firearms,
   controlled substances, pharma/devices, and sanctioned-origin goods.

The brands with the most to gain sit where **both** are high: high duty/tariff
exposure **and** high PGA/penalty complexity. In the scores, that's **textiles &
apparel, tobacco/nicotine, consumer/children's goods, food, wildlife, and
seafood** — high score *and* large, fragmented importer populations.

## 3. Building the "most underserved" list

Underserved score = **value of getting it right** × **likelihood they're getting
it wrong**. The first factor we already have (the category score). The second
comes from external importer-level signals.

```
underserved_score(importer)
  = broker_value_score(their category)        # demand: how much it matters
  * underserved_probability(importer)          # signals they're unserved/badly served
  * size_weight(import value or volume)        # prioritize bigger prizes
```

### Signals of "no broker / bad broker" (most are public or licensable)

| Signal | Source | Why it indicates underservice |
| --- | --- | --- |
| FDA import **refusals** by firm | FDA Import Refusal Report (OASIS), monthly, public | Direct evidence of failed entries |
| **Self-filer** / no broker on record | Bill-of-lading & ACE-derived datasets | No professional representation |
| AD/CVD **EAPA** evasion cases | CBP determinations, public | Compliance failure |
| **UFLPA** detentions | CBP statistics + BoL origin | Supply-chain/compliance gap |
| **New importer** / no continuous bond | BoL data, first-appearance date | Inexperienced, high error rate |
| Heavy pre-2025 **de minimis / DTC** reliance | Carrier mix, channel, brand type | Newly exposed after Aug 2025 repeal |
| CBP penalties / liquidated damages | FOIA, litigation records | History of problems |
| High **exam/hold** frequency | BoL + trade-data providers | Operational friction |

### Data sources to assemble it

- **Bill-of-lading / manifest data** (importer + product + origin + volume, and
  sometimes broker): ImportYeti (free tier), Panjiva/S&P, ImportGenius,
  Descartes Datamyne, Trade Data Monitor. *Ocean only — air/truck not covered.*
- **FDA Import Refusal Report** — public, downloadable, names firms. Best single
  "bad current process" signal for FDA-regulated categories.
- **USITC DataWeb / Census** — HTS × country import value to size duty exposure.
- **CBP** — AD/CVD orders, EAPA determinations, UFLPA stats, broker license list.
- **Firmographics** — SAM.gov, state registries, enrichment (Clearbit/etc.).

### Suggested build steps

1. Pull BoL data for the high-score categories; dedupe to importer-of-record.
2. Join FDA refusals, AD/CVD/EAPA, UFLPA, new-importer, and channel signals.
3. Compute `underserved_probability` (weighted signal sum) and `size_weight`.
4. Multiply by the category `broker_value_score`; rank descending.
5. Segment by category for tailored outreach (the pain differs by commodity).

## Caveats

- Scores in `broker-value-scores.csv` are **structured judgment**, not measured
  outcomes — calibrate against real refusal/penalty data once joined.
- CBP does not broadly publish importer-of-record lists; named-brand targeting
  relies on the commercial BoL datasets above.
- Not legal advice; verify duty/AD-CVD/UFLPA specifics per shipment.

# Blockers & Limitations — what I couldn't finish, and how to tackle it

Everything in this folder was built in a sandboxed remote environment with **no
outbound network**, **no `ANTHROPIC_API_KEY`**, and **no third-party Python packages
installed**. That capped a few things at "scaffold + offline mock" rather than
"validated and running against real data." This file is the backlog to close those
gaps, organized around the core tenets you named: **data accessibility, accuracy,
completeness, and evals.**

Priority key: **P0** = blocks trust/production, **P1** = high value, **P2** = nice to have.

---

## 1. Evals (P0) — *harness built; still needs a real labeled set + key*

**Update:** the eval harness now exists — `classifier/evals/run_eval.py` scores HTS
accuracy at each level (chapter/heading/subheading/full), confidence calibration, and
PGA precision/recall, and runs today on a 15-row synthetic `labeled_sample.csv`. What
it can't yet give you is *real* numbers: the model hasn't been run (no key), and the
sample is synthetic. The classifier itself is still **unmeasured against ground truth**.

**Still blocked by:** no real labeled dataset; no API key to run the model.

**To tackle later:**
- Replace `labeled_sample.csv` with a real **labeled eval set**: 500–2,000 products
  with known-correct 10-digit HTS
  codes. Sources: your own historical entry summaries (CBP Form 7501), broker
  records, or CBP **CROSS** rulings (each ruling = a product description + the ruled
  HTS code — a near-perfect labeled pair).
- Define metrics at **each HTS level**: chapter (2-digit), heading (4), subheading
  (6), full (10). Report exact-match accuracy per level + a "duty-rate-equivalent"
  accuracy (did we land on a code with the same duty rate?).
- Add **confidence calibration**: bucket predictions by reported `confidence` and
  check that 0.9-confidence predictions are right ~90% of the time. The
  `review_required` threshold should be tuned from this curve, not guessed.
- Eval the **PGA layer separately**: precision/recall of agency flags vs. the true
  PGA set for each commodity.
- Acceptance bar before any real use: agree a target (e.g. ≥95% heading-level,
  ≥85% full-code on the eval set) and a max false-"no review needed" rate.
- Harness: a `evals/` runner that takes labeled CSV → runs `classify()` → emits a
  scorecard. Run it on every prompt/model change to catch regressions.

---

## 2. Data accessibility (P0) — *network was blocked; all live sources are stubs*

Outbound requests returned **403** in this environment. Every "real data" path is
therefore unwired or running on a sample.

| Needed data | Used instead | Why it matters |
| --- | --- | --- |
| **Full USITC HTS** (all ~19k codes, JSON/CSV) | a hand-written excerpt in `reference.py` | grounds the model, enables code **validation**, and makes prompt caching actually engage (needs ≥4096-token prefix) |
| **CBP CROSS rulings** corpus | none | retrieval grounding + a free labeled eval set (see §1) |
| **FDA Import Refusal Report** (OASIS) | `tools/sample/fda_refusals_sample.csv` (synthetic) | the lead engine's real input |
| **Bill-of-lading / manifest data** (Panjiva, ImportGenius, ImportYeti, Datamyne) | none | the named-importer side of the "underserved" list |
| **USITC DataWeb / Census** (HTS×country import value) | none | sizing duty exposure / `opportunity_usd` |
| **CBP AD/CVD, EAPA, UFLPA** datasets | none | tail-risk scoring |

**To tackle later:**
- Download the **USITC HTS** export and replace the `reference.py` excerpt; add a
  validator that rejects any model-returned `hts10` not present in the official table
  (kills hallucinated codes — directly serves *accuracy*).
- Pull the **FDA IRR** export and run `tools/fda_refusal_rank.py --input <file>` — the
  tool already accepts real exports; it just needs the file.
- Decide the **bill-of-lading data vendor** (free ImportYeti vs. paid Panjiva-class).
  This is the single fork that gates named-brand targeting — flagged earlier and
  still open.
- Stand up a small **ingest layer** (scheduled pulls + a stable schema) so these
  refresh instead of being one-off downloads.

---

## 3. The classifier was never run against a real model (P0)

No `ANTHROPIC_API_KEY` and the `anthropic` SDK isn't installed here, so
`hts_pga_classifier.py`, `api.py`, and `batch_classify.py` only exercised the
**offline mock**. The real Claude path (structured output parsing, adaptive thinking,
prompt-cache hit verification, the Batch API poll loop) is **unverified end-to-end**.

**To tackle later:**
- Run with a real key; confirm the structured-output JSON parses and the schema holds.
- Verify prompt caching actually engages once the full HTS reference is in place
  (`usage.cache_read_input_tokens > 0` on the 2nd+ request).
- Run `batch_classify.py` on a real CSV and confirm the poll-to-results loop and the
  50% batch pricing behave as expected.
- Sweep `effort` (low/medium/high) and `model` (opus/sonnet/haiku) against the §1
  eval set to pick the cost/accuracy point per use case.

---

## 4. Completeness gaps in the data I *did* build (P1)

These ran fine offline but are **representative, not exhaustive** — they need a domain
pass before they're authoritative.

- **`regulated-imports.csv`** — 29 categories; real coverage is broader and many goods
  are multi-agency. Cross-check against CBP's ACE **PGA message set** documentation.
- **`pga_rules.py`** — chapter→agency map covers the common chapters; gaps exist
  (several chapters unmapped) and some flags are coarse. Validate each mapping against
  the actual agency import requirements; de-duplicate near-identical flags
  (e.g. "FCC" vs "FCC (equipment authorization)").
- **`broker-value-scores.csv`** — scores are **structured judgment, not measured
  outcomes**. Recalibrate against real refusal/penalty/duty data once §2 lands.
- **`underserved-targeting.md`** — methodology only; the scoring formula needs real
  signal weights fit from data, not assumed.

---

## 5. Accuracy safeguards (P1) — *now built offline; needs data to activate*

**Update — these now exist:**
- **HTS code validation** — `classifier/hts_validator.py`; pass `classify(..., hts_table=…)`
  and an invalid code is rejected and forced to review. Activates when you load the
  real USITC HTS (§2).
- **Human-in-the-loop queue + audit log** — `classifier/store.py` (SQLite): logs every
  classification for the 5-year reasonable-care trail, queues `review_required` items,
  records broker corrections, and `export_corrections()` feeds them back as eval rows.
- **`opportunity_usd` pricing** — `classifier/pricing.py` turns a result into a dollar
  figure (placeholder constants until real duty rates / refusal actuals land).

**Still to do:**
- Wire `store.py` into the live `api.py` request path (log + enqueue on every call).
- **Binding-ruling path**: for high-value or genuinely ambiguous items, a workflow to
  request a CBP ruling rather than rely on a prediction.
- Replace pricing/validation placeholders with real USITC duty rates and the HTS table.

---

## 6. Couldn't open a PR / interact beyond the working branch (P2)

Per the environment's scope I committed to `claude/customs-broker-dataset-1q42lo` and
did **not** open a pull request (none was requested). When you're ready, open the PR
from that branch yourself, or ask and I'll do it.

---

## Suggested order of attack

1. **§1 + §2 together** — pull CROSS rulings: they're simultaneously the eval label
   set (§1) *and* free grounding data (§2). Highest leverage, unblocks "accuracy."
2. **§3** — run the classifier for real against the eval set; pick model/effort.
3. **§2** — wire the FDA IRR + choose the bill-of-lading vendor; turns the lead engine
   from sample to live.
4. **§5** — add HTS validation + the review queue + audit log before any real entry.
5. **§4** — domain pass on the PGA/category data for completeness.

Items 1–3 are the difference between "promising scaffold" and "something you can trust
on a real entry."

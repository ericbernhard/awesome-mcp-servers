# HTS + PGA Classifier

Automates the two most error-prone steps a licensed customs broker performs:
determining the **HTS code** for a product and identifying the **Partner Government
Agency (PGA) requirements** that gate its entry. HTS classification is the broker's
core margin lever (correct code = correct duty), so getting it right and auditable
is the point.

## Design

```
description ─▶ Claude (claude-opus-4-8)            ─▶ HTS code + GRI reasoning + confidence
                 · applies GRI 1–6, cites headings
                 · structured JSON (output_config.format)
                 · adaptive thinking
                 · static HTS reference cached (cache_control)
                       │
                       ▼
              pga_rules.agencies_for(code)         ─▶ PGA flags (FDA/USDA/EPA/ATF/FCC…)
                 · DETERMINISTic, chapter-driven
                 · never depends on the model
                       │
                       ▼
              review routing                       ─▶ review_required if low confidence
                                                       or PGA-regulated → licensed broker
```

**Why the split:** classification is a judgment task (good for an LLM); admissibility
is a legal mapping (must be deterministic and reproducible). The model proposes the
code; the rules layer attaches the authoritative agencies from the chapter.

**Guardrails baked in:**
- The model is told never to invent a code and to lower `confidence` when unsure —
  misclassification carries penalties under 19 U.S.C. 1592.
- Anything below the confidence threshold, or anything PGA-regulated, sets
  `review_required` → a **licensed broker reviews before entry**. The service never
  auto-files. For certainty, an importer requests a binding **CBP ruling**.

## Files

| File | Purpose |
| --- | --- |
| `hts_pga_classifier.py` | Core `classify()` + CLI (offline mock without an API key) |
| `pga_rules.py` | Deterministic HTS-chapter / keyword → PGA mapping |
| `reference.py` | System prompt, JSON output schema, static HTS/GRI reference |
| `api.py` | FastAPI service (`POST /classify`, `GET /healthz`) |
| `batch_classify.py` | Bulk catalog classification via the Batch API (50% cheaper) |
| `hts_validator.py` | Validate returned codes against the official HTS table |
| `pricing.py` | Estimate `opportunity_usd` per account from a result |
| `store.py` | SQLite audit log + human review queue (reasonable-care trail) |
| `report.py` | **Import Health Report** generator — the one-page prospect artifact |
| `evals/run_eval.py` | HTS-accuracy eval vs. labeled codes (CROSS rulings / 7501 data) |
| `evals/refusal_eval.py` | PGA/refusal-risk eval vs. **public FDA denial data** (no protected records) |
| `tests/test_all.py` | Tests for the deterministic layers (no key/network needed) |
| `requirements.txt` | `anthropic`, `fastapi`, `uvicorn` |

## Accuracy, evals, and recordkeeping

```bash
# eval scorecard (offline mock; add ANTHROPIC_API_KEY for real numbers)
python evals/run_eval.py
# -> HTS accuracy by level (chapter/heading/subheading/full),
#    confidence calibration buckets, PGA precision/recall/F1

# reject hallucinated codes once the real HTS table is loaded
python -c "from hts_validator import load_hts_table; t=load_hts_table('hts_2026.csv'); \
           from hts_pga_classifier import classify; print(classify('cotton t-shirt', hts_table=t)['hts_valid'])"

# dollar-size an account from a result
python pricing.py --chapter 61 --value 2000000 --shipments 300 --regulated

# audit + review queue (corrections feed back into the eval set)
python store.py --demo

# run the deterministic test suite
python tests/test_all.py

# generate an Import Health Report (the prospect artifact)
python report.py products.csv --importer "Acme Imports" --out acme.md

# eval PGA/refusal-risk against public FDA denial data (no protected records needed)
python evals/refusal_eval.py            # -> FDA-flag recall, review recall, miss-by-charge
```

### Two complementary evals

- **`run_eval.py`** — HTS-code accuracy. Needs *approved* labels (CROSS rulings, or
  your partner's filed 7501 lines). Measures exact-match by level + calibration.
- **`refusal_eval.py`** — PGA/refusal risk. Uses the **public FDA Import Refusal
  Report** (*denied* shipments with descriptions + charges) as ground truth: every
  refused good should have been flagged FDA-regulated and routed to review. Validates
  the compliance half with zero access to anyone's protected entry data.

## Usage

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

# one product
python hts_pga_classifier.py "men's knit cotton t-shirt" --material "100% cotton" --origin China

# service
uvicorn api:app --reload
curl -s localhost:8000/classify -H 'content-type: application/json' \
  -d '{"description":"USB WiFi adapter"}'

# bulk (CSV with a 'description' column)
python batch_classify.py products.csv --out classified.csv
```

Without `ANTHROPIC_API_KEY` the CLI/API run a clearly-labeled **offline mock**
(`"mock": true`, low confidence, `review_required: true`) so the pipeline and the PGA
layer are testable with zero dependencies and no network.

## Output shape

```json
{
  "hts10": "6109100012", "hts6": "610910", "chapter": "61",
  "heading_text": "T-shirts, singlets ... knitted or crocheted",
  "gri_path": "GRI 1; GRI 6", "confidence": 0.86,
  "rationale": "...", "missing_facts": [], "alternates": ["6109100040"],
  "pga_requirements": ["CBP (UFLPA, marking)", "CPSC (children)"],
  "review_required": true, "review_reason": "PGA-regulated / incomplete code",
  "model": "claude-opus-4-8", "mock": false, "disclaimer": "..."
}
```

## Model & cost notes

- Default **`claude-opus-4-8`** ($5 / $25 per MTok). For high-volume, lower-stakes
  catalogs, pass `--model claude-sonnet-4-6` ($3 / $15) or `claude-haiku-4-5`
  ($1 / $5) and raise the confidence threshold so more borderline calls escalate.
- **Prompt caching:** the static HTS/GRI reference sits behind a `cache_control`
  breakpoint, so per-request cost is dominated by the short product description.
  Caching only engages when that prefix is ≥4096 tokens on Opus 4.8 — true once the
  reference is the full USITC HTS + chapter notes (the bundled excerpt is a stand-in
  and won't cache on its own).
- **Batch API** halves cost for bulk onboarding and is the right tool for catalog
  imports.

## Production hardening (not in this scaffold)

- Replace `reference.py`'s excerpt with the **full USITC HTS** (published JSON/CSV) +
  **CBP CROSS** ruling excerpts, retrieved per query into the cached prefix.
- Validate returned `hts10` against the live HTS (reject codes that don't exist).
- Keep a human-in-the-loop queue for `review_required` items and feed broker
  corrections back as few-shot examples / eval cases.
- Log every classification (input, code, GRI path, confidence, reviewer) for the
  5-year recordkeeping and reasonable-care audit trail CBP expects.

*Not legal advice. Verify against current CBP/PGA guidance; use a licensed broker to
file and a CBP ruling for binding certainty.*

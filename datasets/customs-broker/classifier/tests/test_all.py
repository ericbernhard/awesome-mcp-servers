"""
Tests for the deterministic layers (no API key / network needed).

Runs under pytest if installed, or standalone:  python tests/test_all.py
Covers: PGA rules + dedup, HTS validator, pricing model, classifier mock contract,
the audit/review store, and the FDA refusal ranker.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import pga_rules          # noqa: E402
import hts_validator      # noqa: E402
import pricing            # noqa: E402
from hts_pga_classifier import classify  # noqa: E402
from store import Store   # noqa: E402


# ---- pga_rules -------------------------------------------------------------
def test_chapter_mapping():
    assert "USDA FSIS" in pga_rules.agencies_for("0201000000")        # meat
    assert any("FCC" in a for a in pga_rules.agencies_for("8517620090"))  # electronics

def test_keyword_overlay_adds_agency():
    flags = pga_rules.agencies_for("9999000000", "handheld laser pointer")
    assert any("CDRH" in a for a in flags)

def test_dedup_collapses_same_agency():
    flags = pga_rules.agencies_for("8517620090", "wifi router with bluetooth")
    keys = [pga_rules._agency_key(f) for f in flags]
    assert len(keys) == len(set(keys)), f"duplicate agency keys: {flags}"

def test_unknown_chapter_is_empty():
    assert pga_rules.agencies_for("4801000000") == []                 # newsprint, no PGA


# ---- hts_validator ---------------------------------------------------------
def test_validator_unknown_without_table():
    assert hts_validator.is_valid("6109100012", None) is None

def test_validator_with_table():
    table = {"6109100012"}
    assert hts_validator.is_valid("6109.10.0012", table) is True       # normalizes dots
    assert hts_validator.is_valid("9999999999", table) is False
    assert hts_validator.is_valid("61091", table) is False             # wrong length

def test_validator_forces_review_on_invalid():
    res = {"hts10": "0000000000", "review_required": False}
    hts_validator.validate_result(res, {"6109100012"})
    assert res["hts_valid"] is False and res["review_required"] is True


# ---- pricing ---------------------------------------------------------------
def test_opportunity_scales_with_value():
    low = pricing.estimate_opportunity({"chapter": "61", "pga_requirements": []},
                                       annual_import_value=100_000)
    high = pricing.estimate_opportunity({"chapter": "61", "pga_requirements": []},
                                        annual_import_value=1_000_000)
    assert high["duty_leakage_usd"] > low["duty_leakage_usd"] > 0

def test_tail_band_high_for_tobacco():
    o = pricing.estimate_opportunity({"chapter": "24", "pga_requirements": ["FDA (CTP)"]})
    assert o["tail_risk_band"] == "high"

def test_delay_cost_only_when_regulated():
    reg = pricing.estimate_opportunity({"chapter": "03", "pga_requirements": ["FDA"]},
                                       annual_shipments=200)
    unreg = pricing.estimate_opportunity({"chapter": "95", "pga_requirements": []},
                                         annual_shipments=200)
    assert reg["delay_refusal_usd"] > 0 and unreg["delay_refusal_usd"] == 0


# ---- classifier mock contract ----------------------------------------------
def test_mock_result_shape():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    r = classify("men's cotton t-shirt")
    for key in ("hts10", "chapter", "confidence", "pga_requirements",
                "review_required", "disclaimer", "mock"):
        assert key in r, f"missing {key}"
    assert r["mock"] is True
    assert r["review_required"] is True            # mock is always low-confidence

def test_classify_requires_description():
    try:
        classify("  ")
    except ValueError:
        return
    raise AssertionError("expected ValueError on empty description")


# ---- store -----------------------------------------------------------------
def test_store_roundtrip():
    s = Store(":memory:")
    sample = {"description": "x", "hts10": "6109100099", "chapter": "61",
              "confidence": 0.5, "review_required": True, "review_reason": "low confidence"}
    s.log(sample)
    qid = s.enqueue(sample)
    assert len(s.list_pending()) == 1
    s.resolve(qid, "6109100012", reviewer="t", note="")
    assert s.list_pending() == []
    corr = s.export_corrections()
    assert corr == [{"description": "x", "true_hts10": "6109100012"}]


# ---- fda refusal ranker ----------------------------------------------------
def test_fda_ranker_runs_on_sample():
    sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fda_refusal_rank", os.path.join(os.path.dirname(ROOT), "tools", "fda_refusal_rank.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    scores = mod.load_scores()
    assert scores and "Tobacco & nicotine products" in scores
    rows = mod.load_refusals(mod.SAMPLE_CSV)
    ranked = mod.rank(rows, scores)
    assert ranked and ranked[0]["lead_score"] >= ranked[-1]["lead_score"]


# ---- report generator ------------------------------------------------------
def test_report_builds():
    import report
    rep = report.build_report(
        [{"sku": "A1", "description": "men's cotton t-shirt", "annual_value": "1000000",
          "annual_shipments": "100"}],
        importer="Test Co")
    assert rep["importer"] == "Test Co" and rep["sku_count"] == 1
    assert rep["headline_opportunity_usd"] >= 0
    md = report.render_markdown(rep)
    assert "Import Health Report" in md and "opportunity" in md.lower()


# ---- refusal-risk eval -----------------------------------------------------
def test_refusal_eval_runs_on_sample():
    sys.path.insert(0, os.path.join(ROOT, "evals"))
    import refusal_eval
    rows = list(__import__("csv").DictReader(open(refusal_eval.DEFAULT_IRR)))
    rep = refusal_eval.run(rows, "product_description", "refusal_charges")
    assert rep["n"] > 0
    assert 0.0 <= rep["fda_flag_recall"] <= 1.0
    assert rep["review_recall"] == 1.0          # mock routes everything to review


def _run_standalone():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_standalone() else 1)

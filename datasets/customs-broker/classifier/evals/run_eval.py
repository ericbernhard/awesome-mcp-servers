#!/usr/bin/env python3
"""
Eval harness for the HTS + PGA classifier.

Takes a labeled CSV (`description` + `true_hts10`, optional attributes and `true_pga`),
runs classify() on each row, and prints a scorecard:

  * HTS exact-match accuracy at each level: chapter(2) / heading(4) / subheading(6) / full(10)
  * Confidence calibration: predicted-confidence buckets vs. actual full-code accuracy
  * PGA flag precision / recall / F1 (agency-key level, against `true_pga`)

    python evals/run_eval.py                              # bundled labeled sample
    python evals/run_eval.py --input labeled.csv --out scorecard.json
    ANTHROPIC_API_KEY=... python evals/run_eval.py        # real model

Without an API key it runs the offline mock — the harness still works, but the mock
returns no code, so HTS accuracy will read ~0 (chapter may match). That's expected:
the point here is to prove the scorecard runs end-to-end. Real numbers need a key and,
for full-code accuracy, the real HTS reference loaded into the classifier.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hts_pga_classifier import classify  # noqa: E402
from pga_rules import _agency_key, _dedupe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "labeled_sample.csv")
LEVELS = {"chapter": 2, "heading": 4, "subheading": 6, "full": 10}
ATTR_COLS = ("material", "intended_use", "country_of_origin")


def _norm(code):
    return "".join(c for c in (code or "") if c.isdigit())


def _split_pga(field):
    return [_agency_key(p) for p in (field or "").replace(";", ",").split(",") if p.strip()
            and _agency_key(p) not in ("", "NONE", "(NONE)")]


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def run(rows, **classify_kwargs):
    n = len(rows)
    level_hits = {k: 0 for k in LEVELS}
    buckets = {b: [0, 0] for b in ("0.0-0.5", "0.5-0.7", "0.7-0.9", "0.9-1.0")}  # [correct_full, total]
    pga_tp = pga_fp = pga_fn = 0
    details = []

    for r in rows:
        attrs = {c: r.get(c) for c in ATTR_COLS}
        res = classify(r["description"], attributes=attrs, **classify_kwargs)
        pred = _norm(res.get("hts10") or res.get("hts6") or res.get("chapter", ""))
        true = _norm(r["true_hts10"])

        per_level = {}
        for name, k in LEVELS.items():
            hit = len(pred) >= k and len(true) >= k and pred[:k] == true[:k]
            per_level[name] = hit
            if hit:
                level_hits[name] += 1

        conf = float(res.get("confidence", 0) or 0)
        b = ("0.9-1.0" if conf >= 0.9 else "0.7-0.9" if conf >= 0.7
             else "0.5-0.7" if conf >= 0.5 else "0.0-0.5")
        buckets[b][1] += 1
        if per_level["full"]:
            buckets[b][0] += 1

        if "true_pga" in r:
            pred_set = set(_dedupe([p for p in (res.get("pga_requirements") or [])]))
            pred_keys = {_agency_key(p) for p in pred_set}
            true_keys = set(_split_pga(r["true_pga"]))
            pga_tp += len(pred_keys & true_keys)
            pga_fp += len(pred_keys - true_keys)
            pga_fn += len(true_keys - pred_keys)

        details.append({"sku": r.get("sku", ""), "pred": res.get("hts10", ""),
                        "true": r["true_hts10"], "confidence": conf,
                        "levels": per_level, "review_required": res.get("review_required")})

    scorecard = {
        "n": n,
        "mock": details and any(d for d in details) and classify(rows[0]["description"]).get("mock"),
        "hts_accuracy": {k: round(level_hits[k] / n, 3) for k in LEVELS},
        "calibration": {b: {"n": t, "full_accuracy": round(c / t, 3) if t else None}
                        for b, (c, t) in buckets.items()},
        "pga": dict(zip(("precision", "recall", "f1"), _prf(pga_tp, pga_fp, pga_fn))),
    }
    return scorecard, details


def _print(sc):
    print(f"\n=== Eval scorecard (n={sc['n']}{' — MOCK' if sc['mock'] else ''}) ===")
    print("HTS exact-match accuracy by level:")
    for k, v in sc["hts_accuracy"].items():
        print(f"  {k:<11} {v:6.1%}")
    print("Confidence calibration (predicted bucket -> actual full-code accuracy):")
    for b, d in sc["calibration"].items():
        acc = "n/a" if d["full_accuracy"] is None else f"{d['full_accuracy']:.1%}"
        print(f"  {b:<9} n={d['n']:<3} acc={acc}")
    print(f"PGA flags: precision={sc['pga']['precision']:.1%} "
          f"recall={sc['pga']['recall']:.1%} f1={sc['pga']['f1']:.1%}")
    if sc["mock"]:
        print("\nNOTE: offline MOCK — HTS accuracy is ~0 by design. Add ANTHROPIC_API_KEY "
              "and the real HTS reference for meaningful numbers.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=SAMPLE)
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--out", default=None, help="write full scorecard + per-row detail to JSON")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input)))
    if not rows:
        sys.exit("no labeled rows in input")
    sc, details = run(rows, model=args.model, effort=args.effort)
    _print(sc)
    if args.out:
        json.dump({"scorecard": sc, "details": details}, open(args.out, "w"), indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

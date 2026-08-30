#!/usr/bin/env python3
"""
Refusal-based eval — validates the PGA / refusal-risk half of the system against
PUBLIC data, with no access to anyone's protected entry records.

Idea (per the "approved vs denied" framing): the FDA Import Refusal Report is a
public list of *denied* shipments with product descriptions and the refusal charge.
Every refused item is, by construction, an FDA-regulated good that a competent
process should have (a) flagged as FDA-regulated and (b) routed to broker review.

So we run the classifier + PGA layer over the refused descriptions and measure:
  * FDA-flag recall  — did agencies_for() flag FDA for this denied good?
  * review recall    — did the system route it to broker review?
  * by-charge breakdown — where do misses cluster (e.g. specific refusal reasons)?

A high score means the system would have caught these before they were refused.

    python evals/refusal_eval.py                       # bundled FDA sample (offline)
    python evals/refusal_eval.py --input fda_irr.csv   # real FDA IRR export
    ANTHROPIC_API_KEY=... python evals/refusal_eval.py # real model classification

Note: this evaluates *refusal risk / PGA flagging*, not HTS-code accuracy. For
HTS-code ground truth use CROSS rulings with run_eval.py. The two are complementary.
"""
import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hts_pga_classifier import classify  # noqa: E402

_CUSTOMS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_IRR = os.path.join(_CUSTOMS_ROOT, "tools", "sample", "fda_refusals_sample.csv")
DESC_COLS = ("product_description", "product description", "description", "product")
CHARGE_COLS = ("refusal_charges", "refusal charges", "charges")


def _col(fieldnames, options):
    low = {f.lower(): f for f in (fieldnames or [])}
    for o in options:
        if o in low:
            return low[o]
    return None


def run(rows, desc_col, charge_col, **classify_kwargs):
    fda_hits = review_hits = 0
    by_charge = Counter()
    by_charge_miss = Counter()
    misses = []

    for r in rows:
        desc = r.get(desc_col, "")
        if not desc:
            continue
        res = classify(desc, **classify_kwargs)
        flagged_fda = any("FDA" in a for a in res.get("pga_requirements", []))
        routed = bool(res.get("review_required"))
        fda_hits += flagged_fda
        review_hits += routed

        charge = (r.get(charge_col, "") or "").split(";")[0].split(",")[0].strip() or "(unknown)"
        by_charge[charge] += 1
        if not flagged_fda:
            by_charge_miss[charge] += 1
            misses.append({"description": desc, "charge": charge,
                           "flagged": res.get("pga_requirements", [])})

    n = sum(1 for r in rows if r.get(desc_col))
    return {
        "n": n,
        "fda_flag_recall": round(fda_hits / n, 3) if n else None,
        "review_recall": round(review_hits / n, 3) if n else None,
        "by_charge": {c: {"n": by_charge[c], "missed": by_charge_miss[c]} for c in by_charge},
        "misses": misses,
    }


def _print(rep):
    print(f"\n=== Refusal-risk eval (n={rep['n']}) — public FDA denial data ===")
    print(f"FDA-flag recall (denied good flagged FDA-regulated): {rep['fda_flag_recall']:.1%}")
    print(f"Review recall   (denied good routed to broker)     : {rep['review_recall']:.1%}")
    print("By refusal charge (missed = not flagged FDA):")
    for c, d in sorted(rep["by_charge"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {c[:38]:<40} n={d['n']:<3} missed={d['missed']}")
    if rep["misses"]:
        print(f"\n{len(rep['misses'])} misses — descriptions not flagged FDA (investigate keyword/chapter rules):")
        for m in rep["misses"][:10]:
            print(f"  - {m['description'][:50]} [{m['charge']}] -> {m['flagged']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=DEFAULT_IRR, help="FDA Import Refusal Report CSV")
    ap.add_argument("--model", default="claude-opus-4-8")
    args = ap.parse_args()

    reader = csv.DictReader(open(args.input))
    rows = list(reader)
    desc_col = _col(reader.fieldnames, DESC_COLS)
    charge_col = _col(reader.fieldnames, CHARGE_COLS)
    if not desc_col:
        sys.exit(f"no description column found (looked for {DESC_COLS}); headers={reader.fieldnames}")
    rep = run(rows, desc_col, charge_col, model=args.model)
    _print(rep)


if __name__ == "__main__":
    main()

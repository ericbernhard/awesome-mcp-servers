#!/usr/bin/env python3
"""
Import Health Report generator — the one-page artifact you hand a prospect.

Takes an importer's product list (and optionally their FDA refusal history) and
produces a broker-grade audit: SKUs at classification risk, PGA exposure, refusal
summary, and a headline dollar opportunity. This is the wedge offer in the roadmap.

Input CSV columns: description (required); optional sku, material, intended_use,
country_of_origin, annual_value (USD/yr for this SKU), annual_shipments.

    python report.py products.csv --importer "Acme Imports" --out acme_report.md
    python report.py products.csv --refusals their_fda_refusals.csv --format json

Runs offline (mock classifier) so the format is reviewable now; the numbers become
real with an ANTHROPIC_API_KEY and the calibrated duty rates in pricing.py.
"""
import argparse
import csv
import datetime
import json
import sys

from hts_pga_classifier import classify
from pricing import estimate_opportunity, TAIL_RISK


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_report(rows, importer="(importer)", refusals=None, model="claude-opus-4-8"):
    skus = []
    duty_sum = delay_sum = 0.0
    tail_values = [0.0]
    agencies = {}
    review_skus = []
    mock_flag = False

    for r in rows:
        attrs = {k: r.get(k) for k in ("material", "intended_use", "country_of_origin")}
        res = classify(r["description"], attributes=attrs, model=model)
        mock_flag = mock_flag or bool(res.get("mock"))
        value = _num(r.get("annual_value"))
        ships = _num(r.get("annual_shipments"))
        opp = estimate_opportunity(res, annual_import_value=value, annual_shipments=ships)

        duty_sum += opp["duty_leakage_usd"]
        delay_sum += opp["delay_refusal_usd"]
        tail_values.append(TAIL_RISK[opp["tail_risk_band"]])
        for a in res.get("pga_requirements", []):
            agencies.setdefault(a, []).append(r.get("sku") or r["description"][:40])

        entry = {
            "sku": r.get("sku", ""), "description": r["description"],
            "hts10": res.get("hts10", ""), "confidence": res.get("confidence"),
            "pga": res.get("pga_requirements", []),
            "review_required": res.get("review_required"),
            "review_reason": res.get("review_reason"),
            "opportunity_usd": opp["opportunity_usd"],
        }
        skus.append(entry)
        if res.get("review_required"):
            review_skus.append(entry)

    # Tail risk is one catastrophic event, not one per SKU — take the worst band.
    headline = round(duty_sum + delay_sum + max(tail_values), 2)
    return {
        "importer": importer,
        "generated": datetime.date.today().isoformat(),
        "sku_count": len(skus),
        "headline_opportunity_usd": headline,
        "duty_leakage_usd": round(duty_sum, 2),
        "delay_refusal_usd": round(delay_sum, 2),
        "max_tail_risk_usd": max(tail_values),
        "review_flagged": review_skus,
        "pga_exposure": {a: skus_ for a, skus_ in sorted(agencies.items())},
        "refusal_history": refusals or [],
        "skus": skus,
        "mock": mock_flag,
    }


def render_markdown(rep):
    L = []
    L.append(f"# Import Health Report — {rep['importer']}")
    L.append(f"_Generated {rep['generated']} · {rep['sku_count']} SKUs reviewed_\n")
    if rep["mock"]:
        L.append("> **DRAFT / MOCK** — figures are illustrative until the classifier "
                 "runs against the live model and calibrated duty rates.\n")

    L.append("## Estimated annual opportunity\n")
    L.append(f"**~${rep['headline_opportunity_usd']:,.0f}/yr** recoverable, comprising:")
    L.append(f"- Duty leakage (classification/valuation): ${rep['duty_leakage_usd']:,.0f}")
    L.append(f"- Delay & refusal cost: ${rep['delay_refusal_usd']:,.0f}")
    L.append(f"- Tail risk avoided (AD/CVD, UFLPA, seizure, penalty): ${rep['max_tail_risk_usd']:,.0f}\n")

    L.append("## Classification risk\n")
    if rep["review_flagged"]:
        L.append(f"{len(rep['review_flagged'])} of {rep['sku_count']} SKUs need broker "
                 "review (low confidence, incomplete code, or PGA-regulated):\n")
        L.append("| SKU | Description | Code | Why |")
        L.append("|---|---|---|---|")
        for s in rep["review_flagged"][:25]:
            L.append(f"| {s['sku']} | {s['description'][:40]} | {s['hts10'] or '—'} | {s['review_reason']} |")
    else:
        L.append("No SKUs flagged for review.")
    L.append("")

    L.append("## Partner Government Agency exposure\n")
    if rep["pga_exposure"]:
        L.append("| Agency | SKUs affected |")
        L.append("|---|---|")
        for a, sk in rep["pga_exposure"].items():
            L.append(f"| {a} | {len(sk)} |")
    else:
        L.append("No PGA-regulated goods detected.")
    L.append("")

    if rep["refusal_history"]:
        L.append("## Recent import refusals (your history)\n")
        for r in rep["refusal_history"][:10]:
            L.append(f"- {r}")
        L.append("")

    L.append("## Recommended next step\n")
    L.append("A licensed customs broker reviews the flagged SKUs, confirms the correct "
             "HTS classification and PGA handling, and files corrected/compliant entries "
             "under a Power of Attorney. For binding certainty on high-value items, "
             "request a CBP ruling.\n")
    L.append("_Advisory estimate, not legal advice or a CBP ruling. Figures depend on "
             "your actual import values and duty rates._")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="CSV of products (needs a 'description' column)")
    ap.add_argument("--importer", default="(importer)")
    ap.add_argument("--refusals", help="optional CSV/text of prior refusals (one per line or a 'description' column)")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.input)))
    if not rows:
        sys.exit("no product rows in input")
    refusals = []
    if args.refusals:
        with open(args.refusals) as f:
            try:
                refusals = [r.get("description") or next(iter(r.values()))
                            for r in csv.DictReader(f)]
            except Exception:
                f.seek(0)
                refusals = [ln.strip() for ln in f if ln.strip()]

    rep = build_report(rows, importer=args.importer, refusals=refusals, model=args.model)
    out = json.dumps(rep, indent=2) if args.format == "json" else render_markdown(rep)
    if args.out:
        open(args.out, "w").write(out)
        print(f"wrote {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()

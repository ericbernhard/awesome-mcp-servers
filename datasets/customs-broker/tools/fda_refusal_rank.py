#!/usr/bin/env python3
"""
Rank firms appearing in the FDA Import Refusal Report (IRR) as customs-brokerage
leads, weighted by our per-category broker_value_score.

This is the "no paid data" lead engine: FDA import refusals are public, so a firm
showing up here is direct, free evidence of a broken import process — exactly the
"underserved" signal from underserved-targeting.md.

Data: the FDA IRR cannot be fetched from this sandbox (network policy blocks it),
so download it yourself and pass --input. A runnable sample is bundled.

  Source : FDA Import Refusal Report / OASIS
           https://datadashboard.fda.gov/ora/cd/imprefusals.htm  (export to CSV)
  Run    : python3 fda_refusal_rank.py                       # uses bundled sample
           python3 fda_refusal_rank.py --input refusals.csv  # real export
           python3 fda_refusal_rank.py --top 50 --out leads.csv

Expected input columns (case-insensitive; common IRR export headers are aliased):
  refusal_date, firm_name, country, product_description, fda_industry, refusal_charges

Output: one row per firm, ranked by lead_score, with the mapped category, the
broker_value_score driving it, refusal volume, charge diversity, and recency.
No third-party dependencies (stdlib only).
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_CSV = os.path.join(os.path.dirname(HERE), "broker-value-scores.csv")
SAMPLE_CSV = os.path.join(HERE, "sample", "fda_refusals_sample.csv")

# Map FDA "industry" / product wording -> our dataset category (regulated-imports.csv).
# Checked in order; first keyword hit wins. FDA does not cover meat/poultry (USDA).
INDUSTRY_RULES = [
    (("tobacco", "vape", "e-cig", "nicotine"), "Tobacco & nicotine products"),
    (("seafood", "fish", "shrimp", "crab", "tilapia", "tuna"), "Fish & seafood (monitored species)"),
    (("cosmetic", "beauty", "skin", "makeup", "lip", "fragrance"), "Cosmetics"),
    (("device", "surgical", "diagnostic", "implant"), "Medical devices"),
    (("drug", "pharma", "biologic", "tablet", "api"), "Drugs & pharmaceuticals"),
    (("radiolog", "radiation", "laser", "uv ", "x-ray", "microwave", "sterilizer lamp"),
     "Radiation-emitting electronics"),
    (("food", "produce", "beverage", "vegetable", "mushroom", "canned", "dietary"),
     "Human food & beverages"),
]
DEFAULT_CATEGORY = "Human food & beverages"  # FDA's largest bucket

# Header aliases so real IRR exports (which vary) map onto our field names.
HEADER_ALIASES = {
    "refusal_date": {"refusal_date", "refusal date", "date", "ref_date"},
    "firm_name": {"firm_name", "firm name", "firm", "manufacturer/shipper", "name"},
    "country": {"country", "country of origin", "origin"},
    "product_description": {"product_description", "product description", "product", "description"},
    "fda_industry": {"fda_industry", "fda industry", "industry", "industry_name", "product_area"},
    "refusal_charges": {"refusal_charges", "refusal charges", "charges", "fda_charges"},
}


def load_scores():
    scores = {}
    with open(SCORES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            scores[r["category"]] = int(r["broker_value_score"])
    return scores


def map_category(industry, product):
    # Product description wins over the industry label: FDA's combined industry
    # name is literally "Food/Cosmetics", which would otherwise mis-route food.
    for blob in (product.lower(), industry.lower()):
        for keys, cat in INDUSTRY_RULES:
            if any(k in blob for k in keys):
                return cat
    return DEFAULT_CATEGORY


def normalize_headers(fieldnames):
    """Return {our_field: actual_header} for whatever headers the file has."""
    lower = {fn.lower().strip(): fn for fn in fieldnames}
    out = {}
    for ours, aliases in HEADER_ALIASES.items():
        for a in aliases:
            if a in lower:
                out[ours] = lower[a]
                break
    return out


def parse_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def load_refusals(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            sys.exit(f"error: no header row in {path}")
        cols = normalize_headers(reader.fieldnames)
        missing = {"firm_name"} - set(cols)
        if missing:
            sys.exit(f"error: required column firm_name not found in {path} "
                     f"(headers seen: {reader.fieldnames})")
        rows = []
        for raw in reader:
            rows.append({k: raw.get(v, "").strip() for k, v in cols.items()})
    return rows


def rank(rows, scores):
    firms = defaultdict(lambda: {
        "refusals": 0, "charges": set(), "products": set(),
        "country": "", "category": "", "last": None,
    })
    max_date = None
    for r in rows:
        firm = r.get("firm_name", "").strip()
        if not firm:
            continue
        cat = map_category(r.get("fda_industry", ""), r.get("product_description", ""))
        d = parse_date(r.get("refusal_date", ""))
        f = firms[firm]
        f["refusals"] += 1
        f["category"] = cat
        f["country"] = r.get("country", "") or f["country"]
        for c in (r.get("refusal_charges", "") or "").replace(";", ",").split(","):
            c = c.strip()
            if c:
                f["charges"].add(c)
        if r.get("product_description"):
            f["products"].add(r["product_description"])
        if d:
            f["last"] = max(d, f["last"]) if f["last"] else d
            max_date = max(d, max_date) if max_date else d

    out = []
    for firm, f in firms.items():
        score = scores.get(f["category"], 0)
        # Recency multiplier relative to the newest refusal in the dataset, so the
        # ranking is stable regardless of when the script is run.
        recency = 1.0
        if f["last"] and max_date:
            age = (max_date - f["last"]).days
            recency = 1.0 if age <= 90 else (0.8 if age <= 180 else 0.6)
        # lead_score: volume x how much a good broker matters x charge breadth x recency.
        lead = round(f["refusals"] * score * (1 + 0.15 * (len(f["charges"]) - 1)) * recency, 1)
        out.append({
            "firm_name": firm,
            "category": f["category"],
            "broker_value_score": score,
            "refusals": f["refusals"],
            "distinct_charges": len(f["charges"]),
            "country": f["country"],
            "last_refusal": f["last"].isoformat() if f["last"] else "",
            "top_charges": "; ".join(sorted(f["charges"])[:4]),
            "lead_score": lead,
        })
    out.sort(key=lambda x: -x["lead_score"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=SAMPLE_CSV,
                    help="FDA Import Refusal Report CSV export (default: bundled sample)")
    ap.add_argument("--top", type=int, default=20, help="rows to print (default 20)")
    ap.add_argument("--out", default=None, help="write full ranked list to this CSV")
    args = ap.parse_args()

    using_sample = os.path.abspath(args.input) == os.path.abspath(SAMPLE_CSV)
    if using_sample:
        print("NOTE: using bundled SAMPLE data (network-blocked sandbox). "
              "Pass --input with a real FDA IRR export for live leads.\n")

    scores = load_scores()
    rows = load_refusals(args.input)
    ranked = rank(rows, scores)

    cols = ["firm_name", "category", "broker_value_score", "refusals",
            "distinct_charges", "country", "last_refusal", "lead_score"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in ranked)) for c in cols} if ranked else {}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    print("  ".join("-" * widths[c] for c in cols))
    for r in ranked[:args.top]:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ranked[0].keys()) if ranked else [])
            w.writeheader()
            w.writerows(ranked)
        print(f"\nWrote {len(ranked)} ranked leads -> {args.out}")


if __name__ == "__main__":
    main()

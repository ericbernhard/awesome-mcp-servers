#!/usr/bin/env python3
"""
Estimate the annual dollar opportunity of getting an account's classification and
PGA handling right — the number that turns a classifier result into an outreach line
("you're likely losing ~$X/yr"). Roadmap Step 1.

    opportunity_usd = duty_leakage + delay_refusal_cost + tail_risk

All constants below are PLACEHOLDERS for sizing the model; replace with measured
values once you have the USITC HTS duty rates, demurrage/per-diem actuals, and your
own refusal/penalty history. Every figure is an estimate, not a quote.
"""
import argparse
import json

# Placeholder average ad-valorem duty rate by HTS chapter (fraction of value).
# Real rates come from the USITC HTS column-1 general rate per subheading.
CHAPTER_DUTY_RATE = {
    "61": 0.16, "62": 0.14, "63": 0.09, "64": 0.10,   # apparel/textiles/footwear: high
    "42": 0.08, "43": 0.04,
    "85": 0.03, "84": 0.02, "90": 0.02, "87": 0.025,   # machinery/electronics/vehicles
    "22": 0.05, "24": 0.35,                             # spirits low ad-valorem; tobacco high excise
    "39": 0.05, "40": 0.04, "94": 0.03, "95": 0.0,     # toys often free
    "72": 0.0, "73": 0.0, "76": 0.0,                   # base metals often free but AD/CVD-heavy
}
DEFAULT_DUTY_RATE = 0.035

# Assumed share of duty recoverable by correct classification / FTA / valuation work
# when the current process is wrong. Conservative placeholder.
RECOVERABLE_DUTY_FRACTION = 0.20

# Cost of a single PGA hold / refused shipment (demurrage + per-diem + reship/destroy
# + lost sales), averaged. Placeholder.
COST_PER_REFUSAL_EVENT = 4200.0
# Probability a PGA-regulated shipment hits a hold under a bad/no-broker process.
P_HOLD_IF_REGULATED = 0.06

# Tail-risk: probability-weighted annual cost of a catastrophic event
# (AD/CVD/EAPA, UFLPA detention, seizure, 1592 penalty) by exposure level.
TAIL_RISK = {"high": 25000.0, "medium": 6000.0, "low": 1000.0}
HIGH_RISK_CHAPTERS = {"24", "93", "29", "30", "72", "73", "76"}  # tobacco, arms, chem, pharma, AD/CVD metals


def _chapter(result):
    return (result.get("chapter") or (result.get("hts10") or "")[:2] or "").zfill(2)[:2]


def _tail_band(result):
    ch = _chapter(result)
    pga = result.get("pga_requirements") or []
    if ch in HIGH_RISK_CHAPTERS or any("AD/CVD" in p or "ATF" in p or "DDTC" in p for p in pga):
        return "high"
    return "medium" if pga else "low"


def estimate_opportunity(result, *, annual_import_value=None, annual_shipments=None):
    """Return a dollar-opportunity breakdown for one classified account/SKU.

    annual_import_value : USD/yr imported under this commodity (from BoL or DataWeb)
    annual_shipments    : count of entries/yr (for delay-cost sizing)
    """
    ch = _chapter(result)
    duty_rate = CHAPTER_DUTY_RATE.get(ch, DEFAULT_DUTY_RATE)

    duty_leakage = 0.0
    if annual_import_value:
        duty_leakage = annual_import_value * duty_rate * RECOVERABLE_DUTY_FRACTION

    delay_cost = 0.0
    if annual_shipments and (result.get("pga_requirements")):
        delay_cost = annual_shipments * P_HOLD_IF_REGULATED * COST_PER_REFUSAL_EVENT

    band = _tail_band(result)
    tail = TAIL_RISK[band]

    total = round(duty_leakage + delay_cost + tail, 2)
    return {
        "opportunity_usd": total,
        "duty_leakage_usd": round(duty_leakage, 2),
        "delay_refusal_usd": round(delay_cost, 2),
        "tail_risk_usd": tail,
        "tail_risk_band": band,
        "assumed_duty_rate": duty_rate,
        "basis": "PLACEHOLDER constants — recalibrate with USITC duty rates and your "
                 "own refusal/penalty actuals before quoting.",
    }


def main():
    ap = argparse.ArgumentParser(description="Estimate $ opportunity from a classifier result (JSON on stdin or --chapter).")
    ap.add_argument("--chapter", help="2-digit HTS chapter (if not piping a full result)")
    ap.add_argument("--value", type=float, default=None, help="annual import value USD")
    ap.add_argument("--shipments", type=int, default=None, help="annual shipment count")
    ap.add_argument("--regulated", action="store_true", help="mark as PGA-regulated (for --chapter mode)")
    args = ap.parse_args()

    if args.chapter:
        result = {"chapter": args.chapter,
                  "pga_requirements": ["(assumed)"] if args.regulated else []}
    else:
        import sys
        result = json.load(sys.stdin)
    print(json.dumps(estimate_opportunity(
        result, annual_import_value=args.value, annual_shipments=args.shipments), indent=2))


if __name__ == "__main__":
    main()

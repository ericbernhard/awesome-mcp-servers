#!/usr/bin/env python3
"""
Bulk classification via the Message Batches API (50% cheaper, async).

Use this for catalog onboarding — classify thousands of SKUs at once instead of
one synchronous call each. Reads a CSV with a `description` column (optional
`sku`, `material`, `intended_use`, `country_of_origin`) and writes a results CSV.

    export ANTHROPIC_API_KEY=...
    python batch_classify.py products.csv --out classified.csv

PGA flags are still attached deterministically from each returned chapter/code.
Requires the anthropic SDK and a real key (no offline mock for the batch path).
"""
import argparse
import csv
import json
import sys
import time

from pga_rules import agencies_for
from reference import HTS_REFERENCE, OUTPUT_SCHEMA, SYSTEM_INSTRUCTIONS
from hts_pga_classifier import DEFAULT_MODEL, DISCLAIMER, _user_prompt


def _params(description, attributes, model, effort):
    return {
        "model": model,
        "max_tokens": 8000,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort,
                          "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        "system": [
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {"type": "text", "text": HTS_REFERENCE, "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [{"role": "user", "content": _user_prompt(description, attributes)}],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="CSV with a 'description' column")
    ap.add_argument("--out", default="classified.csv")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--threshold", type=float, default=0.8)
    args = ap.parse_args()

    try:
        import anthropic
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
    except ImportError:
        sys.exit("anthropic SDK required: pip install anthropic")

    rows = list(csv.DictReader(open(args.input)))
    if not rows:
        sys.exit("no rows in input")
    client = anthropic.Anthropic()

    requests = []
    for i, r in enumerate(rows):
        attrs = {k: r.get(k) for k in ("material", "intended_use", "country_of_origin")}
        requests.append(Request(
            custom_id=r.get("sku") or f"row-{i}",
            params=MessageCreateParamsNonStreaming(
                **_params(r["description"], attrs, args.model, args.effort)),
        ))

    batch = client.messages.batches.create(requests=requests)
    print(f"submitted batch {batch.id} ({len(requests)} items); polling…")
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        time.sleep(30)

    descriptions = {(r.get("sku") or f"row-{i}"): r["description"] for i, r in enumerate(rows)}
    out_rows = []
    for res in client.messages.batches.results(batch.id):
        cid = res.custom_id
        desc = descriptions.get(cid, "")
        if res.result.type != "succeeded":
            out_rows.append({"custom_id": cid, "error": res.result.type})
            continue
        text = next(b.text for b in res.result.message.content if b.type == "text")
        d = json.loads(text)
        hts = (d.get("hts10") or d.get("hts6") or (d.get("chapter") or "").zfill(2) + "00000000")
        conf = float(d.get("confidence", 0) or 0)
        pga = agencies_for(hts, desc)
        out_rows.append({
            "custom_id": cid, "description": desc, "hts10": d.get("hts10", ""),
            "hts6": d.get("hts6", ""), "chapter": d.get("chapter", ""),
            "confidence": conf, "gri_path": d.get("gri_path", ""),
            "pga_requirements": "; ".join(pga),
            "review_required": conf < args.threshold or bool(pga) or not d.get("hts10"),
            "disclaimer": DISCLAIMER,
        })

    cols = ["custom_id", "description", "hts10", "hts6", "chapter", "confidence",
            "gri_path", "pga_requirements", "review_required", "error", "disclaimer"]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()

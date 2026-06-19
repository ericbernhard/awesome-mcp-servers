#!/usr/bin/env python3
"""
HTS code + PGA requirement classifier.

Given a product description (plus optional attributes), determine the most likely
U.S. HTS code via Claude, then attach Partner Government Agency requirements
deterministically from the chapter (pga_rules). Low-confidence or high-risk results
are routed to a licensed broker for review — the service never auto-files.

Usage:
    export ANTHROPIC_API_KEY=...
    python hts_pga_classifier.py "men's knit cotton t-shirt, 100% cotton"
    python hts_pga_classifier.py --model claude-sonnet-4-6 "lithium-ion power bank"

Without an API key it runs a deterministic OFFLINE MOCK (clearly labeled) so the
pipeline and the PGA layer can be exercised with zero dependencies.

API reference: model claude-opus-4-8; structured output via output_config.format;
adaptive thinking; the static HTS reference is cached via cache_control.
"""
import argparse
import json
import os
import sys

from pga_rules import agencies_for, CHAPTER_PGA, KEYWORD_PGA
from reference import HTS_REFERENCE, OUTPUT_SCHEMA, SYSTEM_INSTRUCTIONS

DEFAULT_MODEL = "claude-opus-4-8"
DISCLAIMER = (
    "Advisory classification, not legal advice or a CBP ruling. A licensed customs "
    "broker must review before entry; for a binding determination request a CBP ruling."
)


def _user_prompt(description, attributes=None):
    lines = [f"Product description: {description}"]
    for k, v in (attributes or {}).items():
        if v:
            lines.append(f"{k}: {v}")
    lines.append("\nClassify per the GRI and return the structured object.")
    return "\n".join(lines)


def _finalize(result, description, confidence_threshold, mock):
    """Attach deterministic PGA flags, review routing, and disclaimer."""
    hts = (result.get("hts10") or result.get("hts6")
           or (result.get("chapter") or "").zfill(2) + "00000000")
    result["pga_requirements"] = agencies_for(hts, description)
    try:
        conf = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    result["confidence"] = conf
    high_risk = bool(result["pga_requirements"]) or not (result.get("hts10") or "").strip()
    result["review_required"] = conf < confidence_threshold or high_risk
    result["review_reason"] = (
        "low confidence" if conf < confidence_threshold
        else "PGA-regulated / incomplete code" if high_risk else "none"
    )
    result["mock"] = mock
    result["disclaimer"] = DISCLAIMER
    return result


def _mock_classify(description, attributes):
    """Deterministic offline stand-in: guess a chapter from keywords, low confidence."""
    blob = f"{description} {' '.join(str(v) for v in (attributes or {}).values())}".lower()
    guess_keywords = {
        "01": ["live animal"], "02": ["beef", "pork", "meat", "poultry"],
        "03": ["fish", "shrimp", "seafood", "tuna"], "22": ["wine", "beer", "spirit", "vodka"],
        "24": ["cigarette", "vape", "nicotine", "tobacco"], "30": ["drug", "tablet", "pharmaceutical"],
        "33": ["cosmetic", "lipstick", "skin cream", "lotion"], "61": ["t-shirt", "knit shirt", "sweater"],
        "62": ["woven shirt", "trousers", "dress"], "64": ["footwear", "shoe", "sneaker", "boot"],
        "85": ["power bank", "charger", "electronic", "wifi", "bluetooth", "phone"],
        "87": ["car", "vehicle", "tire", "motorcycle"], "90": ["medical device", "thermometer", "lens"],
        "95": ["toy", "doll", "game"],
    }
    chapter = "00"
    for ch, kws in guess_keywords.items():
        if any(k in blob for k in kws):
            chapter = ch
            break
    return {
        "hts10": "",
        "hts6": "",
        "chapter": chapter,
        "heading_text": "(mock — no model called)",
        "gri_path": "GRI 1 (mock)",
        "rationale": "OFFLINE MOCK result. Set ANTHROPIC_API_KEY for a real classification.",
        "confidence": 0.2,
        "missing_facts": ["full material composition", "intended use", "construction"],
        "alternates": [],
        "suggested_pga": agencies_for(chapter + "00000000", description),
    }


def classify(description, *, attributes=None, model=DEFAULT_MODEL,
             effort="medium", confidence_threshold=0.8, client=None, hts_table=None):
    """Classify one product. Returns a dict (see README for the shape).

    If `hts_table` (a set of normalized codes from hts_validator.load_hts_table) is
    given, the returned code is validated against it and `hts_valid` is set.
    """
    if not description or not description.strip():
        raise ValueError("description is required")

    def _validated(result):
        from hts_validator import validate_result
        return validate_result(result, hts_table)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if client is None and not api_key:
        return _validated(_finalize(_mock_classify(description, attributes),
                                    description, confidence_threshold, mock=True))

    try:
        import anthropic
    except ImportError:
        sys.stderr.write("anthropic SDK not installed; run `pip install anthropic`. "
                         "Falling back to offline mock.\n")
        return _finalize(_mock_classify(description, attributes),
                         description, confidence_threshold, mock=True)

    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        # effort and the output format both live inside output_config.
        output_config={"effort": effort,
                       "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        system=[
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            # Static reference last in the prefix, cached across requests.
            {"type": "text", "text": HTS_REFERENCE,
             "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": _user_prompt(description, attributes)}],
    )
    # structured outputs guarantee the first text block is schema-valid JSON.
    text = next(b.text for b in resp.content if b.type == "text")
    result = json.loads(text)
    result["model"] = resp.model
    return _validated(_finalize(result, description, confidence_threshold, mock=False))


def main():
    ap = argparse.ArgumentParser(description="Classify a product into an HTS code + PGA flags.")
    ap.add_argument("description", help="Product description")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--threshold", type=float, default=0.8,
                    help="confidence below this routes to broker review")
    ap.add_argument("--material"); ap.add_argument("--use"); ap.add_argument("--origin")
    args = ap.parse_args()

    attrs = {"material": args.material, "intended_use": args.use, "country_of_origin": args.origin}
    result = classify(args.description, attributes=attrs, model=args.model,
                      effort=args.effort, confidence_threshold=args.threshold)
    print(json.dumps(result, indent=2))
    if result["review_required"]:
        sys.stderr.write(f"\n** REVIEW REQUIRED ({result['review_reason']}) — "
                         f"route to a licensed broker before entry. **\n")


if __name__ == "__main__":
    main()

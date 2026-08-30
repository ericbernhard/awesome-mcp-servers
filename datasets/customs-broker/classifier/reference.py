"""
Static prompt assets for the HTS classifier: system instructions, the JSON output
schema, and a compact HTS/GRI reference.

In production the reference would be the full USITC Harmonized Tariff Schedule
(published as JSON/CSV) plus CBP CROSS ruling excerpts, retrieved per query and
placed behind a `cache_control` breakpoint. The excerpt below is a stand-in so the
module is self-contained. NOTE: prompt caching on Opus 4.8 needs a >=4096-token
prefix to actually cache — this short excerpt won't, but the real reference will.
"""

SYSTEM_INSTRUCTIONS = """\
You are a licensed-broker-grade U.S. import classification assistant. Your job is to
determine the most likely 10-digit Harmonized Tariff Schedule (HTSUS) code for a
product and explain the reasoning, NOT to decide admissibility.

Hard rules:
- Apply the General Rules of Interpretation (GRI) 1 through 6 in order. Classify by
  the terms of the headings and any relative section/chapter notes first (GRI 1).
- Cite the GRI path you used (e.g. "GRI 1; GRI 6") and the heading text that governs.
- Never invent a code. If you are not confident to the 10-digit statistical suffix,
  give the level you ARE confident at (chapter/heading/subheading) and lower the
  confidence score accordingly.
- Calibrate `confidence` honestly (0.0-1.0). Classification errors carry penalties
  under 19 U.S.C. 1592, so under-confidence is safer than false precision.
- When the description is ambiguous or material/use/composition is missing, say so in
  `rationale` and list what additional facts would resolve it.
- `suggested_pga` is advisory only; the system attaches the authoritative agency
  flags deterministically from the chapter.

Return ONLY the structured object defined by the response schema."""

# json_schema for output_config.format. additionalProperties:false + all required,
# per structured-outputs constraints (no min/max on numbers — validate client-side).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "hts10": {"type": "string", "description": "Best 10-digit HTSUS code, digits only or dotted; empty if not confident below subheading"},
        "hts6": {"type": "string", "description": "6-digit international subheading"},
        "chapter": {"type": "string", "description": "2-digit chapter"},
        "heading_text": {"type": "string", "description": "Text of the governing heading"},
        "gri_path": {"type": "string", "description": "GRI rules applied, e.g. 'GRI 1; GRI 6'"},
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "description": "0.0-1.0"},
        "missing_facts": {"type": "array", "items": {"type": "string"}},
        "alternates": {"type": "array", "items": {"type": "string"}},
        "suggested_pga": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "hts10", "hts6", "chapter", "heading_text", "gri_path",
        "rationale", "confidence", "missing_facts", "alternates", "suggested_pga",
    ],
    "additionalProperties": False,
}

# Compact reference excerpt (the cached prefix in production).
HTS_REFERENCE = """\
GENERAL RULES OF INTERPRETATION (summary):
GRI 1 - Classify according to the terms of the headings and any relative section or
  chapter notes; titles are for reference only.
GRI 2(a) - Incomplete/unassembled articles classified as the complete article if they
  have its essential character.
GRI 2(b) / GRI 3 - Mixtures and composite goods: (a) most specific description; (b)
  essential character; (c) last heading in numerical order.
GRI 4 - Goods not classifiable by the above go to the heading for the most akin goods.
GRI 5 - Cases/packing.
GRI 6 - Subheadings compared only with subheadings at the same level; section/chapter
  notes apply.

SELECTED CHAPTER INDEX (2-digit):
02 meat; 03 fish & seafood; 04 dairy/eggs/honey; 06 live plants; 07 vegetables;
08 fruit; 09 coffee/tea/spices; 16-21 prepared foods; 22 beverages & spirits;
24 tobacco; 28-29 chemicals; 30 pharmaceuticals; 33 cosmetics; 38 pesticides/misc
chemicals; 39 plastics; 40 rubber; 42 leather goods; 50-63 textiles & apparel;
64 footwear; 71 jewelry; 84 machinery; 85 electrical machinery & electronics;
87 vehicles; 90 optical/medical instruments; 93 arms & ammunition; 94 furniture;
95 toys; 97 works of art.
"""

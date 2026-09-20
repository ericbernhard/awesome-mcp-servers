"""
HTS code validation against the official tariff table.

Catches hallucinated or stale codes: a model-proposed `hts10` that doesn't exist in
the published USITC HTS should never be trusted. Until the real table is loaded this
returns `None` ("unknown") rather than `False`, so it never silently passes or fails.

Wiring: pass a loaded table to `classify(..., hts_table=table)` and the result gets
`hts_valid: true|false|null`. Load the table once at startup.

    from hts_validator import load_hts_table
    table = load_hts_table("hts_2026.csv")   # column 'hts10' or 'HTS Number'
"""
import csv
import re

_NORM = re.compile(r"[.\s]")


def normalize(code: str) -> str:
    """Strip dots/spaces so '6109.10.0012' and '6109100012' compare equal."""
    return _NORM.sub("", code or "")


def load_hts_table(path: str) -> set[str]:
    """Load the official HTS into a set of normalized 10-digit codes."""
    codes: set[str] = set()
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        col = next((c for c in (reader.fieldnames or [])
                    if c.lower().replace(" ", "") in ("hts10", "htsnumber", "hts", "htsus")), None)
        if not col:
            raise ValueError(f"no HTS column found in {path}; headers={reader.fieldnames}")
        for row in reader:
            n = normalize(row.get(col, ""))
            if len(n) == 10 and n.isdigit():
                codes.add(n)
    return codes


def is_valid(code: str, table: set[str] | None) -> bool | None:
    """True/False if a table is loaded; None when the table is unavailable."""
    if table is None:
        return None
    n = normalize(code)
    if len(n) != 10 or not n.isdigit():
        return False
    return n in table


def validate_result(result: dict, table: set[str] | None) -> dict:
    """Attach `hts_valid` to a classifier result and force review on an invalid code."""
    valid = is_valid(result.get("hts10", ""), table)
    result["hts_valid"] = valid
    if valid is False:
        result["review_required"] = True
        result["review_reason"] = "HTS code not found in official tariff table"
    return result

# Lead tooling

## `fda_refusal_rank.py`

Turns the public **FDA Import Refusal Report (IRR)** into a ranked customs-brokerage
lead list. A firm appearing in the IRR is free, direct evidence of a broken import
process — the "underserved" signal from [`../underserved-targeting.md`](../underserved-targeting.md).

It maps each refusal to a dataset `category`, joins the `broker_value_score`, and
ranks firms by:

```
lead_score = refusals  ×  broker_value_score  ×  charge_breadth  ×  recency
```

### Usage

```bash
python3 fda_refusal_rank.py                          # bundled sample (offline)
python3 fda_refusal_rank.py --input refusals.csv     # real FDA IRR export
python3 fda_refusal_rank.py --top 50 --out leads.csv
```

Stdlib only — no dependencies.

### Getting real data

This sandbox blocks outbound network (FDA returns 403), so download the export and
pass `--input`:

1. Go to the FDA Import Refusal Report: https://datadashboard.fda.gov/ora/cd/imprefusals.htm
2. Filter by date range / industry and export to CSV.
3. `python3 fda_refusal_rank.py --input <that file> --out leads.csv`

Headers vary across exports; the script aliases the common ones (`firm_name`,
`fda_industry`, `product_description`, `refusal_charges`, `country`, `refusal_date`).
Only `firm_name` is strictly required.

### Files

- `sample/fda_refusals_sample.csv` — synthetic input so the tool runs offline.
- `sample/ranked_leads_sample.csv` — example output.

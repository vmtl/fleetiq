# FleetIQ — Repair Cost Intelligence (initial release)

## Feature scope

The ninth Streamlit tab, **Repair costs**, provides:

- 12 public, source-linked published cost-range references (three each for Ford Transit, Ram ProMaster, Mercedes Sprinter, and Chevrolet Express).
- Explicit reference model configuration, geographic scope, source name, and review date.
- Comparison chart and downloadable reference table.
- An independently calculated, user-adjustable scenario: `parts + labor_hours × shop_rate + other_fees`.
- Selected vehicle model-year and optional mileage context.
- Topically related classified NHTSA problem reports for the selected model year, with reported mileage coverage and sample size.
- CSV download of a custom budget scenario.

The feature is read-only against source data; no user inputs are stored.

## Provenance and permitted use

Published example figures were read individually from publicly viewable RepairPal estimator pages on 2026-11-21 and credited with individual source URLs. These are **not live quotes, exact-year prices, paid invoices, price guarantees, or re-licensed bulk datasets**. Their use as a small referenced research sample should not be confused with licensed API integration. Check provider licensing before redistributing an expanded commercial corpus. Source pages can be rechecked or removed if conditions change.

RepairPal notes that estimates can vary by ZIP, year, vehicle configuration and shop; tax, diagnostic charges and disposal costs may be excluded: https://repairpal.com/faq

The dashboard makes no claim that a repair is needed because a vehicle has complaints in the corresponding system. It does **not** predict failures, remaining useful life, scheduled maintenance, exact downtime, or a repair date.

## Data schema

`data/repair_costs.csv` contains:

`vehicle, reference_configuration, repair_operation, system, low_usd, high_usd, source_url, related_reported_issue, source_name, checked_on, geographic_scope, source_scope_note`

Catalog validation enforces finite positive price ranges, supported vehicle platforms, HTTPS source references, unique repair identifiers, and review-date fields.

`repair_intelligence.py` keeps cost calculations separate from complaint records and loads `data/problem_summary.csv` only for separately labeled historical symptom evidence. The source of complaint data is NHTSA; grouped complaint mileage **is not the mileage when an actual repair was completed**.

## How to extend

1. Add only documented, individually attributable source observations to `data/repair_costs.csv`. Record exact year/trim/engine when the source makes these available. Do not substitute a general model-family figure for a configured vehicle.
2. Add more vehicle configurations and repairs using the same schema, or introduce versioned data tables for multiple source observations per repair.
3. Integrate a properly licensed labor-time / parts-cost API before claiming model-year/ZIP-specific shop pricing.
4. Incorporate OEM scheduled maintenance data only after independently verifying manuals, year-specific intervals, and usage severity.
5. Do not normalize complaint counts into failure probabilities without exposure data or verified repair outcomes.

## Validation and deployment

```bash
pip install -r requirements.txt pytest
python -m py_compile app.py repair_intelligence.py
python -m pytest -q tests/test_repair_intelligence.py
streamlit run app.py
```

`.github/workflows/validate_repairs.yml` validates the catalog, arithmetic, evidence filters and app startup. Merge only after green checks and a final diff review. Then confirm the live ninth tab renders, source links work, and selecting a repair updates the reference range and calculator.

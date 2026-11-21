# FleetIQ — Commercial Vehicle Decision Intelligence

**FleetIQ** is an interactive Streamlit portfolio project for researching commercial cargo vans and operating-cost scenarios. Its purpose is to help buyers and operators investigate reported vehicle issues and documented maintenance, official safety recalls, repair-price references, vehicle-sales context, and hypothetical ownership expenses.

**Live website:** https://fleetintel.streamlit.app/  
**Technology:** Python, Streamlit, pandas, Plotly, NHTSA public data, GitHub Actions.

## What visitors can do

1. **Failure Hotspots:** Inspect NHTSA complaint shares on an interactive generic vehicle mechanical cutaway. The heat colors are not probabilities of failure.
2. **Compare vehicles / Problem categories / Component deep dive:** Compare complaint volumes, categories, and individual source descriptions with relevant filters and evidence exports.
3. **Problem Intelligence / Reported incidents / Complaint records:** Explore keyword-derived symptoms, mileage coverage, and self-reported events.
4. **Sales data:** Review audited manufacturer sales observations and their verification statuses; incomplete-year sales are kept separate from comparable full-year data.
5. **Repair costs:** Compare a small set of published, sourced repair-price ranges and calculate custom parts-and-labor scenarios.
6. **Maintenance timing:** View manufacturer-scoped service intervals, a conditional mileage-based forecast, cost-reference summaries, and the interactive van heat map.
7. **Safety recalls:** Retrieve the latest official NHTSA make/model/year recall campaigns on demand, read remedy and safety consequence details, and follow the official VIN lookup.
8. **Ownership economics:** Compare vans with editable purchase prices, residual values, annual miles, fuel efficiency, annual operating-cost allowances, downtime, and financing *interest/fees*.

The application currently contains **12 primary tabs**. Some data series have uneven coverage. Where FleetIQ cannot verify an interval, outcome, denominator, or cost, it displays limits rather than inventing values.

## Quick start

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The NHTSA recall feature calls the public NHTSA API on request and caches successful results for up to an hour; it requires network access. Other features load version-controlled datasets in `data/` prepared by repository pipelines.

For validation, install `pytest` then run:

```bash
python -m pytest -q tests/test_release_intelligence.py tests/test_maintenance_forecast.py tests/test_maintenance_intelligence.py tests/test_repair_intelligence.py
```

GitHub Actions checks the new release features, verifies cost calculations and data contracts, and runs Streamlit's application startup test.

## Model integrity and limitations

- **NHTSA consumer complaints are not measured component-failure rates.** Counts have no matched denominator of vehicles exposed to failure, and reporting is voluntary.
- **A model-level recall campaign is not an open recall for an individual VIN.** Use the official [NHTSA VIN recall check](https://www.nhtsa.gov/recalls) to determine applicability and open status. FleetIQ does not ask for or store a VIN.
- **Reported mileage is not verified repair mileage.** A complaint can describe a concern without establishing a fault or documented repair.
- **Manufacturer maintenance service schedules depend on exact model year, engine, duty cycle and owner history.** Currently verified schedule coverage is concentrated on the 2020 model year; Sprinter data remains marketing-level advisory where engine-specific evidence is not established.
- **Maintenance and repair estimates are reference ranges, not guaranteed quotes.** Many operations have no defensible cost reference and are shown as unpriced.
- **Ownership costs are user-defined planning scenarios.** Default values are illustrative placeholders, the same for all vans. Lowest scenario cost is not a reliability or value ranking. An annual maintenance allowance and repair reserve are separate user budgets; adjust them to avoid double counting if your inputs overlap.
- **Financing field is interest and fees only** because ownership depreciation already accounts for acquisition less residual value. Do not enter loan principal again.

## Data lineage

| Domain | Inputs | Derived outputs / code |
|---|---|---|
| Safety complaints | NHTSA consumer complaints | `data/complaints.csv`, `data/summary.csv`, `analyze_complaints.py`, `van_cutaway.py` |
| Vehicle sales | Manufacturer publications and labeled provisional entries | `data/sales_clean.csv`, `data/sales_verification.csv`, `SALES_VALIDATION.md` |
| Repair cost references | Source-linked public estimator examples | `data/repair_costs.csv`, `repair_intelligence.py`, `REPAIR_COST_INTELLIGENCE.md` |
| Maintenance | Official model-year owner-manual schedule references and price observations | `data/maintenance_schedules.csv`, `data/maintenance_cost_refs.csv`, `maintenance_intelligence.py`, `maintenance_forecast.py`, `MAINTENANCE_TIMING.md` |
| Recalls | Official NHTSA API on demand | `recall_intelligence.py`, no built-in or saved VIN register |
| Ownership planning | User-supplied assumptions | `ownership_intelligence.py`, not stored between visits |

## Roadmap after the MVP

- Expand manufacturer-verified maintenance intervals and price coverage across additional model years and engine configurations.
- Add more licensed parts-price and labor-time references, with local estimates where permitted.
- Add authorized VIN decoding and history-specific recall matching if official provider terms support it.
- Derive failure-time distributions only from suitable verified repair outcomes and exposure denominators, never from consumer complaints alone.
- Improve mobile navigation and add monitored end-to-end live-site tests.

The site is a portfolio research project, **not a professional inspection, safety certification, repair quote, recall completion confirmation or financial recommendation**.

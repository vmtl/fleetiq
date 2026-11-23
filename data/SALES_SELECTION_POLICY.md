# FleetIQ annual sales selection policy

Effective: 2026-11-23

## Purpose
Choose a single working U.S. calendar-year sales observation per vehicle nameplate, while preserving the original data and source provenance. This policy does not establish mechanical failure rates or model-year vehicles in operation.

## Deterministic source priority
1. Prefer a published manufacturer U.S. full-calendar-year figure for the same vehicle nameplate and scope.
2. Otherwise use the existing GoodCarBadCar series as the secondary source.
3. Preserve the current value when no stronger same-scope evidence has been established; record a conflict separately rather than silently replacing it.
4. Exclude missing values, explicit zeros without verified discontinued-model context, incomplete reporting years, and years still in progress from comparative denominators.
5. Do not combine sales of a vehicle's distinct nameplates or body styles unless source and complaint classification definitions align.

## Selected conflict decisions
- Chevrolet Express 2018: retain 81,239 (GM-sourced observation).
- Chevrolet Express 2020: retain 55,131 (GM-sourced observation).
- Ram ProMaster 2016: retain 40,440 (FCA-sourced observation).
- Ram ProMaster 2022: retain 60,936 (FCA-sourced observation).
- Mercedes Sprinter 2024: exclude 43,425 from comparative use; source notes missing November reporting.

## Files and interpretation
- `data/sales.csv` is the unchanged source dataset.
- `data/sales_selection.csv` is a row-for-row decision ledger for the 624 existing sales records. `selected` means chosen under the policy, **not independently manufacturer-verified**.
- `annual_sales_only` means the value may be used for calendar-year sales reporting, **not as a model-year vehicle-exposure denominator**.
- 2026 is an incomplete calendar year as of this policy date and is not eligible for full-year comparison.
- A missing observation is not zero sales.
- The live Streamlit dashboard has not been changed to consume the selection ledger.

## Reliability metric limitation
NHTSA complaint counts are self-reported events; calendar-year model-family sales are not the number of operating vehicles of a given model year. Do not label complaints divided by annual sales as a mechanical failure rate or true reliability rate. A future complaint-to-sales index requires a separately documented and defensible temporal matching rule.

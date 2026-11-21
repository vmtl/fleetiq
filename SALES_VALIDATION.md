# FleetIQ Historical Sales Validation — 2026-11-21

## Scope

Reviewed 52 populated, previously flagged U.S. calendar-year vehicle-nameplate sales records for Ford Transit, Ram ProMaster, Mercedes Sprinter, and Chevrolet Express, 2014–2026.

Evidence ledger: `data/sales_verification.csv`.

The repository source file `data/sales.csv` has eleven corrected values. Original values, reference URLs, and verification classification remain recorded in the ledger and Git history. Do not use these sales totals as model-year populations, vehicle exposure, or failure-rate denominators.

## Findings

- Six Ram ProMaster values corrected using FCA/Stellantis year-end manufacturer reporting: 2016 39,691 → 40,440; 2019 56,410 → 56,409; 2020 50,553 → 50,556; 2021 63,362 → 63,361; 2022 60,937 → 60,936; 2024 65,868 → 65,869.
- Five Chevrolet Express values corrected using original GM annual U.S. deliveries documents: 2018 66,963 → 81,239; 2020 55,040 → 55,131; 2021 44,357 → 44,355; 2022 52,796 → 52,888; and 2023 40,659 → 40,660. Every Chevrolet Express 2014–2025 value was reconciled against original GM deliveries tables.
- FCA/Stellantis year-end releases support ProMaster 2014–2025; Ford's year-end releases confirm Transit 2022–2025; 2019 and 2020 differ by one unit from other independent compiled references and remain open for official reconciliation.
- Mercedes-Benz's own 2024 U.S. reporting uses a broader vans group total and introduced a reporting-methodology change. GoodCarBadCar identifies incomplete November 2024 data. The Sprinter-only 2024 value must remain unresolved and should not be replaced by the broader Mercedes Vans number.
- A historical Sprinter source notes that Metris figures were included in the Sprinter series during parts of 2015–2016; these rows have a nameplate-scope warning.
- 2026 totals are **year-to-date only**, not full calendar-year deliveries: Transit Jan–Oct; ProMaster Jan–Sep; Sprinter Jan–Sep; Express Jan–Sep (as described in the original cited secondary tables).

## Audit outcome

- 52 previously flagged vehicle-year records reviewed.
- 28 records supported by original manufacturer reporting (17 unchanged verified and 11 corrected and verified).
- 14 secondary-only records, three unresolved published conflicts, two mixed-scope Sprinter records, one independently corroborated trade figure, and four partial-year 2026 records.
- The remaining 24 must not be described as manufacturer-verified.
- All 624 source platform-year records are retained; the cleaned dataset and quality report include separate manufacturer-verification indicators.

## Status definitions

- `verified_manufacturer`: original number exactly matches year-end manufacturer evidence.
- `corrected_manufacturer`: corrected number exactly matches year-end manufacturer evidence.
- `secondary_only`: original data and secondary reporting inspected, but insufficient manufacturer-level confirmation.
- `corroborated_independent`: matches trade reporting, without exact original manufacturer nameplate evidence.
- `conflict_unresolved`: conflicting published values; retain disputed value until source and scope adjudicated.
- `scope_mismatch`: historical series includes a different nameplate or mixed vehicle definition.
- `partial_year`: only year-to-date data, cannot be used as a completed-year figure.

Only `verified_manufacturer` and `corrected_manufacturer` qualify as independently verified under the current conservative policy. Legacy `source_status` labels are not verification evidence.

## ETL behavior

Run from repository root:

```bash
python clean_sales.py --as-of 2026-11-21
python -m pytest -q tests/test_sales_validation.py
```

`clean_sales.py` loads the ledger, rejects duplicate vehicle-year entries and mismatched sales values, and adds `source_verification_status`, `source_verified`, and `verified_for_comparison`. The older `ready_for_full_year_comparison` remains a *structural* eligibility flag; it must not be interpreted as source verification.

The new GitHub Actions workflow `.github/workflows/validate_sales.yml` runs regression tests and regenerates output in a temporary directory to validate counts and corrected values without overwriting production datasets.

## Known remaining issues

- Obtain original year-end manufacturer evidence for provisional Ford, Chevrolet, and Sprinter records.
- Adjudicate the one-unit Ford Transit 2019/2020 differences.
- Reconcile 2024 Sprinter definitions and reporting periods with Mercedes-Benz.
- Audit other sales platforms currently outside this 52-record scope.
- The branch contains regenerated `data/sales_clean.csv` and `data/sales_quality_report.json`, and updates the Streamlit Sales Data UI to display source-verification status separately from structural eligibility. Run CI and inspect the branch before merging into production.

**Do not describe all 52 rows as verified.** A completed audit can legitimately result in verified, corrected, and unresolved outcomes.

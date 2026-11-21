# FleetIQ — Portfolio Case Study Evidence Log

**Status:** Engineering evidence log and case-study outline; not a published case study.  
**Project:** FleetIQ commercial van research and fleet operations pilot  
**Repository:** https://github.com/vmtl/fleetiq  
**Public app:** https://fleetintel.streamlit.app/ (external UI and production behavior must be independently reviewed)

## 1. Problem statement

Independent delivery operators and small fleet managers face fragmented information about vehicle defects, maintenance schedules, recall campaigns, purchase economics and documented service history. Existing public NHTSA consumer complaints describe self-reported events, not verified failure probabilities. Different data sources have inconsistent year and configuration coverage.

FleetIQ explores a transparent decision-support approach that distinguishes manufacturer instructions, reported incidents, sourced prices, user assumptions, and eventually verified service outcomes.

## 2. Engineering architecture and data lineage

| Layer | Modules and data | Evidence |
| --- | --- | --- |
| Ingestion / normalizing | `refresh_data.py`, versioned `data/complaints.csv`, `data/summary.csv` | NHTSA public consumer complaints, validated columns, ODI-level distinct counts |
| Source evidence | `data/maintenance_schedules.csv`, `maintenance_coverage.py`, `catalog_quality.py` | Manufacturer URL and section, vehicle-year applicability, conditional duty scopes and explicit missing coverage |
| Analysis | `maintenance_forecast.py`, `repair_intelligence.py`, `business_economics.py`, `ownership_intelligence.py` | Interval and hypothetical financial calculations separated from observed failures |
| Data exploration | `app.py`, `van_cutaway.py`, `vehicle_report.py` | 14-tab Streamlit research application, interactive van schematic, exportable research report |
| Business workspace pilot | `fleet_workspace.py`, `service_alerts.py` | Session-only vehicle/service entry, odometer updates, validated ZIP export/import, OEM mileage reminders when service history exists |
| Durable SaaS design | `database/001_multi_tenant_schema.sql` | PostgreSQL table definitions, foreign keys, row-level security scoped to trusted server org context; NOT deployed |
| Quality gates | `tests/`, `.github/workflows/` | pytest regression checks, Python compile and Streamlit AppTest startup |

## 3. Significant engineering decisions

1. **Don't convert complaint counts to failure probabilities.** NHTSA incident reports have no matched population of in-service vehicles or validated nonfailure outcomes; source-data limitations must remain visible.
2. **Preserve OEM service semantics.** An oil-life monitor's maximum ceiling is not a universal change interval; severe-duty schedules only apply where appropriate. A service alert requires a recorded completed service.
3. **Treat catalog coverage honestly.** The target has 51 applicable US van-year cells and one not-applicable 2014 Ford Transit cell; a partly sourced cell is not a fully reviewed model-year/engine/duty combination.
4. **Prevent ownership-cost double counting.** Depreciation includes purchase minus resale, while financing inputs represent interest and fees only. Cash-flow scenarios are modeled separately.
5. **Isolate the pilot from commercial customer data.** The current Streamlit workspace uses session state with local ZIP export, no durable server storage. The PostgreSQL schema is design work, not a deployment claim.
6. **Require verified outcome cohorts for predictive modeling.** No unscheduled failure forecasts are offered without actual repair outcomes, exposure and held-out validation.

## 4. Implementation chronology — cite real pull requests

- [PR #1](https://github.com/vmtl/fleetiq/pulls?q=is%3Apr+is%3Amerged) — Vehicle sales quality and provenance work.
- [PR #2](https://github.com/vmtl/fleetiq/pull/2) — Repair-cost reference intelligence.
- [PR #3](https://github.com/vmtl/fleetiq/pull/3) — Maintenance timing with manufacturer documentation.
- [PR #4](https://github.com/vmtl/fleetiq/pull/4) — Maintenance forecast and issue charts.
- [PR #5](https://github.com/vmtl/fleetiq/pull/5) — Original interactive vehicle hotspot diagram restored to maintenance timing.
- [PR #6](https://github.com/vmtl/fleetiq/pull/6) — Recall intelligence and ownership economics.
- [PR #7](https://github.com/vmtl/fleetiq/pull/7) — Fleet pilot, report generation, route economics and 2014–2026 source-coverage matrix.
- [PR #12](https://github.com/vmtl/fleetiq/pull/12) — Source-checked 2018–2019 Ram schedules, catalog quality audit, operational service reminders, SQL tenancy schema, offline verified-outcome survival research and case-study evidence (merge status must be verified before publication).

## 5. Metrics and what they actually mean

**Repository-verifiable functionality measures:** count of supported UI tabs (14), number of manufacturer schedule entries, number of applicable year-platform cells, percentage with any sourced interval, tests passed and CI workflow status.

**NOT measured or validated:** actual vehicle reliability improvement, reduction in fleet downtime, customer acquisition, forecast calibration, prediction accuracy, revenue produced, number of active users or time saved for customers. Do not fabricate these in interviews or the final case study.

Once a pilot exists, measure service-record completion, time needed to compare vehicle candidates, average time to identify next service, errors prevented, and whether expense forecasts match reconciled operational invoices.

## 6. Portfolio storytelling framework

- **Situation:** Commercial van buyers and owners must correlate complaints, maintenance manuals, recalls and cost references from fragmented public information.
- **Task:** Design an evidence-transparent data application that helps investigate van platforms and build toward usable fleet operations.
- **Action:** Explain ingestion/data contracts, validation, deduplication, the interactive mechanical heat map, interval-based forecasts, recall API, route cost model, GitHub CI, SQL schema and privacy decisions.
- **Result:** Present demonstrated software capabilities, tested scenarios, data coverage and known limitations, not speculative business impact.
- **What I'd improve:** Real repair-outcome data and censoring, full OEM catalog, production auth + durable data, mobile usability and controlled customer pilots.

## 7. Before publishing the case study

- Capture screenshots from the actual live UI at desktop and mobile widths, without exposing customer data.
- Record final merged PR SHA and CI run URLs.
- Produce a reproducible `pytest` test count, dataset-row count and coverage export.
- Verify a real NHTSA API response for a known make/model/year and compare source campaign details.
- Use only screenshots, UI recordings, and metrics observed from the deployed app.
- Clearly separate implemented features from future production-roadmap items.

**No formal, independently reviewed customer production deployment is claimed.**

## 8. Experimental survival methodology (not customer predictions)

`survival_research.py` implements a research-only Kaplan–Meier estimator using delayed-entry odometer observations and right-censored verified outcomes. It validates one platform/system cohort, positive odometer exposure and minimum outcome counts before calculating risk sets. Its numerical outputs are **not** displayed as production reliability scores. Selection bias, competing risks, cohort representativeness, service record data rights, held-out calibration and confidence interval validation still need real-world evidence.

The example unit tests use synthetic events solely to verify calculation correctness; they are not empirical evidence of vehicle reliability.

# FleetIQ Business Roadmap — Implementation and Blockers

Status date: 2026-11-21

| Roadmap workstream | Current deliverable | Commercial release status |
|---|---|---|
| 2014–2026 maintenance coverage | Full 52-cell year inventory, 51 potentially applicable US van-years; expanded sourced partial task rows | **Incomplete**. No full powertrain/year has comprehensive certification; see DATA_CATALOG_AUDIT.md |
| Consolidated vehicle research | Downloadable HTML vehicle intelligence report: complaints, scoped maintenance, cost reference and official VIN recall guidance | **Pilot feature built**. Need user testing, accessible PDF, cleaner cross-tab navigation |
| Fleet accounts and service histories | Streamlit session-only pilot: add vehicles, record completed maintenance, import/export ZIP | **Not production-ready**. No auth, tenant isolation, server persistence, backups or user policies. Do not upload sensitive business information |
| Business economics | Route revenue, driver pay, insurance, financing cash, mileage/fuel, repair reserve, downtime scenario | **Pilot feature built**. Needs real invoices/contracts and reconciliation with ownership economic assumptions |
| Predictive reliability | Data contract and strict cohort readiness check. No trained model or numerical failure probabilities | **Blocked on verified repair outcomes, censoring/exposure, permissions and independent validation** |
| Commercial launch | This governance checklist, test suite and roadmap | **Not launched**. Requires customer pilot, legal/licensing, security and operations review |

## Release requirements for commercial customer data

- Identity provider + MFA, business-scoped authorization, row-level/tenant isolation, role review and signed-out public pages.
- PostgreSQL or another transactional, durable server-side database with migration scripts, tested backups and restoration, change logs and retention controls.
- Secret management, least-privilege access, encrypted data in transit and at rest, deletion/export processes and a documented incident response.
- Source licensing evaluation for OEM repair/manual content, repair-cost references, VIN decoding, NHTSA API terms and any third-party vehicle datasets. Retain attribution and date/version.
- Production integration tests for account separation, schema validation, large inputs, permission failures, downtime and restore.
- Operator onboarding, accessibility and responsive mobile tests on actual devices, including end-to-end live-site checks.
- Pilot agreements and explicit permission to ingest repair invoices / identifiable fleet or driver data.
- Genuine operating-cost reconciliation: financing loan principal for cash-flow planning is different from depreciation plus financing interest for long-horizon ownership economics.
- Safety/legal/financial disclaimers verified by professionals before relying on results for procurement or maintenance decisions.

## Predictive analytics gating

The `assess_prediction_readiness` routine evaluates the structure and rough sufficiency of a supplied *anonymized* repair-outcome cohort, never creates a risk forecast. Even passing a rough sample size cannot establish readiness: it requires independent cohort design, leakage prevention, fairness/shift tests, held-out calibration, interval confidence, repair-label QA, exposure denominators and model monitoring. No claims about unscheduled failures may be made solely from complaint counts.

## Next implementation milestones (not completed)

1. Finish source-audited intervals across all applicable model-year/powertrain combinations and update gap audit until zero unverified applicable configurations remain.
2. Expand local service and repair estimates by model configuration, using licensed/sourced public data.
3. Build authenticated, durable, tenant-isolated fleet service with audited CRUD endpoints and repeatable backups.
4. Pilot with actual commercial van owners and verify expense-calculator assumptions against completed routes.
5. Obtain a permitted cohort of completed repairs AND comparable vehicles without the target repair.
6. Validate predictive models and assess safety, data rights and legal compliance before charging customers.

The Streamlit fleet workspace is for demonstrations only; user-provided session content is not a commercial hosted fleet database.

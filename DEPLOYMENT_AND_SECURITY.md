# FleetIQ — Deployment and Security Design (Not Deployed)

## Current state

FleetIQ runs as a public Streamlit research app, using version-controlled datasets. The fleet workspace in `fleet_workspace.py` holds data in Streamlit session state only. **There is no live authentication service, production PostgreSQL database, customer account isolation, real scheduled email/SMS delivery, or commercial user-data retention.** Do not input actual VINs, driver names, customer contacts, insurance IDs or private commercial records.

## Proposed production architecture

```text
Browser / mobile web
      |
Identity provider (MFA, session management, signed tokens)
      |
Trusted API service (org-role checks, request limits, validation, audit logging)
      |                         |
      |                         +-- scheduler / notification queue (opt-in only)
      |
PostgreSQL (RLS, encrypted backups, migrations, audited service events)
      |
Read-only research datasets and NHTSA recall integration
```

### Database scaffold

`database/001_multi_tenant_schema.sql` defines six tables for organizations, memberships, fleet vehicles, service events, odometer observations and audit events. Composite foreign keys prevent service records referring across organizations. PostgreSQL row-level security restricts CRUD by a transaction-local organization context.

**Security critical:** The session setting `fleetiq.org_id` is **not** an authentication mechanism. A production service must independently validate token authenticity, the requesting user's membership, role and target organization, then set `fleetiq.org_id` exclusively on a trusted database connection inside a transaction using `SET LOCAL`. Untrusted clients must never connect to PostgreSQL or set organization contexts. Table owners/superusers and BYPASSRLS roles must not serve application traffic. Database grants, migration role separation, hardening and recovery drills are mandatory before use.

### Reliable reminders

The pilot `service_alerts.py` generates only **in-session mileage reminder tables** from an exact-match completed operation and a sourced manufacturer interval. It does not schedule emails or texts and does not verify engine applicability automatically. Production delivery would require:

1. Authenticated, opt-in per-organization notification preferences with revocation.
2. Fresh or confirmed odometer readings and last service records for each task.
3. Time-zone aware job scheduling, deduplication, retry limits and delivery receipts.
4. Manufacturer service monitor signals and date-based intervals where applicable.
5. Auditable unsubscribe and repair-history correction procedures.

### Observability and operations checklist

- CI compile and regression suite for the 14-tab public app.
- Structured logs with secrets and personal identifiers redacted.
- Health checks, synthetic NHTSA recall API availability tests, alerting and tracing.
- Automated PostgreSQL backups and separately tested recovery, migration rollback and retention policies.
- SAST/dependency checks, TLS/HSTS, dependency pinning, secret scanning, rate-limiting and audit log review.
- Privacy impact assessment, deletion/export request process, legal terms and source licensing.
- Mobile responsive and accessibility review on real devices.
- Staging environments before production migrations.

## No unaudited claims

The prototype database SQL has **not** been executed against a managed production PostgreSQL service. Schema-presence unit checks are not real tenant-isolation penetration tests. Streamlit startup checks don't prove public availability or a fully functional real-browser journey.

## Potential future acceptance tests

- Provision two tenant organizations with owner, manager and viewer accounts.
- Verify an authenticated owner of org A cannot query, update or delete org B assets by any endpoint or crafted request.
- Verify session expiration, MFA challenges and role changes on all endpoints.
- Restore a backup and reconcile all vehicle, odometer and service rows with audit entries.
- Validate time-based and mileage-based reminders in a staging queue with opt-in enforcement.
- Run load testing, mobile workflows and accessibility audit before onboarding commercial pilots.

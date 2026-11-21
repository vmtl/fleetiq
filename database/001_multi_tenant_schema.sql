-- FleetIQ multi-tenant PostgreSQL schema — deployment scaffold, NOT a live service.
-- Apply only on a provisioned private PostgreSQL instance after identity-provider
-- integration, threat modeling, migration review, encrypted backups and legal review.
BEGIN;

CREATE TABLE IF NOT EXISTS organizations (
  org_id uuid PRIMARY KEY,
  org_name text NOT NULL CHECK (length(trim(org_name)) BETWEEN 1 AND 160),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS members (
  org_id uuid NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('owner','manager','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, user_id)
);
CREATE TABLE IF NOT EXISTS vehicles (
  org_id uuid NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
  asset_id text NOT NULL CHECK (length(trim(asset_id)) BETWEEN 1 AND 64),
  platform text NOT NULL,
  model_year integer NOT NULL CHECK (model_year BETWEEN 1980 AND 2100),
  odometer_miles integer NOT NULL CHECK (odometer_miles >= 0),
  operating_status text NOT NULL DEFAULT 'Active',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, asset_id)
);
CREATE TABLE IF NOT EXISTS service_events (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id text NOT NULL,
  service_date date NOT NULL,
  service_miles integer NOT NULL CHECK (service_miles >= 0),
  operation text NOT NULL CHECK (length(trim(operation)) BETWEEN 1 AND 160),
  cost_usd numeric(13,2) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
  downtime_days numeric(7,2) NOT NULL DEFAULT 0 CHECK (downtime_days >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (org_id, asset_id) REFERENCES vehicles(org_id, asset_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS odometer_observations (
  observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id text NOT NULL,
  reading_miles integer NOT NULL CHECK (reading_miles >= 0),
  observed_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (org_id, asset_id) REFERENCES vehicles(org_id, asset_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS audit_events (
  audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  action text NOT NULL CHECK (length(action) BETWEEN 1 AND 120),
  entity_type text NOT NULL,
  entity_key text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_service_org_asset_date
  ON service_events(org_id, asset_id, service_date DESC);
CREATE INDEX IF NOT EXISTS ix_odometer_org_asset_date
  ON odometer_observations(org_id, asset_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_org_time
  ON audit_events(org_id, recorded_at DESC);

-- Fail-closed row isolation via app context set with SET LOCAL in the transaction.
-- These policies are not a substitute for authenticating the actor and enforcing
-- member roles in a trusted server. Application connections MUST NOT be superusers,
-- table owners, or BYPASSRLS roles.
CREATE OR REPLACE FUNCTION fleetiq_can_access(target_org uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
  SELECT EXISTS (
    SELECT 1 FROM members m
    WHERE m.org_id = target_org
      AND m.user_id = NULLIF(current_setting('fleetiq.user_id', true), '')::uuid
  )
$$;
CREATE OR REPLACE FUNCTION fleetiq_can_write(target_org uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER AS $$
  SELECT EXISTS (
    SELECT 1 FROM members m
    WHERE m.org_id = target_org
      AND m.user_id = NULLIF(current_setting('fleetiq.user_id', true), '')::uuid
      AND m.role IN ('owner','manager')
  )
$$;

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE members ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE odometer_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- FORCE prevents accidental bypass by a table-owner session.
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE members FORCE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;
ALTER TABLE service_events FORCE ROW LEVEL SECURITY;
ALTER TABLE odometer_observations FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

-- Bootstrap organizations and first owner through a separately audited privileged
-- administrative process, never via an untrusted user connection.
CREATE POLICY org_read ON organizations FOR SELECT
  USING (fleetiq_can_access(org_id));
CREATE POLICY members_read ON members FOR SELECT
  USING (fleetiq_can_access(org_id));
CREATE POLICY vehicle_read ON vehicles FOR SELECT
  USING (fleetiq_can_access(org_id));
CREATE POLICY vehicle_write ON vehicles FOR ALL
  USING (fleetiq_can_write(org_id)) WITH CHECK (fleetiq_can_write(org_id));
CREATE POLICY service_read ON service_events FOR SELECT
  USING (fleetiq_can_access(org_id));
CREATE POLICY service_write ON service_events FOR ALL
  USING (fleetiq_can_write(org_id)) WITH CHECK (fleetiq_can_write(org_id));
CREATE POLICY observation_read ON odometer_observations FOR SELECT
  USING (fleetiq_can_access(org_id));
CREATE POLICY observation_write ON odometer_observations FOR ALL
  USING (fleetiq_can_write(org_id)) WITH CHECK (fleetiq_can_write(org_id));
CREATE POLICY audit_read ON audit_events FOR SELECT
  USING (fleetiq_can_access(org_id));

COMMIT;

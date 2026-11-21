"""Commercial-readiness source audit, service alerts and schema tests."""
from pathlib import Path
import pandas as pd
import pytest

from fleet_workspace import update_odometer
from service_alerts import mileage_alerts
from catalog_quality import audit_maintenance_catalog, year_counts

ROOT = Path(__file__).resolve().parents[1]


def assets(miles=125000):
    return pd.DataFrame([{
        "asset_id":"Unit-01", "vehicle":"Ford Transit",
        "model_year":2020, "odometer":miles, "status":"Active",
    }])


def services(task="Cabin air filter", miles=100000):
    return pd.DataFrame([{
        "asset_id":"Unit-01", "operation":task, "service_miles":miles,
        "service_date":"2026-01-01", "cost_usd":100.0,
        "downtime_days":0,
    }])


def catalog():
    return pd.read_csv(ROOT / "data" / "maintenance_schedules.csv")


def test_source_quality_audit_retains_full_context():
    checked, violations = audit_maintenance_catalog(catalog())
    assert len(checked) >= 40
    assert not checked.independently_certified.any()
    assert checked.source_link_present.all()
    assert set(violations.columns) == {
        "row_number", "vehicle", "model_year", "task", "issue_code", "detail"
    }
    years = year_counts(checked)
    assert (years.vehicle.eq("Ford Transit") & years.year.eq(2021)).any()


def test_audit_detects_missing_source_and_duplicates():
    source = catalog().iloc[[0]].copy()
    source.loc[source.index[0], "source_url"] = "not-an-oem-link"
    sample = pd.concat([source, source], ignore_index=True)
    _, warnings = audit_maintenance_catalog(sample)
    assert {"missing_source", "duplicate_scope"} <= set(warnings.issue_code)


def test_service_alert_uses_recorded_last_service():
    rows = mileage_alerts(assets(119100), services(), catalog(), threshold=2000)
    relevant = rows.loc[rows.task.eq("Cabin air filter")]
    assert len(relevant) == 1
    assert int(relevant.iloc[0].OEM_mileage_limit) == 120000
    assert int(relevant.iloc[0].miles_remaining) == 900
    assert relevant.iloc[0].status == "Within reminder window"


def test_service_alert_does_not_assume_unknown_history():
    assert mileage_alerts(assets(), services(task="Something else"), catalog()).empty


def test_service_alert_reports_overdue_limit_not_actual_failure():
    rows = mileage_alerts(assets(125000), services(), catalog())
    row = rows.loc[rows.task.eq("Cabin air filter")].iloc[0]
    assert row.miles_remaining == -5000
    assert row.status == "At/past OEM mileage limit"


def test_odometer_can_increase_but_cannot_rollback():
    latest = update_odometer(assets(), "Unit-01", 126000)
    assert latest.odometer.iloc[0] == 126000
    with pytest.raises(ValueError, match="rollback"):
        update_odometer(latest, "Unit-01", 125000)
    with pytest.raises(ValueError, match="Unknown"):
        update_odometer(latest, "Unit-02", 127000)


def test_database_schema_has_tenant_isolation_and_foreign_keys():
    schema = (ROOT / "database" / "001_multi_tenant_schema.sql").read_text()
    assert "ROW LEVEL SECURITY" in schema
    assert "FORCE ROW LEVEL SECURITY" in schema
    assert "FOREIGN KEY (org_id, asset_id)" in schema
    assert "fleetiq_current_org" in schema
    assert "ALTER TABLE service_events" in schema

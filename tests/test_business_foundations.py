"""Business-workspace, audited coverage and economics regression tests."""
import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from maintenance_coverage import build_coverage_matrix, coverage_stats
from fleet_workspace import (
    clean_assets, clean_services, empty_assets, empty_services,
    export_workspace, import_workspace, safe_csv, fleet_metrics,
)
from vehicle_report import vehicle_report, report_html
from business_economics import delivery_profit_scenario, assess_prediction_readiness

ROOT = Path(__file__).resolve().parents[1]


def schedules():
    return pd.read_csv(ROOT / "data" / "maintenance_schedules.csv")


def test_complete_model_year_coverage_inventory_is_honest():
    matrix = build_coverage_matrix(schedules())
    stats = coverage_stats(matrix)
    assert len(matrix) == 52
    assert stats["target_combinations"] == 51
    assert stats["fully_certified"] == 0
    assert stats["unverified"] > 0
    assert matrix.loc[
        matrix.vehicle.eq("Ford Transit") & matrix.model_year.eq(2014),
        "coverage_status",
    ].iloc[0] == "Not applicable (US)"
    assert matrix.loc[
        matrix.vehicle.eq("Ford Transit") & matrix.model_year.eq(2022),
        "verified_operations",
    ].iloc[0] >= 3
    assert matrix.loc[
        matrix.vehicle.eq("Mercedes Sprinter") & matrix.model_year.eq(2020),
        "coverage_status",
    ].iloc[0] == "Advisory only"


def sample_assets():
    return pd.DataFrame([{
        "asset_id": "Transit-01", "vehicle": "Ford Transit",
        "model_year": 2021, "odometer": 125000, "status": "Active",
    }])


def sample_services():
    return pd.DataFrame([{
        "asset_id": "Transit-01", "service_date": "2026-10-10",
        "service_miles": 120000, "operation": "Oil and filter",
        "cost_usd": 189.0, "downtime_days": 0.5,
    }])


def test_workspace_round_trip_retains_records():
    assets = clean_assets(sample_assets())
    services = clean_services(sample_services(), assets)
    data = export_workspace(assets, services)
    a, s = import_workspace(data)
    assert a.asset_id.tolist() == ["Transit-01"]
    assert float(s.cost_usd.iloc[0]) == 189
    assert fleet_metrics(a, s)["recorded_downtime_days"] == 0.5


def test_bad_vehicle_and_service_records_rejected():
    a = sample_assets()
    with pytest.raises(ValueError, match="unique"):
        clean_assets(pd.concat([a, a]))
    b = sample_services()
    b.loc[0, "service_miles"] = 300000
    with pytest.raises(ValueError, match="exceeds"):
        clean_services(b, clean_assets(a))
    with pytest.raises(ValueError, match="unknown"):
        clean_services(sample_services().assign(asset_id="Unknown"), clean_assets(a))


def test_formula_like_csv_text_escaped():
    a = sample_assets()
    a.loc[0, "asset_id"] = "=1+1"
    assert '"\'=1+1"' in safe_csv(a).decode()


def test_report_refuses_wrong_year_manufacturer_schedules():
    complaints = pd.DataFrame([
        {"vehicle":"Ford Transit","model_year":2021,"odi_number":"ABC",
         "mileage":125000},
        {"vehicle":"Ford Transit","model_year":2021,"odi_number":"ABC",
         "mileage":125000},
    ])
    repairs = pd.read_csv(ROOT / "data" / "repair_costs.csv")
    result = vehicle_report(
        complaints, schedules(), repairs, "Ford Transit", 2024, 125000
    )
    assert result["unique_complaints"] == 0
    assert result["maintenance"].empty
    assert "not a" in report_html(result).lower()


def test_delivery_route_profit_calculations():
    result = delivery_profit_scenario(
        routes_per_week=5, revenue_per_route=400,
        driver_cost_per_route=160, weekly_miles=500, mpg=10,
        fuel_price=4, insurance_weekly=150, vehicle_fixed_weekly=100,
        maintenance_per_mile=.1, other_weekly=0,
        downtime_routes_per_week=1,
    )
    assert result["weekly_revenue"] == 1600
    assert result["weekly_cost"] == 1140
    assert result["weekly_contribution"] == 460


def test_prediction_gate_rejects_missing_outcomes():
    result = assess_prediction_readiness(pd.DataFrame([
        {"vehicle":"Ford Transit", "model_year":2021, "asset_id":"x"}
    ]))
    assert result["ready"] is False
    assert "Missing outcome" in result["reason"]


def test_prediction_gate_rejects_only_failure_samples():
    result = assess_prediction_readiness(pd.DataFrame([
        {"vehicle":"Ford Transit", "model_year":2020, "asset_id":"unit1",
         "event_observed":1, "last_observed_miles":100000,
         "event_miles":90000, "system":"Transmission"},
    ]))
    assert not result["ready"]
    assert "Illustrative minimum" in result["reason"]

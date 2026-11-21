"""Safety and regression checks for the maintenance and timing evidence feature."""
from pathlib import Path

import pandas as pd
import pytest

from maintenance_intelligence import (
    VEHICLES, assess_service, complaint_timing_evidence, validate_schedule,
)


def seed():
    return pd.read_csv(
        Path(__file__).resolve().parents[1] / "data" / "maintenance_schedules.csv"
    )


def test_catalog_is_sourced_and_scoped_to_all_four_vans():
    data = validate_schedule(seed())
    assert set(data.vehicle) == set(VEHICLES)
    assert (data.model_year_start == 2020).all()
    assert (data.model_year_end == 2020).all()
    assert len(data) >= 12
    assert data.source_url.str.startswith("https://").all()


def test_no_unverified_universal_intervals():
    data = validate_schedule(seed())
    mb = data[data.vehicle == "Mercedes Sprinter"]
    assert (mb.schedule_mode == "advisory").all()
    ram = data[data.vehicle == "Ram ProMaster"]
    assert (ram[ram.task.str.contains("maximum limit")].schedule_mode == "monitor_cap").all()


def test_no_due_claim_without_service_history():
    task = {"interval_miles": 20000, "interval_months": 0, "schedule_mode": "recurring"}
    result = assess_service(task, 145000)
    assert result["status"] == "Service history needed"
    assert result["miles_to_limit"] is None


def test_mileage_status_depends_on_actual_service_history():
    task = {"interval_miles": 20000, "interval_months": 0, "schedule_mode": "recurring"}
    near = assess_service(task, 119100, 100000)
    assert near["status"] == "Approaching documented limit"
    assert near["miles_to_limit"] == 900
    past = assess_service(task, 122000, 100000)
    assert past["status"] == "At or past documented limit"
    assert past["limit_mileage"] == 120000


def test_time_limit_and_conditional_advisory():
    task = {"interval_miles": 10000, "interval_months": 12, "schedule_mode": "monitor_cap"}
    assert assess_service(task, 8000, months_since_service=13)["status"] == "At or past documented limit"
    advisory = dict(task, schedule_mode="advisory")
    assert assess_service(advisory, 300000, 0, 240)["status"] == "Reference only"


def test_bad_inputs_and_duplicate_catalog_rejected():
    data = seed()
    data.loc[0, "interval_miles"] = -5
    with pytest.raises(ValueError, match="negative"):
        validate_schedule(data)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_schedule(pd.concat([seed(), seed()], ignore_index=True))
    with pytest.raises(ValueError, match="Last service mileage"):
        assess_service({"interval_miles": 5000, "interval_months": 0, "schedule_mode": "recurring"}, 1000, 1500)


def test_timing_evidence_is_mileage_sample_based_not_failure_prediction():
    data = pd.DataFrame([
        {"vehicle": "Ford Transit", "model_year": 2020,
         "issue": "Engine stalls / loses power",
         "unique_complaints": 10, "mileage_samples": 2, "median_reported_miles": 73000},
        {"vehicle": "Ford Transit", "model_year": 2021,
         "issue": "Engine stalls / loses power",
         "unique_complaints": 5, "mileage_samples": 0, "median_reported_miles": 99999},
        {"vehicle": "Ram ProMaster", "model_year": 2020,
         "issue": "Engine stalls / loses power",
         "unique_complaints": 99, "mileage_samples": 99, "median_reported_miles": 80000},
    ])
    result = complaint_timing_evidence(data, "Ford Transit", 2020, "Engine stalls / loses power")
    assert len(result) == 2
    assert result.iloc[0].coverage_pct == 20
    assert pd.isna(result.iloc[1].median_reported_miles)

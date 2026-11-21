"""Regression coverage: source-priced maintenance timeline and hotspot linkage."""
from pathlib import Path

import pandas as pd
import pytest

from maintenance_forecast import (
    budget_windows, build_forecast, hotspot_table, validate_maintenance_costs,
)
from maintenance_intelligence import validate_schedule

ROOT = Path(__file__).resolve().parents[1]


def schedules():
    return validate_schedule(pd.read_csv(ROOT / "data/maintenance_schedules.csv"))


def prices():
    return validate_maintenance_costs(pd.read_csv(ROOT / "data/maintenance_cost_refs.csv"))


def test_cost_catalog_source_year_and_range_validation():
    data = prices()
    assert len(data) >= 6
    assert (data.model_year == 2020).all()
    assert (data.high_usd >= data.low_usd).all()
    assert data.source_url.str.startswith("https://").all()
    bad = data.copy()
    bad.loc[bad.index[0], "high_usd"] = 1
    with pytest.raises(ValueError, match="Invalid"):
        validate_maintenance_costs(bad)


def test_unrecorded_service_does_not_generate_false_due_events():
    events, other = build_forecast(
        schedules(), prices(), "Ford Transit", 2020, 118000, {}
    )
    assert events.empty
    assert not other.empty
    cost = budget_windows(events)
    assert cost.priced_events.sum() == 0
    assert cost.known_low_usd.isna().all()


def test_known_service_generates_repeated_milestones_with_sourced_prices():
    task = "Cabin air filter"
    events, _ = build_forecast(
        schedules(), prices(), "Ford Transit", 2020, 118000,
        {task: {"last_mileage": 100000}},
    )
    target = events.loc[events.task.eq(task)]
    assert target.event_mileage.tolist() == [120000, 140000, 160000]
    assert target.low_usd.tolist() == [83, 83, 83]
    assert target.high_usd.tolist() == [106, 106, 106]
    budgets = budget_windows(events)
    assert budgets.known_low_usd.tolist() == [83, 166, 249]
    assert budgets.known_high_usd.tolist() == [106, 212, 318]
    assert budgets.priced_events.tolist() == [1, 2, 3]


def test_overdue_interval_is_only_one_event_not_multiple_fictional_cycles():
    events, _ = build_forecast(
        schedules(), prices(), "Ford Transit", 2020, 160000,
        {"Cabin air filter": {"last_mileage": 100000}},
    )
    item = events.loc[events.task.eq("Cabin air filter")]
    assert len(item) == 1
    assert item.iloc[0].event_mileage == 160000
    assert item.iloc[0].documented_limit_mileage == 120000
    assert item.iloc[0].status == "Over limit"


def test_monitor_limit_does_not_project_recurring_changes():
    events, _ = build_forecast(
        schedules(), prices(), "Ram ProMaster", 2020, 100000,
        {"Engine oil and filter (monitor-directed; maximum limit)":
             {"last_mileage": 98000}},
    )
    assert len(events) == 1
    assert events.iloc[0].event_mileage == 108000
    assert events.iloc[0].status == "Maximum limit"
    assert events.iloc[0].price_basis == "Published estimate"


def test_sprinter_advisory_never_becomes_automatic_due():
    events, other = build_forecast(
        schedules(), prices(), "Mercedes Sprinter", 2020, 180000,
        {"Service interval — up to 20000 miles": {"last_mileage": 0}},
    )
    assert events.empty
    assert other.iloc[0].status == "Indicator / advisory only"


def test_unpriced_event_not_silently_free_and_custom_budget_is_labeled():
    task = "Spark plugs"
    histories = {task: {"last_mileage": 0}}
    events, _ = build_forecast(schedules(), prices(), "Ford Transit", 2020, 95000, histories)
    assert len(events) == 1
    assert pd.isna(events.iloc[0].low_usd)
    b = budget_windows(events).iloc[0]
    assert b.unpriced_events == 1
    assert pd.isna(b.known_low_usd)
    custom, _ = build_forecast(
        schedules(), prices(), "Ford Transit", 2020, 95000, histories,
        budget_overrides={task: (300, 500)},
    )
    assert custom.iloc[0].price_basis == "User budget"
    assert custom.iloc[0].low_usd == 300


def test_severe_duty_requires_opt_in():
    h = {"Engine oil and filter (severe-duty limit)": {"last_mileage": 100000}}
    regular, _ = build_forecast(schedules(), prices(), "Ram ProMaster", 2020, 101000, h)
    severe, _ = build_forecast(
        schedules(), prices(), "Ram ProMaster", 2020, 101000, h,
        include_severe=True,
    )
    assert regular.empty
    assert severe.iloc[0].event_mileage == 104000


def test_hotspots_are_selected_year_not_cross_model_aggregation():
    source = pd.DataFrame([
        {"vehicle": "Ford Transit", "model_year": 2020,
         "issue": "Engine stalls / loses power", "unique_complaints": 7,
         "mileage_samples": 2, "median_reported_miles": 120000},
        {"vehicle": "Ford Transit", "model_year": 2020,
         "issue": "Unspecified / manual review", "unique_complaints": 200,
         "mileage_samples": 0, "median_reported_miles": None},
        {"vehicle": "Ford Transit", "model_year": 2021,
         "issue": "Engine stalls / loses power", "unique_complaints": 80,
         "mileage_samples": 20, "median_reported_miles": 130000},
        {"vehicle": "Ram ProMaster", "model_year": 2020,
         "issue": "Engine stalls / loses power", "unique_complaints": 90,
         "mileage_samples": 3, "median_reported_miles": 20000},
    ])
    result = hotspot_table(source, "Ford Transit", 2020)
    assert result["unique_complaints"].tolist() == [7]
    assert result.iloc[0].mileage_coverage_pct == 28.6

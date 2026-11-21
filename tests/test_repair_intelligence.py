"""Tests for FleetIQ repair reference integrity and scenario arithmetic."""
from pathlib import Path

import pandas as pd
import pytest

from repair_intelligence import (
    REPAIR_VEHICLES, reported_issue_evidence, scenario_total,
    validate_repair_catalog,
)


def catalog():
    return pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "repair_costs.csv")


def test_seed_catalog_valid_and_platforms_covered():
    refs = validate_repair_catalog(catalog())
    assert len(refs) >= 12
    assert set(REPAIR_VEHICLES) == set(refs.vehicle)
    assert refs.source_url.str.startswith("https://").all()


def test_each_reference_has_positive_range_and_attribution():
    refs = validate_repair_catalog(catalog())
    assert (refs.high_usd >= refs.low_usd).all()
    assert (refs.low_usd > 0).all()
    assert refs.source_name.notna().all()
    assert refs.checked_on.notna().all()


def test_missing_sources_rejected():
    refs = catalog()
    refs.loc[0, "source_url"] = ""
    with pytest.raises(ValueError, match="HTTPS"):
        validate_repair_catalog(refs)


def test_invalid_and_duplicated_references_rejected():
    refs = catalog()
    refs.loc[0, "low_usd"] = 99999
    with pytest.raises(ValueError, match="range"):
        validate_repair_catalog(refs)
    with pytest.raises(ValueError, match="duplicate"):
        validate_repair_catalog(pd.concat([catalog(), catalog()], ignore_index=True))


def test_scenario_calculation_and_invalid_inputs():
    assert scenario_total(350, 3, 125, 40) == 765.0
    assert scenario_total(0, 0, 120, 0) == 0.0
    with pytest.raises(ValueError):
        scenario_total(-5, 1, 120)
    with pytest.raises(ValueError):
        scenario_total(5, float("inf"), 120)


def test_issue_evidence_filters_year_and_avoids_manual_review():
    frame = pd.DataFrame([
        {"vehicle": "Ford Transit", "model_year": 2020,
         "issue": "Unspecified / manual review", "unique_complaints": 9,
         "mileage_samples": 3, "median_reported_miles": 30000},
        {"vehicle": "Ford Transit", "model_year": 2020,
         "issue": "Cooling system / coolant leak", "unique_complaints": 2,
         "mileage_samples": 1, "median_reported_miles": 73000},
        {"vehicle": "Ford Transit", "model_year": 2021,
         "issue": "Cooling system / coolant leak", "unique_complaints": 4,
         "mileage_samples": 0, "median_reported_miles": None},
    ])
    result = reported_issue_evidence(frame, "Ford Transit", 2020)
    assert result["issue"].tolist() == ["Cooling system / coolant leak"]
    assert result["unique_complaints"].tolist() == [2]

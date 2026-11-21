"""Release regression coverage: official recalls and transparent fleet costs."""
import pandas as pd
import pytest
from recall_intelligence import (
    recall_query_url, parse_recall_response, component_summary,
)
from ownership_intelligence import annual_ownership_cost, comparison_table


def test_official_nhtsa_query_is_scoped_and_encoded():
    url = recall_query_url("Mercedes Sprinter", 2020)
    assert url.startswith("https://api.nhtsa.gov/recalls/recallsByVehicle?")
    assert "Mercedes-Benz" in url and "modelYear=2020" in url
    with pytest.raises(ValueError):
        recall_query_url("Unknown Van", 2020)


def test_nhtsa_records_are_deduplicated_but_keep_remedies_and_consequences():
    record = {
        "NHTSACampaignNumber": "20V123000", "Component": "BRAKES",
        "Summary": "Affected part description", "Consequence": "Safety impact",
        "Remedy": "Manufacturer repairs affected vehicles",
        "Manufacturer": "Example", "ReportReceivedDate": "2020-01-01",
    }
    results = parse_recall_response({"results": [record, record]})
    assert len(results) == 1
    assert results.iloc[0]["Remedy"] == record["Remedy"]
    assert component_summary(results).iloc[0]["Campaigns"] == 1


def test_empty_and_malformed_nhtsa_api_responses():
    assert parse_recall_response({"results": []}).empty
    with pytest.raises(ValueError, match="results"):
        parse_recall_response({})
    with pytest.raises(ValueError, match="schema"):
        parse_recall_response({"results": [{"unexpected": 1}]})


def test_ownership_costs_no_finance_principal_double_count():
    inputs = dict(
        purchase_price=40000, resale_value=20000, ownership_years=5,
        miles_per_year=20000, mpg=20, fuel_price=4,
        insurance_annual=3000, maintenance_per_mile=0.1,
        repairs_annual=1000, other_annual=500,
        financing_total=2500, downtime_days_annual=2,
        downtime_cost_day=200,
    )
    x = annual_ownership_cost(**inputs)
    assert x["components"]["Depreciation"] == 4000
    assert x["components"]["Fuel"] == 4000
    assert x["components"]["Financing interest and fees"] == 500
    assert x["annual_cost"] == 15400
    assert x["monthly_cost"] == round(15400 / 12, 2)
    assert x["cost_per_mile"] == 0.77


def test_zero_mileage_cost_per_mile_unavailable():
    args = dict(
        purchase_price=10000, resale_value=5000, ownership_years=5,
        miles_per_year=0, mpg=20, fuel_price=4,
        insurance_annual=1000, maintenance_per_mile=0,
        repairs_annual=0, other_annual=0,
    )
    assert annual_ownership_cost(**args)["cost_per_mile"] is None


def test_invalid_finance_and_resale_assumptions_rejected():
    x = dict(
        purchase_price=10000, resale_value=20000, ownership_years=5,
        miles_per_year=10000, mpg=12, fuel_price=3,
        insurance_annual=2000, maintenance_per_mile=0.1,
        repairs_annual=1000, other_annual=0,
    )
    with pytest.raises(ValueError, match="Resale"):
        annual_ownership_cost(**x)
    x["resale_value"] = 3000
    x["mpg"] = 0
    with pytest.raises(ValueError, match="greater"):
        annual_ownership_cost(**x)


def test_identical_assumptions_do_not_invent_van_rankings():
    base = dict(
        ownership_years=3, miles_per_year=15000, fuel_price=3,
        insurance_annual=2000, maintenance_per_mile=.05,
        repairs_annual=700, other_annual=800,
    )
    example = dict(
        purchase_price=26000, resale_value=9000, mpg=15,
        financing_total=0,
    )
    table = comparison_table(base, {
        "Ford Transit": example, "Ram ProMaster": example,
    })
    assert table["Annual cost ($)"].nunique() == 1

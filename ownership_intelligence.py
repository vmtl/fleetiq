"""FleetIQ ownership cost scenarios and transparent van comparison.

User-entered assumptions, not actual operating outcomes, financing offers,
repair probabilities, depreciation observations, or model reliability ranks.
"""
from __future__ import annotations

from math import isfinite
import pandas as pd
import plotly.express as px
import streamlit as st

VEHICLES = ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express")


def annual_ownership_cost(
    purchase_price: float, resale_value: float, ownership_years: int,
    miles_per_year: float, mpg: float, fuel_price: float, insurance_annual: float,
    maintenance_per_mile: float, repairs_annual: float, other_annual: float,
    financing_total: float = 0.0, downtime_days_annual: float = 0.0,
    downtime_cost_day: float = 0.0,
) -> dict:
    """Annualized cash + depreciation planning, with no double counting loan principal.

    Purchase minus expected resale is an asset-cost proxy. Only additional
    financing interest/fees belong in financing_total.
    """
    vals = [purchase_price, resale_value, miles_per_year, mpg, fuel_price,
            insurance_annual, maintenance_per_mile, repairs_annual,
            other_annual, financing_total, downtime_days_annual, downtime_cost_day]
    if ownership_years <= 0 or mpg <= 0:
        raise ValueError("Years and fuel efficiency must be greater than zero")
    if any(not isfinite(float(v)) or float(v) < 0 for v in vals):
        raise ValueError("Cost inputs must be finite and nonnegative")
    if resale_value > purchase_price:
        raise ValueError("Resale cannot exceed purchase in this depreciation-only model")
    depreciation = (purchase_price - resale_value) / ownership_years
    fuel = miles_per_year / mpg * fuel_price
    maintenance = miles_per_year * maintenance_per_mile
    financing = financing_total / ownership_years
    downtime = downtime_days_annual * downtime_cost_day
    components = {
        "Depreciation": depreciation,
        "Fuel": fuel,
        "Insurance": insurance_annual,
        "Planned maintenance": maintenance,
        "Repair reserve": repairs_annual,
        "Other fixed / operating": other_annual,
        "Financing interest and fees": financing,
        "Downtime allowance": downtime,
    }
    annual = sum(components.values())
    return {
        "annual_cost": round(annual, 2),
        "monthly_cost": round(annual / 12, 2),
        "cost_per_mile": round(annual / miles_per_year, 3) if miles_per_year else None,
        "five_year_total": round(annual * 5, 2),
        "term_total": round(annual * ownership_years, 2),
        "components": components,
    }


def comparison_table(base: dict, scenarios: dict[str, dict]) -> pd.DataFrame:
    """Compare candidate vans only on explicit scenario inputs."""
    records = []
    for name, overrides in scenarios.items():
        if name not in VEHICLES:
            raise ValueError("Unknown van")
        config = {**base, **overrides}
        result = annual_ownership_cost(**config)
        records.append({
            "Vehicle": name,
            "Annual cost ($)": result["annual_cost"],
            "Monthly cost ($)": result["monthly_cost"],
            "Cost per mile ($)": result["cost_per_mile"],
            "Term total ($)": result["term_total"],
        })
    return pd.DataFrame(records).sort_values("Annual cost ($)")


def render_ownership_tab() -> None:
    st.markdown("#### Ownership Economics & Vehicle Comparison")
    st.caption(
        "Plan cost-of-ownership scenarios and compare up to four vans using "
        "YOUR assumptions. No model-specific price, fuel economy, repair "
        "probability or resale forecast is represented as verified."
    )
    st.info(
        "A lower calculated cost is not a reliability ranking or recommendation. "
        "Change inputs for each van to compare plausible purchase and operating scenarios."
    )
    years = st.slider("Ownership horizon (years)", 1, 10, 5, key="tco_years")
    c1, c2, c3 = st.columns(3)
    with c1:
        miles = st.number_input("Annual miles", 0, 250000, 25000, step=5000, key="tco_miles")
        fuel_price = st.number_input("Fuel price ($/gallon)", 0.0, 20.0, 3.50, step=.10, key="tco_fuel")
        insurance = st.number_input("Annual insurance ($)", 0.0, 100000.0, 6000.0, step=250.0, key="tco_insurance")
    with c2:
        maintenance = st.number_input("Maintenance reserve ($/mile)", 0.0, 5.0, .10, step=.01, key="tco_maintenance")
        repairs = st.number_input("Annual repair reserve ($)", 0.0, 100000.0, 2000.0, step=250.0, key="tco_repairs")
        other = st.number_input("Other annual costs ($)", 0.0, 100000.0, 1000.0, step=250.0, key="tco_other")
    with c3:
        annual_downtime = st.number_input("Downtime days/year", 0.0, 365.0, 0.0, step=1.0, key="tco_downtime_days")
        day_cost = st.number_input("Business cost/day of downtime ($)", 0.0, 10000.0, 0.0, step=50.0, key="tco_downtime_rate")
        st.caption("These values are editable examples for budgeting, not validated averages.")
    candidates = st.multiselect(
        "Compare van platforms", VEHICLES, default=list(VEHICLES)[:2],
        max_selections=4, key="tco_vans",
    )
    if not candidates:
        st.warning("Select at least one vehicle for comparison.")
        return
    shared = {
        "ownership_years": years, "miles_per_year": miles,
        "fuel_price": fuel_price, "insurance_annual": insurance,
        "maintenance_per_mile": maintenance, "repairs_annual": repairs,
        "other_annual": other, "downtime_days_annual": annual_downtime,
        "downtime_cost_day": day_cost,
    }
    st.markdown("##### Vehicle-specific assumptions")
    st.caption(
        "All initial values are illustrative and IDENTICAL across vans to "
        "prevent invented vehicle rankings. Replace with purchase quotes, "
        "verified combined mpg, resale assumptions, and actual finance terms."
    )
    scenarios = {}
    for vehicle in candidates:
        with st.expander(vehicle, expanded=True):
            a, b, c, d = st.columns(4)
            key = vehicle.lower().replace(" ", "_")
            with a:
                purchase = st.number_input(
                    "Purchase price ($)", 0.0, 300000.0, 35000.0,
                    step=1000.0, key=f"{key}_purchase",
                )
            with b:
                resale = st.number_input(
                    "Expected resale after horizon ($)", 0.0,
                    max(0.0, purchase), min(10000.0, purchase),
                    step=1000.0, key=f"{key}_resale",
                )
            with c:
                mpg = st.number_input(
                    "Real-world combined mpg", 1.0, 100.0,
                    15.0, step=1.0, key=f"{key}_mpg",
                )
            with d:
                finance = st.number_input(
                    "Financing interest + fees over horizon ($)", 0.0,
                    100000.0, 0.0, step=250.0, key=f"{key}_finance",
                )
            scenarios[vehicle] = {
                "purchase_price": purchase, "resale_value": resale,
                "mpg": mpg, "financing_total": finance,
            }
    table = comparison_table(shared, scenarios)
    st.dataframe(table, hide_index=True, use_container_width=True)
    if len(table) > 1:
        fig = px.bar(
            table, x="Vehicle", y="Annual cost ($)",
            color="Vehicle", color_discrete_sequence=[
                "#00F5D4", "#E879F9", "#00BFFF", "#FBBF24"
            ], title="Scenario annual ownership cost",
        )
        fig.update_layout(
            template="plotly_dark", showlegend=False,
            paper_bgcolor="rgba(7,14,30,0)",
            plot_bgcolor="rgba(19,34,56,.23)",
        )
        st.plotly_chart(fig, use_container_width=True)
    breakdown = []
    for vehicle in candidates:
        val = annual_ownership_cost(**{**shared, **scenarios[vehicle]})
        breakdown += [
            {"Vehicle": vehicle, "Cost category": k, "Annual USD": round(v, 2)}
            for k, v in val["components"].items()
        ]
    st.markdown("##### Annual cost components")
    st.dataframe(pd.DataFrame(breakdown), hide_index=True, use_container_width=True)
    csv_data = table.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download ownership comparison (CSV)", csv_data,
        "fleetiq_ownership_scenarios.csv", "text/csv", key="tco_download",
    )
    st.caption(
        "Depreciation = (purchase minus assumed resale) / years. "
        "Fuel = annual miles / mpg × price. Financing input is INTEREST AND FEES ONLY; "
        "do not enter loan principal or it will be counted twice. Downtime is "
        "a user-supplied business cost, not a statistically predicted failure event. "
        "Taxes, maintenance, financing, labor, and downtime can vary substantially."
    )

"""Operational economics and evidence gating for predictive maintenance."""
from __future__ import annotations
from math import isfinite
import pandas as pd
import streamlit as st


def delivery_profit_scenario(
    routes_per_week: float, revenue_per_route: float,
    driver_cost_per_route: float, weekly_miles: float, mpg: float,
    fuel_price: float, insurance_weekly: float, vehicle_fixed_weekly: float,
    maintenance_per_mile: float, other_weekly: float,
    downtime_routes_per_week: float = 0,
) -> dict:
    values = (routes_per_week, revenue_per_route, driver_cost_per_route,
              weekly_miles, mpg, fuel_price, insurance_weekly,
              vehicle_fixed_weekly, maintenance_per_mile, other_weekly,
              downtime_routes_per_week)
    if any(not isfinite(float(v)) or v < 0 for v in values) or mpg == 0:
        raise ValueError("Scenario inputs must be finite and nonnegative; mpg must be positive")
    if downtime_routes_per_week > routes_per_week:
        raise ValueError("Missed routes cannot exceed scheduled routes")
    delivered = routes_per_week - downtime_routes_per_week
    revenue = delivered * revenue_per_route
    driver = delivered * driver_cost_per_route
    fuel = weekly_miles / mpg * fuel_price
    maintenance = weekly_miles * maintenance_per_mile
    expense = driver + fuel + maintenance + insurance_weekly + vehicle_fixed_weekly + other_weekly
    contribution = revenue - expense
    return {
        "completed_routes": delivered,
        "weekly_revenue": round(revenue, 2),
        "weekly_cost": round(expense, 2),
        "weekly_contribution": round(contribution, 2),
        "annualized_contribution": round(contribution * 52, 2),
        "breakdown": {
            "Driver labor": driver, "Fuel": fuel, "Maintenance reserve": maintenance,
            "Insurance": insurance_weekly, "Vehicle fixed": vehicle_fixed_weekly,
            "Other operating": other_weekly,
        },
    }


def assess_prediction_readiness(frame: pd.DataFrame) -> dict:
    """A data sufficiency GATE, not a trained model or claimed forecast."""
    needed = {"asset_id", "vehicle", "model_year", "event_observed",
              "last_observed_miles", "event_miles", "system"}
    missing = needed - set(frame.columns)
    if missing:
        return {"ready": False, "reason": "Missing outcome columns: " + ", ".join(sorted(missing))}
    if frame.empty:
        return {"ready": False, "reason": "No observed vehicles or verified repair outcomes"}
    work = frame.copy()
    for col in ("model_year", "event_observed", "last_observed_miles", "event_miles"):
        work[col] = pd.to_numeric(work[col], errors="coerce")
    if work[list(("model_year", "event_observed", "last_observed_miles"))].isna().any().any():
        return {"ready": False, "reason": "Incomplete model-year, event or mileage observations"}
    if (~work.event_observed.isin([0, 1])).any():
        return {"ready": False, "reason": "Event indicator must be 0 (censored) or 1 (repair)"}
    if (work.last_observed_miles <= 0).any():
        return {"ready": False, "reason": "Mileage exposure must be positive"}
    failures = work[work.event_observed.eq(1)]
    censored = work[work.event_observed.eq(0)]
    if failures.event_miles.isna().any() or (failures.event_miles <= 0).any():
        return {"ready": False, "reason": "Observed repair events need verified event mileage"}
    if (failures.event_miles > failures.last_observed_miles).any():
        return {"ready": False, "reason": "Event mileage cannot exceed exposure mileage"}
    if work.asset_id.duplicated().any():
        return {"ready": False, "reason": "A cohort needs one endpoint per unit/system; repeated observations require proper longitudinal modeling"}
    if len(work) < 100 or len(failures) < 25 or len(censored) < 25:
        return {"ready": False, "reason": (
            "Illustrative minimum gate: 100 unique vehicles, 25 verified repair "
            "events and 25 censored observations; independent representativeness "
            "and model validation remain required."
        ), "vehicles": len(work), "events": len(failures), "censored": len(censored)}
    return {"ready": False, "reason": (
        "Sample-volume gate met, but model deployment remains blocked until "
        "cohort comparability, provenance, outcome adjudication, holdout calibration, "
        "time-leakage controls and bias assessments are completed."
    ), "vehicles": len(work), "events": len(failures), "censored": len(censored)}


def render_profitability() -> None:
    st.markdown("##### Route Profitability Scenario")
    st.caption(
        "Editable hypothetical delivery-business unit economics. "
        "This is not verified revenue, accounting, or a cash-flow statement."
    )
    a, b, c = st.columns(3)
    routes = a.number_input("Scheduled routes/week", 0, 30, 5, key="prof_routes")
    revenue = b.number_input("Revenue per completed route ($)", 0.0, 3000.0, 350.0, step=25.0, key="prof_revenue")
    driver = c.number_input("Driver cost/route ($)", 0.0, 1000.0, 170.0, step=10.0, key="prof_driver")
    a, b, c = st.columns(3)
    miles = a.number_input("Driven miles/week", 0.0, 10000.0, 750.0, step=50.0, key="prof_miles")
    mpg = b.number_input("Measured mpg", 1.0, 100.0, 15.0, key="prof_mpg")
    fuel = c.number_input("Fuel ($/gallon)", 0.0, 20.0, 3.50, step=.10, key="prof_fuel")
    a, b, c = st.columns(3)
    ins = a.number_input("Weekly insurance ($)", 0.0, 5000.0, 175.0, key="prof_ins")
    fixed = b.number_input("Vehicle fixed weekly cash costs ($)", 0.0, 5000.0, 125.0, key="prof_fixed")
    maintenance = c.number_input("Maintenance + repair reserve ($/mile)", 0.0, 5.0, .12, step=.01, key="prof_maint")
    a, b = st.columns(2)
    other = a.number_input("Other operating weekly ($)", 0.0, 5000.0, 50.0, key="prof_other")
    missed = b.number_input("Missed routes/week", 0, routes, 0, key="prof_missed")
    result = delivery_profit_scenario(
        routes, revenue, driver, miles, mpg, fuel, ins, fixed,
        maintenance, other, missed
    )
    a, b, c = st.columns(3)
    a.metric("Weekly revenue", f"${result['weekly_revenue']:,.0f}")
    b.metric("Weekly cash cost + reserves", f"${result['weekly_cost']:,.0f}")
    c.metric("Weekly contribution", f"${result['weekly_contribution']:,.0f}")
    st.caption(
        "Contribution before income taxes, depreciation, owner compensation "
        "unless included above, and any other unlisted costs. Fixed cash costs "
        "and reserves may overlap with depreciation-based ownership economics; "
        "do not add both totals without reconciliation."
    )


def render_prediction_readiness() -> None:
    with st.expander("Predictive model readiness and required outcome data"):
        st.write(
            "FleetIQ does not currently have a representative, validated "
            "population of verified repair outcomes plus vehicles without failures. "
            "Consumer complaints cannot fill this gap."
        )
        st.code(
            "asset_id,vehicle,model_year,system,event_observed,event_miles,last_observed_miles",
            language="text",
        )
        uploaded = st.file_uploader(
            "Evaluate an anonymized repair-outcome dataset (CSV, max 2MB)",
            type="csv", key="readiness_csv",
        )
        if uploaded:
            try:
                if uploaded.size > 2_000_000:
                    raise ValueError("CSV exceeds 2MB limit")
                data = pd.read_csv(uploaded)
                result = assess_prediction_readiness(data)
                st.warning(result["reason"])
            except (ValueError, pd.errors.ParserError) as exc:
                st.error(f"Outcome file rejected: {exc}")
        else:
            st.info(
                "Prediction deployment is blocked until real service histories, "
                "nonfailure exposure, independent cohort validation and "
                "appropriate data permissions are available."
            )

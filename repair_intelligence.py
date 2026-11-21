"""FleetIQ Repair Cost Intelligence.

Published third-party estimates are reference observations, not repair diagnoses,
guaranteed quotes, vehicle-year-specific predictions, or validated invoices.
No external API or scraping at dashboard runtime.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REQUIRED = {
    "vehicle", "reference_configuration", "repair_operation", "system",
    "low_usd", "high_usd", "source_url", "related_reported_issue",
    "source_name", "checked_on", "geographic_scope", "source_scope_note",
}
REPAIR_VEHICLES = (
    "Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express"
)


def validate_repair_catalog(frame: pd.DataFrame) -> pd.DataFrame:
    """Fail closed on missing, duplicated, unsourced or nonsensical estimates."""
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError("Repair catalog missing: " + ", ".join(sorted(missing)))
    data = frame.copy()
    for col in ("low_usd", "high_usd"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    if data.empty:
        raise ValueError("Repair catalog has no records")
    if data[["low_usd", "high_usd"]].isna().any().any():
        raise ValueError("Repair catalog has missing or invalid price")
    if ((data["low_usd"] <= 0) | (data["high_usd"] < data["low_usd"])).any():
        raise ValueError("Repair catalog price range is invalid")
    if data.duplicated(["vehicle", "reference_configuration", "repair_operation"]).any():
        raise ValueError("Repair catalog contains duplicate repair references")
    if not data["source_url"].astype(str).str.match(r"^https://", na=False).all():
        raise ValueError("Every repair reference requires an HTTPS source URL")
    if not data["vehicle"].isin(REPAIR_VEHICLES).all():
        raise ValueError("Unknown vehicle platform in repair catalog")
    if not data["checked_on"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Every reference must have an audit date")
    return data


def scenario_total(parts_usd: float, hours: float, hourly_rate_usd: float,
                   fees_usd: float = 0.0) -> float:
    """Scenario arithmetic only; assumptions are not a shop quote."""
    values = (parts_usd, hours, hourly_rate_usd, fees_usd)
    if any(x < 0 or not float(x) < float("inf") for x in values):
        raise ValueError("Inputs must be nonnegative finite numbers")
    return round(parts_usd + hours * hourly_rate_usd + fees_usd, 2)


def reported_issue_evidence(summary: pd.DataFrame, vehicle: str,
                            model_year: int | None = None) -> pd.DataFrame:
    """Return observed complaint issue groups, without conflating with repairs."""
    required = {"vehicle", "model_year", "issue", "unique_complaints",
                "mileage_samples", "median_reported_miles"}
    if required - set(summary.columns):
        return pd.DataFrame()
    subset = summary.loc[summary["vehicle"].eq(vehicle)].copy()
    subset["model_year"] = pd.to_numeric(subset["model_year"], errors="coerce")
    if model_year is not None:
        subset = subset.loc[subset["model_year"].eq(model_year)]
    subset = subset.loc[~subset["issue"].isin(
        ["Unspecified / manual review", "Sensor / warning / diagnostic"]
    )]
    for col in ("unique_complaints", "mileage_samples", "median_reported_miles"):
        subset[col] = pd.to_numeric(subset[col], errors="coerce")
    return subset.sort_values("unique_complaints", ascending=False)


@st.cache_data(show_spinner=False)
def load_repair_catalog(path: str, modified_time: int) -> pd.DataFrame:
    return validate_repair_catalog(pd.read_csv(path))


@st.cache_data(show_spinner=False)
def load_repair_issue_summary(path: str, modified_time: int) -> pd.DataFrame:
    return pd.read_csv(path)


def render_repair_cost_tab(data_dir: Path) -> None:
    st.markdown("#### Repair Cost Intelligence")
    st.caption(
        "Explore published repair-price references for four commercial van "
        "platforms, compare historical complaint evidence, and build a separate "
        "parts-and-labor planning scenario. No automated repair diagnosis or "
        "failure prediction is performed."
    )
    catalog_path = data_dir / "repair_costs.csv"
    if not catalog_path.exists():
        st.warning("Repair cost reference dataset is unavailable.")
        return
    try:
        catalog = load_repair_catalog(
            str(catalog_path), catalog_path.stat().st_mtime_ns
        )
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Cannot load repair references: {exc}")
        return

    left, center, right = st.columns([2, 1, 1])
    with left:
        vehicle = st.selectbox(
            "Commercial van", sorted(catalog["vehicle"].unique()),
            key="repair_vehicle",
        )
    with center:
        selected_year = st.number_input(
            "Model year (context)", min_value=2014, max_value=2026,
            value=2020, step=1, key="repair_model_year",
        )
    with right:
        mileage = st.number_input(
            "Current mileage (optional)", min_value=0, max_value=900000,
            value=0, step=5000, key="repair_mileage",
        )
    rows = catalog[catalog["vehicle"].eq(vehicle)].copy()
    repair = st.selectbox(
        "Repair operation", sorted(rows["repair_operation"].unique()),
        key="repair_operation",
    )
    selected = rows.loc[rows["repair_operation"].eq(repair)].iloc[0]
    st.info(
        f"Reference configuration: {selected['reference_configuration']}. "
        f"Your {selected_year} vehicle may have different parts, engine, drivetrain, "
        "labor time or price. Verify fitment and get an itemized local quote."
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Published low", f"${selected['low_usd']:,.0f}")
    m2.metric("Published high", f"${selected['high_usd']:,.0f}")
    m3.metric("Reference entries", str(len(rows)))
    st.caption(
        f"Source: {selected['source_name']} · {selected['geographic_scope']} · "
        f"reviewed {selected['checked_on']}. These are third-party published "
        "estimator figures, not guaranteed prices or an invoice."
    )
    st.markdown(f"[View original repair estimate]({selected['source_url']})")
    st.caption(str(selected["source_scope_note"]))

    st.markdown("##### Compare published repair references")
    fig = px.bar(
        rows.sort_values("high_usd"),
        x="repair_operation", y=["low_usd", "high_usd"],
        barmode="group",
        labels={
            "value": "Published reference (USD)",
            "repair_operation": "Repair operation", "variable": "Range endpoint",
        },
        color_discrete_sequence=["#00F5D4", "#E879F9"],
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(7,14,30,0)",
        plot_bgcolor="rgba(19,34,56,.23)",
        legend_title_text="Published reference",
        margin=dict(l=20, r=20, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        rows[["repair_operation", "reference_configuration", "low_usd",
              "high_usd", "source_url"]].rename(columns={
                  "repair_operation": "Repair",
                  "reference_configuration": "Reference configuration",
                  "low_usd": "Low (USD)", "high_usd": "High (USD)",
                  "source_url": "Published source",
              }),
        column_config={"Published source": st.column_config.LinkColumn()},
        hide_index=True, use_container_width=True,
    )
    st.download_button(
        "Download selected published repair references (CSV)",
        data=rows.to_csv(index=False).encode("utf-8"),
        file_name="fleetiq_repair_references.csv",
        mime="text/csv", key="repair_reference_download",
    )

    st.markdown("##### Build a custom repair budget scenario")
    st.caption(
        "Enter values from a shop quote or your own planning assumptions. "
        "This calculation is separate from published estimates; it is not a "
        "location-adjusted estimate or a price prediction."
    )
    with st.expander("Parts, labor, and additional fees", expanded=True):
        a, b, c, d = st.columns(4)
        with a:
            parts = st.number_input("Parts (USD)", min_value=0.0,
                                    max_value=100000.0, value=0.0,
                                    step=25.0, key="repair_parts")
        with b:
            hours = st.number_input("Labor hours", min_value=0.0,
                                    max_value=200.0, value=0.0,
                                    step=0.5, key="repair_hours")
        with c:
            rate = st.number_input("Shop rate (USD/hr)", min_value=0.0,
                                   max_value=1000.0, value=120.0,
                                   step=10.0, key="repair_rate")
        with d:
            fees = st.number_input("Other fees (USD)", min_value=0.0,
                                   max_value=10000.0, value=0.0,
                                   step=10.0, key="repair_fees")
        total = scenario_total(parts, hours, rate, fees)
        st.metric("Your hypothetical scenario total", f"${total:,.2f}")
        st.caption(
            "Before taxes, unless included in your fees. The initial $120/hr "
            "is an editable planning assumption, not a model- or ZIP-specific rate."
        )
        st.download_button(
            "Download budget scenario (CSV)",
            data=pd.DataFrame([{
                "vehicle": vehicle, "model_year": selected_year,
                "mileage": mileage if mileage else None,
                "repair_operation": repair,
                "parts_usd": parts, "labor_hours": hours,
                "shop_rate_usd": rate, "other_fees_usd": fees,
                "scenario_total_usd": total,
                "classification": "user_entered_hypothetical_not_quote",
            }]).to_csv(index=False).encode("utf-8"),
            file_name="fleetiq_repair_budget_scenario.csv",
            mime="text/csv", key="repair_scenario_download",
        )

    st.markdown("##### Related NHTSA complaint patterns")
    st.caption(
        "Complaints identify reported symptoms, not a confirmed faulty part. "
        "There is no validated failure probability or repair-due-mileage "
        "available from these reports. The association below is topical only."
    )
    problem_path = data_dir / "problem_summary.csv"
    if problem_path.exists():
        try:
            issues = load_repair_issue_summary(
                str(problem_path), problem_path.stat().st_mtime_ns
            )
            filtered = reported_issue_evidence(issues, vehicle, int(selected_year))
            relevant = filtered[
                filtered["issue"].eq(str(selected["related_reported_issue"]))
            ]
            if relevant.empty:
                st.info(
                    "No classified complaint evidence for this repair topic and "
                    "selected model year. This does not indicate that the vehicle "
                    "has zero problems or that this repair is necessary."
                )
            else:
                st.dataframe(
                    relevant[["issue", "unique_complaints", "mileage_samples",
                              "median_reported_miles"]].rename(columns={
                                  "issue": "Reported symptom category",
                                  "unique_complaints": "Unique reports",
                                  "mileage_samples": "Reports with mileage",
                                  "median_reported_miles": "Median reported miles",
                              }),
                    hide_index=True, use_container_width=True,
                )
                st.caption(
                    "Median is based only on complaints with available mileage, "
                    "and represents complaint reporting rather than repair timing."
                )
        except (OSError, pd.errors.ParserError) as exc:
            st.warning(f"Problem-evidence data unavailable: {exc}")
    else:
        st.info("Problem summary not found. Cost references remain available.")

    st.warning(
        "For brakes, steering, fuel leaks, electrical fire or other safety "
        "concerns, seek a professional inspection promptly. A report or a price "
        "reference does not determine whether a vehicle is safe to drive."
    )

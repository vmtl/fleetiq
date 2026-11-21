"""FleetIQ manufacturer maintenance schedules and NHTSA timing exploration.

Never interprets consumer complaint mileage as a failure distribution or quotes
a universal service interval for mismatched year / engine / duty cycle.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

SCHEDULE_REQUIRED = {
    "vehicle", "model_year_start", "model_year_end", "task",
    "interval_miles", "interval_months", "schedule_mode",
    "operating_condition", "engine_scope", "source_url", "source_name",
    "source_section", "notes", "reviewed_on",
}
MODES = {"recurring", "monitor_cap", "condition_cap", "monitor_event", "advisory"}
VEHICLES = ["Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express"]


def validate_schedule(frame: pd.DataFrame) -> pd.DataFrame:
    missing = SCHEDULE_REQUIRED - set(frame.columns)
    if missing:
        raise ValueError("Maintenance schedule missing columns: " + ", ".join(sorted(missing)))
    if frame.empty:
        raise ValueError("Maintenance schedule is empty")
    out = frame.copy()
    for column in ("model_year_start", "model_year_end", "interval_miles", "interval_months"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if out[["model_year_start", "model_year_end", "interval_miles", "interval_months"]].isna().any().any():
        raise ValueError("Maintenance schedule has missing numeric values")
    for column in ("model_year_start", "model_year_end", "interval_miles", "interval_months"):
        if (out[column] % 1 != 0).any():
            raise ValueError("Maintenance schedule requires integral intervals and years")
        out[column] = out[column].astype(int)
    if (out["model_year_start"] > out["model_year_end"]).any():
        raise ValueError("Maintenance schedule has reversed year range")
    if ((out["interval_miles"] < 0) | (out["interval_months"] < 0)).any():
        raise ValueError("Maintenance intervals cannot be negative")
    if (~out["schedule_mode"].isin(MODES)).any():
        raise ValueError("Unknown schedule mode")
    if (out["schedule_mode"].isin(["recurring", "monitor_cap", "condition_cap"])
            & out["interval_miles"].eq(0) & out["interval_months"].eq(0)).any():
        raise ValueError("Calculable schedule must have mileage or time limit")
    if (out["source_url"].isna() | ~out["source_url"].astype(str).str.startswith("https://")).any():
        raise ValueError("Every maintenance row needs an HTTPS manufacturer source")
    if (~out["vehicle"].isin(VEHICLES)).any():
        raise ValueError("Unknown vehicle in maintenance schedule")
    if out.duplicated(["vehicle", "model_year_start", "model_year_end", "task"]).any():
        raise ValueError("Duplicate maintenance operation")
    return out


def assess_service(task: dict, mileage: int,
                   last_service_mileage: int | None = None,
                   months_since_service: int | None = None) -> dict:
    """Calculate mileage/time limit only when service history is supplied.

    Neither 'due' nor 'overdue' claims can be made without service history.
    This does not assess vehicle-condition, service monitor, or engine hours.
    """
    current = int(mileage)
    limit = int(task["interval_miles"])
    months_limit = int(task["interval_months"])
    mode = str(task["schedule_mode"])
    if current < 0:
        raise ValueError("Mileage must not be negative")
    if last_service_mileage is not None and (last_service_mileage < 0 or last_service_mileage > current):
        raise ValueError("Last service mileage must be between 0 and odometer")
    if months_since_service is not None and months_since_service < 0:
        raise ValueError("Months since service must not be negative")

    result = {
        "status": "Reference only",
        "miles_since_service": None,
        "miles_to_limit": None,
        "limit_mileage": None,
        "time_limit_reached": False,
        "known_history": False,
    }
    if mode in {"advisory", "monitor_event"}:
        return result
    has_miles = last_service_mileage is not None and limit > 0
    has_months = months_since_service is not None and months_limit > 0
    if not (has_miles or has_months):
        result["status"] = "Service history needed"
        return result
    if has_miles:
        since = current - int(last_service_mileage)
        result["miles_since_service"] = since
        result["limit_mileage"] = int(last_service_mileage) + limit
        result["miles_to_limit"] = limit - since
    if has_months:
        result["time_limit_reached"] = months_since_service >= months_limit
    exceeded = (has_miles and result["miles_to_limit"] <= 0) or result["time_limit_reached"]
    if exceeded:
        result["status"] = "At or past documented limit"
    elif has_miles and result["miles_to_limit"] <= min(1000, limit * 0.1):
        result["status"] = "Approaching documented limit"
    else:
        result["status"] = "Within documented limit (based on inputs)"
    result["known_history"] = True
    return result


def complaint_timing_evidence(frame: pd.DataFrame, vehicle: str,
                              model_year: int, issue: str) -> pd.DataFrame:
    required = {"vehicle", "model_year", "issue", "unique_complaints",
                "mileage_samples", "median_reported_miles"}
    if required - set(frame.columns):
        raise ValueError("Problem summary lacks required columns")
    subset = frame.loc[frame["vehicle"].eq(vehicle) & frame["issue"].eq(issue)].copy()
    for column in ["model_year", "unique_complaints", "mileage_samples", "median_reported_miles"]:
        subset[column] = pd.to_numeric(subset[column], errors="coerce")
    subset = subset[subset["model_year"].between(max(2014, model_year - 3), min(2026, model_year + 3))]
    subset = subset.sort_values("model_year")
    # A positive odometer reported in a complaint is evidence of reported
    # mileage, not proof that a repair or a failure happened at that value.
    subset["coverage_pct"] = (
        subset["mileage_samples"].div(subset["unique_complaints"].where(
            subset["unique_complaints"] > 0
        )).mul(100).round(1)
    )
    subset.loc[subset["mileage_samples"].eq(0), "median_reported_miles"] = float("nan")
    return subset


@st.cache_data(show_spinner=False)
def load_schedule(path: str, updated_ns: int) -> pd.DataFrame:
    return validate_schedule(pd.read_csv(path))


@st.cache_data(show_spinner=False)
def load_problem_summary(path: str, updated_ns: int) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def render_maintenance_tab(data_dir: Path) -> None:
    st.markdown("#### Maintenance & Repair Timing")
    st.caption(
        "Manufacturer maintenance guidance and historical NHTSA complaint "
        "mileage are separate evidence. An odometer reading alone cannot "
        "diagnose repairs or establish a vehicle's service history."
    )
    schedule_path = data_dir / "maintenance_schedules.csv"
    if not schedule_path.exists():
        st.warning("Maintenance schedule data is not installed.")
        return
    try:
        catalog = load_schedule(str(schedule_path), schedule_path.stat().st_mtime_ns)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Unable to validate maintenance references: {exc}")
        return

    a, b, c = st.columns([2, 1, 1])
    with a:
        vehicle = st.selectbox("Vehicle", VEHICLES, key="maintenance_vehicle")
    with b:
        year = st.number_input(
            "Model year", min_value=2014, max_value=2026,
            value=2020, step=1, key="maintenance_year",
        )
    with c:
        odometer = st.number_input(
            "Current odometer (miles)", min_value=0,
            max_value=1000000, value=100000, step=500,
            key="maintenance_odometer",
        )
    selected = catalog.loc[
        catalog["vehicle"].eq(vehicle)
        & catalog["model_year_start"].le(year)
        & catalog["model_year_end"].ge(year)
    ].copy()
    if selected.empty:
        st.info(
            "No year-specific manufacturer maintenance schedule has been "
            f"verified for the {year} {vehicle} in FleetIQ yet. "
            "Do not substitute a different model year's intervals. "
            "Historical complaint mileage remains available below."
        )
    else:
        st.markdown("##### Documented maintenance guidance")
        st.caption(
            "Source scope matters: engine, transmission, severe duty, and "
            "service indicator requirements may differ. Always check your "
            "specific owner's manual and actual service records."
        )
        st.dataframe(
            selected[["task", "interval_miles", "interval_months",
                      "schedule_mode", "operating_condition", "engine_scope"]]
            .rename(columns={
                "task": "Task", "interval_miles": "Miles", "interval_months": "Months",
                "schedule_mode": "Type", "operating_condition": "Conditions",
                "engine_scope": "Configuration applicability",
            }),
            hide_index=True, use_container_width=True,
        )
        task_name = st.selectbox(
            "Evaluate one maintenance operation",
            selected["task"].tolist(), key="maintenance_task",
        )
        task = selected.loc[selected["task"].eq(task_name)].iloc[0]
        st.caption(
            "A fixed interval means recurring service; a monitor cap is an "
            "absolute maximum, not permission to ignore an earlier dashboard "
            "warning. Advisory entries never produce a due-date calculation."
        )
        h1, h2 = st.columns(2)
        with h1:
            have_last = st.checkbox(
                "I know the mileage at the last completed service",
                value=False, key="maintenance_known_miles",
            )
            last_miles = (
                st.number_input(
                    "Odometer at last service", min_value=0,
                    max_value=int(odometer), value=0, step=500,
                    key="maintenance_last_mileage",
                ) if have_last else None
            )
        with h2:
            have_months = st.checkbox(
                "I know how many months since the last service",
                value=False, key="maintenance_known_months",
            )
            months = (
                st.number_input(
                    "Months since service", min_value=0,
                    max_value=600, value=0, step=1,
                    key="maintenance_elapsed_months",
                ) if have_months else None
            )
        result = assess_service(task.to_dict(), int(odometer), last_miles, months)
        st.metric("Maintenance interval assessment", result["status"])
        if result["miles_to_limit"] is not None:
            st.write(
                f"Recorded mileage since service: "
                f"**{result['miles_since_service']:,} miles** · "
                f"Documented mileage ceiling: "
                f"**{result['limit_mileage']:,} miles**"
            )
            if result["miles_to_limit"] > 0:
                st.caption(
                    f"{result['miles_to_limit']:,} miles remain until the "
                    "documented limit, based solely on your entries. Other "
                    "conditions or a service monitor can call for earlier work."
                )
        if result["status"] == "Service history needed":
            st.info("Provide the applicable last-service history to evaluate the interval.")
        if task["schedule_mode"] in {"advisory", "monitor_event"}:
            st.info(
                "No fixed next-service mileage is calculated for this "
                "monitor-based or general manufacturer advisory."
            )
        st.caption(
            f"Source: {task['source_name']} · {task['source_section']} · "
            f"reviewed {task['reviewed_on']}"
        )
        st.markdown(f"[Open original manufacturer reference]({task['source_url']})")
        st.caption(str(task["notes"]))
        st.download_button(
            "Download selected maintenance assessment (CSV)",
            data=pd.DataFrame([{
                "vehicle": vehicle, "model_year": year,
                "current_miles": odometer, "operation": task_name,
                "last_service_miles": last_miles,
                "months_since_service": months,
                "assessment": result["status"],
                "documented_miles_to_limit": result["miles_to_limit"],
                "source_url": task["source_url"],
                "disclaimer": "Historical guidance, not a confirmed repair need",
            }]).to_csv(index=False).encode("utf-8"),
            file_name="fleetiq_maintenance_assessment.csv", mime="text/csv",
            key="maintenance_export",
        )

    st.divider()
    st.markdown("##### Historical complaint mileage and vehicle age")
    st.caption(
        "Source: NHTSA consumer submissions analyzed by FleetIQ. "
        "Median odometer values describe when complaints were reported, "
        "not when repairs were performed or when components are likely to fail. "
        "There is no fleet-exposure denominator."
    )
    problem_path = data_dir / "problem_summary.csv"
    if not problem_path.exists():
        st.warning("Historical complaint analysis is unavailable.")
        return
    try:
        problems = load_problem_summary(str(problem_path), problem_path.stat().st_mtime_ns)
        subset = problems.loc[problems["vehicle"].eq(vehicle)].copy()
        subset["model_year"] = pd.to_numeric(subset["model_year"], errors="coerce")
        subset = subset[subset["model_year"].eq(year)]
        issue_choices = sorted(
            subset.loc[~subset["issue"].eq("Unspecified / manual review"),
                       "issue"].dropna().unique()
        )
        if not issue_choices:
            st.info("No classified complaint issues for this model year; this is not evidence of zero failures.")
            return
        issue = st.selectbox("Reported issue category", issue_choices,
                             key="maintenance_issue")
        timing = complaint_timing_evidence(problems, vehicle, int(year), issue)
        current = timing[timing["model_year"].eq(year)]
        if not current.empty:
            current_row = current.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Selected-year reports mentioning issue",
                      f"{int(current_row['unique_complaints']):,}")
            c2.metric("Reports with mileage",
                      f"{int(current_row['mileage_samples']):,}")
            c3.metric(
                "Selected-year reported median odometer",
                f"{int(current_row['median_reported_miles']):,} mi"
                if pd.notna(current_row["median_reported_miles"]) else "Unavailable",
            )
        chart_rows = timing[
            timing["mileage_samples"].ge(2)
            & timing["median_reported_miles"].notna()
        ].copy()
        if not chart_rows.empty:
            chart_rows["model_year"] = chart_rows["model_year"].astype(int).astype(str)
            fig = px.scatter(
                chart_rows, x="model_year", y="median_reported_miles",
                size="mileage_samples", color="coverage_pct",
                color_continuous_scale=["#152A4A", "#00F5D4"],
                hover_data=["unique_complaints", "mileage_samples"],
                labels={
                    "model_year": "Vehicle model year",
                    "median_reported_miles": "Median reported odometer (miles)",
                    "coverage_pct": "Mileage coverage (%)",
                },
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(7,14,30,0)",
                plot_bgcolor="rgba(19,34,56,.23)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Too few reports with mileage for a useful cross-year chart (minimum 2 per model year).")
        st.dataframe(
            timing[["model_year", "unique_complaints", "mileage_samples",
                    "coverage_pct", "median_reported_miles"]]
            .rename(columns={
                "model_year": "Model year", "unique_complaints": "Complaint reports",
                "mileage_samples": "With mileage",
                "coverage_pct": "Mileage coverage %",
                "median_reported_miles": "Reported median miles",
            }),
            hide_index=True, use_container_width=True,
        )
        # Link only topically corresponding repair references, not suggested
        # fixes or vehicle-year-specific repair quotes.
        repair_catalog_path = data_dir / "repair_costs.csv"
        if repair_catalog_path.exists():
            try:
                references = pd.read_csv(repair_catalog_path)
                needed = {
                    "vehicle", "related_reported_issue", "repair_operation",
                    "low_usd", "high_usd", "source_url",
                }
                if needed.issubset(references.columns):
                    linked = references.loc[
                        references["vehicle"].eq(vehicle)
                        & references["related_reported_issue"].eq(issue)
                    ].copy()
                    if not linked.empty:
                        st.markdown("##### Related repair cost references")
                        st.caption(
                            "These are reference prices for possible repair "
                            "operations in this symptom category, NOT proof "
                            "that this repair was performed or is needed."
                        )
                        st.dataframe(
                            linked[[
                                "repair_operation", "low_usd",
                                "high_usd", "source_url"
                            ]].rename(columns={
                                "repair_operation": "Possible operation",
                                "low_usd": "Reference low (USD)",
                                "high_usd": "Reference high (USD)",
                                "source_url": "Source",
                            }),
                            hide_index=True, use_container_width=True,
                            column_config={
                                "Source": st.column_config.LinkColumn()
                            },
                        )
            except (OSError, pd.errors.ParserError) as exc:
                st.caption(f"Repair reference data is unavailable: {exc}")

        st.download_button(
            "Download historical complaint timing evidence (CSV)",
            data=timing.to_csv(index=False).encode("utf-8"),
            file_name="fleetiq_complaint_timing.csv",
            mime="text/csv", key="maintenance_timing_export",
        )
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(f"Complaint mileage evidence could not be displayed: {exc}")

    st.caption(
        "Maintenance assessment is informational, not an inspection, diagnosis, "
        "repair estimate, failure prediction or warranty statement."
    )

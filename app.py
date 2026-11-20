"""FleetIQ: NHTSA commercial vehicle complaint comparison dashboard.

Data is prepared by refresh_data.py and committed to data/ by GitHub Actions.
Raw complaint counts are not vehicle failure or reliability rates.
"""

from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="FleetIQ | Fleet Vehicle Comparisons", page_icon="🚐", layout="wide")
DATA_DIR = Path(__file__).resolve().parent / "data"


@st.cache_data(show_spinner=False)
def load_data(summary_mtime, complaints_mtime):
    summary = pd.read_csv(DATA_DIR / "summary.csv")
    complaints = pd.read_csv(
        DATA_DIR / "complaints.csv", dtype={"odi_number": "string"}
    )
    required_summary = {
        "vehicle", "vehicle_class", "model_year", "complaint_count", "component_records"
    }
    required_complaints = {
        "odi_number", "vehicle", "vehicle_class", "model_year", "component",
        "date_received", "mileage", "crash", "fire", "description"
    }
    if missing := required_summary - set(summary.columns):
        raise ValueError(f"summary.csv is missing columns: {', '.join(sorted(missing))}")
    if missing := required_complaints - set(complaints.columns):
        raise ValueError(f"complaints.csv is missing columns: {', '.join(sorted(missing))}")
    for frame in (summary, complaints):
        frame["model_year"] = pd.to_numeric(frame["model_year"], errors="coerce")
        frame["vehicle"] = frame["vehicle"].fillna("Unknown")
        frame["vehicle_class"] = frame["vehicle_class"].fillna("Unknown")
    summary["complaint_count"] = pd.to_numeric(summary["complaint_count"], errors="coerce")
    summary["component_records"] = pd.to_numeric(summary["component_records"], errors="coerce")
    complaints["mileage"] = pd.to_numeric(complaints["mileage"], errors="coerce")
    complaints["component"] = complaints["component"].fillna("UNKNOWN OR OTHER")
    complaints["odi_number"] = complaints["odi_number"].astype("string")
    complaints["received_date"] = pd.to_datetime(
        complaints["date_received"].astype("string"), format="%Y%m%d", errors="coerce"
    )
    return summary, complaints


st.title("🚐 FleetIQ")
st.subheader("Cargo Van & Commercial Truck Complaint Intelligence")
st.caption(
    "Source: NHTSA consumer complaints. Counts describe reported complaints, "
    "not failure rates or reliability scores. Truck chassis are not necessarily box-bodied vehicles."
)

summary_path = DATA_DIR / "summary.csv"
complaints_path = DATA_DIR / "complaints.csv"
if not summary_path.is_file() or not complaints_path.is_file():
    st.error("FleetIQ datasets were not found. Run the GitHub Actions refresh first so data/summary.csv and data/complaints.csv exist.")
    st.stop()

try:
    summary, complaints = load_data(
        summary_path.stat().st_mtime_ns, complaints_path.stat().st_mtime_ns
    )
except (OSError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Unable to read FleetIQ datasets: {exc}")
    st.stop()

if summary.empty or complaints.empty:
    st.warning("The downloaded datasets are empty.")
    st.stop()

classes = sorted(summary["vehicle_class"].dropna().unique().tolist())
years = sorted(summary["model_year"].dropna().astype(int).unique().tolist())

st.sidebar.header("Comparison filters")
default_classes = [
    name for name in ["Full-size cargo van", "Compact cargo van", "Electric cargo van"]
    if name in classes
]
selected_classes = st.sidebar.multiselect(
    "Vehicle categories", options=classes, default=default_classes or classes
)

class_filtered = summary[summary["vehicle_class"].isin(selected_classes)]
vehicle_options = sorted(class_filtered["vehicle"].unique().tolist())
priority = ["Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express"]
default_vehicles = [x for x in priority if x in vehicle_options][:4]
if not default_vehicles:
    default_vehicles = vehicle_options[:4]
selected_vehicles = st.sidebar.multiselect(
    "Compare vehicle platforms", vehicle_options, default=default_vehicles
)
default_start = 2018 if 2018 in years else years[0]
default_end = 2023 if 2023 in years else years[-1]
start_year, end_year = st.sidebar.select_slider(
    "Model-year range", options=years, value=(default_start, default_end)
)

if not selected_classes or not selected_vehicles:
    st.info("Select at least one category and one vehicle platform to compare.")
    st.stop()

summary_filtered = summary.loc[
    summary["vehicle_class"].isin(selected_classes)
    & summary["vehicle"].isin(selected_vehicles)
    & summary["model_year"].between(start_year, end_year)
].copy()
complaints_filtered = complaints.loc[
    complaints["vehicle_class"].isin(selected_classes)
    & complaints["vehicle"].isin(selected_vehicles)
    & complaints["model_year"].between(start_year, end_year)
].copy()

if summary_filtered.empty:
    st.warning("No complaint records match these selections. An absent row is not proof of zero complaints.")
    st.stop()

# If one ODI number has multiple component rows, count it only once per vehicle/year.
unique_keys = ["vehicle", "model_year", "odi_number"]
complaint_level = complaints_filtered.drop_duplicates(subset=unique_keys)

# Check mileage once per unique complaint, not once per component row.
# A complaint's component records can repeat the same odometer value.
mileage_by_complaint = (
    complaints_filtered.assign(
        valid_mileage=complaints_filtered["mileage"].where(
            complaints_filtered["mileage"] > 0
        )
    )
    .groupby(["vehicle", "model_year", "odi_number"], as_index=False)
    .agg(reported_mileage=("valid_mileage", "median"))
)
mileage_reported = int(mileage_by_complaint["reported_mileage"].notna().sum())
mileage_total = len(mileage_by_complaint)
mileage_coverage = 100 * mileage_reported / mileage_total if mileage_total else 0

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Unique complaints", f"{complaint_level['odi_number'].nunique():,}")
metric2.metric("Complaint-component rows", f"{len(complaints_filtered):,}")
metric3.metric("Selected platforms with records", f"{summary_filtered['vehicle'].nunique():,}")
metric4.metric("Model years with records", f"{summary_filtered['model_year'].nunique():,}")

st.caption(
    f"Mileage availability: {mileage_reported:,} of {mileage_total:,} unique complaints "
    f"({mileage_coverage:.1f}%) have usable reported mileage. "
    "Unreported or nonpositive mileage is excluded from mileage calculations."
)

st.info(
    "Comparisons are **complaint volumes only**. Higher counts may reflect more vehicles "
    "sold, more years on the road, or greater mileage—not necessarily lower reliability. "
    "Missing model-year rows are left blank, not treated as zero."
)

overview_tab, components_tab, severity_tab, records_tab = st.tabs(
    ["Compare vehicles", "Problem categories", "Reported incidents", "Complaint records"]
)

with overview_tab:
    st.markdown("#### Total complaints in selected model years")
    totals = (
        summary_filtered.groupby(["vehicle", "vehicle_class"], as_index=False)
        .agg(
            unique_complaints=("complaint_count", "sum"),
            component_records=("component_records", "sum"),
            model_years_with_records=("model_year", "nunique"),
        )
        .sort_values("unique_complaints", ascending=False)
    )
    # Complaint IDs across different years/platforms should not be summed twice.
    verified_totals = (
        complaint_level.groupby("vehicle")["odi_number"].nunique()
    )
    totals["unique_complaints"] = totals["vehicle"].map(verified_totals).fillna(0).astype(int)
    st.dataframe(
        totals.rename(columns={
            "vehicle": "Vehicle", "vehicle_class": "Category",
            "unique_complaints": "Unique complaints",
            "component_records": "Component records",
            "model_years_with_records": "Years with reported complaints",
        }),
        hide_index=True,
        use_container_width=True,
    )
    st.bar_chart(totals.set_index("vehicle")["unique_complaints"], x_label="Vehicle platform", y_label="Unique complaints")

    st.markdown("#### Compare the same model years")
    trend = summary_filtered.pivot(
        index="model_year", columns="vehicle", values="complaint_count"
    ).sort_index()
    # Treat model years as categories to avoid axis labels like 2,016.
    trend_chart = trend.copy()
    trend_chart.index = trend_chart.index.astype(int).astype(str)
    trend_chart.index.name = "Model year"
    st.line_chart(trend_chart, x_label="Model year", y_label="Unique complaints")

    # Preserve NaN in the underlying data; only display an em dash.
    trend_display = trend.rename_axis("Model year").style.format(
        formatter="{:.0f}", na_rep="—"
    )
    st.dataframe(trend_display, use_container_width=True)
    st.caption(
        "Blank cells mean the pipeline has no matched complaint records for that platform/year. "
        "They must not be interpreted as zero until coverage is verified."
    )

with components_tab:
    st.markdown("#### Most frequently reported components")
    components = (
        complaints_filtered[["vehicle", "odi_number", "component"]]
        .drop_duplicates()
        .groupby(["vehicle", "component"], as_index=False)["odi_number"]
        .nunique()
        .rename(columns={"odi_number": "complaints"})
    )
    if components.empty:
        st.info("No complaint component records match the filters.")
    else:
        component_totals = (
            components.groupby("component")["complaints"]
            .sum().sort_values(ascending=False)
        )
        top_components = component_totals.head(12).index.tolist()
        chart_data = (
            components[components["component"].isin(top_components)]
            .pivot(index="component", columns="vehicle", values="complaints")
            .fillna(0)
            .reindex(top_components)
        )
        st.bar_chart(chart_data, horizontal=True, x_label="Complaint reports mentioning component", y_label="Component")
        st.dataframe(
            components.sort_values("complaints", ascending=False).rename(columns={
                "vehicle": "Vehicle", "component": "NHTSA component", "complaints": "Unique complaints"
            }),
            hide_index=True,
            use_container_width=True,
        )
        st.caption("A complaint can mention multiple components; component totals cannot be added to obtain unique complaints.")

with severity_tab:
    st.markdown("#### Reported crash, fire, and mileage indicators")
    # Flags are consolidated across component records for each ODI ID.
    incident_rows = complaints_filtered.copy()
    incident_rows["crash_flag"] = incident_rows["crash"].astype("string").str.upper().eq("Y")
    incident_rows["fire_flag"] = incident_rows["fire"].astype("string").str.upper().eq("Y")
    incidents = (
        incident_rows.groupby(["vehicle", "odi_number"], as_index=False)
        .agg(
            crash_reported=("crash_flag", "max"),
            fire_reported=("fire_flag", "max"),
            reported_mileage=("mileage", "median"),
        )
    )
    incidents["valid_mileage"] = incidents["reported_mileage"].where(incidents["reported_mileage"] > 0)
    incidents_summary = (
        incidents.groupby("vehicle", as_index=False)
        .agg(
            complaints=("odi_number", "nunique"),
            crash_reports=("crash_reported", "sum"),
            fire_reports=("fire_reported", "sum"),
            median_reported_miles=("valid_mileage", "median"),
            mileage_samples=("valid_mileage", "count"),
        )
        .sort_values("complaints", ascending=False)
    )
    incidents_summary["mileage_coverage_pct"] = (
        100 * incidents_summary["mileage_samples"] / incidents_summary["complaints"]
    ).round(1)
    st.dataframe(
        incidents_summary.rename(columns={
            "vehicle": "Vehicle", "complaints": "Complaints",
            "crash_reports": "Crash-flagged complaints", "fire_reports": "Fire-flagged complaints",
            "median_reported_miles": "Median mileage reported", "mileage_samples": "Mileage observations",
            "mileage_coverage_pct": "Mileage coverage (%)",
        }),
        hide_index=True, use_container_width=True,
    )
    st.caption(
        "Crash/fire flags reflect consumer reports, not confirmed causation. "
        "Mileage is missing for many records. Mileage coverage is the percentage of unique complaints "
        "with a positive reported mileage. Medians only describe that subset and should not be "
        "interpreted as expected vehicle failure mileage."
    )

with records_tab:
    st.markdown("#### Underlying NHTSA complaint records")
    available_components = sorted(complaints_filtered["component"].dropna().unique().tolist())
    chosen_components = st.multiselect(
        "Filter by component", available_components, default=[],
        help="Leave empty to view all components."
    )
    records = complaints_filtered.copy()
    if chosen_components:
        records = records[records["component"].isin(chosen_components)]
    records = records.sort_values("received_date", ascending=False)
    display_cols = [
        "odi_number", "vehicle", "model_year", "make", "model", "component",
        "received_date", "mileage", "crash", "fire", "description"
    ]
    display_cols = [col for col in display_cols if col in records.columns]
    st.caption(
        f"{records['odi_number'].nunique():,} unique complaints across "
        f"{len(records):,} component rows"
    )
    st.dataframe(records[display_cols], hide_index=True, use_container_width=True)
    st.download_button(
        "Download filtered complaint records (CSV)",
        data=records[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="fleetiq_filtered_complaints.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "FleetIQ uses the NHTSA bulk complaint archive processed by refresh_data.py. "
    "Recalls are not displayed because this data pipeline has not yet collected a verified recall dataset. "
    "Sales/registration denominators will be needed before any complaint-rate or reliability ranking is appropriate."
)

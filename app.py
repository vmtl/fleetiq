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
metric2.metric("Component rows", f"{len(complaints_filtered):,}")
metric3.metric("Platforms", f"{summary_filtered['vehicle'].nunique():,}")
metric4.metric("Model years", f"{summary_filtered['model_year'].nunique():,}")

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

overview_tab, components_tab, detail_tab, severity_tab, records_tab, sales_tab = st.tabs(
    ["Compare vehicles", "Problem categories", "Component deep dive", "Reported incidents", "Complaint records", "Sales data"]
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
            "model_years_with_records": "Years with reports",
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

    # Format a display-only copy so missing values show as a dash, not None.
    # Keep true nulls in the underlying trend table and line chart.
    trend_display = trend.copy()
    trend_display.index = trend_display.index.astype(int).astype(str)
    trend_display.index.name = "Model year"
    trend_display = trend_display.apply(
        lambda col: col.map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
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

# Normalize to a broad system while retaining the original NHTSA subcomponent.
# A complaint can mention multiple system categories; never sum category counts
# as if they were distinct complaints.
def component_system(component):
    term = str(component).upper().strip()
    rules = [
        ("Powertrain / transmission", ("POWER TRAIN", "TRANSMISSION")),
        ("Engine / cooling", ("ENGINE", "COOLING")),
        ("Fuel system", ("FUEL", "PROPULSION")),
        ("Electrical / electronics", ("ELECTRICAL", "ELECTRONIC", "SOFTWARE")),
        ("Brakes", ("BRAKE",)),
        ("Steering", ("STEERING",)),
        ("Suspension", ("SUSPENSION",)),
        ("Wheels / tires", ("WHEEL", "TIRE")),
        ("Body / structure", ("STRUCTURE", "BODY", "DOOR", "LATCH")),
        ("Safety / driver assistance", (
            "AIR BAG", "SEAT BELT", "FORWARD COLLISION", "BACK OVER",
            "LANE DEPARTURE", "BLIND SPOT", "CRUISE CONTROL", "VEHICLE SPEED CONTROL",
        )),
        ("Visibility / lighting", ("VISIBILITY", "WIPER", "EXTERIOR LIGHTING")),
        ("Interior / comfort", ("SEAT", "EQUIPMENT", "HVAC")),
    ]
    for label, terms in rules:
        if any(keyword in term for keyword in terms):
            return label
    return "Other / unspecified"


with detail_tab:
    st.markdown("#### Component-level complaint investigation")
    st.caption("Identify recurring systems, affected model years, available odometer readings, and original NHTSA narratives.")
    detail_vehicle = st.selectbox("Vehicle platform", selected_vehicles, key="detail_vehicle")
    detail_rows = complaints_filtered.loc[
        complaints_filtered["vehicle"].eq(detail_vehicle)
    ].copy()
    detail_rows["system"] = detail_rows["component"].map(component_system)

    # One ODI ID per vehicle-model-year-system, regardless of component rows.
    per_system = detail_rows.drop_duplicates(
        ["odi_number", "model_year", "system"]
    ).copy()
    totals_by_system = (
        per_system.groupby("system")["odi_number"]
        .nunique().sort_values(ascending=False)
    )
    selected_system = st.selectbox(
        "Problem system", totals_by_system.index.tolist(), key="detail_system"
    )
    system_rows = detail_rows.loc[detail_rows["system"].eq(selected_system)].copy()
    system_odi = system_rows.drop_duplicates("odi_number")
    system_complaints = int(system_odi["odi_number"].nunique())

    # Consolidate mileage by ODI to prevent duplicate components overweighting
    # the same incident; only positive numeric readings are considered usable.
    odometer = (
        system_rows.assign(valid_miles=system_rows["mileage"].where(system_rows["mileage"] > 0))
        .groupby("odi_number")["valid_miles"].median()
    )
    available = int(odometer.notna().sum())
    coverage_pct = 100 * available / system_complaints if system_complaints else 0
    all_odi = int(detail_rows["odi_number"].nunique())
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("System complaints", f"{system_complaints:,}")
    x2.metric("Of vehicle complaints", f"{system_complaints / all_odi:.1%}" if all_odi else "—")
    x3.metric("Mileage coverage", f"{available:,}/{system_complaints:,} ({coverage_pct:.0f}%)")
    x4.metric("Median reported miles", f"{odometer.median():,.0f}" if available else "—")
    st.caption(
        "A complaint may involve multiple systems. Reported mileage is voluntary and "
        "does not estimate the mileage at which a vehicle will fail."
    )

    st.markdown("##### Compare problem systems")
    # Horizontal Streamlit bar charts render labels more clearly than a very
    # long list of raw NHTSA component strings.
    overview_systems = totals_by_system.head(15)
    st.bar_chart(
        overview_systems,
        horizontal=True,
        x_label="Unique complaints mentioning system",
        y_label="Problem system",
    )

    st.markdown(f"##### {selected_system}: complaints by model year")
    year_counts = (
        system_rows.drop_duplicates(["model_year", "odi_number"])
        .groupby("model_year")["odi_number"].nunique()
        .sort_index()
    )
    year_frame = year_counts.rename("Unique complaints").to_frame()
    year_frame.index = year_frame.index.astype(int).astype(str)
    year_frame.index.name = "Model year"
    st.bar_chart(year_frame, x_label="Model year", y_label="Unique complaints")
    st.caption("Only model years with matched complaint records appear. Missing years are not verified zeros.")

    st.markdown("##### Specific NHTSA components in this system")
    subcomponent = (
        system_rows.drop_duplicates(["component", "odi_number"])
        .groupby("component")["odi_number"].nunique()
        .sort_values(ascending=False)
    )
    subtable = subcomponent.rename("Unique complaints").reset_index().rename(
        columns={"component": "NHTSA component"}
    )
    st.dataframe(subtable, hide_index=True, use_container_width=True)

    st.markdown("##### Review original complaint descriptions")
    selected_subcomponent = st.selectbox(
        "Filter to a specific NHTSA component (optional)",
        ["All components in selected system"] + subcomponent.index.tolist(),
        key="detail_subcomponent",
    )
    evidence = system_rows
    if selected_subcomponent != "All components in selected system":
        evidence = evidence.loc[evidence["component"].eq(selected_subcomponent)]
    evidence = evidence.drop_duplicates("odi_number").sort_values("received_date", ascending=False)
    evidence_cols = [
        "odi_number", "model_year", "received_date", "mileage",
        "component", "description",
    ]
    st.caption(f"Showing {len(evidence):,} distinct complaint IDs. Expand or scroll rows to read descriptions.")
    st.dataframe(evidence[evidence_cols], hide_index=True, use_container_width=True)
    st.download_button(
        "Download selected complaint evidence (CSV)",
        data=evidence[evidence_cols].to_csv(index=False).encode("utf-8"),
        file_name="fleetiq_component_evidence.csv",
        mime="text/csv",
        key="component_evidence_download",
    )
    st.caption(
        "NHTSA does not supply standardized repair cost per complaint. A dollar amount "
        "in narrative text may be an estimate, purchase price, or unrelated expense."
    )

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

with sales_tab:
    st.markdown("#### U.S. vehicle sales reference data")
    st.caption(
        "This is a separately maintained source table. Published U.S. sales are usually "
        "calendar-year totals, whereas NHTSA complaints use vehicle model years. "
        "These are different cohorts and must not be divided to claim a reliability rate."
    )
    sales_path = DATA_DIR / "sales.csv"
    required_sales = {
        "vehicle", "calendar_year", "us_sales", "source_name", "source_url", "notes"
    }
    if not sales_path.exists():
        st.info("Optional sales dataset not installed. Add data/sales.csv to your repository when you have verified annual sales figures.")
        st.code(
            "vehicle,calendar_year,us_sales,source_name,source_url,notes\n"
            "Ford Transit,2025,161797,Ford Motor Company,"
            "https://www.fromtheroad.ford.com/us/en/articles/2026/ford-2025-full-year-us-sales-results,"
            "US calendar-year sales; includes Transit configurations; not model-year cohort sales",
            language="text",
        )
    else:
        try:
            sales = pd.read_csv(sales_path)
            if missing := required_sales - set(sales.columns):
                st.error("data/sales.csv is missing: " + ", ".join(sorted(missing)))
            else:
                sales["calendar_year"] = pd.to_numeric(sales["calendar_year"], errors="coerce")
                sales["us_sales"] = pd.to_numeric(sales["us_sales"], errors="coerce")
                sales = sales.loc[sales["us_sales"].gt(0) & sales["calendar_year"].notna()].copy()
                subset = sales.loc[sales["vehicle"].isin(selected_vehicles)].copy()
                if subset.empty:
                    st.info("No verified sales records yet for the selected vehicle platforms.")
                else:
                    st.dataframe(
                        subset.sort_values(["vehicle", "calendar_year"]),
                        hide_index=True, use_container_width=True,
                        column_config={"source_url": st.column_config.LinkColumn("Source")},
                    )
                st.caption(
                    "Sales figures may combine cargo, passenger, electric, chassis, or other variants; "
                    "verify manufacturer definitions before comparing. No complaint-rate calculation "
                    "is performed using calendar-year sales."
                )
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"Unable to load optional sales dataset: {exc}")

st.divider()
st.caption(
    "FleetIQ uses the NHTSA bulk complaint archive processed by refresh_data.py. "
    "Recalls are not displayed because this data pipeline has not yet collected a verified recall dataset. "
    "Sales/registration denominators will be needed before any complaint-rate or reliability ranking is appropriate."
)

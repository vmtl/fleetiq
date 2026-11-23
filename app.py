"""FleetIQ: NHTSA commercial vehicle complaint comparison dashboard.

Data is prepared by refresh_data.py and committed to data/ by GitHub Actions.
Raw complaint counts are not vehicle failure or reliability rates.
"""

from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as st_components
from van_cutaway import render_cutaway, SYSTEMS
from repair_intelligence import render_repair_cost_tab
from maintenance_intelligence import render_maintenance_tab
from recall_intelligence import render_recall_tab
from ownership_intelligence import render_ownership_tab
from vehicle_report import render_vehicle_report
from fleet_workspace import render_fleet_workspace
from business_economics import render_profitability, render_prediction_readiness
from age_comparison import render_age_matched_comparison


st.set_page_config(page_title="FleetIQ | Fleet Vehicle Comparisons", page_icon="🚐", layout="wide")
DATA_DIR = Path(__file__).resolve().parent / "data"

# Shared FleetIQ chart palette; chart styling never changes source data.
NEON_PALETTE = ["#00F5D4", "#E879F9", "#00BFFF", "#FBBF24",
                "#FF5277", "#B4F000", "#A78BFA", "#FF8A4C"]


def neon_style(fig):
    """Use one readable dark neon theme for every FleetIQ chart."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(7,14,30,0)",
        plot_bgcolor="rgba(19,34,56,.23)",
        font=dict(color="#E8F3FF", family="Arial, sans-serif", size=13),
        colorway=NEON_PALETTE,
        margin=dict(l=24, r=24, t=25, b=30),
        legend=dict(bgcolor="rgba(8,14,29,0)", font=dict(color="#D7E9FF")),
        hoverlabel=dict(bgcolor="#17243B", font_color="#F5FBFF"),
    )
    fig.update_xaxes(
        showline=False, zeroline=False,
        gridcolor="rgba(113,142,178,0.09)",
        tickfont=dict(color="#C6D7EB"),
        title_font=dict(color="#DCEAFB"),
    )
    fig.update_yaxes(
        showline=False, zeroline=False,
        gridcolor="rgba(113,142,178,0.10)",
        tickfont=dict(color="#C6D7EB"),
        title_font=dict(color="#DCEAFB"),
    )
    return fig


def neon_bar(data, horizontal=False, x_label=None, y_label=None):
    """Show existing series or wide tables without changing their counts."""
    frame = data.to_frame() if isinstance(data, pd.Series) else data.copy()
    fig = go.Figure()
    for index, column in enumerate(frame.columns):
        color = NEON_PALETTE[index % len(NEON_PALETTE)]
        values = pd.to_numeric(frame[column], errors="coerce")
        categories = [str(item) for item in frame.index]
        trace_args = dict(
            name=str(column), marker_color=color,
            marker_line=dict(color=color, width=0.5), opacity=0.76,
        )
        if horizontal:
            fig.add_trace(go.Bar(
                x=values, y=categories, orientation="h", **trace_args
            ))
        else:
            fig.add_trace(go.Bar(x=categories, y=values, **trace_args))
    neon_style(fig)
    fig.update_layout(
        barmode="group", showlegend=len(frame.columns) > 1,
        xaxis_title=x_label, yaxis_title=y_label,
    )
    if horizontal:
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=max(330, min(760, 35 * len(frame.index) + 110)))
    st.plotly_chart(fig, use_container_width=True)


def neon_line(data, x_label=None, y_label=None):
    """Show time series with neon accents; missing values remain gaps."""
    frame = data.to_frame() if isinstance(data, pd.Series) else data.copy()
    fig = go.Figure()
    labels = [str(item) for item in frame.index]
    for index, column in enumerate(frame.columns):
        color = NEON_PALETTE[index % len(NEON_PALETTE)]
        values = pd.to_numeric(frame[column], errors="coerce")
        fig.add_trace(go.Scatter(
            x=labels, y=values, mode="lines", name=str(column),
            line=dict(color=color, width=9), opacity=0.09,
            hoverinfo="skip", showlegend=False, connectgaps=False,
        ))
        fig.add_trace(go.Scatter(
            x=labels, y=values, mode="lines+markers", name=str(column),
            line=dict(color=color, width=2.5),
            marker=dict(size=7, color=color), connectgaps=False,
        ))
    neon_style(fig)
    fig.update_layout(
        xaxis_title=x_label, yaxis_title=y_label,
        hovermode="x unified", showlegend=len(frame.columns) > 1,
    )
    st.plotly_chart(fig, use_container_width=True)




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


st.markdown("""
<style>
[data-testid="stAppViewContainer"] {background: radial-gradient(ellipse at 80% 0%, #192b48, #0b1425 44%, #080d1a);}
[data-testid="stSidebar"] {background: rgba(10,21,39,.94);}
[data-testid="stMetric"] {
 padding:14px 17px; border:1px solid rgba(115,211,249,.18);
 border-radius:15px; background:linear-gradient(135deg,rgba(32,64,90,.37),rgba(15,25,48,.28));
 backdrop-filter:blur(12px); box-shadow:0 6px 24px rgba(0,0,0,.14);
}
[data-testid="stPlotlyChart"] {
 background:linear-gradient(145deg,rgba(48,80,117,.20),rgba(12,24,48,.21));
 border:1px solid rgba(111,203,241,.19); border-radius:18px;
 padding:8px; backdrop-filter:blur(14px); box-shadow:0 8px 30px rgba(0,0,0,.12);
}
/* Let the complete 14-tab workspace remain navigable on smaller screens. */
[data-testid="stTabs"] [role="tablist"] {
  overflow-x:auto;
  max-width:100%;
  scrollbar-width:thin;
  scroll-snap-type:x proximity;
}
[data-testid="stTabs"] [role="tab"] {
  white-space:nowrap;
  flex-shrink:0;
  scroll-snap-align:start;
}
@media(max-width:760px) {
  .block-container {padding:0.8rem 0.7rem 3rem;}
  [data-testid="stMetric"] {padding:9px 10px;}
  [data-testid="stPlotlyChart"] {padding:2px;}
  [data-testid="stDataFrame"] {max-width:100%;overflow-x:auto;}
  h1 {font-size:1.65rem!important;}
}
</style>
""", unsafe_allow_html=True)

st.title("🚐 FleetIQ")
st.subheader("Commercial Vehicle Research & Fleet Planning")
st.caption(
    "Explore documented issues, OEM maintenance, recall campaigns, vehicle reports, " 
    "and illustrative business costs. NHTSA counts describe reported complaints, "
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

hotspots_tab, overview_tab, components_tab, detail_tab, intelligence_tab, severity_tab, records_tab, sales_tab, repair_tab, maintenance_tab, recalls_tab, ownership_tab, report_tab, fleet_tab = st.tabs(
    ["Failure Hotspots", "Compare vehicles", "Problem categories", "Component deep dive", "Problem Intelligence", "Reported incidents", "Complaint records", "Sales data", "Repair costs", "Maintenance timing", "Safety recalls", "Ownership economics", "Vehicle report", "Fleet workspace"]
)

with overview_tab:
    render_age_matched_comparison(complaints, NEON_PALETTE)
    st.divider()
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
    neon_bar(totals.set_index("vehicle")["unique_complaints"], x_label="Vehicle platform", y_label="Unique complaints")

    st.markdown("#### Compare the same model years")
    trend = summary_filtered.pivot(
        index="model_year", columns="vehicle", values="complaint_count"
    ).sort_index()
    # Treat model years as categories to avoid axis labels like 2,016.
    trend_chart = trend.copy()
    trend_chart.index = trend_chart.index.astype(int).astype(str)
    trend_chart.index.name = "Model year"
    neon_line(trend_chart, x_label="Model year", y_label="Unique complaints")

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
        neon_bar(chart_data, horizontal=True, x_label="Complaint reports mentioning component", y_label="Component")
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
    neon_bar(
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
    neon_bar(year_frame, x_label="Model year", y_label="Unique complaints")
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

# The enriched dataset is produced by analyze_complaints.py, not by app.py.
# Keep the original NHTSA complaint archive unchanged.
@st.cache_data(show_spinner=False)
def load_problem_analysis(file_mtime):
    analysis = pd.read_csv(
        DATA_DIR / "problem_analysis.csv",
        dtype={"odi_number": "string"},
        low_memory=False,
    )
    mandatory = {
        "odi_number", "vehicle", "model_year", "primary_reported_issue",
        "reported_issues", "issue_detection", "approx_vehicle_age_years",
        "age_band", "description",
    }
    missing = mandatory - set(analysis.columns)
    if missing:
        raise ValueError("problem_analysis.csv missing: " + ", ".join(sorted(missing)))
    analysis["model_year"] = pd.to_numeric(analysis["model_year"], errors="coerce")
    analysis["approx_vehicle_age_years"] = pd.to_numeric(
        analysis["approx_vehicle_age_years"], errors="coerce"
    )
    analysis["odi_number"] = analysis["odi_number"].astype("string")
    analysis["age_band"] = analysis["age_band"].fillna("Unknown")
    analysis["primary_reported_issue"] = analysis["primary_reported_issue"].fillna(
        "Unspecified / manual review"
    )
    analysis["reported_issues"] = analysis["reported_issues"].fillna(
        "Unspecified / manual review"
    )
    if "date_received" in analysis.columns:
        analysis["date_received"] = pd.to_datetime(analysis["date_received"], errors="coerce")
    return analysis


with intelligence_tab:
    st.markdown("#### Problem Intelligence — reported issues by vehicle age")
    st.caption(
        "Issue labels are preliminary keyword-based interpretations of owner narratives, "
        "not verified repairs or mechanical diagnoses. Vehicle age is approximated "
        "as complaint receipt year minus model year."
    )
    analysis_path = DATA_DIR / "problem_analysis.csv"
    if not analysis_path.is_file():
        st.warning(
            "Problem Intelligence requires data/problem_analysis.csv. "
            "Run Refresh FleetIQ Data in GitHub Actions to generate it."
        )
    else:
        try:
            analysis = load_problem_analysis(analysis_path.stat().st_mtime_ns)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"Unable to load problem analysis: {exc}")
        else:
            # Honor the sidebar vehicle and model-year filters.
            analysis = analysis.loc[
                analysis["vehicle"].isin(selected_vehicles)
                & analysis["model_year"].between(start_year, end_year)
            ].drop_duplicates(subset=["odi_number"]).copy()
            if analysis.empty:
                st.info("No analyzed complaints match the selected vehicles and model years.")
            else:
                chosen_vehicle = st.selectbox(
                    "Investigate vehicle", sorted(analysis["vehicle"].unique()),
                    key="intelligence_vehicle"
                )
                vehicle_data = analysis.loc[
                    analysis["vehicle"].eq(chosen_vehicle)
                ].copy()
                selected_years = sorted(vehicle_data["model_year"].dropna().astype(int).unique().tolist())
                chosen_years = st.multiselect(
                    "Model years to investigate (leave empty for all selected years)",
                    selected_years, default=[], key="intelligence_years"
                )
                if chosen_years:
                    vehicle_data = vehicle_data.loc[
                        vehicle_data["model_year"].isin(chosen_years)
                    ].copy()
                complaint_total = int(vehicle_data["odi_number"].nunique())
                age_count = int(vehicle_data["approx_vehicle_age_years"].notna().sum())
                # Count only specifically identified symptoms as classified.
                # Generic dashboard warnings are not mechanical diagnoses.
                if "specific_issue_detected" in vehicle_data.columns:
                    specific_mask = (
                        vehicle_data["specific_issue_detected"]
                        .astype("string").str.lower().eq("true").fillna(False)
                    )
                else:
                    specific_mask = (
                        vehicle_data["classification_status"]
                        .fillna("").eq("Specific symptom keyword match (unverified)")
                        if "classification_status" in vehicle_data.columns
                        else vehicle_data["issue_detection"].fillna("")
                        .str.contains("Keyword match", case=False, regex=False)
                    )
                specific_count = int(specific_mask.sum())
                generic_count = int((
                    vehicle_data.get(
                        "classification_status",
                        pd.Series("", index=vehicle_data.index),
                    ) == "Generic warning/diagnostic only"
                ).sum())
                unclassified_count = complaint_total - specific_count - generic_count
                coverage_pct = 100 * specific_count / complaint_total if complaint_total else 0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Complaints", f"{complaint_total:,}")
                m2.metric("Age available", f"{age_count:,}/{complaint_total:,}")
                m3.metric("Specific issues", f"{specific_count:,} ({coverage_pct:.1f}%)")
                m4.metric("Needs review", f"{unclassified_count:,}")
                st.caption(
                    f"Generic warning/diagnostic only: {generic_count:,}. "
                    "These are not counted as specific mechanical issues. "
                    "Issue labels are unverified narrative matches; some complaints mention multiple issues."
                )

                st.markdown("##### Classification coverage")
                breakdown = pd.DataFrame({
                    "Classification": [
                        "Specific symptom identified (unverified)",
                        "Generic warning/diagnostic only",
                        "Unspecified / manual review",
                    ],
                    "Complaints": [specific_count, generic_count, unclassified_count],
                })
                breakdown["Share (%)"] = (
                    (100 * breakdown["Complaints"] / complaint_total).round(1)
                    if complaint_total else 0.0
                )
                st.dataframe(breakdown, hide_index=True, use_container_width=True)

                if "repair_evidence_status" in vehicle_data.columns:
                    st.markdown("##### Repair evidence mentioned in narratives")
                    repair_counts = (
                        vehicle_data["repair_evidence_status"]
                        .fillna("Not classified")
                        .value_counts()
                        .rename_axis("Narrative evidence")
                        .reset_index(name="Complaints")
                    )
                    st.dataframe(repair_counts, hide_index=True, use_container_width=True)
                    st.caption(
                        "Repair mentions are automated text indicators, not verified invoices, "
                        "completed services, or confirmed failed parts."
                    )

                # Split multi-issue text into complaint-issue links, deduplicated by ODI.
                issue_links = vehicle_data[[
                    "odi_number", "model_year", "approx_vehicle_age_years", "age_band", "reported_issues"
                ]].copy()
                issue_links["issue"] = issue_links["reported_issues"].str.split(" | ", regex=False)
                issue_links = issue_links.explode("issue")
                issue_links["issue"] = issue_links["issue"].astype(str).str.strip()
                issue_links = issue_links.loc[issue_links["issue"].ne("")]
                issue_links = issue_links.drop_duplicates(["odi_number", "issue"])

                issue_counts = (
                    issue_links.loc[~issue_links["issue"].isin([
                        "Unspecified / manual review", "Sensor / warning / diagnostic"
                    ])]
                    .groupby("issue")["odi_number"].nunique()
                    .sort_values(ascending=False)
                )
                st.markdown("##### Most frequently reported specific issues")
                if issue_counts.empty:
                    st.info("No specific issues were detected in these records.")
                else:
                    neon_bar(
                        issue_counts.head(15), horizontal=True,
                        x_label="Unique complaints mentioning issue",
                        y_label="Reported issue"
                    )
                    st.dataframe(
                        issue_counts.rename("Complaint IDs").reset_index().rename(
                            columns={"issue": "Reported issue"}
                        ), hide_index=True, use_container_width=True
                    )

                st.markdown("##### Complaints by approximate vehicle age")
                age_order = ["0–1 years", "2–3 years", "4–5 years", "6–8 years", "9+ years", "Unknown"]
                age_counts = (
                    vehicle_data.groupby("age_band")["odi_number"].nunique()
                    .reindex(age_order, fill_value=0)
                    .rename("Unique complaints")
                )
                neon_bar(age_counts, x_label="Approximate age at complaint receipt", y_label="Unique complaints")
                st.caption(
                    "These counts describe when NHTSA received reports, not the exact age "
                    "when a fault began. They are not age-specific failure rates: different "
                    "vehicle cohorts have had different amounts of time to accumulate complaints."
                )

                st.markdown("##### Investigate an issue")
                issue_options = issue_counts.index.tolist()
                for additional in ["Sensor / warning / diagnostic", "Unspecified / manual review"]:
                    if additional in issue_links["issue"].values:
                        issue_options.append(additional)
                if issue_options:
                    selected_issue = st.selectbox(
                        "Reported issue", issue_options, key="intelligence_issue"
                    )
                    relevant_ids = issue_links.loc[
                        issue_links["issue"].eq(selected_issue), "odi_number"
                    ].dropna().unique()
                    evidence = vehicle_data.loc[
                        vehicle_data["odi_number"].isin(relevant_ids)
                    ].copy()
                    issue_by_age = (
                        evidence.groupby("age_band")["odi_number"].nunique()
                        .reindex(age_order, fill_value=0)
                        .rename("Unique complaints")
                    )
                    neon_bar(
                        issue_by_age, x_label="Approximate age at report receipt",
                        y_label="Complaints mentioning issue"
                    )
                    st.caption(
                        f"{evidence['odi_number'].nunique():,} distinct complaints mention "
                        f"{selected_issue}. These are reported symptoms, not confirmed repair diagnoses."
                    )
                    evidence_cols = [
                        "odi_number", "model_year", "date_received",
                        "approx_vehicle_age_years", "age_band", "primary_reported_issue",
                        "reported_issues", "classification_status", "specific_issue_detected",
                        "repair_evidence_status", "repair_action", "repair_component",
                        "repair_evidence_excerpt", "nhtsa_components", "description",
                    ]
                    evidence_cols = [c for c in evidence_cols if c in evidence.columns]
                    if "date_received" in evidence:
                        evidence = evidence.sort_values("date_received", ascending=False)
                    st.dataframe(
                        evidence[evidence_cols], hide_index=True, use_container_width=True,
                    )
                    st.download_button(
                        "Download issue evidence (CSV)",
                        data=evidence[evidence_cols].to_csv(index=False).encode("utf-8"),
                        file_name="fleetiq_problem_intelligence_evidence.csv",
                        mime="text/csv", key="intelligence_download"
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
    st.markdown("##### Crash and fire indicators by vehicle")
    incident_chart = incidents_summary.set_index("vehicle")[
        ["crash_reports", "fire_reports"]
    ].rename(columns={
        "crash_reports": "Crash-flagged complaints",
        "fire_reports": "Fire-flagged complaints",
    })
    if incident_chart.empty or not incident_chart.to_numpy().any():
        st.info("No crash or fire indicators are reported in this selection.")
    else:
        neon_bar(
            incident_chart, x_label="Vehicle",
            y_label="Unique complaints with reported indicator",
        )
    st.caption(
        "A single complaint may report both a crash and a fire; bars may overlap. "
        "These are consumer-reported flags, not confirmed causal findings."
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
    st.markdown("##### Most frequently mentioned NHTSA components")
    record_components = (
        records[["odi_number", "component"]].drop_duplicates()
        .groupby("component")["odi_number"].nunique()
        .sort_values(ascending=False).head(12)
        .rename("Unique complaints")
    )
    if record_components.empty:
        st.info("No component reports match the current filters.")
    else:
        neon_bar(
            record_components, horizontal=True,
            x_label="Unique complaints mentioning component",
            y_label="NHTSA component",
        )
    st.caption(
        "Component categories can overlap within a complaint; do not add the "
        "bars together as unique complaints."
    )
    st.dataframe(records[display_cols], hide_index=True, use_container_width=True)
    st.download_button(
        "Download filtered complaint records (CSV)",
        data=records[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="fleetiq_filtered_complaints.csv",
        mime="text/csv",
    )

with sales_tab:
    st.markdown("#### Vehicle Sales Intelligence")
    st.caption(
        "Explore published U.S. calendar-year model-family sales. These figures "
        "are market context, not model-year vehicle populations or reliability rates."
    )
    sales_path = DATA_DIR / "sales_clean.csv"
    sales_required = {
        "vehicle", "calendar_year", "us_sales", "source_name", "source_url",
        "notes", "source_status", "quality_flags",
        "ready_for_full_year_comparison", "source_verification_status",
        "verified_for_comparison"
    }
    if not sales_path.is_file():
        st.warning("Cleaned sales data is missing. Run `python clean_sales.py`.")
    else:
        try:
            sales = pd.read_csv(sales_path)
            missing_columns = sales_required - set(sales.columns)
            if missing_columns:
                st.error(
                    "data/sales_clean.csv is missing required columns: "
                    + ", ".join(sorted(missing_columns))
                )
            else:

                sales["calendar_year"] = pd.to_numeric(
                    sales["calendar_year"], errors="coerce"
                ).astype("Int64")
                sales["us_sales"] = pd.to_numeric(
                    sales["us_sales"], errors="coerce"
                )
                # These are provisional source labels, NOT verification claims.
                labels = {
                    "source_reported_model_family": "Source-reported",
                    "previously_sourced_needs_revalidation": "Review needed",
                    "not_yet_verified": "Missing",
                }
                sales["Status"] = (
                    sales["source_status"].map(labels).fillna("Review needed")
                )
                verification_labels = {
                    "verified_manufacturer": "Verified",
                    "corrected_manufacturer": "Corrected & verified",
                    "corroborated_independent": "Independently corroborated",
                    "secondary_only": "Provisional",
                    "conflict_unresolved": "Unresolved",
                    "scope_mismatch": "Mixed scope",
                    "partial_year": "Partial year",
                }
                evidence_labels = sales["source_verification_status"].map(verification_labels)
                sales["Status"] = evidence_labels.fillna(sales["Status"])
                sales.loc[sales["us_sales"].isna(), "Status"] = "Missing"
                sales.loc[sales["us_sales"].eq(0), "Status"] = "Reported zero"
                sales["Source link"] = sales["source_url"].fillna("")
                sales["Source link"] = sales["Source link"].where(
                    sales["Source link"].str.startswith(("http://", "https://")), ""
                )
                # A calendar year is not complete before its end; require the
                # cleaner's eligibility flag as well when comparing full years.
                sales["is_complete_calendar_year"] = sales[
                    "is_complete_calendar_year"
                ].fillna(False).astype(bool) if "is_complete_calendar_year" in sales.columns else False
                sales["Full year"] = sales["is_complete_calendar_year"].map(
                    {True: "Completed", False: "Partial / future"}
                )
                sales["ready_for_full_year_comparison"] = (
                    sales["ready_for_full_year_comparison"]
                    .fillna(False).astype(bool)
                )

                all_sales_vehicles = sorted(sales["vehicle"].dropna().unique().tolist())
                all_sales_years = sorted(
                    sales["calendar_year"].dropna().astype(int).unique().tolist()
                )
                initial_sales_vehicles = [
                    v for v in ["Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express"]
                    if v in all_sales_vehicles
                ]
                st.markdown("##### Sales filters")
                sales_filter1, sales_filter2 = st.columns([2, 1])
                with sales_filter1:
                    sales_vehicles = st.multiselect(
                        "Vehicles", options=all_sales_vehicles,
                        default=initial_sales_vehicles or all_sales_vehicles[:4],
                        key="sales_vehicle_filter",
                    )
                with sales_filter2:
                    sales_year_range = st.select_slider(
                        "Calendar years", options=all_sales_years,
                        value=(all_sales_years[0], all_sales_years[-1]),
                        key="sales_year_filter",
                    )
                status_options = [
                    "Verified", "Corrected & verified", "Independently corroborated",
                    "Source-reported", "Provisional", "Unresolved", "Mixed scope",
                    "Partial year", "Reported zero", "Missing",
                ]
                sales_statuses = st.multiselect(
                    "Data status", options=status_options,
                    default=status_options, key="sales_status_filter",
                )
                sales_subset = sales.loc[
                    sales["vehicle"].isin(sales_vehicles)
                    & sales["calendar_year"].between(*sales_year_range)
                    & sales["Status"].isin(sales_statuses)
                ].copy()

                if sales_subset.empty:
                    st.info("No sales records match these filters. Adjust the vehicle, year, or status selections.")
                else:
                    available = sales_subset["us_sales"].notna()
                    total_rows = len(sales_subset)
                    # Count vehicle platforms with any reported sales, not
                    # all platforms that simply have placeholder rows.
                    with_values = sales_subset.loc[available, "vehicle"].nunique()
                    coverage_pct = 100 * int(available.sum()) / total_rows
                    review_count = int(
                        sales_subset["us_sales"].notna().sum()
                        - sales_subset["Status"].isin(["Verified", "Corrected & verified"]).sum()
                    )
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Sales records available", f"{int(available.sum()):,}")
                    m2.metric("Vehicles with sales data", f"{with_values:,}")
                    m3.metric("Selected data coverage", f"{coverage_pct:.1f}%")
                    m4.metric("Records needing review", f"{review_count:,}")
                    st.caption(
                        "Coverage is populated records divided by selected vehicle-year rows. "
                        "These figures describe data availability, not accuracy."
                    )

                    st.markdown("##### Annual U.S. sales trends")
                    show_provisional = st.checkbox(
                        "Include provisional full-year figures in charts",
                        value=False, key="sales_include_provisional",
                        help="Off: manufacturer-verified annual figures only. On: also include provisional and independently corroborated totals; unresolved and mixed-scope figures remain excluded.",
                    )
                    chart_rows = sales_subset.loc[
                        sales_subset["is_complete_calendar_year"]
                        & sales_subset["us_sales"].notna()
                        & sales_subset["us_sales"].gt(0)
                        & sales_subset["Status"].isin(
                            ["Verified", "Corrected & verified", "Independently corroborated", "Provisional", "Source-reported"]
                            if show_provisional else ["Verified", "Corrected & verified"]
                        )
                    ].copy()
                    if chart_rows.empty:
                        st.info(
                            "No positive, completed-year sales figures qualify for "
                            "these chart settings. The detailed table remains available."
                        )
                    else:
                        chart_rows["Calendar year"] = chart_rows["calendar_year"].astype(int)
                        fig_trend = px.line(
                            chart_rows.sort_values("Calendar year"),
                            x="Calendar year", y="us_sales", color="vehicle",
                            markers=True,
                            color_discrete_sequence=NEON_PALETTE,
                            labels={
                                "us_sales": "U.S. sales",
                                "vehicle": "Vehicle",
                                "Calendar year": "Calendar year",
                            },
                            hover_data={"Status": True, "source_name": True},
                        )
                        fig_trend.update_layout(
                            legend_title_text="Vehicle",
                            margin=dict(l=10, r=10, t=15, b=10),
                        )
                        fig_trend.update_xaxes(dtick=1, tickformat="d")
                        fig_trend.update_traces(opacity=0.83)
                        neon_style(fig_trend)
                        st.plotly_chart(
                            fig_trend, use_container_width=True, key="sales_trend_chart"
                        )
                        st.caption(
                            "Only completed calendar years with positive published figures "
                            "are plotted. Gaps mean unavailable or excluded data. "
                            "Provisional figures are shown only when requested; disputed and mixed-scope rows are excluded."
                        )

                        st.markdown("##### Compare vehicles in one year")
                        bar_years = sorted(
                            chart_rows["Calendar year"].unique().tolist()
                        )
                        bar_year = st.selectbox(
                            "Comparison year", options=bar_years,
                            index=len(bar_years) - 1,
                            key="sales_bar_year",
                        )
                        bar_rows = chart_rows.loc[
                            chart_rows["Calendar year"].eq(bar_year)
                        ].sort_values("us_sales", ascending=False)
                        fig_bar = px.bar(
                            bar_rows, x="vehicle", y="us_sales", color="vehicle",
                            color_discrete_sequence=NEON_PALETTE,
                            labels={"vehicle": "Vehicle", "us_sales": "U.S. sales"},
                            hover_data={"Status": True, "source_name": True},
                        )
                        fig_bar.update_layout(
                            showlegend=False, margin=dict(l=10, r=10, t=15, b=10)
                        )
                        fig_bar.update_traces(opacity=0.76)
                        neon_style(fig_bar)
                        st.plotly_chart(
                            fig_bar, use_container_width=True, key="sales_year_bar_chart"
                        )
                    st.caption(
                        "Sales figures can include different configurations and body types; "
                        "do not infer market share or mechanical failure rates."
                    )

                    st.markdown("##### Detailed sales records")
                    table = sales_subset.copy()
                    table["Sales availability"] = "Reported"
                    table.loc[table["us_sales"].isna(), "Sales availability"] = "Missing"
                    table.loc[table["us_sales"].eq(0), "Sales availability"] = "Reported zero"
                    view = table[[
                        "vehicle", "calendar_year", "us_sales", "Status",
                        "Full year", "source_name", "Source link"
                    ]].rename(columns={
                        "vehicle": "Vehicle", "calendar_year": "Year",
                        "us_sales": "U.S. sales", "source_name": "Source"
                    }).sort_values(["Vehicle", "Year"])
                    st.dataframe(
                        view, hide_index=True, use_container_width=True,
                        column_config={
                            "Source link": st.column_config.LinkColumn("Reference"),
                            "U.S. sales": st.column_config.NumberColumn(
                                "U.S. sales", format="%d"
                            ),
                        },
                    )
                    st.caption(
                        "Verified denotes documented manufacturer evidence. Provisional and source-reported "
                        "figures remain unverified; unresolved and mixed-scope totals require further research. "
                        "Partial years are not full annual totals."
                    )

                    with st.expander("Data quality, source notes & download"):
                        st.markdown(
                            "**Validation definitions:** Source-reported means a source "
                            "was identified, not that FleetIQ independently confirmed "
                            "the number. Review needed requires checking the cited "
                            "source. Reported zero must be checked before being "
                            "interpreted as zero deliveries. Missing values are "
                            "unavailable, not assumed zero."
                        )
                        st.write(
                            f"Selected rows: {total_rows:,} | "
                            f"Missing sales: {int((~available).sum()):,} | "
                            f"Reported zeros: {int(sales_subset['us_sales'].eq(0).sum()):,} | "
                            f"Partial/future-year populated values: "
                            f"{int((available & ~sales_subset['is_complete_calendar_year']).sum()):,}"
                        )
                        st.dataframe(
                            sales_subset[[
                                "vehicle", "calendar_year", "us_sales", "Status",
                                "source_name", "Source link", "quality_flags",
                                "notes", "ready_for_full_year_comparison",
                                "source_verification_status", "verified_for_comparison"
                            ]].rename(columns={
                                "vehicle": "Vehicle", "calendar_year": "Year",
                                "us_sales": "U.S. sales", "source_name": "Source",
                                "quality_flags": "Quality flags", "notes": "Source notes",
                                "ready_for_full_year_comparison": "Structurally eligible",
                                "source_verification_status": "Audit status",
                                "verified_for_comparison": "Manufacturer verified annual",
                            }).sort_values(["Vehicle", "Year"]),
                            hide_index=True, use_container_width=True,
                            column_config={
                                "Source link": st.column_config.LinkColumn("Reference")
                            },
                        )
                        st.download_button(
                            "Download filtered sales CSV",
                            data=sales_subset.to_csv(index=False).encode("utf-8"),
                            file_name="fleetiq_sales_filtered.csv",
                            mime="text/csv",
                            key="sales_csv_download",
                        )
                        st.caption(
                            "Calendar-year sales cannot be divided by NHTSA model-year "
                            "complaint counts to obtain a reliability score."
                        )
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"Unable to load cleaned sales dataset: {exc}")


# The diagram is illustrative: marker positions denote broad component systems.

def hotspot_level(pct, count):
    # Descriptive shares, never calibrated part failure probabilities.
    if count == 0:
        return "No reports", "#76899C"
    if pct >= 30:
        return "High share", "#FF5277"
    if pct >= 15:
        return "Elevated share", "#FFAD42"
    if pct >= 5:
        return "Moderate share", "#FFE66D"
    return "Lower share", "#00F5D4"


with hotspots_tab:
    st.markdown("#### Failure Hotspots — Reported Vehicle Systems")
    st.caption(
        "Compare up to three vehicles. Colors show the share of distinct NHTSA "
        "complaints mentioning a system, NOT the likelihood that a part will fail. "
        "The illustrated vehicle is a generic mechanical cutaway; actual layouts vary."
    )
    hotspot_options = sorted(complaints["vehicle"].dropna().unique().tolist())
    favorite_hotspots = [
        x for x in ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter")
        if x in hotspot_options
    ]
    hotspot_vans = st.multiselect(
        "Vehicles to compare (up to 3)", hotspot_options,
        default=favorite_hotspots[:2] or hotspot_options[:2],
        max_selections=3, key="hotspot_vans",
    )
    hotspot_years = sorted(
        complaints["model_year"].dropna().astype(int).unique().tolist()
    )
    hotspot_period = st.select_slider(
        "Model-year range", options=hotspot_years,
        value=(hotspot_years[0], hotspot_years[-1]),
        key="hotspot_period",
    )
    st.caption(
        "Independent hotspot filters. A complaint can reference multiple systems, "
        "but is counted only once within any single system."
    )
    if not hotspot_vans:
        st.info("Choose one or more vehicles to view their reported systems.")
    else:
        hs = complaints.loc[
            complaints["vehicle"].isin(hotspot_vans)
            & complaints["model_year"].between(*hotspot_period)
        ].copy()
        hs["system"] = hs["component"].map(component_system)
        hs_unique = hs.drop_duplicates(["vehicle", "odi_number", "system"])
        denominators = hs.groupby("vehicle")["odi_number"].nunique()
        counts = (
            hs_unique.groupby(["vehicle", "system"])["odi_number"]
            .nunique().reset_index(name="complaints")
        )
        counts["total"] = counts["vehicle"].map(denominators)
        counts["share_pct"] = 100 * counts["complaints"] / counts["total"]
        st.caption(
            "🟢 Lower share (<5%) · 🟡 Moderate (5–<15%) · "
            "🟠 Elevated (15–<30%) · 🔴 High (30%+) · "
            "Gray = no matched reports. Thresholds are descriptive, not risk ratings."
        )
        columns = st.columns(len(hotspot_vans))
        for column, van in zip(columns, hotspot_vans):
            with column:
                total = int(denominators.get(van, 0))
                st.markdown(f"##### {van}")
                if not total:
                    st.info("No matching complaints for these model years.")
                    continue
                sub = counts.loc[counts["vehicle"].eq(van)]
                lookup = sub.set_index("system")[
                    ["complaints", "share_pct"]
                ].to_dict("index")
                st_components.html(
                    render_cutaway(lookup, total, van, detailed=False),
                    height=440, scrolling=False,
                )
                table = pd.DataFrame([
                    {
                        "System": system,
                        "Complaints": int(lookup.get(system, {}).get("complaints", 0)),
                        "Share (%)": round(
                            float(lookup.get(system, {}).get("share_pct", 0)), 1
                        ),
                    }
                    for system in SYSTEMS
                ])
                table["Level"] = table.apply(
                    lambda row: hotspot_level(
                        row["Share (%)"], row["Complaints"]
                    )[0], axis=1
                )
                st.dataframe(
                    table, hide_index=True, use_container_width=True, height=340
                )
        focused_van = st.selectbox(
            "Inspect detailed vehicle anatomy",
            hotspot_vans, key="hotspot_detailed_van",
        )
        focused_total = int(denominators.get(focused_van, 0))
        if focused_total:
            focus_data = counts.loc[counts["vehicle"].eq(focused_van)]
            focus_lookup = focus_data.set_index("system")[
                ["complaints", "share_pct"]
            ].to_dict("index")
            st.markdown(f"##### Expanded mechanical cutaway — {focused_van}")
            st.caption(
                "Expanded view retains mechanical detail and complaint excerpts. "
                "The compact comparison cards use simplified, smaller components."
            )
            # Selectable SVG component groups reveal source excerpts directly.
            focus_evidence = hs.loc[hs["vehicle"].eq(focused_van)].copy()
            focus_evidence = focus_evidence.drop_duplicates(
                ["system", "odi_number"]
            )
            excerpts = {}
            for source_system, section in focus_evidence.groupby("system"):
                excerpts[source_system] = [
                    {
                        "model_year": row.model_year,
                        "component": row.component,
                        "description": row.description
                        if pd.notna(row.description) else "",
                    }
                    for row in section.head(3).itertuples(index=False)
                ]
            st_components.html(
                render_cutaway(
                    focus_lookup, focused_total, focused_van,
                    detailed=True, evidence_rows=excerpts
                ),
                height=695, scrolling=False,
            )
            st.caption(
                "Click a highlighted component in the cutaway to see its complaint "
                "share and short NHTSA excerpts inside the viewer. The detailed "
                "table and downloadable source evidence remain below. "
                "This is a generic schematic, not a vehicle-specific service diagram. "
                "Engine/radiator and front/rear wheel-end parts share broad NHTSA "
                "system categories when complaint records lack part-level precision."
            )
        if not counts.empty:
            st.markdown("##### Compare complaint shares across vehicles")
            shares = counts.pivot(
                index="system", columns="vehicle", values="share_pct"
            ).reindex(SYSTEMS).fillna(0)
            neon_bar(
                shares, horizontal=True,
                x_label="Share of each vehicle's distinct complaints (%)",
                y_label="Reported system",
            )
            st.caption(
                "System shares can total more than 100%, since one complaint "
                "may involve several systems. Lower shares are not evidence of "
                "greater reliability."
            )
        st.markdown("##### Review the underlying NHTSA complaints")
        evidence_van = st.selectbox(
            "Vehicle for evidence", hotspot_vans, key="hotspot_evidence_van"
        )
        evidence_system = st.selectbox(
            "Reported system", SYSTEMS,
            key="hotspot_evidence_system",
        )
        evidence = hs.loc[
            hs["vehicle"].eq(evidence_van)
            & hs["system"].eq(evidence_system)
        ].drop_duplicates("odi_number").sort_values(
            "received_date", ascending=False
        )
        st.caption(
            f"{len(evidence):,} distinct complaints mention {evidence_system} "
            f"for {evidence_van} in the selected model years."
        )
        if evidence.empty:
            st.info("No matching reports for this system and vehicle.")
        else:
            evidence_cols = [
                "odi_number", "model_year", "received_date",
                "component", "mileage", "description",
            ]
            st.dataframe(
                evidence[evidence_cols], hide_index=True,
                use_container_width=True,
            )
            st.download_button(
                "Download hotspot complaint evidence",
                data=evidence[evidence_cols].to_csv(index=False).encode("utf-8"),
                file_name="fleetiq_hotspot_evidence.csv", mime="text/csv",
                key="hotspot_evidence_download",
            )
    st.info(
        "Sales-context limitation: calendar-year vehicle sales are not the "
        "registered model-year population at risk. FleetIQ does not calculate "
        "failure probabilities from these incompatible datasets."
    )

st.divider()
st.caption(
    "FleetIQ uses the NHTSA bulk complaint archive processed by refresh_data.py. "
    "Official recall campaigns are queried on demand in the Safety recalls tab. "
    "Sales/registration denominators will be needed before any complaint-rate or reliability ranking is appropriate."
)


with repair_tab:
    render_repair_cost_tab(DATA_DIR)

with maintenance_tab:
    render_maintenance_tab(DATA_DIR)


with recalls_tab:
    render_recall_tab()

with ownership_tab:
    render_ownership_tab()


with report_tab:
    render_vehicle_report(DATA_DIR, complaints)

with fleet_tab:
    render_fleet_workspace()
    st.divider()
    render_profitability()
    render_prediction_readiness()

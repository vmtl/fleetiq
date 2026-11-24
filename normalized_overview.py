"""Sales-normalized complaint reporting index; not a vehicle failure rate."""
from pathlib import Path
import pandas as pd
import streamlit as st

def render_normalized_overview(complaints, data_dir, key_prefix="overview"):
    st.subheader("Sales-normalized complaint comparison")
    st.caption("Unique NHTSA complaints received per 1,000 U.S. vehicles sold in the same calendar-year window. This is a reporting index, not the percentage of vehicles that failed.")
    path = Path(data_dir) / "sales_selection.csv"
    if not path.exists():
        st.info("Selected sales figures are unavailable.")
        return
    sales = pd.read_csv(path)
    required = {"vehicle", "calendar_year", "us_sales", "selection_status", "comparison_eligibility"}
    if not required.issubset(sales.columns) or not {"vehicle", "received_date", "odi_number"}.issubset(complaints.columns):
        st.info("Sales and complaint fields needed for normalization are unavailable.")
        return
    sales["calendar_year"] = pd.to_numeric(sales["calendar_year"], errors="coerce")
    sales["us_sales"] = pd.to_numeric(sales["us_sales"], errors="coerce")
    sales = sales[(sales["selection_status"] == "selected") & (sales["us_sales"] > 0) & (sales["comparison_eligibility"] == "annual_sales_only")].copy()
    sales = sales[sales["calendar_year"].between(2015, 2025)]
    if sales.empty:
        st.info("No eligible annual sales figures.")
        return
    available = sorted(sales["calendar_year"].astype(int).unique())
    year_start, year_end = st.select_slider("Calendar-year reporting window", options=available, value=(available[0], available[-1]), key=f"{key_prefix}_normalized_years")
    sales = sales[sales["calendar_year"].between(year_start, year_end)]
    # Require complete positive annual sales coverage within the selected window.
    expected = year_end - year_start + 1
    grouped = sales.groupby("vehicle").agg(sales_units=("us_sales", "sum"), covered_years=("calendar_year", "nunique")).reset_index()
    grouped = grouped[grouped["covered_years"] == expected]
    c = complaints[["vehicle", "received_date", "odi_number"]].copy()
    c["report_year"] = pd.to_datetime(c["received_date"], errors="coerce").dt.year
    c = c[c["report_year"].between(year_start, year_end)].dropna(subset=["odi_number"])
    counts = c.groupby("vehicle")["odi_number"].nunique()
    grouped["complaints_received"] = grouped["vehicle"].map(counts).fillna(0).astype(int)
    grouped["index"] = grouped["complaints_received"] / grouped["sales_units"] * 1000
    grouped = grouped.sort_values("index", ascending=True)
    if grouped.empty:
        st.info("No platforms have complete selected sales coverage for this reporting window. Try a shorter range.")
        return
    st.bar_chart(grouped.set_index("vehicle")["index"], horizontal=True, x_label="Complaints received per 1,000 vehicles sold")
    display = grouped.rename(columns={"vehicle": "Vehicle", "sales_units": "U.S. sales", "complaints_received": "Unique complaints received", "index": "Complaints per 1,000 sold"})
    st.dataframe(display[["Vehicle", "U.S. sales", "Unique complaints received", "Complaints per 1,000 sold"]], hide_index=True, use_container_width=True, column_config={"Complaints per 1,000 sold": st.column_config.NumberColumn(format="%.2f"), "U.S. sales": st.column_config.NumberColumn(format="localized"), "Unique complaints received": st.column_config.NumberColumn(format="localized")})
    st.caption(f"Reporting period: {year_start}–{year_end}. Only platforms with selected positive sales in every year are shown. Sales are calendar-year transactions, not a count of unique vehicles in service. Complaints may involve vehicles sold in earlier years or multiple reports about one vehicle. Rankings describe reporting volume relative to sales, not mechanical reliability.")



@st.cache_data(show_spinner=False)
def eligible_sales(data_dir, start, end):
    """Only complete selected annual U.S. sales histories are comparable."""
    path = Path(data_dir) / "sales_selection.csv"
    if not path.exists():
        return pd.Series(dtype=float)
    sales = pd.read_csv(path)
    required = {"vehicle", "calendar_year", "us_sales", "selection_status", "comparison_eligibility"}
    if not required.issubset(sales.columns):
        return pd.Series(dtype=float)
    sales["calendar_year"] = pd.to_numeric(sales["calendar_year"], errors="coerce")
    sales["us_sales"] = pd.to_numeric(sales["us_sales"], errors="coerce")
    sales = sales.loc[
        sales["calendar_year"].between(start, end)
        & sales["selection_status"].eq("selected")
        & sales["comparison_eligibility"].eq("annual_sales_only")
        & sales["us_sales"].gt(0)
    ].drop_duplicates(["vehicle", "calendar_year"])
    totals = sales.groupby("vehicle").agg(units=("us_sales", "sum"), years=("calendar_year", "nunique"))
    return totals.loc[totals["years"].eq(end - start + 1), "units"]


def reporting_index(complaints, denominators, start, end, category=None):
    """Unique ODI reports per 1,000 sales; missing denominators remain NaN."""
    units = pd.to_numeric(denominators, errors="coerce")
    units = units.where(units.gt(0))
    c = complaints.loc[pd.to_datetime(complaints["received_date"], errors="coerce").dt.year.between(start, end)]
    if category is None:
        counts = c.groupby("vehicle")["odi_number"].nunique()
        return counts.reindex(units.index, fill_value=0).div(units).mul(1000)
    counts = c.groupby([category, "vehicle"])["odi_number"].nunique().unstack(fill_value=0)
    return counts.reindex(columns=units.index, fill_value=0).div(units, axis=1).mul(1000)


def normalized_component_chart(complaints, data_dir, vehicles, component_mapper=None, flags=None):
    """Compare report categories per 1,000 sales using one consistent receipt window."""
    window = st.session_state.get("overview_normalized_years", (2015, 2025))
    start, end = map(int, window)
    denominators = eligible_sales(str(data_dir), start, end)
    denominators = denominators[denominators.index.isin(vehicles)]
    if denominators.empty:
        st.info("No complete positive annual sales series for these vehicles and calendar years.")
        return
    c = complaints.loc[complaints["vehicle"].isin(denominators.index)].copy()
    c = c.loc[pd.to_datetime(c["received_date"], errors="coerce").dt.year.between(start, end)]
    if flags:
        frames = []
        for label, column in flags.items():
            flagged = c.loc[c[column].astype(str).str.upper().isin(["Y", "YES", "TRUE", "1"])].copy()
            flagged["category"] = label
            frames.append(flagged)
        c = pd.concat(frames, ignore_index=True) if frames else c.iloc[0:0]
    else:
        c["category"] = c["component"].map(component_mapper) if component_mapper else c["component"]
    if c.empty:
        st.info("No matching complaint indicators in this calendar-year reporting window.")
        return
    chart = reporting_index(c, denominators, start, end, category="category")
    chart = chart.loc[chart.max(axis=1).sort_values(ascending=False).head(15).index]
    st.bar_chart(chart, horizontal=True, x_label="Reports mentioning category per 1,000 U.S. vehicles sold")
    st.caption(f"{start}–{end} calendar-year reporting index. Categories can overlap; sales and complaint cohorts are not linked. Not a failure rate.")

def render_tab_sales_context(complaints, data_dir, selected_vehicles=None):
    """Compact shared reporting index, not a model-year failure rate."""
    path = Path(data_dir) / "sales_selection.csv"
    if not path.exists():
        return
    sales = pd.read_csv(path)
    needed = {"vehicle", "calendar_year", "us_sales", "selection_status", "comparison_eligibility"}
    if not needed.issubset(sales.columns):
        return
    sales["calendar_year"] = pd.to_numeric(sales["calendar_year"], errors="coerce")
    sales["us_sales"] = pd.to_numeric(sales["us_sales"], errors="coerce")
    window = st.session_state.get("overview_normalized_years", (2015, 2025))
    start, end = int(window[0]), int(window[1])
    sales = sales[
        sales["calendar_year"].between(start, end)
        & sales["selection_status"].eq("selected")
        & sales["comparison_eligibility"].eq("annual_sales_only")
        & sales["us_sales"].gt(0)
    ]
    grouped = sales.groupby("vehicle", as_index=False).agg(
        sales_units=("us_sales", "sum"), years=("calendar_year", "nunique")
    )
    grouped = grouped[grouped["years"].eq(end - start + 1)]
    if selected_vehicles is not None:
        grouped = grouped[grouped["vehicle"].isin(selected_vehicles)]
    if grouped.empty:
        st.caption("Sales-normalized comparison unavailable for this selection and reporting window.")
        return
    c = complaints[["vehicle", "received_date", "odi_number"]].copy()
    c["year"] = pd.to_datetime(c["received_date"], errors="coerce").dt.year
    c = c[c["year"].between(start, end)]
    counts = c.groupby("vehicle")["odi_number"].nunique()
    grouped["reports"] = grouped["vehicle"].map(counts).fillna(0).astype(int)
    grouped["per_1000"] = grouped["vehicle"].map(reporting_index(complaints, eligible_sales(str(data_dir), start, end), start, end))
    grouped = grouped.sort_values("per_1000")
    st.markdown("##### Sales-normalized complaint context")
    st.dataframe(
        grouped.rename(columns={"vehicle": "Vehicle", "sales_units": "U.S. sales", "reports": "Complaints received", "per_1000": "Reports per 1,000 sold"})
        [["Vehicle", "Reports per 1,000 sold", "U.S. sales", "Complaints received"]],
        hide_index=True, use_container_width=True,
        column_config={"Reports per 1,000 sold": st.column_config.NumberColumn(format="%.2f"), "U.S. sales": st.column_config.NumberColumn(format="localized"), "Complaints received": st.column_config.NumberColumn(format="localized")},
    )
    st.caption(f"{start}–{end} calendar-year reporting index. Sales and complaint cohorts are not linked; this is not a vehicle failure rate.")

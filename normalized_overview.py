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
    st.dataframe(display[["Vehicle", "U.S. sales", "Unique complaints received", "Complaints per 1,000 sold"]], hide_index=True, use_container_width=True, column_config={"Complaints per 1,000 sold": st.column_config.NumberColumn(format="%.2f"), "U.S. sales": st.column_config.NumberColumn(format="%d")})
    st.caption(f"Reporting period: {year_start}–{year_end}. Only platforms with selected positive sales in every year are shown. Sales are calendar-year transactions, not a count of unique vehicles in service. Complaints may involve vehicles sold in earlier years or multiple reports about one vehicle. Rankings describe reporting volume relative to sales, not mechanical reliability.")

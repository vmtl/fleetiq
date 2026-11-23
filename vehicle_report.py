"""FleetIQ consolidated acquisition research report with explicit evidence gaps."""
from __future__ import annotations
import html
import io
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from normalized_overview import eligible_sales

VANS = ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express")


def vehicle_report(complaints: pd.DataFrame, schedules: pd.DataFrame,
                   repair_prices: pd.DataFrame, vehicle: str,
                   year: int, current_miles: int) -> dict:
    if vehicle not in VANS or year < 2014 or year > 2026 or current_miles < 0:
        raise ValueError("Unsupported vehicle, year, or odometer")
    raw = complaints.loc[
        complaints.vehicle.eq(vehicle)
        & pd.to_numeric(complaints.model_year, errors="coerce").eq(year)
    ].copy()
    unique = raw.drop_duplicates("odi_number") if "odi_number" in raw.columns else raw.iloc[0:0]
    mileage = pd.to_numeric(unique.get("mileage", pd.Series(dtype=float)), errors="coerce")
    usable = mileage[(mileage > 0) & mileage.notna()]
    scoped = schedules.loc[
        schedules.vehicle.eq(vehicle)
        & pd.to_numeric(schedules.model_year_start, errors="coerce").le(year)
        & pd.to_numeric(schedules.model_year_end, errors="coerce").ge(year)
    ].copy()
    estimates = repair_prices.loc[repair_prices.vehicle.eq(vehicle)].copy()
    return {
        "vehicle": vehicle, "year": int(year), "miles": int(current_miles),
        "unique_complaints": len(unique), "reports_with_mileage": len(usable),
        "median_reported_miles": int(usable.median()) if len(usable) else None,
        "maintenance": scoped, "prices": estimates,
        "comparable_sample": False,
    }


def report_html(data: dict) -> str:
    """Self-contained HTML export, escaping all external and imported strings."""
    e = lambda s: html.escape(str(s), quote=True)
    def rows(frame, columns):
        if frame.empty:
            return "<p>No year-matched verified entries currently available.</p>"
        values = ["<tr>" + "".join("<th>" + e(c) + "</th>" for c in columns) + "</tr>"]
        for _, record in frame.head(50).iterrows():
            values.append("<tr>" + "".join("<td>" + e(record.get(c, "")) + "</td>" for c in columns) + "</tr>")
        return "<table>" + "".join(values) + "</table>"
    schedules = data["maintenance"]
    prices = data["prices"]
    label = f"{data['year']} {data['vehicle']}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>FleetIQ — {e(label)}</title>
<style>body{{font-family:system-ui,sans-serif;background:#101b2a;color:#e9f2ff;
padding:30px;max-width:1100px;margin:auto;line-height:1.5}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{border-bottom:1px solid #37465a;padding:8px;text-align:left}}
small{{color:#b5c4db}}h1,h2{{color:#8ce1e4}}</style></head><body>
<h1>FleetIQ Vehicle Intelligence Report</h1>
<p><strong>{e(label)}</strong> · Entered odometer: {data['miles']:,} miles · Generated: {date.today().isoformat()}</p>
<h2>Sales-normalized complaint reporting index</h2>
<p>{f"{data['reporting_index']:.2f} complaints received per 1,000 U.S. vehicles sold" if data.get('reporting_index') is not None else "Unavailable: incomplete eligible annual sales coverage"} during {data.get('reporting_window', ('?', '?'))[0]}–{data.get('reporting_window', ('?', '?'))[1]}.</p>
<small>Calendar-year sales and complaint cohorts are not linked; this is not a model-year failure rate.</small>
<h2>Historical NHTSA consumer complaints</h2>
<p>Distinct complaint records: {data['unique_complaints']:,}.
Records with usable reported mileage: {data['reports_with_mileage']:,}.
Median reported mileage: {data['median_reported_miles'] if data['median_reported_miles'] is not None else "Unavailable"}.</p>
<small>Complaint records are neither actual failure probabilities nor repair histories. There is no matched in-service fleet denominator.</small>
<h2>Manufacturer maintenance guidance</h2>
{rows(schedules, ["task","interval_miles","interval_months","schedule_mode","engine_scope","source_url"])}
<small>Only year-matched manufacturer references are shown. No service due assessment without per-task completion records.</small>
<h2>Published repair price references (not vehicle-year-specific quotes)</h2>
{rows(prices, ["reference_configuration","repair_operation","low_usd","high_usd","source_url"])}
<small>Reference estimates may not match selected engine, local labor, parts or model year.</small>
<h2>Official recall verification</h2>
<p>Check <a href="https://www.nhtsa.gov/recalls">NHTSA VIN recalls</a> for open campaigns on a specific van. Model-level campaign lookup is provided within FleetIQ.</p>
<h2>Purchase due diligence</h2>
<p>Independently inspect the exact vehicle, review maintenance invoices, verify VIN-specific recalls, test drive,
confirm title and commercial suitability, and obtain local repair quotes. FleetIQ has not assessed the condition of a specific vehicle.</p>
<small>Research report, not an inspection, financial opinion or safety certification. No reliability ranking is generated.</small>
</body></html>"""


def render_vehicle_report(data_dir: Path, complaints: pd.DataFrame) -> None:
    st.markdown("#### Vehicle Intelligence Report")
    st.caption(
        "One exportable view of complaint exposure, manufacturer-sourced "
        "maintenance and published repair cost references. Report figures "
        "are descriptive, not a vehicle condition or reliability rating."
    )
    a, b, c = st.columns([2, 1, 1])
    vehicle = a.selectbox("Research vehicle", VANS, key="report_van")
    year = b.number_input("Model year", min_value=2014,
                          max_value=2026, value=2020, key="report_year")
    miles = c.number_input("Odometer", min_value=0, max_value=1000000,
                           value=100000, step=5000, key="report_miles")
    try:
        schedules = pd.read_csv(data_dir / "maintenance_schedules.csv")
        prices = pd.read_csv(data_dir / "repair_costs.csv")
        result = vehicle_report(
            complaints, schedules, prices, vehicle, int(year), int(miles)
        )
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        st.error(f"Unable to compile report: {exc}")
        return
    window = st.session_state.get("overview_normalized_years", (2015, 2025))
    start, end = map(int, window)
    sales = eligible_sales(str(data_dir), start, end)
    received = complaints.loc[
        complaints["vehicle"].eq(vehicle)
        & pd.to_datetime(complaints["received_date"], errors="coerce").dt.year.between(start, end),
        "odi_number",
    ].nunique()
    reporting_index = 1000 * received / sales[vehicle] if vehicle in sales.index else None
    result["reporting_index"] = reporting_index
    result["reporting_window"] = (start, end)
    a, b, c = st.columns(3)
    a.metric("Reports / 1,000 sold", f"{reporting_index:.2f}" if reporting_index is not None else "N/A")
    b.metric("Reports with mileage", f"{result['reports_with_mileage']:,}")
    c.metric("Year-matched OEM service entries", len(result["maintenance"]))
    if result["maintenance"].empty:
        st.info("Year-specific maintenance coverage is not verified for this selection.")
    else:
        st.dataframe(
            result["maintenance"][["task","interval_miles","interval_months","schedule_mode","engine_scope","source_url"]],
            hide_index=True, use_container_width=True,
        )
    st.markdown("##### Published repair-cost references")
    st.dataframe(
        result["prices"][["reference_configuration","repair_operation","low_usd","high_usd","source_url"]],
        hide_index=True, use_container_width=True,
    )
    st.caption(
        "Prices are for reference configurations and NOT selected-year repair quotes. "
        "Download includes source links and the limits of the evidence."
    )
    st.download_button(
        "Download Vehicle Intelligence Report (HTML)",
        data=report_html(result).encode("utf-8"),
        file_name=f"fleetiq_vehicle_report_{year}.html",
        mime="text/html", key="vehicle_report_download",
    )

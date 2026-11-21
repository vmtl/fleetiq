"""Transparent OEM maintenance coverage audit for FleetIQ's 2014–2026 target.

One row for every model-year, including unsupported, incomplete and advisory
cases. A valid row of source-backed maintenance is NOT a complete manual.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

VANS = ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express")
YEARS = tuple(range(2014, 2027))
RULES = {
    ("Ford Transit", 2014): ("Not applicable (US)", "US full-size Transit launched as model year 2015. E-Series is a different platform."),
}
NEEDED = {"vehicle", "model_year_start", "model_year_end",
          "schedule_mode", "source_url", "task"}


def build_coverage_matrix(schedules: pd.DataFrame) -> pd.DataFrame:
    if NEEDED - set(schedules.columns):
        raise ValueError("OEM schedule does not have required coverage fields")
    rows = []
    for vehicle in VANS:
        for year in YEARS:
            subset = schedules.loc[
                schedules.vehicle.eq(vehicle)
                & pd.to_numeric(schedules.model_year_start, errors="coerce").le(year)
                & pd.to_numeric(schedules.model_year_end, errors="coerce").ge(year)
            ]
            modes = subset.schedule_mode.dropna().astype(str).tolist()
            supported = subset.loc[
                subset.schedule_mode.isin(["recurring", "monitor_cap", "condition_cap"])
                & subset.source_url.astype(str).str.startswith("https://")
            ]
            if (vehicle, year) in RULES:
                status, reason = RULES[(vehicle, year)]
            elif subset.empty:
                status, reason = "Unverified", "No manufacturer-backed schedule entries have been reviewed for this year"
            elif supported.empty:
                status, reason = "Advisory only", "Existing reference does not support interval forecasting"
            else:
                status, reason = "Partially verified", "Some manufacturer-backed operations are entered; completeness and full configurations not certified"
            rows.append({
                "vehicle": vehicle, "model_year": year,
                "coverage_status": status, "verified_operations": len(supported),
                "advisory_operations": len(subset) - len(supported),
                "source_count": subset.source_url.nunique(),
                "review_required": status not in ("Not applicable (US)",),
                "scope_notes": reason,
            })
    return pd.DataFrame(rows)


def coverage_stats(matrix: pd.DataFrame) -> dict:
    applicable = matrix[~matrix.coverage_status.eq("Not applicable (US)")]
    return {
        "target_combinations": len(applicable),
        "with_any_verified_operations": int(
            applicable.verified_operations.gt(0).sum()
        ),
        "unverified": int(applicable.coverage_status.eq("Unverified").sum()),
        "fully_certified": 0,  # No complete, powertrain-audited manuals certified yet.
    }


def render_coverage_audit(data_dir: Path) -> None:
    st.markdown("##### Manufacturer maintenance catalog coverage — 2014–2026")
    try:
        catalog = pd.read_csv(data_dir / "maintenance_schedules.csv")
        table = build_coverage_matrix(catalog)
        stats = coverage_stats(table)
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        st.warning(f"Unable to assess manufacturer coverage: {exc}")
        return
    a, b, c = st.columns(3)
    a.metric("Applicable van-year groups", stats["target_combinations"])
    b.metric("Groups with verified operations", stats["with_any_verified_operations"])
    c.metric("Fully audited configurations", stats["fully_certified"])
    st.caption(
        "Coverage is incomplete. A manufacturer-backed interval is not "
        "certification that all engines, operating conditions and services "
        "for that model year have been verified. The 2014 Ford Transit "
        "full-size van was not a US model-year offering."
    )
    status_colors = {"Partially verified": "🟡",
                     "Unverified": "⚪",
                     "Advisory only": "🟠",
                     "Not applicable (US)": "—"}
    pivot = table.copy()
    pivot["display"] = pivot.apply(
        lambda r: (
            f"🟡 {int(r.verified_operations)} ops"
            if r.coverage_status == "Partially verified"
            else status_colors[r.coverage_status]
        ), axis=1
    )
    st.dataframe(
        pivot.pivot(index="vehicle", columns="model_year", values="display"),
        use_container_width=True,
    )
    with st.expander("Inspect every missing or partially verified model-year"):
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button(
            "Download manufacturer coverage and verification gaps (CSV)",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name="fleetiq_maintenance_coverage.csv", mime="text/csv",
            key="coverage_export",
        )
    st.warning(
        "Service predictions are limited to supported, year-specific tasks. "
        "Historical NHTSA complaint mileage is not a failure time series."
    )

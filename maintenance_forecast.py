"""Top-of-page FleetIQ maintenance forecast and complaint hotspot visuals.

Intervals are conditional on per-operation service history. Cost totals include
only published, year-specific references or explicitly user-entered budgets.
No estimated repair failures or complaint-derived due dates.
"""
from __future__ import annotations

from pathlib import Path
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

COST_COLUMNS = {"vehicle", "model_year", "task", "low_usd", "high_usd",
                "reference_configuration", "source_url", "source_name",
                "checked_on", "price_scope"}
WINDOWS = (10000, 25000, 50000)
PALETTE = {"Over limit": "#FF5277", "Upcoming": "#00F5D4",
           "Maximum limit": "#FBBF24", "Conditional": "#E879F9"}


def validate_maintenance_costs(frame: pd.DataFrame) -> pd.DataFrame:
    missing = COST_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("Maintenance cost references missing columns: " + ", ".join(sorted(missing)))
    data = frame.copy()
    for col in ("model_year", "low_usd", "high_usd"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    if data[list(("model_year", "low_usd", "high_usd"))].isna().any().any():
        raise ValueError("Maintenance costs must have valid numbers")
    if ((data.low_usd < 0) | (data.high_usd < data.low_usd)
        | ~data.source_url.astype(str).str.startswith("https://")).any():
        raise ValueError("Invalid cost range or source")
    if data.duplicated(["vehicle", "model_year", "task"]).any():
        raise ValueError("Duplicate maintenance cost reference")
    return data


def build_forecast(schedule: pd.DataFrame, cost_refs: pd.DataFrame,
                   vehicle: str, year: int, mileage: int,
                   histories: dict, include_severe: bool = False,
                   budget_overrides: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Milestone events from known service history; never infer missing history.

    Overdue tasks produce one immediate marker, not fabricated additional
    intervals; monitor-based caps produce at most one ceiling event.
    """
    if int(mileage) < 0:
        raise ValueError("Odometer must be nonnegative")
    horizon = int(mileage) + max(WINDOWS)
    events, other = [], []
    overrides = budget_overrides or {}
    selected = schedule.loc[
        schedule.vehicle.eq(vehicle)
        & schedule.model_year_start.le(year)
        & schedule.model_year_end.ge(year)
    ].copy()
    for _, row in selected.iterrows():
        task = str(row.task)
        mode = str(row.schedule_mode)
        if mode == "condition_cap" and not include_severe:
            continue
        hist = histories.get(task, {})
        last = hist.get("last_mileage")
        months = hist.get("months_since_service")
        limit = int(row.interval_miles)
        month_limit = int(row.interval_months)
        entry = {"task": task, "status": "History needed",
                 "documented_interval_miles": limit, "documented_interval_months": month_limit,
                 "mode": mode, "source_url": str(row.source_url)}
        if mode in ("advisory", "monitor_event"):
            entry["status"] = "Indicator / advisory only"
            other.append(entry)
            continue
        if last is not None and (int(last) < 0 or int(last) > mileage):
            raise ValueError("Last-service odometer must be within current mileage")
        if months is not None and int(months) < 0:
            raise ValueError("Elapsed months must be nonnegative")
        time_due = month_limit > 0 and months is not None and months >= month_limit
        if limit <= 0 or last is None:
            entry["status"] = "Time limit reached" if time_due else "Time-based / history needed"
            other.append(entry)
            continue
        first_due = int(last) + limit
        if time_due:
            entry["status"] = "Time limit reached (mileage timing not applicable)"
            other.append(entry)
        cost_row = cost_refs.loc[
            cost_refs.vehicle.eq(vehicle)
            & cost_refs.model_year.eq(year)
            & cost_refs.task.eq(task)
        ] if not cost_refs.empty else pd.DataFrame()
        cost = cost_row.iloc[0] if not cost_row.empty else None
        own = overrides.get(task)
        if own is not None:
            low, high, price_label = float(own[0]), float(own[1]), "User budget"
            price_url = ""
        elif cost is not None:
            low, high, price_label = float(cost.low_usd), float(cost.high_usd), "Published estimate"
            price_url = str(cost.source_url)
        else:
            low, high, price_label, price_url = None, None, "Cost unavailable", ""
        if first_due <= mileage:
            positions = [int(mileage)]
            labels = ["Over limit"]
            due_mileages = [first_due]
        elif first_due > horizon:
            continue
        elif mode in ("monitor_cap", "condition_cap"):
            positions, labels, due_mileages = [first_due], [
                "Maximum limit" if mode == "monitor_cap" else "Conditional"
            ], [first_due]
        else:
            positions = list(range(first_due, horizon + 1, limit))
            labels = ["Upcoming"] * len(positions)
            due_mileages = positions
        for marker, label, actual_due in zip(positions, labels, due_mileages):
            events.append({
                "task": task, "event_mileage": int(marker),
                "documented_limit_mileage": int(actual_due),
                "distance_miles": max(0, int(marker) - int(mileage)),
                "status": label, "schedule_mode": mode,
                "low_usd": low, "high_usd": high,
                "price_basis": price_label, "price_url": price_url,
                "maintenance_source": str(row.source_url),
                "model_year": year, "vehicle": vehicle,
            })
    return pd.DataFrame(events), pd.DataFrame(other)


def budget_windows(events: pd.DataFrame, windows=WINDOWS) -> pd.DataFrame:
    """Cumulative budget subtotal for priced events only; no unknown-cost zeros."""
    rows = []
    for window in windows:
        subset = events.loc[events.distance_miles.le(window)] if not events.empty else pd.DataFrame()
        priced = subset.loc[subset.low_usd.notna() & subset.high_usd.notna()] if not subset.empty else pd.DataFrame()
        rows.append({
            "window_miles": int(window),
            "known_low_usd": float(priced.low_usd.sum()) if not priced.empty else None,
            "known_high_usd": float(priced.high_usd.sum()) if not priced.empty else None,
            "priced_events": len(priced), "unpriced_events": len(subset) - len(priced),
            "events": len(subset),
        })
    return pd.DataFrame(rows)


def hotspot_table(problem_summary: pd.DataFrame, vehicle: str,
                  year: int, max_rows: int = 6) -> pd.DataFrame:
    """Complaint counts by issue, NOT a distinct-complaint failure rate."""
    required = {"vehicle", "model_year", "issue", "unique_complaints",
                "mileage_samples", "median_reported_miles"}
    if required - set(problem_summary.columns):
        raise ValueError("Problem summary missing hotspot columns")
    selected = problem_summary.loc[
        problem_summary.vehicle.eq(vehicle)
        & pd.to_numeric(problem_summary.model_year, errors="coerce").eq(year)
        & ~problem_summary.issue.isin(
            ["Unspecified / manual review", "Sensor / warning / diagnostic"]
        )
    ].copy()
    for column in ("unique_complaints", "mileage_samples", "median_reported_miles"):
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    selected = selected.loc[selected.unique_complaints.gt(0)]
    selected["mileage_coverage_pct"] = (
        selected.mileage_samples.div(selected.unique_complaints).mul(100).round(1)
    )
    selected.loc[selected.mileage_samples.eq(0), "median_reported_miles"] = float("nan")
    return selected.sort_values(
        ["unique_complaints", "issue"], ascending=[False, True]
    ).head(max_rows)


@st.cache_data(show_spinner=False)
def load_maintenance_prices(path: str, mtime: int) -> pd.DataFrame:
    return validate_maintenance_costs(pd.read_csv(path))


def render_forecast_overview(data_dir: Path, selected: pd.DataFrame,
                             vehicle: str, year: int, mileage: int,
                             problem_summary_loader) -> None:
    st.markdown("##### Maintenance Forecast & Budget")
    st.caption(
        "Near-term mileage outlook and selected-van reported issue hotspots. "
        "Only manufacturer-backed schedule entries with your last-service "
        "history can generate projected milestones. This is not a diagnosis."
    )
    cost_path = data_dir / "maintenance_cost_refs.csv"
    try:
        costs = load_maintenance_prices(
            str(cost_path), cost_path.stat().st_mtime_ns
        ) if cost_path.exists() else pd.DataFrame()
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(f"Published service cost references unavailable: {exc}")
        costs = pd.DataFrame()

    histories: dict = {}
    overrides: dict = {}
    severe = st.checkbox(
        "Include manufacturer-listed severe-duty maintenance scenarios",
        value=False, key="forecast_severe_duty",
        help="Only if your vehicle and driving conditions meet the OEM severe-duty criteria."
    )
    if not selected.empty:
        with st.expander("Enter service history and optional price assumptions", expanded=False):
            st.caption(
                "Enter the last mileage for EACH completed service you know. "
                "Leave the checkbox off when unknown. Price inputs are optional "
                "planning assumptions and never replace published reference prices silently."
            )
            for i, row in selected.iterrows():
                task = str(row.task)
                if row.schedule_mode == "condition_cap" and not severe:
                    continue
                if row.schedule_mode in ("advisory", "monitor_event"):
                    continue
                st.markdown("**" + task + "**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    known_miles = st.checkbox(
                        "Last service mileage known",
                        key=f"forecast_known_miles_{vehicle}_{year}_{i}",
                    )
                    last = st.number_input(
                        "Last completed at (miles)", min_value=0,
                        max_value=int(mileage), value=0, step=500,
                        key=f"forecast_last_{vehicle}_{year}_{i}",
                    ) if known_miles else None
                with c2:
                    known_months = st.checkbox(
                        "Time since service known",
                        key=f"forecast_known_months_{vehicle}_{year}_{i}",
                    )
                    months = st.number_input(
                        "Months elapsed", min_value=0,
                        max_value=600, value=0, step=1,
                        key=f"forecast_months_{vehicle}_{year}_{i}",
                    ) if known_months else None
                with c3:
                    use_override = st.checkbox(
                        "Use my own price range",
                        key=f"forecast_cost_override_{vehicle}_{year}_{i}",
                    )
                    if use_override:
                        low = st.number_input(
                            "Budget low ($)", min_value=0.0, max_value=100000.0,
                            step=25.0, value=0.0,
                            key=f"forecast_low_{vehicle}_{year}_{i}",
                        )
                        high = st.number_input(
                            "Budget high ($)", min_value=float(low), max_value=100000.0,
                            step=25.0, value=float(low),
                            key=f"forecast_high_{vehicle}_{year}_{i}",
                        )
                        overrides[task] = (low, high)
                histories[task] = {
                    "last_mileage": int(last) if last is not None else None,
                    "months_since_service": int(months) if months is not None else None,
                }
    events, time_items = build_forecast(
        selected, costs, vehicle, year, int(mileage), histories,
        include_severe=severe, budget_overrides=overrides,
    )
    # Put the requested timeline and hotspot beside each other, high in the tab.
    left, right = st.columns([1.4, 1])
    with left:
        st.markdown("**Next 50,000 miles — documented service limits**")
        if selected.empty:
            st.info("No year-matched manufacturer schedule available. A forecast cannot be inferred.")
        elif events.empty:
            st.info(
                "No mileage milestones yet. Enter last-service odometer readings "
                "above; time-only and monitor-based tasks are listed separately."
            )
        else:
            import plotly.express as px
            shown = events.copy()
            shown["Cost"] = shown.apply(
                lambda r: (
                    f"${r.low_usd:,.0f}–${r.high_usd:,.0f} ({r.price_basis})"
                    if pd.notna(r.low_usd) else "Unpriced"
                ), axis=1,
            )
            fig = px.scatter(
                shown, x="event_mileage", y="task", color="status",
                color_discrete_map=PALETTE,
                symbol="status",
                hover_data={
                    "documented_limit_mileage": True,
                    "Cost": True, "price_basis": True,
                    "event_mileage": ":,",
                },
                labels={"event_mileage": "Odometer miles", "task": "Service operation"},
            )
            fig.add_vline(x=int(mileage), line_width=2, line_dash="dash",
                          line_color="#9FE7FF")
            fig.update_traces(marker=dict(size=12))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(7,14,30,0)",
                plot_bgcolor="rgba(19,34,56,.23)",
                height=max(320, min(540, len(shown.task.unique()) * 58 + 145)),
                margin=dict(l=10, r=10, t=15, b=35),
                legend_title_text="Interval status",
                xaxis_range=[max(0, int(mileage)-1500), int(mileage)+52000],
            )
            st.plotly_chart(fig, use_container_width=True, key="forecast_timeline_chart")
            st.caption(
                "Dashed vertical line = current odometer. A past limit is "
                "shown at today’s mileage, not as a proven missed repair. "
                "Future repetitions assume each preceding scheduled service is completed."
            )
    with right:
        st.markdown("**Failure Hotspots — selected van**")
        problem_path = data_dir / "problem_summary.csv"
        if problem_path.exists():
            try:
                source = problem_summary_loader(
                    str(problem_path), problem_path.stat().st_mtime_ns
                )
                hotspots = hotspot_table(source, vehicle, int(year))
                if hotspots.empty:
                    st.info("No classified complaint hotspots for the selected model year.")
                else:
                    names = hotspots.sort_values("unique_complaints")
                    hotspot_fig = go.Figure(go.Bar(
                        x=names.unique_complaints, y=names.issue,
                        orientation="h", marker_color="#E879F9",
                        opacity=0.8,
                        customdata=names[["mileage_samples", "median_reported_miles"]].to_numpy(),
                        hovertemplate=(
                            "%{y}: %{x} complaint reports"
                            "<br>Reports with mileage: %{customdata[0]}"
                            "<br>Median reported miles: %{customdata[1]:,.0f}"
                            "<extra></extra>"
                        ),
                    ))
                    hotspot_fig.update_layout(
                        template="plotly_dark", height=max(320, min(540, len(names)*58+145)),
                        paper_bgcolor="rgba(7,14,30,0)",
                        plot_bgcolor="rgba(19,34,56,.23)",
                        xaxis_title="Issue-tagged reports (not failure rates)",
                        margin=dict(l=5, r=10, t=10, b=35),
                        yaxis=dict(automargin=True),
                    )
                    st.plotly_chart(
                        hotspot_fig, use_container_width=True,
                        key="forecast_hotspot_chart",
                    )
                    st.caption(
                        "NHTSA complaint issue counts can overlap. Mileage samples "
                        "are incomplete; this chart does NOT predict when repairs are needed."
                    )
            except (OSError, ValueError, pd.errors.ParserError) as exc:
                st.warning(f"Hotspot evidence unavailable: {exc}")
        else:
            st.info("No historical hotspot dataset currently available.")

    st.markdown("##### Potential scheduled maintenance spending")
    budget = budget_windows(events)
    cols = st.columns(3)
    for col, row in zip(cols, budget.itertuples()):
        with col:
            title = f"Next {row.window_miles//1000}k miles"
            value = (
                f"${row.known_low_usd:,.0f}–${row.known_high_usd:,.0f}"
                if row.priced_events else "Not priced"
            )
            st.metric(title, value)
            st.caption(
                f"{row.priced_events} priced / {row.unpriced_events} unpriced milestones; "
                "known-price subtotal only, not total ownership cost."
            )
    if not events.empty:
        display = events[[
            "task", "event_mileage", "status", "low_usd",
            "high_usd", "price_basis", "price_url", "maintenance_source",
        ]].rename(columns={
            "task": "Service", "event_mileage": "Projected odometer",
            "status": "Limit status", "low_usd": "Reference low ($)",
            "high_usd": "Reference high ($)", "price_basis": "Price basis",
            "price_url": "Price source", "maintenance_source": "OEM schedule",
        })
        st.dataframe(
            display, hide_index=True, use_container_width=True,
            column_config={
                "Price source": st.column_config.LinkColumn(),
                "OEM schedule": st.column_config.LinkColumn(),
            },
        )
    if not time_items.empty:
        with st.expander("Time-based, service-monitor, and history-incomplete tasks"):
            st.dataframe(
                time_items[["task", "status", "documented_interval_months",
                            "source_url"]].rename(columns={
                    "task": "Service", "status": "Assessment",
                    "documented_interval_months": "Time limit (months)",
                    "source_url": "OEM source",
                }),
                hide_index=True, use_container_width=True,
                column_config={"OEM source": st.column_config.LinkColumn()},
            )
    st.download_button(
        "Download maintenance forecast and cost assumptions (CSV)",
        data=events.to_csv(index=False).encode("utf-8"),
        file_name="fleetiq_maintenance_forecast.csv",
        mime="text/csv", key="maintenance_forecast_export",
    )
    st.caption(
        "Published prices are configuration-specific estimates, excluding "
        "potential tax and extra shop fees. Unpriced events are excluded, "
        "not counted as free. A maintenance ceiling is not a guaranteed "
        "failure or a repair prediction. Entering service history is optional."
    )

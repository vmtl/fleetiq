"""Age-matched NHTSA complaint patterns for FleetIQ.

Counts are unique ODI reports, not vehicle failure rates. Model-year age is
approximate; actual manufacture, sale, and in-service dates are unknown.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_age_matched_comparison(complaints, palette=None):
    st.markdown("#### Age-matched complaint comparison")
    st.caption(
        "Compare complaints at the same approximate vehicle age and model years. "
        "Counts are reports, not failure probabilities."
    )
    needed = {"vehicle", "model_year", "odi_number", "received_date", "component", "mileage"}
    if not needed.issubset(complaints.columns):
        st.warning("Age comparison requires vehicle, model year, ODI number, date, component, and mileage.")
        return
    data = complaints.copy()
    data["model_year"] = pd.to_numeric(data["model_year"], errors="coerce")
    data["received_date"] = pd.to_datetime(data["received_date"], errors="coerce")
    data = data.dropna(subset=["vehicle", "model_year", "odi_number", "received_date"])
    data["model_year"] = data["model_year"].astype(int)
    data["approx_age"] = data["received_date"].dt.year - data["model_year"]
    data = data[data["approx_age"].between(0, 15)].copy()
    if data.empty:
        st.info("No complaints with usable model-year and received-date pairs.")
        return

    latest_year = int(data["received_date"].dt.year.max())
    # Do not compare cohorts that have not had the full observation window.
    max_age = st.slider("Compare through approximate age (years)", 1, 8, 3, key="age_compare_max")
    mature_years = sorted(
        y for y in data["model_year"].unique()
        if y + max_age < latest_year
    )
    if not mature_years:
        st.info("No model-year cohorts have completed the selected observation window.")
        return
    earliest = min(mature_years)
    latest = max(mature_years)
    initial_start = max(earliest, 2018)
    initial_end = min(latest, 2021)
    if initial_start > initial_end:
        initial_start, initial_end = earliest, latest
    year_range = st.slider(
        "Model-year cohorts (same range for every vehicle)",
        min_value=earliest, max_value=latest,
        value=(initial_start, initial_end),
        key="age_compare_cohorts",
    )
    options = sorted(data["vehicle"].unique().tolist())
    defaults = [v for v in ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express") if v in options]
    selected = st.multiselect(
        "Vehicles (up to 6)", options, default=defaults[:4] or options[:2],
        max_selections=6, key="age_compare_vehicles",
    )
    if not selected:
        st.info("Choose vehicles to compare.")
        return

    subset = data[
        data["vehicle"].isin(selected)
        & data["model_year"].between(*year_range)
        & data["approx_age"].between(0, max_age)
    ].copy()
    # Avoid counting multiple component rows as multiple complaints.
    unique = subset.drop_duplicates(["vehicle", "model_year", "odi_number", "approx_age"])
    age_counts = (
        unique.groupby(["vehicle", "approx_age"])["odi_number"]
        .nunique().unstack("vehicle")
        .reindex(range(max_age + 1))
    )
    fig = go.Figure()
    colors = palette or ["#00F5D4", "#E879F9", "#00BFFF", "#FBBF24", "#FF5277", "#B4F000"]
    for i, vehicle in enumerate(selected):
        if vehicle in age_counts:
            fig.add_trace(go.Scatter(
                x=age_counts.index, y=age_counts[vehicle],
                mode="lines+markers", name=vehicle,
                line=dict(color=colors[i % len(colors)], width=3),
                connectgaps=False,
            ))
    fig.update_layout(
        template="plotly_dark", height=390,
        xaxis_title="Approximate age at complaint (calendar years)",
        yaxis_title="Distinct NHTSA complaints",
        margin=dict(l=20, r=20, t=25, b=25),
        hovermode="x unified",
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Included model years: {year_range[0]}–{year_range[1]}; "
        f"latest complaint year in the loaded dataset: {latest_year}. "
        "Only model years with a completed observation window are selectable. "
        "A blank point means no matched report in this dataset, not verified zero incidents. "
        "Approximate age uses complaint calendar year minus vehicle model year."
    )
    totals = (
        unique.groupby("vehicle")["odi_number"].nunique()
        .reindex(selected).rename("Unique complaints")
        .reset_index().rename(columns={"vehicle": "Vehicle"})
    )
    st.dataframe(totals, hide_index=True, use_container_width=True)
    st.markdown("##### Reported components and mileage")
    component_counts = (
        subset.drop_duplicates(["vehicle", "odi_number", "component"])
        .groupby(["vehicle", "component"])["odi_number"].nunique()
        .reset_index(name="Unique complaints mentioning component")
        .sort_values("Unique complaints mentioning component", ascending=False)
    )
    st.dataframe(component_counts.groupby("vehicle", group_keys=False).head(5),
                 hide_index=True, use_container_width=True)
    mileage = (
        subset.assign(mileage=pd.to_numeric(subset["mileage"], errors="coerce"))
        .query("mileage > 0")
        .groupby(["vehicle", "odi_number"], as_index=False)["mileage"].median()
        .groupby("vehicle")["mileage"].agg(["count", "median"])
        .rename(columns={"count": "Mileage samples", "median": "Median reported miles"})
        .reindex(selected)
    )
    st.dataframe(mileage, use_container_width=True)
    st.caption(
        "Different sales volumes, usage intensity, and reporting behavior still affect "
        "complaint counts. Reported mileage is optional and not representative of all vehicles."
    )

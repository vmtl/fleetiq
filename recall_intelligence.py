"""FleetIQ official NHTSA recall lookups.

NHTSA make/model/year results are campaigns, NOT proof that a particular VIN
has an outstanding recall. Data is fetched on demand and never fabricated.
"""
from __future__ import annotations

from urllib.parse import urlencode
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

RECALL_ENDPOINT = "https://api.nhtsa.gov/recalls/recallsByVehicle"
MODELS = {
    "Ford Transit": ("Ford", "Transit"),
    "Ram ProMaster": ("Ram", "ProMaster"),
    "Mercedes Sprinter": ("Mercedes-Benz", "Sprinter"),
    "Chevrolet Express": ("Chevrolet", "Express"),
}
REQUIRED_FIELDS = {
    "NHTSACampaignNumber", "Component", "Summary", "Consequence", "Remedy",
}
DISPLAY_FIELDS = {
    "NHTSACampaignNumber": "Campaign",
    "ReportReceivedDate": "Reported date",
    "Component": "System",
    "Manufacturer": "Manufacturer",
    "Summary": "Recall summary",
    "Consequence": "Safety consequence",
    "Remedy": "Manufacturer remedy",
    "Notes": "Additional notes",
}


def recall_query_url(vehicle: str, model_year: int) -> str:
    if vehicle not in MODELS:
        raise ValueError("Unsupported recall vehicle")
    if not 1980 <= int(model_year) <= 2030:
        raise ValueError("Invalid model year")
    make, model = MODELS[vehicle]
    return RECALL_ENDPOINT + "?" + urlencode({
        "make": make, "model": model, "modelYear": int(model_year)
    })


def parse_recall_response(payload: dict) -> pd.DataFrame:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("NHTSA response is missing a results list")
    results = payload["results"]
    if results and not all(isinstance(row, dict) for row in results):
        raise ValueError("NHTSA results contain malformed recall rows")
    if results and not REQUIRED_FIELDS.issubset(set(results[0])):
        raise ValueError("NHTSA returned an unexpected recall schema")
    if not results:
        return pd.DataFrame(columns=list(DISPLAY_FIELDS))
    records = pd.DataFrame(results)
    for col in DISPLAY_FIELDS:
        if col not in records:
            records[col] = ""
    for col in DISPLAY_FIELDS:
        records[col] = records[col].fillna("").astype(str)
    records = records.drop_duplicates(subset=["NHTSACampaignNumber"])
    return records[list(DISPLAY_FIELDS)].reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recalls(url: str) -> pd.DataFrame:
    response = requests.get(
        url, timeout=14, headers={"Accept": "application/json", "User-Agent": "FleetIQ/1.0"}
    )
    response.raise_for_status()
    return parse_recall_response(response.json())


def component_summary(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame(columns=["Component", "Campaigns"])
    return (
        records.groupby("Component", dropna=False)["NHTSACampaignNumber"]
        .nunique().sort_values(ascending=False)
        .rename("Campaigns").reset_index()
    )


def render_recall_tab() -> None:
    st.markdown("#### Recall & Safety Intelligence")
    st.caption(
        "Official NHTSA safety campaigns by make, model and model year. "
        "Campaign listings do not show whether an individual vehicle has "
        "an OPEN recall; confirm with the official VIN lookup."
    )
    a, b = st.columns([2, 1])
    with a:
        vehicle = st.selectbox("Vehicle platform", list(MODELS), key="recall_van")
    with b:
        year = st.number_input("Model year", 2014, 2026, 2020, key="recall_year")
    url = recall_query_url(vehicle, int(year))
    st.markdown("[Check open recalls by VIN on NHTSA](https://www.nhtsa.gov/recalls)")
    st.caption(
        "VINs are not collected or retained by FleetIQ. The external NHTSA "
        "VIN lookup determines whether a specific vehicle has an outstanding recall."
    )
    if st.button("Look up official recall campaigns", key="recall_lookup", type="primary"):
        try:
            with st.spinner("Checking NHTSA for the selected make, model and year..."):
                st.session_state["recall_lookup_data"] = {
                    "url": url, "frame": fetch_recalls(url)
                }
        except (requests.RequestException, ValueError) as exc:
            st.session_state.pop("recall_lookup_data", None)
            st.error(
                "NHTSA could not be reached or returned an unexpected response. "
                f"Try again or use the official link. Details: {exc}"
            )
    saved = st.session_state.get("recall_lookup_data")
    if not saved or saved["url"] != url:
        st.info("Select the vehicle and year, then run the official recall lookup.")
        return
    records = saved["frame"]
    if records.empty:
        st.info(
            "NHTSA returned no campaigns for this make/model/year lookup. "
            "This does not establish that any specific VIN has no outstanding recalls."
        )
        return
    st.metric("NHTSA recall campaigns returned", f"{len(records):,}")
    summary = component_summary(records)
    fig = px.bar(
        summary.head(12).sort_values("Campaigns"),
        x="Campaigns", y="Component", orientation="h",
        color_discrete_sequence=["#FF5277"],
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(7,14,30,0)",
        plot_bgcolor="rgba(19,34,56,.23)",
        margin=dict(l=10, r=10, t=10, b=30),
        height=max(320, min(650, len(summary) * 45 + 120)),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("##### Official campaign details")
    for row in records.itertuples(index=False):
        campaign = row.NHTSACampaignNumber
        with st.expander(f"{campaign} · {row.Component}"):
            st.write("**Manufacturer:**", row.Manufacturer or "Not provided")
            st.write("**Reported:**", row.ReportReceivedDate or "Not provided")
            st.write("**Summary:**", row.Summary or "Not provided")
            st.write("**Safety consequence:**", row.Consequence or "Not provided")
            st.write("**Remedy:**", row.Remedy or "Not provided")
            if row.Notes:
                st.write("**Notes:**", row.Notes)
    st.download_button(
        "Download official model-level recall campaigns (CSV)",
        records.rename(columns=DISPLAY_FIELDS).to_csv(index=False).encode("utf-8"),
        "fleetiq_nhtsa_recalls.csv", mime="text/csv", key="recall_export",
    )
    st.caption(
        f"Source: NHTSA recallsByVehicle API, queried for {year} {vehicle}. "
        "These results reflect the last successful lookup in this session "
        "(cached for up to one hour); a campaign may affect only certain VINs."
    )

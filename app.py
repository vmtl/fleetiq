
import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="FleetIQ",
    page_icon="🚐",
    layout="wide"
)

st.title("FleetIQ")
st.subheader("Cargo Van Reliability Intelligence")

st.caption(
    "Vehicle safety complaints and recalls from NHTSA. "
    "Complaint counts are not mechanical failure rates."
)

@st.cache_data(ttl=86400)
def fetch_nhtsa(endpoint, make, model, year):
    url = f"https://api.nhtsa.gov/{endpoint}"

    response = requests.get(
        url,
        params={
            "make": make,
            "model": model,
            "modelYear": year
        },
        timeout=30
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("results", [])

vehicles = {
    "Ford Transit": ("Ford", "Transit"),
    "Ram ProMaster": ("RAM", "ProMaster"),
    "Mercedes-Benz Sprinter": ("Mercedes-Benz", "Sprinter")
}

vehicle = st.selectbox(
    "Select cargo van",
    list(vehicles.keys())
)

year = st.selectbox(
    "Select model year",
    list(range(2026, 2013, -1))
)

make, model = vehicles[vehicle]

try:
    complaints = fetch_nhtsa(
        "complaints/complaintsByVehicle",
        make, model, year
    )
    recalls = fetch_nhtsa(
        "recalls/recallsByVehicle",
        make, model, year
    )

    col1, col2 = st.columns(2)
    col1.metric("Reported Complaints", len(complaints))
    col2.metric("Recall Records", len(recalls))

    tab1, tab2 = st.tabs(["Complaints", "Recalls"])

    with tab1:
        st.dataframe(
            pd.DataFrame(complaints),
            use_container_width=True
        )

    with tab2:
        st.dataframe(
            pd.DataFrame(recalls),
            use_container_width=True
        )

except requests.RequestException as error:
    st.error(f"Could not retrieve NHTSA data: {error}")


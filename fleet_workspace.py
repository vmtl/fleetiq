"""Privacy-conscious fleet workspace prototype.

Records exist only inside each Streamlit session and locally exported CSV
archives. This is NOT multi-user durable storage, an authenticated SaaS
backend, or a regulated maintenance compliance system.
"""
from __future__ import annotations
import io
import zipfile
from datetime import date

import pandas as pd
import streamlit as st

VEHICLES = ("Ford Transit", "Ram ProMaster", "Mercedes Sprinter", "Chevrolet Express")
ASSET_COLS = ["asset_id", "vehicle", "model_year", "odometer", "status"]
SERVICE_COLS = ["asset_id", "service_date", "service_miles", "operation", "cost_usd", "downtime_days"]
MAX_ROWS = 3000


def empty_assets() -> pd.DataFrame:
    return pd.DataFrame(columns=ASSET_COLS)


def empty_services() -> pd.DataFrame:
    return pd.DataFrame(columns=SERVICE_COLS)


def clean_assets(frame: pd.DataFrame) -> pd.DataFrame:
    """Enforce limited schema; never export arbitrary uploaded columns."""
    if set(ASSET_COLS) - set(frame.columns):
        raise ValueError("Fleet file is missing required vehicle fields")
    if len(frame) > MAX_ROWS:
        raise ValueError("Fleet record limit exceeded")
    df = frame[ASSET_COLS].copy().fillna("")
    df["asset_id"] = df["asset_id"].astype(str).str.strip()
    df["vehicle"] = df["vehicle"].astype(str).str.strip()
    df["status"] = df["status"].astype(str).str.strip()
    if df.asset_id.eq("").any() or df.asset_id.duplicated().any():
        raise ValueError("Fleet IDs must be nonempty and unique")
    if (~df.vehicle.isin(VEHICLES)).any():
        raise ValueError("Unsupported commercial van platform")
    df["model_year"] = pd.to_numeric(df.model_year, errors="coerce")
    df["odometer"] = pd.to_numeric(df.odometer, errors="coerce")
    if df[["model_year", "odometer"]].isna().any().any():
        raise ValueError("Vehicle year and odometer must be valid numbers")
    if ((df.model_year < 2014) | (df.model_year > 2026)
        | (df.odometer < 0) | (df.odometer % 1 != 0)
        | (df.model_year % 1 != 0)).any():
        raise ValueError("Vehicle year or odometer outside supported bounds")
    df[["model_year", "odometer"]] = df[["model_year", "odometer"]].astype(int)
    if df.status.str.len().gt(60).any() or df.asset_id.str.len().gt(64).any():
        raise ValueError("Fleet label is too long")
    return df.reset_index(drop=True)


def clean_services(frame: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    if set(SERVICE_COLS) - set(frame.columns):
        raise ValueError("Service file missing required fields")
    if len(frame) > MAX_ROWS:
        raise ValueError("Service record limit exceeded")
    df = frame[SERVICE_COLS].copy().fillna("")
    df["asset_id"] = df.asset_id.astype(str).str.strip()
    df["operation"] = df.operation.astype(str).str.strip()
    dates = pd.to_datetime(df.service_date, errors="coerce")
    if dates.isna().any():
        raise ValueError("Service dates must be valid")
    if ((dates.dt.date > date.today())).any():
        raise ValueError("Future completed service dates are not accepted")
    df["service_date"] = dates.dt.strftime("%Y-%m-%d")
    for col in ["service_miles", "cost_usd", "downtime_days"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["service_miles", "cost_usd", "downtime_days"]].isna().any().any():
        raise ValueError("Service mileage, cost and downtime must be numeric")
    if ((df[["service_miles", "cost_usd", "downtime_days"]] < 0).any().any()
        or (df.service_miles % 1 != 0).any()):
        raise ValueError("Service measures must be nonnegative; miles integral")
    limits = assets.set_index("asset_id")["odometer"].to_dict()
    if (~df.asset_id.isin(limits)).any():
        raise ValueError("Service references an unknown vehicle ID")
    if df.apply(lambda r: r.service_miles > limits[r.asset_id], axis=1).any():
        raise ValueError("Service odometer exceeds current vehicle odometer")
    if df.operation.eq("").any() or df.operation.str.len().gt(120).any():
        raise ValueError("Service operation must be 1–120 characters")
    df["service_miles"] = df.service_miles.astype(int)
    return df.reset_index(drop=True)


def safe_csv(frame: pd.DataFrame) -> bytes:
    """Prevent spreadsheet formula injection when user-supplied CSV is opened."""
    out = frame.copy()
    for col in out.select_dtypes(include=["object", "str", "string"]).columns:
        out[col] = out[col].map(
            lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        )
    return out.to_csv(index=False).encode("utf-8")


def export_workspace(assets: pd.DataFrame, services: pd.DataFrame) -> bytes:
    good_assets = clean_assets(assets) if len(assets) else empty_assets()
    good_services = clean_services(services, good_assets) if len(services) else empty_services()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("fleet_vehicles.csv", safe_csv(good_assets))
        z.writestr("fleet_services.csv", safe_csv(good_services))
        z.writestr("README.txt",
                   "FleetIQ local-only workspace. No cloud persistence. "
                   "Keep backups securely; uploaded data is held in your session only.\n")
    return buf.getvalue()


def import_workspace(raw: bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(raw) > 5_000_000:
        raise ValueError("Workspace archive exceeds 5MB")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files = z.namelist()
        if len(files) > 10 or not {"fleet_vehicles.csv", "fleet_services.csv"}.issubset(files):
            raise ValueError("Workspace archive lacks expected CSV files")
        for name in ("fleet_vehicles.csv", "fleet_services.csv"):
            if z.getinfo(name).file_size > 5_000_000:
                raise ValueError("Uncompressed CSV exceeds safe size")
        assets = clean_assets(pd.read_csv(z.open("fleet_vehicles.csv"), keep_default_na=False))
        services = clean_services(
            pd.read_csv(z.open("fleet_services.csv"), keep_default_na=False), assets
        )
    return assets, services


def fleet_metrics(assets: pd.DataFrame, services: pd.DataFrame) -> dict:
    return {
        "vehicles": len(assets),
        "maintenance_records": len(services),
        "recorded_spending": round(pd.to_numeric(services.cost_usd, errors="coerce").sum(), 2)
        if not services.empty else 0.0,
        "recorded_downtime_days": round(pd.to_numeric(
            services.downtime_days, errors="coerce"
        ).sum(), 1) if not services.empty else 0.0,
    }


def render_fleet_workspace() -> None:
    st.markdown("#### Fleet Workspace — session-only pilot")
    st.warning(
        "PILOT, NOT A PRIVATE BUSINESS ACCOUNT: Entries exist only in this browser "
        "session and are NOT saved on the server. Export a backup ZIP before "
        "closing or refreshing. Do not upload sensitive VINs, names, invoices "
        "or regulated business records. Production accounts need authentication, "
        "tenant isolation, backups and a security review."
    )
    if "fleetiq_assets" not in st.session_state:
        st.session_state.fleetiq_assets = empty_assets()
    if "fleetiq_services" not in st.session_state:
        st.session_state.fleetiq_services = empty_services()
    uploaded = st.file_uploader("Import a previous FleetIQ workspace ZIP",
                                type=["zip"], key="fleet_import")
    if uploaded and st.button("Import local workspace", key="fleet_import_apply"):
        try:
            a, s = import_workspace(uploaded.getvalue())
            st.session_state.fleetiq_assets = a
            st.session_state.fleetiq_services = s
            st.success("Workspace loaded for this session.")
        except (ValueError, zipfile.BadZipFile, UnicodeError, KeyError) as exc:
            st.error(f"Import rejected: {exc}")
    st.markdown("##### Fleet vehicles")
    with st.form("fleet_add_vehicle"):
        c1, c2, c3 = st.columns(3)
        asset = c1.text_input("Fleet unit ID (no VIN)", max_chars=64)
        vehicle = c2.selectbox("Vehicle", VEHICLES)
        year = c3.number_input("Model year", 2014, 2026, 2020)
        c4, c5 = st.columns(2)
        odo = c4.number_input("Current odometer", 0, 1000000, 100000, step=500)
        status = c5.selectbox("Operating status", ["Active", "Maintenance", "Unavailable", "Retired"])
        submit = st.form_submit_button("Add fleet vehicle")
    if submit:
        try:
            row = pd.DataFrame([{
                "asset_id": asset, "vehicle": vehicle, "model_year": year,
                "odometer": odo, "status": status,
            }])
            st.session_state.fleetiq_assets = clean_assets(
                pd.concat([st.session_state.fleetiq_assets, row], ignore_index=True)
            )
            st.success("Vehicle added to session workspace.")
        except ValueError as exc:
            st.error(str(exc))
    assets = st.session_state.fleetiq_assets
    if not assets.empty:
        st.dataframe(assets, hide_index=True, use_container_width=True)
        st.caption("To update a vehicle's mileage, export the workspace, edit the vehicle CSV and re-import.")
    st.markdown("##### Completed service / repair records")
    if not assets.empty:
        with st.form("fleet_add_service"):
            col1, col2, col3 = st.columns(3)
            key = col1.selectbox("Fleet unit", assets.asset_id.tolist())
            day = col2.date_input("Service completion date", value=date.today(),
                                  max_value=date.today())
            miles = col3.number_input(
                "Odometer at service", min_value=0,
                max_value=int(assets.set_index("asset_id").loc[key, "odometer"]),
                value=0, step=500,
            )
            col4, col5, col6 = st.columns(3)
            task = col4.text_input("Completed service operation", max_chars=120)
            cost = col5.number_input("Actual invoiced cost ($)", min_value=0.0, value=0.0, step=25.0)
            down = col6.number_input("Downtime days", min_value=0.0, value=0.0, step=0.5)
            add = st.form_submit_button("Record completed service")
        if add:
            try:
                record = pd.DataFrame([{
                    "asset_id": key, "service_date": day.isoformat(),
                    "service_miles": miles, "operation": task,
                    "cost_usd": cost, "downtime_days": down,
                }])
                st.session_state.fleetiq_services = clean_services(
                    pd.concat([st.session_state.fleetiq_services, record], ignore_index=True),
                    assets,
                )
                st.success("Service added to local session history.")
            except ValueError as exc:
                st.error(str(exc))
    services = st.session_state.fleetiq_services
    if not services.empty:
        st.dataframe(services.sort_values("service_date", ascending=False),
                     hide_index=True, use_container_width=True)
    metrics = fleet_metrics(assets, services)
    a, b, c, d = st.columns(4)
    a.metric("Vehicles", metrics["vehicles"])
    b.metric("Service records", metrics["maintenance_records"])
    c.metric("Recorded spending", f"${metrics['recorded_spending']:,.2f}")
    d.metric("Recorded downtime (days)", f"{metrics['recorded_downtime_days']:,.1f}")
    st.download_button(
        "Export complete local workspace ZIP",
        export_workspace(assets, services),
        "fleetiq_workspace.zip", mime="application/zip",
        key="fleet_export",
    )
    st.caption(
        "Fleet entries and completed service records are useful operational "
        "history, but they cannot alone train a failure-prediction model. "
        "Censored exposure observations, verified outcomes and representative "
        "vehicle cohorts are also required."
    )

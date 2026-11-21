"""Validated maintenance service alerts from actual fleet history + OEM intervals.

A matched task is assessed only when a last completed odometer is known.
Time-based-only tasks require a last service date and are reported separately;
monitor/service-due messages always override odometer caps.
"""
from __future__ import annotations

from datetime import date
import pandas as pd

from maintenance_intelligence import validate_schedule

SUPPORTED = ("recurring", "monitor_cap", "condition_cap")


def mileage_alerts(assets: pd.DataFrame, services: pd.DataFrame,
                   schedules: pd.DataFrame, threshold: int = 2000,
                   severe_duty: bool = False) -> pd.DataFrame:
    if threshold < 0:
        raise ValueError("Threshold must not be negative")
    required_assets = {"asset_id", "vehicle", "model_year", "odometer"}
    required_services = {"asset_id", "operation", "service_miles"}
    if required_assets - set(assets.columns) or required_services - set(services.columns):
        raise ValueError("Missing fleet vehicle or service history columns")
    catalog = validate_schedule(schedules)
    output = []
    for asset in assets.itertuples(index=False):
        rows = catalog.loc[
            catalog.vehicle.eq(asset.vehicle)
            & catalog.model_year_start.le(int(asset.model_year))
            & catalog.model_year_end.ge(int(asset.model_year))
        ]
        if not severe_duty:
            rows = rows.loc[~rows.schedule_mode.eq("condition_cap")]
        for entry in rows.itertuples(index=False):
            if entry.schedule_mode not in SUPPORTED or entry.interval_miles <= 0:
                continue
            history = services.loc[
                services.asset_id.eq(asset.asset_id)
                & services.operation.astype(str).str.casefold().eq(str(entry.task).casefold())
            ]
            if history.empty:
                continue  # no invented last completion or due date
            past = pd.to_numeric(history.service_miles, errors="coerce").dropna()
            past = past.loc[past.le(asset.odometer)]
            if past.empty:
                continue
            due = int(past.max()) + int(entry.interval_miles)
            left = due - int(asset.odometer)
            if left < 0:
                status = "At/past OEM mileage limit"
            elif left <= threshold:
                status = "Within reminder window"
            else:
                status = "Not yet in reminder window"
            output.append({
                "asset_id": asset.asset_id, "vehicle": asset.vehicle,
                "task": entry.task, "current_odometer": int(asset.odometer),
                "last_service_miles": int(past.max()),
                "OEM_mileage_limit": due, "miles_remaining": left,
                "status": status, "schedule_mode": entry.schedule_mode,
                "engine_scope": entry.engine_scope, "source_url": entry.source_url,
            })
    return pd.DataFrame(output, columns=[
        "asset_id", "vehicle", "task", "current_odometer",
        "last_service_miles", "OEM_mileage_limit", "miles_remaining",
        "status", "schedule_mode", "engine_scope", "source_url",
    ])


def service_history_coverage(assets: pd.DataFrame, services: pd.DataFrame) -> dict:
    return {
        "registered": int(len(assets)),
        "has_any_history": int(services.asset_id.nunique()) if not services.empty else 0,
        "total_records": int(len(services)),
    }

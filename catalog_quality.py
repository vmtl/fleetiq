"""Maintenance reference integrity and honest source confidence assessment.

Checks never equate existence of a URL with independent verification of its
contents. Verification requires a reviewer and a documented manual page.
"""
from __future__ import annotations

import pandas as pd

REQUIRED = {
    "vehicle", "model_year_start", "model_year_end", "task", "interval_miles",
    "interval_months", "schedule_mode", "operating_condition", "engine_scope",
    "source_url", "source_name", "source_section", "notes", "reviewed_on",
}


def audit_maintenance_catalog(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if missing := REQUIRED - set(frame.columns):
        raise ValueError("Maintenance dataset missing: " + ", ".join(sorted(missing)))
    items = frame.copy().reset_index(drop=True)
    issues = []
    for idx, row in items.iterrows():
        identifiers = {
            "row_number": idx + 2,
            "vehicle": str(row["vehicle"]),
            "model_year": str(row["model_year_start"]),
            "task": str(row["task"]),
        }
        def issue(code, note):
            issues.append({**identifiers, "issue_code": code, "detail": note})
        try:
            start = int(row["model_year_start"])
            end = int(row["model_year_end"])
            miles = int(row["interval_miles"])
            months = int(row["interval_months"])
            if start > end or miles < 0 or months < 0:
                issue("invalid_range", "Invalid model-year or interval")
        except (TypeError, ValueError):
            issue("invalid_numeric", "Nonintegral year or interval")
        if not str(row["source_url"]).startswith("https://"):
            issue("missing_source", "Official or explanatory HTTPS reference required")
        if not str(row["source_section"]).strip() or str(row["source_section"]).lower() == "nan":
            issue("missing_section", "Record exact source page or chapter")
        if not str(row["engine_scope"]).strip() or str(row["engine_scope"]).lower() == "nan":
            issue("missing_configuration", "Engine or equipment applicability missing")
        if not str(row["operating_condition"]).strip() or str(row["operating_condition"]).lower() == "nan":
            issue("missing_duty", "Normal/severe/monitor condition missing")
        if str(row["schedule_mode"]) not in {
            "recurring", "monitor_cap", "condition_cap", "monitor_event", "advisory"
        }:
            issue("invalid_mode", "Unknown schedule semantics")
    groups = [
        "vehicle", "model_year_start", "model_year_end",
        "task", "operating_condition", "engine_scope",
    ]
    for _, duplicate in items.loc[items.duplicated(groups, keep=False)].iterrows():
        issues.append({
            "row_number": int(duplicate.name) + 2,
            "vehicle": str(duplicate["vehicle"]),
            "model_year": str(duplicate["model_year_start"]),
            "task": str(duplicate["task"]),
            "issue_code": "duplicate_scope",
            "detail": "Duplicate task with identical year, powertrain and duty scope",
        })
    # Review flags, not verified content claims.
    items["source_link_present"] = items.source_url.astype(str).str.startswith("https://")
    items["manual_scope_recorded"] = (
        items.source_section.astype(str).str.strip().ne("")
        & items.engine_scope.astype(str).str.strip().ne("")
        & items.operating_condition.astype(str).str.strip().ne("")
    )
    items["independently_certified"] = False
    items["review_status"] = "Documented reference — full configuration audit pending"
    return items, pd.DataFrame(
        issues, columns=["row_number","vehicle","model_year","task","issue_code","detail"]
    )


def year_counts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["vehicle", "year", "documented_operations"])
    rows = []
    for x in frame.itertuples(index=False):
        for year in range(int(x.model_year_start), int(x.model_year_end) + 1):
            rows.append({"vehicle": x.vehicle, "year": year, "task": x.task})
    records = pd.DataFrame(rows)
    return (
        records.groupby(["vehicle", "year"])["task"].nunique()
        .rename("documented_operations").reset_index()
    )

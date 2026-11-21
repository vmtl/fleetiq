"""Research-only survival analysis for verified fleet outcomes.

DO NOT use NHTSA complaint rows or public symptom charts to train this
model. No public reliability risk forecast is produced by FleetIQ.

This Kaplan–Meier prototype supports delayed-entry mileage (left truncation)
and right-censored repair exposures. It is NOT validated for production use.
"""
from __future__ import annotations

import math
import pandas as pd

REQUIRED = {
    "asset_id", "vehicle", "model_year", "system", "entry_miles",
    "exit_miles", "event_observed", "outcome_verified",
}


def validate_cohort(frame: pd.DataFrame, min_vehicles: int = 100,
                    min_events: int = 25, min_censored: int = 25) -> pd.DataFrame:
    if missing := REQUIRED - set(frame.columns):
        raise ValueError("Verified outcome dataset missing: " + ", ".join(sorted(missing)))
    work = frame[list(REQUIRED)].copy()
    if work.empty:
        raise ValueError("No records in verified repair-outcome cohort")
    if work[list(["asset_id", "vehicle", "system"])].isna().any().any():
        raise ValueError("Missing fleet, vehicle, or system identifiers")
    if work.duplicated(["asset_id", "system"]).any():
        raise ValueError("Only one event or censoring endpoint per asset/system")
    for field in ("model_year", "entry_miles", "exit_miles", "event_observed"):
        work[field] = pd.to_numeric(work[field], errors="coerce")
    if work[["model_year","entry_miles","exit_miles","event_observed"]].isna().any().any():
        raise ValueError("Invalid missing or nonnumeric mileage, year or outcome")
    if (~work.event_observed.isin([0, 1])).any():
        raise ValueError("event_observed must be 0 (censored) or 1 (verified repair)")
    if (work.entry_miles < 0).any() or (work.exit_miles <= work.entry_miles).any():
        raise ValueError("Each vehicle must have positive exposure after entry")
    if not work.outcome_verified.astype(str).str.lower().isin(["true", "1"]).all():
        raise ValueError("Repair/censoring evidence has not been source-verified")
    if work.model_year.lt(1980).any() or work.model_year.gt(2100).any():
        raise ValueError("Model year outside plausible bounds")
    # Never pool dissimilar vehicle platforms or mechanical systems by default.
    if work.vehicle.nunique() != 1 or work.system.nunique() != 1:
        raise ValueError("Cohort must refer to one vehicle platform and one outcome system")
    failures = int(work.event_observed.eq(1).sum())
    censored = int(work.event_observed.eq(0).sum())
    if len(work) < min_vehicles or failures < min_events or censored < min_censored:
        raise ValueError(
            f"Insufficient exposure and events: {len(work)} vehicles; "
            f"{failures} verified repairs; {censored} right-censored observations"
        )
    return work


def kaplan_meier_mileage(frame: pd.DataFrame,
                         min_vehicles: int = 100,
                         min_events: int = 25,
                         min_censored: int = 25) -> pd.DataFrame:
    """Left-truncated risk sets at observed failure mileages.

    This is a research estimate conditioned on cohort entry and subject to
    selection bias. It is not automatically a general-market risk estimate.
    """
    cohort = validate_cohort(frame, min_vehicles, min_events, min_censored)
    times = sorted(cohort.loc[cohort.event_observed.eq(1), "exit_miles"].unique())
    survival = 1.0
    greenwood = 0.0
    output = []
    for t in times:
        at_risk = int(
            (cohort.entry_miles.le(t) & cohort.exit_miles.ge(t)).sum()
        )
        failures = int(
            (cohort.event_observed.eq(1) & cohort.exit_miles.eq(t)).sum()
        )
        if at_risk < failures or at_risk <= 0:
            raise ValueError("Invalid left-truncated risk set")
        survival *= 1 - failures / at_risk
        if at_risk > failures:
            greenwood += failures / (at_risk * (at_risk - failures))
            variance = survival * survival * greenwood
        else:
            # No at-risk vehicles remain after all failed at this mileage.
            variance = 0.0
        output.append({
            "mileage": float(t), "at_risk": at_risk,
            "verified_repairs": failures, "estimated_survival": survival,
            "greenwood_variance": variance,
        })
    return pd.DataFrame(output)


def research_readiness_note() -> str:
    return (
        "Research only. Cohort inclusion, representativeness, censoring, repair "
        "classification, left-truncation assumptions, independent holdout, "
        "calibration, uncertainty and drift must be evaluated before deployment. "
        "NHTSA consumer complaints are not repair outcome data."
    )

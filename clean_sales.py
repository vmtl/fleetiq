"""FleetIQ sales dataset cleaning and data-quality validation.

Run from repository root:
    python clean_sales.py

Reads data/sales.csv; writes data/sales_clean.csv and
 data/sales_quality_report.json. Never overwrites the source file.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED = ["vehicle", "calendar_year", "us_sales", "source_name", "source_url", "notes"]
STATUSES = {"source_reported_model_family", "previously_sourced_needs_revalidation", "not_yet_verified"}


def clean(input_file: Path, output_file: Path, report_file: Path, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    df = pd.read_csv(input_file, dtype="string", keep_default_na=False)
    absent = set(REQUIRED) - set(df.columns)
    if absent:
        raise ValueError(f"Missing required columns: {', '.join(sorted(absent))}")
    df = df[REQUIRED].copy()
    for col in ["vehicle", "source_name", "source_url", "notes"]:
        df[col] = df[col].str.strip().str.replace(r"\s+", " ", regex=True)
    df["vehicle"] = df["vehicle"].str.replace(r"\s+", " ", regex=True)
    df["calendar_year"] = pd.to_numeric(df["calendar_year"], errors="coerce").astype("Int64")
    df["us_sales"] = pd.to_numeric(df["us_sales"].str.replace(",", "", regex=False), errors="coerce")

    # Preserve exact original row count; never discard uncertain data.
    df["source_status"] = df["notes"].str.extract(r"Status:\s*([a-z_]+)", expand=False).fillna("status_missing")
    df["source_status"] = df["source_status"].where(df["source_status"].isin(STATUSES), "status_missing_or_unknown")
    # Evidence ledger is independent of third-party source labels.
    ledger_path = input_file.parent / "sales_verification.csv"
    df["source_verification_status"] = "not_audited"
    if ledger_path.exists():
        audit = pd.read_csv(ledger_path, dtype="string", keep_default_na=False)
        required_audit = {"vehicle", "calendar_year", "validated_sales", "status"}
        if not required_audit.issubset(audit.columns):
            raise ValueError("Sales verification ledger is missing mandatory columns")
        audit["calendar_year"] = pd.to_numeric(audit["calendar_year"], errors="raise").astype("Int64")
        audit["validated_sales"] = pd.to_numeric(audit["validated_sales"], errors="raise")
        if audit.duplicated(["vehicle", "calendar_year"]).any():
            raise ValueError("Duplicate vehicle-year combinations in verification ledger")
        temp = df[["vehicle", "calendar_year", "us_sales"]].merge(
            audit[["vehicle", "calendar_year", "validated_sales", "status"]],
            on=["vehicle", "calendar_year"], how="left", validate="one_to_one"
        )
        mismatched = temp["validated_sales"].notna() & temp["us_sales"].ne(temp["validated_sales"]).fillna(True)
        if mismatched.any():
            raise ValueError("Verified sales ledger disagrees with source sales.csv; reconcile before cleaning")
        df["source_verification_status"] = temp["status"].fillna("not_audited").replace("", "not_audited").values
    df["source_verified"] = df["source_verification_status"].isin(
        ["verified_manufacturer", "corrected_manufacturer"]
    )

    df["sales_available"] = df["us_sales"].notna()
    df["is_zero_sales"] = df["sales_available"] & df["us_sales"].eq(0)
    df["is_complete_calendar_year"] = df["calendar_year"].lt(as_of.year).fillna(False)
    df["is_future_year"] = df["calendar_year"].gt(as_of.year).fillna(False)
    df["needs_source_revalidation"] = df["source_status"].ne("source_reported_model_family")
    df["has_source_reference"] = df["source_name"].ne("") & df["source_url"].str.match(r"^https?://", na=False)
    df["valid_sales_value"] = df["us_sales"].isna() | ((df["us_sales"] >= 0) & df["us_sales"].mod(1).eq(0))
    df["valid_year"] = df["calendar_year"].between(1900, as_of.year + 1).fillna(False)

    def row_flags(row: pd.Series) -> str:
        flags = []
        if not row["valid_year"]: flags.append("invalid_year")
        if not row["valid_sales_value"]: flags.append("invalid_sales_value")
        if not row["sales_available"]: flags.append("sales_missing")
        if row["is_zero_sales"]: flags.append("reported_zero_check_source")
        if row["sales_available"] and not row["has_source_reference"]: flags.append("missing_source_reference")
        if row["sales_available"] and row["needs_source_revalidation"]: flags.append("source_revalidation_needed")
        if row["sales_available"] and not row["is_complete_calendar_year"]: flags.append("partial_or_future_calendar_year")
        if not row["vehicle"]: flags.append("vehicle_missing")
        return "; ".join(flags)

    df["quality_flags"] = df.apply(row_flags, axis=1)
    duplicated = df.duplicated(subset=["vehicle", "calendar_year"], keep=False)
    df.loc[duplicated, "quality_flags"] = df.loc[duplicated, "quality_flags"].apply(
        lambda x: f"{x}; duplicate_vehicle_year" if x else "duplicate_vehicle_year"
    )
    df["ready_for_full_year_comparison"] = (
        df["sales_available"] & df["valid_sales_value"] & df["valid_year"]
        & df["is_complete_calendar_year"] & df["has_source_reference"]
        & ~df["needs_source_revalidation"] & ~duplicated
        & df["vehicle"].ne("")
    )
    # A formerly provisional row can become verified after its manufacturer
    # evidence is recorded. Do not require the old notes-derived source label.
    df["verified_for_comparison"] = (
        df["sales_available"] & df["valid_sales_value"] & df["valid_year"]
        & df["is_complete_calendar_year"] & df["has_source_reference"]
        & df["source_verified"] & ~duplicated & df["vehicle"].ne("")
    )
    df = df.sort_values(["vehicle", "calendar_year"], kind="stable", na_position="last")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    report = {
        "as_of_date": as_of.isoformat(),
        "input_file": str(input_file),
        "output_file": str(output_file),
        "total_rows": int(len(df)),
        "platforms": int(df["vehicle"].nunique()),
        "populated_sales": int(df["sales_available"].sum()),
        "missing_sales": int((~df["sales_available"]).sum()),
        "reported_zero_sales": int(df["is_zero_sales"].sum()),
        "duplicate_vehicle_year_rows": int(duplicated.sum()),
        "invalid_year_rows": int((~df["valid_year"]).sum()),
        "invalid_sales_value_rows": int((~df["valid_sales_value"]).sum()),
        "populated_values_needing_source_revalidation": int((df["sales_available"] & df["needs_source_revalidation"]).sum()),
        "populated_current_or_future_year_values": int((df["sales_available"] & ~df["is_complete_calendar_year"]).sum()),
        "ready_for_full_year_comparison": int(df["ready_for_full_year_comparison"].sum()),
        "source_verified_sales_rows": int((df["sales_available"] & df["source_verified"]).sum()),
        "verified_for_comparison": int(df["verified_for_comparison"].sum()),
        "verification_status_counts": {str(k): int(v) for k, v in df["source_verification_status"].value_counts().items()},

        "source_status_counts": {str(k): int(v) for k,v in df["source_status"].value_counts().items()},
        "year_coverage": [
            {"year": int(y), "total_rows": int(len(g)), "populated_sales": int(g["sales_available"].sum())}
            for y,g in df.dropna(subset=["calendar_year"]).groupby("calendar_year", sort=True)
        ],
        "interpretation": "Ready means structurally suitable for full-year comparison based on existing labels. It is not independent verification of source accuracy or comparable vehicle definitions."
    }
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/sales.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/sales_clean.csv"))
    parser.add_argument("--report", type=Path, default=Path("data/sales_quality_report.json"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD")
    args = parser.parse_args()
    print(json.dumps(clean(args.input, args.output, args.report, args.as_of), indent=2))

if __name__ == "__main__":
    main()

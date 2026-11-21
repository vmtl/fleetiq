"""Regression tests for FleetIQ sales evidence ledger."""
from datetime import date
from pathlib import Path
import pandas as pd
import pytest

from clean_sales import clean

def _write_inputs(tmp_path: Path, sales: int = 100, ledger: int = 100) -> Path:
    src = tmp_path / "sales.csv"
    pd.DataFrame([{
        "vehicle": "Ram ProMaster", "calendar_year": 2024,
        "us_sales": sales, "source_name": "FCA",
        "source_url": "https://example.com/fca", "notes": "Status: previously_sourced_needs_revalidation"
    }]).to_csv(src, index=False)
    pd.DataFrame([{
        "vehicle": "Ram ProMaster", "calendar_year": 2024,
        "original_sales": 99, "validated_sales": ledger,
        "status": "corrected_manufacturer",
        "evidence_source": "FCA", "evidence_url": "https://example.com/fca"
    }]).to_csv(tmp_path / "sales_verification.csv", index=False)
    return src

def test_manufacturer_verified_overrides_legacy_status(tmp_path):
    src = _write_inputs(tmp_path)
    report = clean(src, tmp_path / "clean.csv", tmp_path / "quality.json", date(2026, 11, 21))
    df = pd.read_csv(tmp_path / "clean.csv")
    assert bool(df.loc[0, "source_verified"])
    assert bool(df.loc[0, "verified_for_comparison"])
    assert report["source_verified_sales_rows"] == 1
    assert report["verified_for_comparison"] == 1

def test_source_mismatch_refuses_publication(tmp_path):
    src = _write_inputs(tmp_path, sales=100, ledger=101)
    with pytest.raises(ValueError, match="ledger disagrees"):
        clean(src, tmp_path / "clean.csv", tmp_path / "quality.json", date(2026, 11, 21))

def test_partial_year_cannot_be_verified_full_year(tmp_path):
    src = _write_inputs(tmp_path)
    sales = pd.read_csv(src)
    sales.loc[0, "calendar_year"] = 2026
    sales.to_csv(src, index=False)
    ledger = pd.read_csv(tmp_path / "sales_verification.csv")
    ledger.loc[0, "calendar_year"] = 2026
    ledger.loc[0, "status"] = "partial_year"
    ledger.to_csv(tmp_path / "sales_verification.csv", index=False)
    report = clean(src, tmp_path / "clean.csv", tmp_path / "quality.json", date(2026, 11, 21))
    assert report["verified_for_comparison"] == 0

def test_duplicate_verification_rows_rejected(tmp_path):
    src = _write_inputs(tmp_path)
    ledger = pd.read_csv(tmp_path / "sales_verification.csv")
    pd.concat([ledger, ledger]).to_csv(tmp_path / "sales_verification.csv", index=False)
    with pytest.raises(ValueError, match="Duplicate vehicle-year"):
        clean(src, tmp_path / "clean.csv", tmp_path / "quality.json", date(2026, 11, 21))

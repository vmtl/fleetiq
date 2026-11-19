
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

SOURCE_URL = (
    "https://static.nhtsa.gov/odi/ffdd/cmpl/"
    "FLAT_CMPL.zip"
)

OUTPUT = Path("data")
CURRENT_YEAR = datetime.now(timezone.utc).year
MIN_YEAR = CURRENT_YEAR - 11

# Cargo-van model classification.
# Expand after checking model names in the bulk dataset.
VAN_PATTERNS = {
    "Ford Transit": r"^TRANSIT(?:[- ](?:150|250|350|350HD))?$",
    "Ford Transit Connect": r"^TRANSIT CONNECT$",
    "Ford E-Transit": r"^E[- ]?TRANSIT$",
    "Ram ProMaster": r"^PROMASTER(?:[- ](?:1500|2500|3500))?$",
    "Ram ProMaster City": r"^PROMASTER CITY$",
    "Mercedes Sprinter": r"^SPRINTER(?:[- ].*)?$",
    "Mercedes Metris": r"^METRIS$",
    "Chevrolet Express": r"^EXPRESS(?:[- ].*)?$",
    "Chevrolet City Express": r"^CITY EXPRESS$",
    "GMC Savana": r"^SAVANA(?:[- ].*)?$",
    "Nissan NV": r"^NV(?:1500|2500|3500)(?: HD)?$",
    "Nissan NV200": r"^NV200$",
}

# Zero-based field positions from NHTSA CMPL.txt
FIELDS = {
    1: "odi_number",
    3: "make",
    4: "model",
    5: "model_year",
    6: "crash",
    8: "fire",
    9: "injuries",
    10: "deaths",
    11: "component",
    16: "date_received",
    17: "mileage",
    19: "description",
    45: "product_type",
}

def classify(model):
    model = str(model).strip().upper()
    for label, pattern in VAN_PATTERNS.items():
        if re.match(pattern, model):
            return label
    return None

def main():
    OUTPUT.mkdir(exist_ok=True)
    matched = []
    rows_scanned = 0

    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "complaints.zip"

        print("Downloading NHTSA complaints archive...")

        with requests.get(
            SOURCE_URL, stream=True, timeout=180
        ) as response:
            response.raise_for_status()
            with archive.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

        with zipfile.ZipFile(archive) as z:
            files = [
                name for name in z.namelist()
                if name.lower().endswith((".txt", ".csv"))
            ]

            if not files:
                raise RuntimeError(
                    "No complaint data file found in ZIP."
                )

            with z.open(files[0]) as source:
                chunks = pd.read_csv(
                    source,
                    sep="\t",
                    header=None,
                    usecols=list(FIELDS.keys()),
                    names=list(FIELDS.values()),
                    encoding="latin-1",
                    dtype=str,
                    chunksize=25000,
                    on_bad_lines="skip",
                    low_memory=False,
                )

                for chunk in chunks:
                    rows_scanned += len(chunk)

                    chunk["model_year"] = pd.to_numeric(
                        chunk["model_year"],
                        errors="coerce"
                    )

                    chunk = chunk[
                        chunk["model_year"].between(
                            MIN_YEAR, CURRENT_YEAR
                        )
                        & (
                            chunk["product_type"]
                            .str.strip().str.upper() == "V"
                        )
                    ].copy()

                    if chunk.empty:
                        continue

                    chunk["vehicle"] = (
                        chunk["model"].map(classify)
                    )

                    chunk = chunk[
                        chunk["vehicle"].notna()
                    ].copy()

                    if not chunk.empty:
                        matched.append(chunk)

    if not matched:
        raise RuntimeError(
            "No cargo van records matched. "
            "Check model classification patterns."
        )

    complaints = pd.concat(
        matched, ignore_index=True
    )

    complaints["model_year"] = (
        complaints["model_year"].astype(int)
    )

    # A complaint can appear in multiple component rows.
    # Keep the detail rows; count unique ODI numbers
    # in the summary.
    summary = (
        complaints.groupby(
            ["vehicle", "model_year"],
            as_index=False
        )
        .agg(
            complaint_count=(
                "odi_number", "nunique"
            ),
            component_records=(
                "component", "size"
            ),
        )
        .sort_values(
            ["vehicle", "model_year"]
        )
    )

    complaints.to_csv(
        OUTPUT / "complaints.csv", index=False
    )
    summary.to_csv(
        OUTPUT / "summary.csv", index=False
    )

    status = {
        "last_updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": SOURCE_URL,
        "first_model_year": MIN_YEAR,
        "last_model_year": CURRENT_YEAR,
        "rows_scanned": rows_scanned,
        "matched_rows": len(complaints),
        "unique_complaints": (
            complaints["odi_number"].nunique()
        ),
    }

    (OUTPUT / "refresh_status.json").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(status, indent=2))

if __name__ == "__main__":
    main()

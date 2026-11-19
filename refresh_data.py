
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

DATA_DIR = Path("data")

CURRENT_YEAR = datetime.now(timezone.utc).year
FIRST_YEAR = CURRENT_YEAR - 11

# Model-name patterns used to identify cargo vans.
# These are classification rules, not a complete
# manufacturer registry.
VAN_PATTERNS = [
    ("Ford", "Ford Transit",
     r"^TRANSIT(?:[- ](?:150|250|350|350HD))?$"),

    ("Ford", "Ford Transit Connect",
     r"^TRANSIT CONNECT$"),

    ("Ford", "Ford E-Transit",
     r"^E[- ]?TRANSIT$"),

    ("Ram", "Ram ProMaster",
     r"^PROMASTER(?:[- ](?:1500|2500|3500))?$"),

    ("Ram", "Ram ProMaster City",
     r"^PROMASTER CITY$"),

    ("Mercedes-Benz", "Mercedes Sprinter",
     r"^(?:SPRINTER|SPRINTER[- ].*)$"),

    ("Mercedes-Benz", "Mercedes Metris",
     r"^METRIS$"),

    ("Chevrolet", "Chevrolet Express",
     r"^EXPRESS(?:[- ].*)?$"),

    ("Chevrolet", "Chevrolet City Express",
     r"^CITY EXPRESS$"),

    ("GMC", "GMC Savana",
     r"^SAVANA(?:[- ].*)?$"),

    ("Nissan", "Nissan NV",
     r"^NV(?:1500|2500|3500)(?: HD)?$"),

    ("Nissan", "Nissan NV200",
     r"^NV200$"),
]

# Zero-based positions from the NHTSA complaint
# flat-file layout.
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

OUTPUT_COLUMNS = [
    "odi_number",
    "make",
    "model",
    "model_year",
    "crash",
    "fire",
    "injuries",
    "deaths",
    "component",
    "date_received",
    "mileage",
    "description",
    "product_type",
    "vehicle",
]


def normalize(value):
    return re.sub(
        r"\s+", " ", str(value).strip().upper()
    )


def classify_vehicle(make, model):
    make = normalize(make)
    model = normalize(model)

    for brand, label, pattern in VAN_PATTERNS:
        if brand == "Mercedes-Benz":
            valid_make = (
                "MERCEDES" in make
                or "FREIGHTLINER" in make
            )
        elif brand == "Ram":
            valid_make = (
                make == "RAM" or make == "DODGE"
            )
        else:
            valid_make = make == brand.upper()

        if valid_make and re.fullmatch(
            pattern, model
        ):
            return label

    return None


def download_archive(destination):
    print("Downloading NHTSA complaints archive...")

    with requests.get(
        SOURCE_URL,
        stream=True,
        timeout=(30, 300),
    ) as response:
        response.raise_for_status()

        with destination.open("wb") as file:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    file.write(chunk)

    print("Download completed.")


def process_archive(archive):
    matched_chunks = []
    rows_scanned = 0

    with zipfile.ZipFile(archive) as zipped:
        names = [
            name for name in zipped.namelist()
            if name.lower().endswith(
                (".txt", ".csv")
            )
        ]

        if not names:
            raise RuntimeError(
                "No data file found in archive."
            )

        with zipped.open(names[0]) as source:
            reader = pd.read_csv(
                source,
                sep="\t",
                header=None,
                usecols=list(FIELDS.keys()),
                dtype=str,
                encoding="latin-1",
                chunksize=25000,
                on_bad_lines="skip",
                low_memory=False,
            )

            for chunk in reader:
                rows_scanned += len(chunk)

                # Rename using actual column positions.
                chunk = chunk.rename(
                    columns=FIELDS
                )

                chunk["model_year"] = (
                    pd.to_numeric(
                        chunk["model_year"],
                        errors="coerce",
                    )
                )

                chunk = chunk[
                    chunk["model_year"].between(
                        FIRST_YEAR,
                        CURRENT_YEAR,
                    )
                ].copy()

                if chunk.empty:
                    continue

                # NHTSA product type V = vehicle.
                chunk = chunk[
                    chunk["product_type"]
                    .fillna("")
                    .str.strip()
                    .str.upper()
                    .eq("V")
                ].copy()

                if chunk.empty:
                    continue

                chunk["vehicle"] = [
                    classify_vehicle(make, model)
                    for make, model in zip(
                        chunk["make"],
                        chunk["model"],
                    )
                ]

                chunk = chunk[
                    chunk["vehicle"].notna()
                ].copy()

                if not chunk.empty:
                    matched_chunks.append(chunk)

                if rows_scanned % 250000 < 25000:
                    print(
                        f"Scanned {rows_scanned:,} rows"
                    )

    if not matched_chunks:
        raise RuntimeError(
            "No cargo van records matched."
        )

    complaints = pd.concat(
        matched_chunks,
        ignore_index=True,
    )

    complaints["model_year"] = (
        complaints["model_year"].astype(int)
    )

    # Keep one record per complaint-component row.
    # Avoid duplicated rows on repeated imports.
    complaints = complaints.drop_duplicates()

    complaints = complaints[OUTPUT_COLUMNS]

    return complaints, rows_scanned


def build_summary(complaints):
    return (
        complaints.groupby(
            ["vehicle", "model_year"],
            as_index=False,
        )
        .agg(
            complaint_count=(
                "odi_number",
                "nunique",
            ),
            component_records=(
                "component",
                "size",
            ),
        )
        .sort_values(
            ["vehicle", "model_year"]
        )
    )


def main():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "complaints.zip"

        download_archive(archive)

        complaints, rows_scanned = (
            process_archive(archive)
        )

    summary = build_summary(complaints)

    if complaints.empty or summary.empty:
        raise RuntimeError(
            "Generated dataset is empty."
        )

    status = {
        "last_updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": SOURCE_URL,
        "first_model_year": FIRST_YEAR,
        "last_model_year": CURRENT_YEAR,
        "rows_scanned": rows_scanned,
        "matched_rows": len(complaints),
        "unique_complaints": int(
            complaints["odi_number"].nunique()
        ),
        "vehicle_platforms": int(
            complaints["vehicle"].nunique()
        ),
    }

    # Prepare output files before replacing old data.
    complaints_file = (
        DATA_DIR / "complaints.csv"
    )
    summary_file = DATA_DIR / "summary.csv"
    status_file = (
        DATA_DIR / "refresh_status.json"
    )

    complaints.to_csv(
        complaints_file.with_suffix(".tmp"),
        index=False,
    )

    summary.to_csv(
        summary_file.with_suffix(".tmp"),
        index=False,
    )

    status_file.with_suffix(".tmp").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )

    # Replace the previous outputs after processing.
    for destination in [
        complaints_file,
        summary_file,
        status_file,
    ]:
        destination.with_suffix(".tmp").replace(
            destination
        )

    print("FleetIQ refresh successful.")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()


import csv
import json
import re
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

SOURCE_URL = (
    "https://static.nhtsa.gov/odi/ffdd/cmpl/"
    "FLAT_CMPL.zip"
)

DATA_DIR = Path("data")

CURRENT_YEAR = datetime.now(timezone.utc).year
FIRST_YEAR = CURRENT_YEAR - 11


# ============================================================
# VEHICLE CLASSIFICATION
# ============================================================
# These rules classify known cargo van platforms and
# commercial chassis commonly used for box trucks.
#
# A chassis match does not prove that the vehicle has
# an installed box body.
#
# The model inventory and candidate reports help identify
# additional NHTSA naming variations.
# ============================================================

VEHICLE_PATTERNS = [
    # FULL-SIZE CARGO VANS
    (
        "Ford", "Ford Transit", "Full-size cargo van",
        r"^TRANSIT(?:[- ]?(?:150|250|350|350HD|350 HD))?$"
    ),
    (
        "Ford", "Ford E-Transit", "Electric cargo van",
        r"^E[- ]?TRANSIT$"
    ),
    (
        "Ram", "Ram ProMaster", "Full-size cargo van",
        r"^PROMASTER(?:[- ]?(?:1500|2500|3500))?$"
    ),
    (
        "Mercedes-Benz", "Mercedes Sprinter",
        "Full-size cargo van",
        r"^(?:SPRINTER|SPRINTER[- ].*)$"
    ),
    (
        "Mercedes-Benz", "Mercedes eSprinter",
        "Electric cargo van",
        r"^E[- ]?SPRINTER$"
    ),
    (
        "Chevrolet", "Chevrolet Express",
        "Full-size cargo van",
        r"^EXPRESS(?:[- ].*)?$"
    ),
    (
        "GMC", "GMC Savana", "Full-size cargo van",
        r"^SAVANA(?:[- ].*)?$"
    ),
    (
        "Nissan", "Nissan NV", "Full-size cargo van",
        r"^(?:NV|NV[- ]?(?:1500|2500|3500)(?:[- ]?HD)?)$"
    ),

    # COMPACT CARGO VANS
    (
        "Ford", "Ford Transit Connect",
        "Compact cargo van",
        r"^TRANSIT[- ]CONNECT$"
    ),
    (
        "Ram", "Ram ProMaster City",
        "Compact cargo van",
        r"^PROMASTER[- ]CITY$"
    ),
    (
        "Mercedes-Benz", "Mercedes Metris",
        "Compact cargo van",
        r"^METRIS$"
    ),
    (
        "Nissan", "Nissan NV200",
        "Compact cargo van",
        r"^NV[- ]?200$"
    ),
    (
        "Chevrolet", "Chevrolet City Express",
        "Compact cargo van",
        r"^CITY[- ]EXPRESS$"
    ),

    # BOX-TRUCK / CUTAWAY CHASSIS
    (
        "Ford", "Ford E-Series",
        "Box-truck capable chassis",
        r"^(?:E[- ]?(?:350|450)(?:[- ]?(?:SUPER DUTY|SD))?)$"
    ),
    (
        "Ford", "Ford F-450",
        "Box-truck capable chassis",
        r"^F[- ]?450(?:[- ].*)?$"
    ),
    (
        "Ford", "Ford F-550",
        "Box-truck capable chassis",
        r"^F[- ]?550(?:[- ].*)?$"
    ),
    (
        "Ford", "Ford F-600",
        "Box-truck capable chassis",
        r"^F[- ]?600(?:[- ].*)?$"
    ),
    (
        "Chevrolet", "Chevrolet Medium Duty",
        "Box-truck capable chassis",
        r"^(?:SILVERADO[- ]?)?(?:4500|5500|6500)(?:HD)?$"
    ),
    (
        "Isuzu", "Isuzu NPR",
        "Box-truck capable chassis",
        r"^NPR(?:[- ].*)?$"
    ),
    (
        "Isuzu", "Isuzu NQR",
        "Box-truck capable chassis",
        r"^NQR(?:[- ].*)?$"
    ),
    (
        "Isuzu", "Isuzu NRR",
        "Box-truck capable chassis",
        r"^NRR(?:[- ].*)?$"
    ),
    (
        "Hino", "Hino Commercial Truck",
        "Box-truck capable chassis",
        r"^(?:155|195|258|268|338|L6|L7)(?:[- ].*)?$"
    ),
    (
        "Freightliner", "Freightliner M2",
        "Box-truck capable chassis",
        r"^(?:M2|M2[- ]?106|BUSINESS CLASS M2)(?:[- ].*)?$"
    ),
    (
        "International", "International MV",
        "Box-truck capable chassis",
        r"^(?:MV|MV SERIES|DURASTAR)(?:[- ].*)?$"
    ),
    (
        "Mitsubishi Fuso", "Fuso Canter",
        "Box-truck capable chassis",
        r"^(?:CANTER|FE(?:[- ]?[0-9A-Z]+)?)(?:[- ].*)?$"
    ),
]


MAKE_ALIASES = {
    "FORD": "Ford",
    "RAM": "Ram",
    "DODGE": "Ram",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "MERCEDES BENZ": "Mercedes-Benz",
    "FREIGHTLINER": "Freightliner",
    "CHEVROLET": "Chevrolet",
    "GMC": "GMC",
    "NISSAN": "Nissan",
    "ISUZU": "Isuzu",
    "HINO": "Hino",
    "INTERNATIONAL": "International",
    "NAVISTAR": "International",
    "MITSUBISHI FUSO": "Mitsubishi Fuso",
    "MITSUBISHI FUSO TRUCK": "Mitsubishi Fuso",
}

# Some Sprinter vehicles are registered under Freightliner.
# Treat them as the Mercedes Sprinter platform.
SPECIAL_MAKE_ALIASES = {
    ("FREIGHTLINER", "SPRINTER"): "Mercedes-Benz",
}

# These names flag potentially relevant models for review.
# A keyword match does not automatically add a vehicle.
CANDIDATE_TERMS = re.compile(
    r"TRANSIT|SPRINTER|PROMASTER|METRIS|EXPRESS|SAVANA|"
    r"NV[ -]?(?:1500|200|2500|3500)|"
    r"^E[ -]?(?:350|450)|^F[ -]?(?:450|550|600)|"
    r"^NPR|^NQR|^NRR|^M2|DURASTAR|"
    r"^MV(?:[ -]|$)|CANTER|CUTAWAY|"
    r"BOX TRUCK|CHASSIS",
    re.IGNORECASE,
)


# ============================================================
# NHTSA COMPLAINT FIELD MAPPING
# ============================================================

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
    "vehicle_class",
]


# ============================================================
# HELPERS
# ============================================================

def normalize(value):
    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip().upper()
    )


def standardize_make(make, model):
    make = normalize(make)
    model = normalize(model)

    for (raw_make, prefix), standard_make in (
        SPECIAL_MAKE_ALIASES.items()
    ):
        if make == raw_make and model.startswith(prefix):
            return standard_make

    return MAKE_ALIASES.get(make, make.title())


def classify_vehicle(make, model):
    model = normalize(model)
    standard_make = standardize_make(make, model)

    for brand, vehicle, vehicle_class, pattern in (
        VEHICLE_PATTERNS
    ):
        if brand != standard_make:
            continue

        if re.fullmatch(pattern, model):
            return vehicle, vehicle_class

    return None, None


def write_inventory(counter, destination):
    with destination.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "make",
            "model",
            "model_year",
            "complaint_rows",
            "classification",
            "vehicle",
            "vehicle_class",
        ])

        for (make, model, year), count in sorted(
            counter.items()
        ):
            vehicle, vehicle_class = classify_vehicle(
                make, model
            )

            if vehicle:
                classification = "matched"
            elif CANDIDATE_TERMS.search(model):
                classification = "review"
            else:
                classification = "unclassified"

            writer.writerow([
                make,
                model,
                year,
                count,
                classification,
                vehicle or "",
                vehicle_class or "",
            ])


def write_candidates(counter, destination):
    with destination.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "make",
            "model",
            "model_year",
            "complaint_rows",
            "reason",
        ])

        for (make, model, year), count in sorted(
            counter.items()
        ):
            vehicle, _ = classify_vehicle(make, model)

            if vehicle:
                continue

            if CANDIDATE_TERMS.search(model):
                writer.writerow([
                    make,
                    model,
                    year,
                    count,
                    "Potential commercial vehicle; review",
                ])


# ============================================================
# DOWNLOAD NHTSA DATA
# ============================================================

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


# ============================================================
# PROCESS NHTSA DATA
# ============================================================

def process_archive(archive):
    matched_chunks = []
    model_inventory = Counter()
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

                chunk = chunk.rename(columns=FIELDS)

                chunk["model_year"] = pd.to_numeric(
                    chunk["model_year"],
                    errors="coerce",
                )

                # Keep only the rolling 12-year window.
                chunk = chunk[
                    chunk["model_year"].between(
                        FIRST_YEAR,
                        CURRENT_YEAR,
                    )
                ].copy()

                if chunk.empty:
                    continue

                # V identifies vehicle complaints.
                chunk = chunk[
                    chunk["product_type"]
                    .fillna("")
                    .str.strip()
                    .str.upper()
                    .eq("V")
                ].copy()

                if chunk.empty:
                    continue

                # Discover model names BEFORE classification.
                chunk["make"] = chunk["make"].map(normalize)
                chunk["model"] = chunk["model"].map(normalize)

                inventory_counts = (
                    chunk.groupby(
                        ["make", "model", "model_year"],
                        dropna=False,
                    )
                    .size()
                )

                for key, count in inventory_counts.items():
                    make, model, year = key

                    model_inventory[
                        (make, model, int(year))
                    ] += int(count)

                # Classify cargo vans and truck chassis.
                classifications = [
                    classify_vehicle(make, model)
                    for make, model in zip(
                        chunk["make"],
                        chunk["model"],
                    )
                ]

                chunk["vehicle"] = [
                    result[0]
                    for result in classifications
                ]

                chunk["vehicle_class"] = [
                    result[1]
                    for result in classifications
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
            "No commercial vehicle records matched."
        )

    complaints = pd.concat(
        matched_chunks,
        ignore_index=True,
    )

    complaints["model_year"] = (
        complaints["model_year"].astype(int)
    )

    complaints = complaints.drop_duplicates()
    complaints = complaints[OUTPUT_COLUMNS]

    return complaints, model_inventory, rows_scanned


# ============================================================
# BUILD SUMMARY
# ============================================================

def build_summary(complaints):
    return (
        complaints.groupby(
            [
                "vehicle",
                "vehicle_class",
                "model_year",
            ],
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
            ["vehicle_class", "vehicle", "model_year"]
        )
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "complaints.zip"

        download_archive(archive)

        complaints, inventory, rows_scanned = (
            process_archive(archive)
        )

    summary = build_summary(complaints)

    if complaints.empty or summary.empty:
        raise RuntimeError(
            "Generated dataset is empty."
        )

    # Count model combinations needing review.
    review_candidates = sum(
        1
        for (make, model, year) in inventory
        if classify_vehicle(make, model)[0] is None
        and CANDIDATE_TERMS.search(model)
    )

    matched_models = {
        (make, model)
        for make, model, year in inventory
        if classify_vehicle(make, model)[0]
    }

    quality = {
        "unique_odi_numbers": int(
            complaints["odi_number"].nunique()
        ),
        "missing_odi_numbers": int(
            complaints["odi_number"].isna().sum()
        ),
        "missing_descriptions": int(
            complaints["description"].isna().sum()
        ),
        "missing_mileage": int(
            complaints["mileage"].isna().sum()
        ),
        "matched_raw_models": len(matched_models),
        "review_candidates": review_candidates,
        "inventory_combinations": len(inventory),
    }

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
        "review_candidates": review_candidates,
    }

    # Write temporary output files.
    output_files = {
        "complaints.csv": "complaints",
        "summary.csv": "summary",
        "model_inventory.csv": "inventory",
        "unmatched_models.csv": "candidates",
        "refresh_status.json": "status",
        "data_quality.json": "quality",
    }

    complaints.to_csv(
        DATA_DIR / "complaints.csv.tmp",
        index=False,
    )

    summary.to_csv(
        DATA_DIR / "summary.csv.tmp",
        index=False,
    )

    write_inventory(
        inventory,
        DATA_DIR / "model_inventory.csv.tmp",
    )

    write_candidates(
        inventory,
        DATA_DIR / "unmatched_models.csv.tmp",
    )

    (DATA_DIR / "refresh_status.json.tmp").write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )

    (DATA_DIR / "data_quality.json.tmp").write_text(
        json.dumps(quality, indent=2),
        encoding="utf-8",
    )

    # Replace old datasets only after processing succeeds.
    for filename in output_files:
        temporary = DATA_DIR / f"{filename}.tmp"
        destination = DATA_DIR / filename
        temporary.replace(destination)

    print("FleetIQ refresh successful.")
    print(json.dumps(status, indent=2))
    print(json.dumps(quality, indent=2))


if __name__ == "__main__":
    main()

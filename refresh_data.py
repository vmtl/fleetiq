
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://api.nhtsa.gov"
OUTPUT_FILE = Path("data/nhtsa.json")

CURRENT_YEAR = datetime.now(timezone.utc).year
YEARS = range(CURRENT_YEAR - 12, CURRENT_YEAR + 1)

# Cargo van model names to validate against NHTSA.
# Additional models can be added without changing the ETL logic.
VEHICLES = [
    ("Ford", "Transit"),
    ("Ford", "Transit Connect"),
    ("Ford", "E-Transit"),
    ("RAM", "ProMaster"),
    ("RAM", "ProMaster City"),
    ("Mercedes-Benz", "Sprinter"),
    ("Mercedes-Benz", "Metris"),
    ("Mercedes-Benz", "eSprinter"),
    ("Chevrolet", "Express"),
    ("Chevrolet", "City Express"),
    ("GMC", "Savana"),
    ("Nissan", "NV"),
    ("Nissan", "NV200"),
]

ENDPOINTS = {
    "complaints": "complaints/complaintsByVehicle",
    "recalls": "recalls/recallsByVehicle",
}


def fetch_json(session, endpoint, params):
    url = f"{BASE_URL}/{endpoint}"

    for attempt in range(3):
        try:
            response = session.get(
                url,
                params=params,
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()

            results = payload.get("results")

            if not isinstance(results, list):
                raise ValueError(
                    f"Unexpected API response: {url}"
                )

            return results

        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise

            time.sleep(2 ** attempt)


def main():
    records = []
    errors = []

    with requests.Session() as session:
        for make, model in VEHICLES:
            for year in YEARS:
                for data_type, endpoint in ENDPOINTS.items():
                    params = {
                        "make": make,
                        "model": model,
                        "modelYear": year,
                    }

                    try:
                        results = fetch_json(
                            session, endpoint, params
                        )

                        records.append({
                            "make": make,
                            "model": model,
                            "year": year,
                            "type": data_type,
                            "count": len(results),
                            "results": results,
                        })

                        print(
                            f"{year} {make} {model}: "
                            f"{len(results)} {data_type}"
                        )

                    except (
                        requests.RequestException,
                        ValueError,
                    ) as error:
                        errors.append({
                            **params,
                            "type": data_type,
                            "error": str(error),
                        })

                    time.sleep(0.25)

    if errors:
        print(json.dumps(errors, indent=2))
        raise RuntimeError(
            f"Refresh failed: {len(errors)} requests"
        )

    output = {
        "last_updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "first_model_year": min(YEARS),
        "last_model_year": max(YEARS),
        "vehicle_count": len(VEHICLES),
        "records": records,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True, exist_ok=True
    )

    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(output, file)

    temp_file.replace(OUTPUT_FILE)

    print("FleetIQ data refresh completed.")


if __name__ == "__main__":
    main()

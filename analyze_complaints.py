"""FleetIQ: derive complaint problem labels, approximate age, and optional mileage.

Run from the repository root: python analyze_complaints.py
Inputs: data/complaints.csv
Outputs: data/problem_analysis.csv, data/problem_summary.csv

Labels are keyword-based descriptions of *reported symptoms*, not confirmed repairs.
Complaint age is based on receipt year minus model year, not actual failure date.
Missing mileage is never statistically filled or replaced with zero.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
INPUT_FILE = DATA_DIR / "complaints.csv"
ANALYSIS_FILE = DATA_DIR / "problem_analysis.csv"
SUMMARY_FILE = DATA_DIR / "problem_summary.csv"

# Use restrained, explicit patterns. A complaint can mention several symptoms.
# Order determines the primary label if more than one matches.
ISSUE_PATTERNS = {
    "Engine stalls / loses power": r"\b(?:engine\s+stall(?:ed|s|ing)?|vehicle\s+stall(?:ed|s|ing)?|stall(?:ed|s|ing)?\s+(?:while|when|at)|lost\s+(?:all\s+)?(?:engine\s+)?power|loss\s+of\s+(?:engine\s+)?power|shut\s+off\s+(?:while|when)|shuts?\s+off\s+(?:while|when))\b",
    "Engine overheating": r"\b(?:overheat(?:s|ed|ing)?|engine\s+temperature\s+(?:high|rising)|coolant\s+temperature\s+(?:high|rising))\b",
    "Engine oil leak / consumption": r"\b(?:oil\s+leak(?:s|ing|ed)?|leak(?:s|ing|ed)?\s+oil|burn(?:s|ing)?\s+oil|excessive\s+oil\s+consumption|oil\s+consumption)\b",
    "Engine misfire / rough running": r"\b(?:misfire(?:s|d)?|rough\s+idle|engine\s+shudder(?:s|ing)?|engine\s+runs?\s+rough)\b",
    "Transmission slipping / shifting": r"\b(?:transmission\s+slip(?:s|ped|ping)?|slip(?:s|ped|ping)?\s+gears?|hard\s+shift(?:s|ing)?|rough\s+shift(?:s|ing)?|jerk(?:s|ing)?\s+(?:while\s+)?shift(?:ing)?|won'?t\s+shift|will\s+not\s+shift|delayed\s+engagement)\b",
    "Transmission failure / loss of drive": r"\b(?:transmission\s+fail(?:ed|ure|s)?|transmission\s+replac(?:ed|ement)|no\s+forward\s+gear|lost\s+(?:forward\s+)?drive|won'?t\s+go\s+into\s+gear)\b",
    "Brake malfunction / reduced braking": r"\b(?:brake(?:s)?\s+fail(?:ed|ure|s)?|loss\s+of\s+brak(?:es|ing)|brake\s+pedal\s+(?:went\s+to\s+floor|sank)|reduced\s+brak(?:es|ing)|brake\s+fluid\s+leak)\b",
    "Premature brake wear / vibration": r"\b(?:premature\s+brake\s+wear|brake\s+(?:pads?|rotors?)\s+(?:worn|warped|vibrat)|warped\s+rotors?|brake\s+judder)\b",
    "Steering assist / control failure": r"\b(?:power\s+steering\s+(?:fail(?:ed|ure|s)?|lost|loss)|loss\s+of\s+steering|steering\s+(?:lock(?:ed|s)?|fail(?:ed|ure|s)?)|hard\s+to\s+steer)\b",
    "Electrical power / battery / charging": r"\b(?:alternator\s+fail(?:ed|ure|s)?|battery\s+(?:drain(?:s|ed|ing)?|die(?:s|d)|dead)|electrical\s+(?:power\s+)?(?:fail(?:ed|ure|s)?|outage)|charging\s+system\s+(?:fail(?:ed|ure|s)?|fault)|wiring\s+(?:melt(?:ed|ing)?|short))\b",
    "Fuel leak / fuel system": r"\b(?:fuel\s+leak(?:s|ing|ed)?|gas(?:oline)?\s+leak(?:s|ing|ed)?|fuel\s+pump\s+fail(?:ed|ure|s)?|fuel\s+line\s+(?:rupture|leak))\b",
    "Cooling system / coolant leak": r"\b(?:coolant\s+leak(?:s|ing|ed)?|antifreeze\s+leak(?:s|ing|ed)?|radiator\s+leak(?:s|ing|ed)?|water\s+pump\s+(?:fail(?:ed|ure|s)?|leak))\b",
    "Door / latch malfunction": r"\b(?:door\s+(?:latch|lock|handle|hinge|roller)\s+(?:fail(?:ed|ure|s)?|break|broke|broken)|sliding\s+door\s+(?:open(?:s|ed)?|stuck|detach)|door\s+(?:open(?:ed|s)?\s+(?:while\s+)?driving|will\s+not\s+latch))\b",
    "Airbag / restraint malfunction": r"\b(?:air\s?bag\s+(?:fail(?:ed|ure|s)?|deploy(?:ed|ment)?|warning)|seat\s?belt\s+(?:fail(?:ed|ure|s)?|won'?t\s+latch|will\s+not\s+latch))\b",
    "Tire failure / separation": r"\b(?:tire\s+(?:blowout|blow\s?out|separation|separat(?:ed|ion)|burst)|tread\s+separat(?:ed|ion))\b",
    "Visibility / wiper malfunction": r"\b(?:windshield\s+wiper(?:s)?\s+(?:fail(?:ed|ure|s)?|stop(?:ped)?|inoperative)|wiper\s+motor\s+fail(?:ed|ure|s)?|defrost(?:er)?\s+(?:fail(?:ed|ure|s)?|inoperative))\b",
    "Turbocharger / boost system": r"\b(?:turbocharger|turbo\s+fail(?:ed|ure|s)?|boost\s+(?:pressure|leak|loss)|intercooler\s+leak)\b",
    "Fuel injector / injection system": r"\b(?:fuel\s+injector|injector\s+fail(?:ed|ure|s)?|injection\s+system\s+fail)\b",
    "Emissions / DEF / DPF": r"\b(?:diesel\s+exhaust\s+fluid|\bDEF\b|DPF|particulate\s+filter|EGR\s+(?:valve|cooler)|emissions\s+system|SCR\s+system)\b",
    "Suspension / axle / springs": r"\b(?:leaf\s+spring|coil\s+spring|suspension\s+(?:fail|collapse|break)|shock\s+absorber|strut\s+fail|axle\s+(?:break|fail|snap))\b",
    "Driveline / differential / driveshaft": r"\b(?:drive\s*shaft|propeller\s+shaft|differential\s+(?:fail|leak|noise)|universal\s+joint|\bU[- ]joint\b)\b",
    "Starter / no crank": r"\b(?:starter\s+(?:motor\s+)?fail|won'?t\s+crank|will\s+not\s+crank|no[- ]crank)\b",
    "Sensor / warning / diagnostic": r"\b(?:check\s+engine\s+light|warning\s+light|sensor\s+(?:fail|fault|malfunction)|fault\s+code|diagnostic\s+trouble\s+code)\b",
    "HVAC / air conditioning": r"\b(?:air\s+conditioning\s+(?:fail|stop)|\bA/C\b\s+(?:fail|stop)|blower\s+motor\s+fail|heater\s+core\s+leak|HVAC\s+fail)\b",
    "Wheel bearing / hub": r"\b(?:wheel\s+bearing|hub\s+assembly|hub\s+bearing)\b",
    "Exhaust leak / failure": r"\b(?:exhaust\s+(?:leak|pipe\s+break|manifold\s+crack)|catalytic\s+converter\s+(?:fail|clog))\b",
    "Battery / high voltage system": r"\b(?:high[- ]voltage\s+battery|traction\s+battery|battery\s+pack\s+(?:fail|fault)|inverter\s+fail)\b",
}
COMPILED_ISSUES = [(label, re.compile(pattern, re.I)) for label, pattern in ISSUE_PATTERNS.items()]

# Only explicit odometer / mileage expressions, NOT speed, distance driven, or
# maintenance intervals. Typical examples: "odometer read 83000 miles",
# "at 83,000 miles", "vehicle has 83k miles".
MILEAGE_PATTERNS = [
    re.compile(r"\b(?:odometer|mileage)\s*(?:was|is|reads?|reading|of|at|approximately|about|:)?\s*(\d{1,3}(?:,\d{3})+|\d{4,6}|\d{1,3}(?:\.\d+)?\s*[kK])\s*(?:miles?|mi\b)?", re.I),
    re.compile(r"\b(?:at|around|approximately|approx\.?|about|with|has|had)\s+(\d{1,3}(?:,\d{3})+|\d{4,6}|\d{1,3}(?:\.\d+)?\s*[kK])\s*(?:miles?|mi\b)\s+(?:on\s+the\s+(?:vehicle|odometer)|the\s+vehicle|on\s+it|when\s+(?:the|it)|at\s+(?:the|which))", re.I),
    re.compile(r"\b(?:at|around|approximately|approx\.?|about)\s+(\d{1,3}(?:,\d{3})+|\d{4,6}|\d{1,3}(?:\.\d+)?\s*[kK])\s*(?:miles?|mi\b)\s*[,;:]?\s+(?:the\s+(?:vehicle|engine|transmission|brakes?|problem)|it\s+(?:began|started|failed|stalled))", re.I),
]


def numeric_mileage(value):
    try:
        mileage = float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
    if 1 <= mileage <= 1_000_000:
        return round(mileage)
    return None


def extract_explicit_mileage(description):
    """Conservative extraction; ambiguous narratives remain missing."""
    text = str(description or "")
    for pattern in MILEAGE_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1).replace(" ", "").replace(",", "")
            try:
                number = float(raw[:-1]) * 1000 if raw.lower().endswith("k") else float(raw)
            except ValueError:
                continue
            value = numeric_mileage(number)
            # Avoid most speeds and distances; explicit mileage below 1k is ambiguous.
            if value is not None and value >= 1000:
                return value
    return None


def extract_issues(description):
    return [label for label, pattern in COMPILED_ISSUES if pattern.search(str(description or ""))]


def first_present(series):
    for value in series:
        if pd.notna(value) and str(value).strip():
            return value
    return ""


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing {INPUT_FILE}; run refresh_data.py first.")

    raw = pd.read_csv(INPUT_FILE, dtype={"odi_number": "string"}, low_memory=False)
    required = {"odi_number", "vehicle", "model_year", "component", "description", "mileage", "date_received"}
    if missing := required - set(raw.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if raw.empty or raw["odi_number"].isna().any():
        raise ValueError("Complaint input is empty or contains missing ODI identifiers")

    # One complaint can have multiple NHTSA component records; assess once per ODI.
    if raw.groupby("odi_number")["vehicle"].nunique().gt(1).any():
        raise ValueError("One or more ODI IDs are assigned to multiple vehicle platforms")
    if raw.groupby("odi_number")["model_year"].nunique().gt(1).any():
        raise ValueError("One or more ODI IDs have conflicting model years")

    rows = []
    for odi, group in raw.groupby("odi_number", sort=False):
        description = str(first_present(group["description"]))
        components = sorted({str(v).strip() for v in group["component"].dropna() if str(v).strip()})
        reported = next((m for m in (numeric_mileage(v) for v in group["mileage"]) if m is not None), None)
        extracted = None if reported is not None else extract_explicit_mileage(description)
        selected = reported if reported is not None else extracted
        method = "NHTSA field" if reported is not None else "Narrative (explicit)" if extracted is not None else "Missing"
        issues = extract_issues(description)
        # NHTSA date_received is YYYYMMDD and is not the date the incident occurred.
        received_raw = first_present(group["date_received"])
        received_date = pd.to_datetime(str(received_raw), format="%Y%m%d", errors="coerce")
        model_year = int(first_present(group["model_year"]))
        receipt_year = int(received_date.year) if pd.notna(received_date) else None
        age = receipt_year - model_year if receipt_year is not None else None
        if age is not None and age < 0:
            age_status = "Pre-model-year receipt"
            age = None
        elif age is None:
            age_status = "Missing/invalid receipt date"
        else:
            age_status = "Approximate: receipt year minus model year"
        age_band = ("Unknown" if age is None else
                    "0–1 years" if age <= 1 else
                    "2–3 years" if age <= 3 else
                    "4–5 years" if age <= 5 else
                    "6–8 years" if age <= 8 else "9+ years")
        rows.append({
            "odi_number": str(odi),
            "vehicle": str(first_present(group["vehicle"])),
            "vehicle_class": str(first_present(group["vehicle_class"])) if "vehicle_class" in group else "",
            "model_year": model_year,
            "date_received": received_date.strftime("%Y-%m-%d") if pd.notna(received_date) else "",
            "complaint_received_year": receipt_year,
            "approx_vehicle_age_years": age,
            "age_band": age_band,
            "age_method": age_status,
            "nhtsa_components": " | ".join(components),
            "primary_reported_issue": issues[0] if issues else "Unspecified / manual review",
            "reported_issues": " | ".join(issues) if issues else "Unspecified / manual review",
            "issue_detection": "Keyword match (review required)" if issues else "No keyword match",
            "mileage_nhtsa": reported,
            "mileage_extracted": extracted,
            "mileage_best_available": selected,
            "mileage_source": method,
            "description": description,
        })

    analysis = pd.DataFrame(rows)
    if analysis["odi_number"].duplicated().any() or len(analysis) != raw["odi_number"].nunique():
        raise AssertionError("Output ODI deduplication check failed")

    # One row per ODI/issue, so multiple complaints on a single vehicle are never
    # counted multiple times *within the same issue*.
    exploded = analysis.assign(issue=analysis["reported_issues"].str.split(" | ", regex=False)).explode("issue")
    summary = (
        exploded.groupby(["vehicle", "vehicle_class", "model_year", "issue"], dropna=False)
        .agg(
            unique_complaints=("odi_number", "nunique"),
            mileage_samples=("mileage_best_available", "count"),
            complaints_with_age=("approx_vehicle_age_years", "count"),
            median_approx_age_years=("approx_vehicle_age_years", "median"),
            median_reported_miles=("mileage_best_available", "median"),
            narrative_mileage_samples=("mileage_source", lambda s: int((s == "Narrative (explicit)").sum())),
        )
        .reset_index()
        .sort_values(["vehicle", "model_year", "unique_complaints"], ascending=[True, True, False])
    )
    summary["mileage_coverage_pct"] = (
        100 * summary["mileage_samples"] / summary["unique_complaints"]
    ).round(1)
    summary["median_reported_miles"] = summary["median_reported_miles"].round().astype("Int64")
    summary["age_coverage_pct"] = (
        100 * summary["complaints_with_age"] / summary["unique_complaints"]
    ).round(1)
    summary["median_approx_age_years"] = summary["median_approx_age_years"].round(1)

    for destination, dataframe in [(ANALYSIS_FILE, analysis), (SUMMARY_FILE, summary)]:
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        dataframe.to_csv(temporary, index=False)
        temporary.replace(destination)

    print(f"Source complaint-component rows: {len(raw):,}")
    print(f"Unique complaints analyzed: {len(analysis):,}")
    print(f"Complaints with approximate age: {analysis['approx_vehicle_age_years'].notna().sum():,}")
    print(f"Narrative mileage recovered: {(analysis['mileage_source'] == 'Narrative (explicit)').sum():,}")
    print(f"Missing mileage after extraction: {(analysis['mileage_source'] == 'Missing').sum():,}")
    print(f"Issue summary rows: {len(summary):,}")
    print("Created data/problem_analysis.csv and data/problem_summary.csv")


if __name__ == "__main__":
    main()

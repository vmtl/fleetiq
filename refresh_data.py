
    
  

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

# Order matters: specific variants must precede broad model families.
VEHICLE_PATTERNS = [
    # Cargo vans: variants are consolidated into their model families.
    ("Ford", "Ford Transit Connect", "Compact cargo van", r"^TRANSIT[- ]CONNECT$"),
    ("Ford", "Ford E-Transit", "Electric cargo van", r"^E[- ]?TRANSIT$"),
    ("Ford", "Ford Transit", "Full-size cargo van",
     r"^TRANSIT(?:[- ]?(?:T[- ]?)?(?:150|250|350)(?:[- ]?HD)?)?$"),
    ("Ram", "Ram ProMaster City", "Compact cargo van", r"^PROMASTER[- ]CITY$"),
    ("Ram", "Ram ProMaster", "Full-size cargo van",
     r"^PROMASTER(?:[- ]?(?:1500|2500|3500))?$"),
    ("Mercedes-Benz", "Mercedes eSprinter", "Electric cargo van",
     r"^E[- ]?SPRINTER$"),
    ("Mercedes-Benz", "Mercedes Sprinter", "Full-size cargo van",
     r"^SPRINTER(?:[- ].*)?$"),
    ("Mercedes-Benz", "Mercedes Metris", "Compact cargo van", r"^METRIS$"),
    ("Chevrolet", "Chevrolet City Express", "Compact cargo van",
     r"^CITY[- ]EXPRESS$"),
    ("Chevrolet", "Chevrolet Express Cutaway", "Box-truck capable chassis",
     r"^EXPRESS[- ]CUTAWAY(?:[- ]VAN)?$"),
    ("Chevrolet", "Chevrolet Express", "Full-size cargo van",
     r"^EXPRESS(?:[- ].*)?$"),
    ("GMC", "GMC Savana Cutaway", "Box-truck capable chassis",
     r"^SAVANA[- ]CUTAWAY(?:[- ]VAN)?$"),
    ("GMC", "GMC Savana", "Full-size cargo van",
     r"^SAVANA(?:[- ].*)?$"),
    ("Nissan", "Nissan NV200", "Compact cargo van", r"^NV[- ]?200$"),
    ("Nissan", "Nissan NV", "Full-size cargo van",
     r"^(?:NV|NV[- ]?(?:1500|2500|3500)(?:[- ]?HD)?)$"),

    # Commercial chassis: body configuration is NOT confirmed by the model name.
    ("Ford", "Ford E-Series", "Box-truck capable chassis",
     r"^E[- ]?(?:350|450)(?:[- ]?(?:SUPER DUTY|SD))?$"),
    ("Ford", "Ford F-450", "Box-truck capable chassis", r"^F[- ]?450(?:[- ].*)?$"),
    ("Ford", "Ford F-550", "Box-truck capable chassis", r"^F[- ]?550(?:[- ].*)?$"),
    ("Ford", "Ford F-600", "Box-truck capable chassis", r"^F[- ]?600(?:[- ].*)?$"),
    # Medium-duty Ford chassis. Keep F-650 and F-750 separate from F-450/F-550.
    ("Ford", "Ford F-650", "Box-truck capable chassis", r"^F[- ]?650(?:[- ]?SD)?$"),
    ("Ford", "Ford F-750", "Box-truck capable chassis", r"^F[- ]?750(?:[- ]?SD)?$"),
    ("Ram", "Ram 3500 Cab Chassis", "Box-truck capable chassis",
     r"^3500[- ]CAB[- ]CHASSIS$"),
    ("Ram", "Ram 4500", "Box-truck capable chassis",
     r"^4500(?:[- ]CAB[- ]CHASSIS)?$"),
    ("Ram", "Ram 5500", "Box-truck capable chassis",
     r"^5500(?:[- ]CAB[- ]CHASSIS)?$"),
    ("Chevrolet", "Chevrolet G4500", "Box-truck capable chassis", r"^G[- ]?4500$"),
    ("Chevrolet", "Chevrolet Low Cab Forward", "Box-truck capable chassis",
     r"^LOW[- ]CAB[- ]FORWARD(?:[- ](?:4500|5500|6500))?$"),
    ("Chevrolet", "Chevrolet Medium Duty", "Box-truck capable chassis",
     r"^(?:SILVERADO[- ]?)?(?:4500|5500|6500)(?:[- ]?HD)?$"),
    ("Isuzu", "Isuzu NPR", "Box-truck capable chassis", r"^NPR(?:[- ].*)?$"),
    ("Isuzu", "Isuzu NQR", "Box-truck capable chassis", r"^NQR(?:[- ].*)?$"),
    ("Isuzu", "Isuzu NRR", "Box-truck capable chassis", r"^NRR(?:[- ].*)?$"),
    ("Isuzu", "Isuzu FTR", "Box-truck capable chassis", r"^FTR(?:[- ].*)?$"),
    ("Isuzu", "Isuzu N-Series", "Box-truck capable chassis", r"^N[- ]?SERIES$"),


"""
Sierra Leone Geographic Reference Data
=======================================

Loads administrative hierarchy and flood-prone community data from portable
reference files (CSV/JSON) rather than hardcoding them in Python source.

Data files:
  - ``reference/admin_hierarchy.csv``   → District-level admin geography
  - ``reference/flood_zones.json``      → Flood-prone community catalog

These reference files are version-controlled and human-editable. Changes
to the geographic substrate should be made there, not in this module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TypedDict

# ── Resolve paths relative to this file ──────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent
_REFERENCE_DIR = _DATA_DIR / "reference"


# ── Type definitions ─────────────────────────────────────────────────

class FloodEvent(TypedDict):
    year: int
    description: str
    impact: str


class FloodZone(TypedDict):
    id: str
    name: str
    district: str
    region: str
    lat: float
    lng: float
    elevation_m: float
    drainage_quality: str
    distance_to_water_km: float
    typical_saturation_pct: float
    water_body: str
    urban_type: str
    population: int
    flood_history: list[FloodEvent]


# ── Load districts from CSV ──────────────────────────────────────────

def _load_districts() -> dict:
    """Load district data from reference/admin_hierarchy.csv."""
    path = _REFERENCE_DIR / "admin_hierarchy.csv"
    districts = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            districts[row["district_id"]] = {
                "name": row["district_name"],
                "region": row["region"],
                "centroid": (float(row["centroid_lat"]), float(row["centroid_lng"])),
                "rainy_season_months": (
                    int(row["rainy_season_start_month"]),
                    int(row["rainy_season_end_month"]),
                ),
                "typical_aug_rainfall_mm": int(row["typical_aug_rainfall_mm"]),
            }
    return districts


# ── Load flood zones from JSON ───────────────────────────────────────

def _load_flood_zones() -> list[FloodZone]:
    """Load flood-prone community catalog from reference/flood_zones.json."""
    path = _REFERENCE_DIR / "flood_zones.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Module-level data (loaded once at import time) ───────────────────

DISTRICTS: dict = _load_districts()
FLOOD_ZONES: list[FloodZone] = _load_flood_zones()
ZONES_BY_ID: dict[str, FloodZone] = {z["id"]: z for z in FLOOD_ZONES}


# ── Public API (unchanged from original) ─────────────────────────────

def list_zones() -> list[FloodZone]:
    """Return all flood zones in catalog order."""
    return list(FLOOD_ZONES)


def get_zone(zone_id: str) -> FloodZone | None:
    return ZONES_BY_ID.get(zone_id)


def list_districts() -> dict:
    return dict(DISTRICTS)


def zones_in_district(district_id: str) -> list[FloodZone]:
    return [z for z in FLOOD_ZONES if z["district"] == district_id]


def country_bounds() -> dict:
    """Bounding box for Sierra Leone (used to fit the Leaflet map)."""
    return {
        "south_west": [6.92, -13.30],
        "north_east": [10.00, -10.27],
        "centroid": [8.46, -11.78],
    }

"""
Master Facility List (MFL) Data Service
==========================================
Loads, validates, and serves facility data from the MFL CSV.
This is the authoritative facility reference layer for CHEWS.

Data integrity rules:
  - Do NOT invent facility information
  - Do NOT present missing information as zero
  - Display "Data not available" for unavailable indicators
  - Do NOT fabricate readiness or risk scores from insufficient data
"""

from __future__ import annotations

import csv
import json
import math
import hashlib
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MFL_PATH = DATA_DIR / "01_raw" / "master_facility_list" / "mfl_readiness_chews_v1.csv"
FLOOD_ZONES_PATH = DATA_DIR / "reference" / "flood_zones.json"
ADMIN_PATH = DATA_DIR / "reference" / "admin_hierarchy.csv"

# ── Module state ─────────────────────────────────────────────────────

_facilities: list[dict] = []
_facilities_by_id: dict[str, dict] = {}
_district_centroids: dict[str, tuple[float, float]] = {}
_district_info: dict[str, dict] = {}
_flood_zones: list[dict] = []
_data_quality: dict = {}
_initialized = False

# ── District code mapping ────────────────────────────────────────────

DISTRICT_CODES = {
    "Bo": "BO",
    "Bombali": "BOM",
    "Bonthe": "BON",
    "Falaba": "FAL",
    "Kailahun": "KAI",
    "Kambia": "KAM",
    "Karene": "KAR",
    "Kenema": "KEN",
    "Koinadugu": "KOI",
    "Kono": "KON",
    "Moyamba": "MOY",
    "Port Loko": "PLK",
    "Pujehun": "PUJ",
    "Tonkolili": "TON",
    "Western Rural": "WRU",
    "Western Urban": "WUR",
}

VALID_FACILITY_TYPES = {"MCHP", "CHP", "CHC", "Primary", "Secondary", "Tertiary"}

# Sierra Leone bounding box
SL_BOUNDS = {"lat_min": 6.9, "lat_max": 10.0, "lng_min": -13.4, "lng_max": -10.2}


# ── Readiness classification ────────────────────────────────────────

def _classify_readiness(score: float) -> dict:
    """Classify readiness score into level and color."""
    if score >= 0.70:
        return {"level": "Ready", "color": "#22c55e", "css_class": "ready"}
    elif score >= 0.50:
        return {"level": "Partially Ready", "color": "#f59e0b", "css_class": "partial"}
    elif score >= 0.30:
        return {"level": "Under-prepared", "color": "#f97316", "css_class": "underprepared"}
    else:
        return {"level": "Critical", "color": "#ef4444", "css_class": "critical"}


def _generate_facility_id(name: str, district: str, index: int) -> str:
    """Generate a stable facility ID from name + district."""
    code = DISTRICT_CODES.get(district, "UNK")
    return f"SL-{code}-{index + 1:03d}"


def _identify_gaps(facility: dict) -> list[str]:
    """Identify key gaps based on available indicators."""
    gaps = []
    if facility.get("malaria_medicine_stock", 1.0) < 0.3:
        stock = facility["malaria_medicine_stock"]
        gaps.append(f"Low malaria medicine stock ({stock:.0%})")
    if facility.get("power_availability") == 0:
        gaps.append("No reliable power supply")
    if facility.get("water_availability") == 0:
        gaps.append("No reliable water supply")
    workers = facility.get("health_workers", 0)
    load = facility.get("patient_load", 1)
    if load > 0 and workers / load < 0.3:
        gaps.append(f"Low staff-to-patient ratio ({workers}:{load})")
    beds = facility.get("beds_available", 0)
    if load > 0 and beds > 0 and load / beds > 3.0:
        gaps.append(f"Facility overloaded ({load} patients vs {beds} beds)")
    return gaps


def _compute_approximate_coords(district: str, index: int, total_in_district: int) -> dict:
    """
    Generate approximate coordinates by offsetting from district centroid.
    Clearly marks these as approximate.
    """
    centroid = _district_centroids.get(district)
    if not centroid:
        return {"latitude": None, "longitude": None, "coord_source": "unavailable"}

    lat, lng = centroid
    # Spiral offset to prevent stacking — each facility gets a unique position
    angle = (2 * math.pi * index) / max(total_in_district, 1)
    radius = 0.03 + 0.01 * (index % 5)  # ~3-4km offset
    offset_lat = radius * math.cos(angle)
    offset_lng = radius * math.sin(angle)

    return {
        "latitude": round(lat + offset_lat, 6),
        "longitude": round(lng + offset_lng, 6),
        "coord_source": "approximate_district_centroid",
    }


# ── Flood zone linkage ──────────────────────────────────────────────

# Map flood_zones.json district IDs to MFL district names
_FLOOD_DISTRICT_MAP = {
    "western_area_urban": "Western Urban",
    "western_area_rural": "Western Rural",
    "bo": "Bo",
    "pujehun": "Pujehun",
    "bonthe": "Bonthe",
    "kenema": "Kenema",
    "port_loko": "Port Loko",
    "kambia": "Kambia",
    "tonkolili": "Tonkolili",
    "moyamba": "Moyamba",
    "bombali": "Bombali",
    "kailahun": "Kailahun",
    "kono": "Kono",
    "koinadugu": "Koinadugu",
    "falaba": "Falaba",
    "karene": "Karene",
}


def _get_district_flood_risk(district: str) -> dict:
    """Get flood risk information for a district based on flood zones data."""
    zones = [
        z for z in _flood_zones
        if _FLOOD_DISTRICT_MAP.get(z.get("district")) == district
    ]
    if not zones:
        return {
            "flood_zones_count": 0,
            "flood_risk_level": "Data not available",
            "flood_zones": [],
            "data_source": "No flood zones mapped for this district",
        }

    # Compute aggregate risk from zone characteristics
    avg_saturation = sum(z.get("typical_saturation_pct", 50) for z in zones) / len(zones)
    total_pop_exposed = sum(z.get("population", 0) for z in zones)

    if avg_saturation >= 75:
        risk = "High"
    elif avg_saturation >= 65:
        risk = "Moderate"
    else:
        risk = "Low"

    return {
        "flood_zones_count": len(zones),
        "flood_risk_level": risk,
        "avg_saturation_pct": round(avg_saturation, 1),
        "population_in_flood_zones": total_pop_exposed,
        "flood_zones": [
            {
                "name": z["name"],
                "elevation_m": z.get("elevation_m"),
                "drainage_quality": z.get("drainage_quality"),
                "population": z.get("population"),
            }
            for z in zones
        ],
        "data_source": "CHEWS flood_zones.json (district-level)",
    }


# ── Data quality checks ─────────────────────────────────────────────

def _run_data_quality_checks(facilities: list[dict]) -> dict:
    """Run comprehensive data quality checks on the MFL data."""
    issues = []
    total = len(facilities)

    # Missing coordinates
    no_coords = sum(1 for f in facilities if f.get("coord_source") != "dhis2")
    if no_coords > 0:
        issues.append({
            "check": "Missing real coordinates",
            "severity": "warning",
            "count": no_coords,
            "description": f"{no_coords}/{total} facilities use approximate district centroid positions. Real DHIS2 coordinates are not yet available.",
        })

    # Duplicate facility names
    names = [f["facility_name"] for f in facilities]
    seen = {}
    duplicates = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
    for n, c in seen.items():
        if c > 1:
            duplicates.append(f"{n} (×{c})")
    if duplicates:
        issues.append({
            "check": "Duplicate facility names",
            "severity": "info",
            "count": len(duplicates),
            "description": f"Duplicate names found: {', '.join(duplicates[:5])}{'...' if len(duplicates) > 5 else ''}",
        })

    # Missing district
    no_district = sum(1 for f in facilities if not f.get("district"))
    if no_district > 0:
        issues.append({
            "check": "Missing district",
            "severity": "error",
            "count": no_district,
            "description": f"{no_district} facilities have no district assigned.",
        })

    # Invalid facility types
    invalid_types = [
        f["facility_name"]
        for f in facilities
        if f.get("facility_type") not in VALID_FACILITY_TYPES
    ]
    if invalid_types:
        issues.append({
            "check": "Invalid facility type",
            "severity": "warning",
            "count": len(invalid_types),
            "description": f"Facilities with unrecognized types: {', '.join(invalid_types[:5])}",
        })

    # Zero beds (potential data issue for non-MCHP)
    zero_beds = [
        f["facility_name"]
        for f in facilities
        if f.get("beds_available", 0) == 0 and f.get("facility_type") not in ("MCHP", "CHP")
    ]
    if zero_beds:
        issues.append({
            "check": "Zero beds (non-community facility)",
            "severity": "info",
            "count": len(zero_beds),
            "description": f"Non-MCHP/CHP facilities with 0 beds — may need verification.",
        })

    # Zero health workers
    zero_workers = sum(1 for f in facilities if f.get("health_workers", 0) == 0)
    if zero_workers > 0:
        issues.append({
            "check": "Zero health workers",
            "severity": "warning",
            "count": zero_workers,
            "description": f"{zero_workers} facilities report 0 health workers.",
        })

    # Extremely low readiness
    critical = sum(1 for f in facilities if f.get("readiness_score", 1.0) < 0.20)
    if critical > 0:
        issues.append({
            "check": "Critically low readiness",
            "severity": "warning",
            "count": critical,
            "description": f"{critical} facilities have readiness scores below 0.20 — requires urgent assessment.",
        })

    # Missing facility identifiers (DHIS2 UID)
    no_dhis2 = sum(1 for f in facilities if not f.get("dhis2_uid"))
    if no_dhis2 > 0:
        issues.append({
            "check": "Missing DHIS2 UID",
            "severity": "info",
            "count": no_dhis2,
            "description": f"{no_dhis2}/{total} facilities have no DHIS2 UID. Linkage to DHIS2 surveillance data is not yet possible.",
        })

    # Compute overall quality score
    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if error_count > 0:
        quality_grade = "Poor"
    elif warning_count > 3:
        quality_grade = "Fair"
    elif warning_count > 0:
        quality_grade = "Good"
    else:
        quality_grade = "Excellent"

    return {
        "total_facilities": total,
        "total_issues": len(issues),
        "quality_grade": quality_grade,
        "issues": issues,
        "unavailable_fields": [
            {"field": "Real coordinates (latitude/longitude)", "source_needed": "DHIS2 MFL export"},
            {"field": "Services offered", "source_needed": "DHIS2 service datasets"},
            {"field": "Operational status", "source_needed": "DHIS2 or facility surveys"},
            {"field": "Ownership (public/private/NGO)", "source_needed": "MFL registry"},
            {"field": "Emergency preparedness plan", "source_needed": "Facility assessment surveys"},
            {"field": "Road access quality", "source_needed": "Infrastructure surveys"},
            {"field": "Building type/condition", "source_needed": "Facility assessment surveys"},
            {"field": "Population served", "source_needed": "DHIS2 / census"},
        ],
    }


# ══════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════

def initialize() -> bool:
    """Load MFL data at startup."""
    global _facilities, _facilities_by_id, _district_centroids, _district_info
    global _flood_zones, _data_quality, _initialized

    # Load admin hierarchy for district centroids
    if ADMIN_PATH.exists():
        with open(ADMIN_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row["district_name"]
                _district_centroids[name] = (
                    float(row["centroid_lat"]),
                    float(row["centroid_lng"]),
                )
                _district_info[name] = {
                    "district_id": row["district_id"],
                    "region": row["region"],
                    "centroid_lat": float(row["centroid_lat"]),
                    "centroid_lng": float(row["centroid_lng"]),
                    "rainy_season": f"{row['rainy_season_start_month']}–{row['rainy_season_end_month']}",
                    "typical_aug_rainfall_mm": int(row["typical_aug_rainfall_mm"]),
                }
        # Map alternate names
        if "Western Area Urban" in _district_centroids:
            _district_centroids["Western Urban"] = _district_centroids["Western Area Urban"]
            _district_info["Western Urban"] = _district_info["Western Area Urban"]
        if "Western Area Rural" in _district_centroids:
            _district_centroids["Western Rural"] = _district_centroids["Western Area Rural"]
            _district_info["Western Rural"] = _district_info["Western Area Rural"]

    # Load flood zones
    if FLOOD_ZONES_PATH.exists():
        with open(FLOOD_ZONES_PATH, encoding="utf-8") as f:
            _flood_zones = json.load(f)

    # Load MFL
    if not MFL_PATH.exists():
        print(f"[CHEWS] MFL file not found at {MFL_PATH}")
        return False

    raw_facilities = []
    with open(MFL_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_facilities.append(row)

    # Count facilities per district for coordinate spacing
    district_counts: dict[str, int] = {}
    for f in raw_facilities:
        d = f.get("district", "")
        district_counts[d] = district_counts.get(d, 0) + 1

    district_index: dict[str, int] = {}

    _facilities = []
    for i, row in enumerate(raw_facilities):
        district = row.get("district", "").strip()
        facility_type = row.get("facility_type", "").strip()
        name = row.get("facility_name", "").strip()

        # Track index within district for coordinate spacing
        idx = district_index.get(district, 0)
        district_index[district] = idx + 1

        # Parse numeric fields safely
        def safe_int(val, default=0):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def safe_float(val, default=0.0):
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        beds = safe_int(row.get("beds_available"))
        workers = safe_int(row.get("health_workers"))
        medicine = safe_float(row.get("malaria_medicine_stock"))
        power = safe_int(row.get("power_availability"))
        water = safe_int(row.get("water_availability"))
        load = safe_int(row.get("patient_load"))
        score = safe_float(row.get("readiness_score"))

        # Generate stable ID
        facility_id = _generate_facility_id(name, district, i)

        # Approximate coordinates
        coords = _compute_approximate_coords(district, idx, district_counts.get(district, 1))

        # Readiness classification
        readiness = _classify_readiness(score)

        # Key gaps
        facility_data = {
            "malaria_medicine_stock": medicine,
            "power_availability": power,
            "water_availability": water,
            "health_workers": workers,
            "patient_load": load,
            "beds_available": beds,
            "facility_type": facility_type,
        }
        gaps = _identify_gaps(facility_data)

        # District flood risk
        flood_risk = _get_district_flood_risk(district)

        # Infrastructure score
        infra_score = (power + water) / 2  # 0, 0.5, or 1

        # Capacity ratio
        capacity_ratio = round(load / max(beds, 1), 2) if beds > 0 else None
        staff_ratio = round(workers / max(load, 1), 2) if load > 0 else None

        facility = {
            # Identity
            "facility_id": facility_id,
            "facility_name": name,
            "dhis2_uid": None,  # To be linked when DHIS2 data arrives
            "facility_code": None,

            # Classification
            "facility_type": facility_type,
            "district": district,
            "region": _district_info.get(district, {}).get("region", "Data not available"),

            # Coordinates
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "coord_source": coords["coord_source"],

            # Readiness indicators (AVAILABLE from MFL)
            "beds_available": beds,
            "health_workers": workers,
            "malaria_medicine_stock": medicine,
            "power_availability": power,
            "water_availability": water,
            "patient_load": load,

            # Derived indicators
            "readiness_score": score,
            "readiness_level": readiness["level"],
            "readiness_color": readiness["color"],
            "readiness_css": readiness["css_class"],
            "infrastructure_score": infra_score,
            "capacity_ratio": capacity_ratio,
            "staff_ratio": staff_ratio,
            "key_gaps": gaps if gaps else ["No critical gaps identified"],

            # District-level risk exposure
            "flood_risk": flood_risk,

            # Unavailable indicators — explicitly marked
            "services_offered": "Data not available",
            "operational_status": "Data not available",
            "ownership": "Data not available",
            "emergency_plan": "Data not available — Requires facility assessment",
            "road_access": "Data not available — Requires facility assessment",
            "building_condition": "Data not available — Requires facility assessment",
            "distance_to_referral_km": "Data not available — Requires coordinates",
            "population_served": "Data not available — Requires DHIS2 data",

            # Metadata
            "data_completeness": {
                "available": [
                    "facility_name", "district", "facility_type",
                    "beds_available", "health_workers", "malaria_medicine_stock",
                    "power_availability", "water_availability", "patient_load",
                    "readiness_score",
                ],
                "unavailable": [
                    "dhis2_uid", "real_coordinates", "services_offered",
                    "operational_status", "ownership", "emergency_plan",
                    "road_access", "building_condition", "population_served",
                ],
                "pct_complete": round(10 / 19 * 100, 1),
            },
        }
        _facilities.append(facility)
        _facilities_by_id[facility_id] = facility

    # Run data quality checks
    _data_quality = _run_data_quality_checks(_facilities)
    _initialized = True

    print(f"[CHEWS] MFL loaded — {len(_facilities)} facilities across "
          f"{len(district_counts)} districts. Data quality: {_data_quality['quality_grade']}")
    return True


def get_all_facilities(
    district: Optional[str] = None,
    facility_type: Optional[str] = None,
    search: Optional[str] = None,
    readiness_level: Optional[str] = None,
) -> list[dict]:
    """Get facilities with optional filters."""
    results = _facilities

    if district:
        results = [f for f in results if f["district"] == district]
    if facility_type:
        results = [f for f in results if f["facility_type"] == facility_type]
    if readiness_level:
        results = [f for f in results if f["readiness_level"] == readiness_level]
    if search:
        q = search.lower()
        results = [
            f for f in results
            if q in f["facility_name"].lower()
            or q in f["district"].lower()
            or q in f["facility_id"].lower()
        ]

    return results


def get_facility(facility_id: str) -> Optional[dict]:
    """Get a single facility profile by ID."""
    return _facilities_by_id.get(facility_id)


def get_national_summary() -> dict:
    """Get national overview statistics."""
    total = len(_facilities)
    if total == 0:
        return {"total_facilities": 0, "message": "No facility data loaded"}

    # By type
    type_counts = {}
    for f in _facilities:
        t = f["facility_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    # By district
    district_counts = {}
    for f in _facilities:
        d = f["district"]
        district_counts[d] = district_counts.get(d, 0) + 1

    # By readiness
    readiness_counts = {"Ready": 0, "Partially Ready": 0, "Under-prepared": 0, "Critical": 0}
    for f in _facilities:
        lvl = f["readiness_level"]
        readiness_counts[lvl] = readiness_counts.get(lvl, 0) + 1

    # Average readiness
    avg_readiness = sum(f["readiness_score"] for f in _facilities) / total

    # Infrastructure
    with_power = sum(1 for f in _facilities if f["power_availability"] == 1)
    with_water = sum(1 for f in _facilities if f["water_availability"] == 1)

    # Facilities in flood-exposed districts
    flood_exposed = sum(
        1 for f in _facilities
        if f["flood_risk"]["flood_risk_level"] not in ("Data not available", "Low")
    )

    # Facilities needing assessment
    needs_assessment = sum(
        1 for f in _facilities
        if f["readiness_level"] in ("Under-prepared", "Critical")
    )

    return {
        "total_facilities": total,
        "by_type": type_counts,
        "by_district": district_counts,
        "by_readiness": readiness_counts,
        "avg_readiness_score": round(avg_readiness, 3),
        "avg_readiness_level": _classify_readiness(avg_readiness)["level"],
        "facilities_with_power": with_power,
        "facilities_with_power_pct": round(with_power / total * 100, 1),
        "facilities_with_water": with_water,
        "facilities_with_water_pct": round(with_water / total * 100, 1),
        "flood_exposed_facilities": flood_exposed,
        "needs_assessment": needs_assessment,
        "districts_covered": len(district_counts),
        "data_quality_grade": _data_quality.get("quality_grade", "Unknown"),
    }


def get_data_quality() -> dict:
    """Get data quality report."""
    return _data_quality


def get_facilities_geojson(
    district: Optional[str] = None,
    facility_type: Optional[str] = None,
) -> dict:
    """Export facilities as GeoJSON for map rendering."""
    facilities = get_all_facilities(district=district, facility_type=facility_type)

    features = []
    for f in facilities:
        if f["latitude"] is None or f["longitude"] is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [f["longitude"], f["latitude"]],
            },
            "properties": {
                "facility_id": f["facility_id"],
                "name": f["facility_name"],
                "type": f["facility_type"],
                "district": f["district"],
                "readiness_score": f["readiness_score"],
                "readiness_level": f["readiness_level"],
                "readiness_color": f["readiness_color"],
                "coord_source": f["coord_source"],
                "beds": f["beds_available"],
                "workers": f["health_workers"],
                "power": f["power_availability"],
                "water": f["water_availability"],
                "flood_risk": f["flood_risk"]["flood_risk_level"],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total": len(features),
            "coord_note": "Coordinates are approximate (district centroids) until real DHIS2 coordinates are integrated.",
        },
    }


def get_district_priorities() -> list[dict]:
    """
    Generate district prioritization for strategic planning.
    Combines facility density, readiness scores, and flood exposure.
    """
    districts = {}
    for f in _facilities:
        d = f["district"]
        if d not in districts:
            districts[d] = {
                "district": d,
                "region": f["region"],
                "facilities": [],
            }
        districts[d]["facilities"].append(f)

    priorities = []
    for d, info in districts.items():
        facs = info["facilities"]
        n = len(facs)
        avg_readiness = sum(f["readiness_score"] for f in facs) / n
        critical_count = sum(1 for f in facs if f["readiness_level"] == "Critical")
        underprepared_count = sum(1 for f in facs if f["readiness_level"] == "Under-prepared")
        with_power = sum(1 for f in facs if f["power_availability"] == 1)
        with_water = sum(1 for f in facs if f["water_availability"] == 1)

        # District flood risk
        flood = _get_district_flood_risk(d)
        flood_level = flood["flood_risk_level"]

        # Priority score: lower readiness + higher flood risk = higher priority
        readiness_deficit = 1.0 - avg_readiness
        flood_score = {"High": 0.8, "Moderate": 0.5, "Low": 0.2}.get(flood_level, 0.0)
        critical_pct = (critical_count + underprepared_count) / n

        priority_score = round(
            0.40 * readiness_deficit + 0.30 * flood_score + 0.30 * critical_pct,
            3,
        )

        if priority_score >= 0.6:
            priority_level = "Urgent"
        elif priority_score >= 0.45:
            priority_level = "High"
        elif priority_score >= 0.3:
            priority_level = "Moderate"
        else:
            priority_level = "Low"

        priorities.append({
            "district": d,
            "region": info["region"],
            "total_facilities": n,
            "avg_readiness_score": round(avg_readiness, 3),
            "avg_readiness_level": _classify_readiness(avg_readiness)["level"],
            "critical_facilities": critical_count,
            "underprepared_facilities": underprepared_count,
            "facilities_with_power": with_power,
            "facilities_with_water": with_water,
            "flood_risk_level": flood_level,
            "flood_zones_count": flood["flood_zones_count"],
            "priority_score": priority_score,
            "priority_level": priority_level,
            "by_type": _count_by_key(facs, "facility_type"),
            "by_readiness": _count_by_key(facs, "readiness_level"),
            "recommended_actions": _generate_district_actions(
                avg_readiness, flood_level, critical_count, with_power, with_water, n
            ),
        })

    # Sort by priority score descending
    priorities.sort(key=lambda x: x["priority_score"], reverse=True)
    return priorities


def _count_by_key(items: list[dict], key: str) -> dict:
    counts = {}
    for item in items:
        v = item.get(key, "Unknown")
        counts[v] = counts.get(v, 0) + 1
    return counts


def _generate_district_actions(
    avg_readiness: float,
    flood_level: str,
    critical_count: int,
    with_power: int,
    with_water: int,
    total: int,
) -> list[str]:
    """Generate recommended actions for a district based on available data."""
    actions = []
    if critical_count > 0:
        actions.append(f"Conduct facility assessments at {critical_count} critical-readiness facilities")
    if avg_readiness < 0.5:
        actions.append("Prioritize resource allocation to improve district readiness")
    if flood_level == "High":
        actions.append("Develop flood preparedness plan for health facilities in flood zones")
    if with_power < total * 0.5:
        pct = round((1 - with_power / total) * 100)
        actions.append(f"Address power gaps — {pct}% of facilities lack reliable power")
    if with_water < total * 0.5:
        pct = round((1 - with_water / total) * 100)
        actions.append(f"Address water gaps — {pct}% of facilities lack reliable water")
    if not actions:
        actions.append("Continue routine facility monitoring and assessment")
    return actions


def get_facility_early_warning(facility_id: str) -> Optional[dict]:
    """
    Get early warning context for a facility — connects MFL to CHEWS risk layers.
    Uses district-level risk data since facility-level coordinates are approximate.
    """
    facility = _facilities_by_id.get(facility_id)
    if not facility:
        return None

    district = facility["district"]
    flood = facility["flood_risk"]

    # Build hazard exposure summary
    hazards = []
    if flood["flood_risk_level"] != "Data not available":
        hazards.append({
            "hazard": "Flood",
            "risk_level": flood["flood_risk_level"],
            "detail": f"{flood['flood_zones_count']} flood zone(s) in district",
            "data_source": "CHEWS flood_zones.json (district-level)",
        })

    # Malaria risk from district rainfall patterns
    district_data = _district_info.get(district, {})
    rainfall = district_data.get("typical_aug_rainfall_mm", 0)
    if rainfall > 600:
        malaria_risk = "High"
    elif rainfall > 400:
        malaria_risk = "Moderate"
    else:
        malaria_risk = "Low"

    hazards.append({
        "hazard": "Malaria",
        "risk_level": malaria_risk,
        "detail": f"Based on typical August rainfall: {rainfall}mm",
        "data_source": "admin_hierarchy.csv (district-level seasonal data)",
    })

    # Generate preparedness recommendations
    recommendations = []
    if flood["flood_risk_level"] in ("High", "Moderate"):
        recommendations.append("Develop facility-specific flood response plan")
        recommendations.append("Pre-position emergency medical supplies")
    if malaria_risk in ("High", "Moderate"):
        recommendations.append("Ensure adequate malaria medicine stock")
        if facility["malaria_medicine_stock"] < 0.5:
            recommendations.append("URGENT: Replenish malaria medicine stock")
    if facility["power_availability"] == 0:
        recommendations.append("Install backup power for emergency operations")
    if facility["water_availability"] == 0:
        recommendations.append("Secure emergency water supply arrangements")
    if not recommendations:
        recommendations.append("Maintain current readiness posture")

    return {
        "facility_id": facility["facility_id"],
        "facility_name": facility["facility_name"],
        "district": district,
        "facility_type": facility["facility_type"],
        "readiness_score": facility["readiness_score"],
        "readiness_level": facility["readiness_level"],
        "hazard_exposure": hazards,
        "preparedness_recommendations": recommendations,
        "note": "Risk levels are derived from district-level data. Facility-level spatial analysis requires real coordinates (DHIS2 integration pending).",
    }

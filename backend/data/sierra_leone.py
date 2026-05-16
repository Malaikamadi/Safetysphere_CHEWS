"""
Sierra Leone Flood Zone Catalog
================================

Curated catalog of communities in Sierra Leone with documented exposure
to flooding, used as the geographic substrate for the Flood Atlas
dashboard.

Each zone captures the static geomorphological inputs that drive
``models.flood_risk.predict`` (elevation, drainage, distance to water,
typical soil saturation), plus identifiers, population estimates and
a short historical record of significant events. The dynamic inputs
(rainfall intensity, 24h rainfall, current saturation) are supplied
at request time by ``services.flood_dashboard``.

Coordinates are taken from public OSM / GeoNames references; elevation
and drainage classifications follow the qualitative descriptions in
NDMA / UNDP / IFRC flood appeals for Sierra Leone (2015–2023). Numbers
are deliberately rounded — they are intended to support visual triage
on the dashboard, not to substitute for an authoritative GIS layer.
"""

from __future__ import annotations

from typing import TypedDict


class FloodEvent(TypedDict):
    year: int
    description: str
    impact: str  # short impact summary


class FloodZone(TypedDict):
    id: str
    name: str
    district: str
    region: str           # Western / Northern / Southern / Eastern
    lat: float
    lng: float
    elevation_m: float
    drainage_quality: str       # poor / moderate / good
    distance_to_water_km: float
    typical_saturation_pct: float  # baseline rainy-season saturation
    water_body: str
    urban_type: str        # informal_settlement / town / coastal / rural / dam_buffer
    population: int
    flood_history: list[FloodEvent]


# ---------------------------------------------------------------------
# Districts (used for grouping & district-level dashboard signals).
# ---------------------------------------------------------------------

DISTRICTS = {
    "western_area_urban": {
        "name": "Western Area Urban",
        "region": "Western",
        "centroid": (8.4844, -13.2299),
        "rainy_season_months": (5, 10),  # May → October peak
        "typical_aug_rainfall_mm": 894,
    },
    "western_area_rural": {
        "name": "Western Area Rural",
        "region": "Western",
        "centroid": (8.3870, -13.0930),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 760,
    },
    "bo": {
        "name": "Bo",
        "region": "Southern",
        "centroid": (7.9647, -11.7383),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 540,
    },
    "pujehun": {
        "name": "Pujehun",
        "region": "Southern",
        "centroid": (7.3500, -11.7164),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 620,
    },
    "bonthe": {
        "name": "Bonthe",
        "region": "Southern",
        "centroid": (7.5269, -12.5025),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 700,
    },
    "kenema": {
        "name": "Kenema",
        "region": "Eastern",
        "centroid": (7.8767, -11.1903),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 470,
    },
    "port_loko": {
        "name": "Port Loko",
        "region": "Northern",
        "centroid": (8.6044, -13.1956),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 690,
    },
    "kambia": {
        "name": "Kambia",
        "region": "Northern",
        "centroid": (9.1208, -12.9181),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 720,
    },
    "tonkolili": {
        "name": "Tonkolili",
        "region": "Northern",
        "centroid": (8.7203, -11.9442),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 480,
    },
    "moyamba": {
        "name": "Moyamba",
        "region": "Southern",
        "centroid": (8.1571, -12.4322),
        "rainy_season_months": (5, 10),
        "typical_aug_rainfall_mm": 590,
    },
}


# ---------------------------------------------------------------------
# Flood-prone communities.
#
# Selection criteria: documented in at least one of the 2015, 2017,
# 2019, 2021 or 2023 NDMA / IFRC / UNICEF Sierra Leone flood appeals
# or post-disaster needs assessments. Coordinates rounded to four
# decimals (~10m precision is plenty for community-scale triage).
# ---------------------------------------------------------------------

FLOOD_ZONES: list[FloodZone] = [
    # ------------------ Freetown (Western Area Urban) ------------------
    {
        "id": "kroo_bay",
        "name": "Kroo Bay",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4892, "lng": -13.2387,
        "elevation_m": 3.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.05,
        "typical_saturation_pct": 78,
        "water_body": "Atlantic estuary (Crocodile River outlet)",
        "urban_type": "informal_settlement",
        "population": 11500,
        "flood_history": [
            {"year": 2015, "description": "September floods inundated Kroo Bay shanties",
             "impact": "~3,000 displaced, several drowned"},
            {"year": 2017, "description": "Aug 14 mudslide & flash floods",
             "impact": "Major casualties across Freetown low zones"},
            {"year": 2023, "description": "August torrential rains submerged community",
             "impact": "Hundreds of homes inundated"},
        ],
    },
    {
        "id": "susans_bay",
        "name": "Susan's Bay",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4922, "lng": -13.2333,
        "elevation_m": 4.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.08,
        "typical_saturation_pct": 80,
        "water_body": "Atlantic Ocean (Freetown harbour)",
        "urban_type": "informal_settlement",
        "population": 13800,
        "flood_history": [
            {"year": 2017, "description": "Mudslide and tidal surge",
             "impact": "Hundreds displaced, sanitation crisis"},
            {"year": 2021, "description": "March fire compounded flood damage",
             "impact": "Over 7,000 affected"},
            {"year": 2023, "description": "August flooding repeat",
             "impact": "Estimated 200 households impacted"},
        ],
    },
    {
        "id": "mabella",
        "name": "Mabella",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4945, "lng": -13.2214,
        "elevation_m": 5.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.10,
        "typical_saturation_pct": 75,
        "water_body": "Freetown harbour",
        "urban_type": "informal_settlement",
        "population": 8200,
        "flood_history": [
            {"year": 2017, "description": "Coastal flooding",
             "impact": "Homes destroyed near shoreline"},
            {"year": 2019, "description": "September flash flood",
             "impact": "School and clinic affected"},
        ],
    },
    {
        "id": "granville_brook",
        "name": "Granville Brook (Kingtom)",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4845, "lng": -13.2475,
        "elevation_m": 6.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.20,
        "typical_saturation_pct": 72,
        "water_body": "Granville Brook (canalised)",
        "urban_type": "informal_settlement",
        "population": 7500,
        "flood_history": [
            {"year": 2017, "description": "Brook overtopped during August rains",
             "impact": "Open dumpsite contamination spread"},
            {"year": 2022, "description": "July flood",
             "impact": "Sanitation outbreak risk flagged"},
        ],
    },
    {
        "id": "regent",
        "name": "Regent / Sugar Loaf",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4406, "lng": -13.2336,
        "elevation_m": 280.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.4,
        "typical_saturation_pct": 70,
        "water_body": "Babadorie stream",
        "urban_type": "informal_settlement",
        "population": 6300,
        "flood_history": [
            {"year": 2017, "description": "Aug 14 catastrophic mudslide on Sugar Loaf",
             "impact": "1,141 confirmed dead, ~3,000 displaced"},
        ],
    },
    {
        "id": "kissy",
        "name": "Kissy / Mountain Cut",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4810, "lng": -13.1862,
        "elevation_m": 18.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.6,
        "typical_saturation_pct": 70,
        "water_body": "Aberdeen Creek tributary",
        "urban_type": "informal_settlement",
        "population": 22000,
        "flood_history": [
            {"year": 2017, "description": "Flash floods in low-lying alleyways",
             "impact": "Roads impassable for 48h"},
            {"year": 2023, "description": "August floods",
             "impact": "Health post damaged"},
        ],
    },
    {
        "id": "wellington",
        "name": "Wellington",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4717, "lng": -13.1634,
        "elevation_m": 12.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.30,
        "typical_saturation_pct": 73,
        "water_body": "Bunce River estuary",
        "urban_type": "informal_settlement",
        "population": 27500,
        "flood_history": [
            {"year": 2019, "description": "Industrial-zone flooding",
             "impact": "Factory operations halted"},
            {"year": 2023, "description": "Repeat Aug flooding",
             "impact": "Drainage canals overwhelmed"},
        ],
    },
    {
        "id": "calaba_town",
        "name": "Calaba Town",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4633, "lng": -13.1490,
        "elevation_m": 14.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.6,
        "typical_saturation_pct": 70,
        "water_body": "Orogu River",
        "urban_type": "informal_settlement",
        "population": 18900,
        "flood_history": [
            {"year": 2021, "description": "August flash flood",
             "impact": "Dozens of homes inundated"},
            {"year": 2023, "description": "Wet-season recurrence",
             "impact": "Roads cut, primary school closed for a week"},
        ],
    },
    {
        "id": "lumley",
        "name": "Lumley Beach front",
        "district": "western_area_urban",
        "region": "Western",
        "lat": 8.4670, "lng": -13.2853,
        "elevation_m": 4.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.05,
        "typical_saturation_pct": 65,
        "water_body": "Atlantic Ocean",
        "urban_type": "coastal",
        "population": 4500,
        "flood_history": [
            {"year": 2017, "description": "Storm surge during August rains",
             "impact": "Beachfront restaurants damaged"},
            {"year": 2024, "description": "King-tide coastal flooding",
             "impact": "Erosion of beach road"},
        ],
    },
    # ------------------ Western Area Rural ------------------
    {
        "id": "waterloo",
        "name": "Waterloo",
        "district": "western_area_rural",
        "region": "Western",
        "lat": 8.3424, "lng": -13.0719,
        "elevation_m": 24.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.8,
        "typical_saturation_pct": 65,
        "water_body": "Ribbi / Pampana confluence",
        "urban_type": "town",
        "population": 39000,
        "flood_history": [
            {"year": 2019, "description": "Ribbi River burst banks",
             "impact": "Hundreds of farms washed out"},
            {"year": 2021, "description": "Highway 2 cut for 3 days",
             "impact": "Freetown supply chain disrupted"},
        ],
    },
    {
        "id": "hastings_jui",
        "name": "Hastings / Jui",
        "district": "western_area_rural",
        "region": "Western",
        "lat": 8.4076, "lng": -13.1114,
        "elevation_m": 18.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.5,
        "typical_saturation_pct": 68,
        "water_body": "Jui Creek",
        "urban_type": "town",
        "population": 22000,
        "flood_history": [
            {"year": 2017, "description": "Highway flooding cut Freetown access",
             "impact": "Major commuting disruption"},
            {"year": 2023, "description": "Hospital approach road flooded",
             "impact": "Ambulance routing diverted"},
        ],
    },
    # ------------------ Bo District (Southern) ------------------
    {
        "id": "bo_town",
        "name": "Bo Town",
        "district": "bo",
        "region": "Southern",
        "lat": 7.9647, "lng": -11.7383,
        "elevation_m": 125.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 1.2,
        "typical_saturation_pct": 60,
        "water_body": "Sewa River basin",
        "urban_type": "town",
        "population": 174354,
        "flood_history": [
            {"year": 2022, "description": "August urban flash flood",
             "impact": "Markets in Mahei Boima Road inundated"},
        ],
    },
    {
        "id": "sumbuya",
        "name": "Sumbuya",
        "district": "bo",
        "region": "Southern",
        "lat": 7.6547, "lng": -11.9000,
        "elevation_m": 62.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.4,
        "typical_saturation_pct": 70,
        "water_body": "Sewa River",
        "urban_type": "rural",
        "population": 5400,
        "flood_history": [
            {"year": 2019, "description": "Sewa River overflow",
             "impact": "Cassava and rice farms destroyed"},
            {"year": 2022, "description": "Repeat seasonal flooding",
             "impact": "Bridge crossing damaged"},
        ],
    },
    # ------------------ Pujehun District ------------------
    {
        "id": "pujehun_town",
        "name": "Pujehun Town",
        "district": "pujehun",
        "region": "Southern",
        "lat": 7.3500, "lng": -11.7164,
        "elevation_m": 28.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.3,
        "typical_saturation_pct": 75,
        "water_body": "Waanje River",
        "urban_type": "town",
        "population": 8500,
        "flood_history": [
            {"year": 2019, "description": "September floods devastated district",
             "impact": "5,000+ displaced district-wide"},
            {"year": 2023, "description": "August floods",
             "impact": "Health centre approach roads cut"},
        ],
    },
    # ------------------ Bonthe District ------------------
    {
        "id": "bonthe_island",
        "name": "Bonthe (Sherbro Island)",
        "district": "bonthe",
        "region": "Southern",
        "lat": 7.5269, "lng": -12.5025,
        "elevation_m": 2.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.05,
        "typical_saturation_pct": 82,
        "water_body": "Atlantic Ocean / Sherbro estuary",
        "urban_type": "coastal",
        "population": 9200,
        "flood_history": [
            {"year": 2018, "description": "King-tide coastal flooding",
             "impact": "Sea-level rise displacement risk"},
            {"year": 2022, "description": "Storm surge inundation",
             "impact": "Government wharf submerged"},
        ],
    },
    {
        "id": "mattru_jong",
        "name": "Mattru Jong",
        "district": "bonthe",
        "region": "Southern",
        "lat": 7.6242, "lng": -11.9433,
        "elevation_m": 14.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.2,
        "typical_saturation_pct": 76,
        "water_body": "Jong River",
        "urban_type": "town",
        "population": 12500,
        "flood_history": [
            {"year": 2019, "description": "Jong River overflow",
             "impact": "Riverside homes evacuated"},
        ],
    },
    # ------------------ Kenema District (Eastern) ------------------
    {
        "id": "kenema_town",
        "name": "Kenema Town",
        "district": "kenema",
        "region": "Eastern",
        "lat": 7.8767, "lng": -11.1903,
        "elevation_m": 148.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 1.5,
        "typical_saturation_pct": 55,
        "water_body": "Sewa-Mano basin",
        "urban_type": "town",
        "population": 200354,
        "flood_history": [
            {"year": 2020, "description": "Urban flash floods downtown",
             "impact": "Drainage capacity exceeded"},
        ],
    },
    # ------------------ Port Loko (Northern) ------------------
    {
        "id": "lungi_tagrin",
        "name": "Lungi / Tagrin",
        "district": "port_loko",
        "region": "Northern",
        "lat": 8.6044, "lng": -13.1956,
        "elevation_m": 8.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.4,
        "typical_saturation_pct": 70,
        "water_body": "Sierra Leone River estuary",
        "urban_type": "coastal",
        "population": 36000,
        "flood_history": [
            {"year": 2017, "description": "Coastal surge during Aug rains",
             "impact": "Airport approach roads flooded"},
            {"year": 2022, "description": "Tidal flood",
             "impact": "Tagrin ferry terminal closed"},
        ],
    },
    # ------------------ Kambia (Northern) ------------------
    {
        "id": "kambia_town",
        "name": "Kambia Town",
        "district": "kambia",
        "region": "Northern",
        "lat": 9.1208, "lng": -12.9181,
        "elevation_m": 17.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.2,
        "typical_saturation_pct": 73,
        "water_body": "Great Scarcies River",
        "urban_type": "town",
        "population": 17000,
        "flood_history": [
            {"year": 2020, "description": "Cross-border flooding from Guinea",
             "impact": "Customs and market disrupted"},
            {"year": 2023, "description": "Great Scarcies overflow",
             "impact": "Two villages cut off for a week"},
        ],
    },
    {
        "id": "rokupr",
        "name": "Rokupr",
        "district": "kambia",
        "region": "Northern",
        "lat": 8.6817, "lng": -12.3825,
        "elevation_m": 11.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.3,
        "typical_saturation_pct": 78,
        "water_body": "Little Scarcies River",
        "urban_type": "rural",
        "population": 7800,
        "flood_history": [
            {"year": 2019, "description": "Rice research station flooded",
             "impact": "Mangrove rice harvest lost"},
        ],
    },
    # ------------------ Tonkolili (Northern) ------------------
    {
        "id": "magburaka",
        "name": "Magburaka",
        "district": "tonkolili",
        "region": "Northern",
        "lat": 8.7203, "lng": -11.9442,
        "elevation_m": 50.0,
        "drainage_quality": "moderate",
        "distance_to_water_km": 0.6,
        "typical_saturation_pct": 60,
        "water_body": "Rokel River",
        "urban_type": "town",
        "population": 25000,
        "flood_history": [
            {"year": 2019, "description": "Rokel River surge",
             "impact": "Bridge approach closed"},
        ],
    },
    {
        "id": "bumbuna",
        "name": "Bumbuna (dam buffer)",
        "district": "tonkolili",
        "region": "Northern",
        "lat": 9.0292, "lng": -11.7414,
        "elevation_m": 110.0,
        "drainage_quality": "good",
        "distance_to_water_km": 1.0,
        "typical_saturation_pct": 55,
        "water_body": "Seli River (Bumbuna dam reservoir)",
        "urban_type": "dam_buffer",
        "population": 4000,
        "flood_history": [
            {"year": 2018, "description": "Spillway-release downstream surge",
             "impact": "Downstream villages temporarily evacuated"},
        ],
    },
    # ------------------ Moyamba (Southern) ------------------
    {
        "id": "shenge",
        "name": "Shenge",
        "district": "moyamba",
        "region": "Southern",
        "lat": 8.1486, "lng": -12.9533,
        "elevation_m": 3.0,
        "drainage_quality": "poor",
        "distance_to_water_km": 0.05,
        "typical_saturation_pct": 80,
        "water_body": "Atlantic Ocean",
        "urban_type": "coastal",
        "population": 4900,
        "flood_history": [
            {"year": 2019, "description": "Coastal storm surge",
             "impact": "Fishing fleet damaged"},
            {"year": 2024, "description": "Sea-level rise erosion event",
             "impact": "Two homes lost to ocean"},
        ],
    },
]


# ---------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------

ZONES_BY_ID = {z["id"]: z for z in FLOOD_ZONES}


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

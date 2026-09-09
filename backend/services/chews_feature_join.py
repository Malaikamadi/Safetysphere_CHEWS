"""
Join curated DHIS2 *health* rows with separate climate / environment / population layers.

Does not invent DHIS2 climate. Does not call or retrain malaria_predictor.
Prototype GBT remaining gaps are flagged on each row.
"""

from __future__ import annotations

from typing import Optional

# Exact feature order expected by models/malaria_predictor.py (trained artifact).
PROTOTYPE_GBT_FEATURES = [
    "rainfall_mm",
    "temperature_c",
    "humidity_percent",
    "water_stagnation_index",
    "mosquito_breeding_sites",
    "reported_fever_cases",
    "population_density",
    "district_encoded",
    "rain_x_stagnation",
    "temp_humidity_index",
    "breeding_density",
]

DHIS2_HEALTH_FIELDS = (
    "malaria_confirmed",
    "malaria_confirmed_u5",
    "malaria_tests",
    "malaria_rdt_positive",
)

CLIMATE_FIELDS = ("rainfall_mm", "temperature_c", "humidity_percent")
ENVIRONMENT_FIELDS = ("water_stagnation_index", "mosquito_breeding_sites")
POPULATION_FIELDS = ("population_density",)


def _key(row: dict, *, period_field: str = "source_period") -> tuple:
    period = row.get(period_field) or row.get("period")
    ou = row.get("org_unit_id")
    district = (row.get("district_name") or row.get("district") or "").casefold()
    return (period, ou, district)


def _lookup(rows: Optional[list[dict]], period, org_unit_id, district_name) -> Optional[dict]:
    if not rows:
        return None
    want_d = (district_name or "").casefold()
    for row in rows:
        rp = row.get("source_period") or row.get("period")
        if rp != period:
            continue
        if org_unit_id and row.get("org_unit_id") == org_unit_id:
            return row
        rd = (row.get("district") or row.get("district_name") or "").casefold()
        if want_d and rd == want_d:
            return row
    return None


def join_feature_rows(
    dhis2_malaria: list[dict],
    *,
    climate: Optional[list[dict]] = None,
    environment: Optional[list[dict]] = None,
    population: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Left-join DHIS2 curated malaria onto other sources.
    Unmatched climate/env/pop fields stay None (not 0).
    """
    out = []
    for health in dhis2_malaria:
        period = health.get("source_period") or health.get("period")
        ou = health.get("org_unit_id")
        district = health.get("district_name") or health.get("district")
        clim = _lookup(climate, period, ou, district) or {}
        env = _lookup(environment, period, ou, district) or {}
        pop = _lookup(population, period, ou, district) or {}

        rainfall = clim.get("rainfall_mm")
        temp = clim.get("temperature_c")
        humidity = clim.get("humidity_percent")
        stag = env.get("water_stagnation_index")
        breeding = env.get("mosquito_breeding_sites")
        dens = pop.get("population_density")

        rain_x = None
        if rainfall is not None and stag is not None:
            rain_x = rainfall * stag
        temp_h = None
        if temp is not None and humidity is not None:
            temp_h = temp * humidity / 100
        breed_d = None
        if breeding is not None and stag is not None:
            breed_d = breeding * stag

        row = {
            "source_period": period,
            "period": period,
            "period_type": health.get("period_type"),
            "normalized_period": health.get("normalized_period"),
            "district": district,
            "facility": health.get("facility_name") or health.get("facility"),
            "org_unit_id": ou,
            "latitude": health.get("latitude"),
            "longitude": health.get("longitude"),
            "malaria_confirmed": health.get("malaria_confirmed"),
            "malaria_confirmed_u5": health.get("malaria_confirmed_u5"),
            "malaria_tests": health.get("malaria_tests"),
            "malaria_rdt_positive": health.get("malaria_rdt_positive"),
            "rainfall_mm": rainfall,
            "temperature_c": temp,
            "humidity_percent": humidity,
            "water_stagnation_index": stag,
            "mosquito_breeding_sites": breeding,
            "population_density": dens,
            "reported_fever_cases": None,
            "malaria_cases": None,
            "district_encoded": None,
            "rain_x_stagnation": rain_x,
            "temp_humidity_index": temp_h,
            "breeding_density": breed_d,
            "join_notes": "DHIS2 health left-joined; climate/environment/population from other sources only",
        }
        missing_gbt = [f for f in PROTOTYPE_GBT_FEATURES if row.get(f) is None]
        row["prototype_gbt_compatible"] = len(missing_gbt) == 0
        row["prototype_gbt_missing"] = missing_gbt
        out.append(row)
    return out

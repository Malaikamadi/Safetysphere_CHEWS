"""
Strategic Planning Router — Area 1
====================================
Endpoints for hazard mapping, vulnerability scoring, pollution hotspots, carbon accounting.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from data import sierra_leone as sl
from models import air_quality, flood_risk, heat_stress, carbon_accounting
from services import vulnerability, flood_dashboard

router = APIRouter(prefix="/strategic", tags=["Area 1: Strategic Planning"])


# --- Schemas ---
class VulnerabilityInput(BaseModel):
    facility_type: str = Field(default="health_center")
    building_type: str = Field(default="semi_permanent")
    flood_risk: float = Field(default=0.3, ge=0, le=1)
    heat_risk: float = Field(default=0.3, ge=0, le=1)
    air_quality_risk: float = Field(default=0.3, ge=0, le=1)
    malaria_risk: float = Field(default=0.3, ge=0, le=1)
    population_under5: int = Field(default=0, ge=0)
    population_pregnant: int = Field(default=0, ge=0)
    population_elderly: int = Field(default=0, ge=0)
    total_population: int = Field(default=100, ge=1)
    water_source: str = Field(default="borehole")
    power_source: str = Field(default="grid_unreliable")
    staff_count: int = Field(default=5, ge=0)
    has_emergency_plan: bool = Field(default=False)
    road_access: str = Field(default="paved")
    distance_to_referral_km: float = Field(default=10.0, ge=0)


class HazardMapInput(BaseModel):
    location_name: str = Field(default="Community Health Center")
    latitude: float = Field(default=8.484, ge=-90, le=90)
    longitude: float = Field(default=-13.234, ge=-180, le=180)
    rainfall: float = Field(default=100, ge=0)
    temperature: float = Field(default=28, ge=-10, le=55)
    humidity: float = Field(default=70, ge=0, le=100)
    pm25: float = Field(default=20, ge=0)
    rainfall_intensity: float = Field(default=5, ge=0)
    elevation: float = Field(default=50, ge=0)


class PollutionInput(BaseModel):
    pm25: float = Field(default=0, ge=0)
    pm10: float = Field(default=0, ge=0)
    o3: float = Field(default=0, ge=0)
    no2: float = Field(default=0, ge=0)
    so2: float = Field(default=0, ge=0)
    has_children: bool = Field(default=True)
    has_respiratory_conditions: bool = Field(default=False)


class CarbonInput(BaseModel):
    facility_type: str = Field(default="health_center")
    floor_area_sqm: float = Field(default=200)
    diesel_liters_month: float = Field(default=0, ge=0)
    petrol_liters_month: float = Field(default=0, ge=0)
    lpg_liters_month: float = Field(default=0, ge=0)
    kerosene_liters_month: float = Field(default=0, ge=0)
    charcoal_kg_month: float = Field(default=0, ge=0)
    wood_kg_month: float = Field(default=0, ge=0)
    electricity_kwh_month: float = Field(default=0, ge=0)
    grid_region: str = Field(default="sierra_leone")
    has_solar: bool = Field(default=False)
    solar_kwh_month: float = Field(default=0, ge=0)
    generator_hours_month: float = Field(default=0, ge=0)
    generator_fuel: str = Field(default="diesel")
    generator_consumption_lph: float = Field(default=3.0)


# --- Endpoints ---
@router.post("/vulnerability-score")
async def get_vulnerability_score(data: VulnerabilityInput):
    """Generate composite vulnerability score for a health facility or school."""
    result = vulnerability.score_facility(
        facility_type=data.facility_type, building_type=data.building_type,
        flood_risk=data.flood_risk, heat_risk=data.heat_risk,
        air_quality_risk=data.air_quality_risk, malaria_risk=data.malaria_risk,
        population_under5=data.population_under5,
        population_pregnant=data.population_pregnant,
        population_elderly=data.population_elderly,
        total_population=data.total_population,
        water_source=data.water_source, power_source=data.power_source,
        staff_count=data.staff_count, has_emergency_plan=data.has_emergency_plan,
        road_access=data.road_access,
        distance_to_referral_km=data.distance_to_referral_km,
    )
    return result._asdict()


@router.post("/hazard-map")
async def generate_hazard_map(data: HazardMapInput):
    """Generate multi-layer hazard assessment for a location."""
    from models import environmental, epidemiological
    env = environmental.predict(data.rainfall, data.temperature, data.humidity)
    aq = air_quality.predict(pm25=data.pm25)
    fl = flood_risk.predict(rainfall_intensity=data.rainfall_intensity, elevation=data.elevation)
    ht = heat_stress.predict(temperature=data.temperature, humidity=data.humidity)

    return {
        "location": data.location_name,
        "coordinates": {"lat": data.latitude, "lng": data.longitude},
        "hazard_layers": {
            "malaria": {"score": env.score, "factors": env.factors},
            "air_quality": {"aqi": aq.aqi, "category": aq.category, "health_risk": aq.health_risk},
            "flood": {"score": fl.risk_score, "level": fl.risk_level},
            "heat": {"score": ht.risk_score, "level": ht.risk_level, "wbgt": ht.wbgt},
        },
        "composite_hazard": round(
            0.30 * env.score + 0.25 * aq.health_risk + 0.25 * fl.risk_score + 0.20 * ht.risk_score, 4
        ),
    }


@router.post("/pollution-hotspot")
async def assess_pollution(data: PollutionInput):
    """Assess pollution levels and identify hotspot potential."""
    result = air_quality.predict(
        pm25=data.pm25, pm10=data.pm10, o3=data.o3, no2=data.no2, so2=data.so2,
        has_children=data.has_children,
        has_respiratory_conditions=data.has_respiratory_conditions,
    )
    return {
        "aqi": result.aqi, "category": result.category,
        "health_risk": result.health_risk,
        "dominant_pollutant": result.dominant_pollutant,
        "pollutant_scores": result.pollutant_scores,
        "child_risk_multiplier": result.child_risk_multiplier,
        "is_hotspot": result.aqi > 100,
        "factors": result.factors,
        "recommendations": result.recommendations,
    }


# ---------------------------------------------------------------------
# Flood Atlas — Sierra Leone
# ---------------------------------------------------------------------

class DistrictOverride(BaseModel):
    rainfall_intensity_mult: Optional[float] = Field(default=None, ge=0, le=10)
    rainfall_24h_mult: Optional[float] = Field(default=None, ge=0, le=10)
    saturation_offset: Optional[float] = Field(default=None, ge=-100, le=100)


class FloodForecastInput(BaseModel):
    """Scenario inputs for the Flood Atlas 'what-if' simulator.

    A flat block applies to every district. ``per_district`` lets the
    UI pin overrides to specific districts (e.g. only soak Western
    Area Urban while leaving Bo unchanged).
    """
    rainfall_intensity_mult: float = Field(default=1.0, ge=0, le=10)
    rainfall_24h_mult: float = Field(default=1.0, ge=0, le=10)
    saturation_offset: float = Field(default=0.0, ge=-100, le=100)
    per_district: Optional[dict[str, DistrictOverride]] = None
    seed: Optional[int] = None


@router.get("/flood-zones")
async def flood_zones():
    """Return the static catalog of flood-prone communities in
    Sierra Leone (real coordinates, elevation, drainage, history)."""
    return {
        "country": "Sierra Leone",
        "bounds": sl.country_bounds(),
        "districts": sl.list_districts(),
        "zones": sl.list_zones(),
    }


@router.get("/flood-dashboard")
async def flood_dashboard_view(seed: Optional[int] = Query(default=None)):
    """Live Flood Atlas snapshot.

    Combines per-district synthetic live signals (rainfall intensity,
    24h rainfall, soil saturation, river stage, tide stage) with the
    static catalog and runs the flood-risk model for every zone.
    Returns aggregate KPIs, district signals, and per-zone
    predictions ready to render on a map.

    Pass ``seed`` to pin the snapshot for screenshots or tests.
    """
    return flood_dashboard.snapshot(seed=seed)


@router.post("/flood-forecast")
async def flood_forecast(scenario: FloodForecastInput):
    """Re-run the Flood Atlas snapshot with scenario overrides.

    Use this from the UI to answer questions like "if rainfall doubled
    in Western Area Urban, who would tip into the Severe band?".
    """
    overrides: dict = {}
    if scenario.per_district:
        for did, ov in scenario.per_district.items():
            if did not in sl.DISTRICTS:
                raise HTTPException(status_code=400, detail=f"unknown district: {did}")
            overrides[did] = {k: v for k, v in ov.model_dump().items() if v is not None}
    if not overrides:
        # Flat overrides — apply to all districts.
        flat = {
            "rainfall_intensity_mult": scenario.rainfall_intensity_mult,
            "rainfall_24h_mult": scenario.rainfall_24h_mult,
            "saturation_offset": scenario.saturation_offset,
        }
        overrides = flat
    return flood_dashboard.snapshot(overrides=overrides, seed=scenario.seed)


@router.get("/flood-zone/{zone_id}/forecast")
async def flood_zone_forecast(zone_id: str, hours: int = Query(default=24, ge=1, le=72)):
    """Return a per-zone hourly forecast strip for the next ``hours``
    hours (default 24)."""
    fc = flood_dashboard.zone_forecast(zone_id, hours=hours)
    if fc.get("error"):
        raise HTTPException(status_code=404, detail=fc["error"])
    return fc


# ---------------------------------------------------------------------
# Carbon Footprint
# ---------------------------------------------------------------------

@router.post("/carbon-footprint")
async def estimate_carbon(data: CarbonInput):
    """Estimate facility carbon footprint and reduction opportunities."""
    result = carbon_accounting.predict(
        facility_type=data.facility_type, floor_area_sqm=data.floor_area_sqm,
        diesel_liters_month=data.diesel_liters_month,
        petrol_liters_month=data.petrol_liters_month,
        lpg_liters_month=data.lpg_liters_month,
        kerosene_liters_month=data.kerosene_liters_month,
        charcoal_kg_month=data.charcoal_kg_month,
        wood_kg_month=data.wood_kg_month,
        electricity_kwh_month=data.electricity_kwh_month,
        grid_region=data.grid_region, has_solar=data.has_solar,
        solar_kwh_month=data.solar_kwh_month,
        generator_hours_month=data.generator_hours_month,
        generator_fuel=data.generator_fuel,
        generator_consumption_lph=data.generator_consumption_lph,
    )
    return result._asdict()

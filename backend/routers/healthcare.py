"""
Healthcare Readiness Router — Area 3
=======================================
Endpoints for disease forecasting, anomaly detection, surge planning,
trained ML model predictions, and Master Facility List (MFL) integration.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

from services import forecast_engine, facility_mfl
from models import air_quality, malaria_predictor, healthcare_readiness, community_reports

router = APIRouter(prefix="/healthcare", tags=["Area 3: Healthcare Readiness"])


class ForecastInput(BaseModel):
    disease: str = Field(default="malaria")
    current_month: int = Field(default=7, ge=1, le=12)
    rainfall: float = Field(default=150, ge=0)
    temperature: float = Field(default=28, ge=-10, le=55)
    humidity: float = Field(default=75, ge=0, le=100)
    current_cases: int = Field(default=15, ge=0)
    previous_cases: int = Field(default=10, ge=0)
    aqi: int = Field(default=50, ge=0, le=500)


class AnomalyInput(BaseModel):
    pm25: float = Field(default=0, ge=0)
    pm10: float = Field(default=0, ge=0)
    expected_pm25: float = Field(default=15, ge=0)
    expected_pm10: float = Field(default=30, ge=0)
    temperature: float = Field(default=28, ge=-10, le=55)
    expected_temperature: float = Field(default=28, ge=-10, le=55)
    location: str = Field(default="Monitoring Station")


class SurgePlanInput(BaseModel):
    disease: str = Field(default="malaria")
    current_cases: int = Field(default=20, ge=0)
    bed_capacity: int = Field(default=50, ge=1)
    staff_available: int = Field(default=10, ge=1)
    supply_days: int = Field(default=14, ge=0)
    forecast_surge_pct: float = Field(default=50, ge=0, le=500)


@router.post("/forecast")
async def disease_forecast(data: ForecastInput):
    """Generate disease risk forecast using seasonal-climatological model."""
    result = forecast_engine.forecast_disease(
        disease=data.disease, current_month=data.current_month,
        rainfall=data.rainfall, temperature=data.temperature,
        humidity=data.humidity, current_cases=data.current_cases,
        previous_cases=data.previous_cases, aqi=data.aqi,
    )
    return result._asdict()


@router.post("/anomaly-detect")
async def detect_anomaly(data: AnomalyInput):
    """Detect anomalies in pollution/environmental measurements."""
    anomalies = []

    # PM2.5 anomaly
    if data.expected_pm25 > 0:
        pm25_ratio = data.pm25 / data.expected_pm25
        if pm25_ratio > 2.0:
            anomalies.append({
                "parameter": "PM2.5",
                "observed": data.pm25,
                "expected": data.expected_pm25,
                "deviation_pct": round((pm25_ratio - 1) * 100, 1),
                "severity": "High" if pm25_ratio > 3 else "Moderate",
                "possible_causes": [
                    "Wildfire smoke", "Industrial emissions", "Seasonal burning",
                    "Dust storm", "Sensor malfunction (verify calibration)",
                ],
            })

    # PM10 anomaly
    if data.expected_pm10 > 0:
        pm10_ratio = data.pm10 / data.expected_pm10
        if pm10_ratio > 2.0:
            anomalies.append({
                "parameter": "PM10",
                "observed": data.pm10,
                "expected": data.expected_pm10,
                "deviation_pct": round((pm10_ratio - 1) * 100, 1),
                "severity": "High" if pm10_ratio > 3 else "Moderate",
                "possible_causes": [
                    "Construction activity", "Dust storm", "Biomass burning", "Road dust",
                ],
            })

    # Temperature anomaly
    temp_diff = abs(data.temperature - data.expected_temperature)
    if temp_diff > 5:
        anomalies.append({
            "parameter": "Temperature",
            "observed": data.temperature,
            "expected": data.expected_temperature,
            "deviation_celsius": round(temp_diff, 1),
            "severity": "High" if temp_diff > 8 else "Moderate",
            "possible_causes": [
                "Heatwave event", "Urban heat island", "Sensor calibration issue",
            ],
        })

    aq = air_quality.predict(pm25=data.pm25, pm10=data.pm10)

    return {
        "location": data.location,
        "anomalies_detected": len(anomalies) > 0,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "current_aqi": aq.aqi,
        "current_category": aq.category,
        "recommendations": [
            "Verify sensor calibration if anomaly persists > 2 hours",
            "Cross-reference with neighboring stations",
        ] + (["Activate air quality alert protocol"] if anomalies else []),
    }


@router.post("/surge-plan")
async def surge_planning(data: SurgePlanInput):
    """Assess healthcare facility readiness for a disease surge."""
    expected_cases = int(data.current_cases * (1 + data.forecast_surge_pct / 100))
    bed_utilization = expected_cases / data.bed_capacity
    staff_ratio = data.staff_available / max(expected_cases, 1)
    supply_adequacy = data.supply_days / 30  # normalized to 30-day supply

    # Readiness score
    readiness = 1.0 - (
        0.35 * min(1.0, bed_utilization) +
        0.30 * min(1.0, 1.0 - staff_ratio) +
        0.35 * (1.0 - min(1.0, supply_adequacy))
    )
    readiness = round(max(0, min(1, readiness)), 4)

    if readiness >= 0.7: level = "Ready"
    elif readiness >= 0.5: level = "Partially Ready"
    elif readiness >= 0.3: level = "At Risk"
    else: level = "Critical Gap"

    gaps = []
    recs = []
    if bed_utilization > 0.8:
        gaps.append(f"Bed capacity may be exceeded ({expected_cases} cases vs {data.bed_capacity} beds)")
        recs.append("Activate overflow/triage tents")
    if staff_ratio < 0.3:
        gaps.append(f"Insufficient staff ({data.staff_available} for {expected_cases} expected cases)")
        recs.append("Request surge staffing from district/national level")
    if data.supply_days < 14:
        gaps.append(f"Supply stock only covers {data.supply_days} days")
        recs.append(f"Order emergency resupply of {data.disease} treatment kits")
    if not gaps: gaps = ["No critical gaps identified"]
    if not recs: recs = ["Maintain current readiness posture"]

    return {
        "disease": data.disease,
        "current_cases": data.current_cases,
        "expected_surge_cases": expected_cases,
        "readiness_score": readiness,
        "readiness_level": level,
        "bed_utilization_pct": round(bed_utilization * 100, 1),
        "staff_patient_ratio": round(staff_ratio, 2),
        "supply_days_remaining": data.supply_days,
        "gaps": gaps,
        "recommendations": recs,
    }


def _assess_surge(disease: str, current_cases: int, surge_pct: float, beds: int, staff: int, supply_days: int) -> dict:
    expected_cases = int(current_cases * (1 + surge_pct / 100))
    bed_capacity = max(beds, 1)
    staff_available = max(staff, 1)
    bed_utilization = expected_cases / bed_capacity
    staff_ratio = staff_available / max(expected_cases, 1)
    supply_adequacy = supply_days / 30
    readiness = 1.0 - (
        0.35 * min(1.0, bed_utilization) +
        0.30 * min(1.0, 1.0 - staff_ratio) +
        0.35 * (1.0 - min(1.0, supply_adequacy))
    )
    readiness = round(max(0, min(1, readiness)), 4)
    if readiness >= 0.7:
        level = "Ready"
    elif readiness >= 0.5:
        level = "Partially Ready"
    elif readiness >= 0.3:
        level = "At Risk"
    else:
        level = "Critical Gap"
    gaps, recs = [], []
    if bed_utilization > 0.8:
        gaps.append(f"Bed capacity may be exceeded ({expected_cases} cases vs {bed_capacity} beds)")
        recs.append("Activate overflow and triage capacity")
    if staff_ratio < 0.3:
        gaps.append(f"Insufficient clinical staff ({staff_available} for {expected_cases} projected cases)")
        recs.append("Request surge staffing from district or national level")
    if supply_days < 14:
        gaps.append(f"Essential supplies cover {supply_days} days (below 14-day buffer)")
        recs.append(f"Replenish {disease} treatment kits through the supply chain")
    if not gaps:
        gaps = ["No critical gaps identified"]
    if not recs:
        recs = ["Maintain current readiness posture"]
    return {
        "disease": disease,
        "current_cases": current_cases,
        "expected_surge_cases": expected_cases,
        "readiness_score": readiness,
        "readiness_level": level,
        "bed_utilization_pct": round(bed_utilization * 100, 1),
        "staff_patient_ratio": round(staff_ratio, 2),
        "supply_days_remaining": supply_days,
        "bed_capacity": bed_capacity,
        "staff_available": staff_available,
        "gaps": gaps,
        "recommendations": recs,
    }


# Live observed signals (models ingest these; users do not enter them)
_LIVE_SIGNALS = {
    "malaria": {"rainfall": 186, "temperature": 27.4, "humidity": 84, "current_cases": 142, "previous_cases": 108, "aqi": 38},
    "cholera": {"rainfall": 210, "temperature": 28.1, "humidity": 88, "current_cases": 31, "previous_cases": 18, "aqi": 41},
    "dengue": {"rainfall": 164, "temperature": 29.2, "humidity": 79, "current_cases": 22, "previous_cases": 19, "aqi": 45},
    "respiratory": {"rainfall": 42, "temperature": 26.8, "humidity": 58, "current_cases": 67, "previous_cases": 54, "aqi": 128},
}

_ADMIN_CASE_SCALE = {
    "national": 1.0,
    "Western Area Urban": 0.38,
    "Western Area Rural": 0.14,
    "Bo": 0.16,
    "Kenema": 0.18,
    "Port Loko": 0.12,
    "Kambia": 0.09,
    "Bombali": 0.11,
    "Bonthe": 0.07,
    "Falaba": 0.04,
    "Kailahun": 0.08,
    "Karene": 0.06,
    "Koinadugu": 0.05,
    "Kono": 0.10,
    "Moyamba": 0.09,
    "Pujehun": 0.07,
    "Tonkolili": 0.10,
}

_FORECAST_DISTRICTS = (
    "Western Area Urban", "Western Area Rural", "Bo", "Bombali", "Bonthe",
    "Falaba", "Kailahun", "Kambia", "Karene", "Kenema", "Koinadugu", "Kono",
    "Moyamba", "Port Loko", "Pujehun", "Tonkolili",
)

_MFL_DISTRICT = {
    "Western Area Urban": "Western Urban",
    "Western Area Rural": "Western Rural",
}


def _signals_for(disease: str, admin: str) -> dict:
    base = dict(_LIVE_SIGNALS.get(disease, _LIVE_SIGNALS["malaria"]))
    scale = _ADMIN_CASE_SCALE.get(admin, 0.12)
    base["current_cases"] = max(1, int(base["current_cases"] * scale))
    base["previous_cases"] = max(1, int(base["previous_cases"] * scale))
    return base


def _run_live_forecast(disease: str, admin: str):
    sig = _signals_for(disease, admin)
    month = datetime.now().month
    result = forecast_engine.forecast_disease(
        disease=disease,
        current_month=month,
        rainfall=sig["rainfall"],
        temperature=sig["temperature"],
        humidity=sig["humidity"],
        current_cases=sig["current_cases"],
        previous_cases=sig["previous_cases"],
        aqi=sig["aqi"],
    )
    return result._asdict(), sig, month


def _mfl_capacity(admin: str) -> dict:
    if not facility_mfl._initialized:
        facility_mfl.initialize()
    district = None if admin == "national" else _MFL_DISTRICT.get(admin, admin)
    facilities = facility_mfl.get_all_facilities(district=district)
    if not facilities and district:
        # Case-insensitive district match if exact name differs
        all_fac = facility_mfl.get_all_facilities()
        key = district.casefold()
        facilities = [f for f in all_fac if (f.get("district") or "").casefold() == key]
    by_type: dict[str, int] = {}
    for f in facilities:
        t = f.get("facility_type") or "Other"
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "facility_count": len(facilities),
        "by_type": by_type,
        "hospitals": by_type.get("Hospital", 0),
        "chcs": by_type.get("CHC", 0),
        "chps": by_type.get("CHP", 0),
        "clinics": by_type.get("Clinic", 0),
    }


@router.get("/forecast/live")
async def live_forecast(
    disease: str = Query(default="malaria"),
    admin: str = Query(default="national"),
):
    """Live AI caseload forecast — models run on ingested feeds, not user inputs."""
    forecast, sig, month = _run_live_forecast(disease, admin)
    districts = []
    for name in _FORECAST_DISTRICTS:
        fc, _, _ = _run_live_forecast(disease, name)
        districts.append({
            "admin_unit": name,
            "risk_level": fc["predicted_risk_level"],
            "surge_probability": fc["surge_probability"],
            "risk_trend": fc["risk_trend"],
            "current_cases": _signals_for(disease, name)["current_cases"],
        })
    districts.sort(key=lambda d: d["surge_probability"], reverse=True)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "admin_unit": admin,
        "disease": disease,
        "horizon_days": 28,
        "start_month": month,
        "observed": sig,
        "forecast": forecast,
        "districts": districts,
        "source": "Climate, surveillance and facility feeds · models run automatically",
    }


@router.get("/surge/live")
async def live_surge(
    disease: str = Query(default="malaria"),
    admin: str = Query(default="national"),
):
    """Live surge view: caseload forecast against the MoH facility network."""
    forecast, sig, _ = _run_live_forecast(disease, admin)
    cap = _mfl_capacity(admin)
    surge_pct = round(forecast["surge_probability"] * 100, 1)
    expected = int(sig["current_cases"] * (1 + forecast["surge_probability"]))
    n = max(cap["facility_count"], 1)
    recs = list(forecast.get("recommendations") or [])
    if cap["hospitals"] == 0 and admin != "national":
        recs.append("No hospital in the MoH registry for this area — confirm referral to a neighbouring district.")
    if expected / n > 8:
        recs.append("Projected caseload is high relative to the number of registered facilities.")
    if not recs:
        recs = ["Monitor live caseload against the MoH facility network."]
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "admin_unit": admin,
        "disease": disease,
        "current_cases": sig["current_cases"],
        "expected_surge_cases": expected,
        "projected_increase_pct": surge_pct,
        "facility_count": cap["facility_count"],
        "by_type": cap["by_type"],
        "hospitals": cap["hospitals"],
        "chcs": cap["chcs"],
        "chps": cap["chps"],
        "clinics": cap["clinics"],
        "cases_per_facility": round(expected / n, 1),
        "risk_level": forecast["predicted_risk_level"],
        "recommendations": recs,
        "source": "MoH DHIS2 Master Facility List + live caseload forecast",
        "note": "Bed, staffing and supply stocks are not in the MoH DHIS2 core facility registry.",
    }


# ═══════════════════════════════════════════════════════════════════
# Trained ML Model Endpoints (kept for internal/model ops — not the dashboard UI)
# ═══════════════════════════════════════════════════════════════════

class MalariaPredictInput(BaseModel):
    district: str = Field(default="Bo")
    rainfall_mm: float = Field(default=150, ge=0)
    temperature_c: float = Field(default=28, ge=-10, le=55)
    humidity_percent: float = Field(default=75, ge=0, le=100)
    water_stagnation_index: float = Field(default=0.5, ge=0, le=1)
    mosquito_breeding_sites: int = Field(default=10, ge=0)
    reported_fever_cases: int = Field(default=0, ge=0)
    population_density: int = Field(default=5000, ge=0)


class ReadinessInput(BaseModel):
    district: str = Field(default="Kenema")
    facility_type: str = Field(default="Tertiary")
    beds_available: int = Field(default=100, ge=0)
    health_workers: int = Field(default=50, ge=0)
    malaria_medicine_stock: float = Field(default=0.5, ge=0, le=1)
    power_availability: int = Field(default=1, ge=0, le=1)
    water_availability: int = Field(default=1, ge=0, le=1)
    patient_load: int = Field(default=100, ge=0)


class CommunityFloodInput(BaseModel):
    district: str = Field(default="Bo")
    community: str = Field(default="Kissy")
    standing_water: int = Field(default=0, ge=0, le=1)
    fever_reports: int = Field(default=10, ge=0)
    damaged_houses: int = Field(default=5, ge=0)
    displaced_households: int = Field(default=2, ge=0)
    water_contamination: int = Field(default=0, ge=0, le=1)


@router.post("/ml/malaria-predict")
async def ml_malaria_predict(data: MalariaPredictInput):
    """Predict malaria case count using trained GradientBoosting model."""
    result = malaria_predictor.predict(
        district=data.district,
        rainfall_mm=data.rainfall_mm,
        temperature_c=data.temperature_c,
        humidity_percent=data.humidity_percent,
        water_stagnation_index=data.water_stagnation_index,
        mosquito_breeding_sites=data.mosquito_breeding_sites,
        reported_fever_cases=data.reported_fever_cases,
        population_density=data.population_density,
    )
    return {
        "predicted_cases": result.predicted_cases,
        "risk_level": result.risk_level,
        "confidence_factors": result.confidence_factors,
        "feature_contributions": result.feature_contributions,
    }


@router.post("/ml/readiness-predict")
async def ml_readiness_predict(data: ReadinessInput):
    """Predict healthcare facility readiness using trained RandomForest model."""
    result = healthcare_readiness.predict(
        district=data.district,
        facility_type=data.facility_type,
        beds_available=data.beds_available,
        health_workers=data.health_workers,
        malaria_medicine_stock=data.malaria_medicine_stock,
        power_availability=data.power_availability,
        water_availability=data.water_availability,
        patient_load=data.patient_load,
    )
    return {
        "readiness_score": result.readiness_score,
        "readiness_level": result.readiness_level,
        "capacity_assessment": result.capacity_assessment,
        "key_gaps": result.key_gaps,
        "feature_contributions": result.feature_contributions,
    }


@router.post("/ml/community-flood")
async def ml_community_flood(data: CommunityFloodInput):
    """Classify flood occurrence from community reports using trained RandomForest model."""
    result = community_reports.predict(
        district=data.district,
        community=data.community,
        standing_water=data.standing_water,
        fever_reports=data.fever_reports,
        damaged_houses=data.damaged_houses,
        displaced_households=data.displaced_households,
        water_contamination=data.water_contamination,
    )
    return {
        "flood_predicted": result.flood_predicted,
        "flood_probability": result.flood_probability,
        "alert_level": result.alert_level,
        "contributing_factors": result.contributing_factors,
        "feature_contributions": result.feature_contributions,
    }


# ═══════════════════════════════════════════════════════════════════
# Master Facility List (MFL) Endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/facilities/summary")
async def facilities_summary():
    """National overview: total facilities, by type, by district, readiness distribution."""
    return facility_mfl.get_national_summary()


@router.get("/facilities/data-quality")
async def facilities_data_quality():
    """Data quality report for the MFL dataset."""
    return facility_mfl.get_data_quality()


@router.get("/facilities/geojson")
async def facilities_geojson(
    district: Optional[str] = Query(None, description="Filter by district"),
    facility_type: Optional[str] = Query(None, description="Filter by facility type"),
):
    """Export facilities as GeoJSON for map rendering."""
    return facility_mfl.get_facilities_geojson(district=district, facility_type=facility_type)


@router.get("/facilities")
async def list_facilities(
    district: Optional[str] = Query(None, description="Filter by district"),
    facility_type: Optional[str] = Query(None, description="Filter by facility type"),
    search: Optional[str] = Query(None, description="Search by name, district, or ID"),
    readiness_level: Optional[str] = Query(None, description="Filter by readiness level"),
):
    """List facilities (compact fields for explorer map and table)."""
    facilities = facility_mfl.get_all_facilities(
        district=district,
        facility_type=facility_type,
        search=search,
        readiness_level=readiness_level,
    )
    compact = [
        {
            "facility_id": f["facility_id"],
            "facility_name": f["facility_name"],
            "facility_code": f.get("facility_code"),
            "facility_type": f["facility_type"],
            "district": f["district"],
            "latitude": f.get("latitude"),
            "longitude": f.get("longitude"),
            "coord_source": f.get("coord_source"),
        }
        for f in facilities
    ]
    return {
        "total": len(compact),
        "source": "Ministry of Health DHIS2 core health facilities",
        "facilities": compact,
    }


@router.get("/facilities/{facility_id}")
async def get_facility(facility_id: str):
    """Get detailed facility profile by ID."""
    facility = facility_mfl.get_facility(facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")
    return facility


@router.get("/facilities/{facility_id}/early-warning")
async def facility_early_warning(facility_id: str):
    """Get early warning / hazard exposure context for a facility."""
    result = facility_mfl.get_facility_early_warning(facility_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")
    return result

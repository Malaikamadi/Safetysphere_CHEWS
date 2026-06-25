"""
Healthcare Readiness Router — Area 3
=======================================
Endpoints for disease forecasting, anomaly detection, surge planning,
and trained ML model predictions.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from services import forecast_engine
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


# ═══════════════════════════════════════════════════════════════════
# Trained ML Model Endpoints
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

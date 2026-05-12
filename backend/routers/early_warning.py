"""
Early Warning Router — Area 2
===============================
Endpoints for hyper-local alerts, sensor data assessment, and trigger management.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from models import air_quality, flood_risk, heat_stress
from services import alert_engine

router = APIRouter(prefix="/early-warning", tags=["Area 2: Early Warning"])


class EarlyWarningInput(BaseModel):
    location: str = Field(default="Freetown Community")
    temperature: float = Field(default=28, ge=-10, le=55)
    humidity: float = Field(default=70, ge=0, le=100)
    rainfall_intensity: float = Field(default=5, ge=0)
    rainfall_24h: float = Field(default=50, ge=0)
    pm25: float = Field(default=20, ge=0)
    pm10: float = Field(default=30, ge=0)
    wind_speed: float = Field(default=1.0, ge=0)
    uv_index: float = Field(default=5.0, ge=0, le=15)
    elevation: float = Field(default=50, ge=0)
    soil_saturation: float = Field(default=50, ge=0, le=100)


class AlertTriggerInput(BaseModel):
    hazard_type: str = Field(default="flood")
    current_value: float = Field(default=0.5, ge=0)
    location: str = Field(default="Unknown")
    context: str = Field(default="")


@router.post("/assess")
async def comprehensive_assessment(data: EarlyWarningInput):
    """Run comprehensive early warning assessment across all hazard types."""
    aq = air_quality.predict(pm25=data.pm25, pm10=data.pm10)
    fl = flood_risk.predict(
        rainfall_intensity=data.rainfall_intensity, rainfall_24h=data.rainfall_24h,
        elevation=data.elevation, soil_saturation=data.soil_saturation,
    )
    ht = heat_stress.predict(
        temperature=data.temperature, humidity=data.humidity, wind_speed=data.wind_speed,
    )

    # Generate alerts for any threshold exceedances
    alerts = []
    for hazard, value in [
        ("flood", fl.risk_score), ("heat", ht.risk_score), ("air_quality", aq.aqi),
    ]:
        alert = alert_engine.evaluate_alert(hazard, value, data.location)
        if alert:
            alerts.append(alert._asdict())

    # UV warning
    uv_level = "Low"
    uv_actions = []
    if data.uv_index >= 11:
        uv_level = "Extreme"
        uv_actions = ["Avoid outdoor exposure 10am–4pm", "Mandatory sun protection for outdoor workers"]
    elif data.uv_index >= 8:
        uv_level = "Very High"
        uv_actions = ["Seek shade during midday hours", "Apply SPF 30+ sunscreen"]
    elif data.uv_index >= 6:
        uv_level = "High"
        uv_actions = ["Wear protective clothing outdoors"]
    elif data.uv_index >= 3:
        uv_level = "Moderate"

    return {
        "location": data.location,
        "assessment_time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "hazards": {
            "air_quality": {"aqi": aq.aqi, "category": aq.category, "risk": aq.health_risk},
            "flood": {"score": fl.risk_score, "level": fl.risk_level, "impact": fl.estimated_impact},
            "heat": {"wbgt": ht.wbgt, "score": ht.risk_score, "category": ht.category, "heatwave": ht.is_heatwave},
            "uv": {"index": data.uv_index, "level": uv_level, "actions": uv_actions},
        },
        "active_alerts": alerts,
        "overall_threat_level": _overall_threat(fl.risk_score, ht.risk_score, aq.health_risk),
    }


@router.post("/trigger")
async def trigger_alert(data: AlertTriggerInput):
    """Manually trigger an alert or evaluate a sensor reading against thresholds."""
    alert = alert_engine.evaluate_alert(
        data.hazard_type, data.current_value, data.location, data.context,
    )
    if alert:
        return {"triggered": True, "alert": alert._asdict()}
    return {"triggered": False, "message": "Value below alert thresholds"}


@router.get("/alerts")
async def get_alerts(min_severity: str = "Advisory"):
    """Get all active alerts at or above the specified severity."""
    return {"alerts": alert_engine.get_active_alerts(min_severity)}


def _overall_threat(flood, heat, aq):
    """Calculate overall threat level from individual hazards."""
    max_threat = max(flood, heat, aq)
    if max_threat >= 0.8: return "Critical"
    elif max_threat >= 0.6: return "High"
    elif max_threat >= 0.4: return "Elevated"
    elif max_threat >= 0.2: return "Guarded"
    return "Normal"

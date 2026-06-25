"""
Flood Risk Model
=================
Predicts flood risk for communities and health facilities.
Uses multi-factor scoring: rainfall, elevation, drainage, proximity to water, soil saturation.
Supports both rule-based and trained ML model predictions.
"""

from __future__ import annotations
import numpy as np
import json
from pathlib import Path
from typing import NamedTuple

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False


class FloodRiskResult(NamedTuple):
    risk_score: float
    risk_level: str
    rainfall_contrib: float
    terrain_contrib: float
    drainage_contrib: float
    proximity_contrib: float
    saturation_contrib: float
    factors: list[str]
    recommendations: list[str]
    estimated_impact: str


DRAINAGE_SCORES = {"poor": 0.85, "moderate": 0.50, "good": 0.15}


def _rainfall_risk(intensity, total_24h):
    if intensity >= 50: i_score, factor = 0.95, f"Extreme rainfall ({intensity:.1f} mm/hr) — flash flood conditions"
    elif intensity >= 30: i_score, factor = 0.80, f"Very heavy rainfall ({intensity:.1f} mm/hr)"
    elif intensity >= 15: i_score, factor = 0.60, f"Heavy rainfall ({intensity:.1f} mm/hr)"
    elif intensity >= 7.5: i_score, factor = 0.35, f"Moderate rainfall ({intensity:.1f} mm/hr)"
    else: i_score, factor = 0.10, None
    accum = min(1.0, 0.5 + (total_24h - 100) / 200) if total_24h > 100 else (0.3 if total_24h > 50 else 0.0)
    if total_24h > 100 and not factor: factor = f"Heavy 24h rainfall ({total_24h:.0f}mm)"
    return round(float(min(1.0, i_score * 0.6 + accum * 0.4)), 4), factor


def _terrain_risk(elevation):
    if elevation <= 5: return 0.95, f"Very low elevation ({elevation:.0f}m) — extreme flood exposure"
    elif elevation <= 15: return 0.70, f"Low elevation ({elevation:.0f}m) — significant flood exposure"
    elif elevation <= 50: return round(0.70 - 0.45 * ((elevation - 15) / 35), 4), None
    elif elevation <= 100: return 0.15, None
    return 0.05, None


def _proximity_risk(distance_km):
    if distance_km <= 0.1: return 0.95, f"Adjacent to water body ({distance_km*1000:.0f}m)"
    elif distance_km <= 0.5: return 0.75, f"Near water body ({distance_km:.1f}km)"
    elif distance_km <= 1.0: return 0.45, None
    elif distance_km <= 3.0: return 0.20, None
    return 0.05, None


def _saturation_risk(pct):
    s = np.clip(pct, 0, 100)
    if s >= 90: return 0.95, f"Soil saturated ({s:.0f}%) — zero absorption"
    elif s >= 70: return 0.65, f"High soil saturation ({s:.0f}%)"
    elif s >= 50: return 0.35, None
    return 0.10, None


RECS = {
    "Low": ["Maintain routine flood monitoring", "Ensure drainage channels are clear"],
    "Moderate": ["Monitor water levels nearby", "Pre-position sandbags", "Alert community leaders"],
    "High": ["Activate flood early warning", "Move medical supplies to upper floors", "Pre-position water purification supplies"],
    "Severe": ["IMMEDIATE: Evacuate low-lying facilities", "Activate district disaster response", "Set up temporary health posts"],
    "Extreme": ["EMERGENCY: Full evacuation of flood-zone facilities", "Request national emergency support", "Deploy search and rescue"],
}

IMPACTS = {
    "Low": "Minimal impact expected",
    "Moderate": "Localized waterlogging possible",
    "High": "Significant flooding likely — health facility access may be disrupted",
    "Severe": "Major flooding expected — evacuate low-lying health facilities",
    "Extreme": "Catastrophic flooding imminent — full emergency response required",
}


def predict(
    rainfall_intensity=0.0, rainfall_24h=0.0, elevation=50.0,
    drainage_quality="moderate", proximity_water=2.0, soil_saturation=50.0,
) -> FloodRiskResult:
    r_s, r_f = _rainfall_risk(rainfall_intensity, rainfall_24h)
    t_s, t_f = _terrain_risk(elevation)
    d_s = DRAINAGE_SCORES.get(drainage_quality.lower().strip(), 0.50)
    d_f = "Poor drainage — water cannot evacuate quickly" if drainage_quality.lower().strip() == "poor" else None
    p_s, p_f = _proximity_risk(proximity_water)
    s_s, s_f = _saturation_risk(soil_saturation)

    composite = 0.30*r_s + 0.20*t_s + 0.20*d_s + 0.15*p_s + 0.15*s_s
    if r_s > 0.5 and d_s > 0.7 and s_s > 0.6:
        composite = min(1.0, composite * 1.25)
    composite = round(float(np.clip(composite, 0, 1)), 4)

    if composite < 0.20: level = "Low"
    elif composite < 0.40: level = "Moderate"
    elif composite < 0.60: level = "High"
    elif composite < 0.80: level = "Severe"
    else: level = "Extreme"

    factors = [f for f in [r_f, t_f, d_f, p_f, s_f] if f]
    if not factors: factors = ["Flood risk factors within normal ranges"]

    return FloodRiskResult(
        risk_score=composite, risk_level=level,
        rainfall_contrib=r_s, terrain_contrib=t_s, drainage_contrib=d_s,
        proximity_contrib=p_s, saturation_contrib=s_s,
        factors=factors, recommendations=RECS.get(level, RECS["Moderate"]),
        estimated_impact=IMPACTS.get(level, IMPACTS["Moderate"]),
    )


# ---------------------------------------------------------------------------
# Trained ML Model Support
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).resolve().parent.parent
_MODEL_DIR = _BASE_DIR / "data" / "trained_models"
_MODEL_PATH = _MODEL_DIR / "flood_model.joblib"
_CONFIG_PATH = _MODEL_DIR / "feature_config.json"

_trained_model = None
_feature_config = None


def initialize():
    """Load the trained flood model at startup."""
    global _trained_model, _feature_config
    if not JOBLIB_AVAILABLE or not _MODEL_PATH.exists():
        print("[CHEWS] Flood ML model not found — using rule-based only.")
        return False

    _trained_model = joblib.load(_MODEL_PATH)
    with open(_CONFIG_PATH) as f:
        _feature_config = json.load(f)
    print(f"[CHEWS] Flood ML model loaded — {type(_trained_model).__name__}")
    return True


def predict_ml(
    rainfall_mm_24h: float = 0.0,
    temperature_c: float = 28.0,
    humidity_percent: float = 70.0,
    elevation_m: float = 50.0,
    water_level_m: float = 1.0,
    drainage_quality: str = "moderate",
    soil_saturation: float = 0.5,
    community_reports: int = 10,
) -> dict | None:
    """
    Predict flood risk using the trained ML model.
    Returns None if the trained model is not available.
    """
    if _trained_model is None:
        return None

    drainage_map = {"poor": 0, "moderate": 1, "good": 2}
    drainage_encoded = drainage_map.get(drainage_quality.lower().strip(), 1)

    # Interaction features (must match training)
    rain_x_saturation = rainfall_mm_24h * soil_saturation
    rain_x_drainage = rainfall_mm_24h * (2 - drainage_encoded)
    low_elevation_flag = 1 if elevation_m < 50 else 0

    features = np.array([[
        rainfall_mm_24h, temperature_c, humidity_percent,
        elevation_m, water_level_m, drainage_encoded,
        soil_saturation, community_reports,
        rain_x_saturation, rain_x_drainage, low_elevation_flag
    ]])

    prediction = int(_trained_model.predict(features)[0])
    probability = float(_trained_model.predict_proba(features)[0][1])

    return {
        "flood_predicted": bool(prediction),
        "flood_probability": round(probability, 4),
        "model_type": "trained_ml",
    }


"""
Malaria Case Predictor
=======================
Loads the trained GradientBoostingRegressor to predict malaria case counts
from climate, environmental, and demographic features.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import numpy as np
import joblib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "data" / "trained_models"
MODEL_PATH = MODEL_DIR / "malaria_model.joblib"
ENCODERS_PATH = MODEL_DIR / "label_encoders.joblib"
CONFIG_PATH = MODEL_DIR / "feature_config.json"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class MalariaPrediction(NamedTuple):
    """Output of the malaria case predictor."""
    predicted_cases: int
    risk_level: str
    confidence_factors: list[str]
    feature_contributions: dict


# Known districts from training data
DISTRICTS = [
    "Bo", "Bombali", "Bonthe", "Kambia", "Kenema",
    "Kono", "Port Loko", "Tonkolili", "Western Rural", "Western Urban"
]

# Risk thresholds for malaria case counts
CASE_THRESHOLDS = {
    "low": 15,
    "moderate": 30,
    "high": 45,
}

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
_model = None
_encoders = None
_feature_config = None


def _load_model():
    """Load the trained model and encoders from disk."""
    global _model, _encoders, _feature_config

    if not MODEL_PATH.exists():
        print(f"[CHEWS] Malaria model not found at {MODEL_PATH}. Run training first.")
        return False

    _model = joblib.load(MODEL_PATH)
    _encoders = joblib.load(ENCODERS_PATH)
    with open(CONFIG_PATH) as f:
        _feature_config = json.load(f)

    print(f"[CHEWS] Malaria predictor loaded — {type(_model).__name__}")
    return True


def initialize():
    """Initialize the malaria predictor at startup."""
    return _load_model()


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def predict(
    district: str,
    rainfall_mm: float,
    temperature_c: float,
    humidity_percent: float,
    water_stagnation_index: float = 0.5,
    mosquito_breeding_sites: int = 10,
    reported_fever_cases: int = 0,
    population_density: int = 5000,
) -> MalariaPrediction:
    """
    Predict malaria case count for a district.

    Parameters
    ----------
    district : str
        Sierra Leone district name
    rainfall_mm : float
        Rainfall in mm
    temperature_c : float
        Temperature in °C
    humidity_percent : float
        Relative humidity %
    water_stagnation_index : float
        Water stagnation index (0-1)
    mosquito_breeding_sites : int
        Number of known breeding sites
    reported_fever_cases : int
        Recently reported fever cases
    population_density : int
        Population density of the area
    """
    if _model is None:
        if not _load_model():
            # Fallback: rule-based estimate
            return _fallback_predict(
                rainfall_mm, temperature_c, humidity_percent,
                water_stagnation_index, mosquito_breeding_sites
            )

    # Encode district
    le = _encoders.get("malaria_district")
    if le is not None and district in le.classes_:
        district_encoded = le.transform([district])[0]
    else:
        district_encoded = 0  # default

    # Build feature vector (must match training order)
    rain_x_stagnation = rainfall_mm * water_stagnation_index
    temp_humidity_index = temperature_c * humidity_percent / 100
    breeding_density = mosquito_breeding_sites * water_stagnation_index

    features = np.array([[
        rainfall_mm, temperature_c, humidity_percent,
        water_stagnation_index, mosquito_breeding_sites,
        reported_fever_cases, population_density, district_encoded,
        rain_x_stagnation, temp_humidity_index, breeding_density
    ]])

    # Predict
    predicted = max(0, round(float(_model.predict(features)[0])))

    # Classify risk
    if predicted < CASE_THRESHOLDS["low"]:
        risk_level = "Low"
    elif predicted < CASE_THRESHOLDS["moderate"]:
        risk_level = "Moderate"
    elif predicted < CASE_THRESHOLDS["high"]:
        risk_level = "High"
    else:
        risk_level = "Critical"

    # Generate factors
    factors = []
    if rainfall_mm > 150:
        factors.append(f"High rainfall ({rainfall_mm:.0f}mm) increases breeding sites")
    if humidity_percent > 75:
        factors.append(f"Humidity at {humidity_percent:.0f}% supports mosquito survival")
    if water_stagnation_index > 0.6:
        factors.append(f"High water stagnation ({water_stagnation_index:.2f}) favours larval development")
    if mosquito_breeding_sites > 20:
        factors.append(f"{mosquito_breeding_sites} known breeding sites in area")
    if not factors:
        factors = ["Environmental conditions within normal ranges"]

    # Feature contributions (from model importances)
    feature_names = _feature_config.get("malaria", [])
    importances = _model.feature_importances_
    contributions = {}
    for name, imp in zip(feature_names, importances):
        contributions[name] = round(float(imp), 4)

    return MalariaPrediction(
        predicted_cases=predicted,
        risk_level=risk_level,
        confidence_factors=factors,
        feature_contributions=contributions,
    )


def _fallback_predict(rainfall, temp, humidity, stagnation, breeding_sites):
    """Rule-based fallback when trained model is unavailable."""
    base = 15
    if rainfall > 150:
        base += 10
    if temp > 25 and temp < 33:
        base += 8
    if humidity > 70:
        base += 5
    if stagnation > 0.5:
        base += 7
    base += breeding_sites * 0.3

    predicted = max(0, round(base))
    risk_level = "Low" if predicted < 15 else "Moderate" if predicted < 30 else "High"

    return MalariaPrediction(
        predicted_cases=predicted,
        risk_level=risk_level,
        confidence_factors=["Using rule-based fallback (trained model not available)"],
        feature_contributions={},
    )

"""
Healthcare Readiness Predictor
================================
Loads the trained RandomForestRegressor to predict healthcare facility
readiness scores from infrastructure and resource data.
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
MODEL_PATH = MODEL_DIR / "healthcare_model.joblib"
ENCODERS_PATH = MODEL_DIR / "label_encoders.joblib"
CONFIG_PATH = MODEL_DIR / "feature_config.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class ReadinessResult(NamedTuple):
    """Output of the healthcare readiness predictor."""
    readiness_score: float
    readiness_level: str
    capacity_assessment: str
    key_gaps: list[str]
    feature_contributions: dict


FACILITY_TYPES = ["CHC", "MCHP", "Primary", "Secondary", "Tertiary"]

DISTRICTS = [
    "Bo", "Bombali", "Bonthe", "Kambia", "Kenema",
    "Kono", "Port Loko", "Tonkolili", "Western Rural", "Western Urban"
]

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
        print(f"[CHEWS] Healthcare model not found at {MODEL_PATH}. Run training first.")
        return False

    _model = joblib.load(MODEL_PATH)
    _encoders = joblib.load(ENCODERS_PATH)
    with open(CONFIG_PATH) as f:
        _feature_config = json.load(f)

    print(f"[CHEWS] Healthcare readiness predictor loaded — {type(_model).__name__}")
    return True


def initialize():
    """Initialize the healthcare readiness predictor at startup."""
    return _load_model()


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def predict(
    district: str,
    facility_type: str,
    beds_available: int,
    health_workers: int,
    malaria_medicine_stock: float,
    power_availability: int,
    water_availability: int,
    patient_load: int,
) -> ReadinessResult:
    """
    Predict healthcare facility readiness score.

    Parameters
    ----------
    district : str
        Sierra Leone district name
    facility_type : str
        One of: CHC, MCHP, Primary, Secondary, Tertiary
    beds_available : int
        Number of beds available
    health_workers : int
        Number of health workers
    malaria_medicine_stock : float
        Medicine stock level (0-1)
    power_availability : int
        Power available (0 or 1)
    water_availability : int
        Water available (0 or 1)
    patient_load : int
        Current patient load
    """
    if _model is None:
        if not _load_model():
            return _fallback_predict(
                beds_available, health_workers, malaria_medicine_stock,
                power_availability, water_availability, patient_load
            )

    # Encode categorical features
    le_district = _encoders.get("healthcare_district")
    le_facility = _encoders.get("healthcare_facility_type")

    district_encoded = 0
    if le_district is not None and district in le_district.classes_:
        district_encoded = le_district.transform([district])[0]

    facility_encoded = 0
    if le_facility is not None and facility_type in le_facility.classes_:
        facility_encoded = le_facility.transform([facility_type])[0]

    # Engineered features (must match training)
    resource_ratio = health_workers / (patient_load + 1)
    infrastructure_score = power_availability + water_availability
    capacity_utilization = patient_load / (beds_available + 1)

    features = np.array([[
        beds_available, health_workers, malaria_medicine_stock,
        power_availability, water_availability, patient_load,
        district_encoded, facility_encoded,
        resource_ratio, infrastructure_score, capacity_utilization
    ]])

    # Predict
    score = float(np.clip(_model.predict(features)[0], 0, 1))
    score = round(score, 4)

    # Classify readiness
    if score >= 0.7:
        level = "Ready"
        assessment = "Facility is well-prepared for disease response"
    elif score >= 0.5:
        level = "Partially Ready"
        assessment = "Facility has moderate capacity but gaps exist"
    elif score >= 0.3:
        level = "Under-prepared"
        assessment = "Significant gaps in facility readiness"
    else:
        level = "Critical"
        assessment = "Facility lacks essential resources for response"

    # Identify gaps
    gaps = []
    if malaria_medicine_stock < 0.3:
        gaps.append(f"Low malaria medicine stock ({malaria_medicine_stock:.0%})")
    if power_availability == 0:
        gaps.append("No power supply available")
    if water_availability == 0:
        gaps.append("No water supply available")
    if resource_ratio < 0.5:
        gaps.append(f"Low health worker to patient ratio ({resource_ratio:.2f})")
    if capacity_utilization > 2.0:
        gaps.append(f"Facility overloaded (utilization: {capacity_utilization:.1f}x)")
    if not gaps:
        gaps = ["No critical gaps identified"]

    # Feature contributions
    feature_names = _feature_config.get("healthcare", [])
    importances = _model.feature_importances_
    contributions = {}
    for name, imp in zip(feature_names, importances):
        contributions[name] = round(float(imp), 4)

    return ReadinessResult(
        readiness_score=score,
        readiness_level=level,
        capacity_assessment=assessment,
        key_gaps=gaps,
        feature_contributions=contributions,
    )


def _fallback_predict(beds, workers, medicine, power, water, load):
    """Rule-based fallback."""
    score = 0.3
    score += min(0.2, beds / 500)
    score += min(0.15, workers / 200)
    score += medicine * 0.15
    score += power * 0.1
    score += water * 0.1
    score = round(float(np.clip(score, 0, 1)), 4)

    level = "Ready" if score >= 0.7 else "Partially Ready" if score >= 0.5 else "Under-prepared"

    return ReadinessResult(
        readiness_score=score,
        readiness_level=level,
        capacity_assessment="Using rule-based fallback",
        key_gaps=["Trained model not available"],
        feature_contributions={},
    )

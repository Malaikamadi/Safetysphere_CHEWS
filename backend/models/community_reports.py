"""
Community Flood Reports Classifier
=====================================
Loads the trained RandomForestClassifier to predict flood occurrence
from community-level report data.
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
MODEL_PATH = MODEL_DIR / "community_model.joblib"
ENCODERS_PATH = MODEL_DIR / "label_encoders.joblib"
CONFIG_PATH = MODEL_DIR / "feature_config.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class CommunityFloodResult(NamedTuple):
    """Output of the community flood classifier."""
    flood_predicted: bool
    flood_probability: float
    alert_level: str
    contributing_factors: list[str]
    feature_contributions: dict


DISTRICTS = [
    "Bo", "Bombali", "Bonthe", "Kambia", "Kenema",
    "Kono", "Port Loko", "Tonkolili", "Western Rural", "Western Urban"
]

COMMUNITIES = [
    "Aberdeen", "Calaba", "Cline Town", "Dworzark", "Kissy",
    "Kroo Bay", "Mambolo", "Moyamba Junction", "Regent",
    "Susan's Bay", "Tikonko", "Waterloo"
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
        print(f"[CHEWS] Community model not found at {MODEL_PATH}. Run training first.")
        return False

    _model = joblib.load(MODEL_PATH)
    _encoders = joblib.load(ENCODERS_PATH)
    with open(CONFIG_PATH) as f:
        _feature_config = json.load(f)

    print(f"[CHEWS] Community flood classifier loaded — {type(_model).__name__}")
    return True


def initialize():
    """Initialize the community flood classifier at startup."""
    return _load_model()


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def predict(
    district: str,
    community: str,
    standing_water: int,
    fever_reports: int,
    damaged_houses: int,
    displaced_households: int,
    water_contamination: int,
) -> CommunityFloodResult:
    """
    Predict flood occurrence from community report data.

    Parameters
    ----------
    district : str
        Sierra Leone district name
    community : str
        Community name
    standing_water : int
        Standing water observed (0 or 1)
    fever_reports : int
        Number of fever reports
    damaged_houses : int
        Number of damaged houses
    displaced_households : int
        Number of displaced households
    water_contamination : int
        Water contamination observed (0 or 1)
    """
    if _model is None:
        if not _load_model():
            return _fallback_predict(
                standing_water, damaged_houses, displaced_households
            )

    # Encode categoricals
    le_district = _encoders.get("community_district")
    le_community = _encoders.get("community_community")

    district_encoded = 0
    if le_district is not None and district in le_district.classes_:
        district_encoded = le_district.transform([district])[0]

    community_encoded = 0
    if le_community is not None and community in le_community.classes_:
        community_encoded = le_community.transform([community])[0]

    # Engineered features (must match training)
    damage_displacement_index = damaged_houses * displaced_households
    total_impact = damaged_houses + displaced_households + water_contamination

    features = np.array([[
        standing_water, fever_reports, damaged_houses,
        displaced_households, water_contamination,
        district_encoded, community_encoded,
        damage_displacement_index, total_impact
    ]])

    # Predict
    prediction = int(_model.predict(features)[0])
    probability = float(_model.predict_proba(features)[0][1])

    # Alert level
    if probability >= 0.8:
        alert_level = "Critical"
    elif probability >= 0.5:
        alert_level = "Warning"
    elif probability >= 0.3:
        alert_level = "Watch"
    else:
        alert_level = "Normal"

    # Contributing factors
    factors = []
    if damaged_houses > 20:
        factors.append(f"{damaged_houses} houses damaged — significant structural impact")
    if displaced_households > 10:
        factors.append(f"{displaced_households} households displaced — humanitarian response needed")
    if standing_water == 1:
        factors.append("Standing water observed — flood conditions present")
    if water_contamination == 1:
        factors.append("Water contamination reported — health risk elevated")
    if fever_reports > 30:
        factors.append(f"{fever_reports} fever cases — potential disease outbreak")
    if not factors:
        factors = ["Community conditions within normal parameters"]

    # Feature contributions
    feature_names = _feature_config.get("community", [])
    importances = _model.feature_importances_
    contributions = {}
    for name, imp in zip(feature_names, importances):
        contributions[name] = round(float(imp), 4)

    return CommunityFloodResult(
        flood_predicted=bool(prediction),
        flood_probability=round(probability, 4),
        alert_level=alert_level,
        contributing_factors=factors,
        feature_contributions=contributions,
    )


def _fallback_predict(standing_water, damaged_houses, displaced):
    """Rule-based fallback."""
    score = 0.1
    if standing_water:
        score += 0.3
    if damaged_houses > 20:
        score += 0.3
    if displaced > 10:
        score += 0.2
    probability = min(1.0, score)

    return CommunityFloodResult(
        flood_predicted=probability >= 0.5,
        flood_probability=round(probability, 4),
        alert_level="Warning" if probability >= 0.5 else "Normal",
        contributing_factors=["Using rule-based fallback (trained model not available)"],
        feature_contributions={},
    )

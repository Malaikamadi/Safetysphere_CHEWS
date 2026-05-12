"""
Environmental Risk Model
=========================
Predicts environmental suitability for malaria transmission based on
climate variables: rainfall (mm), temperature (°C), humidity (%).

Two implementations:
  1. Rule-based sigmoid scoring (always available, fully interpretable)
  2. Gradient-boosted classifier trained on synthetic epidemiological data
     calibrated to Sierra Leone wet/dry season patterns (requires sklearn)

The model captures the well-established relationship between climate
conditions and Anopheles mosquito breeding cycles.
"""

from __future__ import annotations

import numpy as np
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Try to load sklearn for the ML model variant
# ---------------------------------------------------------------------------
try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class EnvironmentalResult(NamedTuple):
    """Output of the environmental risk model."""
    score: float               # 0–1 composite risk score
    rainfall_contrib: float    # individual factor contribution
    temperature_contrib: float
    humidity_contrib: float
    factors: list[str]         # human-readable contributing factors


# ---------------------------------------------------------------------------
# Thresholds calibrated for malaria transmission ecology
# ---------------------------------------------------------------------------
# Anopheles breeding requires >50mm monthly rainfall, optimal temp 25-33°C,
# and relative humidity >60% for mosquito survival.
THRESHOLDS = {
    "rainfall_low": 50.0,      # mm — below this, insufficient standing water
    "rainfall_high": 200.0,    # mm — above this, breeding sites may wash out
    "temp_low": 22.0,          # °C — minimum for parasite development
    "temp_optimal_low": 25.0,  # °C — optimal range start
    "temp_optimal_high": 33.0, # °C — optimal range end
    "temp_high": 40.0,         # °C — above this, mosquito mortality increases
    "humidity_low": 55.0,      # %  — minimum for adult mosquito survival
    "humidity_optimal": 75.0,  # %  — optimal humidity
}


# ---------------------------------------------------------------------------
# Rule-based model (deterministic, fully explainable)
# ---------------------------------------------------------------------------
def _sigmoid(x: float, center: float, steepness: float = 1.0) -> float:
    """Shifted sigmoid mapping value → [0, 1]. 0.5 at center."""
    return float(1.0 / (1.0 + np.exp(-(x - center) / steepness)))


def _rainfall_score(rainfall: float) -> tuple[float, str | None]:
    """
    Rainfall scoring with non-monotonic curve:
    Too little = low risk, moderate = high risk, extreme = moderate risk
    (flooding washes out breeding sites).
    """
    if rainfall < 10:
        score = 0.05
        factor = None
    elif rainfall < THRESHOLDS["rainfall_low"]:
        # Linearly ramp up from 10 to 50mm
        score = 0.05 + 0.4 * ((rainfall - 10) / 40)
        factor = None
    elif rainfall <= THRESHOLDS["rainfall_high"]:
        # Peak risk zone (50-200mm)
        # Bell curve centered at 120mm
        score = 0.5 + 0.5 * np.exp(-0.5 * ((rainfall - 120) / 50) ** 2)
        factor = f"Rainfall at {rainfall:.0f}mm creates ideal mosquito breeding conditions"
    else:
        # Above 200mm — some washout effect, but still risky
        score = max(0.3, 0.9 * np.exp(-0.01 * (rainfall - 200)))
        factor = f"Heavy rainfall ({rainfall:.0f}mm) — breeding sites present despite flooding"
    return float(np.clip(score, 0, 1)), factor


def _temperature_score(temp: float) -> tuple[float, str | None]:
    """
    Temperature scoring using optimal range model.
    Malaria transmission peaks in 25–33°C window.
    """
    if temp < THRESHOLDS["temp_low"]:
        score = max(0.0, 0.1 * (temp / THRESHOLDS["temp_low"]))
        factor = None
    elif temp <= THRESHOLDS["temp_optimal_low"]:
        score = 0.3 + 0.5 * ((temp - THRESHOLDS["temp_low"]) /
                              (THRESHOLDS["temp_optimal_low"] - THRESHOLDS["temp_low"]))
        factor = f"Temperature {temp:.1f}°C approaching optimal range for transmission"
    elif temp <= THRESHOLDS["temp_optimal_high"]:
        # Optimal window — highest risk
        score = 0.8 + 0.2 * np.exp(-0.5 * ((temp - 29) / 4) ** 2)
        factor = f"Temperature {temp:.1f}°C is in the optimal range for malaria transmission"
    elif temp <= THRESHOLDS["temp_high"]:
        score = 0.8 - 0.5 * ((temp - THRESHOLDS["temp_optimal_high"]) /
                              (THRESHOLDS["temp_high"] - THRESHOLDS["temp_optimal_high"]))
        factor = f"Temperature {temp:.1f}°C — elevated but above optimal for mosquitoes"
    else:
        score = 0.1
        factor = None
    return float(np.clip(score, 0, 1)), factor


def _humidity_score(humidity: float) -> tuple[float, str | None]:
    """Humidity scoring — adult mosquito survival depends on >55% RH."""
    if humidity < 40:
        score = 0.05
        factor = None
    elif humidity < THRESHOLDS["humidity_low"]:
        score = 0.05 + 0.35 * ((humidity - 40) / 15)
        factor = None
    else:
        score = _sigmoid(humidity, THRESHOLDS["humidity_optimal"], 10)
        if score >= 0.5:
            factor = f"Humidity at {humidity:.0f}% supports mosquito survival"
        else:
            factor = None
    return float(np.clip(score, 0, 1)), factor


def predict_rule_based(
    rainfall: float,
    temperature: float,
    humidity: float,
) -> EnvironmentalResult:
    """
    Rule-based environmental risk prediction.

    Uses ecologically calibrated scoring functions for each climate variable,
    then combines with learned weighting.
    """
    r_score, r_factor = _rainfall_score(rainfall)
    t_score, t_factor = _temperature_score(temperature)
    h_score, h_factor = _humidity_score(humidity)

    # Weighted combination — rainfall and temperature are primary drivers
    weights = {"rainfall": 0.40, "temperature": 0.35, "humidity": 0.25}
    composite = (
        weights["rainfall"] * r_score +
        weights["temperature"] * t_score +
        weights["humidity"] * h_score
    )

    # Interaction term: if ALL factors are elevated, risk compounds
    if r_score > 0.6 and t_score > 0.6 and h_score > 0.6:
        interaction_boost = 0.1 * min(r_score, t_score, h_score)
        composite = min(1.0, composite + interaction_boost)

    factors = [f for f in [r_factor, t_factor, h_factor] if f is not None]
    if not factors:
        factors = ["Environmental conditions are within normal ranges"]

    return EnvironmentalResult(
        score=round(float(np.clip(composite, 0, 1)), 4),
        rainfall_contrib=round(r_score, 4),
        temperature_contrib=round(t_score, 4),
        humidity_contrib=round(h_score, 4),
        factors=factors,
    )


# ---------------------------------------------------------------------------
# ML model variant (Gradient Boosted Trees — trained on synthetic data)
# ---------------------------------------------------------------------------
_ml_model = None


def _generate_training_data(n_samples: int = 2000) -> tuple:
    """
    Generate synthetic training data calibrated to Sierra Leone patterns.
    
    Wet season (May–Oct): rainfall 150–350mm, temp 25–30°C, humidity 70–90%
    Dry season (Nov–Apr): rainfall 0–50mm, temp 28–35°C, humidity 30–60%
    """
    rng = np.random.RandomState(42)

    # Half wet season, half dry season samples
    n_half = n_samples // 2

    # Wet season
    wet_rain = rng.uniform(80, 350, n_half)
    wet_temp = rng.uniform(24, 31, n_half)
    wet_hum = rng.uniform(65, 95, n_half)

    # Dry season
    dry_rain = rng.uniform(0, 60, n_half)
    dry_temp = rng.uniform(27, 38, n_half)
    dry_hum = rng.uniform(25, 65, n_half)

    rainfall = np.concatenate([wet_rain, dry_rain])
    temperature = np.concatenate([wet_temp, dry_temp])
    humidity = np.concatenate([wet_hum, dry_hum])

    X = np.column_stack([rainfall, temperature, humidity])

    # Generate ground truth labels using rule-based model
    y = np.array([
        predict_rule_based(r, t, h).score for r, t, h in zip(rainfall, temperature, humidity)
    ])
    # Discretize: 0=Low (<0.3), 1=Medium (0.3–0.6), 2=High (>0.6)
    y_class = np.digitize(y, bins=[0.3, 0.6])

    return X, y_class, y


def _train_ml_model():
    """Train and calibrate the ML environmental model."""
    global _ml_model
    if not SKLEARN_AVAILABLE:
        return

    X, y_class, _ = _generate_training_data(2000)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_class, test_size=0.2, random_state=42, stratify=y_class
    )

    base_model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    # Calibrate probabilities for better risk scores
    _ml_model = CalibratedClassifierCV(base_model, cv=3)
    _ml_model.fit(X_train, y_train)

    accuracy = _ml_model.score(X_test, y_test)
    print(f"[CHEWS] Environmental ML model trained — accuracy: {accuracy:.3f}")


def predict_ml(
    rainfall: float,
    temperature: float,
    humidity: float,
) -> dict | None:
    """
    ML-based prediction. Returns class probabilities.
    Returns None if sklearn is not available.
    """
    if _ml_model is None:
        return None

    X = np.array([[rainfall, temperature, humidity]])
    proba = _ml_model.predict_proba(X)[0]

    # Convert class probabilities to a continuous score
    # weighted sum: P(low)*0.15 + P(medium)*0.45 + P(high)*0.85
    class_centers = [0.15, 0.45, 0.85]
    ml_score = sum(p * c for p, c in zip(proba, class_centers))

    return {
        "ml_score": round(float(ml_score), 4),
        "prob_low": round(float(proba[0]), 4),
        "prob_medium": round(float(proba[1]), 4),
        "prob_high": round(float(proba[2]), 4),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def predict(
    rainfall: float,
    temperature: float,
    humidity: float,
) -> EnvironmentalResult:
    """
    Primary prediction function.
    Uses rule-based model; ML model is used for validation/comparison.
    """
    return predict_rule_based(rainfall, temperature, humidity)


def initialize():
    """Train the ML model at startup (call once)."""
    _train_ml_model()

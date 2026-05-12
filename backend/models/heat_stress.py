"""
Heat Stress Model
==================
Predicts heat-related health risk using Wet Bulb Globe Temperature (WBGT)
and heatwave detection. Calibrated for tropical/sub-tropical settings.
"""

from __future__ import annotations
import numpy as np
from typing import NamedTuple


class HeatStressResult(NamedTuple):
    wbgt: float
    risk_score: float
    risk_level: str
    category: str
    heat_index: float
    is_heatwave: bool
    heatwave_day: int
    factors: list[str]
    recommendations: list[str]


def _approx_wbgt(temp_c, humidity, wind_speed=1.0, solar_rad=500):
    """Approximate WBGT from temperature, humidity, wind, solar radiation."""
    # Wet bulb approximation (Stull 2011)
    tw = temp_c * np.arctan(0.151977 * (humidity + 8.313659)**0.5) + \
         np.arctan(temp_c + humidity) - np.arctan(humidity - 1.676331) + \
         0.00391838 * humidity**1.5 * np.arctan(0.023101 * humidity) - 4.686035
    # Globe temperature approximation
    tg = 1.1 * temp_c + 2.0 * (solar_rad / 1000) - 0.5 * wind_speed
    wbgt = 0.7 * tw + 0.2 * tg + 0.1 * temp_c
    return round(float(wbgt), 1)


def _heat_index(temp_c, humidity):
    """Simplified heat index (feels-like temperature)."""
    t = temp_c * 9/5 + 32  # Convert to F
    if t < 80: return round(temp_c, 1)
    hi = (-42.379 + 2.04901523*t + 10.14333127*humidity
          - 0.22475541*t*humidity - 6.83783e-3*t**2
          - 5.481717e-2*humidity**2 + 1.22874e-3*t**2*humidity
          + 8.5282e-4*t*humidity**2 - 1.99e-6*t**2*humidity**2)
    return round((hi - 32) * 5/9, 1)


WBGT_CATEGORIES = [
    (25, "Safe", 0.10),
    (28, "Caution", 0.30),
    (30, "Warning", 0.55),
    (32, "Danger", 0.75),
    (35, "Extreme Danger", 0.95),
]

RECS = {
    "Safe": ["Normal activities can continue", "Ensure adequate hydration"],
    "Caution": ["Increase water intake", "Schedule rest breaks for outdoor workers", "Monitor vulnerable individuals"],
    "Warning": ["Reduce outdoor activities during peak heat (10am–4pm)", "Activate cooling centers", "Alert health facilities for heat-related cases"],
    "Danger": ["Cancel strenuous outdoor activities", "Activate emergency heat response", "Door-to-door checks on elderly and chronically ill", "Distribute oral rehydration salts to communities"],
    "Extreme Danger": ["EMERGENCY: Cease all outdoor activity", "Open all emergency cooling shelters", "Health facilities on maximum alert for heat stroke", "Mobilize emergency medical teams"],
}


def predict(
    temperature=30.0, humidity=60.0, wind_speed=1.0, solar_radiation=500,
    consecutive_hot_days=0, temp_threshold=35.0,
) -> HeatStressResult:
    wbgt = _approx_wbgt(temperature, humidity, wind_speed, solar_radiation)
    hi = _heat_index(temperature, humidity)
    is_heatwave = consecutive_hot_days >= 3 and temperature >= temp_threshold

    category, risk_score = "Extreme Danger", 0.95
    for threshold, cat, score in WBGT_CATEGORIES:
        if wbgt <= threshold:
            category, risk_score = cat, score
            break

    if is_heatwave:
        risk_score = min(1.0, risk_score * 1.3)

    if risk_score < 0.25: level = "Low"
    elif risk_score < 0.50: level = "Moderate"
    elif risk_score < 0.70: level = "High"
    elif risk_score < 0.85: level = "Very High"
    else: level = "Extreme"

    factors = []
    if wbgt >= 30: factors.append(f"WBGT at {wbgt}°C — heat stress conditions")
    if hi >= 40: factors.append(f"Heat index at {hi}°C — significant perceived heat")
    if is_heatwave: factors.append(f"Heatwave: {consecutive_hot_days} consecutive days above {temp_threshold}°C")
    if humidity >= 80 and temperature >= 30: factors.append(f"High humidity ({humidity}%) compounds heat risk")
    if not factors: factors = ["Heat conditions within safe ranges"]

    return HeatStressResult(
        wbgt=wbgt, risk_score=round(risk_score, 4), risk_level=level,
        category=category, heat_index=hi, is_heatwave=is_heatwave,
        heatwave_day=consecutive_hot_days, factors=factors,
        recommendations=RECS.get(category, RECS["Caution"]),
    )

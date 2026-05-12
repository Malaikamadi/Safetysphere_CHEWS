"""
Air Quality Model
==================
Predicts air quality health risk from pollutant concentrations.

Supports:
    PM2.5, PM10, O3, NO2, SO2 → composite AQI + health impact score.

Based on EPA AQI breakpoints adapted for child health sensitivity
(children and pregnant women are more susceptible to air pollution).

Use cases:
    - Pollution hotspot identification (Area 1)
    - Air quality early warnings (Area 2)
    - Respiratory surge forecasting (Area 3)
    - Linking pollution exposure to child health outcomes
"""

from __future__ import annotations

import numpy as np
from typing import NamedTuple


class AirQualityResult(NamedTuple):
    """Output of the air quality risk model."""
    aqi: int                      # 0–500 Air Quality Index
    health_risk: float            # 0–1 health risk score
    category: str                 # Good / Moderate / Unhealthy for Sensitive / Unhealthy / Very Unhealthy / Hazardous
    dominant_pollutant: str       # which pollutant drives the AQI
    pollutant_scores: dict        # individual pollutant AQI values
    child_risk_multiplier: float  # elevated risk for children
    factors: list[str]            # human-readable factor explanations
    recommendations: list[str]    # actionable recommendations


# ---------------------------------------------------------------------------
# EPA AQI breakpoints (simplified)
# Each tuple: (C_low, C_high, I_low, I_high)
# ---------------------------------------------------------------------------
AQI_BREAKPOINTS = {
    "pm25": [
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 500.4, 301, 500),
    ],
    "pm10": [
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 604, 301, 500),
    ],
    "o3": [
        (0, 54, 0, 50),
        (55, 70, 51, 100),
        (71, 85, 101, 150),
        (86, 105, 151, 200),
        (106, 200, 201, 300),
        (201, 504, 301, 500),
    ],
    "no2": [
        (0, 53, 0, 50),
        (54, 100, 51, 100),
        (101, 360, 101, 150),
        (361, 649, 151, 200),
        (650, 1249, 201, 300),
        (1250, 2049, 301, 500),
    ],
    "so2": [
        (0, 35, 0, 50),
        (36, 75, 51, 100),
        (76, 185, 101, 150),
        (186, 304, 151, 200),
        (305, 604, 201, 300),
        (605, 1004, 301, 500),
    ],
}

AQI_CATEGORIES = [
    (50, "Good", "#22c55e"),
    (100, "Moderate", "#fbbf24"),
    (150, "Unhealthy for Sensitive Groups", "#f97316"),
    (200, "Unhealthy", "#ef4444"),
    (300, "Very Unhealthy", "#a855f7"),
    (500, "Hazardous", "#7f1d1d"),
]

POLLUTANT_NAMES = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "Ozone (O₃)",
    "no2": "Nitrogen Dioxide (NO₂)",
    "so2": "Sulfur Dioxide (SO₂)",
}


def _calc_aqi(concentration: float, breakpoints: list[tuple]) -> int:
    """Calculate AQI for a single pollutant using EPA linear interpolation."""
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= concentration <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (concentration - c_low) + i_low
            return int(round(aqi))
    # Above highest breakpoint
    return 500


def _get_category(aqi: int) -> str:
    """Map AQI to health category."""
    for threshold, category, _ in AQI_CATEGORIES:
        if aqi <= threshold:
            return category
    return "Hazardous"


def predict(
    pm25: float = 0.0,
    pm10: float = 0.0,
    o3: float = 0.0,
    no2: float = 0.0,
    so2: float = 0.0,
    has_children: bool = True,
    has_respiratory_conditions: bool = False,
) -> AirQualityResult:
    """
    Predict air quality health risk from pollutant concentrations.

    Parameters
    ----------
    pm25 : float — PM2.5 in μg/m³ (24-hour average)
    pm10 : float — PM10 in μg/m³ (24-hour average)
    o3 : float — Ozone in ppb (8-hour average)
    no2 : float — NO2 in ppb (1-hour average)
    so2 : float — SO2 in ppb (1-hour average)
    has_children : bool — whether children are present
    has_respiratory_conditions : bool — pre-existing respiratory conditions

    Returns
    -------
    AirQualityResult with AQI, health risk, category, and recommendations.
    """
    concentrations = {
        "pm25": max(0, pm25),
        "pm10": max(0, pm10),
        "o3": max(0, o3),
        "no2": max(0, no2),
        "so2": max(0, so2),
    }

    # Calculate individual AQIs
    pollutant_aqis = {}
    for pollutant, conc in concentrations.items():
        if conc > 0:
            pollutant_aqis[pollutant] = _calc_aqi(conc, AQI_BREAKPOINTS[pollutant])
        else:
            pollutant_aqis[pollutant] = 0

    # Overall AQI is the maximum of individual pollutant AQIs
    if pollutant_aqis:
        overall_aqi = max(pollutant_aqis.values())
        dominant = max(pollutant_aqis, key=pollutant_aqis.get)
    else:
        overall_aqi = 0
        dominant = "pm25"

    category = _get_category(overall_aqi)

    # Health risk score (0–1)
    health_risk = min(1.0, overall_aqi / 300.0)

    # Child risk multiplier (children breathe more air per kg body weight)
    child_multiplier = 1.0
    if has_children:
        child_multiplier = 1.5
    if has_respiratory_conditions:
        child_multiplier *= 1.3

    adjusted_risk = min(1.0, health_risk * child_multiplier)

    # Generate factors
    factors = []
    if overall_aqi > 150:
        factors.append(f"AQI at {overall_aqi} — {category} level, driven by {POLLUTANT_NAMES.get(dominant, dominant)}")
    elif overall_aqi > 100:
        factors.append(f"AQI at {overall_aqi} — unhealthy for sensitive groups including children")
    elif overall_aqi > 50:
        factors.append(f"AQI at {overall_aqi} — moderate air quality, some pollutants present")

    if pm25 > 35:
        factors.append(f"PM2.5 at {pm25:.1f} μg/m³ — exceeds WHO guideline (15 μg/m³)")
    if pm10 > 45:
        factors.append(f"PM10 at {pm10:.1f} μg/m³ — exceeds WHO guideline (45 μg/m³)")
    if has_children and overall_aqi > 50:
        factors.append("Children present — elevated respiratory vulnerability")
    if has_respiratory_conditions:
        factors.append("Pre-existing respiratory conditions increase health impact")

    if not factors:
        factors = ["Air quality is within acceptable ranges"]

    # Generate recommendations
    recommendations = _get_recommendations(overall_aqi, has_children, has_respiratory_conditions)

    return AirQualityResult(
        aqi=overall_aqi,
        health_risk=round(adjusted_risk, 4),
        category=category,
        dominant_pollutant=POLLUTANT_NAMES.get(dominant, dominant),
        pollutant_scores={POLLUTANT_NAMES.get(k, k): v for k, v in pollutant_aqis.items()},
        child_risk_multiplier=round(child_multiplier, 2),
        factors=factors,
        recommendations=recommendations,
    )


def _get_recommendations(aqi: int, has_children: bool, has_respiratory: bool) -> list[str]:
    """Generate actionable recommendations based on AQI level."""
    if aqi <= 50:
        recs = ["Air quality is satisfactory — normal outdoor activities are safe"]
    elif aqi <= 100:
        recs = [
            "Unusually sensitive individuals should consider limiting prolonged outdoor exertion",
            "Monitor air quality trends for potential deterioration",
        ]
    elif aqi <= 150:
        recs = [
            "Sensitive groups (children, elderly, respiratory conditions) should reduce prolonged outdoor exertion",
            "Consider moving outdoor school activities indoors",
            "Close windows in health facilities and schools during peak pollution hours",
        ]
    elif aqi <= 200:
        recs = [
            "Everyone should reduce prolonged outdoor exertion",
            "Move all school activities indoors immediately",
            "Health facilities should activate respiratory surge protocols",
            "Distribute masks to community health workers",
        ]
    elif aqi <= 300:
        recs = [
            "Health warning: entire population at risk",
            "Cancel all outdoor activities for children",
            "Activate emergency ventilation in health facilities",
            "Issue public health advisory through all channels",
            "Deploy air purifiers to schools and clinics if available",
        ]
    else:
        recs = [
            "HAZARDOUS — health emergency conditions",
            "Evacuate outdoor workers, close schools",
            "All health facilities on emergency footing",
            "Coordinate with district emergency management",
            "Request national-level support for affected areas",
        ]

    if has_children and aqi > 100:
        recs.append("Priority: protect children under 5 — they breathe 50% more air per kg body weight")
    if has_respiratory and aqi > 50:
        recs.append("Ensure rescue inhalers are available for individuals with asthma/COPD")

    return recs

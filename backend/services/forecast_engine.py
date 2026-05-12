"""
Forecast Engine Service
========================
Predictive analytics for disease onset, surge forecasting, and seasonal anomaly detection.
Implements 'Forecast-in-a-Box' concept — lightweight, rule-based forecasting
that works without historical time-series databases.
"""

from __future__ import annotations
import numpy as np
from typing import NamedTuple


class ForecastResult(NamedTuple):
    disease: str
    forecast_period: str
    risk_trend: str             # Rising / Stable / Declining
    predicted_risk_level: str   # Low / Moderate / High / Very High
    onset_likelihood: float     # 0–1 probability of season onset
    surge_probability: float    # 0–1 probability of case surge
    peak_window: str            # expected peak period
    confidence: float           # model confidence 0–1
    factors: list[str]
    recommendations: list[str]


# Seasonal calibration for Sierra Leone
SEASONS = {
    "malaria": {
        "peak_months": [7, 8, 9, 10],        # Jul–Oct (wet season)
        "onset_months": [5, 6],                # May–Jun (early rains)
        "decline_months": [11, 12, 1],         # Nov–Jan (dry season)
        "rainfall_threshold": 80,              # mm/month to trigger transmission
        "temp_range": (25, 33),                # optimal temp range
    },
    "dengue": {
        "peak_months": [6, 7, 8, 9],
        "onset_months": [4, 5],
        "decline_months": [11, 12, 1, 2],
        "rainfall_threshold": 60,
        "temp_range": (26, 35),
    },
    "cholera": {
        "peak_months": [7, 8, 9],             # peak during flooding
        "onset_months": [6, 7],
        "decline_months": [10, 11, 12],
        "rainfall_threshold": 150,
        "temp_range": (25, 37),
    },
    "respiratory": {
        "peak_months": [12, 1, 2, 3],         # dry/dusty season
        "onset_months": [11, 12],
        "decline_months": [4, 5, 6],
        "rainfall_threshold": 0,               # inversely related
        "temp_range": (20, 40),
    },
}


def forecast_disease(
    disease: str = "malaria",
    current_month: int = 1,
    rainfall: float = 100.0,
    temperature: float = 28.0,
    humidity: float = 70.0,
    current_cases: int = 10,
    previous_cases: int = 8,
    aqi: int = 50,
) -> ForecastResult:
    """Generate disease forecast using seasonal-climatological model."""
    config = SEASONS.get(disease, SEASONS["malaria"])

    # Seasonal position
    in_peak = current_month in config["peak_months"]
    in_onset = current_month in config["onset_months"]
    in_decline = current_month in config["decline_months"]

    # Base seasonality score
    if in_peak: season_score = 0.85
    elif in_onset: season_score = 0.60
    elif in_decline: season_score = 0.20
    else: season_score = 0.40

    # Climate suitability
    temp_min, temp_max = config["temp_range"]
    if temp_min <= temperature <= temp_max:
        climate_score = 0.7 + 0.3 * (1 - abs(temperature - (temp_min + temp_max)/2) / ((temp_max - temp_min)/2))
    else:
        climate_score = max(0.1, 0.5 - 0.05 * min(abs(temperature - temp_min), abs(temperature - temp_max)))

    # Rainfall suitability
    if disease == "respiratory":
        rain_score = max(0.1, 1.0 - rainfall / 200)
        if aqi > 100: rain_score = min(1.0, rain_score + 0.3)
    else:
        if rainfall >= config["rainfall_threshold"]:
            rain_score = min(1.0, 0.5 + (rainfall - config["rainfall_threshold"]) / 200)
        else:
            rain_score = max(0.1, rainfall / config["rainfall_threshold"] * 0.5)

    # Case trend
    if previous_cases > 0:
        case_ratio = current_cases / previous_cases
    else:
        case_ratio = 1.0 if current_cases == 0 else 2.0

    if case_ratio > 1.2: trend = "Rising"
    elif case_ratio < 0.8: trend = "Declining"
    else: trend = "Stable"

    trend_factor = min(1.5, max(0.5, case_ratio))

    # Composite
    onset_likelihood = min(1.0, season_score * 0.4 + climate_score * 0.3 + rain_score * 0.3)
    surge_prob = min(1.0, onset_likelihood * trend_factor * (1.2 if in_peak else 0.8))

    if surge_prob >= 0.7: pred_level = "Very High"
    elif surge_prob >= 0.5: pred_level = "High"
    elif surge_prob >= 0.3: pred_level = "Moderate"
    else: pred_level = "Low"

    # Peak window
    peak_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                  7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    if config["peak_months"]:
        peak_str = f"{peak_names[config['peak_months'][0]]}–{peak_names[config['peak_months'][-1]]}"
    else:
        peak_str = "Unknown"

    confidence = min(0.95, 0.5 + 0.1 * (1 if in_peak or in_onset else 0) + 0.1 * (1 if rainfall > 50 else 0))

    forecast_period = f"Next 4 weeks (from month {current_month})"

    factors = []
    if in_peak: factors.append(f"Currently in peak {disease} season")
    elif in_onset: factors.append(f"Approaching {disease} season onset")
    if climate_score > 0.6: factors.append(f"Climate conditions favorable for {disease}")
    if rain_score > 0.6: factors.append(f"Rainfall supports {'transmission' if disease != 'respiratory' else 'dust/pollution'}")
    if trend == "Rising": factors.append(f"Cases trending upward (ratio: {case_ratio:.1f}x)")
    if not factors: factors = [f"Conditions do not strongly favor {disease} at this time"]

    recs = _get_forecast_recs(disease, pred_level, in_onset)

    return ForecastResult(
        disease=disease, forecast_period=forecast_period,
        risk_trend=trend, predicted_risk_level=pred_level,
        onset_likelihood=round(onset_likelihood, 4),
        surge_probability=round(surge_prob, 4),
        peak_window=peak_str, confidence=round(confidence, 4),
        factors=factors, recommendations=recs,
    )


def _get_forecast_recs(disease, level, in_onset):
    if level in ("Very High", "High"):
        base = [
            f"Pre-position {disease} diagnostic supplies and treatments",
            "Activate surge staffing plans at health facilities",
            "Intensify community surveillance and reporting",
            "Issue public health advisory",
        ]
    elif level == "Moderate":
        base = [
            f"Monitor {disease} case trends closely",
            "Ensure adequate supply stocks",
            "Brief community health workers on signs and symptoms",
        ]
    else:
        base = [f"Maintain routine {disease} surveillance", "Continue prevention activities"]

    if in_onset:
        base.append(f"Season onset approaching — begin preventive interventions for {disease}")
    return base

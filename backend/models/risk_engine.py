"""
Risk Engine
============
Final risk aggregation layer that combines outputs from the three
sub-models (environmental, epidemiological, exposure) into a unified
risk assessment with full explainability.

Architecture:
    final_risk = (0.4 × environmental) + (0.4 × epidemiological) + (0.2 × exposure)

The engine also:
    - Generates a prioritised list of contributing factors
    - Produces a natural-language explanation
    - Maps the composite score to a risk level (Low / Medium / High)
    - Provides actionable recommendations by risk tier
"""

from __future__ import annotations

from typing import NamedTuple
from models import environmental, epidemiological, exposure


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
class RiskAssessment(NamedTuple):
    """Complete risk assessment output."""
    final_risk: float
    risk_level: str
    breakdown: dict
    explanation: str
    factors: list[str]
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Aggregation weights
# ---------------------------------------------------------------------------
WEIGHTS = {
    "environmental":   0.40,
    "epidemiological": 0.40,
    "exposure":        0.20,
}

# Risk level thresholds
RISK_THRESHOLDS = {"low": 0.30, "high": 0.60}


# ---------------------------------------------------------------------------
# Advice by risk level
# ---------------------------------------------------------------------------
RECOMMENDATIONS = {
    "High": [
        "Distribute insecticide-treated nets (ITNs) to all households immediately",
        "Activate community health workers for door-to-door symptom screening",
        "Pre-position rapid diagnostic test (RDT) kits at health facilities",
        "Conduct indoor residual spraying (IRS) in high-burden areas",
        "Issue public health advisory: pregnant women and children under 5 are priority",
        "Coordinate with district health management team for emergency response",
    ],
    "Medium": [
        "Increase community awareness through health education campaigns",
        "Ensure mosquito net usage is maintained nightly",
        "Monitor community fever cases daily — escalate if numbers rise",
        "Clear stagnant water and potential breeding sites",
        "Stock antimalarial medications at peripheral health units",
    ],
    "Low": [
        "Maintain routine prevention practices (nets, hygiene)",
        "Continue community health surveillance",
        "Educate families on early symptom recognition",
        "Ensure health facilities maintain basic antimalarial supplies",
    ],
}


# ---------------------------------------------------------------------------
# Explanation generator
# ---------------------------------------------------------------------------
def _generate_explanation(
    env_result: environmental.EnvironmentalResult,
    epi_result: epidemiological.EpidemiologicalResult,
    exp_result: exposure.ExposureResult,
    final_score: float,
    risk_level: str,
) -> str:
    """
    Generate a natural-language explanation of the risk assessment.
    Prioritises the dominant contributing factors.
    """
    # Identify the dominant driver
    scores = {
        "environmental conditions": env_result.score,
        "disease surveillance data": epi_result.score,
        "population exposure": exp_result.score,
    }
    dominant = max(scores, key=scores.get)
    dominant_score = scores[dominant]

    # Build explanation
    parts = [f"Overall malaria risk is {risk_level.upper()} (score: {final_score:.2f})."]

    # Primary driver
    if dominant_score > 0.5:
        parts.append(f"The primary driver is {dominant} (score: {dominant_score:.2f}).")

    # Add top contributing factors (up to 3)
    all_factors = env_result.factors + epi_result.factors + exp_result.factors
    # Filter out generic/normal-range factors
    significant = [f for f in all_factors if "normal" not in f.lower() and "manageable" not in f.lower()]

    if significant:
        parts.append("Key contributing factors:")
        for f in significant[:3]:
            parts.append(f"  • {f}")
    else:
        parts.append("No individual factor is significantly elevated at this time.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def assess(
    rainfall: float,
    temperature: float,
    humidity: float,
    reported_cases: int,
    trend: str = "stable",
    vulnerable_population: int = 0,
    exposure_level: str = "medium",
) -> RiskAssessment:
    """
    Run the full multi-layer risk assessment pipeline.

    Parameters
    ----------
    rainfall : float            — mm of rainfall
    temperature : float         — temperature in °C
    humidity : float            — relative humidity %
    reported_cases : int        — confirmed/suspected cases
    trend : str                 — "increasing", "stable", "decreasing"
    vulnerable_population : int — count of children <5 + pregnant women
    exposure_level : str        — "low", "medium", or "high"

    Returns
    -------
    RiskAssessment with final score, level, breakdown, explanation,
    factors, and recommendations.
    """
    # --- Layer 1: Environmental Model ---
    env_result = environmental.predict(rainfall, temperature, humidity)

    # --- Layer 2: Epidemiological Model ---
    epi_result = epidemiological.predict(reported_cases, trend)

    # --- Layer 3: Exposure Model ---
    exp_result = exposure.predict(vulnerable_population, exposure_level)

    # --- Final Aggregation ---
    final_score = (
        WEIGHTS["environmental"]   * env_result.score +
        WEIGHTS["epidemiological"] * epi_result.score +
        WEIGHTS["exposure"]        * exp_result.score
    )
    final_score = round(min(1.0, max(0.0, final_score)), 4)

    # --- Risk Classification ---
    if final_score < RISK_THRESHOLDS["low"]:
        risk_level = "Low"
    elif final_score <= RISK_THRESHOLDS["high"]:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # --- Breakdown ---
    breakdown = {
        "environmental": {
            "score": env_result.score,
            "rainfall_contrib": env_result.rainfall_contrib,
            "temperature_contrib": env_result.temperature_contrib,
            "humidity_contrib": env_result.humidity_contrib,
            "weight": WEIGHTS["environmental"],
        },
        "epidemiological": {
            "score": epi_result.score,
            "case_burden": epi_result.case_burden_score,
            "trend_multiplier": epi_result.trend_multiplier,
            "weight": WEIGHTS["epidemiological"],
        },
        "exposure": {
            "score": exp_result.score,
            "vulnerability": exp_result.vulnerability_score,
            "exposure_level": exp_result.exposure_level_score,
            "weight": WEIGHTS["exposure"],
        },
    }

    # --- Explanation ---
    explanation = _generate_explanation(
        env_result, epi_result, exp_result, final_score, risk_level
    )

    # --- Collect all factors ---
    all_factors = env_result.factors + epi_result.factors + exp_result.factors

    # --- Recommendations ---
    recommendations = RECOMMENDATIONS.get(risk_level, RECOMMENDATIONS["Low"])

    return RiskAssessment(
        final_risk=final_score,
        risk_level=risk_level,
        breakdown=breakdown,
        explanation=explanation,
        factors=all_factors,
        recommendations=recommendations,
    )

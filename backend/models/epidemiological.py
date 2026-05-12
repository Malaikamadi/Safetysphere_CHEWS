"""
Epidemiological Model
======================
Predicts disease spread probability from case surveillance data.

Inputs:
    reported_cases — number of confirmed/suspected cases in the reporting period
    trend          — "increasing", "stable", or "decreasing"

The model uses an epidemiological curve approach:
    - Case counts are mapped through a log-sigmoid to capture the
      nonlinear relationship between case burden and transmission risk
    - Trend direction modifies the score via a multiplier that accounts
      for reproductive number (R_t) direction
    - A momentum term rewards/penalises based on how quickly cases are
      rising or falling
"""

from __future__ import annotations

import numpy as np
from typing import NamedTuple


class EpidemiologicalResult(NamedTuple):
    """Output of the epidemiological risk model."""
    score: float               # 0–1 disease spread probability
    case_burden_score: float   # contribution from absolute case count
    trend_multiplier: float    # contribution from trend direction
    factors: list[str]         # human-readable factor explanations


# ---------------------------------------------------------------------------
# Case count thresholds (per reporting period, e.g. weekly for a district)
# ---------------------------------------------------------------------------
CASE_THRESHOLDS = {
    "baseline": 3,       # expected endemic baseline
    "alert": 10,         # alert threshold
    "outbreak": 25,      # outbreak threshold
    "emergency": 50,     # emergency threshold
}

# Trend multipliers — how much trend direction modifies the risk
TREND_MULTIPLIERS = {
    "increasing": 1.30,   # 30% risk amplification
    "stable":     1.00,   # no modification
    "decreasing": 0.75,   # 25% risk reduction
}


def _case_burden_score(reported_cases: int) -> tuple[float, str | None]:
    """
    Map case count to a 0–1 burden score using a log-sigmoid.
    
    This captures the epidemiological principle that risk grows rapidly
    with initial cases but saturates at high case counts (healthcare
    systems are already overwhelmed).
    """
    if reported_cases <= 0:
        return 0.02, None

    # Log transform for diminishing returns at high counts
    log_cases = np.log1p(reported_cases)
    log_outbreak = np.log1p(CASE_THRESHOLDS["outbreak"])

    # Sigmoid centered at outbreak threshold
    score = float(1.0 / (1.0 + np.exp(-(log_cases - log_outbreak) / 0.6)))

    # Generate explanatory factor
    if reported_cases >= CASE_THRESHOLDS["emergency"]:
        factor = f"Emergency-level case count ({reported_cases} cases) — outbreak response required"
    elif reported_cases >= CASE_THRESHOLDS["outbreak"]:
        factor = f"Outbreak-level case count ({reported_cases} cases) — active transmission"
    elif reported_cases >= CASE_THRESHOLDS["alert"]:
        factor = f"Elevated case count ({reported_cases} cases) — above alert threshold"
    elif reported_cases >= CASE_THRESHOLDS["baseline"]:
        factor = f"Case count ({reported_cases}) near endemic baseline"
    else:
        factor = None

    return round(float(np.clip(score, 0, 1)), 4), factor


def _apply_trend(
    base_score: float,
    trend: str,
) -> tuple[float, float, str | None]:
    """
    Apply trend direction multiplier to the base burden score.
    
    Returns the adjusted score, the multiplier used, and a factor explanation.
    """
    trend_lower = trend.lower().strip()
    multiplier = TREND_MULTIPLIERS.get(trend_lower, 1.0)

    adjusted = base_score * multiplier

    if trend_lower == "increasing":
        factor = "Cases are increasing — suggests rising transmission (R_t > 1)"
    elif trend_lower == "decreasing":
        factor = "Cases are decreasing — transmission may be slowing (R_t < 1)"
    else:
        factor = None

    return round(float(np.clip(adjusted, 0, 1)), 4), multiplier, factor


def predict(
    reported_cases: int,
    trend: str = "stable",
) -> EpidemiologicalResult:
    """
    Predict disease spread probability from case data and trend.

    Parameters
    ----------
    reported_cases : int
        Number of confirmed/suspected cases in the reporting period.
    trend : str
        Direction of case trend: "increasing", "stable", or "decreasing".

    Returns
    -------
    EpidemiologicalResult with score, contributions, and factors.
    """
    # Step 1: Case burden score
    burden_score, burden_factor = _case_burden_score(reported_cases)

    # Step 2: Apply trend modifier
    final_score, multiplier, trend_factor = _apply_trend(burden_score, trend)

    # Collect factors
    factors = [f for f in [burden_factor, trend_factor] if f is not None]
    if not factors:
        factors = ["Case surveillance data within normal endemic levels"]

    return EpidemiologicalResult(
        score=final_score,
        case_burden_score=burden_score,
        trend_multiplier=multiplier,
        factors=factors,
    )

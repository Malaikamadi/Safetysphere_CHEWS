"""
Exposure Model
===============
Assesses population vulnerability and exposure risk.

Inputs:
    vulnerable_population — count or category of high-risk individuals
                            (children under 5, pregnant women)
    exposure_level        — "low", "medium", or "high"
                            (based on housing quality, net usage, proximity
                             to breeding sites)

The model captures the well-documented disparity in malaria outcomes:
    - Children under 5 account for ~80% of malaria deaths in Africa
    - Pregnant women face 3x higher risk of severe disease
    - Exposure factors (housing, nets, proximity) modulate transmission
"""

from __future__ import annotations

import numpy as np
from typing import NamedTuple


class ExposureResult(NamedTuple):
    """Output of the exposure risk model."""
    score: float                    # 0–1 exposure risk score
    vulnerability_score: float      # contribution from vulnerable population
    exposure_level_score: float     # contribution from exposure conditions
    factors: list[str]              # human-readable factor explanations


# ---------------------------------------------------------------------------
# Exposure level mapping
# ---------------------------------------------------------------------------
EXPOSURE_SCORES = {
    "low":    0.20,   # well-protected: nets, screened housing, away from water
    "medium": 0.55,   # partial protection: some nets, near water sources
    "high":   0.90,   # minimal protection: no nets, poor housing, near stagnant water
}

# Vulnerability thresholds (count of vulnerable individuals)
VULNERABILITY_THRESHOLDS = {
    "minimal": 5,      # small group
    "moderate": 15,    # moderate group
    "high": 30,        # large vulnerable population
}


def _vulnerability_score(vulnerable_population: int) -> tuple[float, str | None]:
    """
    Score based on the size of the vulnerable population.
    
    Uses a saturating curve — each additional vulnerable person adds risk,
    but the marginal increase diminishes at high counts.
    """
    if vulnerable_population <= 0:
        return 0.05, None

    # Saturating log-linear score
    score = 1.0 - np.exp(-0.05 * vulnerable_population)

    if vulnerable_population >= VULNERABILITY_THRESHOLDS["high"]:
        factor = (
            f"{vulnerable_population} vulnerable individuals (children <5, pregnant women) "
            f"— high population risk"
        )
    elif vulnerable_population >= VULNERABILITY_THRESHOLDS["moderate"]:
        factor = (
            f"{vulnerable_population} vulnerable individuals identified "
            f"— moderate population risk"
        )
    elif vulnerable_population >= VULNERABILITY_THRESHOLDS["minimal"]:
        factor = (
            f"{vulnerable_population} vulnerable individuals — "
            f"targeted protection recommended"
        )
    else:
        factor = None

    return round(float(np.clip(score, 0, 1)), 4), factor


def _exposure_level_score(exposure_level: str) -> tuple[float, str | None]:
    """Map qualitative exposure level to a numeric score with explanation."""
    level = exposure_level.lower().strip()
    score = EXPOSURE_SCORES.get(level, 0.55)  # default to medium

    if level == "high":
        factor = (
            "High exposure: minimal protection from mosquitoes "
            "(poor housing, no nets, near breeding sites)"
        )
    elif level == "medium":
        factor = (
            "Medium exposure: partial protection available "
            "(some nets, moderate proximity to water)"
        )
    elif level == "low":
        factor = None  # low exposure doesn't generate a warning
    else:
        factor = f"Unknown exposure level '{exposure_level}' — defaulting to medium"

    return score, factor


def predict(
    vulnerable_population: int,
    exposure_level: str = "medium",
) -> ExposureResult:
    """
    Predict exposure risk from vulnerability and environmental exposure data.

    Parameters
    ----------
    vulnerable_population : int
        Count of high-risk individuals (children <5, pregnant women).
    exposure_level : str
        Qualitative exposure level: "low", "medium", or "high".

    Returns
    -------
    ExposureResult with score, contributions, and explanatory factors.
    """
    v_score, v_factor = _vulnerability_score(vulnerable_population)
    e_score, e_factor = _exposure_level_score(exposure_level)

    # Weighted combination — exposure conditions are slightly more important
    # because they're modifiable (intervention target)
    composite = 0.45 * v_score + 0.55 * e_score

    factors = [f for f in [v_factor, e_factor] if f is not None]
    if not factors:
        factors = ["Exposure and vulnerability levels are within manageable ranges"]

    return ExposureResult(
        score=round(float(np.clip(composite, 0, 1)), 4),
        vulnerability_score=round(v_score, 4),
        exposure_level_score=round(e_score, 4),
        factors=factors,
    )

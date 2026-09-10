"""
Operational malaria seasonal-anomaly rules — specification and simulation only.

Does NOT train a model.
Does NOT connect to dashboard, risk engine, or /api/healthcare/forecast/live.
Does NOT treat missing DHIS2 values as zero.
Does NOT use robust z as the operational trigger.
"""

from __future__ import annotations

from typing import Any, Optional

from services.district_names import display_name
from services.malaria_forecast import calendar_prev
from services.malaria_anomaly import COMPLETENESS_MIN, MIN_PRIOR_YEARS_PRIMARY, _float

# Policy-configured magnitude gates, in percentage points. Not fitted.
CANDIDATE_GATES_PP = (2, 3, 5, 10)

# Conventional meteorological grouping for Sierra Leone. Not a malaria discovery.
WET_SEASON_MONTHS = frozenset({5, 6, 7, 8, 9, 10})

# Policy-configured context tolerances. Not fitted.
TESTS_CHANGE_MATERIAL = 0.15
COMPLETENESS_DROP_MATERIAL = 0.15
LOW_TEST_VOLUME_ABS = 1000.0

STATUS_WITHIN_BASELINE = "within_seasonal_baseline"
STATUS_UNUSUAL_POSITIVITY = "unusual_positivity"
STATUS_DATA_QUALITY = "data_quality_issue"
STATUS_INSUFFICIENT_HISTORY = "insufficient_history"
STATUS_NO_OBSERVATION = "no_observation"

QUALITY_REASONS = (
    "missing_observation",
    "tests_not_positive",
    "insufficient_history",
    "low_completeness",
    "reporting_collapse",
    "low_test_volume",
)


def to_percentage_points(abs_dev_median: Optional[float]) -> Optional[float]:
    if abs_dev_median is None:
        return None
    return float(abs_dev_median) * 100.0


def magnitude_flag(abs_dev_median: Optional[float], gate_pp: float) -> bool:
    """True when positivity is at least gate_pp above the past-only seasonal median."""
    if abs_dev_median is None:
        return False
    return float(abs_dev_median) >= (float(gate_pp) / 100.0)


def sierra_leone_season(calendar_month: int) -> str:
    if calendar_month in WET_SEASON_MONTHS:
        return "wet"
    return "dry"


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / previous


def classify_data_quality(
    *,
    observed_positivity: Optional[float],
    tests: Optional[float],
    n_prior: Optional[int],
    completeness: Optional[float],
    prior_completeness: Optional[float],
    prior_tests: Optional[float],
    missing_observation: bool = False,
) -> dict[str, Any]:
    """
    Data-quality gates suppress an operational malaria anomaly.

    Missing tests/confirmed stay missing. They are never filled with 0.
    """
    reasons: list[str] = []
    if missing_observation:
        reasons.append("missing_observation")
    if tests is None or tests <= 0 or observed_positivity is None:
        reasons.append("tests_not_positive")
    if n_prior is None or n_prior < MIN_PRIOR_YEARS_PRIMARY:
        reasons.append("insufficient_history")
    if completeness is None or completeness < COMPLETENESS_MIN:
        reasons.append("low_completeness")
    if (
        completeness is not None
        and prior_completeness is not None
        and (completeness - prior_completeness) <= -COMPLETENESS_DROP_MATERIAL
    ):
        reasons.append("reporting_collapse")
    if tests is not None and tests > 0:
        if tests < LOW_TEST_VOLUME_ABS:
            reasons.append("low_test_volume")
        elif prior_tests is not None and prior_tests > 0 and tests < 0.25 * prior_tests:
            reasons.append("low_test_volume")

    if "missing_observation" in reasons:
        status = STATUS_NO_OBSERVATION
    elif "insufficient_history" in reasons and "tests_not_positive" not in reasons:
        status = STATUS_INSUFFICIENT_HISTORY
    elif reasons:
        status = STATUS_DATA_QUALITY
    else:
        status = None
    return {
        "blocks_malaria_alert": bool(reasons),
        "reasons": reasons,
        "status_if_blocked": status,
    }


def classify_operational_context(
    *,
    abs_dev_median: Optional[float],
    confirmed: Optional[float],
    tests: Optional[float],
    completeness: Optional[float],
    prior_confirmed: Optional[float],
    prior_tests: Optional[float],
    prior_completeness: Optional[float],
) -> dict[str, Any]:
    """
    Contextual flags for a positivity deviation. Not outbreak labels.
    Compared with the prior-year same calendar month when available.
    """
    d_conf = None if confirmed is None or prior_confirmed is None else confirmed - prior_confirmed
    d_tests_pct = _pct_change(tests, prior_tests)
    d_conf_pct = _pct_change(confirmed, prior_confirmed)
    d_comp = None
    if completeness is not None and prior_completeness is not None:
        d_comp = completeness - prior_completeness

    confirmed_increasing = bool(d_conf is not None and d_conf > 0)
    confirmed_decreasing = bool(d_conf is not None and d_conf < 0)
    tests_increasing = bool(d_tests_pct is not None and d_tests_pct >= TESTS_CHANGE_MATERIAL)
    tests_decreasing = bool(d_tests_pct is not None and d_tests_pct <= -TESTS_CHANGE_MATERIAL)
    completeness_deterioration = bool(
        d_comp is not None and d_comp <= -COMPLETENESS_DROP_MATERIAL
    )
    positivity_up = bool(abs_dev_median is not None and abs_dev_median > 0)

    # States requested in the operational review (can co-occur; primary is ordered).
    states = []
    if positivity_up and confirmed_increasing:
        states.append("positivity_anomaly_confirmed_increasing")
    if positivity_up and tests_increasing:
        states.append("positivity_anomaly_tests_increasing")
    if positivity_up and tests_decreasing:
        states.append("positivity_anomaly_tests_decreasing")
    if positivity_up and completeness_deterioration:
        states.append("positivity_anomaly_completeness_deterioration")
    if positivity_up and not confirmed_increasing and not tests_increasing and not tests_decreasing and not completeness_deterioration:
        states.append("positivity_anomaly_without_supporting_evidence")

    primary_state = None
    if completeness_deterioration:
        primary_state = "completeness_deterioration"
    elif tests_decreasing and not confirmed_increasing:
        primary_state = "tests_decreasing"
    elif confirmed_increasing:
        primary_state = "confirmed_increasing"
    elif tests_increasing:
        primary_state = "tests_increasing"
    elif positivity_up:
        primary_state = "without_supporting_evidence"

    return {
        "confirmed_increasing": confirmed_increasing,
        "confirmed_decreasing": confirmed_decreasing,
        "tests_increasing": tests_increasing,
        "tests_decreasing": tests_decreasing,
        "completeness_deterioration": completeness_deterioration,
        "d_confirmed": d_conf,
        "d_confirmed_pct": d_conf_pct,
        "d_tests_pct": d_tests_pct,
        "d_completeness": d_comp,
        "states": states,
        "primary_state": primary_state,
    }


def attach_quality_blocks(
    scored: list[dict],
    panel_index: dict[tuple[str, str], dict],
) -> None:
    """Stamp data-quality blocks on scored rows (gate-independent)."""
    for row in scored:
        period = row["source_period"]
        district = row["district_slug"]
        prior_period = f"{int(period[:4]) - 1}{period[4:6]}"
        prior = panel_index.get((district, prior_period))
        quality = classify_data_quality(
            observed_positivity=row.get("observed"),
            tests=row.get("malaria_tests"),
            n_prior=row.get("n_prior"),
            completeness=row.get("facility_completeness"),
            prior_completeness=None if prior is None else _float(prior.get("facility_completeness")),
            prior_tests=None if prior is None else _float(prior.get("malaria_tests")),
            missing_observation=bool(row.get("missing_observation")),
        )
        row["quality_blocks"] = quality["blocks_malaria_alert"]
        row["quality_reasons"] = quality["reasons"]


def consecutive_anomaly_months(
    score_index: dict[tuple[str, str], dict],
    district: str,
    period: str,
    gate_pp: float,
) -> int:
    """
    Count calendar-consecutive months ending at `period` that pass the magnitude gate
    and are not data-quality blocked. Missing calendar months break the run.
    """
    run = 0
    current = period
    while True:
        row = score_index.get((district, current))
        if row is None:
            break
        blocked = row.get("quality_blocks")
        if blocked is None:
            blocked = not row.get("primary_eligible")
        if blocked:
            break
        if not magnitude_flag(row.get("abs_dev_median"), gate_pp):
            break
        run += 1
        current = calendar_prev(current)
    return run


def operational_status(
    *,
    quality: dict[str, Any],
    abs_dev_median: Optional[float],
    gate_pp: float,
) -> str:
    if quality.get("blocks_malaria_alert"):
        return quality.get("status_if_blocked") or STATUS_DATA_QUALITY
    if magnitude_flag(abs_dev_median, gate_pp):
        return STATUS_UNUSUAL_POSITIVITY
    return STATUS_WITHIN_BASELINE


def format_pp(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.{digits}f}"


def operational_message(
    *,
    district_slug: str,
    positivity: Optional[float],
    seasonal_median: Optional[float],
    abs_dev_pp: Optional[float],
    status: str,
    quality_reasons: list[str],
    context: dict[str, Any],
    consecutive_months: int,
    gate_pp: float,
) -> str:
    """Honest language for a public-health reader. Not an outbreak claim."""
    name = display_name(district_slug, district_slug.replace("_", " ").title())
    if status == STATUS_NO_OBSERVATION:
        return (
            f"No malaria observation is available for {name} this month. "
            "Missing DHIS2 values are not treated as zero cases."
        )
    if status == STATUS_INSUFFICIENT_HISTORY:
        return (
            f"{name} does not yet have {MIN_PRIOR_YEARS_PRIMARY} prior years of the same "
            "calendar month in the comparable-era series. No seasonal anomaly is issued."
        )
    if status == STATUS_DATA_QUALITY:
        if "tests_not_positive" in quality_reasons:
            return (
                f"Malaria positivity cannot be calculated for {name} because tests are "
                "missing or not positive. This is a data-quality signal, not a malaria anomaly."
            )
        if "low_completeness" in quality_reasons or "reporting_collapse" in quality_reasons:
            return (
                f"Malaria positivity in {name} is not issued as an operational anomaly because "
                "reporting completeness is below the operational threshold or collapsed versus "
                "the same month last year. Treat as a data-quality signal pending confirmation."
            )
        if "low_test_volume" in quality_reasons:
            return (
                f"Testing volume in {name} is too low for a stable positivity comparison. "
                "Treat as a data-quality signal, not a malaria anomaly."
            )
        return (
            f"A seasonal malaria comparison is withheld for {name} because of data-quality "
            f"issues ({', '.join(quality_reasons)})."
        )

    pos_pp = None if positivity is None else positivity * 100.0
    med_pp = None if seasonal_median is None else seasonal_median * 100.0
    base = (
        f"Malaria positivity in {name} is {format_pp(pos_pp)}% "
        f"(historical seasonal median {format_pp(med_pp)}%; "
        f"deviation {format_pp(abs_dev_pp, 1)} percentage points vs a past-only expanding median)."
    )
    if status == STATUS_WITHIN_BASELINE:
        return (
            f"{base} This is within the operational magnitude gate of +{gate_pp:.0f} percentage points. "
            "This is a seasonal comparison, not an outbreak prediction."
        )

    extra = []
    d_conf_pct = context.get("d_confirmed_pct")
    d_tests_pct = context.get("d_tests_pct")
    if context.get("confirmed_increasing") and d_conf_pct is not None:
        extra.append(
            f"Confirmed malaria cases increased {abs(d_conf_pct)*100:.0f}% compared with the same month last year."
        )
    elif context.get("confirmed_increasing"):
        extra.append("Confirmed malaria cases also increased compared with the same month last year.")
    if context.get("tests_decreasing") and d_tests_pct is not None:
        extra.append(
            f"Interpretation is limited because testing activity decreased {abs(d_tests_pct)*100:.0f}% versus the same month last year."
        )
    elif context.get("tests_increasing") and d_tests_pct is not None:
        extra.append(
            f"Testing activity increased {d_tests_pct*100:.0f}% versus the same month last year."
        )
    if context.get("primary_state") == "without_supporting_evidence":
        extra.append(
            "Confirmed cases and testing volume do not independently support an increase; treat as a positivity-only seasonal anomaly."
        )
    if consecutive_months >= 2:
        extra.append(
            f"The +{gate_pp:.0f} pp seasonal anomaly has now persisted for {consecutive_months} consecutive calendar months."
        )
    extra.append(
        "This is a contemporaneous seasonal comparison, not an AI outbreak prediction and not a next-month forecast."
    )
    return base + " " + " ".join(extra)


def assess_row(
    row: dict,
    panel_index: dict[tuple[str, str], dict],
    score_index: dict[tuple[str, str], dict],
    *,
    gate_pp: float,
) -> dict[str, Any]:
    district = row["district_slug"]
    period = row["source_period"]
    prior_period = f"{int(period[:4]) - 1}{period[4:6]}"
    prior = panel_index.get((district, prior_period))
    prior_confirmed = None if prior is None else _float(prior.get("malaria_confirmed"))
    prior_tests = None if prior is None else _float(prior.get("malaria_tests"))
    prior_completeness = None if prior is None else _float(prior.get("facility_completeness"))

    quality = classify_data_quality(
        observed_positivity=row.get("observed"),
        tests=row.get("malaria_tests"),
        n_prior=row.get("n_prior"),
        completeness=row.get("facility_completeness"),
        prior_completeness=prior_completeness,
        prior_tests=prior_tests,
        missing_observation=row.get("observed") is None and row.get("tests_not_positive") is True and row.get("malaria_tests") is None,
    )
    # Missing current month: caller passes a placeholder with missing_observation True.
    if row.get("missing_observation"):
        quality = classify_data_quality(
            observed_positivity=None,
            tests=None,
            n_prior=row.get("n_prior") or 0,
            completeness=None,
            prior_completeness=None,
            prior_tests=None,
            missing_observation=True,
        )

    context = classify_operational_context(
        abs_dev_median=row.get("abs_dev_median"),
        confirmed=row.get("malaria_confirmed"),
        tests=row.get("malaria_tests"),
        completeness=row.get("facility_completeness"),
        prior_confirmed=prior_confirmed,
        prior_tests=prior_tests,
        prior_completeness=prior_completeness,
    )
    # Annotate scored row so consecutive walks can see quality blocks.
    row["quality_blocks"] = quality["blocks_malaria_alert"]
    consecutive = consecutive_anomaly_months(score_index, district, period, gate_pp)
    status = operational_status(
        quality=quality,
        abs_dev_median=row.get("abs_dev_median"),
        gate_pp=gate_pp,
    )
    abs_pp = to_percentage_points(row.get("abs_dev_median"))
    message = operational_message(
        district_slug=district,
        positivity=row.get("observed"),
        seasonal_median=row.get("expanding_median"),
        abs_dev_pp=abs_pp,
        status=status,
        quality_reasons=quality["reasons"],
        context=context,
        consecutive_months=consecutive if status == STATUS_UNUSUAL_POSITIVITY else 0,
        gate_pp=gate_pp,
    )
    return {
        "district_slug": district,
        "district_name": display_name(district, district),
        "source_period": period,
        "calendar_month": row.get("calendar_month"),
        "season": sierra_leone_season(int(row.get("calendar_month") or period[4:6])),
        "gate_pp": gate_pp,
        "gate_source": "operational_policy_not_fitted",
        "positivity": row.get("observed"),
        "seasonal_median": row.get("expanding_median"),
        "abs_dev_median": row.get("abs_dev_median"),
        "abs_dev_pp": abs_pp,
        "robust_z_not_used_as_trigger": True,
        "n_prior": row.get("n_prior"),
        "malaria_confirmed": row.get("malaria_confirmed"),
        "malaria_tests": row.get("malaria_tests"),
        "facility_completeness": row.get("facility_completeness"),
        "quality": quality,
        "context": context,
        "status": status,
        "unusual_positivity": status == STATUS_UNUSUAL_POSITIVITY,
        "consecutive_anomaly_months": consecutive if status == STATUS_UNUSUAL_POSITIVITY else 0,
        "sustained_2": bool(status == STATUS_UNUSUAL_POSITIVITY and consecutive >= 2),
        "sustained_3": bool(status == STATUS_UNUSUAL_POSITIVITY and consecutive >= 3),
        "message": message,
        "baseline_periods": row.get("baseline_periods"),
        "lead1_abs_dev_median": None if not score_index.get((district, row.get("lead1_period") or "")) else score_index[(district, row["lead1_period"])].get("abs_dev_median"),
        "lead1_period": row.get("lead1_period"),
    }

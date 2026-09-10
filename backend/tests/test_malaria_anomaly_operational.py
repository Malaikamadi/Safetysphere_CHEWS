"""Operational seasonal-anomaly rules — no training, no CHEWS integration."""

from __future__ import annotations

from services.malaria_anomaly import (
    load_comparable_panel,
    score_panel,
)
import pytest
from services.malaria_anomaly_operational import (
    CANDIDATE_GATES_PP,
    COMPLETENESS_MIN,
    STATUS_DATA_QUALITY,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_NO_OBSERVATION,
    STATUS_UNUSUAL_POSITIVITY,
    STATUS_WITHIN_BASELINE,
    attach_quality_blocks,
    classify_data_quality,
    classify_operational_context,
    consecutive_anomaly_months,
    magnitude_flag,
    operational_message,
    operational_status,
    to_percentage_points,
)


def _row(slug, period, confirmed, tests, completeness=0.5, **extra):
    payload = {
        "district_slug": slug,
        "district_name": slug,
        "source_period": period,
        "malaria_confirmed": confirmed,
        "malaria_tests": tests,
        "facility_completeness": completeness,
        "rainfall_mm": 100.0,
        "temperature_c": 27.0,
        "humidity_percent": 80.0,
    }
    payload.update(extra)
    return payload


def _june_panel(confirmed_by_year: dict, tests=5000, completeness=0.5):
    expansion = [
        _row("bo", f"{year}06", confirmed, tests, completeness)
        for year, confirmed in confirmed_by_year.items()
    ]
    return load_comparable_panel(expansion, [])


def test_magnitude_gate_uses_percentage_points_not_robust_z():
    assert magnitude_flag(0.029, 3) is False
    assert magnitude_flag(0.03, 3) is True
    assert magnitude_flag(0.049, 5) is False
    assert magnitude_flag(0.05, 5) is True
    assert magnitude_flag(None, 3) is False
    assert to_percentage_points(0.042) == 4.2
    assert 3 in CANDIDATE_GATES_PP


def test_past_only_baseline_still_required_for_operational_flag():
    rows = _june_panel({2021: 2500, 2022: 2500, 2023: 2500, 2024: 4000})
    scored = score_panel(rows)
    june_2024 = next(r for r in scored if r["source_period"] == "202406")
    assert all(p < "202406" for p in june_2024["baseline_periods"])
    assert june_2024["expanding_median"] == 0.5
    assert magnitude_flag(june_2024["abs_dev_median"], 3) is True
    assert june_2024["abs_dev_median"] == pytest.approx(0.3)


def test_insufficient_history_blocks_alert():
    rows = _june_panel({2021: 2500, 2022: 2500, 2023: 4000})
    scored = score_panel(rows)
    row = next(r for r in scored if r["source_period"] == "202306")
    quality = classify_data_quality(
        observed_positivity=row["observed"],
        tests=row["malaria_tests"],
        n_prior=row["n_prior"],
        completeness=row["facility_completeness"],
        prior_completeness=0.5,
        prior_tests=100,
    )
    assert row["n_prior"] == 2
    assert quality["blocks_malaria_alert"] is True
    assert "insufficient_history" in quality["reasons"]
    assert operational_status(quality=quality, abs_dev_median=0.3, gate_pp=3) == STATUS_INSUFFICIENT_HISTORY


def test_zero_tests_is_data_quality_not_zero_positivity():
    quality = classify_data_quality(
        observed_positivity=None,
        tests=0,
        n_prior=4,
        completeness=0.5,
        prior_completeness=0.5,
        prior_tests=100,
    )
    assert "tests_not_positive" in quality["reasons"]
    assert quality["blocks_malaria_alert"] is True
    status = operational_status(quality=quality, abs_dev_median=None, gate_pp=3)
    assert status == STATUS_DATA_QUALITY
    assert magnitude_flag(None, 3) is False


def test_missing_observation_not_converted_to_zero():
    quality = classify_data_quality(
        observed_positivity=None,
        tests=None,
        n_prior=4,
        completeness=None,
        prior_completeness=None,
        prior_tests=None,
        missing_observation=True,
    )
    assert "missing_observation" in quality["reasons"]
    assert operational_status(quality=quality, abs_dev_median=None, gate_pp=3) == STATUS_NO_OBSERVATION
    msg = operational_message(
        district_slug="bo",
        positivity=None,
        seasonal_median=None,
        abs_dev_pp=None,
        status=STATUS_NO_OBSERVATION,
        quality_reasons=quality["reasons"],
        context={},
        consecutive_months=0,
        gate_pp=3,
    )
    assert "not treated as zero" in msg


def test_completeness_gating_and_reporting_collapse():
    low = classify_data_quality(
        observed_positivity=0.7,
        tests=1000,
        n_prior=4,
        completeness=0.10,
        prior_completeness=0.50,
        prior_tests=1000,
    )
    assert "low_completeness" in low["reasons"]
    assert COMPLETENESS_MIN == 0.20
    collapse = classify_data_quality(
        observed_positivity=0.7,
        tests=1000,
        n_prior=4,
        completeness=0.30,
        prior_completeness=0.55,
        prior_tests=1000,
    )
    assert "reporting_collapse" in collapse["reasons"]
    assert "low_completeness" not in collapse["reasons"]


def test_testing_bias_states_are_contextual_not_alarm_levels():
    genuine = classify_operational_context(
        abs_dev_median=0.04,
        confirmed=1200,
        tests=2000,
        completeness=0.5,
        prior_confirmed=1000,
        prior_tests=2000,
        prior_completeness=0.5,
    )
    assert genuine["confirmed_increasing"] is True
    assert "positivity_anomaly_confirmed_increasing" in genuine["states"]
    assert genuine["primary_state"] == "confirmed_increasing"

    tests_down = classify_operational_context(
        abs_dev_median=0.04,
        confirmed=800,
        tests=1000,
        completeness=0.5,
        prior_confirmed=800,
        prior_tests=2000,
        prior_completeness=0.5,
    )
    assert tests_down["tests_decreasing"] is True
    assert tests_down["primary_state"] == "tests_decreasing"

    unsupported = classify_operational_context(
        abs_dev_median=0.04,
        confirmed=1000,
        tests=2000,
        completeness=0.5,
        prior_confirmed=1000,
        prior_tests=2000,
        prior_completeness=0.5,
    )
    assert unsupported["primary_state"] == "without_supporting_evidence"


def test_sustained_anomaly_requires_calendar_consecutive_months():
    expansion = []
    for year in (2021, 2022, 2023):
        expansion.append(_row("bo", f"{year}06", 2500, 5000))
        expansion.append(_row("bo", f"{year}07", 2500, 5000))
        expansion.append(_row("bo", f"{year}08", 2500, 5000))
        expansion.append(_row("bo", f"{year}10", 2500, 5000))
    expansion.extend([
        _row("bo", "202406", 4000, 5000),
        _row("bo", "202407", 4000, 5000),
        _row("bo", "202408", 4000, 5000),
        _row("bo", "202410", 4000, 5000),  # skip September
    ])
    scored = score_panel(load_comparable_panel(expansion, []))
    panel_index = {(r["district_slug"], r["source_period"]): r for r in load_comparable_panel(expansion, [])}
    attach_quality_blocks(scored, panel_index)
    index = {(r["district_slug"], r["source_period"]): r for r in scored}
    assert consecutive_anomaly_months(index, "bo", "202406", 3) == 1
    assert consecutive_anomaly_months(index, "bo", "202407", 3) == 2
    assert consecutive_anomaly_months(index, "bo", "202408", 3) == 3
    assert consecutive_anomaly_months(index, "bo", "202410", 3) == 1  # gap in September


def test_operational_message_does_not_claim_ai_or_outbreak():
    msg = operational_message(
        district_slug="kenema",
        positivity=0.70,
        seasonal_median=0.658,
        abs_dev_pp=4.2,
        status=STATUS_UNUSUAL_POSITIVITY,
        quality_reasons=[],
        context={
            "confirmed_increasing": True,
            "d_confirmed_pct": 0.12,
            "tests_decreasing": False,
            "tests_increasing": False,
            "primary_state": "confirmed_increasing",
            "d_tests_pct": 0.0,
        },
        consecutive_months=1,
        gate_pp=3,
    )
    lower = msg.lower()
    assert "kenema" in lower
    assert "4.2 percentage points" in msg
    assert "ai predicts" not in lower
    assert "high malaria risk" not in lower
    assert "not an ai outbreak prediction" in lower
    limited = operational_message(
        district_slug="bo",
        positivity=0.70,
        seasonal_median=0.65,
        abs_dev_pp=5.0,
        status=STATUS_UNUSUAL_POSITIVITY,
        quality_reasons=[],
        context={
            "confirmed_increasing": False,
            "tests_decreasing": True,
            "d_tests_pct": -0.18,
            "d_confirmed_pct": None,
            "primary_state": "tests_decreasing",
        },
        consecutive_months=1,
        gate_pp=3,
    )
    assert "testing activity decreased 18%" in limited
    assert operational_status(
        quality={"blocks_malaria_alert": False},
        abs_dev_median=0.01,
        gate_pp=3,
    ) == STATUS_WITHIN_BASELINE

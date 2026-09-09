"""Positivity training table — calendar t+1, no model training."""

import pytest

from services.malaria_positivity_forecast import (
    COMPLETENESS_MIN,
    FEATURE_COLUMNS,
    TARGET_NAME,
    filter_positivity_rows,
    leakage_audit,
    positivity,
)


def _row(slug, period, confirmed, tests, completeness, **extra):
    payload = {
        "district_slug": slug,
        "district_id": slug,
        "district_name": slug,
        "source_period": period,
        "malaria_confirmed": confirmed,
        "malaria_tests": tests,
        "facility_completeness": completeness,
        "reporting_facilities": 10,
        "expected_facilities": 20,
        "rainfall_mm": 10,
        "temperature_c": 27,
        "humidity_percent": 80,
        "health_source": "test",
        "climate_source": "test",
    }
    payload.update(extra)
    return payload


def test_positivity_only_when_tests_positive():
    assert positivity(50, 100) == 0.5
    assert positivity(50, 0) is None
    assert positivity(50, None) is None
    assert positivity(None, 100) is None


def test_keeps_calendar_t_plus_1_positivity():
    panel = [
        _row("bo", "202501", 100, 200, 0.5),
        _row("bo", "202502", 80, 160, 0.5),
    ]
    kept, report = filter_positivity_rows(panel)
    assert report["final_training_rows"] == 1
    assert kept[0]["feature_period"] == "202501"
    assert kept[0]["target_period"] == "202502"
    assert kept[0][TARGET_NAME] == 0.5
    assert kept[0]["malaria_positivity"] == 0.5
    assert "malaria_confirmed_next" not in kept[0]
    assert TARGET_NAME not in FEATURE_COLUMNS


def test_rejects_skipped_month_even_if_later_row_exists():
    panel = [
        _row("bo", "202603", 15000, 20000, 0.53),
        _row("bo", "202605", 104, 200, 0.50),
    ]
    kept, report = filter_positivity_rows(panel)
    assert kept == []
    assert report["rows_removed_non_consecutive_target"] == 2


def test_rejects_zero_target_tests():
    panel = [
        _row("bo", "202501", 100, 200, 0.5),
        _row("bo", "202502", 80, 0, 0.5),
    ]
    kept, report = filter_positivity_rows(panel)
    assert kept == []
    assert report["rows_removed_target_tests_not_positive"] == 1


def test_null_lag_when_202306_absent():
    panel = [
        _row("bo", "202307", 100, 200, 0.5),
        _row("bo", "202308", 90, 180, 0.5),
    ]
    kept, _ = filter_positivity_rows(panel)
    assert kept[0]["lag1_malaria_confirmed"] is None
    assert kept[0]["lag1_malaria_tests"] is None
    assert kept[0]["lag1_rainfall_mm"] is None
    assert kept[0]["three_month_rainfall_accumulation"] is None
    assert kept[0]["confirmed_pct_change"] is None
    assert kept[0]["lag1_malaria_positivity"] is None


def test_climate_lags_are_calendar_not_next_observed():
    panel = [
        _row("bo", "202501", 100, 200, 0.5, rainfall_mm=10),
        _row("bo", "202503", 90, 180, 0.5, rainfall_mm=99),
        _row("bo", "202504", 80, 160, 0.5, rainfall_mm=5),
    ]
    kept, _ = filter_positivity_rows(panel)
    by_period = {r["feature_period"]: r for r in kept}
    assert "202501" not in by_period  # no calendar 202502
    assert by_period["202503"]["lag1_rainfall_mm"] is None
    assert by_period["202503"]["rainfall_mm"] == 99


def test_leakage_audit_excludes_target_period_fields():
    panel = [
        _row("bo", "202501", 100, 200, 0.5),
        _row("bo", "202502", 80, 160, 0.5),
    ]
    kept, report = filter_positivity_rows(panel)
    audit = leakage_audit(kept)
    assert audit["passed"] is True
    assert report["leakage_audit"]["passed"] is True
    assert report["model_trained"] is False


def test_stop_if_positivity_outside_unit_interval():
    panel = [
        _row("bo", "202501", 100, 200, 0.5),
        _row("bo", "202502", 300, 100, 0.5),
    ]
    with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
        filter_positivity_rows(panel)


def test_completeness_threshold_unchanged():
    assert COMPLETENESS_MIN == 0.20
    panel = [
        _row("bo", "202501", 100, 200, 0.10),
        _row("bo", "202502", 80, 160, 0.50),
    ]
    kept, report = filter_positivity_rows(panel)
    assert kept == []
    assert report["rows_removed_low_completeness_feature"] == 1

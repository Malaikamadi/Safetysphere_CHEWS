"""Quality filter for malaria_confirmed(t+1) — no training."""

from services.malaria_forecast import (
    COMPLETENESS_MIN,
    TARGET_NAME,
    calendar_next,
    filter_training_rows,
)


def _row(slug, period, confirmed, completeness, **extra):
    payload = {
        "district_slug": slug,
        "district_id": slug,
        "district_name": slug,
        "source_period": period,
        "malaria_confirmed": confirmed,
        "facility_completeness": completeness,
        "reporting_facilities": 10,
        "expected_facilities": 20,
        "malaria_tests": 100,
        "malaria_rdt_positive": 40,
        "rainfall_mm": 10,
        "temperature_c": 27,
        "humidity_percent": 80,
        "trainable": True,
    }
    payload.update(extra)
    return payload


def test_calendar_next():
    assert calendar_next("202512") == "202601"
    assert calendar_next("202501") == "202502"


def test_keeps_consecutive_complete_pair():
    panel = [
        _row("bo", "202501", 100, 0.5),
        _row("bo", "202502", 110, 0.5),
    ]
    kept, report = filter_training_rows(panel)
    assert report["final_training_rows"] == 1
    assert kept[0]["feature_period"] == "202501"
    assert kept[0]["target_period"] == "202502"
    assert kept[0][TARGET_NAME] == 110
    assert kept[0]["calendar_consecutive"] is True


def test_rejects_skipped_month_even_if_next_observed_exists():
    panel = [
        _row("bo", "202503", 100, 0.6),
        _row("bo", "202505", 90, 0.6),
    ]
    kept, report = filter_training_rows(panel)
    assert kept == []
    assert report["rows_removed_non_consecutive_target"] == 2


def test_rejects_low_completeness_feature_and_target():
    panel = [
        _row("bo", "202501", 100, 0.10),
        _row("bo", "202502", 110, 0.50),
        _row("kono", "202501", 100, 0.50),
        _row("kono", "202502", 20, 0.05),
    ]
    kept, report = filter_training_rows(panel)
    assert kept == []
    assert report["rows_removed_low_completeness_feature"] == 1
    assert report["rows_removed_low_completeness_target"] == 1
    assert COMPLETENESS_MIN == 0.20


def test_does_not_impute_missing_202604():
    panel = [
        _row("bo", "202603", 15000, 0.53),
        _row("bo", "202605", 104, 0.007),
    ]
    kept, report = filter_training_rows(panel)
    assert kept == []
    assert report["imputed_missing_months"] is False
    assert report["missing_filled_as_zero"] is False
    assert report["model_trained"] is False

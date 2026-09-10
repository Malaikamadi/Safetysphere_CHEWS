"""Flood-event data foundation — schema validation only; no training, no CHEWS integration."""

from __future__ import annotations

from datetime import date

from services.flood_data_foundation import (
    FORBIDDEN_LABEL_ORIGINS,
    VERDICT_B,
    geographic_join_plan,
    missing_not_nonflood,
    validate_flood_event,
    weather_alignment_windows,
)


def _valid_event(**overrides):
    row = {
        "event_id": "ndma-example-2023-delken",
        "event_start": "2023-09-01",
        "event_end": "2023-09-01",
        "district": "bonthe",
        "location_name": "Delken Village",
        "event_type": "coastal_flood",
        "source": "NDMA public assessment page (schema example only — not ingested)",
        "label_origin": "ndma_assessment",
        "verified": False,
        "affected_population": None,
    }
    row.update(overrides)
    return row


def test_missing_is_not_converted_to_nonflood():
    assert missing_not_nonflood(None) is None
    assert missing_not_nonflood("") is None
    assert missing_not_nonflood("unknown") is None
    assert missing_not_nonflood(12) == 12


def test_rainfall_threshold_label_is_rejected():
    result = validate_flood_event(_valid_event(label_origin="rainfall_threshold"))
    assert result["ok"] is False
    assert "rainfall_or_synthetic_label_origin_forbidden" in result["errors"]
    assert "rainfall_threshold" in FORBIDDEN_LABEL_ORIGINS


def test_synthetic_source_cannot_be_verified_observation():
    result = validate_flood_event(_valid_event(
        source="synthetic_chews_training",
        verified=True,
        label_origin="synthetic_flood_occurred",
    ))
    assert result["ok"] is False
    assert "synthetic_source_cannot_be_an_observation" in result["errors"]
    assert "synthetic_source_cannot_be_verified" in result["errors"]


def test_valid_dated_community_event_is_lead_time_eligible():
    result = validate_flood_event(_valid_event())
    assert result["ok"] is True
    assert result["lead_time_eligible"] is True
    assert result["temporal_grain"] == "day"


def test_year_only_history_is_not_lead_time_eligible():
    result = validate_flood_event(_valid_event(event_start="2017"))
    assert result["ok"] is True
    assert result["lead_time_eligible"] is False
    assert result["temporal_grain"] == "year"
    assert "year_only_start_not_usable_for_lead_time" in result["warnings"]


def test_weather_windows_are_strictly_before_t0():
    windows = weather_alignment_windows(date(2022, 8, 28))
    assert windows["lead_time_features"]["t-1"]["end"] == "2022-08-27"
    assert windows["lead_time_features"]["t-3"]["start"] == "2022-08-25"
    assert windows["lead_time_features"]["t-7"]["end"] == "2022-08-27"
    assert windows["lead_time_features"]["t-1"]["includes_t0"] is False
    assert windows["forbidden"]["t+1_and_later"] is True
    assert windows["do_not_use_as_event_label"] is True
    assert windows["contemporaneous_context_not_lead_time"]["t0"]["start"] == "2022-08-28"


def test_district_only_event_is_high_uncertainty_not_silent_centroid():
    result = validate_flood_event(_valid_event(location_name=None, latitude=None, longitude=None))
    assert result["ok"] is True
    geo = result["geographic_join"]
    assert geo["method"] == "district_centroid_fallback"
    assert geo["mapping_uncertainty"] == "high"
    assert geo["centroid_used_silently"] is False


def test_coordinates_outrank_centroid():
    geo = geographic_join_plan({
        "latitude": 8.44,
        "longitude": -13.23,
        "location_name": "Regent",
        "district": "western_area_urban",
    })
    assert geo["method"] == "event_coordinates"
    assert geo["mapping_uncertainty"] == "low"


def test_canonical_table_rejects_synthetic_flood_occurred_column():
    result = validate_flood_event(_valid_event(flood_occurred=1))
    assert result["ok"] is False
    assert "do_not_store_synthetic_flood_occurred_on_canonical_events" in result["errors"]


def test_verdict_is_acquisition_required_not_dataset_complete():
    assert VERDICT_B == "B"

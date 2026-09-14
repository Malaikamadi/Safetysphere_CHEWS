"""chews_flood_event_v0 — observation registry tests; no training, no rainfall labels."""

from __future__ import annotations

from datetime import date

from services.chews_flood_event_v0 import (
    FORBIDDEN_LABEL_FIELDS,
    canonicalize_record,
    detect_duplicates,
    historical_context_from_catalog,
    join_weather,
    match_event_location,
    parse_iso_date,
    quality_audit,
)

ZONES = [
    {"id": "regent", "name": "Regent / Sugar Loaf", "district": "western_area_urban", "lat": 8.4406, "lng": -13.2336},
    {"id": "bumbuna", "name": "Bumbuna (dam buffer)", "district": "tonkolili", "lat": 8.72, "lng": -11.94},
    {"id": "kroo_bay", "name": "Kroo Bay", "district": "western_area_urban", "lat": 8.4892, "lng": -13.2387},
]


def test_iso_dates_are_valid_and_year_only_is_not_a_day():
    assert parse_iso_date("2023-09-01") == date(2023, 9, 1)
    assert parse_iso_date("2017") is None
    event = canonicalize_record({
        "source_record_id": "year-only",
        "event_source": "catalog",
        "event_start_date": None,
        "event_year": 2017,
        "event_location_name": "Regent",
        "exclude_from_daily_target": True,
    }, ZONES)
    assert event["in_daily_target"] is False


def test_year_only_catalog_stays_in_context_not_daily_target():
    rows = historical_context_from_catalog([{
        "id": "regent", "name": "Regent", "district": "western_area_urban",
        "flood_history": [{"year": 2017, "description": "Aug 14 mudslide", "impact": "deaths"}],
    }])
    assert rows[0]["temporal_grain"] == "year"
    assert rows[0]["in_daily_target"] is False


def test_duplicate_event_detection():
    events = [
        {"event_id": "a", "in_daily_target": True, "event_start_date": "2022-08-28",
         "event_location_name": "Kaningo", "event_source": "ifrc_dref"},
        {"event_id": "b", "in_daily_target": True, "event_start_date": "2022-08-28",
         "event_location_name": "Kaningo", "event_source": "ifrc_dref"},
        {"event_id": "c", "in_daily_target": True, "event_start_date": "2022-08-28",
         "event_location_name": "Culvert", "event_source": "ifrc_dref"},
    ]
    dups = detect_duplicates(events)
    assert len(dups) == 1
    assert set(dups[0]["event_ids"]) == {"a", "b"}


def test_source_provenance_is_retained():
    event = canonicalize_record({
        "source_record_id": "ndma-delken-2023-09-01",
        "event_source": "ndma_assessment",
        "source_url": "https://ndma.gov.sl/example",
        "source_document": "NDMA Delken assessment",
        "event_start_date": "2023-09-01",
        "event_location_name": "Delken Village",
        "district": "bonthe",
    }, ZONES)
    assert event["event_source"] == "ndma_assessment"
    assert event["source_url"].startswith("https://")


def test_coordinates_are_not_fabricated_and_unmatched_stays_unmatched():
    event = canonicalize_record({
        "source_record_id": "ndma-delken-2023-09-01",
        "event_source": "ndma_assessment",
        "event_start_date": "2023-09-01",
        "event_location_name": "Delken Village",
        "district": "bonthe",
        "latitude": None,
        "longitude": None,
    }, ZONES)
    assert event["latitude"] is None
    assert event["location_match_status"] == "unmatched"
    assert event["matched_flood_zone_id"] is None
    assert event["centroid_assigned_silently"] is False


def test_named_catalog_community_matches_without_inventing_coords():
    match = match_event_location({"event_location_name": "Regent", "latitude": None, "longitude": None}, ZONES)
    assert match["location_match_status"] == "matched"
    assert match["matched_flood_zone_id"] == "zone:regent"
    assert match["centroid_assigned_silently"] is False


def test_district_event_does_not_silently_get_a_centroid():
    match = match_event_location({
        "event_location_name": "Bonthe District (several chiefdoms)",
        "district": "bonthe",
        "latitude": None,
        "longitude": None,
    }, ZONES)
    assert match["location_match_status"] == "unmatched"
    assert match["centroid_assigned_silently"] is False


def test_lead_safe_weather_excludes_event_day_and_preserves_missing():
    joined = join_weather(
        {
            "in_daily_target": True,
            "event_start_date": "2024-09-23",
            "location_match_status": "matched",
            "matched_flood_zone_id": "zone:bumbuna",
        },
        {("zone:bumbuna", "2024-09-23"): {
            "precipitation_mm": "80", "rainfall_24h": "80",
            "rainfall_prev_24h": "12", "rainfall_prev_72h": "40",
            "rainfall_prev_7d": "90", "rainfall_prev_14d": "",
        }},
    )
    assert joined["lead_safe_uses_event_day"] is False
    assert joined["rainfall_prev_24h"] == 12
    assert joined["event_day_rainfall_24h"] == 80
    assert joined["rainfall_prev_14d"] is None
    assert joined["weather_join_status"] == "incomplete_windows"


def test_unmatched_event_does_not_receive_centroid_weather():
    joined = join_weather(
        {
            "in_daily_target": True,
            "event_start_date": "2023-09-01",
            "location_match_status": "unmatched",
            "matched_flood_zone_id": None,
        },
        {("district_centroid:bonthe", "2023-09-01"): {"rainfall_prev_24h": "99"}},
    )
    assert joined["weather_join_status"] == "unmatched_location_no_centroid_weather"
    assert joined["rainfall_prev_24h"] is None


def test_no_rainfall_threshold_or_negative_labels():
    event = canonicalize_record({
        "source_record_id": "x",
        "event_source": "ndma_assessment",
        "event_start_date": "2023-09-01",
        "event_location_name": "Delken Village",
        "district": "bonthe",
    }, ZONES)
    for field in FORBIDDEN_LABEL_FIELDS:
        assert field not in event
    assert event["negative_label_created"] is False
    audit = quality_audit([event], [], [])
    assert audit["flood_occurred_created"] is False
    assert audit["negative_labels_created"] is False


def test_insufficient_events_are_not_declared_backtest_ready():
    audit = quality_audit([{
        "event_id": "one",
        "in_daily_target": True,
        "temporal_grain": "day",
        "event_start_date": "2023-09-01",
        "district": "bonthe",
        "location_match_status": "unmatched",
        "matched_flood_zone_id": None,
        "event_source": "ndma_assessment",
        "observation_status": "observed",
        "corroborating_sources": [],
        "latitude": None,
        "longitude": None,
        "weather_join_status": "unmatched_location_no_centroid_weather",
    }], [], [])
    assert audit["classification"] == "C"
    assert audit["planning_criteria"]["met"] is False

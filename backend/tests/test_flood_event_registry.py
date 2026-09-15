"""Flood-event acquisition: corroboration merge and planning-floor rules."""

from __future__ import annotations

from services.chews_flood_event_v0 import canonicalize_record, quality_audit
from services.flood_event_registry import (
    geographic_floor_met,
    merge_corroborated_records,
    wet_season_year,
)


def test_corroborated_duplicate_events_merge_to_one():
    merged, candidates = merge_corroborated_records([
        {
            "source_record_id": "ifrc-wellington-2022-08-28",
            "event_source": "ifrc_dref",
            "source_url": "https://example.org/ifrc",
            "event_start_date": "2022-08-28",
            "event_location_name": "Wellington",
            "district": "western_area_urban",
            "description": "IFRC lists Wellington among 28 August 2022 flood neighbourhoods.",
            "confidence": "medium",
            "latitude": None,
            "longitude": None,
        },
        {
            "source_record_id": "ndma-wellington-2022-08-28",
            "event_source": "ndma_assessment",
            "source_url": "https://ndma.gov.sl/example",
            "event_start_date": "2022-08-28",
            "event_location_name": "Wellington",
            "district": "western_area_urban",
            "description": "NDMA: Water Street, Wellington was among the hardest hit on 28 August 2022.",
            "confidence": "high",
            "latitude": None,
            "longitude": None,
        },
    ])
    daily = [row for row in merged if row.get("event_start_date")]
    assert len(daily) == 1
    assert daily[0]["source_record_id"] == "ndma-wellington-2022-08-28"
    assert daily[0]["corroboration_count"] == 2
    assert daily[0]["latitude"] is None
    assert len(candidates) == 1
    assert set(candidates[0]["record_ids"]) == {
        "ifrc-wellington-2022-08-28",
        "ndma-wellington-2022-08-28",
    }
    sources = {ref["event_source"] for ref in daily[0]["corroborating_sources"]}
    assert "ifrc_dref" in sources


def test_same_place_different_dates_are_not_merged():
    merged, candidates = merge_corroborated_records([
        {
            "source_record_id": "culvert-2019",
            "event_source": "ifrc_dref",
            "event_start_date": "2019-08-01",
            "event_location_name": "Culvert",
            "district": "western_area_urban",
        },
        {
            "source_record_id": "culvert-2022",
            "event_source": "ifrc_dref",
            "event_start_date": "2022-08-28",
            "event_location_name": "Culvert",
            "district": "western_area_urban",
        },
    ])
    assert len(merged) == 2
    assert candidates == []


def test_merge_does_not_invent_coordinates_from_a_district_centroid():
    merged, _ = merge_corroborated_records([
        {
            "source_record_id": "a",
            "event_source": "ifrc_dref",
            "event_start_date": "2019-08-01",
            "event_location_name": "Culvert",
            "district": "western_area_urban",
            "latitude": None,
            "longitude": None,
        },
        {
            "source_record_id": "b",
            "event_source": "ndma_assessment",
            "event_start_date": "2019-08-01",
            "event_location_name": "Culvert",
            "district": "western_area_urban",
            "latitude": None,
            "longitude": None,
        },
    ])
    assert merged[0]["latitude"] is None
    assert merged[0]["longitude"] is None


def test_western_area_plus_four_regimes_meets_geographic_floor():
    geo = geographic_floor_met({
        "western_area_urban",
        "bonthe",
        "tonkolili",
        "bo",
        "pujehun",
    })
    assert geo["met"] is True
    assert geo["western_area_plus_four_regimes_met"] is True


def test_wet_season_year_is_may_to_november_only():
    assert wet_season_year("2024-08-14") == "2024"
    assert wet_season_year("2024-01-12") is None


def test_thirty_dated_events_can_meet_event_data_floor_while_unmatched():
    events = []
    districts = [
        "western_area_urban", "bonthe", "tonkolili", "bo", "pujehun",
        "kenema", "moyamba", "kono",
    ]
    years = [2019, 2022, 2024]
    for i in range(30):
        events.append({
            "event_id": f"e{i}",
            "in_daily_target": True,
            "temporal_grain": "day",
            "event_start_date": f"{years[i % 3]}-08-{(i % 28) + 1:02d}",
            "district": districts[i % len(districts)],
            "location_match_status": "unmatched",
            "matched_flood_zone_id": None,
            "event_source": "ifrc_dref",
            "observation_status": "observed",
            "corroborating_sources": [],
            "latitude": None,
            "longitude": None,
            "weather_join_status": "unmatched_location_no_centroid_weather",
            "corroboration_count": 1,
        })
    audit = quality_audit(events, [], [])
    assert audit["planning_criteria"]["event_data_floor_met"] is True
    assert audit["flood_occurred_created"] is False
    assert audit["classification"] == "B"
    assert "STOP BEFORE MODELING" in audit["classification_label"]

"""Flood weather history v1 — no flood labels, no training, no production edits."""

from __future__ import annotations

from datetime import date

from services.flood_weather_history import (
    FORBIDDEN_LABEL_FIELDS,
    attach_baselines_efficient,
    attach_rainfall_features,
    daterange,
    load_canonical_locations,
    missing_not_zero,
    quality_audit,
    rolling_sum,
    validate_coordinates,
)


def missing_not_zero(value):  # noqa: A001 — test helper name if not exported
    from services.flood_weather_history import _num
    return _num(value)


def _days(precip):
    rows = []
    start = date(2020, 8, 1)
    for i, value in enumerate(precip):
        day = date(2020, 8, 1 + i)
        rows.append({
            "location_id": "zone:test",
            "location_name": "Test",
            "location_type": "flood_zone",
            "district": "bo",
            "latitude": 7.96,
            "longitude": -11.74,
            "date": day.isoformat(),
            "precipitation_mm": value,
            "calendar_month": day.month,
            "wet_season_indicator": True,
            "observation_present": value is not None,
        })
    return rows


def test_rolling_sum_does_not_zero_fill_missing():
    values = [1.0, None, 3.0, 4.0]
    assert rolling_sum(values, 3, 3, include_end=True) is None
    assert rolling_sum(values, 3, 2, include_end=True) == 7.0


def test_lead_safe_windows_exclude_current_day():
    rows = _days([1, 2, 4, 8, 16])
    attach_rainfall_features(rows)
    day = rows[4]  # 16
    assert day["rainfall_24h"] == 16
    assert day["rainfall_72h"] == 4 + 8 + 16
    assert day["rainfall_prev_24h"] == 8
    assert day["rainfall_prev_72h"] == 2 + 4 + 8
    assert day["rainfall_prev_24h"] != day["rainfall_24h"]


def test_no_future_days_in_prev_features():
    rows = _days([10, 20, 30])
    attach_rainfall_features(rows)
    assert rows[0]["rainfall_prev_24h"] is None
    assert rows[1]["rainfall_prev_24h"] == 10
    assert rows[1]["rainfall_prev_72h"] is None  # needs 3 prior days
    assert rows[2]["rainfall_24h"] == 30
    assert 40 not in (rows[0].get("rainfall_prev_24h"), rows[1].get("rainfall_prev_7d"))


def test_date_continuity_helper_has_no_gaps():
    days = daterange(date(2015, 1, 1), date(2015, 1, 31))
    assert len(days) == 31
    assert days[0].isoformat() == "2015-01-01"
    assert days[-1].isoformat() == "2015-01-31"


def test_duplicate_location_date_detected():
    rows = _days([1, 2]) + _days([1, 2])
    audit = quality_audit(
        rows,
        [{"location_id": "zone:test"}],
        date(2020, 8, 1),
        date(2020, 8, 2),
    )
    assert audit["n_duplicate_location_dates"] == 2


def test_missing_precipitation_stays_none_not_zero():
    rows = _days([0.0, None, 5.0])
    attach_rainfall_features(rows)
    assert rows[1]["precipitation_mm"] is None
    assert rows[1]["rainfall_24h"] is None
    assert rows[0]["precipitation_mm"] == 0.0
    assert rows[2]["rainfall_72h"] is None


def test_coordinates_validated_in_sierra_leone_bbox():
    assert validate_coordinates(8.4892, -13.2387)["ok"] is True
    assert validate_coordinates(0.0, 0.0)["ok"] is False
    assert validate_coordinates(None, -13.2)["ok"] is False


def test_canonical_locations_include_zones_and_flagged_centroids():
    locations = load_canonical_locations()
    zones = [loc for loc in locations if loc["location_type"] == "flood_zone"]
    cents = [loc for loc in locations if loc["location_type"] == "district_centroid"]
    assert len(zones) == 23
    assert len(cents) == 16
    assert all(z["coordinate_ok"] for z in zones)
    assert all(c["coordinate_quality"] == "admin_centroid_fallback" for c in cents)
    assert all(loc["represents_all_flood_prone_communities"] is False for loc in locations)


def test_past_only_baseline_ignores_later_years():
    rows = []
    for year, august_rain in ((2015, 10.0), (2016, 10.0), (2017, 10.0), (2018, 40.0)):
        rows.append({
            "location_id": "zone:test",
            "date": f"{year}-08-15",
            "precipitation_mm": august_rain,
        })
    attach_baselines_efficient(rows)
    y2018 = next(r for r in rows if r["date"].startswith("2018"))
    y2016 = next(r for r in rows if r["date"].startswith("2016"))
    assert y2016["rainfall_historical_median_past_only"] is None
    assert y2018["baseline_prior_years"] == 3
    assert y2018["rainfall_historical_median_past_only"] == 10.0
    assert y2018["rainfall_anomaly_past_only"] == 30.0
    assert y2018["rainfall_historical_median_descriptive"] == 10.0


def test_dataset_schema_forbids_flood_labels():
    rows = _days([1.0])
    attach_rainfall_features(rows)
    for field in FORBIDDEN_LABEL_FIELDS:
        assert field not in rows[0]
    audit = quality_audit(rows, [{"location_id": "zone:test"}], date(2020, 8, 1), date(2020, 8, 1))
    assert audit["forbidden_label_fields_present"] == []
    assert audit["missing_not_replaced_with_zero"] is True


def test_precipitation_non_negativity_counted():
    rows = _days([-1.0, 0.0, 2.0])
    audit = quality_audit(rows, [{"location_id": "zone:test"}], date(2020, 8, 1), date(2020, 8, 3))
    assert audit["negative_precipitation"] == 1


def test_build_dataset_from_opener_is_reproducible_and_unlabelled():
    from services.flood_weather_history import build_dataset, build_manifest

    def opener(_url):
        return {
            "daily": {
                "time": ["2015-08-01", "2015-08-02", "2015-08-03"],
                "precipitation_sum": [1.0, 2.0, 4.0],
                "rain_sum": [1.0, 2.0, 4.0],
                "temperature_2m_mean": [26.0, 26.0, 26.0],
                "temperature_2m_min": [24.0, 24.0, 24.0],
                "temperature_2m_max": [28.0, 28.0, 28.0],
                "relative_humidity_2m_mean": [80.0, 80.0, 80.0],
                "soil_moisture_0_to_7cm_mean": [0.3, 0.3, 0.3],
                "wind_speed_10m_mean": [10.0, 10.0, 10.0],
            },
            "daily_units": {"precipitation_sum": "mm"},
            "timezone": "Africa/Abidjan",
            "elevation": 3.0,
        }

    locations = [{
        "location_id": "zone:kroo_bay",
        "location_name": "Kroo Bay",
        "location_type": "flood_zone",
        "district": "western_area_urban",
        "latitude": 8.4892,
        "longitude": -13.2387,
        "source": "test",
        "coordinate_quality": "catalog_point",
        "coordinate_ok": True,
        "represents_all_flood_prone_communities": False,
    }]
    payload = build_dataset(
        start=date(2015, 8, 1),
        end=date(2015, 8, 3),
        opener=opener,
        locations=locations,
    )
    assert payload["flood_labels_created"] is False
    assert payload["model_trained"] is False
    assert payload["quality"]["n_rows"] == 3
    assert payload["extracts"][0]["http_status"] == 200
    manifest = build_manifest(payload)
    assert manifest["flood_labels_created"] is False
    assert "flood_occurred" not in manifest["transformations"]
    assert payload["rows"][2]["rainfall_prev_24h"] == 2.0

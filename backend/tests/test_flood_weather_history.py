"""Flood weather history v1 — no flood labels, no training, no production edits."""

from __future__ import annotations

from datetime import date

from services.flood_weather_history import (
    FORBIDDEN_LABEL_FIELDS,
    attach_baselines_efficient,
    attach_rainfall_features,
    daterange,
    load_canonical_locations,
    quality_audit,
    rolling_sum,
    validate_coordinates,
)


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
    assert payload["rows"][2]["rainfall_24h"] == 4.0
    assert payload["extracts"][0]["timezone"] == "Africa/Abidjan"
    assert payload["extracts"][0]["daily_units"]["precipitation_sum"] == "mm"
    assert "flood_occurred" not in payload["rows"][0]
    assert payload["disclaimer"].startswith("Historical weather data does not constitute")


def test_build_dataset_records_fetch_failure_without_flood_labels(monkeypatch):
    from services import flood_weather_history as mod

    def boom(*_args, **_kwargs):
        raise RuntimeError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(mod, "fetch_archive_daily", boom)
    locations = [{
        "location_id": "zone:fetch_fail",
        "location_name": "Fail",
        "location_type": "flood_zone",
        "district": "bo",
        "latitude": 7.96,
        "longitude": -11.74,
        "source": "test",
        "coordinate_quality": "catalog_point",
        "coordinate_ok": True,
        "represents_all_flood_prone_communities": False,
    }]
    payload = mod.build_dataset(
        start=date(2015, 8, 1),
        end=date(2015, 8, 2),
        locations=locations,
        reuse_raw=False,
        persist_raw=False,
        sleep_seconds=0,
    )
    assert payload["rows"] == []
    assert payload["fetch_failures"][0]["location_id"] == "zone:fetch_fail"
    assert payload["fetch_failures"][0]["last_error"]
    assert payload["fetch_failures"][0]["failure_status"]
    assert payload["flood_labels_created"] is False
    assert "flood_occurred" not in (payload.get("quality") or {})


def test_quality_audit_tracks_year_and_month_gaps():
    rows = _days([1.0, None])
    rows[1]["date"] = "2020-09-02"
    rows[1]["wet_season_indicator"] = True
    audit = quality_audit(rows, [{"location_id": "zone:test"}], date(2020, 8, 1), date(2020, 8, 2))
    assert audit["gaps_by_year"]["2020"] == 1
    assert audit["gaps_by_month"]["09"] == 1
    assert audit["gaps_by_location"]["zone:test"] == 1


def _ok_payload(times, precip):
    n = len(times)
    return {
        "daily": {
            "time": times,
            "precipitation_sum": precip,
            "rain_sum": precip,
            "temperature_2m_mean": [26.0] * n,
            "temperature_2m_min": [24.0] * n,
            "temperature_2m_max": [28.0] * n,
            "relative_humidity_2m_mean": [80.0] * n,
            "soil_moisture_0_to_7cm_mean": [0.3] * n,
            "wind_speed_10m_mean": [10.0] * n,
        },
        "daily_units": {"precipitation_sum": "mm", "temperature_2m_mean": "°C", "relative_humidity_2m_mean": "%"},
        "timezone": "Africa/Abidjan",
    }


def test_expected_v1_calendar_is_4261_days():
    from services.flood_weather_history import EXPECTED_DAYS_V1, PERIOD_END, PERIOD_START
    assert EXPECTED_DAYS_V1 == 4261
    assert len(daterange(PERIOD_START, PERIOD_END)) == 4261


def test_retry_after_seconds_win_over_exponential():
    from services.flood_weather_history import retry_wait_seconds
    wait = retry_wait_seconds(0, retry_after="9", backoff_seconds=20, rng=type("R", (), {"uniform": staticmethod(lambda a, b: 0)})())
    assert wait == 9.0


def test_exponential_backoff_with_zero_jitter():
    from services.flood_weather_history import retry_wait_seconds
    rng = type("R", (), {"uniform": staticmethod(lambda a, b: 0.0)})()
    assert retry_wait_seconds(0, backoff_seconds=20, rng=rng) == 20
    assert retry_wait_seconds(1, backoff_seconds=20, rng=rng) == 40
    assert retry_wait_seconds(2, backoff_seconds=20, rng=rng) == 80


def test_429_retries_then_succeeds_without_tight_loop():
    import json
    from services.flood_weather_history import fetch_archive_daily

    waits = []
    calls = {"n": 0}

    def transport(_url, _timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            return 429, b"rate limited", {"Retry-After": "11"}
        body = json.dumps(_ok_payload(["2015-08-01"], [1.0]))
        return 200, body.encode(), {}

    payload = fetch_archive_daily(
        8.4892, -13.2387, date(2015, 8, 1), date(2015, 8, 1),
        transport=transport,
        sleeper=waits.append,
        max_retries=5,
        backoff_seconds=20,
    )
    assert calls["n"] == 3
    assert waits == [11.0, 11.0]
    assert payload["daily"]["precipitation_sum"] == [1.0]
    assert payload["_chews_request"]["attempts"] == 3


def test_500_uses_exponential_backoff_not_immediate_retry():
    from services.flood_weather_history import ArchiveFetchError, fetch_archive_daily

    waits = []

    def transport(_url, _timeout):
        return 500, b'{"error":true}', {}

    rng = type("R", (), {"uniform": staticmethod(lambda a, b: 0.0)})()
    try:
        fetch_archive_daily(
            8.4, -13.2, date(2015, 8, 1), date(2015, 8, 1),
            transport=transport,
            sleeper=waits.append,
            rng=rng,
            max_retries=3,
            backoff_seconds=20,
        )
        raise AssertionError("expected ArchiveFetchError")
    except ArchiveFetchError as exc:
        assert exc.http_status == 500
        assert exc.attempts == 3
    assert waits == [20.0, 40.0]


def test_resume_does_not_request_cached_locations(tmp_path, monkeypatch):
    import json
    from services import flood_weather_history as mod

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    loc = {
        "location_id": "district_centroid:bo",
        "location_name": "Bo",
        "location_type": "district_centroid",
        "district": "bo",
        "latitude": 7.9647,
        "longitude": -11.7383,
        "source": "test",
        "coordinate_quality": "admin_centroid_fallback",
        "coordinate_ok": True,
    }
    cached = _ok_payload(["2015-08-01", "2015-08-02"], [1.0, 2.0])
    (tmp_path / "district_centroid_bo.json").write_text(json.dumps(cached), encoding="utf-8")
    calls = []

    def transport(url, _timeout):
        calls.append(url)
        raise AssertionError(f"cached location was requested: {url}")

    payload = mod.build_dataset(
        start=date(2015, 8, 1),
        end=date(2015, 8, 2),
        locations=[loc],
        reuse_raw=True,
        live_fetch=True,
        persist_raw=False,
        transport=transport,
        sleep_seconds=0,
    )
    assert calls == []
    assert payload["extracts"][0]["from_cache"] is True
    assert payload["rows"][0]["coordinate_quality"] == "admin_centroid_fallback"
    assert payload["quality"]["n_fetch_failures"] == 0


def test_request_throttling_is_serialized_between_live_fetches():
    import json
    from services.flood_weather_history import build_dataset

    waits = []
    urls = []

    def transport(url, _timeout):
        urls.append(url)
        body = json.dumps(_ok_payload(["2015-08-01"], [0.0]))
        return 200, body.encode(), {}

    locs = [
        {
            "location_id": "district_centroid:bo",
            "location_name": "Bo",
            "location_type": "district_centroid",
            "district": "bo",
            "latitude": 7.9647,
            "longitude": -11.7383,
            "source": "test",
            "coordinate_quality": "admin_centroid_fallback",
            "coordinate_ok": True,
        },
        {
            "location_id": "district_centroid:kenema",
            "location_name": "Kenema",
            "location_type": "district_centroid",
            "district": "kenema",
            "latitude": 7.8767,
            "longitude": -11.1903,
            "source": "test",
            "coordinate_quality": "admin_centroid_fallback",
            "coordinate_ok": True,
        },
    ]
    payload = build_dataset(
        start=date(2015, 8, 1),
        end=date(2015, 8, 1),
        locations=locs,
        reuse_raw=False,
        live_fetch=True,
        persist_raw=False,
        transport=transport,
        sleeper=waits.append,
        sleep_seconds=3.5,
        max_retries=1,
    )
    assert len(urls) == 2
    assert waits == [3.5]
    assert payload["quality"]["n_rows"] == 2


def test_failed_location_stays_missing_without_zero_or_substitution():
    import json
    from services.flood_weather_history import build_dataset

    def transport(url, _timeout):
        if "7.9647" in url:
            return 429, b"rate limited", {}
        body = json.dumps(_ok_payload(["2015-08-01"], [4.0]))
        return 200, body.encode(), {}

    locs = [
        {
            "location_id": "district_centroid:bo",
            "location_name": "Bo",
            "location_type": "district_centroid",
            "district": "bo",
            "latitude": 7.9647,
            "longitude": -11.7383,
            "source": "test",
            "coordinate_quality": "admin_centroid_fallback",
            "coordinate_ok": True,
        },
        {
            "location_id": "zone:kroo_bay",
            "location_name": "Kroo Bay",
            "location_type": "flood_zone",
            "district": "western_area_urban",
            "latitude": 8.4892,
            "longitude": -13.2387,
            "source": "test",
            "coordinate_quality": "catalog_point",
            "coordinate_ok": True,
        },
    ]
    payload = build_dataset(
        start=date(2015, 8, 1),
        end=date(2015, 8, 1),
        locations=locs,
        reuse_raw=False,
        persist_raw=False,
        transport=transport,
        sleeper=lambda _s: None,
        sleep_seconds=0,
        max_retries=2,
        backoff_seconds=1,
        rng=type("R", (), {"uniform": staticmethod(lambda a, b: 0.0)})(),
    )
    ids = {r["location_id"] for r in payload["rows"]}
    assert ids == {"zone:kroo_bay"}
    assert payload["rows"][0]["precipitation_mm"] == 4.0
    assert payload["rows"][0]["latitude"] == 8.4892
    fail = payload["fetch_failures"][0]
    assert fail["location_id"] == "district_centroid:bo"
    assert fail["http_status"] == 429
    assert fail["attempts"] >= 1
    assert fail["timestamp"]
    assert payload["quality"]["missing_not_replaced_with_zero"] is True
    assert "flood_occurred" not in payload["rows"][0]


def test_complete_daily_series_validation():
    from services.flood_weather_history import payload_to_daily_rows, validate_location_series

    loc = {
        "location_id": "zone:kroo_bay",
        "location_name": "Kroo Bay",
        "location_type": "flood_zone",
        "coordinate_quality": "catalog_point",
        "district": "western_area_urban",
        "latitude": 8.4892,
        "longitude": -13.2387,
    }
    payload = _ok_payload(["2015-01-01", "2015-01-02", "2015-01-03"], [0.0, None, 2.0])
    rows = payload_to_daily_rows(loc, payload, date(2015, 1, 1), date(2015, 1, 3))
    result = validate_location_series(rows, loc, date(2015, 1, 1), date(2015, 1, 3))
    assert result["ok"] is True
    assert result["n_rows"] == 3
    assert rows[1]["precipitation_mm"] is None
    assert rows[0]["precipitation_mm"] == 0.0
    assert rows[0]["coordinate_quality"] == "catalog_point"


def test_geographic_grains_are_not_merged():
    locations = load_canonical_locations()
    zones = [loc for loc in locations if loc["location_type"] == "flood_zone"]
    cents = [loc for loc in locations if loc["location_type"] == "district_centroid"]
    assert {z["coordinate_quality"] for z in zones} == {"catalog_point"}
    assert {c["coordinate_quality"] for c in cents} == {"admin_centroid_fallback"}
    assert {z["location_type"] for z in zones}.isdisjoint({c["location_type"] for c in cents})


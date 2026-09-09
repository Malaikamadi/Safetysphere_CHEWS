"""
DHIS2 client, parsing, quality, org-unit mapping, and pipeline tests.

Run from backend/:
    pip install -r requirements.txt -r requirements-dev.txt
    python -m pytest tests/test_dhis2.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def analytics_sample():
    return json.loads((BACKEND / "data/01_raw/dhis2/mock/analytics_sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def org_units_sample():
    return json.loads((BACKEND / "data/01_raw/dhis2/mock/organisation_units_sample.json").read_text(encoding="utf-8"))


def test_config_no_secrets_in_public_status(monkeypatch):
    from config import dhis2 as cfg
    monkeypatch.setattr(cfg, "DHIS2_USERNAME", "secret-user")
    monkeypatch.setattr(cfg, "DHIS2_PASSWORD", "secret-pass")
    monkeypatch.setattr(cfg, "DHIS2_MOCK_MODE", True)
    monkeypatch.setattr(cfg, "DHIS2_API_TOKEN", None)
    status = cfg.public_status()
    dumped = json.dumps(status)
    assert "secret-user" not in dumped
    assert "secret-pass" not in dumped
    assert status["auth_method"] == "mock"
    assert status["core_indicators"]["malaria_confirmed"] == "XHQqFqfUfIf"
    assert "treatment_within_24h" in status["supporting_indicators"]


def test_credentials_incomplete_without_mock(monkeypatch):
    from config import dhis2 as cfg
    from services.dhis2_service import Dhis2AuthError, Dhis2Client
    monkeypatch.setattr(cfg, "DHIS2_MOCK_MODE", False)
    monkeypatch.setattr(cfg, "DHIS2_USERNAME", None)
    monkeypatch.setattr(cfg, "DHIS2_PASSWORD", None)
    monkeypatch.setattr(cfg, "DHIS2_API_TOKEN", None)
    client = Dhis2Client(mock=False)
    with pytest.raises(Dhis2AuthError):
        client.fetch_analytics()


def test_parse_analytics_required_fixture(analytics_sample):
    from services.dhis2_service import parse_analytics_rows
    rows = parse_analytics_rows(analytics_sample)
    confirmed = next(
        r for r in rows
        if r["indicator_id"] == "XHQqFqfUfIf" and r["period"] == "202509" and r["org_unit_id"] == "dar4XkzRmN0"
    )
    u5 = next(
        r for r in rows
        if r["indicator_id"] == "tjRoHuika9k" and r["period"] == "202509" and r["org_unit_id"] == "dar4XkzRmN0"
    )
    assert confirmed["value"] == 144
    assert u5["value"] == 100


def test_parse_malformed_rows():
    from services.dhis2_service import Dhis2ParseError, parse_analytics_rows
    with pytest.raises(Dhis2ParseError):
        parse_analytics_rows(None)
    with pytest.raises(Dhis2ParseError):
        parse_analytics_rows({"not_rows": []})
    with pytest.raises(Dhis2ParseError):
        parse_analytics_rows({"rows": "bad"})
    with pytest.raises(Dhis2ParseError):
        parse_analytics_rows({"rows": [["too", "short"]]})


def test_empty_data():
    from services.dhis2_service import parse_analytics_rows
    rows = parse_analytics_rows({"rows": []})
    assert rows == []
    from services.dhis2_pipeline import validate_records
    report = validate_records([], [])
    assert report["record_count"] == 0
    assert any(i["code"] == "empty_extract" for i in report["issues_truncated"])


def test_numeric_conversion_and_missing_not_zero():
    from services.dhis2_service import parse_analytics_rows, parse_numeric
    assert parse_numeric("144") == 144
    assert parse_numeric(144) == 144.0
    assert parse_numeric("") is None
    assert parse_numeric(None) is None
    assert parse_numeric("n/a") is None
    assert parse_numeric("not-a-number") is None
    rows = parse_analytics_rows({
        "rows": [
            ["XHQqFqfUfIf", "202509", "dar4XkzRmN0", ""],
            ["XHQqFqfUfIf", "202509", "other", "abc"],
        ]
    })
    assert rows[0]["value"] is None
    assert rows[0]["invalid_numeric"] is False
    assert rows[1]["value"] is None
    assert rows[1]["invalid_numeric"] is True


def test_http_error_mapped(monkeypatch):
    from services.dhis2_service import Dhis2Client, Dhis2HttpError
    import io
    import urllib.error

    def _boom(*args, **kwargs):
        raise urllib.error.HTTPError("http://x", 500, "err", hdrs=None, fp=io.BytesIO())

    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_MOCK_MODE", False)
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_USERNAME", "u")
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_PASSWORD", "p")
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_API_TOKEN", None)
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_RETRIES", 1)
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    client = Dhis2Client(mock=False)
    with pytest.raises(Dhis2HttpError) as exc:
        client.fetch_analytics()
    assert exc.value.status_code == 500


def test_auth_http_401(monkeypatch):
    from services.dhis2_service import Dhis2AuthError, Dhis2Client
    import io
    import urllib.error

    def _boom(*args, **kwargs):
        raise urllib.error.HTTPError("http://x", 401, "no", hdrs=None, fp=io.BytesIO())

    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_USERNAME", "u")
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_PASSWORD", "p")
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_API_TOKEN", None)
    monkeypatch.setattr("services.dhis2_service.cfg.DHIS2_RETRIES", 1)
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    client = Dhis2Client(mock=False)
    with pytest.raises(Dhis2AuthError):
        client.fetch_analytics()


def test_coordinate_conversion_lon_lat():
    from services.dhis2_service import parse_coordinates
    lon, lat, geom = parse_coordinates({"type": "Point", "coordinates": [-13.28778, 8.49314]})
    assert lon == pytest.approx(-13.28778)
    assert lat == pytest.approx(8.49314)
    assert geom["type"] == "Point"
    lon2, lat2, _ = parse_coordinates(None)
    assert lon2 is None and lat2 is None
    lon3, lat3, raw = parse_coordinates({"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]})
    assert lon3 is None and lat3 is None
    assert raw["type"] == "Polygon"


def test_org_unit_hierarchy(org_units_sample):
    from services.dhis2_orgunits import map_organisation_units
    from services.dhis2_service import parse_org_unit_payload
    units = parse_org_unit_payload(org_units_sample)
    mapped = map_organisation_units(units)
    hospital = next(u for u in mapped if u["dhis2_org_unit_id"] == "dar4XkzRmN0")
    assert hospital["display_name"] == "Aberdeen Women Centre Hospital"
    assert hospital["level"] == 5
    assert hospital["zone_id"] == "RqcjKMD6wRN"
    assert hospital["zone_name"] == "West 3 Zone"
    assert hospital["council_id"] == "wlDW6S0pHLL"
    assert hospital["council_name"] == "Freetown City Council"
    assert hospital["district_id"] == "PMLlCzM0mWT"
    assert hospital["district_name"] == "Western Area Urban District"
    assert hospital["longitude"] == pytest.approx(-13.28778)
    assert hospital["latitude"] == pytest.approx(8.49314)
    assert hospital["is_facility_level"] is True


def test_unmapped_facility_flagged():
    from services.dhis2_orgunits import map_organisation_units
    units = [
        {"id": "ImspTQPwCqd", "displayName": "Sierra Leone", "level": 1, "parent": None},
        {
            "id": "zzzzNotInMFL",
            "displayName": "Unknown Post",
            "level": 5,
            "parent": {"id": "ImspTQPwCqd", "displayName": "Sierra Leone", "level": 1},
        },
    ]
    mapped = map_organisation_units(units)
    unknown = next(u for u in mapped if u["dhis2_org_unit_id"] == "zzzzNotInMFL")
    assert unknown["mfl_mapped"] is False
    assert unknown["unmapped"] is True
    assert unknown["mfl_facility_id"] is None


def test_duplicate_handling():
    from services.dhis2_pipeline import validate_records
    records = [
        {"indicator_id": "XHQqFqfUfIf", "period": "202509", "org_unit_id": "dar4XkzRmN0", "value": 144, "invalid_numeric": False},
        {"indicator_id": "XHQqFqfUfIf", "period": "202509", "org_unit_id": "dar4XkzRmN0", "value": 144, "invalid_numeric": False},
    ]
    report = validate_records(records, [])
    assert report["duplicates"] == 1


def test_pipeline_mock_ingest(tmp_path, monkeypatch):
    from config import dhis2 as cfg
    monkeypatch.setattr(cfg, "RAW_DHIS2_DIR", tmp_path / "01_raw" / "dhis2")
    monkeypatch.setattr(cfg, "STAGING_DHIS2_DIR", tmp_path / "02_staging" / "dhis2")
    monkeypatch.setattr(cfg, "CURATED_SURVEILLANCE_DIR", tmp_path / "03_curated" / "surveillance")
    monkeypatch.setattr(cfg, "AI_FEATURES_DIR", tmp_path / "04_ai" / "features")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)

    from services.dhis2_pipeline import ingest, live_case_overlay, risk_engine_inputs_from_dhis2
    from services.dhis2_service import Dhis2Client

    result = ingest(client=Dhis2Client(mock=True), persist=True)
    wide = result["wide"]
    row = next(r for r in wide if r["period"] == "202509" and r["org_unit_id"] == "dar4XkzRmN0")
    assert row["malaria_confirmed"] == 144
    assert row["malaria_confirmed_u5"] == 100
    feat = next(f for f in result["features"] if f["period"] == "202509")
    assert feat["lag1_malaria_confirmed"] == 130
    assert feat["delta_malaria_confirmed"] == 14
    overlay = live_case_overlay("national")
    assert overlay["current_cases"] == 144
    mapped = risk_engine_inputs_from_dhis2("national")
    assert mapped["reported_cases"] == 144
    assert mapped["trend"] == "increasing"
    assert (tmp_path / "01_raw" / "dhis2" / "analytics").exists()


def test_percent_indicator_not_forced_into_wide(analytics_sample):
    from services.dhis2_pipeline import build_long_rows, build_wide_table
    from services.dhis2_service import parse_analytics_rows
    records = parse_analytics_rows(analytics_sample)
    records.append({
        "indicator_id": "MM7wnFwsi7q",
        "period": "202509",
        "org_unit_id": "dar4XkzRmN0",
        "value": 12.5,
        "invalid_numeric": False,
    })
    long_rows = build_long_rows(records, [{
        "dhis2_org_unit_id": "dar4XkzRmN0",
        "display_name": "Aberdeen Women Centre Hospital",
        "mfl_facility_name": "Aberdeen Women Centre Hospital",
        "level": 5,
        "district_id": "PMLlCzM0mWT",
        "district_name": "Western Area Urban District",
        "mfl_district": "Western Area Urban",
        "council_id": "wlDW6S0pHLL",
        "council_name": "Freetown City Council",
        "zone_id": "RqcjKMD6wRN",
        "zone_name": "West 3 Zone",
        "latitude": 8.49314,
        "longitude": -13.28778,
        "mfl_mapped": True,
        "unmapped": False,
    }], source="test", ingested_at="t")
    wide = build_wide_table(long_rows)
    assert "child_malaria_death" not in wide[0]
    assert any(r["indicator_id"] == "MM7wnFwsi7q" for r in long_rows)

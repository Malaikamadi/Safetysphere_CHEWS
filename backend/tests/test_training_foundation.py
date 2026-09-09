"""
Historical DHIS2 extract, Open-Meteo Archive climate, and training-readiness tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


def test_explicit_monthly_window_not_last_5_years():
    from services.dhis2_periods import expand_monthly_range, historical_window
    months = expand_monthly_range("202301", "202303")
    assert months == ["202301", "202302", "202303"]
    start, end, tokens = historical_window(start="202309", end="202608", months=36)
    assert start == "202309"
    assert end == "202608"
    assert len(tokens) == 36
    assert "LAST_5_YEARS" not in tokens
    assert all(len(t) == 6 and t.isdigit() for t in tokens)


def test_yyyymm_to_date_bounds():
    from services.dhis2_periods import yyyymm_to_date_bounds
    assert yyyymm_to_date_bounds("202508", "202509") == ("2025-08-01", "2025-09-30")
    assert yyyymm_to_date_bounds("202402", "202402") == ("2024-02-01", "2024-02-29")


def test_district_slug_aliases():
    from services.district_names import district_slug
    assert district_slug("Western Area Urban District") == "western_area_urban"
    assert district_slug("Western Urban") == "western_area_urban"
    assert district_slug("Port Loko") == "port_loko"


def test_historical_mock_extract_is_not_enough(tmp_path, monkeypatch):
    from config import dhis2 as cfg
    monkeypatch.setattr(cfg, "RAW_DHIS2_HISTORICAL_DIR", tmp_path / "historical")
    monkeypatch.setattr(cfg, "STAGING_DHIS2_DIR", tmp_path / "staging")
    monkeypatch.setattr(cfg, "CURATED_DISTRICT_MONTH_DIR", tmp_path / "curated")

    from services.dhis2_historical import extract_historical
    from services.dhis2_service import Dhis2Client

    result = extract_historical(
        client=Dhis2Client(mock=True),
        start="202309",
        end="202608",
        persist=True,
    )
    assert result["mock"] is True
    assert result["prototype_gbt"]["connected"] is False
    assert result["indicator_keys"] == [
        "malaria_confirmed", "malaria_confirmed_u5", "malaria_tests", "malaria_rdt_positive",
    ]
    completeness = result["completeness"]
    assert completeness["requested_month_count"] == 36
    assert completeness["observed_month_count"] == 2
    assert completeness["district_count"] == 1
    dm = result["district_month"]
    sep = next(r for r in dm if r["source_period"] == "202509")
    assert sep["malaria_confirmed"] == 144
    assert sep["district_slug"] == "western_area_urban"


def test_district_month_aggregation_sums_non_null_only():
    from services.dhis2_historical import aggregate_district_month
    wide = [
        {
            "source_period": "202509", "period": "202509", "period_type": "monthly",
            "org_unit_id": "a", "district_name": "Bo", "district_id": "bo-id",
            "malaria_confirmed": 10, "malaria_confirmed_u5": 4,
            "malaria_tests": 20, "malaria_rdt_positive": 8,
        },
        {
            "source_period": "202509", "period": "202509", "period_type": "monthly",
            "org_unit_id": "b", "district_name": "Bo", "district_id": "bo-id",
            "malaria_confirmed": 5, "malaria_confirmed_u5": None,
            "malaria_tests": None, "malaria_rdt_positive": 2,
        },
        {
            "source_period": "202509", "period": "202509", "period_type": "monthly",
            "org_unit_id": "c", "district_name": "Bo", "district_id": "bo-id",
            "malaria_confirmed": None, "malaria_confirmed_u5": None,
            "malaria_tests": None, "malaria_rdt_positive": None,
        },
    ]
    expected = {"bo": {"expected_facilities": 3, "district_id": "bo-id"}}
    rows = aggregate_district_month(wide, expected)
    assert len(rows) == 1
    assert rows[0]["malaria_confirmed"] == 15
    assert rows[0]["malaria_confirmed_u5"] == 4
    assert rows[0]["malaria_tests"] == 20
    assert rows[0]["malaria_rdt_positive"] == 10
    assert rows[0]["reporting_facilities"] == 2
    assert rows[0]["completeness"] == pytest.approx(2 / 3)


def test_climate_daily_to_monthly():
    from services.climate_archive import aggregate_daily_to_monthly
    monthly = aggregate_daily_to_monthly(
        dates=["2025-08-01", "2025-08-02", "2025-09-01"],
        precipitation=[10.0, 5.0, 3.0],
        temperature=[26.0, 28.0, 27.0],
        humidity=[80.0, 90.0, 70.0],
    )
    assert monthly["202508"]["rainfall_mm"] == 15.0
    assert monthly["202508"]["temperature_c"] == pytest.approx(27.0)
    assert monthly["202508"]["humidity_percent"] == pytest.approx(85.0)
    assert monthly["202509"]["rainfall_mm"] == 3.0


def test_climate_mock_fixture_does_not_touch_realtime(tmp_path, monkeypatch):
    from config import climate_archive as clim_cfg
    monkeypatch.setattr(clim_cfg, "CURATED_CLIMATE_DIR", tmp_path / "climate")
    from services.climate_archive import ingest_historical_climate
    result = ingest_historical_climate(start="202508", end="202509", mock=True, persist=True)
    assert result["mock"] is True
    assert result["realtime_weather_untouched"] is True
    assert result["source"] == "open_meteo_archive_mock"
    periods = {r["source_period"] for r in result["district_month"]}
    assert periods == {"202508", "202509"}


def test_mock_panel_is_not_ready_for_training(tmp_path, monkeypatch):
    from config import dhis2 as cfg
    from config import climate_archive as clim_cfg
    monkeypatch.setattr(cfg, "RAW_DHIS2_HISTORICAL_DIR", tmp_path / "historical")
    monkeypatch.setattr(cfg, "STAGING_DHIS2_DIR", tmp_path / "staging")
    monkeypatch.setattr(cfg, "CURATED_DISTRICT_MONTH_DIR", tmp_path / "curated")
    monkeypatch.setattr(cfg, "AI_TRAINING_SETS_DIR", tmp_path / "training_sets")
    monkeypatch.setattr(clim_cfg, "CURATED_CLIMATE_DIR", tmp_path / "climate")

    from services.dhis2_service import Dhis2Client
    from services.training_panel import NOT_READY, build_training_panel

    result = build_training_panel(
        dhis2_client=Dhis2Client(mock=True),
        climate_mock=True,
        start="202309",
        end="202608",
        persist=False,
    )
    assert result["verdict"] == NOT_READY
    assert result["readiness"]["ready"] is False
    assert "live_dhis2" in result["readiness"]["blocking_checks"]
    assert "min_observed_months" in result["readiness"]["blocking_checks"]
    assert result["readiness"]["prototype_gbt"]["connected_to_this_panel"] is False
    assert result["readiness"]["target"] == "malaria_confirmed_next"


def test_readiness_true_only_on_live_aligned_panel():
    from services.district_names import ADMIN_DISTRICTS, district_slug
    from services.dhis2_periods import expand_monthly_range
    from services.training_panel import (
        READY,
        assess_training_readiness,
        engineer_training_features,
        join_district_month,
    )

    months = expand_monthly_range("202301", "202512")
    assert len(months) == 36
    health, climate = [], []
    for name in ADMIN_DISTRICTS:
        slug = district_slug(name)
        for i, period in enumerate(months):
            health.append({
                "source_period": period,
                "district_slug": slug,
                "district_name": name,
                "malaria_confirmed": 20 + i,
                "malaria_confirmed_u5": 8,
                "malaria_tests": 40,
                "malaria_rdt_positive": 15,
            })
            climate.append({
                "source_period": period,
                "district_slug": slug,
                "district_name": name,
                "rainfall_mm": 120.0,
                "temperature_c": 27.0,
                "humidity_percent": 80.0,
                "source": "open_meteo_archive",
            })
    features = engineer_training_features(join_district_month(health, climate))
    readiness = assess_training_readiness(
        features,
        health_source="dhis2_live",
        climate_source="open_meteo_archive",
        mock_health=False,
        mock_climate=False,
        requested_months=months,
    )
    assert readiness["verdict"] == READY
    assert readiness["trainable_rows"] >= 200
    sample = next(r for r in features if r["trainable"])
    assert sample["malaria_confirmed_next"] is not None
    assert sample["lag1_malaria_confirmed"] is not None


def test_training_panel_does_not_import_malaria_predictor():
    import services.training_panel as mod
    assert "malaria_predictor" not in getattr(mod, "__dict__", {})
    assert not hasattr(mod, "malaria_predictor")

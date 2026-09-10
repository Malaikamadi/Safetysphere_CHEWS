"""Isolated malaria anomaly shadow pilot — no CHEWS integration, no training."""

from __future__ import annotations

import pytest

from services.malaria_anomaly_shadow import (
    CONTEXT_A,
    CONTEXT_C,
    CONTEXT_D,
    CONTEXT_E,
    SHADOW_GATE_PP,
    build_shadow_pilot,
)


def _row(slug, period, confirmed, tests, completeness=0.5, **extra):
    payload = {
        "district_slug": slug,
        "district_name": slug,
        "source_period": period,
        "malaria_confirmed": confirmed,
        "malaria_tests": tests,
        "malaria_confirmed_u5": extra.pop("malaria_confirmed_u5", None),
        "malaria_rdt_positive": extra.pop("malaria_rdt_positive", None),
        "facility_completeness": completeness,
        "rainfall_mm": 100.0,
        "temperature_c": 27.0,
        "humidity_percent": 80.0,
    }
    payload.update(extra)
    return payload


def _years(slug, month, confirmed_by_year, tests=5000, completeness=0.5):
    return [
        _row(slug, f"{year}{month:02d}", confirmed, tests, completeness)
        for year, confirmed in confirmed_by_year.items()
    ]


def test_shadow_gate_is_plus_three_pp_policy_not_learned():
    assert SHADOW_GATE_PP == 3.0


def test_shadow_past_only_baseline_and_district_calendar_month_grouping():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 4000})
    expansion += _years("kenema", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2500})
    payload = build_shadow_pilot(expansion, [])
    bo = next(r for r in payload["records"] if r["district_slug"] == "bo" and r["current_period"] == "202406")
    kenema = next(r for r in payload["records"] if r["district_slug"] == "kenema" and r["current_period"] == "202406")
    assert bo["baseline_years_used"] == ["2021", "2022", "2023"]
    assert bo["baseline_observation_count"] == 3
    assert all(p[4:6] == "06" for p in bo["baseline_periods"])
    assert all(p < "202406" for p in bo["baseline_periods"])
    assert "202406" not in bo["baseline_periods"]
    assert "202506" not in bo["baseline_periods"]
    assert bo["anomaly_flag"] is True
    assert kenema["anomaly_flag"] is False
    assert payload["audit"]["leakage_audit"]["passed"] is True


def test_shadow_rejects_future_year_in_baseline():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2500, 2025: 4000})
    payload = build_shadow_pilot(expansion, [])
    june_2024 = next(r for r in payload["records"] if r["current_period"] == "202406")
    june_2025 = next(r for r in payload["records"] if r["current_period"] == "202506")
    assert "2025" not in june_2024["baseline_years_used"]
    assert june_2025["baseline_years_used"] == ["2021", "2022", "2023", "2024"]
    assert june_2024["is_forecast"] is False
    assert june_2024["is_ai"] is False
    assert june_2024["is_outbreak_label"] is False


def test_shadow_plus_3pp_gate():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2640})  # +2.8 pp
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert row["deviation_pp"] == pytest.approx(2.8)
    assert row["anomaly_flag"] is False
    expansion2 = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2660})  # +3.2 pp
    payload2 = build_shadow_pilot(expansion2, [])
    row2 = next(r for r in payload2["records"] if r["current_period"] == "202406")
    assert row2["deviation_pp"] == pytest.approx(3.2)
    assert row2["anomaly_flag"] is True
    assert row2["gate_threshold_pp"] == 3.0


def test_shadow_zero_tests_is_data_quality_not_zero_positivity():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500})
    expansion.append(_row("bo", "202406", 4000, 0, 0.5))
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert row["positivity"] is None
    assert row["anomaly_flag"] is False
    assert row["data_quality_status"] == "data_quality_issue"
    assert "tests_not_positive" in row["data_quality_reasons"]


def test_shadow_low_completeness_blocks_anomaly():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500})
    expansion.append(_row("bo", "202406", 4000, 5000, 0.05))
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert row["anomaly_flag"] is False
    assert "low_completeness" in row["data_quality_reasons"]
    assert row["context_class"] == CONTEXT_D


def test_shadow_missing_current_month_placeholder():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2500})
    payload = build_shadow_pilot(expansion, [])
    july = next(r for r in payload["records"] if r["district_slug"] == "bo" and r["current_period"] == "202407")
    assert july["malaria_confirmed"] is None
    assert july["positivity"] is None
    assert july["anomaly_flag"] is False
    assert july["data_quality_status"] == "no_observation"
    assert "missing_observation" in july["data_quality_reasons"]
    assert july["context_class"] == CONTEXT_D


def test_shadow_insufficient_baseline():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 4000})
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202306")
    assert row["baseline_observation_count"] == 2
    assert row["anomaly_flag"] is False
    assert row["data_quality_status"] == "insufficient_history"


def test_shadow_testing_down_and_confirmed_support_classes():
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500})
    expansion.append(_row("bo", "202406", 4000, 3000, 0.5))
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert row["anomaly_flag"] is True
    assert row["confirmed_change_context"] == "increasing"
    assert row["context_class"] == CONTEXT_A

    expansion_c = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500})
    expansion_c.append(_row("bo", "202406", 2400, 3000, 0.5))
    payload_c = build_shadow_pilot(expansion_c, [])
    row_c = next(r for r in payload_c["records"] if r["current_period"] == "202406")
    assert row_c["anomaly_flag"] is True
    assert row_c["testing_change_context"] == "decreasing"
    assert row_c["context_class"] == CONTEXT_C


def test_shadow_unsupported_positivity_is_class_e():
    # Tests drop <15% so this is not a testing-down artifact; confirmed unchanged.
    expansion = _years("bo", 6, {2021: 2500, 2022: 2500, 2023: 2500})
    expansion.append(_row("bo", "202406", 2500, 4545, 0.5))
    payload = build_shadow_pilot(expansion, [])
    row = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert row["anomaly_flag"] is True
    assert row["confirmed_change_context"] == "unchanged"
    assert row["testing_change_context"] == "unchanged"
    assert row["context_class"] == CONTEXT_E


def test_shadow_sustained_anomaly_calendar_consecutive():
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
        _row("bo", "202410", 4000, 5000),
    ])
    payload = build_shadow_pilot(expansion, [])
    june = next(r for r in payload["records"] if r["current_period"] == "202406")
    july = next(r for r in payload["records"] if r["current_period"] == "202407")
    august = next(r for r in payload["records"] if r["current_period"] == "202408")
    october = next(r for r in payload["records"] if r["current_period"] == "202410")
    assert june["consecutive_anomaly_months"] == 1
    assert june["sustained_anomaly"] is False
    assert july["consecutive_anomaly_months"] == 2
    assert july["sustained_anomaly"] is True
    assert august["consecutive_anomaly_months"] == 3
    assert october["consecutive_anomaly_months"] == 1
    assert october["sustained_anomaly"] is False


def test_incomplete_period_demotes_anomaly_on_national_panel():
    slugs = [
        "bo", "kenema", "kono", "pujehun", "bonthe", "kailahun", "moyamba", "tonkolili",
        "bombali", "port_loko", "kambia", "karene", "koinadugu", "falaba",
        "western_area_urban", "western_area_rural",
    ]
    expansion = []
    for slug in slugs:
        expansion += _years(slug, 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2500})
    # Bo has a full July history so 202407 would otherwise pass the +3 pp gate.
    expansion += _years("bo", 7, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 4000})
    payload = build_shadow_pilot(expansion, [])
    july = next(
        r for r in payload["records"]
        if r["district_slug"] == "bo" and r["current_period"] == "202407"
    )
    assert july["anomaly_flag"] is False
    assert "incomplete_period" in july["data_quality_reasons"]
    assert july["context_class"] == CONTEXT_D
    assert "202407" in payload["audit"]["incomplete_periods"]


def test_shadow_does_not_pool_pre_comparable_era():
    expansion = [_row("bo", "202105", 9999, 10000)] + _years(
        "bo", 6, {2021: 2500, 2022: 2500, 2023: 2500, 2024: 2500}
    )
    payload = build_shadow_pilot(expansion, [])
    june = next(r for r in payload["records"] if r["current_period"] == "202406")
    assert "202105" not in june["baseline_periods"]
    assert all(p >= "202106" for p in june["baseline_periods"])
    assert payload["audit"]["model_trained"] is False
    assert payload["audit"]["integrated_into_chews"] is False
    assert payload["audit"]["notifications_sent"] is False

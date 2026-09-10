"""Past-only seasonal malaria positivity anomaly — no training, no CHEWS integration."""

from __future__ import annotations

import pytest

from services.malaria_anomaly import (
    COMPARABLE_START,
    MIN_PRIOR_YEARS_PRIMARY,
    anomaly_measures,
    audit_no_future_in_baselines,
    expanding_baselines,
    leakage_check,
    load_comparable_panel,
    positivity,
    prior_same_month_rows,
    score_observation,
    score_panel,
)


def _row(slug, period, confirmed, tests, completeness=0.5, **extra):
    payload = {
        "district_slug": slug,
        "district_name": slug,
        "source_period": period,
        "malaria_confirmed": confirmed,
        "malaria_tests": tests,
        "facility_completeness": completeness,
        "rainfall_mm": extra.pop("rainfall_mm", 100.0),
        "temperature_c": extra.pop("temperature_c", 27.0),
        "humidity_percent": extra.pop("humidity_percent", 80.0),
    }
    payload.update(extra)
    return payload


def test_positivity_only_when_tests_positive():
    assert positivity(50, 100) == 0.5
    assert positivity(50, 0) is None
    assert positivity(50, None) is None
    assert positivity(None, 100) is None
    assert positivity(50, -1) is None


def test_load_comparable_panel_drops_pre_era_and_prefers_v1():
    expansion = [
        _row("bo", "202105", 10, 20),  # pre-comparable
        _row("bo", "202106", 30, 60),
        _row("bo", "202206", 40, 80),
    ]
    v1 = [
        _row("bo", "202206", 99, 100),  # overlap: v1 wins
        _row("kenema", "202307", 10, 20),
    ]
    panel = load_comparable_panel(expansion, v1)
    periods = {(r["district_slug"], r["source_period"]) for r in panel}
    assert ("bo", "202105") not in periods
    assert all(r["source_period"] >= COMPARABLE_START for r in panel)
    bo_202206 = next(r for r in panel if r["source_period"] == "202206" and r["district_slug"] == "bo")
    assert bo_202206["malaria_confirmed"] == 99
    assert bo_202206["panel_source"] == "v1_reference"


def test_prior_same_month_excludes_current_future_and_other_months():
    rows = load_comparable_panel(
        [
            _row("bo", "202106", 10, 20),
            _row("bo", "202107", 99, 100),
            _row("bo", "202206", 12, 20),
            _row("bo", "202306", 14, 20),
            _row("bo", "202307", 15, 20),
            _row("kenema", "202206", 50, 50),
        ],
        [],
    )
    index = {(r["district_slug"], r["source_period"]): r for r in rows}
    prior = prior_same_month_rows(index, "bo", "202306")
    periods = [r["source_period"] for r in prior]
    assert periods == ["202106", "202206"]
    assert "202306" not in periods
    assert "202307" not in periods
    assert "202107" not in periods
    assert all(r["district_slug"] == "bo" for r in prior)


def test_leakage_check_rejects_future_and_other_groups():
    current = "202406"
    ok = leakage_check(current, [_row("bo", "202106", 1, 2), _row("bo", "202306", 1, 2)], "bo")
    assert ok["passed"] is True
    bad_future = leakage_check(current, [_row("bo", "202506", 1, 2)], "bo")
    assert bad_future["passed"] is False
    bad_month = leakage_check(current, [_row("bo", "202307", 1, 2)], "bo")
    assert bad_month["passed"] is False
    bad_district = leakage_check(current, [_row("kenema", "202306", 1, 2)], "bo")
    assert bad_district["passed"] is False


def test_insufficient_history_when_fewer_than_three_prior_years():
    rows = load_comparable_panel(
        [
            _row("bo", "202106", 50, 100),
            _row("bo", "202206", 50, 100),
            _row("bo", "202306", 80, 100),
        ],
        [],
    )
    index = {(r["district_slug"], r["source_period"]): r for r in rows}
    scored = score_observation(index[("bo", "202306")], index)
    assert scored["n_prior"] == 2
    assert scored["n_prior"] < MIN_PRIOR_YEARS_PRIMARY
    assert scored["insufficient_history"] is True
    assert scored["primary_eligible"] is False
    assert scored["conventional_alert"] is False


def test_expanding_baseline_ignores_current_observation():
    prior = [0.50, 0.52, 0.54]
    base = expanding_baselines(prior)
    measures = anomaly_measures(0.90, base)
    assert base["expanding_median"] == pytest.approx(0.52)
    assert measures["robust_z"] is not None
    assert measures["robust_z"] > 2
    # If current 0.90 had leaked into the median, median would be 0.53 and z would shrink.
    leaked = expanding_baselines(prior + [0.90])
    assert leaked["expanding_median"] == pytest.approx(0.53)


def test_score_panel_is_chronological_and_leakage_free():
    expansion = []
    for year in (2021, 2022, 2023, 2024, 2025):
        expansion.append(_row("bo", f"{year}06", 50 + year - 2021, 100))
        expansion.append(_row("bo", f"{year}07", 40, 100))
    rows = load_comparable_panel(expansion, [])
    scored = score_panel(rows)
    june_2025 = next(r for r in scored if r["source_period"] == "202506")
    assert june_2025["baseline_periods"] == ["202106", "202206", "202306", "202406"]
    assert june_2025["max_baseline_period"] == "202406"
    assert all(p < "202506" for p in june_2025["baseline_periods"])
    assert june_2025["n_prior"] == 4
    assert june_2025["primary_eligible"] is True
    audit = audit_no_future_in_baselines(scored)
    assert audit["passed"] is True
    assert all(r.get("lead1_rainfall_mm") is None for r in scored)


def test_full_dataset_mean_is_not_used():
    """A later extreme year must not change an earlier baseline."""
    expansion = [
        _row("bo", "202106", 48, 100),
        _row("bo", "202206", 50, 100),
        _row("bo", "202306", 52, 100),
        _row("bo", "202406", 50, 100),
        _row("bo", "202506", 99, 100),
    ]
    scored = score_panel(load_comparable_panel(expansion, []))
    june_2024 = next(r for r in scored if r["source_period"] == "202406")
    june_2025 = next(r for r in scored if r["source_period"] == "202506")
    assert june_2024["expanding_median"] == pytest.approx(0.50)
    assert june_2025["expanding_median"] == pytest.approx(0.50)
    assert june_2025["observed"] == pytest.approx(0.99)
    assert june_2025["robust_z"] is not None and june_2025["robust_z"] > 2
    assert june_2024["max_baseline_period"] == "202306"


def test_zero_tests_not_scored_as_zero_positivity():
    expansion = [
        _row("bo", "202106", 50, 100),
        _row("bo", "202206", 50, 100),
        _row("bo", "202306", 50, 100),
        _row("bo", "202406", 50, 0),
    ]
    scored = score_panel(load_comparable_panel(expansion, []))
    row = next(r for r in scored if r["source_period"] == "202406")
    assert row["observed"] is None
    assert row["tests_not_positive"] is True
    assert row["primary_eligible"] is False
    assert row["conventional_alert"] is False


def test_low_completeness_blocks_primary_alert():
    expansion = [
        _row("bo", "202106", 50, 100, 0.5),
        _row("bo", "202206", 50, 100, 0.5),
        _row("bo", "202306", 50, 100, 0.5),
        _row("bo", "202406", 90, 100, 0.05),
    ]
    scored = score_panel(load_comparable_panel(expansion, []))
    row = next(r for r in scored if r["source_period"] == "202406")
    assert row["low_completeness"] is True
    assert row["primary_eligible"] is False
    assert row["conventional_alert"] is False


def test_calendar_t_plus_1_not_next_observed_row():
    expansion = [
        _row("bo", "202106", 50, 100),
        _row("bo", "202206", 50, 100),
        _row("bo", "202306", 50, 100),
        _row("bo", "202406", 50, 100),
        _row("bo", "202408", 80, 100),  # skip July
    ]
    scored = score_panel(load_comparable_panel(expansion, []))
    june = next(r for r in scored if r["source_period"] == "202406")
    assert june["lead1_period"] is None
    assert june["lead1_observed"] is None
    assert june.get("lead1_rainfall_mm") is None

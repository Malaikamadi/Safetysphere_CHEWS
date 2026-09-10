"""
Comparable-era malaria positivity anomaly diagnostics and chronological backtest.

Does NOT train a model.
Does NOT modify malaria_forecast_v1, malaria_positivity_forecast_v1, or the GBT.
Does NOT overwrite malaria_district_month_panel_latest.json.
Does NOT persist into CHEWS production paths.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.malaria_anomaly import (  # noqa: E402
    COMPARABLE_END,
    COMPARABLE_START,
    COMPLETENESS_MIN,
    MIN_PRIOR_YEARS_PRIMARY,
    ROBUST_Z_CONVENTION,
    audit_no_future_in_baselines,
    baseline_stability_table,
    load_comparable_panel,
    mae,
    pearson,
    percentile,
    score_panel,
)

EXPANSION = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion.json"
V1_PANEL = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_district_month_panel_latest.json"
OUT_JSON = BACKEND / "data" / "04_ai" / "diagnostics" / "malaria_anomaly_backtest.json"
COUNT_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1" / "model.joblib"
POS_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_positivity_forecast_v1" / "model.joblib"
GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
COUNT_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
POS_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_positivity_forecast_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(values: list) -> list[float]:
    out = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            continue
        out.append(number)
    return out


def _quantile_table(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def _corr_block(rows: list[dict], x_key: str, y_key: str) -> dict:
    pooled = pearson((r.get(x_key) for r in rows), (r.get(y_key) for r in rows))
    by_d: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_d[row["district_slug"]].append(row)
    within = []
    for group in by_d.values():
        value = pearson((r.get(x_key) for r in group), (r.get(y_key) for r in group))
        if value is not None:
            within.append(value)
    return {
        "pooled": pooled,
        "n_districts_with_corr": len(within),
        "median_within_district": (
            sorted(within)[len(within) // 2] if within else None
        ),
        "mean_within_district": (sum(within) / len(within)) if within else None,
    }


def main() -> None:
    hashes_before = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
    }
    v1 = json.loads(V1_PANEL.read_text(encoding="utf-8"))
    if len(v1) != 535:
        raise SystemExit(f"STOP: v1 panel is {len(v1)} rows, expected 535")
    expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
    pre_era = [
        r for r in expansion
        if (r.get("source_period") or "") < COMPARABLE_START
    ]
    rows = load_comparable_panel(expansion, v1)
    if any((r["source_period"] or "") < COMPARABLE_START for r in rows):
        raise SystemExit("STOP: comparable panel contains pre-202106 rows")

    scored = score_panel(rows, field="malaria_positivity")
    leak = audit_no_future_in_baselines(scored)
    if not leak["passed"]:
        raise SystemExit(f"STOP: future leakage detected: {leak}")

    eligible = [r for r in scored if r["primary_eligible"] and r.get("robust_z") is not None]
    scored_pos = [r for r in scored if r.get("observed") is not None]
    n_prior_hist = Counter(r["n_prior"] for r in scored_pos)
    n_prior_eligible = Counter(r["n_prior"] for r in eligible)

    z_vals = _finite([r["robust_z"] for r in eligible])
    z_mean_vals = _finite([r["z_mean"] for r in eligible])
    abs_med = _finite([r["abs_dev_median"] for r in eligible])

    alerts = [r for r in eligible if r["conventional_alert"]]
    mild = [r for r in eligible if r["mild_alert"]]
    sustained = [r for r in eligible if r["sustained_mild_alert"]]
    consecutive = [r for r in eligible if r["consecutive_conventional_alert"]]

    by_district_alerts = Counter(r["district_slug"] for r in alerts)
    by_month_alerts = Counter(r["calendar_month"] for r in alerts)
    by_period_alerts = Counter(r["source_period"] for r in alerts)
    bias = Counter(r["testing_bias_class"] for r in eligible)
    bias_alerts = Counter(r["testing_bias_class"] for r in alerts)

    genuine_alerts = [r for r in alerts if r["testing_bias_class"] == "genuine_increased_positivity"]
    testing_down_alerts = [r for r in alerts if r["testing_bias_class"] == "testing_down"]

    # Persistence of alerts into t+1 (calendar next month only).
    persist_pairs = [
        r for r in eligible
        if r.get("lead1_primary_eligible") and r.get("lead1_robust_z") is not None
    ]
    alert_then_high = [
        r for r in persist_pairs
        if r["conventional_alert"] and (r["lead1_robust_z"] or 0) >= 0
    ]
    alert_then_alert = [
        r for r in persist_pairs
        if r["conventional_alert"] and r.get("lead1_robust_z") is not None
        and r["lead1_robust_z"] >= ROBUST_Z_CONVENTION
    ]
    n_alert_with_lead = sum(1 for r in persist_pairs if r["conventional_alert"])
    n_no_alert_with_lead = sum(1 for r in persist_pairs if not r["conventional_alert"])
    no_alert_then_high = sum(
        1 for r in persist_pairs
        if (not r["conventional_alert"]) and (r["lead1_robust_z"] or 0) >= ROBUST_Z_CONVENTION
    )

    # Forecast-style MAE for positivity(t+1). Seasonal/prior-year baselines are
    # past-only relative to t+1 and do not include month t (different calendar month).
    lead_index = {(r["district_slug"], r["source_period"]): r for r in scored}
    persistence_pairs = []
    seasonal_pairs = []
    prior_year_pairs = []
    anomaly_as_level_pairs = []
    for row in eligible:
        if row.get("lead1_period") is None or row.get("lead1_observed") is None:
            continue
        lead = lead_index.get((row["district_slug"], row["lead1_period"]))
        if lead is None or lead.get("observed") is None:
            continue
        y = lead["observed"]
        if row.get("observed") is not None:
            persistence_pairs.append((y, row["observed"]))
        if lead.get("expanding_median") is not None:
            seasonal_pairs.append((y, lead["expanding_median"]))
        if lead.get("prior_year") is not None:
            prior_year_pairs.append((y, lead["prior_year"]))
        if row.get("observed") is not None and row.get("abs_dev_median") is not None and lead.get("expanding_median") is not None:
            # naive: next month ≈ this month's seasonal baseline is wrong month;
            # compare using current positivity as level (persistence) already above.
            anomaly_as_level_pairs.append((y, row["observed"]))

    stability = baseline_stability_table(scored)
    unstable = [s for s in stability if s.get("unstable_high_step") or s.get("high_mad")]

    # Predictive correlations: anomaly at t vs activity at t+1. Climate at t only.
    pred_eligible = [
        r for r in eligible
        if r.get("lead1_observed") is not None
    ]
    climate_eligible = [
        r for r in eligible
        if r.get("rainfall_anomaly") is not None
    ]

    # Tests vs positivity movement
    d_tests = []
    d_conf = []
    d_pos = []
    for r in eligible:
        if r.get("prior_year") is None or r.get("observed") is None:
            continue
        d_pos.append(r["abs_dev_median"])
        # prior_year is last year's positivity; tests change vs last year's tests is on bias class
    tests_vals = _finite([r["malaria_tests"] for r in eligible])
    inv_sqrt_tests = [1.0 / math.sqrt(t) for t in tests_vals if t > 0]
    abs_z = [abs(r["robust_z"]) for r in eligible if r.get("robust_z") is not None]
    # align inv_sqrt with abs_z via eligible order
    inv_for_corr = []
    abs_for_corr = []
    for r in eligible:
        t = r.get("malaria_tests")
        z = r.get("robust_z")
        if t and t > 0 and z is not None:
            inv_for_corr.append(1.0 / math.sqrt(t))
            abs_for_corr.append(abs(z))

    # Low-test flag: below 5th percentile of eligible tests
    tests_p05 = percentile(tests_vals, 0.05) if tests_vals else None
    low_test_rows = [
        r for r in eligible
        if tests_p05 is not None and r.get("malaria_tests") is not None and r["malaria_tests"] <= tests_p05
    ]

    # False-alert proxy: conventional alert at t but t+1 robust_z < 0 (did not stay elevated)
    false_persist = [
        r for r in persist_pairs
        if r["conventional_alert"] and r.get("lead1_robust_z") is not None and r["lead1_robust_z"] < 0
    ]
    # Missed high at t+1: no alert at t but t+1 conventional-level z
    missed_next = [
        r for r in persist_pairs
        if (not r["conventional_alert"]) and r.get("lead1_robust_z") is not None
        and r["lead1_robust_z"] >= ROBUST_Z_CONVENTION
    ]

    # Districts with zero conventional alerts
    districts = sorted({r["district_slug"] for r in scored})
    silent = [d for d in districts if by_district_alerts.get(d, 0) == 0]

    # n_prior >= 3 sufficiency: MAD and step when n_prior == 3 vs >= 4
    at3 = [r for r in eligible if r["n_prior"] == 3]
    at4p = [r for r in eligible if r["n_prior"] >= 4]
    mad3 = _finite([r["expanding_mad"] for r in at3])
    mad4 = _finite([r["expanding_mad"] for r in at4p])

    summary = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_trained": False,
        "integrated_into_chews": False,
        "comparable_era": {
            "start": COMPARABLE_START,
            "end": COMPARABLE_END,
            "pre_202106_expansion_rows_excluded": len(pre_era),
            "comparable_rows": len(rows),
            "districts": len(districts),
            "observed_months": len({r["source_period"] for r in rows}),
            "positivity_defined": sum(1 for r in rows if r.get("malaria_positivity") is not None),
            "positivity_gt_1": sum(
                1 for r in rows
                if r.get("malaria_positivity") is not None and r["malaria_positivity"] > 1
            ),
            "tests_not_positive": sum(
                1 for r in rows
                if r.get("malaria_tests") is None or r.get("malaria_tests") <= 0
            ),
        },
        "target": {
            "name": "seasonal_malaria_positivity_anomaly",
            "formula": "positivity = malaria_confirmed / malaria_tests when tests > 0",
            "grain": "district × calendar_month",
            "baseline": "expanding historical same-calendar-month median, years strictly before evaluation month",
            "primary_score": "robust_z = (positivity - median) / (1.4826 * MAD)",
            "min_prior_years_primary": MIN_PRIOR_YEARS_PRIMARY,
            "completeness_min": COMPLETENESS_MIN,
            "does_not_use_current_observation_in_baseline": True,
            "does_not_use_future": True,
            "does_not_use_full_dataset_mean": True,
            "does_not_use_t_plus_1_climate": True,
            "pre_indicator_created_pooled": False,
        },
        "n_prior_histogram_all_with_positivity": dict(sorted(n_prior_hist.items())),
        "n_prior_histogram_primary_eligible": dict(sorted(n_prior_eligible.items())),
        "eligibility": {
            "scored_rows": len(scored),
            "positivity_defined": len(scored_pos),
            "primary_eligible": len(eligible),
            "insufficient_history": sum(1 for r in scored if r["insufficient_history"]),
            "low_completeness": sum(1 for r in scored if r["low_completeness"]),
            "tests_not_positive": sum(1 for r in scored if r["tests_not_positive"]),
            "zero_dispersion": sum(1 for r in eligible if r["zero_dispersion"]),
        },
        "robust_z_distribution_primary": _quantile_table(z_vals),
        "mean_z_distribution_primary": _quantile_table(z_mean_vals),
        "abs_dev_median_distribution_primary": _quantile_table(abs_med),
        "n_prior_3_vs_4plus": {
            "n_at_3": len(at3),
            "n_at_4plus": len(at4p),
            "mean_mad_n3": (sum(mad3) / len(mad3)) if mad3 else None,
            "mean_mad_n4plus": (sum(mad4) / len(mad4)) if mad4 else None,
            "p90_abs_robust_z_n3": percentile(_finite([abs(r["robust_z"]) for r in at3]), 0.90),
            "p90_abs_robust_z_n4plus": percentile(_finite([abs(r["robust_z"]) for r in at4p]), 0.90),
        },
        "stability": {
            "district_calendar_month_keys": len(stability),
            "keys_unstable_high_step_or_high_mad": len(unstable),
            "share_unstable": (len(unstable) / len(stability)) if stability else None,
            "mean_of_max_abs_median_step": (
                sum(s["max_abs_median_step"] for s in stability if s.get("max_abs_median_step") is not None)
                / max(1, sum(1 for s in stability if s.get("max_abs_median_step") is not None))
            ),
            "unstable_keys": unstable[:40],
        },
        "testing_bias": {
            "class_counts_primary_eligible": dict(bias),
            "class_counts_conventional_alerts": dict(bias_alerts),
            "corr_abs_robust_z_vs_inv_sqrt_tests": pearson(inv_for_corr, abs_for_corr),
            "tests_p05": tests_p05,
            "n_low_test_eligible": len(low_test_rows),
            "n_low_test_alerts": sum(1 for r in low_test_rows if r["conventional_alert"]),
            "note": "testing_down means positivity rose while tests fell >=15% and confirmed did not rise vs last year's same month.",
        },
        "climate": {
            "corr_robust_z_vs_rainfall_anomaly": _corr_block(climate_eligible, "robust_z", "rainfall_anomaly"),
            "corr_robust_z_vs_temperature_anomaly": _corr_block(climate_eligible, "robust_z", "temperature_anomaly"),
            "corr_robust_z_vs_humidity_anomaly": _corr_block(climate_eligible, "robust_z", "humidity_anomaly"),
            "corr_robust_z_vs_three_month_rainfall": _corr_block(climate_eligible, "robust_z", "three_month_rainfall"),
            "corr_robust_z_vs_lag1_rainfall_anomaly": _corr_block(climate_eligible, "robust_z", "lag1_rainfall_anomaly"),
            "t_plus_1_climate_used": False,
        },
        "thresholds": {
            "data_described_robust_z_percentiles": _quantile_table(z_vals),
            "statistical_convention_alert": {
                "rule": "robust_z >= 2.0 AND n_prior >= 3 AND completeness >= 0.20 AND tests > 0",
                "source": "statistical_convention_not_fitted",
                "not_a_machine_learning_discovery": True,
            },
            "mild_convention": {
                "rule": "robust_z >= 1.5 with the same eligibility gates",
                "source": "statistical_convention_not_fitted",
            },
            "four_class_normal_watch_elevated_high": "not_proposed",
            "policy_thresholds": "none_claimed_as_validated",
        },
        "backtest": {
            "leakage_audit": leak,
            "evaluation": "chronological; baseline at t uses only earlier years of the same district-calendar-month",
            "n_primary_eligible": len(eligible),
            "n_conventional_alerts": len(alerts),
            "alert_rate": (len(alerts) / len(eligible)) if eligible else None,
            "n_mild_alerts": len(mild),
            "mild_alert_rate": (len(mild) / len(eligible)) if eligible else None,
            "n_sustained_mild": len(sustained),
            "n_consecutive_conventional": len(consecutive),
            "n_genuine_increased_positivity_alerts": len(genuine_alerts),
            "n_testing_down_alerts": len(testing_down_alerts),
            "alerts_by_district": dict(by_district_alerts),
            "silent_districts": silent,
            "alerts_by_calendar_month": {str(k): v for k, v in sorted(by_month_alerts.items())},
            "alerts_by_period": dict(sorted(by_period_alerts.items())),
            "n_pairs_with_calendar_t_plus_1": len(persist_pairs),
            "n_alerts_with_t_plus_1": n_alert_with_lead,
            "alert_then_t_plus_1_robust_z_ge_0": len(alert_then_high),
            "alert_then_t_plus_1_still_conventional": len(alert_then_alert),
            "false_persist_proxy_alert_then_z_lt_0": len(false_persist),
            "missed_next_conventional_given_no_alert_at_t": len(missed_next),
            "p_tplus1_z_ge_0_given_alert": (
                (len(alert_then_high) / n_alert_with_lead) if n_alert_with_lead else None
            ),
            "p_tplus1_conventional_given_alert": (
                (len(alert_then_alert) / n_alert_with_lead) if n_alert_with_lead else None
            ),
            "p_tplus1_conventional_given_no_alert": (
                (no_alert_then_high / n_no_alert_with_lead) if n_no_alert_with_lead else None
            ),
            "false_persist_proxy_rate": (
                (len(false_persist) / n_alert_with_lead) if n_alert_with_lead else None
            ),
        },
        "baseline_comparison_predict_positivity_t_plus_1": {
            "metric": "MAE of positivity(t+1)",
            "n_persistence": len(persistence_pairs),
            "mae_persistence_positivity_t": mae(persistence_pairs),
            "n_seasonal_expanding_median_of_t_plus_1": len(seasonal_pairs),
            "mae_seasonal_expanding_median": mae(seasonal_pairs),
            "n_prior_year_same_month_of_t_plus_1": len(prior_year_pairs),
            "mae_prior_year_same_month": mae(prior_year_pairs),
            "note": (
                "Persistence copies positivity(t). Seasonal median and prior-year use the "
                "past-only baseline of month t+1's own calendar month. The anomaly rule is "
                "a detector of unusual t, not a t+1 point forecast."
            ),
        },
        "predictive_value": {
            "corr_robust_z_t_vs_positivity_t_plus_1": _corr_block(pred_eligible, "robust_z", "lead1_observed"),
            "corr_robust_z_t_vs_robust_z_t_plus_1": _corr_block(pred_eligible, "robust_z", "lead1_robust_z"),
            "corr_robust_z_t_vs_confirmed_t_plus_1": _corr_block(pred_eligible, "robust_z", "lead1_confirmed"),
            "corr_positivity_t_vs_positivity_t_plus_1": _corr_block(pred_eligible, "observed", "lead1_observed"),
            "corr_robust_z_t_vs_tests_t_plus_1": _corr_block(pred_eligible, "robust_z", "lead1_tests"),
            "question": "Does an unusual month t provide information about elevated malaria after t?",
        },
        "recommendation": {
            "code": None,
            "options": {
                "A": "ANOMALY RULE/STATISTICAL BASELINE IS SUFFICIENT",
                "B": "ANOMALY TARGET IS PROMISING AND ML MODEL IS JUSTIFIED",
                "C": "MORE DATA IS REQUIRED",
                "D": "ANOMALY APPROACH IS NOT CURRENTLY DEFENSIBLE",
            },
        },
        "protected_hashes_before": hashes_before,
        "scored_primary_eligible": [
            {
                "district_slug": r["district_slug"],
                "source_period": r["source_period"],
                "n_prior": r["n_prior"],
                "observed": r["observed"],
                "expanding_median": r["expanding_median"],
                "expanding_mad": r["expanding_mad"],
                "robust_z": r["robust_z"],
                "z_mean": r["z_mean"],
                "abs_dev_median": r["abs_dev_median"],
                "ratio_median": r["ratio_median"],
                "conventional_alert": r["conventional_alert"],
                "mild_alert": r["mild_alert"],
                "sustained_mild_alert": r["sustained_mild_alert"],
                "testing_bias_class": r["testing_bias_class"],
                "malaria_confirmed": r["malaria_confirmed"],
                "malaria_tests": r["malaria_tests"],
                "facility_completeness": r["facility_completeness"],
                "rainfall_anomaly": r["rainfall_anomaly"],
                "temperature_anomaly": r["temperature_anomaly"],
                "humidity_anomaly": r["humidity_anomaly"],
                "baseline_periods": r["baseline_periods"],
                "lead1_observed": r.get("lead1_observed"),
                "lead1_robust_z": r.get("lead1_robust_z"),
            }
            for r in eligible
        ],
    }

    # Fill recommendation from evidence (still no training).
    persist_mae = summary["baseline_comparison_predict_positivity_t_plus_1"]["mae_persistence_positivity_t"]
    seasonal_mae = summary["baseline_comparison_predict_positivity_t_plus_1"]["mae_seasonal_expanding_median"]
    pred = summary["predictive_value"]
    pooled_z_next = (pred["corr_robust_z_t_vs_robust_z_t_plus_1"] or {}).get("pooled")
    pooled_pos_persist = (pred["corr_positivity_t_vs_positivity_t_plus_1"] or {}).get("pooled")
    climate_r = (summary["climate"]["corr_robust_z_vs_rainfall_anomaly"] or {}).get("pooled")
    alert_rate = summary["backtest"]["alert_rate"]
    genuine_share = (
        (len(genuine_alerts) / len(alerts)) if alerts else None
    )
    testing_share = (
        (len(testing_down_alerts) / len(alerts)) if alerts else None
    )

    # Decision rules for the written recommendation:
    # D if eligible too small or leakage failed (already exited).
    # C if most keys remain unstable and n_prior mostly = 3 with huge MAD.
    # B only if anomaly at t predicts t+1 better than persistence in a way ML could use.
    # A if contemporaneous seasonal detector is defensible but ML is not justified.
    ml_justified = False
    if (
        persist_mae is not None and seasonal_mae is not None
        and pooled_z_next is not None
        and pooled_pos_persist is not None
        and abs(pooled_z_next) > 0.35
        and persist_mae > seasonal_mae * 1.05
    ):
        ml_justified = True

    if len(eligible) < 100:
        code = "C"
        reason = "Too few primary-eligible district-months to defend an operational rule."
    elif ml_justified:
        code = "B"
        reason = "Anomaly shows residual t+1 structure beyond persistence; ML could be specified later."
    elif (
        alert_rate is not None
        and 0 < alert_rate < 0.20
        and leak["passed"]
        and len(eligible) >= 100
    ):
        code = "A"
        reason = (
            "Past-only seasonal robust-z is a defensible contemporaneous detector. "
            "Persistence still dominates t+1 positivity, so an ML forecast is not justified."
        )
    else:
        code = "D"
        reason = "Alert behaviour or predictive value is too weak/unstable to defend the anomaly as EW."

    summary["recommendation"]["code"] = code
    summary["recommendation"]["reason"] = reason
    summary["recommendation"]["genuine_alert_share"] = genuine_share
    summary["recommendation"]["testing_down_alert_share"] = testing_share
    summary["recommendation"]["climate_rainfall_pooled_r"] = climate_r
    summary["recommendation"]["ml_justified_by_numeric_gate"] = ml_justified

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    hashes_after = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
    }
    if hashes_after != hashes_before:
        raise SystemExit(f"STOP: protected file hash changed: {hashes_before} vs {hashes_after}")
    if len(json.loads(V1_PANEL.read_text())) != 535:
        raise SystemExit("STOP: v1 panel row count changed")

    print(json.dumps({
        "out": str(OUT_JSON),
        "comparable_rows": len(rows),
        "primary_eligible": len(eligible),
        "alerts": len(alerts),
        "alert_rate": summary["backtest"]["alert_rate"],
        "recommendation": code,
        "reason": reason,
        "mae_persistence": persist_mae,
        "mae_seasonal": seasonal_mae,
        "corr_z_t_z_t1": pooled_z_next,
        "corr_pos_persist": pooled_pos_persist,
        "climate_rain_r": climate_r,
        "leakage_passed": leak["passed"],
        "protected_hashes_ok": True,
        "model_trained": False,
    }, indent=2))


if __name__ == "__main__":
    main()

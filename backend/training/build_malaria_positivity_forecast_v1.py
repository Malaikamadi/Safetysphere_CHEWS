"""
Build malaria_positivity_forecast_v1 derived table.

Does NOT train a model.
Does NOT run train_all_models.py.
Does NOT overwrite malaria_forecast_v1_filtered.json or malaria_model.joblib.

    cd backend
    python -m training.build_malaria_positivity_forecast_v1
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.malaria_forecast import (  # noqa: E402
    calendar_prev,
    index_panel,
    load_original_panel,
    original_panel_path,
)
from services.malaria_positivity_forecast import (  # noqa: E402
    FEATURE_COLUMNS,
    TARGET_NAME,
    build_positivity_training_set,
    positivity,
)

TRAIN_START, TRAIN_END = "202307", "202412"
VAL_START, VAL_END = "202501", "202508"
TEST_START, TEST_END = "202509", "202602"

COUNT_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
SYNTHETIC_GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
V1_MODEL = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1" / "model.joblib"
ANALYSIS_PATH = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_positivity_forecast_v1_pretraining_analysis.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pearson(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = int(len(x))
    if n < 3 or np.std(x) == 0 or np.std(y) == 0:
        return {"n": n, "r": None}
    return {"n": n, "r": float(np.corrcoef(x, y)[0, 1])}


def _summarize(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return None
    mean = float(a.mean())
    std = float(a.std(ddof=1)) if len(a) > 1 else 0.0
    skew = 0.0 if std == 0 else float(np.mean((a - mean) ** 3) / (std ** 3))
    return {
        "n": int(len(a)),
        "min": float(a.min()),
        "max": float(a.max()),
        "mean": mean,
        "median": float(np.median(a)),
        "std": std,
        "skewness": skew,
        "zeros": int(np.sum(a == 0)),
        "outside_0_1": int(np.sum((a < 0) | (a > 1))),
        "nulls_in_input": None,
    }


def _in_range(period, start, end):
    return start <= period <= end


def analyze(rows, original):
    index = index_panel(original)
    y = np.array([r[TARGET_NAME] for r in rows], float)
    pos_t = np.array([np.nan if r["malaria_positivity"] is None else r["malaria_positivity"] for r in rows], float)
    tests = np.array([np.nan if r["malaria_tests"] is None else r["malaria_tests"] for r in rows], float)
    conf = np.array([np.nan if r["malaria_confirmed"] is None else r["malaria_confirmed"] for r in rows], float)
    rain = np.array([np.nan if r["rainfall_mm"] is None else r["rainfall_mm"] for r in rows], float)
    rain1 = np.array([np.nan if r["lag1_rainfall_mm"] is None else r["lag1_rainfall_mm"] for r in rows], float)
    rain2 = np.array([np.nan if r["lag2_rainfall_mm"] is None else r["lag2_rainfall_mm"] for r in rows], float)
    acc = np.array([
        np.nan if r["three_month_rainfall_accumulation"] is None else r["three_month_rainfall_accumulation"]
        for r in rows
    ], float)
    temp = np.array([np.nan if r["temperature_c"] is None else r["temperature_c"] for r in rows], float)
    temp1 = np.array([np.nan if r["lag1_temperature_c"] is None else r["lag1_temperature_c"] for r in rows], float)
    hum = np.array([np.nan if r["humidity_percent"] is None else r["humidity_percent"] for r in rows], float)
    hum1 = np.array([np.nan if r["lag1_humidity_percent"] is None else r["lag1_humidity_percent"] for r in rows], float)
    month = np.array([r["calendar_month"] for r in rows], float)
    pos_chg = np.array([np.nan if r["positivity_change"] is None else r["positivity_change"] for r in rows], float)
    conf_chg = np.array([np.nan if r["confirmed_change"] is None else r["confirmed_change"] for r in rows], float)

    seasonal = np.full(len(rows), np.nan)
    for i, row in enumerate(rows):
        prior = calendar_prev(row["target_period"], 12)
        src = index.get((row["district_slug"], prior))
        if src:
            value = positivity(src.get("malaria_confirmed"), src.get("malaria_tests"))
            if value is not None:
                seasonal[i] = value

    persist_defined = np.isfinite(pos_t)
    seasonal_defined = np.isfinite(seasonal)

    def _metrics(yhat, mask):
        if not np.any(mask):
            return {"n": 0, "mae": None, "rmse": None, "r2": None, "coverage": 0.0}
        yt = y[mask]
        yp = yhat[mask]
        mae = float(np.mean(np.abs(yt - yp)))
        rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))
        ss_res = float(np.sum((yt - yp) ** 2))
        ss_tot = float(np.sum((yt - yt.mean()) ** 2))
        r2 = None if ss_tot == 0 else 1.0 - ss_res / ss_tot
        return {"n": int(mask.sum()), "mae": mae, "rmse": rmse, "r2": r2, "coverage": float(mask.mean())}

    by_district = defaultdict(list)
    by_month = defaultdict(list)
    for r in rows:
        by_district[r["district_slug"]].append(r[TARGET_NAME])
        by_month[r["calendar_month"]].append(r[TARGET_NAME])

    district_corr = []
    for slug in sorted({r["district_slug"] for r in rows}):
        subset = [r for r in rows if r["district_slug"] == slug]
        if len(subset) < 8:
            continue
        p = [np.nan if r["malaria_positivity"] is None else r["malaria_positivity"] for r in subset]
        t = [r[TARGET_NAME] for r in subset]
        district_corr.append({
            "district": slug,
            "n": len(subset),
            "mean_target": float(np.mean(t)),
            "std_target": float(np.std(t, ddof=1)),
            "min_target": float(np.min(t)),
            "max_target": float(np.max(t)),
            "corr_positivity_t_target": _pearson(p, t),
        })

    # count-target comparison from original calendar pairs among kept rows
    count_pairs_conf = []
    count_pairs_tgt = []
    tests_vs_count_tgt = []
    for r in rows:
        src = index.get((r["district_slug"], r["feature_period"]))
        tgt = index.get((r["district_slug"], r["target_period"]))
        if src and tgt and src.get("malaria_confirmed") is not None and tgt.get("malaria_confirmed") is not None:
            count_pairs_conf.append(float(src["malaria_confirmed"]))
            count_pairs_tgt.append(float(tgt["malaria_confirmed"]))
            tests_vs_count_tgt.append(float(src["malaria_tests"]) if src.get("malaria_tests") is not None else np.nan)

    splits = {
        "train": sum(1 for r in rows if _in_range(r["feature_period"], TRAIN_START, TRAIN_END)),
        "validation": sum(1 for r in rows if _in_range(r["feature_period"], VAL_START, VAL_END)),
        "test": sum(1 for r in rows if _in_range(r["feature_period"], TEST_START, TEST_END)),
        "total": len(rows),
    }

    feature_corr_target = {}
    for name in FEATURE_COLUMNS:
        if name == "district_slug":
            continue
        series = [np.nan if r.get(name) is None else r[name] for r in rows]
        feature_corr_target[name] = _pearson(series, y)

    # redundancy among numeric features (pairwise |r| >= 0.90)
    numeric = [c for c in FEATURE_COLUMNS if c != "district_slug"]
    redundant = []
    matrices = {c: np.array([np.nan if r.get(c) is None else r[c] for r in rows], float) for c in numeric}
    for i, a in enumerate(numeric):
        for b in numeric[i + 1:]:
            stat = _pearson(matrices[a], matrices[b])
            if stat["r"] is not None and abs(stat["r"]) >= 0.90:
                redundant.append({"a": a, "b": b, **stat})

    target_summary = _summarize(y)
    target_summary["nulls"] = int(sum(r[TARGET_NAME] is None for r in rows))
    target_summary["outside_0_1"] = int(np.sum((y < 0) | (y > 1)))

    nulls = {
        "lag1_malaria_confirmed": sum(r["lag1_malaria_confirmed"] is None for r in rows),
        "lag2_malaria_confirmed": sum(r["lag2_malaria_confirmed"] is None for r in rows),
        "rolling_3_malaria_confirmed": sum(r["rolling_3_malaria_confirmed"] is None for r in rows),
        "lag1_malaria_tests": sum(r["lag1_malaria_tests"] is None for r in rows),
        "lag1_malaria_positivity": sum(r["lag1_malaria_positivity"] is None for r in rows),
        "positivity_change": sum(r["positivity_change"] is None for r in rows),
        "confirmed_change": sum(r["confirmed_change"] is None for r in rows),
        "confirmed_pct_change": sum(r["confirmed_pct_change"] is None for r in rows),
        "testing_change": sum(r["testing_change"] is None for r in rows),
        "lag1_rainfall_mm": sum(r["lag1_rainfall_mm"] is None for r in rows),
        "lag2_rainfall_mm": sum(r["lag2_rainfall_mm"] is None for r in rows),
        "three_month_rainfall_accumulation": sum(r["three_month_rainfall_accumulation"] is None for r in rows),
        "lag1_temperature_c": sum(r["lag1_temperature_c"] is None for r in rows),
        "lag1_humidity_percent": sum(r["lag1_humidity_percent"] is None for r in rows),
        "malaria_positivity": sum(r["malaria_positivity"] is None for r in rows),
        TARGET_NAME: sum(r[TARGET_NAME] is None for r in rows),
    }

    return {
        "n_rows": len(rows),
        "districts": sorted({r["district_slug"] for r in rows}),
        "district_count": len({r["district_slug"] for r in rows}),
        "feature_months": sorted({r["feature_period"] for r in rows}),
        "target_months": sorted({r["target_period"] for r in rows}),
        "target": target_summary,
        "by_district": district_corr,
        "by_calendar_month": {
            str(m): {
                "n": len(by_month[m]),
                "mean": float(np.mean(by_month[m])),
                "median": float(np.median(by_month[m])),
                "std": float(np.std(by_month[m], ddof=1)) if len(by_month[m]) > 1 else 0.0,
            }
            for m in range(1, 13) if by_month[m]
        },
        "nulls": nulls,
        "persistence": {
            "corr_positivity_t_vs_target": _pearson(pos_t, y),
            "metrics_where_defined": _metrics(pos_t, persist_defined),
            "undefined_rows": int((~persist_defined).sum()),
        },
        "seasonal_baseline": {
            "corr_where_defined": _pearson(seasonal, y),
            "metrics_where_defined": _metrics(seasonal, seasonal_defined),
            "undefined_rows": int((~seasonal_defined).sum()),
        },
        "climate_and_change_correlations": {
            "rainfall_t": _pearson(rain, y),
            "rainfall_t_minus_1": _pearson(rain1, y),
            "rainfall_t_minus_2": _pearson(rain2, y),
            "three_month_rainfall": _pearson(acc, y),
            "temperature_t": _pearson(temp, y),
            "temperature_t_minus_1": _pearson(temp1, y),
            "humidity_t": _pearson(hum, y),
            "humidity_t_minus_1": _pearson(hum1, y),
            "calendar_month": _pearson(month, y),
            "positivity_t": _pearson(pos_t, y),
            "positivity_change": _pearson(pos_chg, y),
            "confirmed_change": _pearson(conf_chg, y),
        },
        "testing_bias": {
            "tests_t_vs_positivity_target": _pearson(tests, y),
            "tests_t_vs_positivity_t": _pearson(tests, pos_t),
            "confirmed_t_vs_positivity_target": _pearson(conf, y),
            "tests_t_vs_count_target": _pearson(tests_vs_count_tgt, count_pairs_tgt),
            "confirmed_t_vs_count_target": _pearson(count_pairs_conf, count_pairs_tgt),
        },
        "feature_corr_with_target": feature_corr_target,
        "redundant_pairs_abs_r_ge_0_90": redundant,
        "proposed_split": splits,
        "proposed_split_windows": {
            "train": f"{TRAIN_START}-{TRAIN_END}",
            "validation": f"{VAL_START}-{VAL_END}",
            "test": f"{TEST_START}-{TEST_END}",
        },
    }


def main() -> None:
    gbt_before = _sha256(SYNTHETIC_GBT)
    v1_before = _sha256(V1_MODEL)
    panel_before = _sha256(original_panel_path())
    count_before = _sha256(COUNT_FILTERED)

    result = build_positivity_training_set(persist=True)
    rows = result["rows"]
    report = result["report"]
    analysis = analyze(rows, load_original_panel())
    ANALYSIS_PATH.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    gbt_after = _sha256(SYNTHETIC_GBT)
    v1_after = _sha256(V1_MODEL)
    panel_after = _sha256(original_panel_path())
    count_after = _sha256(COUNT_FILTERED)
    if gbt_before != gbt_after:
        raise SystemExit("STOP: malaria_model.joblib changed")
    if v1_before != v1_after:
        raise SystemExit("STOP: malaria_forecast_v1 model.joblib changed")
    if panel_before != panel_after:
        raise SystemExit("STOP: original panel changed")
    if count_before != count_after:
        raise SystemExit("STOP: count filtered dataset changed")

    target = analysis["target"]
    ready = (
        report["leakage_audit"]["passed"]
        and target["outside_0_1"] == 0
        and target["nulls"] == 0
        and analysis["n_rows"] > 0
        and analysis["district_count"] == 16
        and report["model_trained"] is False
    )
    print(json.dumps({
        "rows": analysis["n_rows"],
        "districts": analysis["district_count"],
        "feature_months": len(analysis["feature_months"]),
        "target": target,
        "persistence_r": analysis["persistence"]["corr_positivity_t_vs_target"],
        "tests_vs_pos_target": analysis["testing_bias"]["tests_t_vs_positivity_target"],
        "tests_vs_count_target": analysis["testing_bias"]["tests_t_vs_count_target"],
        "split": analysis["proposed_split"],
        "leakage_passed": report["leakage_audit"]["passed"],
        "ready": ready,
        "paths": result["paths"],
        "analysis_path": str(ANALYSIS_PATH),
        "protection": {
            "malaria_model_joblib": gbt_after,
            "malaria_forecast_v1_model": v1_after,
            "original_panel": panel_after,
            "count_filtered": count_after,
        },
    }, indent=2))


if __name__ == "__main__":
    main()

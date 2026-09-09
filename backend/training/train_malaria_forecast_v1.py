"""
Train malaria_forecast_v1 only.

Loads the quality-filtered district-month table.
Does NOT run train_all_models.py.
Does NOT overwrite data/trained_models/malaria_model.joblib.
Does NOT modify the original 535-row panel.
Does NOT connect to the dashboard or risk engine.

Run:
    cd backend
    python -m training.train_malaria_forecast_v1
"""

from __future__ import annotations

import hashlib
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import OrdinalEncoder

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.malaria_forecast import (  # noqa: E402
    COMPLETENESS_MIN,
    TARGET_NAME,
    calendar_prev,
    index_panel,
    load_original_panel,
    original_panel_path,
)

RANDOM_STATE = 42
TRAIN_START, TRAIN_END = "202307", "202412"
VAL_START, VAL_END = "202501", "202508"
TEST_START, TEST_END = "202509", "202602"
EXPECTED_COUNTS = {"train": 280, "validation": 128, "test": 96, "total": 504}

CORE_FEATURES = [
    "malaria_confirmed",
    "lag1_malaria_confirmed",
    "malaria_tests",
    "rainfall_mm",
    "temperature_c",
    "humidity_percent",
    "calendar_month",
    "district_encoded",
]
OPTIONAL_FEATURES = [
    "lag2_malaria_confirmed",
    "rolling_3_malaria_confirmed",
    "malaria_rdt_positive",
    "rdt_positivity",
]
LEAKAGE_COLUMNS = {
    TARGET_NAME,
    "malaria_confirmed_next",
    "target_period",
    "target_facility_completeness",
    "target_reporting_facilities",
    "target_description",
}

FILTERED_PATH = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
OUTPUT_DIR = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1"
SYNTHETIC_GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
ORIGINAL_PANEL = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_district_month_panel_latest.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _in_range(period: str, start: str, end: str) -> bool:
    return start <= period <= end


def smape(y_true, y_pred) -> float:
    y = np.asarray(y_true, dtype=float)
    yhat = np.asarray(y_pred, dtype=float)
    denom = np.abs(y) + np.abs(yhat)
    out = np.zeros_like(y, dtype=float)
    mask = denom > 0
    out[mask] = 2.0 * np.abs(y[mask] - yhat[mask]) / denom[mask]
    return float(100.0 * np.mean(out))


def metrics(y_true, y_pred) -> dict:
    y = np.asarray(y_true, dtype=float)
    yhat = np.asarray(y_pred, dtype=float)
    return {
        "n": int(len(y)),
        "mae": float(mean_absolute_error(y, yhat)),
        "rmse": float(np.sqrt(mean_squared_error(y, yhat))),
        "r2": float(r2_score(y, yhat)),
        "smape": smape(y, yhat),
    }


def split_rows(rows: list[dict]) -> dict[str, list[dict]]:
    splits = {
        "train": [r for r in rows if _in_range(r["feature_period"], TRAIN_START, TRAIN_END)],
        "validation": [r for r in rows if _in_range(r["feature_period"], VAL_START, VAL_END)],
        "test": [r for r in rows if _in_range(r["feature_period"], TEST_START, TEST_END)],
    }
    total = len(rows)
    counts = {k: len(v) for k, v in splits.items()}
    counts["total"] = total
    if counts != EXPECTED_COUNTS:
        raise SystemExit(
            f"STOP: split counts {counts} != expected {EXPECTED_COUNTS}. "
            "Investigate before training."
        )
    return splits


def fit_district_encoder(train_rows: list[dict]) -> OrdinalEncoder:
    slugs = sorted({r["district_slug"] for r in train_rows})
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        dtype=np.float64,
    )
    encoder.fit(np.array(slugs, dtype=object).reshape(-1, 1))
    encoder.categories_[0] = np.array(slugs, dtype=object)
    # Refit in sorted order for stability
    encoder.fit(np.array(slugs, dtype=object).reshape(-1, 1))
    return encoder


def encode_districts(rows: list[dict], encoder: OrdinalEncoder) -> np.ndarray:
    slugs = np.array([r["district_slug"] for r in rows], dtype=object).reshape(-1, 1)
    encoded = encoder.transform(slugs).ravel()
    if np.any(encoded < 0):
        raise SystemExit("STOP: unknown district in val/test — encoder must be train-only and cover all inference districts.")
    return encoded


def to_nan(value):
    if value is None:
        return np.nan
    if isinstance(value, str) and value.strip().lower() in {"", "null", "nan", "none"}:
        raise SystemExit(f"STOP: string missing marker {value!r} found; expected JSON null → float NaN.")
    return float(value)


def design_matrix(rows: list[dict], feature_names: list[str], encoder: OrdinalEncoder) -> tuple[np.ndarray, np.ndarray]:
    encoded = encode_districts(rows, encoder)
    leakage = [c for c in feature_names if c in LEAKAGE_COLUMNS]
    if leakage:
        raise SystemExit(f"STOP: leakage columns in feature list: {leakage}")
    if TARGET_NAME in feature_names:
        raise SystemExit("STOP: target present in X")
    matrix = np.zeros((len(rows), len(feature_names)), dtype=float)
    for j, name in enumerate(feature_names):
        if name == "district_encoded":
            matrix[:, j] = encoded
            continue
        for i, row in enumerate(rows):
            if name not in row and name != "district_encoded":
                raise SystemExit(f"STOP: feature {name} missing from row")
            matrix[i, j] = to_nan(row[name])
    if matrix.dtype.kind != "f":
        raise SystemExit("STOP: feature matrix is not floating-point")
    y = np.array([to_nan(r[TARGET_NAME]) for r in rows], dtype=float)
    if np.any(~np.isfinite(y)):
        raise SystemExit("STOP: non-finite target values")
    audit_feature_matrix(matrix, feature_names)
    return matrix, y


def audit_feature_matrix(matrix: np.ndarray, feature_names: list[str]) -> None:
    for name in feature_names:
        if "next" in name.lower() or name == TARGET_NAME:
            raise SystemExit(f"STOP: leakage feature name {name}")
    if matrix.dtype != np.float64:
        raise SystemExit("STOP: expected float64 feature matrix")


def persistence_predict(rows: list[dict]) -> np.ndarray:
    return np.array([to_nan(r["malaria_confirmed"]) for r in rows], dtype=float)


def seasonal_predict(rows: list[dict], original_index: dict) -> np.ndarray:
    preds = np.full(len(rows), np.nan, dtype=float)
    for i, row in enumerate(rows):
        prior = calendar_prev(row["target_period"], 12)
        src = original_index.get((row["district_slug"], prior))
        if src and src.get("malaria_confirmed") is not None:
            preds[i] = float(src["malaria_confirmed"])
    return preds


def defined_metrics(y_true, y_pred) -> dict:
    y = np.asarray(y_true, dtype=float)
    yhat = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(yhat)
    if not np.any(mask):
        return {"n": 0, "mae": None, "rmse": None, "r2": None, "smape": None, "coverage": 0.0}
    out = metrics(y[mask], yhat[mask])
    out["coverage"] = float(mask.mean())
    out["n_undefined"] = int((~mask).sum())
    return out


def fit_histgb(X_train, y_train, X_val, y_val) -> tuple[HistGradientBoostingRegressor, dict, dict]:
    grid = []
    for max_depth in (3, 5):
        for learning_rate in (0.05, 0.1):
            for l2 in (0.0, 1.0):
                grid.append({
                    "max_depth": max_depth,
                    "learning_rate": learning_rate,
                    "l2_regularization": l2,
                    "max_iter": 200,
                    "min_samples_leaf": 20,
                    "random_state": RANDOM_STATE,
                    "early_stopping": False,
                })
    best = None
    best_params = None
    best_val = None
    for params in grid:
        model = HistGradientBoostingRegressor(**params)
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_val), 0, None)
        score = metrics(y_val, pred)
        if best_val is None or score["mae"] < best_val["mae"] or (
            score["mae"] == best_val["mae"] and score["rmse"] < best_val["rmse"]
        ):
            best = model
            best_params = params
            best_val = score
    return best, best_params, best_val


def feature_sets() -> list[tuple[str, list[str]]]:
    core = list(CORE_FEATURES)
    return [
        ("core", core),
        ("core_plus_lags_rolling", core + ["lag2_malaria_confirmed", "rolling_3_malaria_confirmed"]),
        ("core_plus_all_optional", core + list(OPTIONAL_FEATURES)),
    ]


def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning)
    started = _utcnow()
    gbt_hash_before = _sha256(SYNTHETIC_GBT) if SYNTHETIC_GBT.exists() else None
    panel_hash_before = _sha256(ORIGINAL_PANEL)
    filtered_hash = _sha256(FILTERED_PATH)

    rows = json.loads(FILTERED_PATH.read_text(encoding="utf-8"))
    if len(rows) != 504:
        raise SystemExit(f"STOP: expected 504 filtered rows, got {len(rows)}")
    splits = split_rows(rows)
    original_index = index_panel(load_original_panel(original_panel_path()))

    encoder = fit_district_encoder(splits["train"])
    train_districts = set(splits["train"][i]["district_slug"] for i in range(len(splits["train"])))
    for fold in ("validation", "test"):
        extra = {r["district_slug"] for r in splits[fold]} - train_districts
        if extra:
            raise SystemExit(f"STOP: {fold} has districts not in train: {extra}")

    selection = []
    for name, features in feature_sets():
        X_tr, y_tr = design_matrix(splits["train"], features, encoder)
        X_va, y_va = design_matrix(splits["validation"], features, encoder)
        model, params, val_scores = fit_histgb(X_tr, y_tr, X_va, y_va)
        selection.append({
            "feature_set": name,
            "features": features,
            "val_mae": val_scores["mae"],
            "val_rmse": val_scores["rmse"],
            "val_r2": val_scores["r2"],
            "val_smape": val_scores["smape"],
            "params": params,
            "model": model,
            "X_train": X_tr,
            "y_train": y_tr,
            "X_val": X_va,
            "y_val": y_va,
        })
        print(f"HistGB {name}: val MAE={val_scores['mae']:.2f} RMSE={val_scores['rmse']:.2f} R2={val_scores['r2']:.4f}")

    chosen = min(selection, key=lambda s: (s["val_mae"], s["val_rmse"]))
    final_features = chosen["features"]
    model = chosen["model"]
    print(f"Selected feature set on validation: {chosen['feature_set']}")

    X_te, y_te = design_matrix(splits["test"], final_features, encoder)

    fold_rows = {
        "train": splits["train"],
        "validation": splits["validation"],
        "test": splits["test"],
    }
    fold_xy = {
        "train": (chosen["X_train"], chosen["y_train"]),
        "validation": (chosen["X_val"], chosen["y_val"]),
        "test": (X_te, y_te),
    }

    evaluation = {"by_model": {}, "feature_set_search": [
        {k: v for k, v in s.items() if k not in {"model", "X_train", "y_train", "X_val", "y_val"}}
        for s in selection
    ]}

    for fold_name, fold in fold_rows.items():
        X, y = fold_xy[fold_name]
        hist_pred = np.clip(model.predict(X), 0, None)
        persist = persistence_predict(fold)
        seasonal = seasonal_predict(fold, original_index)
        evaluation["by_model"].setdefault("previous_month_baseline", {})[fold_name] = metrics(y, persist)
        evaluation["by_model"].setdefault("seasonal_baseline", {})[fold_name] = defined_metrics(y, seasonal)
        evaluation["by_model"].setdefault("hist_gradient_boosting", {})[fold_name] = metrics(y, hist_pred)

    val_ml = evaluation["by_model"]["hist_gradient_boosting"]["validation"]
    val_persist = evaluation["by_model"]["previous_month_baseline"]["validation"]
    val_seasonal = evaluation["by_model"]["seasonal_baseline"]["validation"]
    beats_persist = val_ml["mae"] < val_persist["mae"]
    beats_seasonal = (
        val_seasonal["mae"] is None
        or val_ml["mae"] < val_seasonal["mae"]
    )

    perm = permutation_importance(
        model,
        chosen["X_val"],
        chosen["y_val"],
        n_repeats=20,
        random_state=RANDOM_STATE,
        scoring="neg_mean_absolute_error",
    )
    importance = []
    for name, mean_imp, std_imp in sorted(
        zip(final_features, perm.importances_mean, perm.importances_std),
        key=lambda t: t[1],
        reverse=True,
    ):
        importance.append({
            "feature": name,
            "permutation_importance_mean_mae": float(mean_imp),
            "permutation_importance_std": float(std_imp),
        })

    train_mae = evaluation["by_model"]["hist_gradient_boosting"]["train"]["mae"]
    val_mae = val_ml["mae"]
    test_mae = evaluation["by_model"]["hist_gradient_boosting"]["test"]["mae"]
    overfit_ratio = val_mae / train_mae if train_mae else None
    if overfit_ratio and overfit_ratio > 2.0 and val_mae > val_persist["mae"]:
        overfit_note = "Validation error is much higher than train and worse than persistence — overfitting / no useful signal."
        overfit_flag = "overfitting_and_no_lift"
    elif overfit_ratio and overfit_ratio > 1.8:
        overfit_note = "Validation MAE is substantially higher than train MAE — some overfitting; judge by whether val still beats baselines."
        overfit_flag = "some_overfitting"
    elif val_mae > train_mae * 1.15:
        overfit_note = "Mild train/validation gap, typical for a small district-month panel."
        overfit_flag = "mild_gap"
    else:
        overfit_note = "Train and validation MAE are close."
        overfit_flag = "no_severe_overfitting"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_DIR / "model.joblib")
    joblib.dump(encoder, OUTPUT_DIR / "district_encoder.joblib")

    feature_config = {
        "core_features": CORE_FEATURES,
        "optional_features": OPTIONAL_FEATURES,
        "optional_features_included": [f for f in final_features if f in OPTIONAL_FEATURES],
        "final_features": final_features,
        "target": TARGET_NAME,
        "missing_value_policy": "preserve legitimate NaN values",
        "district_encoding": "train_fold_only",
        "feature_order": final_features,
    }
    (OUTPUT_DIR / "feature_config.json").write_text(json.dumps(feature_config, indent=2), encoding="utf-8")

    null_stats = {
        "null_lag1": sum(r["lag1_malaria_confirmed"] is None for r in rows),
        "null_lag2": sum(r["lag2_malaria_confirmed"] is None for r in rows),
        "null_rolling_3": sum(r["rolling_3_malaria_confirmed"] is None for r in rows),
        "null_rdt_positivity": sum(r["rdt_positivity"] is None for r in rows),
    }
    by_district = {}
    for r in rows:
        by_district[r["district_slug"]] = by_district.get(r["district_slug"], 0) + 1

    training_metadata = {
        "model_version": "malaria_forecast_v1",
        "training_timestamp": started,
        "dataset_path": str(FILTERED_PATH.relative_to(BACKEND)),
        "dataset_sha256": filtered_hash,
        "dataset_rows": 504,
        "district_count": 16,
        "feature_period_start": "202307",
        "feature_period_end": "202602",
        "target_period_start": "202308",
        "target_period_end": "202603",
        "train_rows": 280,
        "validation_rows": 128,
        "test_rows": 96,
        "features": final_features,
        "target": TARGET_NAME,
        "algorithm": "sklearn.ensemble.HistGradientBoostingRegressor",
        "hyperparameters": chosen["params"],
        "feature_set_selected": chosen["feature_set"],
        "split_strategy": "chronological by feature_period: train 202307-202412, val 202501-202508, test 202509-202602",
        "missing_value_policy": "preserve legitimate NaN values; never fill HMIS gaps with 0",
        "completeness_threshold": COMPLETENESS_MIN,
        "source": "DHIS2 historical malaria data + Open-Meteo historical climate",
        "not_synthetic": True,
        "random_state": RANDOM_STATE,
        "python_version": sys.version.split()[0],
        "sklearn_version": __import__("sklearn").__version__,
        "original_panel_unmodified": True,
        "synthetic_gbt_unmodified": True,
    }
    (OUTPUT_DIR / "training_metadata.json").write_text(json.dumps(training_metadata, indent=2), encoding="utf-8")

    persist_mae = val_persist["mae"]
    mae_lift_pct = 100.0 * (persist_mae - val_ml["mae"]) / persist_mae if persist_mae else 0.0
    rmse_better = val_ml["rmse"] < val_persist["rmse"]
    # Require a meaningful validation lift over persistence, not a sub-percent MAE tick.
    meaningful_vs_persist = beats_persist and mae_lift_pct >= 5.0 and rmse_better
    if meaningful_vs_persist and beats_seasonal:
        recommendation = "RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            f"HistGradientBoosting improves validation MAE by {mae_lift_pct:.1f}% vs previous-month "
            "and also beats seasonal RMSE/MAE."
        )
    elif beats_persist and beats_seasonal:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            f"Validation MAE is only {mae_lift_pct:.1f}% below previous-month "
            f"({val_ml['mae']:.1f} vs {persist_mae:.1f}) and RMSE/R² do not improve. "
            "Seasonal baseline is worse, but that is not enough to treat the ML model as useful."
        )
    elif beats_persist or beats_seasonal:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = "HistGradientBoosting does not meaningfully outperform the previous-month baseline on validation."
    else:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = "HistGradientBoosting does not beat the previous-month baseline on validation MAE."

    model_card = {
        "model_name": "malaria_forecast_v1",
        "purpose": "Forecast district-level confirmed malaria cases one calendar month ahead.",
        "intended_use": "Early-warning and preparedness decision support. Not a clinical diagnosis.",
        "data": {
            "source": "Historical DHIS2 malaria Analytics (Sierra Leone HMIS) joined to Open-Meteo Archive monthly climate at district centroids.",
            "filtered_rows": 504,
            "original_panel_rows": 535,
            "geography": "16 Sierra Leone districts in the filtered dataset.",
            "temporal_coverage": {
                "feature_periods": "202307–202602",
                "target_periods": "202308–202603",
            },
        },
        "features": final_features,
        "target": "malaria_confirmed at calendar month t+1 (target_malaria_confirmed_next_period)",
        "algorithm": "HistGradientBoostingRegressor",
        "evaluation_split": training_metadata["split_strategy"],
        "limitations": [
            "Incomplete facility reporting; training required facility_completeness ≥ 0.20 at t and t+1.",
            "HMIS Analytics returned no cells for 202604 and 202607; those months remain missing and were not imputed.",
            "Sparse leftover reporting in 202605/202606/202608 was excluded by the completeness/calendar filter.",
            "Typical facility completeness on kept pairs is about 0.60 (min 0.22, max 0.75).",
            "Confirmed malaria reflects both disease burden and reporting/testing patterns.",
            "Relatively small district-month sample (504 rows, 16 districts, 32 feature months).",
            "Climate variables are Archive month t, not a forecast of t+1 weather.",
            "One-month-ahead forecasting model only.",
            "Not a causal model.",
            "Not a clinical diagnostic model.",
            "Not connected to the CHEWS dashboard or risk engine in this package.",
        ],
        "missing_data_policy": "Legitimate historical gaps remain NaN. Never filled with zero.",
        "known_biases": [
            "Counts scale with testing volume (malaria_tests is a covariate).",
            "Districts/months below 20% facility completeness are out of the training distribution.",
        ],
        "prohibited_use": [
            "Replacing official HMIS reporting.",
            "Diagnosing individual patients.",
            "Using the synthetic malaria GBT feature contract (fever, stagnation, breeding sites).",
        ],
        "review_status": recommendation,
        "review_status_reason": why,
    }
    (OUTPUT_DIR / "model_card.json").write_text(json.dumps(model_card, indent=2), encoding="utf-8")

    evaluation_doc = {
        "metrics": evaluation["by_model"],
        "feature_set_search": evaluation["feature_set_search"],
        "selected_feature_set": chosen["feature_set"],
        "permutation_importance_validation": importance,
        "overfitting": {
            "flag": overfit_flag,
            "note": overfit_note,
            "train_mae": train_mae,
            "validation_mae": val_mae,
            "test_mae": test_mae,
            "val_over_train_mae_ratio": overfit_ratio,
        },
        "baseline_comparison_validation": {
            "histgb_beats_previous_month": beats_persist,
            "histgb_beats_seasonal": beats_seasonal,
        },
        "data_quality": {
            "filtered_rows": 504,
            "districts": 16,
            "feature_months": 32,
            **null_stats,
            "min_district_observations": min(by_district.values()),
            "max_district_observations": max(by_district.values()),
            "completeness_threshold": COMPLETENESS_MIN,
            "feature_completeness_min": min(r["feature_facility_completeness"] for r in rows),
            "feature_completeness_max": max(r["feature_facility_completeness"] for r in rows),
        },
        "leakage_audit": {
            "target_in_features": False,
            "malaria_confirmed_next_in_features": False,
            "encoder_fit_on": "train_fold_only",
            "test_used_for_model_selection": False,
            "nan_policy": "JSON null → numpy.nan",
        },
        "recommendation": recommendation,
        "recommendation_reason": why,
    }
    (OUTPUT_DIR / "evaluation.json").write_text(json.dumps(evaluation_doc, indent=2), encoding="utf-8")

    # Independent reload test
    loaded_model = joblib.load(OUTPUT_DIR / "model.joblib")
    loaded_enc = joblib.load(OUTPUT_DIR / "district_encoder.joblib")
    X_te2, y_te2 = design_matrix(splits["test"], final_features, loaded_enc)
    preds = np.clip(loaded_model.predict(X_te2), 0, None)
    if len(preds) != 96:
        raise SystemExit(f"STOP: reloaded model produced {len(preds)} preds, expected 96")
    if not np.all(np.isfinite(preds)):
        raise SystemExit("STOP: non-finite predictions from saved model")
    reload_metrics = metrics(y_te2, preds)

    gbt_hash_after = _sha256(SYNTHETIC_GBT) if SYNTHETIC_GBT.exists() else None
    panel_hash_after = _sha256(ORIGINAL_PANEL)
    if gbt_hash_before != gbt_hash_after:
        raise SystemExit("STOP: synthetic malaria_model.joblib hash changed")
    if panel_hash_before != panel_hash_after:
        raise SystemExit("STOP: original panel hash changed")

    print("\n=== malaria_forecast_v1 training complete (not integrated) ===")
    print("selected", chosen["feature_set"], final_features)
    print("val HistGB", val_ml)
    print("val persist", val_persist)
    print("val seasonal", val_seasonal)
    print("test HistGB", evaluation["by_model"]["hist_gradient_boosting"]["test"])
    print("reload test MAE", reload_metrics["mae"])
    print("recommendation", recommendation)
    print("synthetic GBT hash unchanged", gbt_hash_after)
    print("output", OUTPUT_DIR)


if __name__ == "__main__":
    main()

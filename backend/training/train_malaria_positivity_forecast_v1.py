"""
Train malaria_positivity_forecast_v1 only.

Loads the positivity derived table.
Does NOT run train_all_models.py.
Does NOT overwrite data/trained_models/malaria_model.joblib.
Does NOT modify malaria_forecast_v1 artifacts.
Does NOT modify the original 535-row panel.
Does NOT connect to the dashboard or risk engine.

Run:
    cd backend
    python -m training.train_malaria_positivity_forecast_v1
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
    calendar_prev,
    index_panel,
    load_original_panel,
    original_panel_path,
)
from services.malaria_positivity_forecast import (  # noqa: E402
    COMPLETENESS_MIN,
    FEATURE_COLUMNS,
    TARGET_NAME,
    positivity,
)

RANDOM_STATE = 42
TRAIN_START, TRAIN_END = "202307", "202412"
VAL_START, VAL_END = "202501", "202508"
TEST_START, TEST_END = "202509", "202602"
EXPECTED_COUNTS = {"train": 280, "validation": 128, "test": 96, "total": 504}

# Recommended non-redundant core from the positivity design (counts/tests levels not dumped in).
POSITIVITY_CORE = [
    "malaria_positivity",
    "lag1_malaria_positivity",
    "positivity_change",
    "calendar_month",
    "district_encoded",
]
CLIMATE_LAGS = [
    "rainfall_mm",
    "lag1_rainfall_mm",
    "lag2_rainfall_mm",
    "temperature_c",
    "lag1_temperature_c",
    "humidity_percent",
    "lag1_humidity_percent",
]
LEAKAGE_COLUMNS = {
    TARGET_NAME,
    "malaria_confirmed_next",
    "target_period",
    "target_facility_completeness",
    "target_reporting_facilities",
    "target_description",
    "target_defined_when",
    "malaria_tests_next",
    "positivity_next",
    "target_malaria_confirmed",
    "target_malaria_tests",
}

DATASET_PATH = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_positivity_forecast_v1.json"
OUTPUT_DIR = BACKEND / "data" / "04_ai" / "models" / "malaria_positivity_forecast_v1"
SYNTHETIC_GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
COUNT_V1_MODEL = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1" / "model.joblib"
COUNT_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
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
    counts = {k: len(v) for k, v in splits.items()}
    counts["total"] = len(rows)
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
    return encoder


def encode_districts(rows: list[dict], encoder: OrdinalEncoder) -> np.ndarray:
    slugs = np.array([r["district_slug"] for r in rows], dtype=object).reshape(-1, 1)
    encoded = encoder.transform(slugs).ravel()
    if np.any(encoded < 0):
        raise SystemExit("STOP: unknown district in val/test — encoder must be train-only.")
    return encoded


def to_nan(value):
    if value is None:
        return np.nan
    if isinstance(value, str) and value.strip().lower() in {"", "null", "nan", "none"}:
        raise SystemExit(f"STOP: string missing marker {value!r}; expected JSON null → float NaN.")
    return float(value)


def design_matrix(rows: list[dict], feature_names: list[str], encoder: OrdinalEncoder) -> tuple[np.ndarray, np.ndarray]:
    encoded = encode_districts(rows, encoder)
    leakage = [c for c in feature_names if c in LEAKAGE_COLUMNS]
    if leakage:
        raise SystemExit(f"STOP: leakage columns in feature list: {leakage}")
    if TARGET_NAME in feature_names:
        raise SystemExit("STOP: target present in X")
    for name in feature_names:
        if name in FEATURE_COLUMNS or name == "district_encoded":
            continue
        raise SystemExit(f"STOP: feature {name} is not in the positivity contract")
    matrix = np.zeros((len(rows), len(feature_names)), dtype=float)
    for j, name in enumerate(feature_names):
        if name == "district_encoded":
            matrix[:, j] = encoded
            continue
        for i, row in enumerate(rows):
            if name not in row:
                raise SystemExit(f"STOP: feature {name} missing from row")
            matrix[i, j] = to_nan(row[name])
    if matrix.dtype != np.float64:
        raise SystemExit("STOP: expected float64 feature matrix")
    y = np.array([to_nan(r[TARGET_NAME]) for r in rows], dtype=float)
    if np.any(~np.isfinite(y)):
        raise SystemExit("STOP: non-finite target values")
    if np.any((y < 0) | (y > 1)):
        raise SystemExit("STOP: target outside [0, 1]")
    return matrix, y


def persistence_predict(rows: list[dict]) -> np.ndarray:
    preds = np.full(len(rows), np.nan, dtype=float)
    for i, row in enumerate(rows):
        value = row.get("malaria_positivity")
        if value is not None:
            preds[i] = float(value)
    return preds


def seasonal_predict(rows: list[dict], original_index: dict) -> np.ndarray:
    preds = np.full(len(rows), np.nan, dtype=float)
    for i, row in enumerate(rows):
        prior = calendar_prev(row["target_period"], 12)
        src = original_index.get((row["district_slug"], prior))
        if not src:
            continue
        value = positivity(src.get("malaria_confirmed"), src.get("malaria_tests"))
        if value is not None:
            preds[i] = value
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


def clip_rate(pred) -> np.ndarray:
    return np.clip(np.asarray(pred, dtype=float), 0.0, 1.0)


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
        pred = clip_rate(model.predict(X_val))
        score = metrics(y_val, pred)
        if best_val is None or score["mae"] < best_val["mae"] or (
            score["mae"] == best_val["mae"] and score["rmse"] < best_val["rmse"]
        ):
            best = model
            best_params = params
            best_val = score
    return best, best_params, best_val


def feature_sets() -> list[tuple[str, list[str]]]:
    core = list(POSITIVITY_CORE)
    return [
        ("positivity_persistence_features", core),
        ("positivity_plus_tests", core + ["malaria_tests"]),
        ("positivity_plus_climate", core + CLIMATE_LAGS),
        ("positivity_tests_climate", core + ["malaria_tests"] + CLIMATE_LAGS),
    ]


def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning)
    started = _utcnow()
    gbt_before = _sha256(SYNTHETIC_GBT)
    count_v1_before = _sha256(COUNT_V1_MODEL)
    panel_before = _sha256(ORIGINAL_PANEL)
    count_filtered_before = _sha256(COUNT_FILTERED)
    dataset_hash = _sha256(DATASET_PATH)

    rows = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if len(rows) != 504:
        raise SystemExit(f"STOP: expected 504 positivity rows, got {len(rows)}")
    splits = split_rows(rows)
    original_index = index_panel(load_original_panel(original_panel_path()))

    encoder = fit_district_encoder(splits["train"])
    train_districts = {r["district_slug"] for r in splits["train"]}
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
        print(
            f"HistGB {name}: val MAE={val_scores['mae']:.6f} "
            f"RMSE={val_scores['rmse']:.6f} R2={val_scores['r2']:.4f}"
        )

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

    evaluation = {
        "by_model": {},
        "feature_set_search": [
            {k: v for k, v in s.items() if k not in {"model", "X_train", "y_train", "X_val", "y_val"}}
            for s in selection
        ],
    }
    for fold_name, fold in fold_rows.items():
        X, y = fold_xy[fold_name]
        hist_pred = clip_rate(model.predict(X))
        persist = persistence_predict(fold)
        seasonal = seasonal_predict(fold, original_index)
        evaluation["by_model"].setdefault("positivity_persistence", {})[fold_name] = defined_metrics(y, persist)
        evaluation["by_model"].setdefault("seasonal_positivity_baseline", {})[fold_name] = defined_metrics(y, seasonal)
        evaluation["by_model"].setdefault("hist_gradient_boosting", {})[fold_name] = metrics(y, hist_pred)

    val_ml = evaluation["by_model"]["hist_gradient_boosting"]["validation"]
    val_persist = evaluation["by_model"]["positivity_persistence"]["validation"]
    val_seasonal = evaluation["by_model"]["seasonal_positivity_baseline"]["validation"]
    test_ml = evaluation["by_model"]["hist_gradient_boosting"]["test"]
    test_persist = evaluation["by_model"]["positivity_persistence"]["test"]

    perm = permutation_importance(
        model,
        chosen["X_val"],
        chosen["y_val"],
        n_repeats=20,
        random_state=RANDOM_STATE,
        scoring="neg_mean_absolute_error",
    )
    importance = [
        {
            "feature": name,
            "permutation_importance_mean_mae": float(mean_imp),
            "permutation_importance_std": float(std_imp),
        }
        for name, mean_imp, std_imp in sorted(
            zip(final_features, perm.importances_mean, perm.importances_std),
            key=lambda t: t[1],
            reverse=True,
        )
    ]

    train_mae = evaluation["by_model"]["hist_gradient_boosting"]["train"]["mae"]
    val_mae = val_ml["mae"]
    test_mae = test_ml["mae"]
    overfit_ratio = val_mae / train_mae if train_mae else None
    if overfit_ratio and overfit_ratio > 2.0 and val_mae > val_persist["mae"]:
        overfit_flag = "overfitting_and_no_lift"
        overfit_note = "Validation MAE is much higher than train and worse than positivity persistence."
    elif overfit_ratio and overfit_ratio > 1.8:
        overfit_flag = "some_overfitting"
        overfit_note = "Validation MAE is substantially higher than train MAE."
    elif val_mae > train_mae * 1.15:
        overfit_flag = "mild_gap"
        overfit_note = "Mild train/validation gap, typical for a small district-month panel."
    else:
        overfit_flag = "no_severe_overfitting"
        overfit_note = "Train and validation MAE are close."

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_DIR / "model.joblib")
    joblib.dump(encoder, OUTPUT_DIR / "district_encoder.joblib")

    feature_config = {
        "core_features": POSITIVITY_CORE,
        "climate_features": CLIMATE_LAGS,
        "optional_features_evaluated": ["malaria_tests"] + CLIMATE_LAGS,
        "final_features": final_features,
        "target": TARGET_NAME,
        "missing_value_policy": "preserve legitimate NaN values",
        "district_encoding": "train_fold_only",
        "feature_order": final_features,
        "prediction_clip": "[0, 1]",
        "not_included_due_to_redundancy": [
            "malaria_confirmed",
            "lag1_malaria_confirmed",
            "lag2_malaria_confirmed",
            "rolling_3_malaria_confirmed",
            "confirmed_change",
            "confirmed_pct_change",
            "lag1_malaria_tests",
            "testing_change",
            "testing_pct_change",
            "three_month_rainfall_accumulation",
        ],
    }
    (OUTPUT_DIR / "feature_config.json").write_text(json.dumps(feature_config, indent=2), encoding="utf-8")

    training_metadata = {
        "model_version": "malaria_positivity_forecast_v1",
        "training_timestamp": started,
        "dataset_path": str(DATASET_PATH.relative_to(BACKEND)),
        "dataset_sha256": dataset_hash,
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
        "count_forecast_v1_unmodified": True,
    }
    (OUTPUT_DIR / "training_metadata.json").write_text(json.dumps(training_metadata, indent=2), encoding="utf-8")

    val_lift_pct = 100.0 * (val_persist["mae"] - val_ml["mae"]) / val_persist["mae"] if val_persist["mae"] else 0.0
    test_lift_pct = 100.0 * (test_persist["mae"] - test_ml["mae"]) / test_persist["mae"] if test_persist["mae"] else 0.0
    beats_val_persist_mae = val_ml["mae"] < val_persist["mae"]
    beats_val_persist_rmse = val_ml["rmse"] < val_persist["rmse"]
    beats_test_persist_mae = test_ml["mae"] < test_persist["mae"]
    meaningful_val = beats_val_persist_mae and val_lift_pct >= 5.0 and beats_val_persist_rmse
    beats_seasonal = val_seasonal["mae"] is None or val_ml["mae"] < val_seasonal["mae"]

    if meaningful_val and beats_test_persist_mae:
        recommendation = "RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            f"Validation MAE improves {val_lift_pct:.1f}% vs positivity persistence "
            f"and untouched test MAE also beats persistence "
            f"({test_ml['mae']:.4f} vs {test_persist['mae']:.4f})."
        )
    elif meaningful_val and not beats_test_persist_mae:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            f"Validation MAE improves {val_lift_pct:.1f}% vs persistence, but the untouched test set "
            f"does not ({test_ml['mae']:.4f} vs persistence {test_persist['mae']:.4f})."
        )
    elif beats_val_persist_mae:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            f"Validation MAE is only {val_lift_pct:.1f}% below positivity persistence "
            f"({val_ml['mae']:.4f} vs {val_persist['mae']:.4f}); not a meaningful operational lift."
        )
    else:
        recommendation = "NOT RECOMMENDED FOR FURTHER VALIDATION"
        why = (
            "HistGradientBoosting does not beat positivity persistence on validation MAE "
            f"({val_ml['mae']:.4f} vs {val_persist['mae']:.4f})."
        )

    model_card = {
        "model_name": "malaria_positivity_forecast_v1",
        "purpose": "Forecast district-level malaria positivity (confirmed/tests) one calendar month ahead.",
        "intended_use": "Early-warning and preparedness decision support. Not a clinical diagnosis. Not a case-count forecast.",
        "data": {
            "source": "Historical DHIS2 malaria Analytics joined to Open-Meteo Archive monthly climate.",
            "filtered_rows": 504,
            "original_panel_rows": 535,
            "geography": "16 Sierra Leone districts.",
            "temporal_coverage": {
                "feature_periods": "202307–202602",
                "target_periods": "202308–202603",
            },
        },
        "features": final_features,
        "target": "malaria_confirmed(t+1) / malaria_tests(t+1) when tests(t+1) > 0",
        "algorithm": "HistGradientBoostingRegressor",
        "evaluation_split": training_metadata["split_strategy"],
        "primary_baseline": "positivity persistence: positivity(t)",
        "limitations": [
            "Positivity still depends on who seeks care, who is tested, and facility reporting.",
            "Typical facility completeness on kept pairs is about 0.60.",
            "HMIS Analytics returned no cells for 202604 and 202607; those months were not imputed.",
            "Relatively small district-month sample (504 rows, 16 districts, 32 feature months).",
            "Climate variables are Archive month t or earlier, not a forecast of t+1 weather.",
            "One-month-ahead forecasting model only.",
            "Not a causal model.",
            "Not a clinical diagnostic model.",
            "Not connected to the CHEWS dashboard or risk engine in this package.",
            "A successful fit is not evidence of usefulness unless the model beats positivity persistence.",
        ],
        "missing_data_policy": "Legitimate historical gaps remain NaN. Never filled with zero.",
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
        "baseline_comparison": {
            "validation_histgb_beats_persistence_mae": beats_val_persist_mae,
            "validation_mae_lift_vs_persist_pct": val_lift_pct,
            "validation_histgb_beats_persistence_rmse": beats_val_persist_rmse,
            "validation_histgb_beats_seasonal_mae": beats_seasonal,
            "test_histgb_beats_persistence_mae": beats_test_persist_mae,
            "test_mae_lift_vs_persist_pct": test_lift_pct,
            "test_persistence_mae": test_persist["mae"],
            "test_histgb_mae": test_ml["mae"],
            "full_table_persistence_mae_reference": 0.025689312169325584,
            "note": "The 0.026 figure is full-table persistence MAE. The decision metric requested is untouched test MAE vs test persistence.",
        },
        "leakage_audit": {
            "target_in_features": False,
            "encoder_fit_on": "train_fold_only",
            "test_used_for_model_selection": False,
            "nan_policy": "JSON null → numpy.nan",
        },
        "recommendation": recommendation,
        "recommendation_reason": why,
    }
    (OUTPUT_DIR / "evaluation.json").write_text(json.dumps(evaluation_doc, indent=2), encoding="utf-8")

    loaded_model = joblib.load(OUTPUT_DIR / "model.joblib")
    loaded_enc = joblib.load(OUTPUT_DIR / "district_encoder.joblib")
    X_te2, y_te2 = design_matrix(splits["test"], final_features, loaded_enc)
    preds = clip_rate(loaded_model.predict(X_te2))
    if len(preds) != 96:
        raise SystemExit(f"STOP: reloaded model produced {len(preds)} preds, expected 96")
    if not np.all(np.isfinite(preds)):
        raise SystemExit("STOP: non-finite predictions from saved model")
    if np.any((preds < 0) | (preds > 1)):
        raise SystemExit("STOP: predictions outside [0, 1]")
    reload_metrics = metrics(y_te2, preds)

    if _sha256(SYNTHETIC_GBT) != gbt_before:
        raise SystemExit("STOP: synthetic malaria_model.joblib hash changed")
    if _sha256(COUNT_V1_MODEL) != count_v1_before:
        raise SystemExit("STOP: malaria_forecast_v1 model.joblib hash changed")
    if _sha256(ORIGINAL_PANEL) != panel_before:
        raise SystemExit("STOP: original panel hash changed")
    if _sha256(COUNT_FILTERED) != count_filtered_before:
        raise SystemExit("STOP: count filtered dataset hash changed")
    if _sha256(DATASET_PATH) != dataset_hash:
        raise SystemExit("STOP: positivity dataset hash changed")

    print("\n=== malaria_positivity_forecast_v1 training complete (not integrated) ===")
    print("selected", chosen["feature_set"], final_features)
    print("val HistGB", val_ml)
    print("val persist", val_persist)
    print("val seasonal", val_seasonal)
    print("test HistGB", test_ml)
    print("test persist", test_persist)
    print("test MAE vs persist", test_ml["mae"], "vs", test_persist["mae"], "beats=", beats_test_persist_mae)
    print("reload test MAE", reload_metrics["mae"])
    print("recommendation", recommendation)
    print("output", OUTPUT_DIR)


if __name__ == "__main__":
    main()

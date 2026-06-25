"""
CHEWS Model Training Pipeline — Master Script
================================================
Trains all 4 ML models from raw Sierra Leone CSV data.

Run:
    cd backend
    python -m training.train_all_models

Steps:
    1. Data Loading & Exploration
    2. Data Preprocessing & Feature Engineering
    3. Train/Test Split
    4. Model Training
    5. Evaluation & Metrics
    6. Save Models to Disk
"""

import os
import sys
import warnings
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "trained_models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FLOOD_CSV = RAW_DIR / "CHEWS_SierraLeone_Flood_Dataset.csv"
MALARIA_CSV = RAW_DIR / "CHEWS_SierraLeone_Malaria_Dataset.csv"
COMMUNITY_CSV = RAW_DIR / "CHEWS_Community_Reports_Dataset(1).csv"
HEALTHCARE_CSV = RAW_DIR / "CHEWS_Healthcare_Readiness_Dataset.csv"

RANDOM_STATE = 42


def banner(text: str):
    """Print a visible step banner."""
    width = 70
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Data Loading & Exploration
# ═══════════════════════════════════════════════════════════════════════════
def step1_load_and_explore():
    """Load all datasets and print exploration summary."""
    banner("STEP 1: Data Loading & Exploration")

    datasets = {}

    # Load Flood dataset
    print("\n Loading Flood Dataset...")
    df_flood = pd.read_csv(FLOOD_CSV)
    datasets["flood"] = df_flood
    print(f"   Shape: {df_flood.shape}")
    print(f"   Columns: {list(df_flood.columns)}")
    print(f"   Target distribution (flood_occurred):")
    print(f"     {df_flood['flood_occurred'].value_counts().to_dict()}")
    print(f"   Null counts: {df_flood.isnull().sum().sum()}")

    # Load Malaria dataset
    print("\ Loading Malaria Dataset...")
    df_malaria = pd.read_csv(MALARIA_CSV)
    datasets["malaria"] = df_malaria
    print(f"   Shape: {df_malaria.shape}")
    print(f"   Columns: {list(df_malaria.columns)}")
    print(f"   Target stats (malaria_cases):")
    print(f"     Mean={df_malaria['malaria_cases'].mean():.1f}, "
          f"Median={df_malaria['malaria_cases'].median():.1f}, "
          f"Min={df_malaria['malaria_cases'].min()}, "
          f"Max={df_malaria['malaria_cases'].max()}")
    print(f"   Null counts: {df_malaria.isnull().sum().sum()}")

    # Load Community Reports dataset
    print("\n Loading Community Reports Dataset...")
    df_community = pd.read_csv(COMMUNITY_CSV)
    datasets["community"] = df_community
    print(f"   Shape: {df_community.shape}")
    print(f"   Columns: {list(df_community.columns)}")
    print(f"   Target distribution (reported_flooding):")
    print(f"     {df_community['reported_flooding'].value_counts().to_dict()}")
    print(f"   Null counts: {df_community.isnull().sum().sum()}")

    # Load Healthcare Readiness dataset
    print("\n Loading Healthcare Readiness Dataset...")
    df_healthcare = pd.read_csv(HEALTHCARE_CSV)
    datasets["healthcare"] = df_healthcare
    print(f"   Shape: {df_healthcare.shape}")
    print(f"   Columns: {list(df_healthcare.columns)}")
    print(f"   Target stats (readiness_score):")
    print(f"     Mean={df_healthcare['readiness_score'].mean():.3f}, "
          f"Median={df_healthcare['readiness_score'].median():.3f}, "
          f"Min={df_healthcare['readiness_score'].min()}, "
          f"Max={df_healthcare['readiness_score'].max()}")
    print(f"   Null counts: {df_healthcare.isnull().sum().sum()}")

    # Summary statistics
    print("\n" + "-" * 50)
    print("Summary Statistics")
    print("-" * 50)
    for name, df in datasets.items():
        print(f"\n--- {name.upper()} ---")
        print(df.describe().round(2).to_string())

    print("\n✅ Step 1 complete — all 4 datasets loaded successfully.")
    return datasets


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Data Preprocessing & Feature Engineering
# ═══════════════════════════════════════════════════════════════════════════
def step2_preprocess(datasets: dict):
    """Clean data, encode categoricals, engineer features."""
    banner("STEP 2: Data Preprocessing & Feature Engineering")

    processed = {}
    encoders = {}

    # --- Flood Dataset ---
    print("\n Processing Flood Dataset...")
    df = datasets["flood"].copy()

    # Encode drainage_quality: poor=0, moderate=1, good=2
    drainage_map = {"poor": 0, "moderate": 1, "good": 2}
    df["drainage_encoded"] = df["drainage_quality"].map(drainage_map)
    print(f"   Encoded drainage_quality: {drainage_map}")

    # Feature columns
    flood_features = [
        "rainfall_mm_24h", "temperature_c", "humidity_percent",
        "elevation_m", "water_level_m", "drainage_encoded",
        "soil_saturation", "community_reports"
    ]
    flood_target = "flood_occurred"

    # Interaction features
    df["rain_x_saturation"] = df["rainfall_mm_24h"] * df["soil_saturation"]
    df["rain_x_drainage"] = df["rainfall_mm_24h"] * (2 - df["drainage_encoded"])  # higher = worse drainage
    df["low_elevation_flag"] = (df["elevation_m"] < 50).astype(int)
    flood_features += ["rain_x_saturation", "rain_x_drainage", "low_elevation_flag"]

    processed["flood"] = {
        "X": df[flood_features],
        "y": df[flood_target],
        "features": flood_features,
    }
    print(f"   Features ({len(flood_features)}): {flood_features}")
    print(f"   Target: {flood_target}")
    print(f"   Class balance: {dict(df[flood_target].value_counts())}")

    # --- Malaria Dataset ---
    print("\n Processing Malaria Dataset...")
    df = datasets["malaria"].copy()

    # Encode district
    le_district_malaria = LabelEncoder()
    df["district_encoded"] = le_district_malaria.fit_transform(df["district"])
    encoders["malaria_district"] = le_district_malaria
    print(f"   Encoded {len(le_district_malaria.classes_)} districts: {list(le_district_malaria.classes_)}")

    malaria_features = [
        "rainfall_mm", "temperature_c", "humidity_percent",
        "water_stagnation_index", "mosquito_breeding_sites",
        "reported_fever_cases", "population_density", "district_encoded"
    ]
    malaria_target = "malaria_cases"

    # Interaction features
    df["rain_x_stagnation"] = df["rainfall_mm"] * df["water_stagnation_index"]
    df["temp_humidity_index"] = df["temperature_c"] * df["humidity_percent"] / 100
    df["breeding_density"] = df["mosquito_breeding_sites"] * df["water_stagnation_index"]
    malaria_features += ["rain_x_stagnation", "temp_humidity_index", "breeding_density"]

    processed["malaria"] = {
        "X": df[malaria_features],
        "y": df[malaria_target],
        "features": malaria_features,
    }
    print(f"   Features ({len(malaria_features)}): {malaria_features}")
    print(f"   Target: {malaria_target}")

    # --- Community Reports Dataset ---
    print("\n Processing Community Reports Dataset...")
    df = datasets["community"].copy()

    # Encode district and community
    le_district_comm = LabelEncoder()
    le_community = LabelEncoder()
    df["district_encoded"] = le_district_comm.fit_transform(df["district"])
    df["community_encoded"] = le_community.fit_transform(df["community"])
    encoders["community_district"] = le_district_comm
    encoders["community_community"] = le_community
    print(f"   Encoded {len(le_district_comm.classes_)} districts, {len(le_community.classes_)} communities")

    community_features = [
        "standing_water", "fever_reports", "damaged_houses",
        "displaced_households", "water_contamination",
        "district_encoded", "community_encoded"
    ]
    community_target = "reported_flooding"

    # Interaction features
    df["damage_displacement_index"] = df["damaged_houses"] * df["displaced_households"]
    df["total_impact"] = df["damaged_houses"] + df["displaced_households"] + df["water_contamination"]
    community_features += ["damage_displacement_index", "total_impact"]

    processed["community"] = {
        "X": df[community_features],
        "y": df[community_target],
        "features": community_features,
    }
    print(f"   Features ({len(community_features)}): {community_features}")
    print(f"   Target: {community_target}")
    print(f"   Class balance: {dict(df[community_target].value_counts())}")

    # --- Healthcare Readiness Dataset ---
    print("\n Processing Healthcare Readiness Dataset...")
    df = datasets["healthcare"].copy()

    # Encode district and facility_type
    le_district_hc = LabelEncoder()
    le_facility = LabelEncoder()
    df["district_encoded"] = le_district_hc.fit_transform(df["district"])
    df["facility_type_encoded"] = le_facility.fit_transform(df["facility_type"])
    encoders["healthcare_district"] = le_district_hc
    encoders["healthcare_facility_type"] = le_facility
    print(f"   Encoded {len(le_district_hc.classes_)} districts, {len(le_facility.classes_)} facility types: {list(le_facility.classes_)}")

    healthcare_features = [
        "beds_available", "health_workers", "malaria_medicine_stock",
        "power_availability", "water_availability", "patient_load",
        "district_encoded", "facility_type_encoded"
    ]
    healthcare_target = "readiness_score"

    # Interaction features
    df["resource_ratio"] = df["health_workers"] / (df["patient_load"] + 1)
    df["infrastructure_score"] = df["power_availability"] + df["water_availability"]
    df["capacity_utilization"] = df["patient_load"] / (df["beds_available"] + 1)
    healthcare_features += ["resource_ratio", "infrastructure_score", "capacity_utilization"]

    processed["healthcare"] = {
        "X": df[healthcare_features],
        "y": df[healthcare_target],
        "features": healthcare_features,
    }
    print(f"   Features ({len(healthcare_features)}): {healthcare_features}")
    print(f"   Target: {healthcare_target}")

    print("\n✅ Step 2 complete — all datasets preprocessed.")
    return processed, encoders


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Train/Test Split
# ═══════════════════════════════════════════════════════════════════════════
def step3_split(processed: dict):
    """Split all datasets into train/test sets."""
    banner("STEP 3: Train/Test Split (80/20)")

    splits = {}

    for name, data in processed.items():
        X, y = data["X"], data["y"]

        # Stratify for classification tasks
        stratify = y if name in ("flood", "community") else None

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=stratify
        )

        splits[name] = {
            "X_train": X_train, "X_test": X_test,
            "y_train": y_train, "y_test": y_test,
            "features": data["features"],
        }

        split_type = "stratified" if stratify is not None else "random"
        print(f"   {name:>15s}:  train={X_train.shape[0]:>4d}  test={X_test.shape[0]:>3d}  ({split_type})")

    print("\n✅ Step 3 complete — all splits created.")
    return splits


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Model Training
# ═══════════════════════════════════════════════════════════════════════════
def step4_train(splits: dict):
    """Train all 4 models with hyperparameter search."""
    banner("STEP 4: Model Training")

    models = {}

    # --- 4a: Flood Risk (GradientBoostingClassifier) ---
    print("\n Training Flood Risk Model (GradientBoostingClassifier)...")
    s = splits["flood"]

    flood_params = {
        "n_estimators": [100, 200],
        "max_depth": [3, 5],
        "learning_rate": [0.05, 0.1],
        "min_samples_split": [5, 10],
    }
    flood_base = GradientBoostingClassifier(random_state=RANDOM_STATE)
    flood_grid = GridSearchCV(
        flood_base, flood_params, cv=3, scoring="roc_auc", n_jobs=-1, verbose=0
    )
    flood_grid.fit(s["X_train"], s["y_train"])
    models["flood"] = flood_grid.best_estimator_
    print(f"   Best params: {flood_grid.best_params_}")
    print(f"   Best CV ROC-AUC: {flood_grid.best_score_:.4f}")

    # --- 4b: Malaria Cases (GradientBoostingRegressor) ---
    print("\n Training Malaria Cases Model (GradientBoostingRegressor)...")
    s = splits["malaria"]

    malaria_params = {
        "n_estimators": [100, 200],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.05, 0.1],
        "min_samples_split": [5, 10],
    }
    malaria_base = GradientBoostingRegressor(random_state=RANDOM_STATE)
    malaria_grid = GridSearchCV(
        malaria_base, malaria_params, cv=3, scoring="neg_mean_absolute_error",
        n_jobs=-1, verbose=0
    )
    malaria_grid.fit(s["X_train"], s["y_train"])
    models["malaria"] = malaria_grid.best_estimator_
    print(f"   Best params: {malaria_grid.best_params_}")
    print(f"   Best CV MAE: {-malaria_grid.best_score_:.4f}")

    # --- 4c: Community Reports (RandomForestClassifier) ---
    print("\n Training Community Reports Model (RandomForestClassifier)...")
    s = splits["community"]

    community_params = {
        "n_estimators": [100, 200],
        "max_depth": [5, 10, None],
        "min_samples_split": [2, 5],
        "min_samples_leaf": [1, 2],
    }
    community_base = RandomForestClassifier(random_state=RANDOM_STATE)
    community_grid = GridSearchCV(
        community_base, community_params, cv=3, scoring="roc_auc",
        n_jobs=-1, verbose=0
    )
    community_grid.fit(s["X_train"], s["y_train"])
    models["community"] = community_grid.best_estimator_
    print(f"   Best params: {community_grid.best_params_}")
    print(f"   Best CV ROC-AUC: {community_grid.best_score_:.4f}")

    # --- 4d: Healthcare Readiness (RandomForestRegressor) ---
    print("\n Training Healthcare Readiness Model (RandomForestRegressor)...")
    s = splits["healthcare"]

    healthcare_params = {
        "n_estimators": [100, 200],
        "max_depth": [5, 10, None],
        "min_samples_split": [2, 5],
        "min_samples_leaf": [1, 2],
    }
    healthcare_base = RandomForestRegressor(random_state=RANDOM_STATE)
    healthcare_grid = GridSearchCV(
        healthcare_base, healthcare_params, cv=3, scoring="r2",
        n_jobs=-1, verbose=0
    )
    healthcare_grid.fit(s["X_train"], s["y_train"])
    models["healthcare"] = healthcare_grid.best_estimator_
    print(f"   Best params: {healthcare_grid.best_params_}")
    print(f"   Best CV R²: {healthcare_grid.best_score_:.4f}")

    print("\n✅ Step 4 complete — all 4 models trained.")
    return models


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Evaluation & Metrics
# ═══════════════════════════════════════════════════════════════════════════
def step5_evaluate(models: dict, splits: dict):
    """Evaluate all models and print detailed metrics."""
    banner("STEP 5: Evaluation & Metrics")

    results = {}

    # --- 5a: Flood Risk ---
    print("\n Flood Risk Model Evaluation")
    print("-" * 40)
    s = splits["flood"]
    model = models["flood"]
    y_pred = model.predict(s["X_test"])
    y_proba = model.predict_proba(s["X_test"])[:, 1]

    acc = accuracy_score(s["y_test"], y_pred)
    prec = precision_score(s["y_test"], y_pred, zero_division=0)
    rec = recall_score(s["y_test"], y_pred, zero_division=0)
    f1 = f1_score(s["y_test"], y_pred, zero_division=0)
    auc = roc_auc_score(s["y_test"], y_proba)
    cm = confusion_matrix(s["y_test"], y_pred)

    print(f"   Accuracy:  {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall:    {rec:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {auc:.4f}")
    print(f"   Confusion Matrix:")
    print(f"     {cm[0]}")
    print(f"     {cm[1]}")

    # Feature importances
    importances = model.feature_importances_
    feat_imp = sorted(zip(s["features"], importances), key=lambda x: -x[1])
    print(f"\n   Feature Importances:")
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 40)
        print(f"     {feat:>25s}: {imp:.4f} {bar}")

    results["flood"] = {
        "accuracy": acc, "precision": prec, "recall": rec,
        "f1": f1, "roc_auc": auc, "feature_importances": dict(feat_imp),
    }

    # --- 5b: Malaria Cases ---
    print("\n\n🦟 Malaria Cases Model Evaluation")
    print("-" * 40)
    s = splits["malaria"]
    model = models["malaria"]
    y_pred = model.predict(s["X_test"])

    mae = mean_absolute_error(s["y_test"], y_pred)
    rmse = np.sqrt(mean_squared_error(s["y_test"], y_pred))
    r2 = r2_score(s["y_test"], y_pred)

    print(f"   MAE:  {mae:.4f} cases")
    print(f"   RMSE: {rmse:.4f} cases")
    print(f"   R²:   {r2:.4f}")
    print(f"   Mean actual: {s['y_test'].mean():.1f}, Mean predicted: {y_pred.mean():.1f}")

    importances = model.feature_importances_
    feat_imp = sorted(zip(s["features"], importances), key=lambda x: -x[1])
    print(f"\n   Feature Importances:")
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 40)
        print(f"     {feat:>25s}: {imp:.4f} {bar}")

    results["malaria"] = {
        "mae": mae, "rmse": rmse, "r2": r2,
        "feature_importances": dict(feat_imp),
    }

    # --- 5c: Community Reports ---
    print("\n\n📋 Community Reports Model Evaluation")
    print("-" * 40)
    s = splits["community"]
    model = models["community"]
    y_pred = model.predict(s["X_test"])
    y_proba = model.predict_proba(s["X_test"])[:, 1]

    acc = accuracy_score(s["y_test"], y_pred)
    prec = precision_score(s["y_test"], y_pred, zero_division=0)
    rec = recall_score(s["y_test"], y_pred, zero_division=0)
    f1 = f1_score(s["y_test"], y_pred, zero_division=0)
    auc = roc_auc_score(s["y_test"], y_proba)
    cm = confusion_matrix(s["y_test"], y_pred)

    print(f"   Accuracy:  {acc:.4f}")
    print(f"   Precision: {prec:.4f}")
    print(f"   Recall:    {rec:.4f}")
    print(f"   F1 Score:  {f1:.4f}")
    print(f"   ROC-AUC:   {auc:.4f}")
    print(f"   Confusion Matrix:")
    print(f"     {cm[0]}")
    print(f"     {cm[1]}")

    importances = model.feature_importances_
    feat_imp = sorted(zip(s["features"], importances), key=lambda x: -x[1])
    print(f"\n   Feature Importances:")
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 40)
        print(f"     {feat:>25s}: {imp:.4f} {bar}")

    results["community"] = {
        "accuracy": acc, "precision": prec, "recall": rec,
        "f1": f1, "roc_auc": auc, "feature_importances": dict(feat_imp),
    }

    # --- 5d: Healthcare Readiness ---
    print("\n\n🏥 Healthcare Readiness Model Evaluation")
    print("-" * 40)
    s = splits["healthcare"]
    model = models["healthcare"]
    y_pred = model.predict(s["X_test"])

    mae = mean_absolute_error(s["y_test"], y_pred)
    rmse = np.sqrt(mean_squared_error(s["y_test"], y_pred))
    r2 = r2_score(s["y_test"], y_pred)

    print(f"   MAE:  {mae:.4f}")
    print(f"   RMSE: {rmse:.4f}")
    print(f"   R²:   {r2:.4f}")
    print(f"   Mean actual: {s['y_test'].mean():.3f}, Mean predicted: {y_pred.mean():.3f}")

    importances = model.feature_importances_
    feat_imp = sorted(zip(s["features"], importances), key=lambda x: -x[1])
    print(f"\n   Feature Importances:")
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 40)
        print(f"     {feat:>25s}: {imp:.4f} {bar}")

    results["healthcare"] = {
        "mae": mae, "rmse": rmse, "r2": r2,
        "feature_importances": dict(feat_imp),
    }

    print("\n✅ Step 5 complete — all models evaluated.")
    return results


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: Save Models to Disk
# ═══════════════════════════════════════════════════════════════════════════
def step6_save(models: dict, encoders: dict, processed: dict, results: dict):
    """Serialize trained models and metadata."""
    banner("STEP 6: Save Models to Disk")

    saved_files = []

    for name, model in models.items():
        model_path = OUTPUT_DIR / f"{name}_model.joblib"
        joblib.dump(model, model_path)
        size_kb = model_path.stat().st_size / 1024
        saved_files.append(str(model_path))
        print(f"   💾 Saved {name} model → {model_path.name} ({size_kb:.1f} KB)")

    # Save label encoders
    encoders_path = OUTPUT_DIR / "label_encoders.joblib"
    joblib.dump(encoders, encoders_path)
    saved_files.append(str(encoders_path))
    print(f"   💾 Saved label encoders → {encoders_path.name}")

    # Save feature lists for each model
    feature_config = {
        name: data["features"] for name, data in processed.items()
    }
    config_path = OUTPUT_DIR / "feature_config.json"
    with open(config_path, "w") as f:
        json.dump(feature_config, f, indent=2)
    saved_files.append(str(config_path))
    print(f"   💾 Saved feature config → {config_path.name}")

    # Save training metadata
    metadata = {
        "trained_at": datetime.now().isoformat(),
        "random_state": RANDOM_STATE,
        "models": {},
    }
    for name in models:
        metadata["models"][name] = {
            "type": type(models[name]).__name__,
            "n_features": len(processed[name]["features"]),
            "features": processed[name]["features"],
        }
        # Add evaluation metrics
        if name in results:
            # Convert numpy types to native Python types for JSON serialization
            clean_results = {}
            for k, v in results[name].items():
                if k == "feature_importances":
                    clean_results[k] = {
                        feat: round(float(imp), 4)
                        for feat, imp in v.items()
                    }
                else:
                    clean_results[k] = round(float(v), 4)
            metadata["models"][name]["metrics"] = clean_results

    meta_path = OUTPUT_DIR / "training_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    saved_files.append(str(meta_path))
    print(f"   💾 Saved training metadata → {meta_path.name}")

    print(f"\n   📁 All files saved to: {OUTPUT_DIR}")
    print(f"   Total files: {len(saved_files)}")

    print("\n✅ Step 6 complete — all models saved to disk.")
    return saved_files


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Run all steps
# ═══════════════════════════════════════════════════════════════════════════
def main():
    """Run the complete training pipeline."""
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║  CHEWS Model Training Pipeline                                    ║")
    print("║  Climate-Health Early Warning System — Sierra Leone               ║")
    print("╚" + "═" * 68 + "╝")

    start_time = datetime.now()

    # Step 1: Load & Explore
    datasets = step1_load_and_explore()

    # Step 2: Preprocess
    processed, encoders = step2_preprocess(datasets)

    # Step 3: Split
    splits = step3_split(processed)

    # Step 4: Train
    models = step4_train(splits)

    # Step 5: Evaluate
    results = step5_evaluate(models, splits)

    # Step 6: Save
    saved_files = step6_save(models, encoders, processed, results)

    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║  🎉 TRAINING COMPLETE                                             ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Time elapsed: {elapsed:.1f}s{' ' * (52 - len(f'{elapsed:.1f}'))}║")
    print(f"║  Models trained: 4{' ' * 49}║")
    print(f"║  Files saved: {len(saved_files)}{' ' * (53 - len(str(len(saved_files))))}║")
    print("╚" + "═" * 68 + "╝")

    # Print a summary table
    print("\n📊 Model Performance Summary:")
    print("┌─────────────────────┬──────────┬──────────┬──────────┐")
    print("│ Model               │ Primary  │ Score    │ Status   │")
    print("├─────────────────────┼──────────┼──────────┼──────────┤")

    r = results["flood"]
    print(f"│ 🌊 Flood Risk       │ ROC-AUC  │ {r['roc_auc']:.4f}   │ ✅ Done  │")

    r = results["malaria"]
    print(f"│ 🦟 Malaria Cases    │ R²       │ {r['r2']:.4f}   │ ✅ Done  │")

    r = results["community"]
    print(f"│ 📋 Community Rpts   │ ROC-AUC  │ {r['roc_auc']:.4f}   │ ✅ Done  │")

    r = results["healthcare"]
    print(f"│ 🏥 Healthcare       │ R²       │ {r['r2']:.4f}   │ ✅ Done  │")

    print("└─────────────────────┴──────────┴──────────┴──────────┘")


if __name__ == "__main__":
    main()

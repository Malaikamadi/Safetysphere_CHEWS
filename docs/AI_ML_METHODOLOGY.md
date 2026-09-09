# CHEWS AI/ML methodology

This document describes **exactly** what the repository trains, loads, and serves. It does not claim outbreak prediction skill, clinical validity, or production MLOps.

**Summary:** The user-facing `/predict` path is a **weighted rule-based scorer**. Separate **experimental sklearn models** exist, trained on **synthetic** tables. One classifier is explicitly **blocked** for leakage. None of the models are validated against real Sierra Leone surveillance outcomes in this repository.

**Malaria GBT vs live DHIS2:** The trained malaria GradientBoostingRegressor is **not connected** to DHIS2 Analytics for inference. Its training target is synthetic `malaria_cases`; live HMIS uses `malaria_confirmed`. A historical district-month panel (`POST /api/dhis2/historical/panel`) is the path toward a **future** `malaria_confirmed(t+1)` model. Until that panel is **READY FOR MODEL TRAINING**, do not retrain or wire the existing GBT. See [DHIS2_ML_DATA_FOUNDATION.md](DHIS2_ML_DATA_FOUNDATION.md).

---

## Current approach

| Component | Type | Location | Serving path |
| --------- | ---- | -------- | ------------ |
| Composite malaria risk | Rule-based weighted sum | `backend/models/risk_engine.py` | `POST /predict` |
| Environmental sub-score | Heuristic (sigmoid/bell) | `backend/models/environmental.py` `predict_rule_based` | Used by risk engine |
| Environmental GBT | sklearn `GradientBoostingClassifier` + `CalibratedClassifierCV` | Trained **in memory at startup** on synthetic data labelled by the same heuristics | Comparison only; `predict()` returns the **rule-based** result |
| Epidemiological sub-score | Log-sigmoid + trend multipliers | `backend/models/epidemiological.py` | Risk engine |
| Exposure sub-score | Lookup tables | `backend/models/exposure.py` | Risk engine |
| Seasonal disease forecast | Climatological rules | `backend/services/forecast_engine.py` | `/healthcare/forecast`, `/forecast/live` |
| Flood, heat, AQI, carbon | Heuristics | `flood_risk.py`, `heat_stress.py`, `air_quality.py`, `carbon_accounting.py` | Strategic / early-warning routers |
| Flood GBT | `GradientBoostingClassifier` joblib | `data/trained_models/` | `flood_risk` if load succeeds |
| Malaria case regressor | `GradientBoostingRegressor` joblib | `malaria_predictor.py` | `POST /healthcare/ml/malaria-predict` |
| Facility readiness regressor | `RandomForestRegressor` joblib | `healthcare_readiness.py` | `POST /healthcare/ml/readiness-predict` |
| Community flood classifier | `RandomForestClassifier` joblib | `community_reports.py` | `POST /healthcare/ml/community-flood` — **do not treat as valid** |
| Triage | Symptom point totals | `services/triage_assistant.py` | `POST /poc/triage` |
| “AI explain” / assistant | Keyword / template text | `situation_room.py`, `main.py` `/ask` | Not machine learning |

**Not used as the live `/predict` model:** Logistic Regression (the previous README claimed this; the code does not).

---

## Input features

### A. Rule-based `/predict` (`PredictionInput` in `backend/main.py`)

| Feature | Meaning | Expected range (API) | Processing | Weight in composite | Role |
| ------- | ------- | -------------------- | ---------- | ------------------- | ---- |
| `rainfall` | Monthly-style rainfall (mm) | 0–500 | Environmental rainfall score | 40% of env; env is 40% of final | Anopheles breeding / transmission suitability |
| `temperature` | Air temperature (°C) | −10–55 | Environmental temperature score | 35% of env | Vector thermal niche |
| `humidity` | Relative humidity (%) | 0–100 | Environmental humidity score | 25% of env | Adult mosquito survival heuristic |
| `reported_cases` | Confirmed/suspected cases in a period | ≥ 0 integer | Log-sigmoid vs thresholds 3 / 10 / 25 / 50 | 40% of final (with trend) | Burden proxy |
| `trend` | `increasing` / `stable` / `decreasing` | enum | Multipliers 1.30 / 1.00 / 0.75 | Modifies epi score | Direction of transmission (assumed, not estimated Rₜ) |
| `vulnerable_population` | Count of high-risk people | ≥ 0 | Mapped into exposure vulnerability | Part of 20% exposure | Children &lt;5 / pregnancy proxy |
| `exposure_level` | `low` / `medium` / `high` | enum | Scores 0.20 / 0.55 / 0.90 | Part of 20% exposure | Nets, housing, water proximity (self-reported category) |

Environmental combination (`environmental.py`): rainfall 0.40, temperature 0.35, humidity 0.25, plus a 0.1 interaction boost if all three sub-scores &gt; 0.6.

Epidemiological thresholds (`CASE_THRESHOLDS`): baseline 3, alert 10, outbreak 25, emergency 50. These are **author-chosen constants**, not fitted from Sierra Leone DHIS2.

### B. Flood heuristic (`models/flood_risk.py`)

Typical inputs used by routers: rainfall intensity, 24h rainfall, elevation, drainage quality, proximity to water, soil saturation. Drainage maps `poor/moderate/good` → 0.85 / 0.50 / 0.15.

### C. Flood sklearn model (model card)

Features: `rainfall_mm_24h`, `temperature_c`, `humidity_percent`, `elevation_m`, `water_level_m`, `drainage_encoded`, `soil_saturation`, `community_reports`, `rain_x_saturation`, `rain_x_drainage`, `low_elevation_flag`.

Top importances (synthetic): rainfall 0.4367, humidity 0.3726, elevation 0.1024. Community reports importance is noted as zero in the model card.

### D. Malaria sklearn regressor (model card)

Features: `rainfall_mm`, `temperature_c`, `humidity_percent`, `water_stagnation_index`, `mosquito_breeding_sites`, `reported_fever_cases`, `population_density`, `district_encoded`, `rain_x_stagnation`, `temp_humidity_index`, `breeding_density`.

**No climate lag features** (model card). Malaria’s 2–4 week lag is therefore **not modelled**.

### E. Healthcare readiness sklearn regressor (model card)

Features: beds, health workers, malaria medicine stock, power, water, patient load, district/type encodings, `resource_ratio`, `infrastructure_score`, `capacity_utilization`.

Trained on **synthetic** `Facility_N`-style rows (`mfl_readiness_chews_v1.csv`, 100 rows). This is **not** the live MoH MFL used by the map.

### F. Community flood sklearn classifier (model card — BLOCKED)

Features include `standing_water`, `fever_reports`, `damaged_houses`, `displaced_households`, `water_contamination`, encodings, **`damage_displacement_index`**, **`total_impact`**. The card states these last two are likely derived from the target.

### G. Live forecast signals (not learned features)

`backend/routers/healthcare.py` `_LIVE_SIGNALS` — example malaria: rainfall 186, temperature 27.4, humidity 84, current_cases 142, previous_cases 108, aqi 38. These are **constants**, scaled by `_ADMIN_CASE_SCALE` for district filters.

---

## Prediction pipeline

### `/predict` (implemented)

```
JSON body
  → Pydantic ValidationError if out of range
  → environmental.predict_rule_based(rainfall, temperature, humidity)
  → epidemiological.predict(reported_cases, trend)
  → exposure.predict(vulnerable_population, exposure_level)
  → final_risk = 0.4*env + 0.4*epi + 0.2*exp
  → risk_level: Low if < 0.30; Medium if ≤ 0.60; else High
  → explanation string + factor list + canned recommendations
  → PredictionOutput JSON
```

`environmental.predict()` **always** returns the rule-based result even if a GBT was trained at startup (`environmental.py` public `predict`).

### Live forecast (implemented, prototype data)

```
GET /healthcare/forecast/live?disease=&admin=
  → lookup _LIVE_SIGNALS[disease]
  → scale cases by district factor
  → forecast_engine.forecast_disease(month, climate, cases, aqi)
  → JSON for the dashboard (no user-entered climate)
```

### sklearn malaria POST (experimental)

```
POST /healthcare/ml/malaria-predict
  → malaria_predictor.predict(...)
  → joblib GradientBoostingRegressor if file loads
  → else printed heuristic fallback
  → predicted_cases, risk_level via CASE_THRESHOLDS 15 / 30 / 45
```

---

## Training

### Script

`backend/training/train_all_models.py`

- Expects CSVs under `backend/data/raw/` (`CHEWS_SierraLeone_Flood_Dataset.csv`, malaria, community, healthcare). Parallel copies also exist under `01_raw/` with different names.  
- `RANDOM_STATE = 42`.  
- `train_test_split` 80/20.  
- Writes `backend/data/trained_models/`.  
- Requires **pandas** (`requirements-dev.txt`), not listed in runtime `requirements.txt`.

### Dataset

| Model | Rows (cards/catalog) | Source file (card) | Real vs synthetic |
| ----- | -------------------- | ------------------ | ----------------- |
| Flood GBT | 300 | `01_raw/climate/chews_flood_features_v1.csv` | Synthetic (catalog) |
| Malaria GBT | 500 | `01_raw/dhis2/dhis2_malaria_chews_v1.csv` | Synthetic despite “dhis2” in the name |
| Readiness RF | 100 | `01_raw/master_facility_list/mfl_readiness_chews_v1.csv` | Synthetic |
| Community RF | 500 | `01_raw/community_reports/community_reports_chews_202607.csv` | Synthetic |

Sample malaria CSV values are continuous floats (e.g. rainfall `141.66840222548586`) consistent with a generator, not a DHIS2 export.

### Algorithms and parameters (from training / model cards)

| Model | Class | Notable params | Split |
| ----- | ----- | -------------- | ----- |
| Flood | GradientBoostingClassifier | Card does not list full hyperparameters; training script uses sklearn ensembles | 80/20 stratified |
| Malaria | GradientBoostingRegressor | As trained 2026-06-25 | 80/20 random |
| Readiness | RandomForestRegressor | 100 samples | 80/20 random |
| Community | RandomForestClassifier | — | 80/20 stratified |
| In-process env GBT | `n_estimators=100`, `max_depth=4`, `learning_rate=0.1`, `random_state=42`, `CalibratedClassifierCV(cv=3)` | Labels from `predict_rule_based` | 80/20 stratified |

GridSearchCV is imported in the training script; **whether every model used a search is not fully restated in the model cards.** Treat exact searched grids as **not fully verifiable** without re-running and inspecting the script’s per-model blocks.

### Evaluation (as recorded — synthetic holdout only)

| Model | Metrics in repo | Interpretation |
| ----- | ---------------- | -------------- |
| Flood | accuracy 0.9667, precision 1.0, recall 0.8947, F1 0.9444, ROC AUC 0.991 | Model card: possible overfitting; synthetic |
| Malaria | MAE 5.7288, RMSE 6.7074, R² 0.6177 | Moderate fit on synthetic; unexplained variance |
| Readiness | MAE 0.0373, RMSE 0.0484, R² 0.8811 | Target was pre-computed; 100 rows |
| Community | all metrics 1.0 | **Leakage / deterministic target**; `review_status`: BLOCKED |
| Env GBT | printed `score` on synthetic test | Trained to clone the rules |

There is **no** external test set, **no** temporal validation, **no** facility-level outcome study, **no** comparison to MoH surveillance.

---

## Synthetic data

**What it is:** Tables generated for CHEWS training (`DATA_CATALOG.md` labels DHIS2, MFL readiness, flood features, and community reports as synthetic / CHEWS training data).

**Why it is used in the MVP:** To demonstrate an end-to-end train → joblib → HTTP predict loop without waiting for data-sharing agreements.

**What it can demonstrate:** Engineering of feature pipelines, API wiring, model-card discipline, and UI for “a number appeared.”

**What it cannot demonstrate:** Skill at predicting real malaria cases, floods, or facility readiness in Sierra Leone; calibration; fairness across districts; operational false-alert rates.

**Why real-world validation is required:** Climate–malaria relationships are lagged, spatially structured, and confounded by treatment, nets, and reporting completeness. A model that fits a generator will not automatically fit DHIS2.

The **MoH DHIS2 core facility CSV** is a different class of data: real **identity and coordinates**, not a training label set. It is not used to train the readiness regressor.

---

## Explainability

- Rule engines emit human-readable `factors` strings (threshold crossings).  
- sklearn endpoints return `feature_contributions` where implemented (importances or local attributions as coded — inspect each wrapper).  
- Situation Room `GET /situation-room/ai-explain/{hazard_type}` is **template text over simulated state**, not model SHAP.  
- There is no documented SHAP/LIME dependency in `requirements.txt`.

---

## Model limitations

| Theme | Fact in this repo |
| ----- | ----------------- |
| Dataset | Almost all ML tables are synthetic; n is small (100–500) |
| Generalization | No external validation set |
| Bias | District encodings on synthetic names; live MFL has 16 districts including Falaba/Karene that malaria `DISTRICTS` list may not match |
| Clinical validation | Absent |
| Epidemiological validation | Absent |
| Feature set | No immunity, EIR, larval habitat maps, intervention coverage, true lags |
| Temporal | Independent rows; no week-ahead forecast evaluation |
| Geographic | Named Sierra Leone districts but not fitted to official time series |
| False positives/negatives | Cannot be estimated from synthetic perfect/near-perfect scores |
| Community model | Explicitly invalid until leakage is removed |
| Live dashboard | Does not call the malaria GBT; uses `forecast_engine` + constants |
| Reproducibility of “live” flood | Open-Meteo when reachable; else time-bucketed random wobble (`flood_dashboard.py`) |

**Do not describe CHEWS as predicting actual malaria outbreaks.** The repository contains no evidence that it can.

---

## Future model development (planned)

A realistic path, **not implemented**:

1. Historical DHIS2 weekly confirmed malaria (and completeness metadata).  
2. Climate with epidemiologically relevant lags (rainfall, temperature, humidity, NDVI if justified).  
3. Facility-level or chiefdom-level series, not only district.  
4. Community reports with independent labels (not features derived from the label).  
5. Proper validation: temporal holdout, spatial cross-validation, comparison to simple seasonal baselines.  
6. Monitoring: prediction vs eventually reported cases; recalibration.  
7. Governance: model cards updated; blocked models not exposed as “AI.”

Until then, treat sklearn endpoints as **experimental demonstrations**.

# CHEWS malaria forecast model design

**Status:** design + quality-filtered training table only. **No model has been trained.**  
**Existing GBT:** `data/trained_models/malaria_model.joblib` is unchanged and is not used.  
**Original panel:** `malaria_district_month_panel_latest.json` is unchanged.

Target: **next-calendar-month confirmed malaria count** (`target_malaria_confirmed_next_period` = `malaria_confirmed` at calendar month t+1).

Filter module (training and later inference share calendar/lag logic): `backend/services/malaria_forecast.py`.

---

## 1. Filtered training dataset

Source panel (untouched): 535 district-month rows, 503 marked `trainable` under the old “next observed row” rule.

Derived file: `backend/data/04_ai/training_sets/malaria_forecast_v1_filtered.json`  
Report: `backend/data/04_ai/training_sets/malaria_forecast_v1_filter_report.json`

Rules applied (no imputation, no zeros for missing HMIS):

| Rule | Effect |
| ---- | ------ |
| `facility_completeness(t) ≥ 0.20` | 6 rows removed |
| `facility_completeness(t+1) ≥ 0.20` | 3 rows removed |
| Target must be **calendar** t+1 | 22 rows removed (`202604`/`202607` holes and other skips) |
| Other | 0 |

| Metric | Value |
| ------ | ----- |
| Original panel rows | **535** |
| Original “trainable” (legacy next-observed) | **503** |
| Removed for low completeness (t or t+1) | **9** |
| Removed for non-consecutive / missing calendar target | **22** |
| **Final training rows** | **504** |
| Districts | **16** (all) |
| Feature months | **32**: `202307`–`202602` |
| Target months | **32**: `202308`–`202603` |
| Date range | features `202307`→`202602`; targets `202308`→`202603` |

`202604` and `202607` remain missing. Sparse `202605`/`202606`/`202608` pairs fail completeness and/or calendar continuity and are **not** in the filtered table.

**Completeness after filter**

| | Feature period t | Target period t+1 |
| --- | --- | --- |
| Minimum | 0.222 | 0.222 |
| Median | 0.635 | 0.635 |
| Mean | 0.605 | 0.601 |
| Maximum | 0.745 | 0.745 |

The old 503 included six leap pairs (e.g. `202603`→`202605`) that looked like 95% case collapses. Those are gone.

Final count (504) is slightly *above* 503 because the new rule does **not** require lag-1 for inclusion; `202307` rows are kept with `lag1_malaria_confirmed = null` (month `202306` was never extracted).

---

## 2. Final feature set

Present on the filtered table (fraction non-null):

| Feature | Non-null | Use in v1 |
| ------- | -------- | --------- |
| `malaria_confirmed` (at t) | 100% | **Yes** — current month count |
| `lag1_malaria_confirmed` (t−1 calendar) | 96.8% | **Yes** |
| `lag2_malaria_confirmed` (t−2 calendar) | 93.7% | Yes, allow missing |
| `rolling_3_malaria_confirmed` (mean t, t−1, t−2) | 93.7% | Yes, allow missing |
| `malaria_tests` | 100% | **Yes** — testing effort |
| `malaria_rdt_positive` | 84.1% | Optional; missing kept null |
| `rdt_positivity` | 84.1% | Optional; undefined if tests = 0 |
| `rainfall_mm`, `temperature_c`, `humidity_percent` (month t) | 100% | **Yes** |
| `calendar_month` (1–12) | 100% | **Yes** |
| `district_slug` | 100% | Encode **after** the time split, train-only fit |

**Not included** (no legitimate live feed): `water_stagnation_index`, `mosquito_breeding_sites`, `reported_fever_cases`, `population_density`.

**Core v1 vector (conservative):**  
`malaria_confirmed`, `lag1_malaria_confirmed`, `malaria_tests`, `rainfall_mm`, `temperature_c`, `humidity_percent`, `calendar_month`, `district_encoded`  
plus optional `lag2_malaria_confirmed`, `rolling_3_malaria_confirmed`, `rdt_positivity`.

---

## 3. Target definition

**Name:** `target_malaria_confirmed_next_period`  
**Meaning:** Next-calendar-month confirmed malaria count.  
**Source field:** DHIS2 `malaria_confirmed` (`XHQqFqfUfIf`) on the district row for month t+1.  
**Not used as target:** `malaria_cases`, `reported_fever_cases`, `malaria_confirmed_u5`, `child_malaria_death`.

---

## 4. Leakage audit

Forecast is issued when **month t** health and climate are known; the quantity to predict is month **t+1**.

| Feature | Time | Known before t+1 HMIS? | Contains t+1? | Safe? |
| ------- | ---- | ---------------------- | ------------- | ----- |
| `malaria_confirmed` | t | Yes, once t is reported | No | Yes |
| `lag1` / `lag2` | t−1 / t−2 calendar | Yes | No | Yes (calendar lags, not “previous leftover facility”) |
| `rolling_3` | mean of t, t−1, t−2 | Yes | No | Yes |
| `malaria_tests`, `malaria_rdt_positive`, `rdt_positivity` | t | Yes | No | Yes — do not use t+1 tests |
| Climate trio | Archive month **t** | Yes for a t+1 forecast after t closes | No if t+1 climate is not a feature | Yes |
| `calendar_month` | t | Yes | No | Yes |
| District | identity | Yes | No | Yes if encoder fit on **train districts only** |
| **Target** | t+1 | No | — | Must not enter X |

**Unsafe if added later:** climate for t+1, `malaria_confirmed` at t+1, rolling windows that include t+1, encoding fit on the test set, or using legacy `malaria_confirmed_next` (next *observed* row).

---

## 5. Feature engineering architecture

Single module: `services/malaria_forecast.py`.

| Operation | Training | Live inference |
| --------- | -------- | -------------- |
| Completeness filter | Drop pairs below 0.20 | Set `data_quality_flag`; do not predict if t incomplete |
| Calendar target | Require row at t+1 | Predict t+1; no skipped-month target |
| Lags / rolling | Calendar t−1, t−2 from **original** panel index | Same lookup on latest curated district-month |
| `rdt_positivity` | `rdt/tests` if tests ≠ 0 else null | Same |
| Missing | Stay null; never 0-fill HMIS | Same |
| District encoding | Fit on training fold only; persist encoder | Apply saved encoder; unknown district → flagged, not silently 0 |

Do not copy formulas into `malaria_predictor.py`. That file stays the synthetic prototype.

---

## 6. Candidate models

Do not pick GradientBoosting just because v0 did.

| Candidate | Role |
| --------- | ---- |
| Naive: ŷ(t+1) = y(t) | Baseline 1 |
| Seasonal naive: ŷ(t+1) = y(same month last year) | Baseline 2 |
| Ridge / Poisson / Tweedie on `log1p` counts | Linear, interpretable |
| `HistGradientBoostingRegressor` | Primary ML — native missing-value support (lags at series start, RDT gaps) |
| RandomForest / ExtraTrees | Backup if complete-case (drop null lags) is preferred |
| Light GBT (`GradientBoostingRegressor`) | Optional comparison only |

Counts are non-negative, overdispersed, seasonal. HistGradientBoosting + a Poisson/Tweedie linear model are the best first ML pair on **this** panel.

---

## 7. Baselines

1. **Persistence:** next month = current month (`malaria_confirmed` at t).  
2. **Seasonal naive:** next month = same calendar month previous year when that district-month exists on the original panel.

An ML model is useful only if it beats **both** on the time-based test set (MAE/RMSE, and high-count months). If it does not, ship the better baseline.

---

## 8. Time-based evaluation

No random 80/20.

Filtered feature months: 32 (`202307`–`202602`). Proposed split **by feature_period**:

| Fold | Feature months | Target months | Approx. rows |
| ---- | -------------- | ------------- | ------------ |
| Train | `202307`–`202412` | `202308`–`202501` | ~18 × 16 |
| Validation | `202501`–`202508` | `202502`–`202509` | ~8 × 16 |
| Test | `202509`–`202602` | `202510`–`202603` | ~6 × 16 |

Fit encoder and any scaler on **train only**. Validation is for model class / depth. Test once.

`202402`–`202404` stay in train (completeness still ≥ 0.20) but should be discussed as a milder reporting dip.

---

## 9. Metrics

| Metric | Why |
| ------ | --- |
| **MAE** | Typical error in cases; robust for DHMT interpretation |
| **RMSE** | Penalises large misses (outbreak months) |
| **R²** | Variance explained vs mean; secondary only |
| **sMAPE or MAE/mean** | Prefer over MAPE: zeros and tiny sparse counts would explode MAPE; filtered data still can have low months |
| Later (not now) | Directional hit (up/down vs t), calibration of high-count tail, threshold exceedance once CHEWS sets action thresholds |

Do not invent Low/Medium/High cutoffs inside training.

---

## 10. Model output contract

```
district_id
district_name
feature_period          # t
forecast_period         # t+1
predicted_malaria_confirmed
prediction_timestamp
model_version           # malaria_forecast_v1
data_quality_flag       # ok | low_completeness | missing_lag | ...
feature_facility_completeness
```

Uncertainty: omit until a method is real (e.g. quantile HistGB). Do not invent confidence percentages.

Risk engine stays separate: it may later map the predicted count + climate into Low/Medium/High.

---

## 11. Model versioning

Do **not** overwrite `data/trained_models/malaria_model.joblib`.

Future training (not done) should write:

```
backend/data/04_ai/models/malaria_forecast_v1/
  model.joblib
  district_encoder.joblib
  feature_config.json
  training_metadata.json
  model_card.json
  evaluation.json
```

---

## 12. Model card structure (to fill after training)

- Purpose: district-month forecast of confirmed malaria for next calendar month  
- Target, training data paths, 16 districts, `202307`–`202603` targets after filter  
- Features, preprocessing, algorithm, time split, MAE/RMSE/R² vs baselines  
- Missing-data policy (null ≠ 0), completeness ≥ 0.20, known 2026 HMIS holes  
- Bias: reporting intensity (`malaria_tests`); incomplete current year  
- Intended use: early-warning **input**, not a clinical diagnosis  
- Prohibited: replacing HMIS, silent use of synthetic GBT features, predicting from 1-facility months  

---

## 13. Recommended model

**Train later:** `HistGradientBoostingRegressor` (sklearn) for the count, plus the two baselines. Compare Poisson/Tweedie regression on the same split.

Rationale: monthly district panel, missing lags at the start, optional RDT holes, CPU-only, no need to copy the synthetic GBT.

---

## 14. Risks and limitations

- Counts track **reporting** as well as transmission; `malaria_tests` is a covariate, not a cure.  
- Completeness typically ~60% of facilities, not 100%.  
- No `202604`/`202607`; forecast across those months needs an explicit quality flag, not a skipped-month target.  
- Climate is month-t Archive, not a weather forecast of t+1.  
- 16 districts × ~32 months is small; trees can overfit without the time split and baselines.  
- Synthetic GBT contract is incompatible and must stay isolated.

---

## 15. Files created now vs later training

**Created now (no weights):**

- `backend/services/malaria_forecast.py` — filter + calendar lags/rolling  
- `backend/tests/test_malaria_forecast_filter.py`  
- `backend/data/04_ai/training_sets/malaria_forecast_v1_filtered.json`  
- `backend/data/04_ai/training_sets/malaria_forecast_v1_filter_report.json`  
- `docs/MALARIA_FORECAST_MODEL_DESIGN.md` (this file)

**Must not change at training time:**

- `backend/data/04_ai/training_sets/malaria_district_month_panel_latest.json`  
- `backend/data/trained_models/malaria_model.joblib`  
- `backend/models/malaria_predictor.py`  
- `backend/training/train_all_models.py`

**To create only when training is approved:**

- `backend/data/04_ai/models/malaria_forecast_v1/*`  
- a new training script e.g. `backend/training/train_malaria_forecast_v1.py` (not `train_all_models.py`)

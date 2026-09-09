# Malaria positivity forecast — target contract

**Status:** design + derived dataset only. **No model has been trained.**  
**Do not** overwrite `malaria_forecast_v1` artifacts, `malaria_model.joblib`, or the 535-row original panel.

---

## TARGET

**Name:** `target_malaria_positivity_next_period`

**Formula:**

```
malaria_confirmed(t+1) / malaria_tests(t+1)
```

**Defined only when** `malaria_tests(t+1) > 0`.  
If tests at t+1 are missing or ≤ 0, the row is **excluded**. Values are never filled with zero.

Verified on the source panel for every kept pair: tests(t+1) > 0 (0 rows dropped for non-positive target tests).

---

## Prediction horizon

One **calendar** month ahead.

- `feature_period` = t  
- `target_period` = exact calendar t+1  

Never “next observed row.” A missing t+1 (including `202603` → `202605`) excludes the row.

---

## Prediction cutoff

**End of month t**, after month-t DHIS2 Analytics and Open-Meteo Archive climate for month t are available.

All features are constructed from t, t−1, t−2, or earlier. **No t+1 health or climate values in X.**

---

## Completeness

Keep a pair only if:

```
facility_completeness(t)  ≥ 0.20
AND
facility_completeness(t+1) ≥ 0.20
```

Applied only when building this derived table. The original panel is unchanged.

---

## Missing value policy

Preserve legitimate NaN. Do not fabricate `202306`. Do not impute lags or climate accumulation with zero.

Examples:

- `lag1_*` and change features are null when t−1 is absent (`202307`).
- `three_month_rainfall_accumulation` is null unless rainfall exists at t, t−1, and t−2.

---

## Dataset

| Item | Path |
| ---- | ---- |
| Derived table | `backend/data/04_ai/training_sets/malaria_positivity_forecast_v1.json` |
| Filter report | `backend/data/04_ai/training_sets/malaria_positivity_forecast_v1_filter_report.json` |
| Analysis (no model) | `backend/data/04_ai/training_sets/malaria_positivity_forecast_v1_pretraining_analysis.json` |
| Builder | `backend/services/malaria_positivity_forecast.py` |
| Entry point | `python -m training.build_malaria_positivity_forecast_v1` |

**Not modified:** `malaria_forecast_v1_filtered.json` (count target).

**Not created:** `backend/data/04_ai/models/malaria_positivity_forecast_v1/` (wait for training phase).

---

## Feature contract (X)

District encoding is **not** fit in this phase. Pass `district_slug`; encode later on the **train fold only**.

### Stored candidate columns

Epidemiological: `malaria_confirmed`, `lag1_malaria_confirmed`, `lag2_malaria_confirmed`, `rolling_3_malaria_confirmed`, `confirmed_change`, `confirmed_pct_change`

Testing: `malaria_tests`, `lag1_malaria_tests`, `testing_change`, `testing_pct_change`

Positivity (time t only): `malaria_positivity` (= confirmed(t)/tests(t) if tests(t)>0), `lag1_malaria_positivity`, `positivity_change`

Climate (≤ t): `rainfall_mm`, `lag1_rainfall_mm`, `lag2_rainfall_mm`, `three_month_rainfall_accumulation` (= rain(t)+rain(t−1)+rain(t−2)), `temperature_c`, `lag1_temperature_c`, `humidity_percent`, `lag1_humidity_percent`, `calendar_month`

Geographic: `district_slug`

### Prohibited in X

- `malaria_confirmed(t+1)`, `malaria_tests(t+1)`, positivity(t+1)
- `malaria_confirmed_next` / non-calendar next
- climate at t+1
- the target column itself

Confirmed(t+1) and tests(t+1) are **not stored** on the derived rows, so they cannot leak into a feature list by accident. The target stores only the ratio.

### Redundancy (do not auto-include everything at train time)

Raw confirmed counts, tests, and rolling_3 are highly collinear (|r| ≥ 0.90). Confirmed change tracks testing change. Prefer positivity-level features plus a small climate/season set; treat raw tests as an **effort covariate**, not a transmission measure.

---

## Persistence baselines (not models)

- **Positivity persistence:** predict positivity(t) when tests(t) > 0.  
- **Seasonal:** positivity at calendar month t+1−12 from the original panel, undefined if that month or tests are missing. Do not fabricate.

---

## Known limitations (contract)

- Positivity still depends on who seeks care, who is tested, and which facilities report.
- Typical facility completeness on kept pairs is ~0.60.
- `202604` and `202607` remain missing in the source extract.
- This is not a clinical diagnostic target and not a causal climate model.

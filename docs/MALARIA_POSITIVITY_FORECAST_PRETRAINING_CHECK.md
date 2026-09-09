# Malaria positivity forecast — pre-training technical check

**Phase:** target redefinition + derived dataset. **No model trained.**  
**Existing count model:** `malaria_forecast_v1` artifacts unchanged.  
**Existing GBT:** `backend/data/trained_models/malaria_model.joblib` unchanged.

---

## 1. Target definition

| | |
| - | - |
| Name | `target_malaria_positivity_next_period` |
| Formula | `malaria_confirmed(t+1) / malaria_tests(t+1)` |
| Condition | `malaria_tests(t+1) > 0` only |
| Horizon | one calendar month |
| Cutoff | end of feature month t |
| Alignment | exact calendar t+1; never next-observed |

Source verification: every kept pair was recomputed from the original panel. **0** rows had tests(t+1) ≤ 0. **0** reconstructed ratios disagreed with the stored target.

---

## 2. Number of rows

**504** derived rows from the **535**-row original panel.

| Exclusion | Rows |
| --------- | ---: |
| Low completeness at t | 6 |
| Low completeness at t+1 | 3 |
| Missing calendar t+1 | 22 |
| Missing target tests | 0 |
| Target tests ≤ 0 | 0 |

Same inclusion grid as the count-filtered table; positivity did not drop extra rows.

---

## 3. District coverage

**16** Sierra Leone districts, all present.

Row counts: most districts **32**; Bo and Port Loko **30**; Koinadugu **28** (202401–202404 completeness filter).

---

## 4. Feature-month coverage

**32** feature months: `202307`–`202602`  
**32** target months: `202308`–`202603`

`202604` / `202607` remain absent in the source extract and were not imputed.

---

## 5. Target distribution

| Statistic | Value |
| --------- | ----: |
| n | 504 |
| Min | 0.341 |
| Max | 0.795 |
| Mean | 0.643 |
| Median | 0.643 |
| Std. dev. | 0.068 |
| Skewness | −0.42 |
| Zeros | **0** |
| Null targets | **0** |
| Values outside [0, 1] | **0** |

No clipping. Investigation stop-rule was not triggered.

**By district (mean target positivity):** Moyamba 0.753, Western Area Rural 0.711, Kambia 0.708, Bonthe 0.701, … Kono 0.556, Kailahun 0.545. District means span about **0.21**, much narrower than raw counts (which spanned thousands of cases).

**By calendar month of t (mean target = positivity at t+1):** lowest Feb/Mar (~0.615); highest Oct/Nov (~0.658–0.660). Seasonal amplitude is modest (~4–5 percentage points).

---

## 6. Missingness

Legitimate calendar gaps only. Not filled with zero.

| Field | Null rows | Notes |
| ----- | --------: | ----- |
| lag1 confirmed / tests / positivity / climate | 16 | all `202307` (no 202306) |
| lag2 confirmed / rainfall; rolling_3; 3-month rain | 32 | t−2 absent |
| malaria_positivity(t) | 0 | tests(t) > 0 on all kept rows |
| target positivity | 0 | |

`confirmed_pct_change` and `testing_pct_change` require lag1; they share the 16 nulls.

---

## 7. Completeness

Threshold **0.20** at t and t+1.

| | Feature t | Target t+1 |
| - | --------: | ---------: |
| Min | 0.222 | 0.222 |
| Median | 0.635 | 0.635 |
| Mean | 0.605 | 0.601 |
| Max | 0.745 | 0.745 |

Kept months still omit ~40% of expected facilities on average.

---

## 8. Persistence baseline availability

`positivity(t)` is defined on **all 504** rows (tests(t) > 0 everywhere in this table).

| Metric (full 504) | Persistence: ŷ = positivity(t) |
| ----------------- | -----------------------------: |
| MAE | 0.0257 |
| RMSE | 0.0390 |
| R² | 0.671 |
| Coverage | 100% |

This is the baseline a future model must beat. It is **not** a trained model.

---

## 9. Seasonal baseline availability

ŷ = positivity at calendar **t+1−12**, from the original panel, only if that month exists and tests > 0.

| | |
| - | -: |
| Defined | 336 / 504 (66.7%) |
| Undefined | 168 (no fabrication) |
| MAE (defined only) | 0.0420 |
| RMSE | 0.0566 |
| R² | 0.216 |
| Pearson r vs target | 0.672 |

Weaker and incomplete compared with month-to-month persistence.

---

## 10. Positivity autocorrelation

| Scope | n | r(positivity(t), positivity(t+1)) |
| ----- | -: | --------------------------------: |
| Pooled | 504 | **0.839** |
| Within-district (16 districts, n≥28) | — | min **0.26**, median **0.55**, mean **0.56**, max **0.76** |

Previous **raw-count** persistence (same pairs): pooled r = **0.936**; within-district median ~0.63.

Positivity is still persistent, but:

- less inflated by district *size* (count variance was 81% between districts);
- within-district r is lower on average (0.56 vs 0.63);
- month-to-month MAE of ~2.6 percentage points on a ~64% mean rate is non-trivial relative to within-district std (0.018–0.065).

**Can ML add early warning?** Possibly, where within-district persistence is weaker (e.g. Port Loko r = 0.26, Kenema 0.33). It is **not** guaranteed: pooled persistence R² is already 0.67. That is a training-phase question, not a contract blocker.

---

## 11. Climate associations (descriptive only)

Pearson r vs **target positivity(t+1)**. Not causal.

| Feature | n | r |
| ------- | -: | -: |
| humidity(t−1) | 488 | 0.23 |
| humidity(t) | 504 | 0.23 |
| rainfall(t−2) | 472 | 0.20 |
| 3-month rainfall (t+t−1+t−2) | 472 | 0.18 |
| rainfall(t−1) | 488 | 0.17 |
| rainfall(t) | 504 | 0.16 |
| calendar_month | 504 | 0.15 |
| positivity_change(t) | 488 | 0.11 |
| confirmed_change(t) | 488 | 0.10 |
| temperature(t) | 504 | −0.05 |
| temperature(t−1) | 488 | −0.02 |
| positivity(t) | 504 | **0.84** |

Climate correlations are weak-to-moderate and **much smaller** than positivity persistence. Humidity and lagged rainfall are the strongest climate-side associations. Temperature is near zero. Do not treat this as evidence that climate drives positivity.

---

## 12. Testing / reporting bias analysis

| Relationship | r |
| ------------ | -: |
| tests(t) vs **count** target (confirmed t+1) | **0.919** |
| tests(t) vs **positivity** target | **−0.289** |
| tests(t) vs positivity(t) | −0.299 |
| confirmed(t) vs positivity target | −0.096 |

Positivity is **much less dominated by testing volume** than raw confirmed counts. A negative association with tests is consistent with more testing bringing in a broader (less positive) mix — still **not** a causal claim.

Positivity does **not** remove reporting bias. It still depends on who seeks care, who is tested, where testing happens, and facility completeness (~0.60).

---

## 13. Leakage audit

Programmatic audit on the derived table:

| Check | Result |
| ----- | ------ |
| Target name in `FEATURE_COLUMNS` | No |
| `malaria_confirmed_next` stored on rows | No |
| confirmed(t+1) / tests(t+1) stored as columns | No |
| Feature names containing `next` or `target_` | None |
| Climate lags from calendar t−1 / t−2, not next-observed | Yes (unit-tested) |
| 202603→202605 skipped | Yes (unit-tested) |
| Encoder fit | Not performed |

**Passed.**

---

## 14. Exact feature contract

**Target:** `target_malaria_positivity_next_period`

**X (candidates on disk, in this order conceptually):**

`malaria_confirmed`, `lag1_malaria_confirmed`, `lag2_malaria_confirmed`, `rolling_3_malaria_confirmed`, `confirmed_change`, `confirmed_pct_change`, `malaria_tests`, `lag1_malaria_tests`, `testing_change`, `testing_pct_change`, `malaria_positivity`, `lag1_malaria_positivity`, `positivity_change`, `rainfall_mm`, `lag1_rainfall_mm`, `lag2_rainfall_mm`, `three_month_rainfall_accumulation`, `temperature_c`, `lag1_temperature_c`, `humidity_percent`, `lag1_humidity_percent`, `calendar_month`, `district_slug`

**Recommended core for a later training run** (redundancy |r|≥0.90 among count/test levels):

`malaria_positivity`, `lag1_malaria_positivity`, `positivity_change`, `malaria_tests` (effort covariate), `rainfall_mm`, `lag1_rainfall_mm`, `lag2_rainfall_mm` **or** `three_month_rainfall_accumulation` (not both; accumulation r = 0.97 with lag1 rain), `temperature_c`, `lag1_temperature_c`, `humidity_percent`, `lag1_humidity_percent`, `calendar_month`, `district_slug` → encode **train-fold only**

Do not auto-include every stored candidate.

---

## 15. Proposed temporal split

Chronological by `feature_period` (same windows as the count model, for comparability):

| Fold | Feature period | Rows |
| ---- | -------------- | ---: |
| Train | 202307–202412 | **280** |
| Validation | 202501–202508 | **128** |
| Test | 202509–202602 | **96** |
| Total | | **504** |

Fit preprocessing (district encoder, any climatology) on **train only**. Do not use test for selection. **Do not train in this phase.**

---

## 16. Known limitations

- Persistence of positivity is still strong (pooled r = 0.84). A model that does not beat ŷ = positivity(t) on validation should not be integrated.
- Climate signal is descriptive and weak relative to persistence.
- ~2.7 years, 28–32 observations per district; climate anomalies would be noisy.
- Incomplete facility reporting; empty Analytics months 202604 and 202607.
- No population denominator; this is not incidence.
- Not a clinical diagnostic; not causal; not connected to the CHEWS dashboard.

---

## Verdict

**READY FOR POSITIVITY MODEL TRAINING**

The derived table, calendar alignment, unit-interval target, leakage audit, and proposed split are in place. This does **not** authorize training in this phase and does **not** claim that ML will beat positivity persistence.

**Do not train now.**

---

## Protection check

| Item | Status |
| ---- | ------ |
| `malaria_model.joblib` | Unchanged (SHA-256 `08a66c59…c5f7`) |
| Existing GBT / `malaria_predictor.py` | Not modified |
| `malaria_forecast_v1` package | Unchanged (`model.joblib` SHA-256 `bf106536…e95b`) |
| Original panel | Unchanged (535 rows) |
| `malaria_forecast_v1_filtered.json` | Unchanged (SHA-256 `771d7612…aa84`) |
| `train_all_models.py` | Not run |
| Model trained this phase | No |
| `models/malaria_positivity_forecast_v1/` | **Not created** |
| Dashboard / risk engine / `/api/healthcare/forecast/live` | Not modified |

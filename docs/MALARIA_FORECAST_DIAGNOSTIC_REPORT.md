# Malaria forecast v1 — data and model diagnostic

**Status:** diagnostic only. No new model was trained.  
**Existing GBT:** `backend/data/trained_models/malaria_model.joblib` was not modified.  
**v1 package:** `backend/data/04_ai/models/malaria_forecast_v1/` was not overwritten.  
**Live CHEWS:** dashboard, risk engine, and `/api/healthcare/forecast/live` were not modified.

**Sources used:** `malaria_forecast_v1_filtered.json` (504 rows), original district-month panel (535 rows), `evaluation.json`.

Associations below are **correlations and descriptive residualizations**, not causal effects.

---

## 1. Executive summary

`malaria_forecast_v1` lost to previous-month persistence because the forecasting target is a **highly persistent district-level case count** that is almost collinear with **testing volume**. Climate at month *t* co-moves seasonally with malaria, but once current confirmed cases are known, leftover month-to-month change is only weakly associated with rainfall, temperature, or humidity.

The pooled correlation between `malaria_confirmed(t)` and `malaria_confirmed(t+1)` is **0.936**. That figure is inflated by stable district size (Western Area Urban vs Falaba). Within a district, the same correlation is still substantial (**median 0.63**, range 0.41–0.82). Median absolute month-to-month change is about **10%** of the current count.

`malaria_tests(t)` correlates **0.967** with `malaria_confirmed(t)` and **0.919** with the target. Tests in the *target* month, which must not be used as a feature, correlate **0.970** with the target. HistGradientBoosting ranked `malaria_tests` as the most important covariate. The model was therefore well positioned to learn **reporting/testing intensity**, not a residual climate-driven transmission signal.

Climate archive coverage in this window is complete. The binding problems are the **target definition**, then **short within-district series** and **incomplete facility reporting** — not the choice of HistGradientBoosting.

**Recommendation:** **REDEFINE THE FORECASTING TARGET**  
Do not retrain on raw confirmed counts. Do not deploy the current HistGB.

---

## 2. Current model result

From `backend/data/04_ai/models/malaria_forecast_v1/evaluation.json`.

| Split | Previous-month MAE | HistGB MAE | Seasonal MAE |
| ----- | -----------------: | ---------: | -----------: |
| Train | 1285.3 | 506.9 | 2075.9 (40% coverage) |
| Validation | **1160.2** | 1150.4 | 2311.5 |
| Test (untouched) | **863.5** | 954.6 | 1333.5 |

Validation: HistGB MAE is **0.8%** below persistence and **worse** on RMSE and R². Test: persistence wins on MAE, RMSE, R², and sMAPE. Train MAE is **2.27×** lower than validation MAE (overfitting).

Permutation importance (validation): `malaria_tests` ≫ `malaria_confirmed` ≫ temperature/rainfall ≫ district/lags. Humidity was near zero.

Verdict already recorded: **NOT RECOMMENDED FOR FURTHER VALIDATION.** This diagnostic explains why, without fitting another model.

---

## 3. Persistence baseline analysis

### Why persistence is strong

1. **District scale dominates the pooled series.** About **81.5%** of target sum-of-squares is between districts. Western Area Urban mean target is 15,977; Falaba is 3,338. A model can look accurate by always predicting “large districts stay large.”
2. **Month-to-month counts move slowly.** Median relative absolute persistence error is **10.3%** (mean 14.7%; p90 29%). Mean signed change is −156 cases on a mean of ~9,650.
3. **Seasonality is already inside `malaria_confirmed(t)`.** Rainy-season months have both higher rainfall and higher counts. Copying last month carries that seasonal level forward one step.

A descriptive OLS of target on `malaria_confirmed(t)` (not a forecast model) has slope **0.94** and intercept **467**. Residuals after that fit are what climate and lags would need to explain. They mostly do not (section 6).

### Autocorrelation (calendar-aligned, no fabricated lags)

| Pair | n | Pearson r | Spearman ρ |
| ---- | -: | --------: | ---------: |
| `malaria_confirmed(t)` vs target(t+1) | 504 | **0.936** | 0.934 |
| `lag1_malaria_confirmed(t)` vs target(t+1) | 488 | 0.871 | 0.866 |
| `lag2_malaria_confirmed(t)` vs target(t+1) | 472 | 0.839 | 0.834 |

`202307` lag1 remains missing (16 rows). Those NaNs were not filled.

### By district (where n ≥ 28)

| District | n | Mean target | Share of total | r(confirmed, target) | r(lag1, target) |
| -------- | -: | ----------: | -------------: | -------------------: | --------------: |
| western_area_urban | 32 | 15,977 | 10.5% | 0.49 | 0.25 |
| tonkolili | 32 | 15,095 | 9.9% | 0.73 | 0.44 |
| kenema | 32 | 13,698 | 9.0% | 0.48 | 0.18 |
| kono | 32 | 13,539 | 8.9% | 0.79 | 0.74 |
| western_area_rural | 32 | 13,227 | 8.7% | 0.82 | 0.72 |
| bo | 30 | 13,529 | 8.3% | 0.73 | 0.15 |
| pujehun | 32 | 8,982 | 5.9% | 0.41 | −0.11 |
| kambia | 32 | 8,923 | 5.9% | 0.78 | 0.53 |
| port_loko | 30 | 8,999 | 5.6% | 0.54 | 0.03 |
| bonthe | 32 | 7,884 | 5.2% | 0.51 | 0.16 |
| kailahun | 32 | 7,146 | 4.7% | 0.60 | 0.22 |
| moyamba | 32 | 7,003 | 4.6% | 0.69 | 0.30 |
| bombali | 32 | 6,877 | 4.5% | 0.64 | 0.19 |
| karene | 32 | 4,864 | 3.2% | 0.76 | 0.44 |
| koinadugu | 28 | 4,938 | 2.8% | 0.54 | −0.05 |
| falaba | 32 | 3,338 | 2.2% | 0.63 | 0.16 |

Within-district r(confirmed, target): **min 0.41, median 0.63, mean 0.63, max 0.82**.  
After subtracting district means, pooled within-district r = **0.65**.

Lag-1 vs target is much weaker and unstable by district (some near zero or negative). Extra lags add little once current confirmed is known (partial r of lag1 given confirmed ≈ **0.01**).

**Implication for CHEWS:** last month’s confirmed count is a hard baseline because the operational series is smooth at monthly resolution. An ML model must beat that residual, not the raw level.

---

## 4. Target distribution

`target_malaria_confirmed_next_period` on the 504-row filtered table:

| Statistic | Value |
| --------- | ----: |
| n | 504 |
| Min | 1,382 |
| Max | 21,568 |
| Mean | 9,650 |
| Median | 8,706.5 |
| Std. dev. | 4,290 |
| Skewness | 0.30 (mild) |
| Zeros | **0** |

No zero counts. The target is a large positive count, not a rare-event series. That is why Poisson was optional and was not needed to explain the v1 failure.

**By district:** top 4 districts (Western Area Urban, Tonkolili, Kenema, Kono) account for **38%** of the summed target; top 8 for **67%**. Falaba is 2.2%. The target is **district-dominated**, not a few outlier months.

**By feature month:** 32 months; no month exceeds **3.8%** of the total summed target (highest: 202307). Lowest share is 202403 (**1.9%**, 13 districts after completeness filter). Month concentration is mild compared with district concentration.

`malaria_confirmed(t)` has nearly the same distribution (mean 9,807, median 8,887, min/max identical range), which is consistent with copying t → t+1.

---

## 5. Testing / reporting analysis

All 504 filtered rows have `malaria_tests > 0`. Ratios below use only those rows. Missing values were not replaced with zero.

| Quantity | n | Mean | Median | Std | Min | Max |
| -------- | -: | ---: | -----: | --: | --: | --: |
| `malaria_tests(t)` | 504 | 15,432 | 14,048 | 7,066 | 2,231 | 33,541 |
| `malaria_confirmed(t) / malaria_tests(t)` | 504 | 0.645 | 0.645 | 0.069 | 0.341 | 0.805 |
| Same ratio at t+1 | 504 | 0.643 | 0.643 | 0.068 | 0.341 | 0.795 |

| Relationship | Pearson r |
| ------------ | --------: |
| tests(t) vs confirmed(t) | **0.967** |
| tests(t) vs target(t+1) | **0.919** |
| tests(t+1) vs target(t+1) | **0.970** |
| confirmed(t) vs target(t+1) | 0.936 |
| positivity(t) vs target count | −0.13 |
| positivity(t) vs positivity(t+1) | **0.839** |

Partial correlations:

- tests vs target **given confirmed(t):** r = **0.16** (most of the tests–target link is shared with current cases)
- confirmed vs target **given tests(t):** r = **0.47** (current cases still add information after tests)
- tests vs target residual after linear confirmed(t): r = **0.04**

`rdt_positivity` (RDT-positive / tests) is missing on **80/504** rows (16%) and correlates only **0.04** with `confirmed/tests`. It is not a substitute for confirmed-case positivity.

**Reporting-effort bias:** using raw `malaria_tests` as a feature can let the model treat testing volume as if it were transmission. Districts and months that test more will appear to have more malaria. That is a limitation of the **count target**, not proof that testing *causes* malaria.

Facility completeness on the filtered table (mean ~0.60) is only weakly associated with confirmed counts (Pearson r ≈ 0.01; Spearman 0.11). Completeness filters who is in the dataset; it does not explain the tests–confirmed collinearity among included rows.

---

## 6. Climate signal analysis

Pooled correlations with the **count** target:

| Feature | Pearson r vs target | Partial r given confirmed(t) | r vs month-to-month change (t+1 − t) |
| ------- | ------------------: | ---------------------------: | ----------------------------------: |
| rainfall_mm(t) | 0.15 | 0.10 | 0.08 |
| temperature_c(t) | −0.14 | 0.01 | 0.03 |
| humidity_percent(t) | 0.30 | 0.10 | 0.05 |
| calendar_month | 0.13 | 0.09 | 0.07 |
| malaria_confirmed(t) | 0.94 | — | — |
| malaria_tests(t) | 0.92 | 0.16 | −0.13 |

Residuals of target after linear confirmed(t) vs climate: rainfall **0.10**, humidity **0.10**, temperature **~0.00**.

**Within-district (demeaned) levels** look more climate-like: rainfall vs target **0.27**, temperature **−0.34**. That is seasonal co-movement of *levels* inside a district (wet/cool months ↔ higher counts). The same rainfall series vs **change** (t+1 − t) is only **0.08**. Climate tracks where you are in the seasonal cycle; `malaria_confirmed(t)` already contains that cycle.

Calendar-month means (filtered rows) show the expected Sierra Leone wet season:

| Calendar month | n | Mean rainfall (mm) | Mean confirmed(t) | Mean positivity |
| -------------: | -: | -----------------: | ----------------: | --------------: |
| 1 | 47 | 18 | 9,880 | 0.64 |
| 2 | 47 | 11 | 8,452 | 0.63 |
| 3 | 29 | 29 | 8,094 | 0.61 |
| 4 | 29 | 94 | 8,650 | 0.61 |
| 5 | 32 | 208 | 9,978 | 0.64 |
| 6 | 32 | 336 | 10,335 | 0.65 |
| 7 | 48 | 560 | 10,724 | 0.66 |
| 8 | 48 | 567 | 10,522 | 0.66 |
| 9 | 48 | 557 | 9,491 | 0.64 |
| 10 | 48 | 347 | 10,222 | 0.65 |
| 11 | 48 | 121 | 10,428 | 0.66 |
| 12 | 48 | 25 | 9,975 | 0.66 |

Lagged rainfall already on the original panel (not used as new training features here):

| Series | n | r vs count target | r vs change | r vs positivity(t+1) |
| ------ | -: | ----------------: | ----------: | -------------------: |
| rain(t−1) | 488 | 0.14 | 0.01 | 0.17 |
| rain(t−2) | 472 | 0.14 | — | — |
| rain(t)+rain(t−1)+rain(t−2) | 472 | 0.16 | 0.07 | 0.18 |

Partial r of 3-month rainfall vs count target given confirmed(t) ≈ **0.09**. Accumulation does not unlock a large residual signal for the **count** target.

**Do not read this as “climate does not affect malaria.”** It says: *in this monthly DHIS2 count series, climate does not add much information for next month’s count beyond current confirmed cases.* That is a prediction-information finding, not a biological conclusion.

---

## 7. Missingness / completeness analysis

Requested historical window on the original panel: **202307–202608**.

| Item | Count |
| ---- | ----: |
| Districts | 16 |
| Expected months | 38 |
| Expected district-months | **608** |
| Observed district-months | **535** |
| Missing district-months | **73** |
| Climate-null original rows | **0** |

**All 73 missing district-months are in five late periods.** They are not scattered holes across 2023–2025.

| Period | Observed districts | Mean facility completeness | Notes |
| ------ | -----------------: | -------------------------: | ----- |
| 202307–202603 | 16 every month | ~0.44–0.64 | Full district grid |
| 202402–202404 | 16 | 0.49 / 0.44 / 0.47 | Completeness trough (Koinadugu min 0.09 in 202403) |
| **202604** | **0** | — | Empty Analytics (known) |
| 202605 | 3 | 0.007 | Sparse leftover reporting |
| 202606 | 3 | 0.010 | Sparse |
| **202607** | **0** | — | Empty Analytics (known) |
| 202608 | 1 | 0.006 | Sparse |

Missing-month counts by district (3–5 each) only reflect whether that district appeared in the sparse 202605/202606/202608 extracts. No district is systematically absent in 202307–202603.

Filtered-table exclusions from original rows with feature period ≤ 202602: **8** rows (512 → 504), all completeness < 0.20 at t and/or t+1, concentrated in **Koinadugu, Bo, Port Loko** around **202401–202404**. No imputation.

Filtered completeness (kept pairs): min **0.22**, median **0.63**, mean **0.61**, max **0.74**. Typical included month still omits ~40% of expected facilities. Counts remain under-ascertainment of true burden.

---

## 8. Reporting bias assessment

Tests track confirmed cases far more tightly than climate does:

| Correlate of `malaria_confirmed(t)` | Pearson r |
| ----------------------------------- | --------: |
| `malaria_tests(t)` | **0.967** |
| humidity(t) | 0.28 |
| rainfall(t) | 0.12 |
| temperature(t) | −0.16 |
| facility completeness(t) | 0.01 |

Tests in month t+1 (not a legal feature) correlate **0.97** with the forecasting target. Permutation importance put `malaria_tests` first.

**Limitation (not a causal claim):**

> The current DHIS2 target may reflect both malaria burden and health-system testing/reporting intensity.

Confirmed counts can rise because transmission rose, because more people were tested, because more facilities reported, or some mix. The v1 model had no way to separate those. Persistence wins in part because testing volume and district reporting systems are themselves persistent.

---

## 9. Target alternatives (design only — not trained)

Population denominators, incidence per 1,000, and entomological rates are **not in the available tables**. They are not proposed.

### A. Raw confirmed cases — `malaria_confirmed(t+1)` (current)

| | |
| - | - |
| **Measures** | District-month sum of confirmed malaria among reporting facilities |
| **Data required** | `malaria_confirmed` at calendar t+1 (already used) |
| **Advantages** | Directly related to case load / commodities; easy to explain |
| **Disadvantages** | Dominated by district size and testing volume; persistence is extremely strong; climate residual is weak |
| **Leakage risks** | Using tests(t+1), confirmed(t+1) lags from the target month, or non-calendar “next observed” rows |
| **Early warning** | Weak. A “forecast” that copies last month does not warn. A model that copies testing volume does not warn either |

**Not recommended as the next ML target.**

### B. Positivity rate — `malaria_confirmed(t+1) / malaria_tests(t+1)`

| | |
| - | - |
| **Measures** | Fraction of tests that are confirmed positive next month |
| **Data required** | `malaria_confirmed` and `malaria_tests` at t+1. Both exist. In the filtered 504 rows, tests are never 0, so the ratio is defined without imputation |
| **Advantages** | Much less collinear with testing volume (tests vs positivity(t+1) r = −0.29). Positivity std is 0.07 around a mean of 0.64, so the series is not a district-size ranking. Closer to a transmission-intensity proxy among people tested |
| **Disadvantages** | Still shaped by who seeks care and who is tested. Not a case-count for stock planning. Persistence remains high (r = 0.84 pooled; 0.52 within-district). Climate residual vs positivity is still modest (partial rain given positivity(t) ≈ 0.11; humidity ≈ 0.18) |
| **Leakage risks** | Any use of confirmed(t+1) or tests(t+1) as features; using positivity(t+1) components from the target month |
| **Early warning** | **More appropriate than raw counts**, if the question is “is positivity rising beyond last month / season?” Operational case-load would remain a separate persistence or planning number, not this ML target |

Do **not** substitute `rdt_positivity` without a separate design: it is 16% missing and almost uncorrelated with confirmed/tests.

### C. Normalized burden using only available fields

Possible **without new data**:

- confirmed / tests (same as B)
- month-to-month **change** or **percent change** of confirmed (forecast Δ, not the level)
- confirmed divided by **reporting facility count** or completeness (intensity per reporting facility)

Not possible without new data: incidence per population, age-standardised rates, under-5 incidence (u5 counts exist in DHIS2 config but were not in this filtered contract), entomological inoculation rate.

Change-as-target would make persistence a **zero baseline** and force the model to predict residuals — closer to the actual early-warning question — but the climate correlations with Δ are currently **~0.03–0.08**. That target would likely need more history or a different signal before ML beats “predict zero change.”

### D. Other DHIS2-supported candidates

| Candidate | Available? | Comment |
| --------- | ---------- | ------- |
| `malaria_confirmed_u5(t+1)` | Indicator exists in config; not in filtered table | Still a count; same testing-volume issues |
| `malaria_rdt_positive(t+1) / malaria_tests(t+1)` | Partial (16% missing on t) | Different from confirmed/tests; missingness must stay NaN |
| Facility-completeness-adjusted counts | Completeness is on the panel | Adjusts reporting coverage, not testing mix |

**Design conclusion:** the next contract should not reuse A as the sole ML target. **B is the leading candidate** for an early-warning quantity that the data can actually support. A raw count can remain a dashboard statistic via persistence, without a second overfit tree.

---

## 10. Proposed improved feature design (not implemented)

Prediction time = end of month *t*, after month-*t* HMIS and Archive climate are in. No t+1 health or climate values.

### SAFE TO USE (constructible from current historical tables)

**Epidemiological (month t and earlier):**

- `malaria_confirmed(t)`, lag1, lag2 (calendar; keep NaN)
- rolling 3-month mean of confirmed (already on filtered rows)
- trend: confirmed(t) − lag1; percent change where lag1 > 0
- district historical baseline: **train-fold only** mean confirmed or positivity for that district / calendar month

**Testing:**

- `malaria_tests(t)` and tests lag1 (if needed)
- positivity(t) = confirmed(t)/tests(t) where tests > 0 (defined on all 504 filtered rows)
- positivity change vs lag1
- **Do not treat raw tests as a transmission feature** if the target is still a count; if the target is positivity, raw tests may still capture mix/effort and should be interpreted as such

**Climate (Archive, already complete in this window):**

- rainfall(t), rainfall(t−1), rainfall(t−2)
- 3-month rainfall accumulation
- temperature(t), temperature(t−1); humidity(t), humidity(t−1)
- calendar month; binary wet-season flag (e.g. Jun–Oct) from calendar, not from t+1 weather
- district-month climate anomaly vs **train-fold** district×month climatology only (noisy with ~2–3 years)

**Geographic:**

- district encoding fit on **train districts only** (same rule as v1)
- train-fold district mean of the **chosen target**

### NOT SAFE / FUTURE / NOT AVAILABLE

| Item | Reason |
| ---- | ------ |
| Climate at t+1 | Future weather relative to prediction time |
| `malaria_confirmed`, tests, RDT, completeness at t+1 | Target-month leakage |
| `malaria_confirmed_next` / non-calendar next row | Already rejected in v1 filter |
| Population denominators, density, fever, stagnation, breeding sites | Not in live DHIS2+Archive contract; synthetic GBT features |
| Encoder or climatology fit on validation/test | Preprocessing leakage |
| Imputing lag1=0 for 202307 | Fabricates a non-existent 202306 |

Climate **timing:** using month-*t* climate for a t+1 malaria outcome is operationally reasonable (lagged hydrology and incubation). The v1 failure was not “wrong month of climate” so much as “wrong target, with climate collinear with current counts.” Do not add t+1 climate to fix it.

---

## 11. Data requirements

If the target is redefined (recommended), before any new training:

1. Write an explicit positivity (or other) feature contract, still calendar t+1, still completeness ≥ 0.20 at t and t+1.
2. Keep legitimate NaNs; do not fill 202604/202607.
3. Re-run a **pre-training technical check** on the new target (splits, leakage, missingness) — no fit until that check is READY.
4. Decide whether raw counts stay as a non-ML operational overlay.

Additional history would help **after** the target is fixed: ~32 feature months and 28–32 observations per district are thin for climate anomalies and for a three-way temporal split. Climate *coverage* in-window is already 100%; the gap is **duration and HMIS completeness**, not missing Open-Meteo months.

Do not extract population from outside DHIS2 and silently join it.

---

## 12. Recommended next step

Ranked limitations for *this* forecasting problem:

| Rank | Limitation | Why it dominated v1 |
| ---: | ---------- | ------------------- |
| 1 | **C. Target definition** | Count target ≈ testing volume (r = 0.97 with tests(t+1)); persistence r = 0.94; ML importance led by tests |
| 2 | **D. Reporting completeness** | Typical ~60% facility completeness; empty 202604/202607; sparse 202605–202608 unusable |
| 3 | **E. Insufficient historical duration** | ~2.7 years, 32 feature months; within-district n ≈ 30; climatology and lag structures are noisy |
| 4 | **B. Feature engineering** | Contemporaneous climate is mostly seasonal level already in confirmed(t); lags/accumulation add little for counts |
| 5 | **A. Model choice** | HistGB vs persistence was not the failure mode; another regressor on the same target is unlikely to matter |
| 6 | **F. Missing climate history** | **Not** the issue in this window (0 climate-null rows) |

**Next step:** redesign the target (positivity or a tests-adjusted measure), document a new contract, and only then consider whether the remaining residual is worth modelling. Do not iterate HistGB/XGBoost/RF/Poisson on raw `target_malaria_confirmed_next_period`.

---

## 13. Explicit limitations

- Correlations are not causation.
- Completeness-filtered rows are not a random sample of district-months; 202402–202404 and late-2026 sparse months are under-represented.
- Confirmed malaria is among **reporting** facilities, not a census of infections.
- Open-Meteo monthly climate is centroid-based, not facility-level, and is month *t*, not a weather forecast.
- RDT positivity ≠ confirmed/tests.
- No population denominator was used or invented.
- v1 artifacts were not altered; this report does not change CHEWS runtime behaviour.
- A positivity model is **not** guaranteed to beat positivity-persistence; that is a later evaluation, after a new contract, not a claim of this phase.

---

## Recommendation

**REDEFINE THE FORECASTING TARGET**

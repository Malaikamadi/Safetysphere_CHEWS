# Malaria anomaly target design and backtest

**Status:** methodological / diagnostic. **No model was trained.**  
**Not modified:** `malaria_model.joblib`, existing GBT, `malaria_forecast_v1`, `malaria_positivity_forecast_v1`, original 535-row panel, dashboard, risk engine, `/api/healthcare/forecast/live`.  
**Not integrated** into production CHEWS.

Reproducible scored rows and summaries: `backend/data/04_ai/diagnostics/malaria_anomaly_backtest.json`  
Implementation: `backend/services/malaria_anomaly.py`  
Runner: `backend/training/analyze_malaria_anomaly.py`  
Tests: `backend/tests/test_malaria_anomaly.py`

---

## Executive recommendation

**A. ANOMALY RULE / STATISTICAL BASELINE IS SUFFICIENT**

Do **not** train an ML model next.

The defensible object is a **past-only district × calendar-month positivity anomaly** against an **expanding seasonal median**. That is a contemporaneous “is this month unusual for this district’s season?” detector. It is **not** a next-month forecast, and it does **not** beat last month’s positivity for predicting t+1.

Standardized robust z with only three prior years is **MAD-fragile**: 22 of 35 `robust_z ≥ 2` flags have MAD < 0.01, including sub-2 percentage-point moves with z > 50. Any operational rule needs a **magnitude gate** (absolute deviation), labelled as policy, not as a learned threshold.

Climate anomalies are essentially uncorrelated with the malaria anomaly (|pooled r| ≤ 0.10). Testing volume distorts some flags (4/35) but most conventional alerts (25/35) coincide with higher confirmed cases vs last year’s same month.

---

## 1. Candidate target

**Name:** `seasonal_malaria_positivity_anomaly`

**Activity measure**

```
malaria_positivity = malaria_confirmed / malaria_tests
```

Defined only when `malaria_tests > 0`. Missing tests are **not** treated as zero. On the comparable-era panel, positivity is defined on all 935 rows; none exceed 1.0.

**Grain:** district × calendar month (16 current admin districts).

**Era:** comparable only, `202106`–`202608`.  
1,947 pre-`202106` expansion rows are excluded and are not pooled. The frozen 535-row v1 panel is **read**, not rewritten; v1 wins on any district-period overlap.

**Baseline (primary):** expanding historical **median** of positivity for the **same district and same calendar month**, using only years **strictly before** the evaluation month.

**Primary anomaly score:**

```
robust_z = (positivity_t − median_prior) / (1.4826 × MAD_prior)
```

Also stored, and in several respects better behaved: expanding mean, mean z, absolute deviation (percentage points), relative deviation, ratio to median, and last year’s same-month residual.

**Eligibility for primary scoring**

- `n_prior ≥ 3`
- `facility_completeness ≥ 0.20` (same gate as the frozen forecast experiments)
- `malaria_tests > 0`
- leakage check passed

**Horizon:** the score describes **month t at the end of month t**. Climate used is month t or earlier. **t+1 climate is never used.**

---

## 2. Baseline methodology (compared, not cherrypicked)

| Method | What it uses | Role |
| ------ | ------------ | ---- |
| A. Prior-year same month | positivity(t−12) only | Simple seasonal copy |
| B/D. Expanding seasonal mean | mean of all prior same-month years | Mean z = (x−mean)/sd |
| C. Expanding seasonal median | median of all prior same-month years | **Primary location** |
| E. Median + MAD | robust scale | **Primary standardized score**, with caveats below |

The current observation is **never** in its own baseline. Future years are **never** in an earlier baseline. The full-dataset mean is **never** used. Tests assert this (including that a 2025 extreme does not change a 2024 baseline).

Chronological backtest leakage audit on 352 primary-eligible rows: **passed, 0 violations**.

---

## 3. What the comparable panel actually supports

| Quantity | Value |
| -------- | ----: |
| Comparable district-months | 935 |
| Districts | 16 |
| Observed months | 61 |
| Pre-`202106` rows excluded | 1947 |
| Primary-eligible rows | **352** |
| Insufficient history (`n_prior` < 3) | 576 |
| Low completeness | 18 |
| Tests not positive | 0 |
| Scorable window | `202406`–`202603` (22 months) |

`n_prior` on rows with positivity:

| n_prior | Rows |
| ------- | ---: |
| 0 | 192 |
| 1 | 192 |
| 2 | 192 |
| 3 | 192 |
| 4 | 163 |
| 5 | 4 |

The coverage report’s “every district-calendar-month has ≥3 prior years **as of `202608`**” is true. In a **chronological** backtest those three years only exist once we reach mid-2024, so most of the comparable era cannot yet be scored. That is expected, not a hidden hole.

---

## 4. Is ≥3 prior years enough?

**Partly, for a median. Not by itself for robust z.**

| | n_prior = 3 | n_prior ≥ 4 |
| - | ----------: | ----------: |
| Eligible rows | 192 | 160 |
| Mean MAD | 0.0183 | 0.0190 |
| p90 of \|robust_z\| | **8.80** | 3.92 |

Across 192 district-calendar-month keys, expanding medians are **stable**: mean of max year-to-year median steps = **0.010** (about 1 percentage point). Only **7 / 192** keys (3.6%) have mean MAD ≥ 0.05 (Falaba Sep, Karene Jun, Kenema Oct, Kono Feb/Nov, Pujehun Apr/Dec). No key had a median step ≥ 0.05.

So the **level** of the seasonal baseline is stable enough to use. The **scale** (MAD) with n = 3 is often tiny, which inflates robust z.

---

## 5. Anomaly definitions and thresholds

### Data-described (in-sample, not a deployed rule)

Primary-eligible robust z (n = 352):

| | robust z | mean z | abs. dev. from median |
| - | -------: | -----: | --------------------: |
| p50 | −0.39 | −0.27 | −0.9 pp |
| p90 | 1.93 | 1.12 | +4.2 pp |
| p95 | 4.08 | 1.68 | +5.9 pp |
| min / max | −76 / +96 | −23 / +9.1 | −32 / +15 pp |

Empirical p90 of robust z is **already ~2**. That is why `z ≥ 2` is a reasonable *convention* and also why it is **not** an independent discovery from this sample.

### Statistical convention (not fitted, not ML)

```
conventional_alert ⇔
  robust_z ≥ 2
  AND n_prior ≥ 3
  AND completeness ≥ 0.20
  AND tests > 0
```

Backtest: **35 / 352 = 9.9%**. Mild convention `robust_z ≥ 1.5`: 44 / 352 = 12.5%. Sustained mild (this month and calendar previous month): 10. Consecutive conventional: 8.

**Problem:** 22/35 conventional alerts have MAD < 0.01; 13/35 have absolute deviation < 3 pp. Example: Port Loko `202406` is **+1.8 pp** vs seasonal median with robust z **95.9**.

Mean z ≥ 2 is stricter and better aligned with large moves: **11** flags.

### Operational / policy candidates (not validated)

NORMAL / WATCH / ELEVATED / HIGH is **not proposed**.

A candidate **magnitude gate**, explicitly policy:

```
candidate_flag ⇔ conventional_alert AND (positivity − median) ≥ +0.03
```

That retains **22** flags (6.3% of eligible). The 0.03 cut is **operational** (about p90 of absolute deviations), not a machine-learning discovery.

Do not ship four-class labels from these percentiles.

---

## 6. Testing-bias assessment

Positivity movements vs last year’s same month, primary-eligible rows:

| Class | Eligible | Conventional alerts |
| ----- | -------: | ------------------: |
| genuine_increased_positivity | 91 | **25** |
| genuine_decreased_positivity | 100 | 0 |
| testing_up_dilution | 60 | 0 |
| testing_down | 15 | **4** |
| mixed | 82 | 4 |
| reporting_artifact (completeness drop ≥ 0.15) | 4 | 2 |

**71%** of `z ≥ 2` flags are “genuine” in this descriptive sense (confirmed up, tests not down more than 5% vs last year’s same month). **11%** are testing-down artifacts. Correlation of |robust z| with `1/√tests` is **0.02**; tests are large (p05 ≈ 5,400), so Poisson-like positivity noise is not the main issue. Two of 18 low-test eligible rows alerted.

**Do not treat every positivity increase as an outbreak.** Pair the anomaly with confirmed-count direction and test-volume change. The four testing-down alerts should not be narrated as transmission surges.

---

## 7. Climate context

Past-only same-calendar-month climate median; current-month climate is contemporaneous context only. No t+1 climate.

Pooled Pearson r of positivity robust z vs:

| Climate feature | Pooled r | Median within-district r |
| --------------- | -------: | -----------------------: |
| Rainfall anomaly (t) | −0.04 | −0.06 |
| Temperature anomaly (t) | −0.01 | −0.03 |
| Humidity anomaly (t) | +0.04 | +0.19 |
| 3-month rainfall sum | −0.10 | −0.12 |
| Lag-1 rainfall anomaly | −0.09 | +0.07 |

**Climate does not provide a useful linear context signal** for this monthly positivity anomaly. Humidity’s within-district median r = 0.19 is still weak. Biologically plausible rainfall effects are not visible at this grain after seasonal malaria is already subtracted.

Climate may still be shown as background on a map. It should not define the alert.

---

## 8. Historical backtest (leakage-free)

For each eligible month t, the baseline uses only earlier years of that district-calendar-month. Then the observed positivity at t is scored. Calendar t+1 (not “next observed row”) is used only **after** the score, to ask what happened next.

**Leakage audit: passed.**

| Backtest quantity | Value |
| ----------------- | ----: |
| Primary-eligible | 352 |
| Conventional alerts | 35 (9.9%) |
| Mild alerts | 44 (12.5%) |
| Districts with ≥1 conventional alert | 11 |
| Silent districts | Bonthe, Kailahun, Kambia, Moyamba, Tonkolili |
| Most alerts | Kono 8, Kenema 7, Western Area Urban 5 |
| Peak month | `202603` (5 alerts) |
| Eligible pairs with calendar t+1 | 336 |
| P(t+1 still conventional \| alert) | **26.7%** |
| P(t+1 conventional \| no alert) | **8.5%** |
| P(t+1 robust z ≥ 0 \| alert) | 73.3% |
| False-persist proxy (alert then z < 0) | 8 / 30 = 26.7% |
| Missed next conventional given no alert at t | 26 |

An alert raises the chance of another conventional flag next month from 8.5% to 26.7% (~3×), but **most next-month conventional flags are not preceded by an alert** (26 missed vs 8 consecutive). Lead time is therefore weak.

Alerts by calendar month are not confined to the rains (March has 7; June has 1). This is a district-season residual, not a wet-season detector.

### Comparison with simple baselines for positivity(t+1)

MAE of positivity(t+1), n = 336 calendar-consecutive eligible pairs:

| Predictor | MAE |
| --------- | --: |
| **Previous-month positivity (persistence)** | **0.0240** |
| Expanding seasonal median of t+1’s own month | 0.0333 |
| Previous-year same calendar month as t+1 | 0.0420 |
| Candidate anomaly rule | not a point forecast |

Persistence wins, as in the earlier HistGB experiments. The seasonal anomaly is **not** a better t+1 predictor than “same as last month.”

Pooled correlations:

| Pair | Pooled r | Median within-district r |
| ---- | -------: | -----------------------: |
| positivity(t), positivity(t+1) | **0.83** | 0.47 |
| robust_z(t), robust_z(t+1) | 0.09 | 0.19 |
| robust_z(t), positivity(t+1) | −0.01 | 0.28 |
| robust_z(t), confirmed(t+1) | 0.07 | 0.30 |

**An unusual month t is only weakly associated with elevated malaria after t.** Identifying an anomaly is useful as a **nowcast of unusualness**, not as an early-warning forecast of next month.

---

## 9. Does a simple statistical rule compare favourably with ML?

Yes. There is nothing left for a tree model to forecast that persistence does not already copy.

The previous HistGB count and positivity packages lost to persistence on untouched tests. This backtest shows the same structure after rewriting the question as a seasonal anomaly: the residual (robust z) barely persists (r = 0.09), while the level (positivity) persists strongly (r = 0.83). Climate residuals are ~0. Training another model on this target would be expected to overfit noise.

If ML were ever specified later (not recommended now):

| Item | Spec |
| ---- | ---- |
| Target | not recommended; if forced, `robust_z(t+1)` or `I(abs_dev_median(t+1) ≥ δ)` |
| Features | past-only z, abs_dev, tests change, completeness, calendar month; **no t+1 climate** |
| Horizon | calendar month t+1 |
| Grain | district-month, comparable era only |
| Leakage | chronological; baseline at each time uses only earlier years |
| Split | by time, never random district-month shuffle |
| Metrics | vs persistence and vs seasonal median; not vs a null of 0 |
| Minimum data | more than the current 22 scorable months before believing a lift |

Leave training for a separate phase **only if** a later review rejects recommendation A.

---

## 10. Limitations

1. Scorable history is short (`202406`–`202603`) even though raw comparable data start in `202106`.
2. Robust z explodes when three prior years almost agree (MAD ≈ 0).
3. Completeness uses **current** MFL expected facilities.
4. No independent outbreak line list exists; “false alert” is a persistence proxy, not a gold-standard error.
5. Falaba/Karene geography is the current 16-district map.
6. Pre-`202106` data remain quarantined.
7. Missing months (`202604`, `202607`, sparse 2026) break calendar t+1 pairs; they are not interpolated.
8. This work is isolated: it does not change live forecast, dashboard, or risk engine.

---

## 11. Classification

| Option | |
| ------ | - |
| **A. Anomaly rule / statistical baseline is sufficient** | **Selected.** Expanding seasonal median + magnitude-aware residual. No ML. |
| B. Anomaly target promising and ML justified | No. Residuals do not forecast t+1 better than persistence. |
| C. More data required | Not for defining this target. More scorable years would stabilize MAD/z, but would not create an ML case from current residuals. |
| D. Anomaly approach not currently defensible | Too strong. The **median residual** is defensible as a nowcast. Raw `robust_z ≥ 2` without a magnitude gate is **not** defensible as an operational alert. |

---

## 12. Next phase (not this one)

1. Design-review the **operational rule**: past-only expanding seasonal median, plus an explicit magnitude gate and a testing-bias flag. Do not present the gate as ML.
2. Keep CHEWS disconnected until that review.
3. Do **not** train HistGB / XGBoost / networks on this target.
4. Do **not** regenerate `malaria_forecast_v1` or `malaria_positivity_forecast_v1`.
5. Optional later: add another comparable year when DHIS2 produces it, then re-run this **same** backtest script — still no training.

---

## Protection check

| Artifact | Status |
| -------- | ------ |
| `malaria_model.joblib` | Unchanged |
| Existing GBT | Unchanged |
| `malaria_forecast_v1` | Unchanged |
| `malaria_positivity_forecast_v1` | Unchanged |
| Original 535-row panel | Unchanged |
| Dashboard / risk engine / live forecast | Unchanged |
| Model trained | **No** |
| Production integration | **No** |

Stopped after analysis and recommendation.

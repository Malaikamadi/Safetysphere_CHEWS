# Malaria early-warning target assessment

**Status:** design and descriptive analysis only. **No model was trained.**  
**Not modified:** `malaria_model.joblib`, existing GBT, `malaria_forecast_v1`, `malaria_positivity_forecast_v1`, original 535-row panel, dashboard, risk engine, `/api/healthcare/forecast/live`.

Both ML packages remain on disk as experimental evidence only.

Associations below are correlations, not causal effects. Threshold examples are **descriptive**, not proposed alerts.

---

## 1. Executive summary

Two real-data HistGradientBoosting experiments failed for the same structural reason: **next month’s malaria series is mostly last month’s series**. Climate and testing covariates add little once that persistence (or district/season level) is known. The models overfit and lost to simple copy-forward baselines on untouched test data.

CHEWS therefore should **not** pursue another ML forecast of counts or positivity.

The operational question that *would* matter for early warning is:

> Is this district’s malaria activity unusual for this district and this season?

That is an **anomaly** question, not a case-count forecast. The current extract cannot yet support a defensible version of it:

- Only ~2.7 years of district-months (`202307`–`202608`, with holes).
- For a past-only same-calendar-month baseline, **192 / 504** filtered rows (38%) have **zero** prior years of that district-month.
- Standardized (z) scores with two prior points are unstable.
- After removing district-season level, climate vs positivity anomaly is ~**0** (|r| ≤ 0.13).
- Four-class labels (NORMAL / WATCH / ELEVATED / HIGH) would require invented cut-offs.

**Recommendation: D. COLLECT MORE HISTORICAL DATA BEFORE DEFINING THE TARGET**

When enough same-month history exists, the target to define is a **past-only district–season malaria-activity anomaly** (positivity-first, counts only as context) — not another regressor, and not a climate-risk classifier trained on the current residuals.

Until then, CHEWS should treat **last month’s observed DHIS2 figures** (with completeness) as the honest case-load number, keep the prototype risk engine unchanged, and **not** present either HistGB as a live forecast.

---

## 2. What the two ML experiments demonstrated

### Raw counts — `malaria_forecast_v1`

| Untouched test | MAE | Winner |
| -------------- | --: | ------ |
| Previous-month persistence | **863.5** | Persistence |
| HistGB | 954.6 | |

Validation MAE lift vs persistence was **0.8%** and RMSE/R² favoured persistence. Train MAE was **2.27×** validation MAE. `malaria_tests` dominated importance. Tests at t+1 (illegal as a feature) correlate **0.97** with the count target.

### Positivity — `malaria_positivity_forecast_v1`

| Untouched test | MAE | Winner |
| -------------- | --: | ------ |
| Positivity persistence | **0.0172** | Persistence (~39% better) |
| HistGB | 0.0239 | |

Persistence also won RMSE, R², and sMAPE. `malaria_positivity` dominated importance. Climate and tests were negligible. Train/validation MAE ratio **1.89**.

The **0.026** figure was full-table persistence MAE. On the test window, persistence was **0.0172**. Comparing HistGB’s 0.0239 to 0.026 without the test baseline would be misleading.

**Shared lesson:** at monthly district resolution, a tree model is mostly re-learning persistence and over-fitting noise. Algorithm choice is not the bottleneck.

---

## 3. Why raw-count forecasting should not be pursued now

1. Persistence is already a strong operational copy of next month’s count (pooled r = 0.94; within-district median ~0.63).
2. Counts mix **burden, testing volume, and which facilities reported**.
3. ~81% of count variance is **between districts** (size), not month-to-month change.
4. Climate at t is largely seasonal information already inside `malaria_confirmed(t)`.
5. A “better” ML count model would still not be an early-warning system if it cannot beat “same as last month.”

There is **no defensible reason** to continue ML case-load forecasting on this extract.

Transparent case-load for logistics: **report last month’s confirmed count**, labelled as observed (with completeness), not as an AI forecast.

---

## 4. Why positivity forecasting should not be pursued now

Redefining the target correctly reduced testing-volume domination (tests vs positivity target r = **−0.29** vs **0.92** for counts). That was the right diagnostic move. It did **not** create a forecastable residual:

- Positivity(t) vs positivity(t+1): r = **0.84**
- HistGB still lost to that copy on validation and test
- Climate vs positivity(t+1) |r| ≈ 0.16–0.23; after seasonal/district anomaly, |r| ≈ 0.05–0.13

Positivity remains the better **description** of activity among tested people. It is not, with this history, a better **one-month ML target**.

---

## 5. Case-load forecasting assessment (target A)

**Question:** “How many confirmed malaria cases will occur next month?”

| Criterion | Finding |
| --------- | ------- |
| Data support | Counts exist; completeness ~0.60 typical |
| Persistence | Very strong |
| ML lift | None that survived test |
| Early-warning value | Low — copying last month does not warn |
| Continue as ML target? | **No** |

Keep counts as a **dashboard statistic** (observed, persistence-as-naive-outlook if a number is required), not as an ML product.

---

## 6. Malaria anomaly assessment (target B)

**Question:** “Is activity unusually high for this district and season?”

### What we constructed (design only, past-only)

For each district-month t on the 504-row positivity table, the same-calendar-month baseline used **only earlier years of that district-month**. No future rows, no full-dataset mean.

| Prior same-month years available | Rows | Share of 504 |
| -------------------------------: | ---: | -----------: |
| 0 | 192 | 38% |
| 1 | 186 | 37% |
| 2 | 126 | 25% |

On the original panel, each district×calendar-month key has **2–4** total replicates (median 3) across the whole extract — including the current month. That is not enough for a stable mean, median, or especially a **standard deviation**.

Where ≥1 prior year exists (n = 312):

- Mean positivity anomaly ≈ **−0.020** (later years slightly below early-year baselines — possible reporting mix, not a finding to over-interpret)
- MAE of positivity vs past same-month mean ≈ **0.041**
- |anomaly| > 5 percentage points: **29%** of those rows  
- |anomaly| > 10 percentage points: **5%**

Those 5 / 10 pp cuts are **not** recommended alerts; they show how often a naive cut would fire. Confirmed-count **percent** anomalies are large (MAE ~22%) because counts still swing with testing.

Z-scores with only two prior points are **not usable** (the empirical z distribution is unstable).

### How this would be implemented later (train / as-of time only)

At prediction cutoff = end of month t:

1. Restrict history to periods **strictly before** the month being scored (and, if a split is used, never use validation/test periods to compute a baseline applied inside those periods).
2. For district d and calendar month m, take positivity (or another series) in (d, m) for years < current year.
3. Baseline = mean or median of that list; require a **minimum n** (e.g. ≥3 or ≥4 prior years) or emit `INSUFFICIENT_HISTORY` instead of a level.
4. Anomaly = observed − baseline (and/or percent). Do not estimate σ until n is large enough.

That protocol is valid. **This extract does not yet satisfy the minimum-n rule for most district-months.**

**Verdict on B:** conceptually the right early-warning target; **not implementable as a defensible detector today.**

---

## 7. Climate-health early-warning assessment (target C)

**Question:** “Are current climate and surveillance conditions indicating elevated malaria risk?” as NORMAL / WATCH / ELEVATED / HIGH.

The live CHEWS risk engine already answers a similar question with **generic ecological rules** and **absolute case thresholds of 3 / 10 / 25 / 50** — calibrated as if for a small weekly outbreak, not for district-month totals of thousands. DHIS2 can already saturate that sigmoid. Climate in the engine is not DHIS2-joined Archive climate; live forecast climate is largely **prototype constants** (`_LIVE_SIGNALS`), with optional DHIS2 case overlay.

On the real panel, after a past-only district-season positivity baseline:

| Climate vs **positivity anomaly** | n | r |
| -------------------------------- | -: | -: |
| rainfall(t) | 312 | −0.05 |
| rainfall(t−1) | 312 | −0.05 |
| rainfall(t−2) | 312 | −0.09 |
| 3-month rain | 312 | −0.08 |
| temperature(t) | 312 | −0.01 |
| humidity(t) | 312 | 0.02 |

Climate vs **raw** positivity remains modest (humidity ~0.16–0.23) because both follow the calendar. That is seasonal co-movement, not a residual warning signal.

A four-class scheme would need either:

- climate residuals that actually separate “unusual” months (they do not, here), or  
- percentile cuts on a long district-season history (not available).

**Do not invent those classes now.** Target C as an ML or threshold classifier on this extract is not supported.

---

## 8. Historical baseline options

| Baseline | Leakage-safe if as-of-time | Status on this extract |
| -------- | -------------------------- | ---------------------- |
| District-month mean of **prior years only** | Yes | 38% of filtered rows have n_prior = 0 |
| District-month median, prior years | Yes | Same n problem; more robust than mean when n grows |
| Expanding window (all past months, any season) | Yes | Mixes wet and dry seasons; not a seasonal expectation |
| Rolling last 12 months | Yes after month 12 | Smooths season rather than comparing to “this month last years” |
| Same month last year only | Yes when previous year exists | One point; “higher than last July” ≠ “historically unusual” |
| Full-dataset district-month mean | **No** if used for scoring months that contributed to it | Forbidden for prediction |
| Z-score vs prior same-month σ | Yes in principle | **Not** with n = 2 |

**Later implementation:** store running per-(district, calendar-month) sufficient statistics updated **after** each month closes; never refit on the month being alerted.

---

## 9. Climate signal assessment

| Question | Evidence |
| -------- | -------- |
| Does climate co-move with malaria **levels**? | Weak–moderate: rain/humidity vs positivity ~0.12–0.23; wet-season months have higher counts |
| Does climate explain **anomalies** vs district-season? | Effectively no for positivity (\|r\| < 0.13) |
| Count % anomalies vs climate | \|r\| ~0.21–0.26 contemporaneous — still modest; may mix testing/completeness |
| Should climate be a **primary** warning feature now? | No |
| Should climate stay as **context** (wet season, Archive month t)? | Yes, labelled as concurrent/lagged weather, not as a predicted outbreak driver |

Do not claim rainfall caused or failed to cause malaria from these correlations.

---

## 10. Lead-time assessment

Prediction cutoff = **end of month t**. Features ≤ t only.

| Lead | Persistence: positivity(t) vs positivity(t+k) | Climate vs positivity(t+k) | Climate vs **anomaly**(t+k) |
| ---- | -------------------------------------------: | -------------------------: | ---------------------------: |
| 0 (nowcast) | 1.00 | rain ~0.12, humidity ~0.16 | ~0 |
| **1 month** | **0.84** | rain ~0.16, humidity ~0.23 | \|r\| ~0.09–0.12 |
| **2 months** | **0.75** | rain ~0.18, humidity ~0.23 | \|r\| ~0.10–0.18 |

What the **data** support:

- **1-month:** health persistence dominates; climate does not add a usable residual. A 1-month “forecast” that copies positivity/counts is statistically OK and operationally not an early warning.
- **2-month:** persistence is still strong (0.75); climate–anomaly links remain weak. **Not supported** as a climate-lead warning horizon on this sample.
- Biology may suggest rainfall → mosquitoes → cases over weeks; **this monthly DHIS2 series does not show a clean 2-month climate residual.** Do not assume a biological lag the table cannot estimate.

No t+1 climate was used.

---

## 11. Data limitations

| Item | Value |
| ---- | ----- |
| Geography | 16 districts (centroids for climate) |
| Temporal resolution | Monthly (not weekly) |
| Requested window | `202307`–`202608` (38 months) |
| Observed district-months | **535** / 608 expected |
| Fully missing months | **202604**, **202607** (empty Analytics) |
| Sparse leftovers | 202605 (3 districts), 202606 (3), 202608 (1), completeness ~0.01 |
| Filtered modelling rows | **504** (completeness ≥0.20 at t and t+1, calendar t+1) |
| Climate | Open-Meteo Archive rainfall, temperature, humidity — **0** nulls in-window |
| Population denominators | **Not in pipeline; not added** |
| Indicators on panel | `malaria_confirmed`, `malaria_confirmed_u5`, `malaria_tests`, `malaria_rdt_positive`, completeness, reporting/expected facilities |
| Positivity | confirmed/tests where tests > 0 (all 504 filtered rows) |
| RDT positivity | Missing on 16% of filtered rows; ≠ confirmed/tests |

Same-month history is **2–4 observations per district-calendar-month**, not a climatology.

---

## 12. Reporting / completeness limitations

- Typical kept completeness **~0.60** (min 0.22 on the filtered table; original panel min ~0.006 in sparse months).
- Completeness trough **202402–202404** (Koinadugu especially).
- Confirmed malaria is among **reporting** facilities.
- Testing mix and care-seeking still shape positivity.
- Empty months must stay missing.

Any future anomaly must carry **completeness and tests** as quality flags, not hide them in a single traffic-light.

---

## 13. Operational early-warning concept

CHEWS is meant to support action. A **future** evidence-based layer, once history exists, would score **unusual activity**, not a fake precise caseload.

Illustrative actions (**not implemented**, not claimed as current CHEWS behaviour):

| Signal (when defensible) | Could trigger review of |
| ------------------------ | ----------------------- |
| Unusual positivity or tests-adjusted activity vs district-season | District health team, DHIS2 completeness, lab/testing mix |
| Sustained rise vs last year same month (with history flag) | Commodity / RDT / ACT stock review |
| Wet-season climate **context** + unusual activity | Facility preparedness, CHW attention |
| Low completeness | Do not alert on “low cases”; alert on **data quality** |

Until then, the honest operational products are:

1. **Observed** DHIS2 confirmed, tests, positivity, completeness (already closer to truth than ML).
2. **Naive outlook:** last month’s value, explicitly labelled “persistence, not a model.”
3. **Climate context:** Archive or realtime weather as environment, not as a predicted case delta.
4. **Existing rule-based risk engine:** leave as prototype; do not dress it up as the new validated malaria EW.

Do not ship NORMAL/WATCH/ELEVATED/HIGH from this sample.

---

## 14. Recommended target

**Not now.** Do not freeze a training target.

**When history is sufficient**, the target to define is:

**Past-only district–season anomaly of malaria positivity** (and, separately, a tests-adjusted or completeness-flagged count deviation for logistics).

Not: `malaria_confirmed(t+1)` ML.  
Not: `positivity(t+1)` ML.  
Not: a four-class climate classifier on current residuals.

---

## 15. Recommended methodology

| Now | Later (after more years) |
| --- | ------------------------ |
| No new ML | Still prefer **statistical / rule-based** anomaly over trees unless residuals appear |
| Do not tune HistGB / XGBoost / RF / nets | Expanding district-month mean/median; minimum n; `INSUFFICIENT_HISTORY` |
| Do not invent 4-class cuts | Percentiles or robust z only with enough prior years |
| Document persistence as the case-load method | Climate as covariate/context, not the definition of “high risk” |

AI/ML elsewhere in CHEWS (e.g. flood prototype) is a separate question. Do not add a malaria ML component for presentation.

---

## 16. Data required for the next phase

Highest value: **more historical district-months from the same DHIS2 + Archive pipeline** (earlier than `202307` if Analytics returns them), still month-by-month, still no zero-fill, still no population join.

Practical bar before defining an operational anomaly target:

- Prefer **≥4–5 years** of reasonably complete district-months (same 16 districts).
- Enough that most district-calendar-months have **≥3 prior years** at scoring time.
- Re-run the past-only baseline coverage table; do not train ML as the first step.

Also useful, still inside approved sources: keep `malaria_tests`, completeness, and u5 counts as **quality and stratification**, not as silent extra targets.

Not required and not to invent: population denominators, weekly interpolation, t+1 climate.

---

## 17. What should remain unchanged in CHEWS

| Component | Action |
| --------- | ------ |
| `backend/data/trained_models/malaria_model.joblib` | Keep; synthetic prototype; do not overwrite |
| `malaria_predictor.py` | Keep disconnected from live DHIS2 |
| `malaria_forecast_v1` artifacts | Keep as experiment |
| `malaria_positivity_forecast_v1` artifacts | Keep as experiment |
| Original 535-row panel | Keep |
| Dashboard / frontend | No change this phase |
| `/api/healthcare/forecast/live` | No change; still `forecast_engine` + optional DHIS2 overlay + prototype climate constants |
| **Risk engine** | **No change** (see below) |

### Current risk engine (read-only review)

`risk_engine.assess()` is **rule-based aggregation**:

`final = 0.4 × environmental + 0.4 × epidemiological + 0.2 × exposure`

- **Environmental:** sigmoid / ecological curves on rainfall, temperature, humidity (`environmental.py`). Optional synthetic GBT variant; not the DHIS2 Archive panel.
- **Epidemiological:** log-sigmoid on **absolute** `reported_cases` with thresholds **3 / 10 / 25 / 50**, times trend multiplier increasing/stable/decreasing (`epidemiological.py`). DHIS2 district-month sums (thousands) will sit at the ceiling.
- **Exposure:** vulnerable population + exposure level (not from DHIS2 Analytics).
- **DHIS2 entry:** `risk_engine_inputs_from_dhis2()` maps confirmed overlay → `reported_cases` + a 10% month-to-month trend. Climate/vulnerability **gaps are documented**; they are not filled from the historical panel.
- **Live forecast** uses `_LIVE_SIGNALS` climate defaults and `forecast_engine.forecast_disease`; malaria cases may overlay DHIS2. **Neither HistGB is on this path.**

**Safe to leave unchanged:** all of the above, plus flood realtime weather (`weather_api.py`).

**What would need to change later** (not now) for an evidence-based malaria EW: district-season baselines, positivity, completeness flags, Archive climate as context, and epidemiological thresholds that are not 3–50 cases. That is a **separate integration phase** after the data bar in §16.

---

## Final recommendation

**D. COLLECT MORE HISTORICAL DATA BEFORE DEFINING THE TARGET**

Not A: case-load ML failed and is the wrong early-warning question.  
Not B yet: anomaly is the right *future* question, but same-month history is too short and climate residuals too weak to define a detector without invented thresholds.  
Not C: four-class climate-health labels are not supported by residual climate signal or by percentile history.

**Do not train. Do not integrate. Do not change the risk engine or live forecast.**

Stopped here.

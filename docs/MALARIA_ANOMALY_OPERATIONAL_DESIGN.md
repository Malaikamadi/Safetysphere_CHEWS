# Malaria seasonal anomaly — operational design review

**Status:** specification and historical simulation only. **No feature was implemented. No model was trained.**  
**Not modified:** original 535-row panel, GBT, `malaria_model.joblib`, `malaria_forecast_v1`, `malaria_positivity_forecast_v1`, dashboard, risk engine, `/api/healthcare/forecast/live`, `malaria_anomaly_backtest.json`.

This signal is a **contemporaneous seasonal nowcast**. It is **not** an outbreak predictor, **not** a next-month forecast, and **not** AI.

Reproducible gate simulation: `backend/data/04_ai/diagnostics/malaria_anomaly_operational_review.json`  
Rules: `backend/services/malaria_anomaly_operational.py`  
Runner: `backend/training/review_malaria_anomaly_operational.py`  
Tests: `backend/tests/test_malaria_anomaly_operational.py` (plus existing leakage tests)

---

## Recommendation

**A. READY FOR CONTROLLED PILOT**

The pilot must remain **separate from the live CHEWS forecast** until NMCP / MoH explicitly approves both the magnitude gate and any UI. Do not wire this into `/api/healthcare/forecast/live`, the risk engine, or the production dashboard in this phase.

Policy starting point (not fitted): **+3 percentage points** above the past-only expanding seasonal median, after data-quality gates, with testing-bias and sustained-run **context** (not extra alarm classes).

---

## 1. Operational objective

Tell a district or national epidemiologist, at the end of month t:

> For this district and this calendar month, is malaria positivity unusually high relative to the last comparable years — and if so, is that movement accompanied by more confirmed cases, fewer tests, or a reporting problem?

It does **not** tell them that next month will be worse, that climate “caused” the month, or that CHEWS has detected an outbreak.

---

## 2. Statistical evidence vs operational policy

| Item | Kind | Value |
| ---- | ---- | ----- |
| Activity measure | **Data-derived** | `positivity = confirmed / tests` only when `tests > 0` |
| Baseline | **Data-derived** | Expanding median of the same district × calendar month, years strictly before t |
| Primary residual | **Data-derived** | `abs_dev_pp = 100 × (positivity − median)` |
| Robust z | Diagnostic only | **Not** the operational trigger |
| `n_prior ≥ 3` | **Policy**, informed by the data bar | Same rule as the coverage phase |
| Completeness ≥ 0.20 | **Policy**, inherited from frozen forecast experiments | Not re-fitted |
| Magnitude gate +2 / +3 / +5 / +10 pp | **Policy candidates** | Simulated below; **+3 pp** recommended as a starting point |
| Tests change ±15% | **Policy** context flag | Not an alarm level |
| Completeness drop ≥ 0.15 | **Policy** data-quality gate | Suppresses malaria anomaly |
| Absolute tests &lt; 1000 | **Policy** low-volume gate | Rare in this district-month series |
| Wet = May–Oct | **Convention** | Meteorological grouping, not a malaria finding |

Empirical distribution of `abs_dev_pp` on 348 quality-pass rows (descriptive, **not** a cut): p50 = **−0.9 pp**, p75 = **+1.2 pp**, p90 = **+4.0 pp**, p95 = **+5.9 pp**. A +3 pp gate sits between p75 and p90. That proximity is why +3 is a reasonable *policy* start — and why it must not be sold as a learned discovery.

---

## 3. Operational signal (proposed)

**A.** Past-only expanding seasonal median (unchanged from the backtest).  
**B.** Absolute positivity deviation in percentage points (primary).  
**C.** Data-quality gates (below).  
**D.** Testing-bias / case-volume context (below).  
**E.** Optional sustained-run annotation (consecutive calendar months passing the same gate).

```
IF data-quality gate fails
    → status = data_quality_issue | insufficient_history | no_observation
    → do not issue a malaria anomaly
ELSE IF abs_dev_pp ≥ GATE_PP
    → status = unusual_positivity
    → attach context flags and consecutive-month count
ELSE
    → status = within_seasonal_baseline
```

Robust z is stored in the diagnostic backtest only. It is not used here.

---

## 4. Magnitude-gate simulation

Universe: comparable era `202106`–`202608`, chronological scores from `202406`, 935 scored rows, **348** passing quality gates (576 insufficient history, 18 low completeness, 46 reporting collapse, 12 low test volume; reasons can co-occur). Leakage audit **passed**. Missing DHIS2 cells were not filled with zero.

| Gate (policy) | Flags | Rate of quality-pass | Confirmed up vs last year | Tests down ≥15% | Followed by same gate at t+1 | Isolated / 2+ / 3+ months | Wet / dry |
| ------------- | ----: | -------------------: | ------------------------: | --------------: | ---------------------------: | ------------------------- | --------- |
| **+2 pp** | 66 | 19.0% | 54 (82%) | 4 (6%) | 52% | 34 / 32 / 17 | 30 / 36 |
| **+3 pp** | **46** | **13.2%** | **41 (89%)** | **3 (7%)** | **56%** | **23 / 23 / 13** | **22 / 24** |
| **+5 pp** | 24 | 6.9% | 22 (92%) | 2 (8%) | 45% | 14 / 10 / 6 | 11 / 13 |
| **+10 pp** | 5 | 1.4% | 5 (100%) | 0 | 25% | 4 / 1 / 0 | 0 / 5 |

### District concentration

| Gate | Districts that ever flag | Dominant | Silent |
| ---- | -----------------------: | -------- | ------ |
| +2 pp | 12 | Kono 14 | Bonthe, Kailahun, Moyamba, Tonkolili |
| **+3 pp** | **11** | **Kono 13, Karene 9, Pujehun 6, Port Loko 6** | Bo, Bonthe, Kailahun, Moyamba, Tonkolili |
| +5 pp | 5 | Kono 11 of 24 | 11 districts never flag |
| +10 pp | 2 | Kono 4, Karene 1 | 14 districts never flag |

+5 and +10 collapse onto Kono/Karene. They are not usable as a **national** starting gate. +2 pp adds eight “positivity-only / unsupported” flags. **+3 pp** is the least bad national compromise: uncommon (~2 district-months per scored calendar month), usually accompanied by higher confirmed counts, not wet-season-only, not a Kono-only rule.

Calendar months at +3 pp are spread (Oct/Nov 6 each; June 2). This is a district-season residual, not a rains detector.

**Recommend +3 pp as an operational starting point**, labelled **policy-configured**, subject to NMCP review. Do not select it because 46 is a convenient number. Reject +10 pp as a national gate. Keep +5 pp as a possible later **escalation discussion** (not implemented, not coloured as “high risk”).

---

## 5. Testing-bias and supporting-evidence flags

Not alarm levels. Compared with the **same calendar month last year**.

| State | Meaning | +3 pp flags |
| ----- | ------- | ----------: |
| A. Positivity anomaly + confirmed increasing | Cases up as well as positivity | **41** |
| B. Positivity anomaly + tests increasing (≥15%) | More testing (may co-occur with A) | 19 |
| C. Positivity anomaly + tests decreasing (≥15%) and confirmed not up | Effort/mix change | **3** |
| D. Completeness deterioration ≥15 pp | **Blocked** as data quality (46 rows never become malaria flags) | 0 among flags |
| E. Positivity anomaly without supporting evidence | Cases and tests do not corroborate | **2** |

Primary message state is ordered: completeness → tests-down-without-case-increase → confirmed-up → tests-up → unsupported.

CHEWS must **not** say “malaria outbreak detected.” The honest stem is always “positivity versus historical seasonal median,” then context.

---

## 6. Data-quality gating

These **suppress** an operational malaria anomaly. They are a different product state from “unusual positivity.”

| Condition | Status | Notes |
| --------- | ------ | ----- |
| No district-month row / empty Analytics | `no_observation` | Includes known holes `202604`, `202607`. **Not zero** |
| `tests` missing or ≤ 0 | `data_quality_issue` | Positivity undefined |
| `n_prior` &lt; 3 | `insufficient_history` | Most of `202106`–`202305` |
| Completeness &lt; 0.20 | `data_quality_issue` | Same floor as frozen experiments |
| Completeness drop ≥ 0.15 vs last year’s same month | `data_quality_issue` (`reporting_collapse`) | 46 rows |
| Tests &lt; 1000, or &lt; 25% of last year’s same-month tests | `data_quality_issue` (`low_test_volume`) | 12 rows; district-month volumes are usually thousands |
| Latest complete month not yet ingested (live ops) | stale / pending | Not simulated here; a live system should only **alert** on the latest complete month and keep older months as archive |

Quality-blocked scored rows: **587 / 935**, almost all insufficient history. That is expected until three prior comparable years exist.

---

## 7. Sustained-anomaly logic

At the +3 pp policy gate, among 46 flags: **23 isolated**, **23** lasting 2+ months, **13** lasting 3+ months. A skipped calendar month (e.g. `202604`) **breaks** the run; “next observed row” is not used.

| Pattern at +3 pp | n | P(t+1 still ≥ +3 pp) |
| ---------------- | -: | -------------------: |
| Isolated month | 23 | **48%** (10/21 with t+1) |
| Already 2+ consecutive | 23 | **65%** (13/20 with t+1) |

Sustained runs are **somewhat** more likely to continue, not dramatically. Treat consecutive months as **context on the same status** (`unusual_positivity`, “persisted for N months”), not as WATCH vs HIGH. Do not assume three months is an outbreak.

---

## 8. Operational messages (examples)

Language rules: name the district, the positivity, the seasonal median, the deviation in pp, then context. Never “AI predicts an outbreak.” Never “high malaria risk” unless a separately validated risk product says so (the current risk engine is **not** that product).

**Unusual positivity, cases also up (Pujehun `202407`, +6.5 pp):**

> Malaria positivity in Pujehun is 64.0% (historical seasonal median 57.5%; deviation 6.5 percentage points vs a past-only expanding median). Confirmed malaria cases increased 3% compared with the same month last year. This is a contemporaneous seasonal comparison, not an AI outbreak prediction and not a next-month forecast.

**Unusual positivity, testing down (Karene `202406`, +5.8 pp):**

> Malaria positivity in Karene is 68.8% (historical seasonal median 63.0%; deviation 5.8 percentage points vs a past-only expanding median). Interpretation is limited because testing activity decreased 26% versus the same month last year. This is a contemporaneous seasonal comparison, not an AI outbreak prediction and not a next-month forecast.

**Unusual positivity without supporting case/testing movement (Koinadugu `202411`, +3.1 pp):**

> Malaria positivity in Koinadugu is 68.1% (historical seasonal median 65.0%; deviation 3.1 percentage points vs a past-only expanding median). Confirmed cases and testing volume do not independently support an increase; treat as a positivity-only seasonal anomaly. This is a contemporaneous seasonal comparison, not an AI outbreak prediction and not a next-month forecast.

**Reporting completeness (template, not a malaria flag):**

> Malaria positivity in District X is not issued as an operational anomaly because reporting completeness is below the operational threshold or collapsed versus the same month last year. Treat as a data-quality signal pending confirmation.

**Missing month:**

> No malaria observation is available for District X this month. Missing DHIS2 values are not treated as zero cases.

**Within gate:**

> … deviation 1.1 percentage points … This is within the operational magnitude gate of +3 percentage points. This is a seasonal comparison, not an outbreak prediction.

---

## 9. Future CHEWS UI concept (not implemented)

Do **not** build this now. Do **not** reuse `--risk-high` / `--risk-critical` from `tokens.css` for this product. Those tokens belong to the existing rule-based risk engine (case thresholds 3/10/25/50), which saturates on district-month malaria and is **not** a validated seasonal-anomaly scale.

### Card (per district, latest complete month)

| Field | Source |
| ----- | ------ |
| District | org-unit / MFL display name |
| Current positivity | confirmed / tests |
| Historical seasonal median | past-only expanding median |
| Deviation (pp) | `abs_dev_pp` |
| Confirmed cases | `malaria_confirmed` |
| Tests | `malaria_tests` |
| Testing change vs same month last year | % |
| Confirmed change vs same month last year | % |
| Facility completeness | pipeline definition |
| Status | `within_seasonal_baseline` / `unusual_positivity` / `data_quality_issue` / `insufficient_history` / `no_observation` |
| Context | confirmed up / tests down / unsupported / sustained N months |
| Interpretation | operational message above |
| Last updated | DHIS2 ingest time |
| Gate (pp) | labelled “operational policy” |
| Disclaimer | “Seasonal comparison, not an AI forecast” |

### Map (three states, no new colour assignment in this review)

1. **Within seasonal baseline** — quality pass, deviation below gate  
2. **Unusual positivity** — quality pass, deviation ≥ gate (caption shows pp and context, not “high risk”)  
3. **Data quality / missing / insufficient history** — distinct from (2)

If colour is added later, it should be a **new** map legend, approved with NMCP, not the five-class risk badge.

No four-class NORMAL / WATCH / ELEVATED / HIGH.

---

## 10. Threshold governance

| Layer | Who decides | Examples | Shown to users as |
| ----- | ----------- | -------- | ----------------- |
| **Statistical / data-derived** | CHEWS data owners; change only with a new comparable-era extract and leakage tests | Positivity formula, past-only median, era `202106+` | “Calculated from DHIS2” |
| **Public-health operational threshold** | **NMCP / MoH** (with CHEWS product owner as steward) | Magnitude gate (+3 pp start), completeness 0.20, ±15% testing band | “Operational policy” |
| **Alert escalation** | MoH emergency / district DMO SOP — **out of scope** | Who is phoned, whether a bulletin goes to partners | Not a CHEWS model output |

Statistical analysis **does not** determine operational action. A later change of +3 → +5 pp is a **policy** change, not a retraining. The UI should print the current gate and its policy label.

Suggested approval path for a pilot: NMCP malaria M&E + CHEWS technical lead + DHIS2 focal point. Record the gate in config with `source = operational_policy_not_fitted`.

---

## 11. Limitations

1. Only **22** scorable months (`202406`–`202603`).  
2. No independent outbreak line list; “followed by another flag” is not a true-positive.  
3. Kono is over-represented; a national gate will look like a Kono detector unless the card always shows pp and context.  
4. Completeness still uses **current** MFL expected facilities.  
5. Lead time remains weak; this is a nowcast.  
6. Climate is not in the operational rule (previous phase: |r| ≤ 0.10).  
7. Pre-`202106` history stays quarantined.  
8. Live CHEWS still uses a different malaria path (prototype GBT / overlay). This design does not replace it.

---

## 12. Controlled pilot (if approved)

**In scope**

- Shadow table or internal bulletin using this spec  
- Same comparable-era pipeline, persist=False against production contracts  
- Monthly review of flags with NMCP (false story vs useful prompt)

**Out of scope until a later approval**

- Dashboard map  
- Risk engine  
- `/api/healthcare/forecast/live`  
- Any ML model  
- Four-class alerts  
- Language that says outbreak, AI, or high risk

**Success for a pilot** is not “more alerts.” It is whether epidemiologists find the **message + context** more honest than the current live overlay, without acting on MAD-fragile z-scores.

---

## Protection check

| Artifact | Status |
| -------- | ------ |
| Original 535-row panel | Unchanged |
| `malaria_model.joblib` / GBT | Unchanged |
| `malaria_forecast_v1` / positivity v1 | Unchanged |
| `malaria_anomaly_backtest.json` | Unchanged (not overwritten) |
| Dashboard / risk engine / live forecast | Unchanged |
| Model trained | **No** |
| Feature implemented in CHEWS | **No** |

Stopped after this operational design review.

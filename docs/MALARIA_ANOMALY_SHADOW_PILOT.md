# Malaria seasonal anomaly — shadow pilot

**Status:** isolated shadow replay only. **No model was trained. The signal is not on the live CHEWS forecast, dashboard, or risk engine.**

Replay dataset: `backend/data/04_ai/shadow/malaria_anomaly_shadow_latest.json`  
Audit: `backend/data/04_ai/shadow/malaria_anomaly_shadow_audit.json`  
Component: `backend/services/malaria_anomaly_shadow.py`  
Runner: `backend/training/run_malaria_anomaly_shadow.py`

Generated: 2026-09-10T14:36:30Z. Live DHIS2 Analytics was **not** called. Pre-`202106` history was **not** pooled. Missing months were **not** filled with zero.

---

## PURPOSE

Let CHEWS developers and designated reviewers observe how a **seasonal malaria positivity anomaly** behaves on comparable-era DHIS2 data (`202106`–`202608`) **without affecting** production or prototype pathways.

This packet is for review, not for action. It is the controlled observer path requested after the operational design review.

---

## WHAT IT IS

A **statistical, transparent, contemporaneous** seasonal comparison:

district × calendar-month malaria positivity  
versus a **past-only expanding seasonal median**  
with a **+3 percentage-point candidate policy gate**.

Each flag is annotated with testing activity, confirmed-case movement, completeness, data-quality status, and whether the flag persisted for consecutive calendar months.

---

## WHAT IT IS NOT

- **Not AI**
- **Not an ML prediction**
- **Not a next-month forecast**
- **Not an outbreak detector**
- **Not a replacement for public-health surveillance**
- **Not a replacement** for `malaria_model.joblib`, `malaria_forecast_v1`, or `malaria_positivity_forecast_v1`
- **Not a production alert** and **not** a notification

`+3 pp` is a **policy/operational starting threshold**. It is not a machine-learned cut and not an outbreak threshold. It must be reviewed by the appropriate Sierra Leone malaria / public-health authority, including **NMCP**.

---

## SIGNAL

| Piece | Rule |
| ----- | ---- |
| Positivity | `malaria_confirmed / malaria_tests` only when `tests > 0`; missing stays missing |
| Grain | district × calendar month |
| Baseline | past-only expanding **median** of the same district and calendar month |
| Leakage | current month, future months, future years, and t+1 data cannot enter the baseline |
| Era | comparable era `202106`–`202608` only |
| Gate | **+3 pp** (`gate_source = operational_policy_not_fitted`) |
| Sustained | `sustained_anomaly` and `consecutive_anomaly_months`; **no** HIGH / ELEVATED / WATCH levels |

Indicators used: `malaria_confirmed`, `malaria_tests`, `malaria_confirmed_u5`, `malaria_rdt_positive` (where present).

---

## CONTEXT

Every potential anomaly is classified. **None of these is an outbreak label.**

| Class | Meaning |
| ----- | ------- |
| A | Anomaly + confirmed cases increasing vs same month last year |
| B | Anomaly + testing increasing (≥15%) |
| C | Anomaly + testing decreasing (≥15%) and confirmed not up |
| D | Reporting / completeness / missing / insufficient history |
| E | Positivity anomaly without supporting case or testing evidence |

Data-quality gates **block** a malaria anomaly when tests are 0 or missing, the current month is missing, the baseline has fewer than 3 prior years, completeness is below 0.20, reporting collapsed versus last year, test volume is too low, the month is structurally incomplete (&lt;8 districts on a national panel), or required data cannot be validated. Replay does not apply a live-staleness check; a future observer would.

---

## SHADOW RESULTS (frozen comparable-era replay)

| Count | Value |
| ----- | ----: |
| Shadow observations (16 districts × 63 months, including placeholders) | **1008** |
| Observed district-months | **935** |
| Missing placeholders (not zero-filled) | **73** |
| Anomaly flags at +3 pp | **46** |
| Blocked by data quality / insufficient history / no observation | **660** |
| Class A — confirmed cases increasing | **41** |
| Class C — testing down, confirmed not up | **3** |
| Class E — positivity only | **2** |
| Class B as **primary** state | **0** (19 class-A flags also had testing up ≥15%) |
| Sustained (≥2 consecutive calendar months) | **23** |
| Isolated (1 month) | **23** |
| 3+ consecutive months | **13** |
| Leakage audit | **passed** |

District concentration at +3 pp: **Kono 13, Karene 9, Pujehun 6, Port Loko 6**. Bo, Bonthe, Kailahun, Moyamba, Tonkolili never flagged. Sparse late-v1 months `202605`, `202606`, `202608` were already blocked as data quality (low completeness / reporting collapse / low volume) and produced **no** flags.

These counts match the operational design simulation. That is expected: this is the same comparable-era panel and the same +3 pp rule, now written to an isolated shadow dataset.

---

## EXAMPLE SHADOW SIGNALS

**Class A — Pujehun `202407` (isolated).** Positivity 64.0% vs seasonal median 57.5% (**+6.5 pp**). Confirmed cases also increased vs July 2023. Baseline years: 2021, 2022, 2023. Interpretation: seasonal comparison, not an outbreak prediction.

**Class C — Karene `202406`.** Positivity 68.8% vs 63.0% (**+5.8 pp**). Confirmed cases and tests both decreased vs June 2023. Treat as a possible testing/mix artifact until NMCP reviews.

**Class E — Koinadugu `202411`.** Positivity 68.1% vs 65.0% (**+3.1 pp**). Tests unchanged; confirmed cases not increasing. Positivity-only residual at the gate.

**Sustained — Kono `202603`.** Same +3 pp rule persisted for **9** consecutive calendar months, deviation **+10.5 pp**, class A. Recorded as `sustained_anomaly = true`, `consecutive_anomaly_months = 9`. **Not** labelled HIGH or outbreak.

**Missing month — Bo `202604`.** `malaria_confirmed` and positivity are `null`. Status `no_observation`. Missing DHIS2 values are not treated as zero cases.

---

## REVIEW QUESTIONS

For NMCP / malaria surveillance (not for CHEWS to answer alone):

1. Are the flagged districts operationally plausible?
2. Are flags understandable to malaria surveillance teams?
3. Are testing/reporting artifacts being mistaken for anomalies?
4. Are data-quality blocks appropriate?
5. Is the +3 pp threshold useful operationally?
6. Should the threshold remain +3 pp?
7. Should the signal be exposed to users?
8. What public-health action, if any, should follow a signal?

Until those questions are answered by the appropriate authority, CHEWS must **not** expose this signal on the dashboard, live forecast, or risk engine.

---

## SAFETY (this phase)

The shadow pilot **did not**:

- modify `/api/healthcare/forecast/live` or any production API
- modify the risk engine or dashboard UI
- modify `malaria_model.joblib`, `malaria_forecast_v1`, or `malaria_positivity_forecast_v1`
- overwrite the original 535-row panel
- overwrite `malaria_anomaly_backtest.json`
- train a model
- send notifications
- create production alerts
- claim an outbreak, a prediction, or AI capability

Protected SHA-256 hashes were identical before and after the run (see audit `protected_hashes_before`).

---

## RECOMMENDATION

**C. NEEDS NMCP/PUBLIC-HEALTH REVIEW**

The isolated shadow packet exists and is leakage-free. Do not integrate it into live CHEWS. Do not retune +3 pp from this replay alone. Keep the observer path unused by production until NMCP / MoH review the eight questions above.

Stopped after the shadow-pilot phase.

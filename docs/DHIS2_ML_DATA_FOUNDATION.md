# DHIS2 + climate data foundation (training readiness)

This document records the **code audit findings** and the **data-foundation pipeline** added so CHEWS can decide, honestly, whether a new malaria model may be trained.

It is **not** a claim that a new model has been trained.

---

## Transparency: the existing malaria GBT

The current malaria GradientBoostingRegressor (`backend/models/malaria_predictor.py`, artifact `data/trained_models/malaria_model.joblib`) is a **synthetic-data prototype**.

| Fact | Evidence |
| ---- | -------- |
| Training table | `backend/data/raw/CHEWS_SierraLeone_Malaria_Dataset.csv` (500 rows, catalogued as synthetic) |
| Target name | `malaria_cases` |
| Features | rainfall, temperature, humidity, stagnation, breeding sites, fever, density, district encoding + 3 interactions |
| Live DHIS2 field | `malaria_confirmed` (`XHQqFqfUfIf`) — **different name and meaning** |
| Inference path | `POST /api/healthcare/ml/malaria-predict` only (caller-supplied JSON) |
| Dashboard | Does **not** call the GBT |
| Historical panel | Does **not** call `malaria_predictor.predict()` |

That mismatch is **intentional and documented**. It is safer than silently mapping live HMIS cells onto the synthetic contract.

**Do not** feed live DHIS2 into `malaria_predictor.predict()`. **Do not** retrain the current joblib until `GET /api/dhis2/historical/readiness` returns `READY FOR MODEL TRAINING`.

---

## Target architecture (implemented as a foundation, not a trained model)

```
DHIS2 Analytics (explicit YYYYMM, LEVEL-5)
        ↓
Raw national extract (01_raw/dhis2/historical/)
        ↓
Validation (quality report; missing stays null, not 0)
        ↓
Facility → district mapping (existing org-unit + MFL walk)
        ↓
District-month aggregation (sum non-null facility counts)
        ↓
Completeness report

Open-Meteo Archive (district centroids, daily ERA5-style series)
        ↓
Monthly rainfall / temperature / humidity
        ↓
district_slug + YYYYMM

DHIS2 district-month  +  climate district-month
        ↓
Temporally aligned join
        ↓
Lags + malaria_confirmed_next (t+1)
        ↓
Training-readiness verdict
```

Realtime flood weather (`services/weather_api.py`, 24h precipitation) is **unchanged** and is **not** this climate series.

---

## What the default mock extract actually contains

Bundled Analytics fixture: **2 months** (`202508`, `202509`) × **1 facility**. Asking for 36 months in mock mode still yields that fixture. The completeness report compares **requested vs observed**, so mock mode is expected to return **NOT READY FOR MODEL TRAINING**.

There is no multi-year live HMIS dump in git (raw extracts are gitignored).

---

## API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/dhis2/historical/extract` | Explicit monthly DHIS2 extract + district-month + completeness |
| POST | `/api/dhis2/historical/climate` | Open-Meteo Archive monthly climate |
| POST | `/api/dhis2/historical/panel` | Join, feature lags, **READY / NOT READY** |
| GET | `/api/dhis2/historical/readiness` | Last verdict |

Operational ingest `POST /api/dhis2/ingest` (default `LAST_12_MONTHS`) is unchanged and still must not retrain the GBT.

Live historical extract requires `DHIS2_MOCK_MODE=false` and HMIS credentials. Live climate requires `CLIMATE_ARCHIVE_MOCK_MODE=false`.

Period queries are **comma-separated YYYYMM**. `LAST_5_YEARS` is **not** used (DHIS2 treats that as yearly periods).

---

## Training-readiness bars

All of the following must pass:

1. Health source is **live DHIS2** (not mock)
2. Climate source is **Open-Meteo Archive** (not the monthly fixture)
3. At least **36** requested **and observed** monthly periods
4. At least **10** districts
5. District-month completeness ≥ **0.5** (share of district × requested-month cells with non-null `malaria_confirmed`)
6. Climate coverage ≥ **0.9** of feature rows
7. At least **200** trainable rows after requiring lag-1 health, climate at t, and `malaria_confirmed` at t+1

Target for a **future** model: **`malaria_confirmed_next`**.

Until live extracts exist, the honest verdict is:

**NOT READY FOR MODEL TRAINING**

---

## Files

| Role | Path |
| ---- | ---- |
| Monthly window helpers | `backend/services/dhis2_periods.py` |
| Historical DHIS2 extract | `backend/services/dhis2_historical.py` |
| Archive climate | `backend/services/climate_archive.py` |
| Join + verdict | `backend/services/training_panel.py` |
| Realtime weather (untouched) | `backend/services/weather_api.py` |
| Prototype GBT (untouched) | `backend/models/malaria_predictor.py` |

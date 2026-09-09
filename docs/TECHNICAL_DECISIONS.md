# CHEWS technical decisions

Each item is grounded in the implementation. Where the **reason** is not written in code comments or docs, it is marked **inferred rationale**.

---

## 1. FastAPI

| | |
| --- | --- |
| **Decision** | Python FastAPI (`backend/main.py`) |
| **Reason** | **Inferred:** rapid REST + OpenAPI (`/docs`) for an MVP evaluation |
| **Advantages** | Pydantic validation; async-capable; obvious evaluator entry (`/docs`) |
| **Trade-offs** | Serverless cold start + in-process training; Python ML deps on the web tier |
| **Alternatives** | Flask, Django, Node; separate model microservice |
| **Future** | Keep FastAPI; move training fully offline; fail closed on import errors |

---

## 2. Vanilla HTML/CSS/JS vs SPA framework

| | |
| --- | --- |
| **Decision** | Static pages in `frontend/`; Vercel static build |
| **Reason** | **Inferred:** zero frontend toolchain for deploy; each page is a dashboard |
| **Advantages** | Simple hosting; no Node required for the product |
| **Trade-offs** | Duplicated `API = "/api"`; no shared state layer; hardcoded HTML KPIs |
| **Alternatives** | React/Vue (a `frontend-react/` Vite app exists but is still the default starter) |
| **Future** | Either finish one React app **or** delete `frontend-react/` to avoid evaluator confusion |

---

## 3. Stateless / no database

| | |
| --- | --- |
| **Decision** | CSV + joblib + RAM alert list |
| **Reason** | Comment in `alert_engine.py`: “would be DB in production.” **Inferred** for the rest: speed of MVP |
| **Advantages** | Easy clone-and-run; no credentials for a database |
| **Trade-offs** | No audit trail; alerts and weather cache are ephemeral; no multi-instance consistency |
| **Alternatives** | SQLite, Postgres, Redis |
| **Future** | Required before any real alert or CHW report workflow |

---

## 4. Rule-based scoring as the primary `/predict` path

| | |
| --- | --- |
| **Decision** | Weighted heuristics; `environmental.predict` ignores the in-process GBT |
| **Reason** | Documented in `environmental.py` (“Uses rule-based model; ML model is used for validation/comparison”) |
| **Advantages** | Deterministic; explainable factor strings; no silent joblib miss on the main path |
| **Trade-offs** | Thresholds are expert guesses; easy to over-claim as “AI” |
| **Alternatives** | Serve only sklearn; Bayesian hierarchical model on real DHIS2 |
| **Future** | Keep rules as **baseline** until real-data models win |

---

## 5. sklearn Gradient Boosting / Random Forest (not Logistic Regression)

| | |
| --- | --- |
| **Decision** | GBT/RF in training script and model cards |
| **Reason** | **Inferred:** tabular synthetic features, sklearn already in requirements |
| **Advantages** | Nonlinear effects; feature importances for cards |
| **Trade-offs** | Overfit on n=100–500; community RF leaked; older README said Logistic Regression |
| **Alternatives** | Logistic / Poisson GLM (stronger baseline story), gradient boosting with proper CV |
| **Future** | Publish GLM baselines on **real** series first |

---

## 6. Synthetic data for ML

| | |
| --- | --- |
| **Decision** | Generated CSVs labelled as CHEWS training data |
| **Reason** | **Inferred:** no DHIS2 data-sharing in-repo; demonstrate pipeline |
| **Advantages** | Reproducible `random_state=42`; model-card honesty on several files |
| **Trade-offs** | Filename `dhis2_malaria_chews_v1.csv` is misleading; metrics unusable operationally |
| **Alternatives** | Public climate + published malaria incidence (still not DHIS2 microdata) |
| **Future** | Replace; keep synthetic only in `tests/fixtures/` |

---

## 7. Real MoH MFL identity without inventing operations

| | |
| --- | --- |
| **Decision** | `MFL_PATH` = `moh_dhis2_core_health_facilities.csv`; docstring forbids inventing beds |
| **Reason** | Explicit in `facility_mfl.py` |
| **Advantages** | Evaluator can trust coordinates; ethical for a health map |
| **Trade-offs** | Surge cannot do real bed math; UI must show “not assessed” |
| **Alternatives** | Continue using synthetic readiness CSV as if it were MoH — **worse** |
| **Future** | Join official operational indicators on `id` |

---

## 8. Hardcoded live signals for Forecast/Surge UI

| | |
| --- | --- |
| **Decision** | `_LIVE_SIGNALS` dict instead of user-entered climate on those pages |
| **Reason** | **Inferred from product direction in UI:** dashboard should show risk, not be a calculator. **Not a comment in that dict.** |
| **Advantages** | Matches “live dashboard” UX; POST forecast still exists internally |
| **Trade-offs** | Looks live; is not live; can mislead evaluators |
| **Alternatives** | Open-Meteo + last DHIS2 week; clearly labelled “demo scenario” |
| **Future** | Replace constants; keep a visible **as-of** timestamp |

---

## 9. Optional Open-Meteo with synthetic fallback

| | |
| --- | --- |
| **Decision** | `weather_api.fetch_realtime_weather`; 2s timeout; no API key |
| **Reason** | Comments: free, no key; cache to avoid rate limits |
| **Advantages** | Sometimes real precipitation |
| **Trade-offs** | Mixed live/fake without a mandatory `data_source` badge in every response field (**verify UI**); timeout failures look like weather |
| **Alternatives** | Fail visibly; never jitter |
| **Future** | Always return `source: open-meteo | climatology-simulation` |

---

## 10. In-memory alerts

| | |
| --- | --- |
| **Decision** | `alert_engine._active_alerts` |
| **Reason** | Code comment: production would use DB |
| **Advantages** | Demo trigger → list in one process |
| **Trade-offs** | Useless on Vercel multi-instance |
| **Alternatives** | Redis, Postgres |
| **Future** | Phase 4 requirement |

---

## 11. Dual `/api` and root router mounts

| | |
| --- | --- |
| **Decision** | `include_router(..., prefix="/api")` and again without prefix |
| **Reason** | Comment: “guarantee compatibility” |
| **Advantages** | Local Uvicorn can hit either path |
| **Trade-offs** | Duplicate routes in OpenAPI; Vercel still only forwards `/api/*` |
| **Alternatives** | Single prefix `/api`; add `/api/predict` and `/api/health` |
| **Future** | One canonical prefix; fix Vercel + JS `/api/health` |

---

## 12. Client-side roles

| | |
| --- | --- |
| **Decision** | `auth.js` `localStorage` `chews-role`; default admin |
| **Reason** | **Inferred:** demo of DHMT vs CHW vs partner nav |
| **Advantages** | Fast UX story |
| **Trade-offs** | Zero security; sidebar links to admin sections that are not implemented (hash routes on `index.html`) |
| **Alternatives** | OIDC, DHIS2 token |
| **Future** | Server sessions; never default to admin |

---

## 13. Resilient imports / debug endpoint

| | |
| --- | --- |
| **Decision** | Try/except per module; `GET /api/debug` |
| **Reason** | Comment: “Temporary debug endpoint to diagnose Vercel runtime issues.” |
| **Advantages** | Easier remote diagnosis |
| **Trade-offs** | Partial startups; information leak |
| **Alternatives** | Health that reports **ok/degraded** without filesystem listing; fail deploy if MFL missing |
| **Future** | Remove debug; structured `/healthz` |

---

## 14. Apache 2.0 licence

| | |
| --- | --- |
| **Decision** | `LICENSE` SafetySphere Global 2026 |
| **Reason** | **Not stated** beyond the file |
| **Advantages** | Clear OSS terms for evaluators |
| **Trade-offs** | Health data (when added) needs separate DPA |
| **Future** | Keep licence; add NOTICE for third-party (Leaflet, OSM, Open-Meteo ToS) |

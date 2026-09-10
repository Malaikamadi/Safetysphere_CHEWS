# CHEWS — Climate-Health Early Warning System

**SafetySphere** · Sierra Leone prototype · UNICEF Venture Fund evaluation **RFPS-NYH-2026-503931**

CHEWS is a **prototype climate-health intelligence dashboard** for Sierra Leone. It demonstrates how environmental, epidemiological, and facility-registry inputs could support early warning and health-system planning. It is an **MVP**, not a clinically or epidemiologically validated outbreak-prediction system.

---

## Problem

Sierra Leone faces climate-sensitive health risks (malaria, flooding, heat, waterborne disease). District teams and community health workers need a shared picture of hazard, facility location, and surge pressure. Today those signals sit in disconnected systems (DHIS2, weather services, paper reports).

## Purpose

CHEWS is designed to become a **live early-warning layer** on top of official data (DHIS2, Master Facility List, climate feeds). The current repository implements a **working prototype** of that idea: a FastAPI backend, a multi-page dashboard, a rule-based risk engine, experimental ML models trained on **synthetic** data, and a real Ministry of Health DHIS2 facility identity/coordinate list.

## Current MVP scope

| Status | What it means in this repo |
| ------ | -------------------------- |
| **Implemented** | FastAPI API, static dashboard, rule-based `/predict` risk scoring, MoH DHIS2 Master Facility List map, view-only disease/surge dashboards, flood-atlas UI, keyword health assistant, in-memory alerts, DHIS2 Analytics ingest (mock + live client) |
| **Prototype** | Situation Room (simulated national command centre), digital twins, sensors, community-report ML, Open-Meteo rainfall overlay |
| **Experimental** | sklearn models (Gradient Boosting / Random Forest) trained on synthetic CSVs |
| **Not implemented** | Scheduled DHIS2 jobs on durable hosting, validated real-time surveillance, authentication, database, automated SMS/push alerts, clinical validation, production monitoring |

The dashboard is **view-oriented**. Healthcare Forecast and Surge pages refresh from server-side signals; they do **not** ask a user to type rainfall or case counts. Those POST endpoints still exist for internal/demo use.

---

## Key features (verified in code)

- **Rule-based malaria risk scoring** (`POST /predict`) combining environmental, epidemiological, and exposure sub-scores.
- **Healthcare facility explorer** loaded from `moh_dhis2_core_health_facilities.csv` (1,615 MoH DHIS2 facilities: id, code, name, level, coordinates). Operational fields (beds, staff, power, water) are **not invented**; they are shown as not assessed.
- **View-only disease forecast and surge views** (`GET /api/healthcare/forecast/live`, `GET /api/healthcare/surge/live`) using **hardcoded climatological/case constants** unless a DHIS2 ingest has been stored (malaria case overlay only).
- **DHIS2 Analytics ingest** (`/api/dhis2/*`) against Sierra Leone HMIS. Default mock mode; live mode needs env credentials. Does **not** retrain the synthetic malaria GBT. Historical monthly extract + Archive climate + **READY/NOT READY** verdict: [docs/DHIS2_ML_DATA_FOUNDATION.md](docs/DHIS2_ML_DATA_FOUNDATION.md). See also [docs/DHIS2_INTEGRATION.md](docs/DHIS2_INTEGRATION.md).
- **Flood Atlas** combining a static 23-zone catalogue with rule-based flood scoring; optional Open-Meteo fetch with synthetic fallback.
- **Point-of-care triage** via symptom keyword scoring (not a diagnostic model).
- **Health assistant** via keyword matching (not an LLM).
- **Role-styled UI** (admin / district / worker / partner) stored in `localStorage` — **not** server authentication.

---

## Architecture overview

```
Browser (frontend/*.html)
        │  fetch /api/...
        ▼
FastAPI (backend/main.py)
        ├── routers/          REST endpoints
        ├── models/           rule engines + sklearn wrappers
        ├── services/         MFL, DHIS2 ingest, forecast, alerts, weather, triage
        └── data/             CSVs, joblib artifacts, reference tables
```

See [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) for component diagrams.

---

## Project structure

```
SafetySphere_CHEWS/
├── backend/
│   ├── main.py                 # FastAPI app, CORS, /health /predict /ask
│   ├── requirements.txt        # Runtime Python deps
│   ├── requirements-dev.txt    # Training extras (pandas, matplotlib)
│   ├── config/                 # DHIS2 env/indicator configuration
│   ├── routers/                # strategic, early_warning, healthcare, point_of_care, situation_room, dhis2
│   ├── tests/                  # pytest (DHIS2 ingest/parsing)
│   ├── models/                 # risk_engine, environmental, epidemiological, flood_risk, sklearn wrappers
│   ├── services/               # facility_mfl, forecast_engine, alert_engine, weather_api, …
│   ├── training/               # train_all_models.py
│   └── data/
│       ├── 01_raw/             # Source CSVs (mostly synthetic; MFL is real identity/coords)
│       ├── 02_staging/         # Empty placeholders (.gitkeep)
│       ├── 03_curated/         # Empty placeholders (.gitkeep)
│       ├── 04_ai/models/       # joblib + model cards
│       ├── trained_models/     # Legacy joblib copies used at runtime
│       └── reference/          # Districts, flood zones
├── frontend/                   # Deployed UI (static HTML/CSS/JS)
├── frontend-react/             # Incomplete Vite/TS scaffold — not the product UI
├── vercel.json                 # Vercel: Python API + static frontend
├── LICENSE                     # Apache-2.0
└── docs/                       # This documentation suite
```

---

## Technology stack

| Layer | Technology | Notes |
| ----- | ---------- | ----- |
| Backend | FastAPI 0.100+, Uvicorn, Pydantic 2 | Version string in app: `4.0.0` |
| Scoring | NumPy rule engines | Primary `/predict` path |
| ML | scikit-learn, joblib | Optional; synthetic training data |
| Frontend | HTML, CSS, vanilla JS | Leaflet maps, Lucide icons via CDN |
| Maps | OpenStreetMap tiles | No map API key |
| Optional weather | Open-Meteo (no key) | Flood dashboard only; 2s timeout; synthetic fallback |
| Hosting | Vercel (`vercel.json`) | `/api/*` → Python; `/*` → `frontend/` |
| Database | None | In-memory alert list only |
| Auth | None on the API | Client `localStorage` role only |

Python **3.10+** is required by syntax in the backend (`str \| None` union types). The exact interpreter is **not pinned** (`runtime.txt` is absent).

---

## Installation

```bash
git clone <repository-url>
cd SafetySphere_CHEWS

cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

To **retrain** models you also need:

```bash
pip install -r requirements-dev.txt
```

`pandas` is **not** in the runtime requirements file. Training will fail without the dev extra.

---

## Configuration

Local DHIS2 mock mode needs **no** credentials. Optional `.env` (see `.env.example`) is loaded via `python-dotenv` when present.

| Variable | Used? | Notes |
| -------- | ----- | ----- |
| `DHIS2_*` | DHIS2 ingest | Documented in [docs/DHIS2_INTEGRATION.md](docs/DHIS2_INTEGRATION.md) |
| CORS | Hardcoded | `allow_origins=["*"]` in `backend/main.py` |

Do not commit secrets. None were found as live credentials in this audit; see [docs/SECURITY.md](docs/SECURITY.md).

---

## Running the backend

From `backend/` with the venv active:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- API: http://127.0.0.1:8000  
- OpenAPI: http://127.0.0.1:8000/docs  

On Vercel, only paths under `/api/` are routed to Python. Root paths `/health`, `/predict`, and `/ask` exist in code but **are not mapped** by `vercel.json`. Prefer `/api/...` router paths in hosted environments. Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Running the frontend

The product UI is **`frontend/`**, not `frontend-react/`.

```bash
cd frontend
python3 -m http.server 3000
```

Open http://localhost:3000/login.html  

For local API calls, the JS modules use `const API = "/api"`. Serving the frontend on port 3000 while the API is on 8000 will **not** proxy `/api`. Options:

1. Use the OpenAPI UI at port 8000 for API checks, or  
2. Put a reverse proxy in front (as Vercel does), or  
3. Open pages through a setup that forwards `/api` to Uvicorn.

`frontend-react/` is a default Vite starter (`src/main.ts` still shows the Vite counter). It is **not** wired in `vercel.json`.

---

## API overview

Full contract: [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md).

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/health` | Liveness (root path; may be unreachable on Vercel) |
| GET | `/api/debug` | Runtime diagnostics — **should not be public** |
| POST | `/predict` | Rule-based composite malaria risk |
| POST | `/ask` | Keyword health assistant |
| GET | `/api/healthcare/facilities` | Compact MoH MFL list |
| GET | `/api/healthcare/forecast/live` | View-only disease forecast |
| GET | `/api/healthcare/surge/live` | View-only surge view |
| GET | `/api/strategic/flood-dashboard` | Flood atlas payload |
| POST | `/api/poc/triage` | Symptom-score triage |
| GET | `/api/situation-room` | Simulated national dashboard |
| GET | `/api/dhis2/status` | DHIS2 config (no secrets) |
| POST | `/api/dhis2/ingest` | Pull Analytics into the data lake |
| GET | `/api/dhis2/malaria` | Curated malaria series |

Routers are mounted **twice** (with and without `/api`) in `backend/main.py`.

---

## Example prediction

`POST /predict` uses **rule-based** aggregation in `models/risk_engine.py`, **not** Logistic Regression.

**Request**

```json
{
  "rainfall": 180,
  "temperature": 28,
  "humidity": 82,
  "reported_cases": 40,
  "trend": "increasing",
  "vulnerable_population": 120,
  "exposure_level": "high"
}
```

**Response shape** (`PredictionOutput`)

```json
{
  "final_risk": 0.72,
  "risk_level": "High",
  "breakdown": {},
  "explanation": "…",
  "factors": ["…"],
  "recommendations": ["…"]
}
```

Thresholds in code: Low &lt; 0.30, Medium ≤ 0.60, else High. Weights: environmental 0.40, epidemiological 0.40, exposure 0.20.

---

## AI/ML methodology summary

- **Primary live scorer:** heuristic functions (sigmoid/bell rainfall, temperature, humidity; log-sigmoid case burden; categorical exposure).  
- **sklearn artifacts:** GradientBoosting / RandomForest trained on **synthetic** CSVs (`random_state=42`, 80/20 split).  
- **Community-flood classifier:** model card marks it **BLOCKED** (perfect 1.0 metrics; likely leakage).  
- **No clinical or epidemiological validation** is present in the repository.  
- Metrics such as flood AUC 0.991 are **in-sample on synthetic data** and must not be read as real-world performance.

Details: [docs/AI_ML_METHODOLOGY.md](docs/AI_ML_METHODOLOGY.md).

---

## Current limitations

- Training and most “DHIS2” CSVs are **synthetic**.  
- Live forecast/surge “observed” climate and cases are **constants** in `healthcare.py` (`_LIVE_SIGNALS`).  
- No database, no server-side auth, CORS `allow_origins=["*"]` with `allow_credentials=True`.  
- No automated tests.  
- Data-lake layers `02_staging` and `03_curated` are empty; `backend/pipelines/` does not exist.  
- Situation Room facilities/sensors are **hardcoded mocks**, separate from the MoH MFL.

Honest assessment: [docs/LIMITATIONS_AND_ROADMAP.md](docs/LIMITATIONS_AND_ROADMAP.md).

---

## Future roadmap (planned — not in code)

1. Schedule DHIS2 ingest on durable hosting; replace remaining climate constants with weather APIs.  
2. Attach operational MFL indicators without fabricating missing fields.  
3. Retrain and validate models on historical Sierra Leone surveillance.  
4. Add authentication, audit logs, and a real alert channel.  
5. Pilot with district health teams; then consider national scale.

---

## Development status

| Item | Status |
| ---- | ------ |
| Prototype dashboard | Implemented |
| Rule-based risk engine | Implemented |
| MoH facility identity + map | Implemented |
| sklearn models | Experimental / pre-production |
| DHIS2 API integration | Implemented (ingest + mock; live needs credentials) |
| Production operations | Not implemented |

---

## Security notes

- APIs are **unauthenticated**.  
- `/api/debug` exposes cwd, data listing, and import errors.  
- Partner HTML contains a **demo** Bearer string (`chews_live_partner_key_2024`); the API does not enforce it.  
- Treat all health-related inputs as sensitive even though the MVP stores nothing durably.

See [docs/SECURITY.md](docs/SECURITY.md).

---

## Licence

Apache License 2.0. Copyright 2026 SafetySphere Global. See [LICENSE](LICENSE).

## Contact / ownership

**Owner:** SafetySphere Global (per `LICENSE`).  
or Email Maliakamadi@safetysphereglobal.org**.

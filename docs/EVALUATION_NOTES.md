# CHEWS evaluation notes

For a UNICEF technical evaluator working **RFPS-NYH-2026-503931**. This page is an index of **verified** behaviour versus **demo theatre**.

---

## What currently works

Verified by inspecting source (runtime of *your* clone should still be checked with the checklist below):

- FastAPI app boots models/MFL in `startup` (`backend/main.py`).  
- Pydantic-validated `POST /predict` rule engine (`models/risk_engine.py`).  
- Keyword `POST /ask` and `POST /api/poc/ask`.  
- Symptom-score `POST /api/poc/triage`.  
- MoH DHIS2 facility CSV load and facility HTTP APIs (`services/facility_mfl.py`, `routers/healthcare.py`).  
- View-only `GET /api/healthcare/forecast/live` and `/surge/live`.  
- Flood dashboard/forecast routes and Open-Meteo helper.  
- Early-warning assess/trigger/alerts (in-memory).  
- Strategic vulnerability, hazard, pollution, carbon, district-priorities.  
- Situation Room JSON for the command-centre UI (**simulated**).  
- Static dashboard pages with Leaflet OSM maps.  
- joblib predict wrappers for malaria, readiness, community flood, flood (if files load).  
- Model cards documenting synthetic data and the blocked community model.  
- Apache-2.0 licence.

---

## What can be demonstrated

1. Clone, `pip install -r backend/requirements.txt`, `uvicorn main:app`.  
2. Open `/docs`, execute `POST /predict` with the body in the README.  
3. Open `frontend/healthcare.html` **behind an `/api` proxy** and show facility pins + forecast panel.  
4. Show a facility detail with **Data not available** for beds.  
5. Show `community_reports_v1_model_card.json` **BLOCKED**.  
6. Show flood atlas; disclose Open-Meteo vs wobble.  
7. Show Situation Room and **say it is mock data**.

That is a coherent **MVP engineering demonstration**, not a validated climate-health early warning **service**.

---

## What is experimental

- All sklearn models on synthetic labels.  
- In-process environmental GBT cloned from rules.  
- Community-flood classifier (invalid).  
- Readiness regressor vs synthetic facilities.  
- Anomaly-detect ratio rules.  
- Carbon accounting heuristic.  
- Digital twins / sensors / scenario simulator.  
- `frontend-react/` playground.

---

## What is planned

DHIS2 live integration, operational MFL attributes, real CHW ingestion, true forecasting, auth, database, monitoring, national scale — see [LIMITATIONS_AND_ROADMAP.md](LIMITATIONS_AND_ROADMAP.md). Sidebar “Administration → DHIS2 / Weather APIs / Audit Logs” entries are **not backed by pages/APIs**.

---

## Evidence in repository

| Capability | Evidence |
| ---------- | -------- |
| App entry | `backend/main.py` |
| Risk formula | `backend/models/risk_engine.py` `WEIGHTS`, `RISK_THRESHOLDS` |
| Env rules | `backend/models/environmental.py` `predict_rule_based` |
| Epi rules | `backend/models/epidemiological.py` |
| MFL | `backend/data/01_raw/master_facility_list/moh_dhis2_core_health_facilities.csv` |
| Live constants | `backend/routers/healthcare.py` `_LIVE_SIGNALS` |
| Forecast rules | `backend/services/forecast_engine.py` |
| Weather | `backend/services/weather_api.py` |
| Training | `backend/training/train_all_models.py` |
| Metrics / leakage | `backend/data/04_ai/models/*_model_card.json` |
| UI | `frontend/*.html`, `frontend/*.js` |
| Hosting | `vercel.json` |
| Deps | `backend/requirements.txt` |

---

## Reproducibility

**Evaluator steps:**

```bash
git clone <url> && cd SafetySphere_CHEWS
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
# another terminal:
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"rainfall":180,"temperature":28,"humidity":82,"reported_cases":40,"trend":"increasing","vulnerable_population":120,"exposure_level":"high"}'
```

Same `/predict` inputs should yield the **same** score (pure functions + fixed weights). Flood dashboard **without** Open-Meteo is **not** bit-stable (time-based RNG). Open-Meteo adds network variance.

Retraining sklearn is a **second** path (`requirements-dev.txt` + `python -m training.train_all_models`) and will not match production if CSV paths differ.

Python patch version is **unpinned** — sklearn joblib may fail across sklearn majors.

---

## Known limitations (short)

Synthetic ML; fake live epi; no auth; no DB; no tests; debug endpoint; CORS; Vercel root-route gap; mock Situation Room; blocked community model; overstated FastAPI description; incomplete data lake.

---

## Evaluation checklist

Marking: **[x]** = confirmed **in the repository** (code/files exist as described). **Runtime** of a fresh machine is still the evaluator’s job. Items that are **code-present but environment-dependent** stay unchecked for execution.

- [x] Repository can be cloned (git repo present)  
- [ ] Dependencies install successfully *(not executed in this documentation pass)*  
- [ ] Backend starts *(not executed in this documentation pass)*  
- [ ] Frontend starts *(static files present; `/api` proxy not included)*  
- [x] `GET /health` **implemented** in `main.py`  
- [x] `POST /predict` **implemented** (rule-based; schema ≠ old README)  
- [x] `POST /ask` **implemented** (keywords)  
- [x] Prediction **can** be reproduced given the same JSON *(deterministic engine)*  
- [x] Documentation suite present under `docs/` + README  
- [x] No live secrets found in-repo *(fake partner Bearer is a demo string, not a server secret)*  

**Do not tick as working on Vercel without testing:** `/health`, `/predict`, `/ask`, `/api/health`.

**Do not tick community-flood as a successful model.**

---

## Questions an evaluator should ask the team

1. When will `_LIVE_SIGNALS` be replaced, and what is the as-of stamp?  
2. Who owns DHIS2 access, and why is the malaria file named DHIS2 if synthetic?  
3. Why is `/api/debug` still deployed?  
4. Why serve a BLOCKED model over HTTP?  
5. How will CHWs be stopped from treating triage colours as diagnosis?  
6. Which facility list is authoritative in the Situation Room vs Healthcare map?

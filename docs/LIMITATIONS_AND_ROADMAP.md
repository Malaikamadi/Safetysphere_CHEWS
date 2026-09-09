# CHEWS limitations and roadmap

Brutally honest assessment for technical evaluators. Items are included only where the codebase supports them.

---

## Current limitations

### Data and models

- **Synthetic training data** for flood, malaria, readiness, and community-report models (`DATA_CATALOG.md`).  
- **DHIS2 ingest is on-demand**, default mock. Live HMIS is not a scheduled national feed on Vercel. Completeness checks are quality flags, not a MoH bulletin.  
- **Live forecast climate/cases are constants** (`_LIVE_SIGNALS`).  
- **No climate lag** in the malaria GBT (model card).  
- **Community classifier blocked** (perfect metrics / leakage).  
- **Flood AUC 0.991 / precision 1.0** on 300 synthetic rows is not evidence of hydrological skill.  
- **Environmental GBT is trained on its own rules** — circular, not independent science.  
- **No clinical or epidemiological validation** artefacts (no protocol, no MoH sign-off file, no holdout against official series).

### Product / architecture

- **No authentication** on APIs; client role is `localStorage`.  
- **No database**; alerts evaporate.  
- **No automated outbound alerts** (SMS, email, radio).  
- **Situation Room, sensors, digital twins** are hardcoded mocks (including bed counts).  
- **Two facility universes:** MoH CSV vs Situation Room list.  
- **Data lake incomplete:** staging/curated empty; no `pipelines/` package.  
- **`DATA_CATALOG.md` stale** (omits live MFL file).  
- **README (before this suite) was inaccurate** (Logistic Regression, `symptoms` field, 3-file tree).  
- **`frontend-react/` is a Vite stub**, not the app.  
- **No automated tests.**  
- **Duplicate router mounts** (maintenance hazard).  
- **Vercel path mismatch** for `/health`, `/predict`, `/ask`.  
- **`GET /api/health` missing** but referenced by `ai-models.js`.  
- **Partner page shows a fake Bearer token.**  
- **Open-Meteo is optional**; UI can look “live” on jitter alone.  
- **Triage is additive symptom points**, not IMCI.  
- **Assistant is keyword matching.**  
- **Hardcoded KPIs** on some HTML pages.  
- **`.gitignore` is minimal** (`__pycache__/`, `*.log`, `.vercel`) — easy to commit secrets later.  
- **pandas not in runtime requirements** while training needs it.  
- **Python version unpinned.**  
- **FastAPI description string claims “AI-powered” and “real-time flood atlas”** — stronger than the implementation.

### Operational

- **No monitoring, tracing, or uptime config.**  
- **CORS `*` + credentials.**  
- **`/api/debug` public.**  
- **Serverless memory** is not a source of truth.

These prevent CHEWS from being **production-ready** or **national-scale**.

---

## Roadmap

### Phase 1 — MVP (what already exists)

- DHIS2 Analytics ingest (mock fixtures + live client), MFL join, curated long/wide tables.  
- Rule-based `/predict`.  
- MoH DHIS2 core facility map with honest missing operational data.  
- View-only forecast/surge shells.  
- Flood atlas + optional Open-Meteo.  
- Experimental joblib models + model cards (including a blocked model).  
- Vercel routing skeleton.  
- This documentation suite.

### Phase 2 — Data integration (needs to be connected)

- Scheduled DHIS2 on durable storage; official climate with quality flags.  
- Official climate (SLMDA / CHIRPS / etc.) with quality flags — **not** only Open-Meteo current precipitation.  
- Operational MFL indicators from a governed source; still **no invention**.  
- CHW report API with authentication and verification workflow (UI labels exist; **backend persistence does not**).  
- Replace `_LIVE_SIGNALS` and Situation Room mocks.  
- Implement or delete the 02/03 data-lake layers.  
- Align malaria district names with the 16-district MFL list.

### Phase 3 — Model validation

- Freeze a training window of **real** weekly malaria.  
- Baseline: seasonal naive / last-year-same-week.  
- Report MAE/RMSE **and** calibration; spatial and temporal CV.  
- Remove leaked features; retrain or **delete** community-flood v1.  
- Independent review of thresholds (epi 3/10/25/50, risk 0.30/0.60).  
- Document that heuristics remain until models beat baselines **on real data**.

### Phase 4 — Pilot

- Closed network, authenticated users, audit logs.  
- 1–2 districts, CHWs + DHMT, paper comparison.  
- Define actions for High (who is paged; what is **not** automatic).  
- Collect false alert / missed event rates.  
- Ethics: symptom endpoints, data processing agreements.

### Phase 5 — Scale

- National DHIS2 + MFL sync jobs, HA database, secret manager.  
- Multi-instance alert bus.  
- Observability, load tests, incident process.  
- MoH hosting or agreed cloud region.  
- Remove debug; pin runtimes; CI; dependency scanning.  
- Legal: Apache-2.0 vs health-data hosting contracts.

---

## Suggested freeze for evaluation day

Show Phase 1 honestly. Label Phase 2–5 as **design**. Do not let Situation Room mock beds or synthetic AUC dominate the narrative.

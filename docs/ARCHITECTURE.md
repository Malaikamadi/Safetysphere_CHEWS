# CHEWS — Climate-Health Intelligence Platform

**Architecture & Design Specification v1.0**
*An AI-powered predictive intelligence layer for governments, NGOs, and humanitarian agencies operating in climate-vulnerable settings.*

---

## 0. Executive Summary

CHEWS (**C**limate-**H**ealth **E**arly **W**arning **S**ystem) is **not another reporting dashboard**. Tools like DHIS2 and Health Information Hubs already visualize what *has* happened. CHEWS is the **predictive intelligence layer that sits next to them** and tells Ministries, NGOs, and frontline workers what is *about* to happen — and what to do about it.

| Today (DHIS2-class systems) | CHEWS adds |
|---|---|
| Historical case counts | 7- and 30-day disease forecasts |
| Death and morbidity trends | Outbreak probability + spread modelling |
| Static facility lists | Predicted facility overload and supply-stress |
| Manual situation reports | AI-generated district priority briefs |
| Reactive alerts | Pre-trigger automated alert escalation |
| Read-only data | Closed-loop community reporting (SMS-first) |

**Design pillars**

1. **Predictive, not descriptive.** Every screen answers "what's next" and "who is most at risk."
2. **Explainable by default.** No prediction ships without drivers, confidence, and feature importance.
3. **Modular ML.** Each model is independently deployable, replaceable, and open-sourceable as a Digital Public Good.
4. **Offline-first, SMS-first, low-bandwidth.** Designed for the last-mile, not the boardroom.
5. **DHIS2-native interoperability.** CHEWS reads from and writes back to DHIS2 — it doesn't replace it.
6. **Geo-scoped RBAC.** Every dataset, model output, and alert is scoped by org × geography × role.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLIENTS                                                                │
│  Web Dashboard · NGO Console · Mobile PWA · USSD/SMS · DHIS2 Plugin     │
└──────────────────────┬──────────────────────────────────────────────────┘
                       │ HTTPS · OAuth2/OIDC · API keys
┌──────────────────────▼──────────────────────────────────────────────────┐
│  API GATEWAY  (FastAPI + Traefik/Nginx)                                 │
│  AuthN/AuthZ · Rate-limit · Audit · Tenant routing                      │
└──────┬───────────────┬────────────────────┬──────────────────┬──────────┘
       │               │                    │                  │
┌──────▼──────┐ ┌──────▼──────┐  ┌──────────▼─────────┐  ┌─────▼──────┐
│ Core API    │ │ ML Inference │  │ Alerting & Comms  │  │ Reporting  │
│ (REST/WS)   │ │ Service      │  │ (SMS, email, push) │  │ (PDF/CSV)  │
└──────┬──────┘ └──────┬──────┘  └──────────┬─────────┘  └─────┬──────┘
       │               │                    │                  │
       └───────┬───────┴────────────────────┴──────────────────┘
               │
       ┌───────▼──────────────────────────────────────────┐
       │  DATA LAYER                                       │
       │  PostgreSQL (OLTP) · PostGIS (geospatial)         │
       │  TimescaleDB (time-series) · S3/MinIO (artifacts) │
       │  Redis (cache/queue) · Vector DB (RAG/assistant)  │
       └───────▲──────────────────────────────────────────┘
               │
       ┌───────┴──────────────────────────────────────────┐
       │  INGESTION (Airflow / Prefect)                    │
       │  DHIS2 · OpenStreetMap · ECMWF/CHIRPS/NASA POWER  │
       │  OpenAQ · WHO · National sentinel surveillance    │
       │  Community reports (SMS, app, kobo)               │
       └───────────────────────────────────────────────────┘
```

**Service inventory (today vs. target):**

| Service | Today (in repo) | Target |
|---|---|---|
| `risk_engine` | rules + sigmoid weighting | + gradient-boosted ensemble |
| `alert_engine` | threshold rules | + change-point detection, geo-clustering |
| `forecast_engine` | linear/seasonal | + Prophet/NeuralProphet + ARIMA hybrid |
| `vulnerability` | composite index | + spatial autocorrelation, equity weighting |
| `triage_assistant` | keyword KB | + RAG over MoH guidelines + Krio NLP |
| *(new)* `ingestion_orchestrator` | — | Airflow DAGs for DHIS2/weather pulls |
| *(new)* `model_registry` | — | MLflow tracking + model card store |
| *(new)* `rbac_service` | — | OIDC + per-org geo scoping |
| *(new)* `comms_service` | — | Twilio/Africa's Talking SMS, FCM push |

---

## 2. Multi-Layer ML Architecture

Five composable models feed a **Final Risk Intelligence Engine**. Each model is independently versioned, evaluated, and deployable as a microservice.

### A. Environmental Risk Model
- **Inputs**: rainfall (mm, 24h/7d/30d), temperature (°C), humidity (%), elevation, soil saturation, NDVI, distance to standing water, flood gauge.
- **Algorithm**: Gradient-boosted regressor (LightGBM) on engineered climate features + sigmoid-normalized rule layer as fallback.
- **Output**: `environmental_risk_score ∈ [0,1]` with per-hazard breakdown (flood, heat, AQ, vector breeding).
- **Repo home**: `backend/models/environmental.py`, `flood_risk.py`, `heat_stress.py`, `air_quality.py`.

### B. Epidemiological Forecasting Model
- **Inputs**: weekly case counts (malaria, cholera, dengue, respiratory), historical seasonality, climate lag features, community-reported fever clusters, mobility proxies.
- **Algorithm**: Hybrid **NeuralProphet (trend + seasonality) + LightGBM (climate residual)**. ARIMA fallback for sparse districts.
- **Outputs**: 7-day & 30-day case forecast with **80% / 95% prediction intervals**, surge probability, onset probability, peak window.
- **Repo home**: `backend/models/epidemiological.py`, `backend/services/forecast_engine.py`.

### C. Vulnerability & Exposure Model
- **Inputs**: population density (WorldPop), U5 population, pregnant population, maternal health indicators (DHS), poverty index, road access, WASH coverage, ITN coverage.
- **Algorithm**: Composite IPCC-style index (hazard × exposure × sensitivity / adaptive capacity), spatially smoothed via **Moran's I** + Getis-Ord Gi\* hot-spot detection.
- **Output**: `vulnerability_score` per admin unit with equity-weighted variants for U5 and maternal.
- **Repo home**: `backend/models/exposure.py`, `backend/services/vulnerability.py`.

### D. Healthcare Readiness Model
- **Inputs**: bed capacity, current admissions, staff-to-patient ratio, medicine stockouts (DHIS2 logistics module), supply-days remaining, distance to referral hospital.
- **Algorithm**: Queuing-theory baseline (M/M/c) + LightGBM on historical surge episodes for predicted overload probability.
- **Outputs**: `facility_stress_probability`, expected surge cases, readiness level (Ready / Partially Ready / At Risk / Critical Gap), gap list, action recommendations.
- **Repo home**: `backend/routers/healthcare.py`, future `backend/models/readiness.py`.

### E. Final Risk Intelligence Engine
Fuses A–D into a single decision-grade score.

```
final_risk = w_env * environmental
           + w_epi * epidemiological
           + w_vul * vulnerability
           + w_hcr * (1 − readiness)
```

Weights are **learned via grid-search calibrated against historical outbreaks** (chiefdom-week resolution). Defaults: `w_env=0.30, w_epi=0.35, w_vul=0.20, w_hcr=0.15`.

**Outputs:**
- `overall_climate_health_risk ∈ [0,1]`
- District/chiefdom prioritization ranking
- Top-3 operational recommendations
- Driver attribution (which model contributed most)
- Confidence interval and data-completeness flag

---

## 3. Forecast Intelligence Engine

| Forecast | Horizon | Output | Confidence model |
|---|---|---|---|
| Malaria surge | 7d / 30d | cases + prediction interval | NeuralProphet PI + bootstrap |
| Cholera onset (post-flood) | 14d | onset probability + cluster | Logistic regression on flood lag features |
| Heatwave maternal risk | 5d | excess obstetric admissions | Heat index + maternal denominator |
| Flood-related disease | 30d | composite (cholera + diarrhea + dermatologic) | Compound-event model |
| Community vulnerability projection | quarterly | admin-unit ranking shift | Trend + climate scenario overlay |

**Explainability is mandatory on every forecast:**

```json
{
  "forecast": { "value": 47, "interval_80": [32, 65], "interval_95": [21, 88] },
  "drivers": [
    { "feature": "rainfall_14d_sum", "contribution": +0.34, "direction": "↑" },
    { "feature": "humidity_7d_avg", "contribution": +0.21, "direction": "↑" },
    { "feature": "itn_coverage", "contribution": -0.12, "direction": "↓" }
  ],
  "model": { "name": "malaria_surge_v0.4", "trained_at": "2026-04-12", "auc": 0.81 },
  "data_completeness": 0.92,
  "narrative": "Risk is climbing because the past 14 days have been unusually wet and warm. ITN coverage in this chiefdom partially offsets the climate signal."
}
```

---

## 4. Explainability Layer

Three explainability surfaces, each rendered in the UI:

1. **Driver attribution** — SHAP values per prediction, surfaced as a horizontal bar chart of top drivers.
2. **Counterfactual cards** — "If rainfall were 20mm lower, projected cases drop ~18%."
3. **Model card** — model name, version, training window, AUC/MAE, fairness checks, last validation date, training data provenance.

Every prediction response includes a `model_card_url` field pointing to a versioned, human-readable model card (see `docs/model_cards/` convention).

---

## 5. Data Model (Core Tables)

PostgreSQL + PostGIS + TimescaleDB. All time-series tables are hypertables.

```sql
-- Tenancy & RBAC
organizations(id, name, type, country, created_at)
users(id, org_id, email, name, locale, phone, created_at)
roles(id, name, permissions JSONB)
user_roles(user_id, role_id, scope JSONB)  -- scope = {country, admin1, admin2, facility_id}
audit_log(id, user_id, action, entity, payload JSONB, ts)

-- Geography
admin_units(id, parent_id, level, name, code, geom GEOGRAPHY)  -- country/district/chiefdom
facilities(id, admin_unit_id, name, type, beds, geom GEOGRAPHY, dhis2_id)

-- Sources
data_sources(id, name, type, endpoint, auth_method, last_sync_at)

-- Climate / environment (TimescaleDB hypertables)
climate_observations(ts, admin_unit_id, var, value, source_id)  -- rainfall, temp, humidity, ndvi
air_quality_obs(ts, station_id, pm25, pm10, no2, o3, geom)
flood_events(id, ts_start, ts_end, admin_unit_id, severity, source)

-- Epidemiology
case_reports(ts, admin_unit_id, disease, cases, deaths, source)  -- DHIS2 or sentinel
community_reports(id, ts, user_id, admin_unit_id, type, payload JSONB, geom)
fever_clusters(id, ts, admin_unit_id, cases, radius_m, confidence)

-- Facility logistics
facility_status(ts, facility_id, admissions, beds_occupied, staff_present, stockouts JSONB)

-- Predictions & alerts
predictions(id, ts, model, version, admin_unit_id, payload JSONB, confidence, drivers JSONB)
alerts(id, ts, type, severity, admin_unit_id, payload JSONB, status, escalated_to, ack_by)

-- ML metadata
models(id, name, version, trained_at, metrics JSONB, training_data_window TSRANGE, card_url)
```

**Why this schema works for funders:** clear separation of *observations* (immutable), *predictions* (versioned + explainable), *alerts* (workflow state). Easy to audit, easy to open-source the schema as a DPG reference.

---

## 6. API Architecture

REST + JSON over HTTPS. Versioned at `/v1/`. WebSocket channel for live alerts. OpenAPI auto-published.

```
GET    /v1/health
GET    /v1/me                                    # current user + scopes

# Geography & facilities
GET    /v1/admin-units?level=district
GET    /v1/admin-units/{id}/summary              # rolled-up risk

# Observations
GET    /v1/climate?admin_unit=...&from=...&to=...
GET    /v1/cases?admin_unit=...&disease=malaria&from=...

# Predictions
POST   /v1/predict/environmental
POST   /v1/predict/epidemiological
POST   /v1/predict/vulnerability
POST   /v1/predict/readiness
POST   /v1/predict/final-risk
GET    /v1/forecasts?admin_unit=...&horizon=7d

# Alerts
GET    /v1/alerts?severity=Warning&admin_unit=...
POST   /v1/alerts/{id}/acknowledge
POST   /v1/alerts/{id}/escalate

# Community reporting
POST   /v1/community-reports
GET    /v1/community-reports/clusters

# Assistant
POST   /v1/assistant/ask           # multilingual RAG

# Reports
POST   /v1/reports/situation-brief # → PDF/CSV job

# Integrations
POST   /v1/integrations/dhis2/sync
GET    /v1/integrations/dhis2/status

# Admin (Super Admin only)
GET    /v1/admin/orgs
POST   /v1/admin/users
GET    /v1/admin/audit
GET    /v1/admin/models
POST   /v1/admin/models/{id}/promote
```

**Streaming**: `WSS /v1/stream/alerts?scope=...` — push alerts and forecast updates in real time to operations rooms.

---

## 7. Backend Architecture

Already mostly in place (`backend/`). Target structure:

```
backend/
├── main.py                   # app bootstrap, CORS, OIDC
├── core/
│   ├── auth.py               # OAuth2/OIDC, JWT, scope check
│   ├── rbac.py               # decorator + scope filters
│   ├── tenancy.py            # org isolation
│   ├── audit.py              # write to audit_log on every mutating call
│   └── settings.py
├── routers/                  # HTTP layer (thin)
│   ├── command_center.py
│   ├── strategic.py          # ← exists
│   ├── early_warning.py      # ← exists
│   ├── healthcare.py         # ← exists
│   ├── point_of_care.py      # ← exists
│   ├── community.py          # NEW — community reports
│   ├── ngo_ops.py            # NEW — sit reps, exports
│   ├── integrations.py       # NEW — DHIS2, weather, SMS
│   └── admin.py              # NEW — RBAC, audit, models
├── services/                 # business logic
│   ├── risk_engine.py        # ← exists (route via models/)
│   ├── alert_engine.py       # ← exists
│   ├── forecast_engine.py    # ← exists
│   ├── vulnerability.py      # ← exists
│   ├── triage_assistant.py   # ← exists
│   ├── escalation.py         # NEW — workflows
│   ├── reporting.py          # NEW — PDF/CSV generation
│   └── comms.py              # NEW — SMS/email/push
├── models/                   # ML models, one file per family
│   ├── environmental.py      # ← exists
│   ├── epidemiological.py    # ← exists
│   ├── exposure.py           # ← exists
│   ├── flood_risk.py         # ← exists
│   ├── heat_stress.py        # ← exists
│   ├── air_quality.py        # ← exists
│   ├── carbon_accounting.py  # ← exists
│   ├── readiness.py          # NEW
│   └── risk_engine.py        # ← exists (fusion layer)
├── ingestion/                # NEW — Airflow/Prefect DAGs
│   ├── dhis2.py
│   ├── chirps_rainfall.py
│   ├── nasa_power.py
│   ├── openaq.py
│   └── community_sms.py
├── db/
│   ├── schema.sql
│   └── migrations/           # Alembic
└── tests/
```

---

## 8. Frontend Architecture

Repo today: vanilla HTML/CSS/JS multi-page app. Target evolution:

**Phase 1 (already done):** Multi-page dark-mode dashboard, unified nav, deep-linkable tabs, global Health Assistant FAB.

**Phase 2:** Migrate to a SPA shell while keeping the multi-page URLs as routes.
- Stack: **Vite + Preact + TypeScript** (~10kb runtime, works on low-end Android) or **SvelteKit** for full SSR.
- State: TanStack Query for server cache, Zustand for UI state.
- Charts: **uPlot** (1.2kb gzipped) for time-series, **MapLibre GL JS** + PMTiles for offline maps.
- i18n: `@formatjs/intl` with English, Krio, French bundles.

**Module-to-screen map:**

| Module | Route | Primary component |
|---|---|---|
| Command Center | `/` | `<GlobalRiskMap/>`, `<KPIStrip/>`, `<AISummaryBrief/>`, `<LiveAlertFeed/>` |
| Situation Room | `/situation` | `<OutbreakTimeline/>`, `<EscalationBoard/>` |
| Strategic Planning | `/strategic` | `<VulnerabilityChoropleth/>`, `<ScenarioSlider/>` |
| Risk Mapping | `/strategic/maps` | `<HazardOverlayMap/>` |
| Data Explorer | `/strategic/data` | `<DatasetCatalog/>`, `<TrendBuilder/>` |
| Resource Optimization | `/strategic/optimize` | `<AllocationSimulator/>` |
| Early Warning | `/early-warning` | `<AssessmentForm/>`, `<AlertFeed/>` |
| Forecast Engine | `/forecast` | `<ForecastChart/>` w/ PI bands, driver bars |
| Alert Network | `/alerts` | `<AlertInbox/>`, `<EscalationRules/>` |
| Sensor Network | `/sensors` | `<SensorMap/>`, `<DeviceHealth/>` |
| Healthcare Readiness | `/healthcare` | `<FacilityStressBoard/>` |
| Facility Readiness | `/healthcare/facilities` | `<FacilityDetail/>` |
| Disease Surveillance | `/healthcare/surveillance` | `<ClusterMap/>` |
| Response Coordination | `/healthcare/response` | `<LogisticsBoard/>` |
| Point-of-Care | `/poc` | `<TriageWizard/>`, `<AssistantChat/>` |
| Community Reporting | `/community` | `<ReportFeed/>`, `<ClusterDetector/>` |
| Offline Access | `/offline` | `<OfflineQueue/>`, `<SMSCodebook/>` |
| AI Models | `/models` | `<ModelCatalog/>`, `<ModelCard/>` |
| Integrations | `/admin/integrations` | DHIS2/OSM/weather connectors |
| Reports | `/admin/reports` | `<ReportBuilder/>` |
| Audit Logs | `/admin/audit` | `<AuditTimeline/>` |

---

## 9. RBAC & Multi-Tenancy

**Model:** `User ↔ Role ↔ Permissions`, with a **scope** object that geographically and organizationally bounds every query.

```json
"scope": {
  "org_id": "uuid",
  "country": "SLE",
  "admin1": ["Western Area"],
  "admin2": ["Freetown"],
  "facility_ids": ["…"]
}
```

The RBAC middleware **injects scope into every DB query** — no service can return data outside the user's scope, even by accident.

### Role matrix

| Role | Dashboards | Read | Write | Admin |
|---|---|---|---|---|
| **Super Admin** | All | All | All | Full (orgs, users, models, integrations, audit) |
| **MoH Admin** | National Command Center, all districts | All within country | National reports, alert escalation, weight overrides | Country-scoped user mgmt |
| **District Health Officer** | District Command Center | District + chiefdom | District alerts, escalate to MoH | Facility user mgmt |
| **NGO / Partner** | Partner Console (humanitarian intel) | Districts shared by MoH | Intervention plans, exports | Org users only |
| **Healthcare Worker** | Facility view + PoC | Facility + assigned chiefdoms | Triage, community reports, facility status | — |
| **Community User** | Personalized alerts + Assistant | Own reports + local alerts | Symptom & hazard reports | — |

### Permission examples

```python
PERMISSIONS = {
  "alerts.read":          ["super_admin","moh_admin","dho","ngo","hcw","community"],
  "alerts.escalate":      ["super_admin","moh_admin","dho"],
  "predictions.run":      ["super_admin","moh_admin","dho","ngo"],
  "models.promote":       ["super_admin"],
  "reports.export":       ["super_admin","moh_admin","dho","ngo"],
  "community.report":     ["hcw","community"],
  "audit.read":           ["super_admin","moh_admin"],
  "integrations.config":  ["super_admin"],
}
```

### Workflow examples

- **DHO → MoH escalation:** District officer marks alert as `escalate`. System notifies all MoH admins for that country, locks alert from re-escalation for 30 min, writes audit row.
- **Community report → cluster detection:** Community user submits fever via SMS. Ingestion service geocodes, runs DBSCAN within 5 km / 7 day window. If ≥3 reports cluster, an `alerts.community_cluster` is opened and auto-routed to the DHO.
- **NGO data sharing:** MoH admin issues a *data share grant* (org_id + admin units + read scope + expiry). Grant is enforced at the query layer and logged in `audit_log`.

---

## 10. Module Specifications (operational details)

### 10.1 Command Center
- **AI-generated brief** at the top: 3 sentences summarizing the next 7 days, written by a constrained LLM over the structured forecast bundle (no free generation — template + slot-filling for reliability).
- **National choropleth** with toggleable layers: composite risk, malaria, cholera, heat, flood.
- **Live alert ticker** (WSS) with severity-colored chips.
- **System status** strip: data freshness per source, model staleness, API latency.

### 10.2 Forecast Intelligence Engine
- Each forecast renders with **PI bands** (80% & 95%), **driver bar chart**, **counterfactual slider**, **model card link**.
- Backtesting view: side-by-side actual vs predicted for the last 12 weeks.

### 10.3 Healthcare Readiness Intelligence
- Facility heatmap of `facility_stress_probability`.
- Per-facility detail: bed utilization curve, supply burndown, predicted overload date, suggested actions ("Pre-position 200 ORS sachets within 48h").

### 10.4 Community Reporting System
- **Channels**: PWA, SMS (Twilio/Africa's Talking), USSD short-code, Kobo Toolbox webhook.
- **Schema** is intentionally minimal: `type` (fever/diarrhea/breeding-site/flood/heat), `count`, optional `geo`, optional `photo_url`.
- **Server-side cluster detection** runs every 15 min (DBSCAN + temporal window).
- **Privacy**: PII is hashed; only aggregate geos leave the cluster service.

### 10.5 AI Health Assistant
- **Architecture**: RAG over a vetted corpus (WHO guidelines, MoH SOPs, IMCI charts, IPC handbooks) + slot-filled answers for triage paths.
- **Languages**: English, Krio, French at launch; Mende and Temne in Phase 3.
- **Safety rails**: cannot diagnose, cannot prescribe; always ends with referral guidance ("Visit nearest facility within 24h if symptoms persist").
- **Offline mode**: a 5MB on-device knowledge pack covers the top 30 questions without network.

### 10.6 NGO & Government Operations Layer
- **Situation Report builder** → PDF/DOCX with template variants (UNICEF, WHO, MoH, ECHO).
- **District comparison analytics** → tabular + radar charts on risk, readiness, vulnerability.
- **Resource allocation intelligence** → optimization over budget × intervention × district, surfaced as a ranked recommendation list with expected impact deltas.
- **Coordination dashboard** → shared activity timeline across orgs (who is doing what, where, when) with deduplication detection.

---

## 11. Alert Escalation System

State machine:

```
draft → open → acknowledged → in_response → resolved
                       │
                       └→ escalated (Tier1 → Tier2 → Tier3)
```

| Tier | Routes to | SLA |
|---|---|---|
| Tier 1 | Local HCWs + DHO | 30 min ack |
| Tier 2 | DHO + MoH desk officer | 2 h response plan |
| Tier 3 | MoH Director + UNICEF/WHO partners + national EOC | immediate broadcast |

**Channels** per tier: dashboard toast, push, SMS, email, WhatsApp Business API. All transitions write to `audit_log`. Escalation is **rule-based, not LLM-decided** (auditable, deterministic).

---

## 12. Integrations

| System | Direction | Method | Notes |
|---|---|---|---|
| **DHIS2** | both | DHIS2 Web API + Tracker | Pull cases, push alerts as DHIS2 events |
| **OpenStreetMap / HOT** | in | Overpass + PMTiles | Roads, facilities, water bodies |
| **CHIRPS / NASA POWER / ECMWF** | in | NetCDF / OpenDAP | Rainfall, temp, humidity grids |
| **OpenAQ** | in | REST | Air quality stations |
| **Africa's Talking / Twilio** | out | REST | SMS alerts and USSD |
| **WhatsApp Business** | out | Cloud API | Operations channels |
| **Kobo Toolbox** | in | Webhook | Field surveys, community reports |
| **FCDO / GLIDE** | in/out | REST | Disaster event correlation |
| **National EOC** | out | webhook / email | Tier 3 broadcasts |

---

## 13. Open-Source & Digital Public Goods Strategy

CHEWS should be registered with the **Digital Public Goods Alliance (DPGA)** and aligned with the 9 DPG indicators. Concretely:

### What to open-source first
1. **Schema + API spec** (`docs/`, `openapi.yaml`) — instant DPG win.
2. **Environmental Risk Model** + **Flood Risk Model** — least PII risk, broad reuse.
3. **Vulnerability Index** — methodologically valuable, no sensitive training data.
4. **Forecast Intelligence Engine** (the framework, not necessarily country-trained weights).
5. **Community Reporting SDK** (PWA + SMS adapters).

### What to gate behind license / data-sharing agreements
- Country-specific trained weights when training data includes patient-level records.
- Tier 3 escalation routing rules with named officials.

### Repository structure (monorepo recommended)

```
chews/
├── apps/
│   ├── backend/                # FastAPI
│   ├── frontend/               # web dashboard
│   ├── mobile/                 # PWA
│   └── sms-gateway/            # USSD + SMS
├── packages/
│   ├── ml-core/                # model interfaces, evaluation
│   ├── ml-environmental/
│   ├── ml-epidemiological/
│   ├── ml-vulnerability/
│   ├── ml-readiness/
│   ├── ml-fusion/
│   └── connectors/             # DHIS2, CHIRPS, OpenAQ, OSM
├── infra/
│   ├── docker/
│   ├── helm/
│   └── terraform/
├── data/
│   ├── samples/                # open synthetic samples for reproducibility
│   └── schemas/
├── docs/                       # this file + model cards + ADRs
└── .github/workflows/
```

### Open datasets strategy
- Publish anonymized chiefdom-week aggregates as a CSV + Parquet dataset on **Zenodo** for citation.
- Publish synthetic training sets that match real distributions for model reproducibility without privacy risk.
- Adopt a **Tiered Data License**: CC-BY-4.0 for aggregates, restricted for facility-level data.

### DHIS2 interoperability
- Ship a **DHIS2 App Hub plugin** so MoH users can view CHEWS forecasts inside DHIS2.
- Publish a CHEWS↔DHIS2 mapping doc (data element codes, organisation unit alignment).

---

## 14. NGO Deployment Workflows

A 5-step "country onboarding" runbook (target: <2 weeks).

1. **Baseline** — pull last 5 years of DHIS2 cases + climate grids; backfill DB.
2. **Calibrate** — grid-search fusion weights against historical outbreaks (auto-generates a calibration report).
3. **Configure RBAC** — load org tree (MoH → districts → facilities → NGOs).
4. **Pilot district** — enable Forecast + Alerts in one district for 2 weeks; tune thresholds.
5. **National rollout** — flip the country-wide switch; activate Tier 3 escalation.

Each step has acceptance criteria and an exit gate; full runbook lives in `docs/runbook/country-onboarding.md`.

---

## 15. UI/UX Direction

Visual reference: Palantir Gotham · WHO EIOS · ECMWF dashboards · USAID FEWS NET.

- **Dark, dense, decision-grade.** Information density is a feature, not a bug — these are operations consoles, not landing pages.
- **Single accent color per severity.** Green (ok), cyan (info), amber (watch), orange (warning), red (emergency). No exceptions.
- **Charts over icons.** Every KPI has an inline sparkline; every prediction has a PI band.
- **One-click drilldown.** Country → district → chiefdom → facility, every screen.
- **Explainability is visible, not hidden.** Driver bars sit next to the number, not behind a tooltip.
- **Mobile-first PWA** for HCWs; **desktop-first** for command centers and NGOs.
- **Accessibility:** WCAG 2.1 AA, full keyboard navigation, screen-reader labels on every chart.

---

## 16. Roadmap

| Phase | Window | Key deliverables |
|---|---|---|
| **0 — Foundations** *(done)* | weeks 0–4 | Multi-page UI, 5 models scaffolded, FAB assistant, deep-linkable tabs |
| **1 — Predictive core** | weeks 4–10 | Forecast engine v1 (NeuralProphet + GBM), explainability layer, model registry (MLflow), DB migration to Postgres+PostGIS+TimescaleDB |
| **2 — Integrations** | weeks 10–16 | DHIS2 connector (read + write), CHIRPS/NASA POWER ingestion, SMS gateway (Africa's Talking) |
| **3 — RBAC + Multi-tenant** | weeks 16–20 | OIDC, geo-scoped permissions, audit log, NGO console |
| **4 — Community layer** | weeks 20–26 | PWA, offline mode, SMS/USSD short-code, cluster detection |
| **5 — Pilot in Sierra Leone** | weeks 26–34 | 1 district pilot, backtesting report, validation against MoH data |
| **6 — DPG submission + scale** | weeks 34–40 | DPGA registration, open-source packages published, second country onboarded |

---

## 17. Security, Privacy, Ethics

- **AuthN**: OIDC (Keycloak self-hosted, or Auth0/Okta managed).
- **AuthZ**: scope-injected RBAC at the query layer.
- **PII**: minimization by design; community reports use device-issued opaque IDs, not phone numbers, in core tables.
- **Encryption**: TLS 1.3 in transit, AES-256 at rest, per-tenant KMS keys.
- **Audit**: every mutating call and every prediction read is written to `audit_log`.
- **Data residency**: deployable in-country (k8s on Sierra Leone Government Cloud or local Hetzner/AWS af-south).
- **Ethics review**: every model carries a fairness statement (district equity, gender-disaggregated outcomes for maternal models).
- **Model governance**: predictions are *decision support*, never *automated decisions*; UI always shows the human override path.

---

## Appendix A — Mapping the existing repo to this spec

The current repo already maps cleanly onto the design above:

| Repo path | Architecture section |
|---|---|
| `backend/main.py` | §1, §6 (API), §7 |
| `backend/models/environmental.py` | §2.A |
| `backend/models/epidemiological.py` | §2.B |
| `backend/models/exposure.py` | §2.C |
| `backend/models/risk_engine.py` | §2.E |
| `backend/models/flood_risk.py`, `heat_stress.py`, `air_quality.py` | §2.A (sub-hazards) |
| `backend/services/forecast_engine.py` | §3 |
| `backend/services/alert_engine.py` | §11 |
| `backend/services/vulnerability.py` | §2.C |
| `backend/services/triage_assistant.py` | §10.5 |
| `frontend/index.html` + nav | §8 (Phase 1 done) |
| `frontend/health-assistant.js` | §10.5 (global FAB) |

The phase 1 surface is in place. Phases 2–6 are the path to a UNICEF Venture Fund–ready system.

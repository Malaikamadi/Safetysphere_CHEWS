# CHEWS API documentation

Base URLs:

- Local Uvicorn: `http://127.0.0.1:8000`  
- Vercel: only **`/api/*`** is routed to FastAPI (`vercel.json`). Root `/health`, `/predict`, `/ask` exist in `main.py` but are **not** rewritten to Python on Vercel.

**Authentication:** None. Every endpoint below is callable without credentials.

**CORS:** `allow_origins=["*"]`, `allow_credentials=True`, all methods and headers (`backend/main.py`).

**Dual mount:** Domain routers are registered at `/<router>` and `/api/<router>`. Examples use the `/api` prefix (what the dashboard calls).

**Validation:** Pydantic v2. Out-of-range bodies typically return **422** with FastAPI’s validation error JSON. Missing facilities return **404**. Other failures may return **500** if uncaught.

---

## System

### GET `/health`

| | |
| --- | --- |
| Purpose | Process liveness and advertised model/router names |
| Auth | None |
| Parameters | None |
| Body | None |

**Example response** (shape from `health_check`):

```json
{
  "status": "ok",
  "service": "CHEWS Climate-Health Intelligence System",
  "version": "4.0.0",
  "models": [
    "environmental", "epidemiological", "exposure", "risk_engine",
    "flood_risk", "heat_stress", "air_quality", "carbon_accounting"
  ],
  "routers": ["/strategic", "/early-warning", "/healthcare", "/poc"]
}
```

Note: `/situation-room` is mounted but **omitted** from this `routers` list.

**Vercel:** this path is **not** under `/api/`. Hosted clients should not assume it works. `frontend/ai-models.js` calls `/api/health`, which is **not defined**.

---

### GET `/api/debug`

| | |
| --- | --- |
| Purpose | Diagnose Vercel/data-path issues |
| Auth | None — **information disclosure** |

Returns Python version, cwd, data directory listing, import errors, MFL init flag and facility count. Points at legacy `mfl_readiness_chews_v1.csv` for `mfl_exists`, which may not match the live `MFL_PATH`.

**Do not expose in production.**

---

## Prediction (root app)

### POST `/predict`

| | |
| --- | --- |
| Purpose | Rule-based composite malaria **risk score** (not an outbreak forecast) |
| Auth | None |

**Body** (`PredictionInput`):

| Field | Type | Constraints | Default |
| ----- | ---- | ----------- | ------- |
| rainfall | float | 0–500 | required |
| temperature | float | −10–55 | required |
| humidity | float | 0–100 | required |
| reported_cases | int | ≥ 0 | required |
| trend | enum | increasing, stable, decreasing | stable |
| vulnerable_population | int | ≥ 0 | 0 |
| exposure_level | enum | low, medium, high | medium |

**Example request**

```http
POST /predict HTTP/1.1
Content-Type: application/json

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

**Example response** (`PredictionOutput`): `final_risk` (0–1), `risk_level` (`Low`/`Medium`/`High`), `breakdown`, `explanation`, `factors[]`, `recommendations[]`.

**Errors:** 422 validation; 500 if `risk_engine` failed to import.

---

### POST `/ask`

| | |
| --- | --- |
| Purpose | Keyword-matched health Q&A (not an LLM) |
| Auth | None |

**Body:** `question` (string, min length 1), optional `risk_score` (0–1).

Matches substrings such as `what is malaria`, `how to prevent`, `symptoms`, `risk score`, `children`, `pregnant`. Otherwise returns a fallback help list.

The dashboard’s assistant uses **`POST /api/poc/ask`**, not this route.

---

## Healthcare (`/api/healthcare`)

### POST `/api/healthcare/forecast`

Seasonal-climatological forecast (`forecast_engine.forecast_disease`).

**Body** (`ForecastInput`): `disease` (default malaria), `current_month` 1–12, `rainfall`, `temperature`, `humidity`, `current_cases`, `previous_cases`, `aqi` 0–500.

Internal/demo; the UI uses **GET live** instead.

---

### GET `/api/healthcare/forecast/live`

| Query | Role |
| ----- | ---- |
| disease | Selects `_LIVE_SIGNALS` key (malaria, cholera, dengue, respiratory) |
| admin | District or national scale via `_ADMIN_CASE_SCALE` |

**Purpose:** View-only dashboard. Climate/cases are **hardcoded constants**, not sensors or DHIS2.

---

### POST `/api/healthcare/anomaly-detect`

Compares PM2.5, PM10, temperature to “expected” values with ratio/difference rules (e.g. PM ratio &gt; 2). **Not** a statistical anomaly model.

**Body** (`AnomalyInput`): `pm25`, `pm10`, `expected_pm25`, `expected_pm10`, `temperature`, `expected_temperature`, `location`.

---

### POST `/api/healthcare/surge-plan`

Rule-based surge notes from cases, beds, staff, supplies, `forecast_surge_pct`.

**Body** (`SurgePlanInput`): `disease`, `current_cases`, `bed_capacity` ≥ 1, `staff_available` ≥ 1, `supply_days`, `forecast_surge_pct` 0–500.

---

### GET `/api/healthcare/surge/live`

View-only surge using live forecast caseload **and MoH MFL facility counts**. Response `note` states beds/staff/supplies are not in the core registry. Query params: disease, admin (same pattern as forecast live).

---

### POST `/api/healthcare/ml/malaria-predict`

Experimental GradientBoostingRegressor (synthetic training).

**Body** (`MalariaPredictInput`): `district`, `rainfall_mm`, `temperature_c`, `humidity_percent`, `water_stagnation_index` 0–1, `mosquito_breeding_sites`, `reported_fever_cases`, `population_density`.

**Response:** `predicted_cases`, `risk_level`, `confidence_factors`, `feature_contributions`.

---

### POST `/api/healthcare/ml/readiness-predict`

Experimental RandomForest on **synthetic** facility rows — not the live MoH list.

**Body** (`ReadinessInput`): `district`, `facility_type`, `beds_available`, `health_workers`, `malaria_medicine_stock` 0–1, `power_availability` 0–1, `water_availability` 0–1, `patient_load`.

---

### POST `/api/healthcare/ml/community-flood`

Experimental classifier. Model card: **BLOCKED** (metrics 1.0 / leakage).

**Body** (`CommunityFloodInput`): `district`, `community`, `standing_water` 0–1, `fever_reports`, `damaged_houses`, `displaced_households`, `water_contamination` 0–1.

---

### GET `/api/healthcare/facilities/summary`

Aggregate counts from the in-memory MFL.

### GET `/api/healthcare/facilities/data-quality`

Coverage / “not assessed” statistics from the loader.

### GET `/api/healthcare/facilities/geojson`

GeoJSON of facilities (larger payload than compact list).

**Query:** optional `district`, `facility_type`.

### GET `/api/healthcare/facilities`

Compact list (id, name, type, district, lat/lon, coord_source). `source`: Ministry of Health DHIS2 core health facilities.

**Query:** `district`, `facility_type`, `search` (name/district/id), `readiness_level` (all optional). Readiness filtering has limited meaning because live MFL rows are not assessed for readiness.

### GET `/api/healthcare/facilities/{facility_id}`

Full facility object or **404**.

### GET `/api/healthcare/facilities/{facility_id}/early-warning`

Hazard context from `facility_mfl.get_facility_early_warning` or **404**.

---

## Strategic (`/api/strategic`)

### POST `/api/strategic/vulnerability-score`

**Body** (`VulnerabilityInput`): facility/building types, flood/heat/AQ/malaria risks 0–1, population counts, water/power sources, staff, emergency plan, road access, referral distance. Defaults exist for all fields.

### POST `/api/strategic/hazard-map`

Runs environmental, air_quality, flood_risk, heat_stress; composite `0.30*malaria_env + 0.25*aq + 0.25*flood + 0.20*heat`.

**Body** (`HazardMapInput`): location name, lat/lng, rainfall, temperature, humidity, pm25, rainfall_intensity, elevation (fields as defined in `strategic.py`).

### POST `/api/strategic/pollution-hotspot`

Air-quality heuristic; `is_hotspot` if AQI &gt; 100.

### GET `/api/strategic/flood-zones`

Static catalogue from reference JSON via flood dashboard/MFL helpers.

### GET `/api/strategic/flood-dashboard`

Per-zone scores; rainfall from Open-Meteo **or** synthetic wobble.

### POST `/api/strategic/flood-forecast`

What-if multipliers (`FloodForecastInput`: `rainfall_intensity_mult`, optional `per_district` overrides).

### GET `/api/strategic/flood-zone/{zone_id}/forecast`

Query `hours` (e.g. 24) for heuristic hourly strip.

### POST `/api/strategic/carbon-footprint`

`carbon_accounting` heuristic.

**Body** (`CarbonInput`): `facility_type`, `floor_area_sqm`, monthly diesel/petrol/LPG/kerosene litres, charcoal/wood kg, `electricity_kwh_month`, `grid_region` (default `sierra_leone`), `has_solar`, `solar_kwh_month`, generator hours/fuel/`generator_consumption_lph`.

### GET `/api/strategic/district-priorities`

`facility_mfl.get_district_priorities()`. Priority score in code is `0.70 * flood_score + 0.30 * (1 - density_score)` where density is facility count capped at 120. It does **not** average missing readiness/bed fields.

---

## Early warning (`/api/early-warning`)

### POST `/api/early-warning/assess`

**Body** (`EarlyWarningInput`): location, temperature, humidity, rainfall_intensity, rainfall_24h, pm25, pm10, wind_speed, uv_index, elevation, soil_saturation.

Runs air_quality, flood_risk, heat_stress; overall threat: Critical/High/Elevated/Guarded/Normal from max score.

### POST `/api/early-warning/trigger`

**Body** (`AlertTriggerInput`): `hazard_type`, `current_value`, `location`, `context`.

Returns `{ "triggered": true, "alert": {...} }` or `{ "triggered": false, "message": "Value below alert thresholds" }`.

### GET `/api/early-warning/alerts`

Query `min_severity` default `Advisory`. Reads **in-memory** `_active_alerts`. Empty after restart unless triggers have run in this process.

---

## Point of care (`/api/poc`)

### POST `/api/poc/triage`

**Body** (`TriageInput`): `symptoms[]`, `patient_group`, `language`, `heat_risk`, `air_quality_risk`, `flood_risk` 0–1.

**Response:** `TriageResult` as dict: urgency Green/Yellow/Orange/Red, category, assessment, actions, referral_needed, climate_context, language.

**This is not a diagnosis.**

### POST `/api/poc/ask`

**Body:** `question`, `language`, optional `risk_score`, `context`. Keyword dictionary (malaria, dengue, cholera, heat, air quality, flood, prevent, symptom, …).

### GET `/api/poc/languages`

Supported language codes from the triage module.

### GET `/api/poc/symptoms`

Known symptom keys (`SYMPTOM_SCORES`).

---

## Situation Room (`/api/situation-room`)

**All data is simulated** (`situation_room.py` module docstring). Do not treat as operational surveillance.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/situation-room` | National dashboard payload |
| GET | `/api/situation-room/map-data` | Map layers |
| GET | `/api/situation-room/timeline/{day_offset}` | Simulated timeline |
| POST | `/api/situation-room/scenario` | What-if over mock state |
| GET | `/api/situation-room/ai-explain/{hazard_type}` | Template “explanation” |
| GET | `/api/situation-room/community-reports` | Mock reports |
| GET | `/api/situation-room/sensors` | Mock sensors |
| GET | `/api/situation-room/digital-twin/{facility_id}` | Mock twin |
| GET | `/api/situation-room/digital-twins` | Mock twin list |
| GET | `/api/situation-room/decision-support` | Mock recommendations |

Hardcoded facilities include named hospitals (e.g. Connaught) with invented bed/staff numbers — **not** the MoH CSV.

---

## Error examples

**422 validation**

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "humidity"],
      "msg": "Input should be less than or equal to 100",
      "input": 140
    }
  ]
}
```

**404 facility**

```json
{ "detail": "Facility CAAuzbg7IFd not found" }
```

(Exact id in the message follows the path parameter.)

---

## Endpoints that do not exist

Do not document or demo: login/token issue, GraphQL. DHIS2 credentials are never returned by `/api/dhis2/*`.

---

## DHIS2 (`/api/dhis2`)

Authentication: none at the CHEWS API layer (same as other routers). HMIS credentials stay on the server.

### GET `/api/dhis2/status`

Public connection flags (`mock_mode`, `auth_method`, indicator IDs). **No username/password/token.**

### POST `/api/dhis2/ingest`

Optional JSON: `period`, `ou_dimension`, `include_supporting`, `persist`.

Pulls Analytics + organisation units (mock or live) into `01_raw` / staging / curated.

### GET `/api/dhis2/malaria`

Query: `district`, `period`, `refresh`. Returns long/wide tables and risk-engine mapping.

### GET `/api/dhis2/facilities`

Query: `unmapped_only`, `refresh`. DHIS2 org units joined to the existing MFL.

### GET `/api/dhis2/health-data`

Combined quality + overlay + hierarchy example.

### GET `/api/dhis2/risk`

Query: `admin`, `rainfall`, `temperature`, `humidity`, `refresh`. Calls **existing** `risk_engine.assess()` with DHIS2 `reported_cases`.

### POST `/api/dhis2/historical/extract`

Explicit YYYYMM window (default 36 months). Facility-level Analytics → validation → district-month → completeness. Does **not** call `malaria_predictor`.

### POST `/api/dhis2/historical/climate`

Open-Meteo **Archive** monthly climate at district centroids. Does **not** change `weather_api.fetch_realtime_weather`.

### POST `/api/dhis2/historical/panel`

Join health + climate, engineer lags, target `malaria_confirmed_next`. Returns **READY FOR MODEL TRAINING** or **NOT READY FOR MODEL TRAINING**.

### GET `/api/dhis2/historical/readiness`

Last verdict (or NOT READY if no panel has been built).

Full detail: [DHIS2_INTEGRATION.md](DHIS2_INTEGRATION.md), [DHIS2_ML_DATA_FOUNDATION.md](DHIS2_ML_DATA_FOUNDATION.md).

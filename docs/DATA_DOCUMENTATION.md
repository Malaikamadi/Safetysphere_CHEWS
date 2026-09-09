# CHEWS data documentation

All statements below are taken from files under `backend/data/`, loaders in `backend/services/facility_mfl.py`, and routers that embed constants. Empty pipeline layers are listed as **not implemented**.

---

## Inventory

| Data element | Source | Current status | Used by | Format |
| ------------ | ------ | -------------- | ------- | ------ |
| MoH DHIS2 core health facilities (id, code, name, level, lon, lat) | Ministry of Health DHIS2 extract committed as CSV | **Implemented** (static file, 1,615 rows) | `facility_mfl.py`, `/healthcare/facilities*`, surge live (counts) | CSV |
| Synthetic MFL readiness (`Facility_N`, beds, workers, readiness_score) | CHEWS generator (`DATA_CATALOG.md`) | **Present, unused by live MFL loader** | Historical sklearn readiness training | CSV |
| Synthetic “DHIS2” malaria rows | CHEWS training data (catalog) | **Prototype / experimental training** | Malaria GBT training; **not** live forecast | CSV |
| Synthetic flood features + `flood_occurred` | CHEWS training data | **Experimental training** | Flood GBT | CSV |
| Synthetic community reports | CHEWS training data (period labelled 2026-07) | **Experimental training** | Community RF (blocked) | CSV |
| Admin hierarchy (16 districts, centroids, typical August rainfall) | Repository reference table | **Implemented** | Flood dashboard, MFL district mapping support | CSV |
| Flood zones (23 communities) | Repository reference JSON | **Implemented** | Flood atlas | JSON |
| Facility type mapping | Reference CSV | **Present** | MFL typing support (see loader) | CSV |
| Sierra Leone district GeoJSON | `frontend/sierra-leone-districts.geojson` | **Implemented** (UI outlines) | Maps | GeoJSON |
| `_LIVE_SIGNALS` climate and cases | Hardcoded in `routers/healthcare.py` | **Prototype** | Forecast/surge live GET | Python dict |
| `_ADMIN_CASE_SCALE` | Hardcoded | **Prototype** | District scaling of live cases | Python dict |
| Situation Room districts, facilities, sensors | Hardcoded in `routers/situation_room.py` | **Prototype / mock** | Situation Room APIs | Python lists |
| Open-Meteo precipitation | api.open-meteo.com | **Partially implemented** | Flood dashboard if fetch succeeds | JSON over HTTPS |
| In-memory alerts | Created at runtime | **Implemented** (ephemeral) | `/early-warning/alerts` | Process RAM |
| Staging Parquet (`02_staging/`) | Documented data lake | **Not implemented** | `.gitkeep` only | — |
| Curated Parquet (`03_curated/`) | Documented data lake | **Not implemented** | `.gitkeep` only | — |
| Population rasters / census | `01_raw/population/` | **Not implemented** | `.gitkeep` | — |
| Admin boundary raw GIS | `01_raw/admin_boundaries/` | **Not implemented** | `.gitkeep` | — |
| Climate NetCDF / official weather archive | `01_raw/climate/` besides flood CSV | **Partial** | Open-Meteo Archive pipeline (`climate_archive.py`); default mock monthly fixture | JSON |
| Live DHIS2 Analytics payloads | Sierra Leone HMIS (`/api/analytics`) or mock fixtures | **Implemented** (ingest; default mock) | `dhis2_service`, `dhis2_pipeline`, `dhis2_historical` | JSON |
| Patient-identifiable EHR | — | **Not present** | — | — |

`DATA_CATALOG.md` (dated 2026-07-31) does **not** list `moh_dhis2_core_health_facilities.csv`. The catalog is therefore **out of date** relative to the live MFL.

---

## Current vs planned sources

### Current (in repo)

- **Environmental / weather (scoring):** User POST bodies, hardcoded live constants, synthetic flood CSV, optional Open-Meteo rainfall.  
- **Malaria variables:** Synthetic case columns for the prototype GBT; live dashboard uses constants unless DHIS2 overlay exists. Historical district-month extract exists but mock coverage is 2 months × 1 facility (**NOT READY** for a new model).  
- **Historical climate:** Open-Meteo Archive monthly pipeline is implemented; default is a 2-month mock fixture. Realtime Open-Meteo 24h precip is flood-only.  
- **Symptoms:** Client-supplied lists to `/poc/triage` (not stored).  
- **Facility data:** Real DHIS2 **identity + coordinates**; synthetic operational columns exist but are not the live registry.  
- **Community reports:** Synthetic CSV + Situation Room mock list.

### Planned (not in code)

- Operational DHIS2 Analytics ingest is implemented (see [DHIS2_INTEGRATION.md](DHIS2_INTEGRATION.md)). Remaining planned work: durable scheduled sync, climate lags, operational MFL indicators without fabricating gaps.  
- Full MFL attributes (beds, staffing, utilities) from an official feed **without fabricating**.  
- National meteorological / hydrological observations and forecasts.  
- Verified CHW electronic reports.  
- Authoritative geospatial layers (flood extents, catchment, roads).  
- Health facility weekly surveillance linked by DHIS2 org unit id.

---

## File-level notes

### `01_raw/master_facility_list/moh_dhis2_core_health_facilities.csv`

- Header: `id,code,name,level,longitude,latitude`.  
- `facility_mfl.py` derives **district from code prefix** (e.g. WAU, WAR, BOO, PLT) and **type from name** (Hospital / CHC / CHP / Clinic / Other).  
- Missing operational indicators are `None` / “Not assessed” / “Data not available” by design (module docstring).

### `01_raw/master_facility_list/mfl_readiness_chews_v1.csv`

- Catalog: 100 rows, synthetic.  
- Used for readiness model training, **not** `MFL_PATH`.

### `01_raw/dhis2/dhis2_malaria_chews_v1.csv`

- Columns include `district,rainfall_mm,temperature_c,humidity_percent,water_stagnation_index,mosquito_breeding_sites,reported_fever_cases,population_density,malaria_cases`.  
- Naming implies DHIS2; catalog says **Synthetic**.

### `01_raw/climate/chews_flood_features_v1.csv`

- Catalog: 300 rows; includes `flood_occurred` label.

### `01_raw/community_reports/community_reports_chews_202607.csv`

- Catalog: 500 rows.  
- Feeds a classifier the model card marks **BLOCKED**.

### `reference/admin_hierarchy.csv`

- 16 districts including Falaba and Karene; rainy season months; `typical_aug_rainfall_mm`.  
- Climatology values are **repository constants**; official meteorological provenance is **not verifiable from the current repository**.

### `reference/flood_zones.json`

- 23 flood-prone communities with static risk factors.  
- Combined with synthesised or Open-Meteo rainfall in `flood_dashboard.py`.

### Legacy `data/raw/` and `data/trained_models/`

- Training script still points at `data/raw/` filenames.  
- Runtime malaria/flood/readiness loaders use `data/trained_models/*.joblib`.  
- Copies also exist under `04_ai/models/` with model cards.

---

## Data pipeline

**Documented** in `backend/data/README.md`: 01_raw → 02_staging → 03_curated → 04_ai.

**Implemented:** File copy + train script + joblib save. **`backend/pipelines/` does not exist.** Staging and curated directories contain only `.gitkeep`.

```
[Implemented] CSV on disk → Python csv/pandas read → optional sklearn fit → joblib
[Implemented] CSV on disk → facility_mfl.initialize() → in-memory list
[Implemented] DHIS2 Analytics JSON → 01_raw (unmodified) → staging rows → curated long/wide → 04_ai DHIS2 features
[Not implemented] Parquet materialisation, cron on Vercel
```

JSON Schemas live under `backend/data/schemas/`. Raw DHIS2 uses `dhis2_analytics.schema.json`. The old `dhis2_weekly_epi.schema.json` filename is a **deprecated alias** of `chews_malaria_features.schema.json` (downstream join, including climate that is **not** from DHIS2).

---

## Preprocessing

- MFL: CSV load, district/type inference, no invented beds.  
- Training script: label encoding, engineered products (`rain_x_stagnation`, etc.). Community features include `damage_displacement_index` and `total_impact` — leakage risk.  
- Environmental GBT: features generated with `numpy.random.RandomState(42)`; labels from the heuristic scorer.  
- Flood dashboard: seasonal factor from month; diurnal sine; optional weather overwrite; saturation still synthesised.

---

## Missing values and data quality

- Live MFL: coordinates present on the committed extract (loader treats this as 100% coord coverage for this file). Operational fields **absent by schema**.  
- Synthetic tables: catalog does not document missingness; generated floats appear complete.  
- Open-Meteo: on failure, flood module **falls back to synthetic rainfall** (silent from a user perspective except logs).  
- Situation Room MFL-like hospitals (Connaught, etc.) are **not** joined to the 1,615-row registry — two parallel “facility” realities.

---

## Storage and retention

- Git-tracked CSVs and joblib.  
- No database retention of predictions or triage.  
- Alert list dies with the process.  
- Weather cache: in-process dict, 3600s TTL.

---

## Privacy and sensitive health information

- Committed MFL is a **public-style facility registry** (names and coordinates of health sites), not patient records.  
- Synthetic malaria/community CSVs do not contain personal identifiers; they still **look like health surveillance** and should not be published as real.  
- Runtime `/poc/triage` accepts symptom lists — **PHI-like**. The API does not persist them, but they traverse an **unauthenticated** HTTP endpoint and may appear in server logs (`print` / hosting logs).  
- No consent, minimisation, or retention policy is implemented in code.

See [SECURITY.md](SECURITY.md).

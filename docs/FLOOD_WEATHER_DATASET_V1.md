# CHEWS Historical Flood Weather Dataset v1

**Status:** weather foundation only. **No flood model was trained. No flood labels were created. Production CHEWS was not modified.**

**Historical weather data does not constitute historical flood-event ground truth.**

This packet sits after `docs/FLOOD_EARLY_WARNING_VALIDATION.md` (verdict **E** — current flood model is not defensible) and `docs/FLOOD_EVENT_DATA_FOUNDATION.md` (verdict **B** — real event source identified, acquisition required). Weather is being built **separately** so a future `chews_flood_event_v0` table can join past-only rainfall without converting rain into synthetic floods.

Outputs:

- `backend/data/04_ai/training_sets/flood_weather_history_v1.csv` (canonical location × day rows)
- `backend/data/04_ai/training_sets/flood_weather_history_v1.json` (same rows; gitignored)
- `backend/data/04_ai/training_sets/flood_weather_history_v1_manifest.json` (gitignored)
- `backend/data/04_ai/diagnostics/flood_weather_history_v1_manifest.json` (reviewable copy)
- `backend/data/04_ai/diagnostics/flood_weather_history_v1_locations.json`
- `backend/services/flood_weather_history.py`
- `backend/training/run_flood_weather_history_v1.py`
- `backend/tests/test_flood_weather_history.py`

Do not treat this file as flood early-warning performance. Do not integrate it into live CHEWS in this phase.

---

## 1. Purpose

Create an isolated, reusable **historical weather/climate foundation** for Sierra Leone locations that can later support:

1. joining real observed flood events (`chews_flood_event_v0`)
2. leakage-safe rainfall features ending **before** event day T
3. eventual flood backtesting

This phase is ingest + validation + temporal feature engineering + geographic validation. It is **not** a training phase.

---

## 2. Why weather is built separately from flood events

Weather is a **predictor candidate**. Flood occurrence is a **target** that must come from independently observed events (NDMA register, validated assessments, or independently validated inundation).

If rainfall above a threshold is stored as `flood_occurred = 1`, later models will rediscover the threshold, not predict floods. CHEWS already has a synthetic-label GBT that cannot be presented as real-world flood prediction. This dataset must not repeat that mistake.

The weather table remains independent of any flood-event target.

---

## 3. Data source

| Item | Value |
| ---- | ----- |
| Provider | Open-Meteo Archive |
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Timezone | `Africa/Abidjan` (Sierra Leone, UTC+0, no DST) |
| Model / dataset | Historical daily reanalysis as served by Open-Meteo Archive (ERA5-family) |
| Authentication | None. No credentials in source. |
| Live CHEWS weather | **Not used.** `weather_api.py` is realtime forecast only. |
| Malaria climate path | **Not used for ingest.** `climate_archive.py` can mock (`CLIMATE_ARCHIVE_MOCK`) and writes monthly district climate. Flood-weather calls the Archive independently. |

Raw per-location API JSON is stored under:

`backend/data/01_raw/climate/open_meteo_archive/flood_weather_v1/`

That directory is **new**. Existing malaria archive files are not overwritten.

---

## 4. Geographic strategy

District centroids are **not** the primary flood-weather geography.

Canonical location table (see diagnostics locations JSON):

| `location_type` | Count | Coordinate quality | Role |
| --------------- | ----- | ------------------ | ---- |
| `flood_zone` | 23 | `catalog_point` from `flood_zones.json` | **Primary** weather grid |
| `district_centroid` | 16 | `admin_centroid_fallback` from `admin_hierarchy.csv` | Documented fallback; malaria monthly comparison only |

Rules:

- Coordinates are validated against a Sierra Leone bounding box. Missing or out-of-box points are flagged, not silently filled.
- The 23 flood-zone communities **do not represent all flood-prone communities in Sierra Leone**. Six districts have no catalog flood-zone point: Bombali, Falaba, Kailahun, Karene, Koinadugu, Kono.
- Facility (MFL) coordinates were inspected and **not** used as the v1 weather grid. They remain available for a later exposure join.
- District centroids are labelled `admin_centroid_fallback`. Do not treat them as catchment pour points or as community flood locations.

---

## 5. Historical period

Open-Meteo Archive returns Sierra Leone daily series from **1940-01-01** in a probe, with some early precipitation nulls. Downloading 1940–2026 for 39 points is unnecessarily large.

**Selected period: 2015-01-01 through 2026-08-31.**

Why this window:

- Covers multiple wet and dry seasons (11+ wet seasons: May–October)
- Overlaps catalog flood-zone narrative years (2015–2024)
- Overlaps the malaria monthly climate extract (~2023-07 to 2026-08) for a consistency check
- Stays well inside Archive availability without a 1940–2014 download

Expected calendar length: 4,261 days per location.

---

## 6. Variables

Requested daily variables:

| Open-Meteo field | Dataset field | Unit |
| ---------------- | ------------- | ---- |
| `precipitation_sum` | `precipitation_mm` | mm/day |
| `rain_sum` | `rain_mm` | mm/day |
| `temperature_2m_mean` | `temperature_mean_c` | °C |
| `temperature_2m_min` | `temperature_min_c` | °C |
| `temperature_2m_max` | `temperature_max_c` | °C |
| `relative_humidity_2m_mean` | `relative_humidity` | % |
| `soil_moisture_0_to_7cm_mean` | `soil_moisture` | m³/m³ |
| `wind_speed_10m_mean` | `wind_speed_10m` | km/h |

Unavailable (probed, not fabricated):

- `soil_moisture_0_to_10cm_mean` — Archive returned unit `undefined`; dropped.

Zero precipitation means **no rain**. Missing precipitation means **no observation**. Missing values are never replaced with zero.

---

## 7. Feature engineering

Grain: **location × calendar day**.

Contemporaneous windows **include day D** (same-day context, not lead-time features):

| Field | Definition |
| ----- | ---------- |
| `rainfall_24h` | precipitation on D |
| `rainfall_72h` | D + D-1 + D-2 |
| `rainfall_7d` | D through D-6 |
| `rainfall_14d` | D through D-13 |

Lead-safe windows **exclude day D** (usable before an event on T = D):

| Field | Definition |
| ----- | ---------- |
| `rainfall_prev_24h` | D-1 |
| `rainfall_prev_72h` | D-1 + D-2 + D-3 |
| `rainfall_prev_7d` | D-1 through D-7 |
| `rainfall_prev_14d` | D-1 through D-14 |

If any day in a window is missing, the window is **null**, not zero-filled. No future days are used.

Also stored: `calendar_month`, `day_of_year`, `wet_season_indicator` (May–October).

---

## 8. Leakage controls

Two rainfall baselines are stored **side by side**:

| Baseline | Definition | Use |
| -------- | ---------- | --- |
| **Descriptive historical baseline** (`rainfall_historical_median_descriptive`) | Median of all daily precipitation for that location × calendar month in this extract, including later years | Description of the climatology in the file. **Not** leakage-safe for backtesting an in-sample event. |
| **Leakage-safe backtest baseline** (`rainfall_historical_median_past_only`, percentile, anomaly) | Same location × calendar month, years **strictly before** the row year; requires ≥3 prior years | Future event backtesting |

Do not use the complete extract to score an earlier date. Do not use `rainfall_24h` / `precipitation_mm` on event day T as a lead-time predictor. Same-day weather is **contemporaneous context only**.

No `flood_occurred` (or alias) field exists.

---

## 9. Data-quality findings

Filled after extract. See the reviewable manifest:

`backend/data/04_ai/diagnostics/flood_weather_history_v1_manifest.json`

Audit includes: row counts vs expected calendar, missing dates, duplicate location-dates, missing precipitation / temperature / humidity / soil moisture, negative precipitation, outliers, gaps by location / year / month, wet-season vs dry-season coverage. Missing weather is preserved as missing.

---

## 10. Comparison with existing CHEWS climate data

The malaria pipeline’s curated file `backend/data/03_curated/climate/climate_district_month_latest.json` is **not overwritten**.

Comparison uses **district-centroid daily rows only**, summed/averaged to month, against malaria `rainfall_mm` and `temperature_c` for overlapping district-months.

Flood-zone catalog coordinates are not expected to match district-centroid monthly totals. Units: both precipitation series are millimetres (daily vs monthly sum).

Exact MAE and overlap counts are in the manifest `malaria_climate_comparison` object.

---

## 11. Limitations

1. Weather is not flood ground truth.
2. 23 catalog communities are not a national flood-zone census.
3. District centroids are fallback geography, not catchments.
4. Archive reanalysis is not a rain-gauge observation and can differ from SLMet/NWRMA stations.
5. `soil_moisture_0_to_10cm_mean` was unavailable and was not invented.
6. Descriptive month medians leak future years if used as a backtest feature; use past-only fields.
7. `chews_flood_event_v0` is still empty — this file cannot be scored against real floods yet.
8. Open-Meteo Archive history is long (from 1940 in a probe) but v1 stops at 2015 to keep the extract practical.

---

## 12. How the dataset will eventually join flood events

```
Flood event (chews_flood_event_v0)
    → event location (mapped, never silent centroid)
    → event_start date T
    → weather location_id
    → weather row on date T
    → past-only features: rainfall_prev_24h / 72h / 7d / 14d
```

For an event on T, future modelling may use only weather available **before T**. Precipitation on T and after T is forbidden for lead-time evaluation. Same-day rainfall may be stored as contemporaneous context.

---

## 13. What this dataset does not prove

- It does **not** prove that CHEWS can predict floods.
- It does **not** identify historical flood days.
- It does **not** validate the existing synthetic flood GBT.
- It does **not** set operational flood thresholds.
- It does **not** replace NDMA / observed event acquisition.

**Historical weather data does not constitute historical flood-event ground truth.**

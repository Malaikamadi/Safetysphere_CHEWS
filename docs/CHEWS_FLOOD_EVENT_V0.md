# CHEWS flood event registry v0

**Status:** observation registry only. **No model was trained. No rainfall-derived flood labels. No operational thresholds. Production CHEWS was not modified. `flood_weather_history_v1` was not modified.**

**Historical weather data does not constitute historical flood-event ground truth.**

This packet is a **data acquisition** expansion of the dated flood-event registry. It does not authorize negative-label construction, rainfall-threshold selection, backtesting, flood model training, or CHEWS integration.

---

## 1. Purpose

Increase `chews_flood_event_v0` with dated, attributed, independently documented flood observations.

Join to `flood_weather_history_v1` only where a catalog flood zone matches, using **past-only** rainfall (`rainfall_prev_24h/72h/7d/14d`). Event-day rain is stored as context and is not a lead-time feature.

This is not a modeling table and not a `flood_occurred=1` panel.

---

## 2. Event-data floor (planning, not labels)

Target before any future backtest:

- ~30+ dated flood events
- ≥3 wet seasons (May–November years with dated events)
- ≥8 districts, **or** Western Area + ≥4 other geographic regimes

Exact community dates are preferred. Missing coordinates stay null. Unmatched places stay unmatched.

---

## 3. Sources searched (this acquisition)

Searched in the required order. Only records with a calendar date **and** a named place or named district were ingested as daily-target events.

| Order | Source | Result in this extract |
| ----- | ------ | ---------------------- |
| 1 | NDMA disaster/incident records | **Register still not acquired** (`ndma_extract.json` is `[]`). Public NDMA assessments used: Bonthe 3–5 Sep 2022; Delken 1 Sep 2023; Wellington/Water Street 28 Aug 2022; Freetown 24 Oct 2024. |
| 2 | SLMet / NWRMA incident lists | No dated flood-incident register found. |
| 3 | IFRC DREF / Emergency Appeals | MDRSL006 (5–6 Sep 2015 Kpahn and Pujehun); MDRSL008 (1–2 Aug 2019 named Freetown communities + Tombo 6 Aug 2019); MDRSL013 (28 Aug 2022, including corroboration beyond the original ONS seven); MDRSL016 (Bumbuna 23 Sep 2024); MDRSL019 (31 Aug–5 Sep 2025, seven named districts, 17 communities unnamed). |
| 4 | ReliefWeb | Used as the public host for IFRC operations, not as a separate event generator. |
| 5 | Copernicus EMS | EMSR222 Regent 14 Aug 2017; Lumley named with UN-SPIDER. No additional Sierra Leone flood activations found. |
| 6 | UN OCHA / UN-SPIDER | Racecourse and Lumley named for 14 Aug 2017. |
| 7 | Government/local reports | NDMA public pages above. |
| 8 | Peer-reviewed / institutional dated datasets | Not used to invent extra rows. Year-only catalog narratives remain historical context. |

**Held out (not daily-target events):** NDMA 27 communities as of 23 Sep 2024 (no per-community day); Kori Chiefdom assessment 16 Aug 2024 (assessment date, not flood date); July 2024 Freetown risk assessment (named places, no flood day); MDRSL006 Freetown/Bonthe/Port Loko expansion (ONS totals as of 5 Oct 2015, no community-day list); 2021 ECOWAS recovery (year only).

News/social/generic “flooding occurred in 2024” statements were not treated as events.

---

## 4. Normalization rules

- One canonical event per `event_date` + normalized location + district.
- Multiple sources of the same flood are merged; all source references are kept; `corroboration_count` is stored; the stronger evidence is retained.
- Coordinates remain null unless the source published them. **No district centroids.**
- District/chiefdom/country grain is never rewritten as a catalog town/zone.
- Absence of a report is not a non-flood.

Required fields on every daily-target row: `event_id`, `event_date`, `event_end_date`, `location_name`, `district`, `latitude`, `longitude`, `source`, `source_url`, `source_type`, `evidence_text`, `confidence`, `catalog_zone_match`.

---

## 5. Weather join

Attempted only for catalog-matched daily events. Lead-safe fields exclude the event day. If weather is missing, fields stay null.

---

## 6. Data-quality findings

| Check | Result |
| ----- | ------ |
| Raw records loaded | 49 (1 Wellington pair merged) |
| Unique dated daily-target events | **43** |
| Held out (no calendar day / assessment date only) | 5 |
| Catalog year-only context | 41 |
| Duplicate groups remaining | 0 |
| Duplicate candidates merged | 1 (Wellington 2022-08-28 NDMA + IFRC) |
| Corroborated events | 5 |
| Source coordinates | **0** (none invented) |
| Matched to catalog flood zones | **8** |
| Unmatched | **35** |
| Complete lead-safe weather (24h/72h/7d/14d) | **8** |
| NDMA register acquired | **false** |
| `flood_occurred` / negatives / rainfall thresholds | **not created** |
| Earliest / latest dated event | 2015-09-05 / 2025-08-31 |

**By year / wet season:** 2015: 2, 2017: 3, 2019: 12, 2022: 14, 2023: 1, 2024: 4, 2025: 7 (7 wet seasons).

**By district (11):** western_area_urban 30, western_area_rural 1, bonthe 3, bo 2, and 1 each in tonkolili, pujehun, kenema, moyamba, kono, falaba, koinadugu.

**By source:** IFRC DREF 34, NDMA assessments 6, Copernicus EMS 2, UN-SPIDER 1.

**Catalog matches with complete past-only weather:** Regent 2017-08-14; Lumley 2017-08-14 and 2022-08-28; Kroo Bay 2019-08-01 and 2022-08-28; Mabela 2019-08-01; Wellington 2022-08-28; Bumbuna 2024-09-23.

---

## 7. Planning floor comparison

| Criterion | Floor | This registry |
| --------- | ----- | ------------- |
| Dated events | ~30+ | **43** |
| Wet seasons | ≥3 | **7** |
| Districts | ≥8 **or** Western Area + ≥4 other regimes | **11 districts**; Western Area + 9 other regimes |

**Event-data floor: reached.**

Catalog-zone matching and complete weather remain thin (**8 / 43**). The NDMA incident register is still missing. That does **not** reopen modeling in this phase.

**Classification: B. EVENT-DATA FLOOR REACHED — STOP BEFORE MODELING**

This phase does **not** proceed to:

- negative-label construction
- rainfall threshold selection
- backtesting
- flood model training
- ML
- operational thresholds
- CHEWS integration

---

## 8. Files

- `backend/data/01_raw/flood_events/public_assessments_v0.json` — original public extract
- `backend/data/01_raw/flood_events/acquired_dated_events_v1.json` — this acquisition
- `backend/data/01_raw/flood_events/ndma_extract.json` — empty NDMA register slot
- `backend/data/04_ai/training_sets/chews_flood_event_v0.csv`
- `backend/data/04_ai/diagnostics/chews_flood_event_v0_audit.json`
- `backend/services/flood_event_registry.py`
- `backend/services/chews_flood_event_v0.py`
- `backend/training/run_flood_event_acquisition.py`

---

## 9. What this does not prove

It does not prove CHEWS can predict floods. It does not identify all historical flood days. It does not replace the NDMA register.

If the event-data floor is not met, the only valid next step is more acquisition.

If the floor is met, this phase still **stops** before negatives, rainfall thresholds, backtesting, ML, operational thresholds, or CHEWS integration.

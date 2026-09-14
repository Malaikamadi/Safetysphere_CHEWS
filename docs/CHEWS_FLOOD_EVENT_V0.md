# CHEWS flood event registry v0

**Status:** observation registry only. **No model was trained. No rainfall-derived flood labels. No operational thresholds. Production CHEWS was not modified. `flood_weather_history_v1` was not modified.**

**Historical weather data does not constitute historical flood-event ground truth.**

**Classification: C. INSUFFICIENT REAL EVENTS FOR BACKTEST**

This packet sits after `docs/FLOOD_EVENT_DATA_FOUNDATION.md` (acquisition design) and `docs/FLOOD_WEATHER_DATASET_V1.md` (weather foundation **B**, 23 flood-zone series complete).

---

## 1. Purpose

Create `chews_flood_event_v0`: a dated, independently documented flood-event registry that can later join `flood_weather_history_v1` on:

`matched_flood_zone_id` + `event_start_date`

using **past-only** rainfall (`rainfall_prev_*`). Same-day rain is contemporaneous context only.

This is an **observation registry**. It is not a modeling table and not a `flood_occurred=1` panel.

---

## 2. Why weather is not the target

Weather is a predictor candidate. Flood occurrence must come from independently observed events (NDMA register, dated assessments, IFRC/ReliefWeb, Copernicus EMS). Rainfall above a threshold is not ground truth.

Silence in this small public subset is **not** a negative label.

---

## 3. Sources

| Role | Source | In this extract |
| ---- | ------ | --------------- |
| Primary (intended) | NDMA disaster **register** | **Not acquired.** Empty loader: `backend/data/01_raw/flood_events/ndma_extract.json` |
| Primary (public pages only) | NDMA field assessments | Delken 1 Sep 2023; Bonthe 3–5 Sep 2022; nationwide Sep 2024 (no per-community day) |
| Independent corroboration | IFRC DREF / ReliefWeb | MDRSL013 (28 Aug 2022 ONS communities); MDRSL016 (Bumbuna 23 Sep 2024) |
| Independent mapping | Copernicus EMS | EMSR222 Regent mudflow, event time 14 Aug 2017 |
| Not community ground truth | EM-DAT | Not ingested |
| Context only | `flood_zones.json` year narratives | 41 year-only rows in a **separate** historical-context table |

The NDMA register still requires partnership. This phase did **not** fabricate a register.

---

## 4. Geographic matching

Priority: source coordinates (none published here) → exact / alias catalog name → unmatched.

**Never** silent district centroid.

Matched to the 23 catalog flood zones:

- `zone:regent` — 2017-08-14
- `zone:bumbuna` — 2024-09-23

Nine dated events remain unmatched (Freetown communities not in the 23-point catalog; Delken; Bonthe district/chiefdoms). Review table is in the audit JSON.

---

## 5. Temporal rules

Daily target requires ISO `event_start_date`. Year-only catalog history does **not** enter the daily table. The 2024 NDMA “27 incidents” note has no per-community calendar day and is **held out**.

---

## 6. Weather join

Join is attempted only for catalog-matched daily events. Lead-safe fields are `rainfall_prev_24h/72h/7d/14d` (exclude event day). Event-day `precipitation_mm` / `rainfall_24h` stored as context.

Result: **2 / 11** daily events have complete past-only windows. Unmatched events do not receive centroid weather.

---

## 7. Data-quality findings

| Check | Result |
| ----- | ------ |
| Records loaded | 12 |
| Daily target events | **11** |
| Unique event ids | 11 |
| Duplicate groups | 0 |
| Exact calendar dates | 11 |
| Year/month-only held out | 1 (NDMA nationwide Sep 2024) |
| Catalog year-only context | 41 |
| Source coordinates | 0 (none invented) |
| Matched to catalog | **2** |
| Unmatched | **9** |
| With corroborating source notes | 2 |
| Reported unverified | 0 |
| Complete weather windows | **2** |
| Missing weather (unmatched or incomplete) | 9 |
| NDMA register acquired | **false** |
| `flood_occurred` / negatives / rainfall thresholds | **not created** |

By source (daily): IFRC DREF 8, NDMA assessment 2, Copernicus EMS 1.  
By year: 2017: 1, 2022: 8, 2023: 1, 2024: 1.  
By district: western_area_urban 8, bonthe 2, tonkolili 1.

---

## 8. Planning criteria (not labels)

Previously documented floors for a **rule** backtest: ≥3 wet seasons, ~30 dated events, ≥8 districts (or Western Area plus ≥4 others).

This extract: **11** dated events, **4** years, **3** districts, **2** catalog-matched events. **Not met.**

---

## 9. Files

- `backend/data/01_raw/flood_events/public_assessments_v0.json` — public records actually read
- `backend/data/01_raw/flood_events/ndma_extract.json` — empty NDMA register slot
- `backend/data/04_ai/training_sets/chews_flood_event_v0.csv`
- `backend/data/04_ai/training_sets/chews_flood_event_v0.json` (gitignored)
- `backend/data/04_ai/diagnostics/chews_flood_event_v0_audit.json`
- `backend/services/chews_flood_event_v0.py`
- `backend/training/run_chews_flood_event_v0.py`
- `backend/tests/test_chews_flood_event_v0.py`

---

## 10. What this does not prove

It does not prove CHEWS can predict floods. It does not identify all historical flood days. It does not replace the NDMA register. It does not authorize a rainfall-rule backtest.

**INSUFFICIENT REAL FLOOD EVENTS FOR BACKTEST.**

Next required step: acquire a dated NDMA (or equivalent) community extract, then reload `ndma_extract.json`. Do not train until that exists.

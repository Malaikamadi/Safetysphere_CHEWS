# Flood-event data foundation

**Status:** specification and acquisition design only. **No model was trained. No events were fabricated. Production flood code was not modified.**

Diagnostics: `backend/data/04_ai/diagnostics/flood_data_foundation.json`  
Schema/validation: `backend/services/flood_data_foundation.py`  
Runner: `backend/training/run_flood_data_foundation.py`

This packet sits **after** `docs/FLOOD_EARLY_WARNING_VALIDATION.md` (verdict **E** — current flood model is not defensible). Existing 96.67% accuracy / 0.991 AUC remains **synthetic-holdout**, not real-world performance.

---

## Recommendation

**B. REAL EVENT DATA SOURCE IDENTIFIED — ACQUISITION REQUIRED**

The National Disaster Management Agency (NDMA) maintains a **disaster register** and publishes dated community assessments. That register is **not in CHEWS** and is **not a public bulk download**. Until a dated extract is acquired (with IFRC/ReliefWeb as independent corroboration), CHEWS still has **zero** observed flood-event rows.

Not selected:

- **A** — the historical dataset does not yet exist in the repo.
- **C** — sources *are* identified; more hunting is not the blocker.
- **D** — the target *is* definable: a dated observed flood at community grain.

**Do not train. Do not integrate. Do not turn rainfall into flood labels.**

---

## 1. Current data inventory

| Asset | Source | Dates | Geography | Grain | Real / synthetic | Target? | Context? |
| ----- | ------ | ----- | --------- | ----- | ---------------- | ------- | -------- |
| `flood_zones.json` (23 points) | Static catalog | Narrative years 2015–2024 | 10/16 districts | Year / point | Compiled places, not a time series | No | **Yes** — exposure |
| Zone `flood_history` | Same file | Year (± month in prose) | Those 23 places | Year | Compiled | No | Qualitative only |
| Open-Meteo Forecast | `weather_api.py` | Live | District **centroids** | Hourly / 24h | Real, with synthetic fallback | No | **Yes** — weather |
| Open-Meteo Archive | `climate_archive.py` | ~202307–202608 on disk; API earlier | Any lat/lng | Daily (CHEWS currently monthly for malaria) | Real | No | **Yes** |
| Malaria monthly climate | expansion file | 201104–202306 | District | Month | Real climate join | No | Too coarse for flash flood |
| Synthetic flood CSV (300) | CHEWS training | None | None | None | **Synthetic** | **No** | No |
| Synthetic community reports | CHEWS 2026-07 | 1–30 Jul 2026 | Invalid pairings | Day (fake) | **Synthetic** | **No** | No |
| MoH DHIS2 core MFL | `moh_dhis2_core_health_facilities.csv` | Snapshot | Facility lat/lng | Point | Real coordinates | No | **Yes** — exposure |
| District table + frontend GeoJSON | `admin_hierarchy.csv`, `sierra-leone-districts.geojson` | Static | 16 districts | Polygon / centroid | Reference | No | **Yes** |
| OCHA COD-AB | HDX (not ingested) | — | Admin 0–4 | Polygon | External | No | Future join |
| River gauges | Absent | — | — | — | — | No | No |
| Inundation extents | Absent | — | — | — | — | No | No |
| Flood-event records | **Absent** | — | — | — | — | — | — |

`01_raw/admin_boundaries/` and `02_staging/admin_boundaries/` are empty placeholders.

---

## 2. Gaps

1. No dated flood-event table.
2. NDMA register not acquired.
3. No gauges, no satellite inundation time series in-repo.
4. No facility-access disruption outcomes.
5. Live weather is centroid-only; zone coordinates unused.
6. Six districts have no flood-zone points (Bombali, Falaba, Kailahun, Karene, Koinadugu, Kono).
7. Synthetic `flood_occurred` and synthetic CHW rows must never enter the canonical table.

---

## 3. Potential real event sources

Documented as **potential**. None were downloaded into CHEWS in this phase. Public pages were used only to confirm that a source exists.

| Source | URL / reference | Years (illustrated) | Geography | Could be ground truth? | Access |
| ------ | --------------- | ------------------- | --------- | ---------------------- | ------ |
| **NDMA disaster register + assessments** | [ndma.gov.sl](https://ndma.gov.sl/); e.g. [2024 nationwide floods](https://ndma.gov.sl/2024/09/24/4259-zsqong/), [Delken 1 Sep 2023](https://ndma.gov.sl/2023/09/15/3818-draunc/), [Bonthe 3–5 Sep 2022](https://ndma.gov.sl/2022/09/20/ndma-responds-to-bonthe-district-flood-victims-assesses-impact-on-livelihoods-and-infrastructure/); Audit Service SL 2025 notes a register with hundreds of incidents from 2021 | 2021+ | Community / chiefdom / district | **Yes — primary, if a dated extract is obtained** | Public posts; **register requires partnership** |
| IFRC DREF / SLRCS on ReliefWeb | [MDRSL016 2024](https://reliefweb.int/report/sierra-leone/sierra-leone-floods-2024-dref-final-report-mdrsl016); MDRSL013 2022 Freetown | At least 2022, 2024 | Named communities | Corroboration of **major** events; too sparse alone | Public |
| EM-DAT | [public.emdat.be](https://public.emdat.be/) | 1900–present | Country (sometimes basin/coords) | Independent **high-impact** check only | Register for non-commercial use |
| DFO / Global Flood Database | [floodobservatory.colorado.edu](https://floodobservatory.colorado.edu/); GFD MODIS 2000–2018 | Large floods | 250 m / polygons | Supporting inundation; misses many flash floods | Research / Earth Engine |
| Copernicus EMS | EMSR222 Regent mudflow 15 Aug 2017 | Activations only | AOI polygons | 2017 landslide/mudflow, not a national series | Public maps |
| NWRMA / SLMet | [nwrma.gov.sl/data](https://nwrma.gov.sl/data/); [slmet.gov.sl](https://slmet.gov.sl/our-services/climate/) | Rainfall cited from 1921 with war gaps | Sparse stations | Weather/stage **context**, not labels | Agency |
| CIDMEWS-SL | [cidmews-sl.solutions](https://www.cidmews-sl.solutions/index.php/early-warning-systems/cidmews) | ~2016–17 layers documented | Western Area hazard polygons cited | Exposure after access review | Geoportal; bulk events not verified |
| HDX COD-AB / CHIRPS | [cod-ab-sle](https://data.humdata.org/dataset/cod-ab-sle); [SLE rainfall](https://data.humdata.org/dataset/sle-rainfall-subnational) | Admin COD; dekadal CHIRPS | Admin polygons | Geometry and rainfall **context** | Public |

**Best potential source:** NDMA disaster register (dated, national, community-level assessments already demonstrated on the public site). IFRC DREF is the best **independent** public corroboration.

---

## 4. Recommended target

**A + C: dated observed flood event, at community grain when the source names a place.**

| Item | Choice |
| ---- | ------ |
| Definition | A flood / flash flood / riverine flood / coastal flood / flood-associated landslide recorded by a named authority at a place on a calendar date |
| Spatial grain | Community / settlement (preferred); district-day only if community unknown, with `mapping_uncertainty=high` |
| Temporal grain | **Calendar day** (`event_start`; `event_end` if known). Year-only catalog history is kept only as incomplete context, not for lead time |
| Lead time | Hours to days **before** `event_start`, using past-only rainfall |
| Required data | NDMA (or equivalent) dated rows; location at least district |
| Not chosen | **B** satellite inundation as primary (misses Freetown flash floods); **D** facility disruption (no outcomes); **F** severity as the detection target (optional observed grade only) |

This is not chosen because it is easy to model. It is chosen because it is what CHEWS would actually need to verify: *did flooding occur here on this day?* Rainfall percentile is context, not the label.

---

## 5. Canonical event schema (`chews_flood_event_v0`)

One row = one dated flood at one place. **Not** a daily panel. Weather is **not** stored as the label.

| Field | Provenance | Notes |
| ----- | ---------- | ----- |
| `event_id` | observed | Required |
| `event_start` | observed | ISO date for lead-time eligibility; year-only allowed but not lead-time eligible |
| `event_end` | observed | Null if unknown |
| `location_name`, `district`, `chiefdom` | observed | At least one of district, name, or coordinates |
| `latitude`, `longitude` | observed | Null if unknown — do not fill with centroid |
| `location_id` | **derived** | Matched flood-zone id, if any |
| `mapping_method`, `mapping_uncertainty`, `geographic_precision` | **derived** | Never silent centroid |
| `event_type` | observed | `flood` / `flash_flood` / `riverine_flood` / `coastal_flood` / `landslide_with_flood` / `unknown` |
| `source`, `source_url`, `reported_by`, `verified`, `verification_date` | observed | Synthetic sources cannot be `verified=true` |
| `source_confidence` | **estimated** | CHEWS judgement of the source, not a flood probability |
| `severity` | **estimated** unless the source grades it | Do not infer from rainfall |
| `affected_population`, `affected_households`, `deaths`, `displacement`, `affected_facilities`, `infrastructure_damage` | observed | **Null if the source is silent. Never 0-from-missing.** |
| `inundation_area_km2` | **estimated** | Only if a satellite product is later joined |
| `label_origin` | observed | Forbidden: `rainfall_threshold`, `synthetic_flood_occurred`, `missing_as_nonflood`, current CHW CSV |
| `notes` | observed | |

Impact fields that cannot realistically be filled stay **out of required**. No invented values. `flood_occurred` from the synthetic CSV is **rejected** on this table.

---

## 6. Weather alignment

`t0` = `event_start` (Africa/Abidjan calendar day).

| Window | Days used | Role |
| ------ | --------- | ---- |
| **t-1** | `t0-1` | Lead-time feature |
| **t-3** | `t0-3` … `t0-1` | Lead-time accumulation |
| **t-7** | `t0-7` … `t0-1` | Lead-time accumulation |
| **t0** | event day only | Contemporaneous **context**, not a forecast feature |
| **t+1 and later** | — | **Forbidden** |

Variables to join later from Open-Meteo Archive (or SLMet/NWRMA if obtained) at **event or zone coordinates**: `precipitation_sum` (required); temperature and humidity optional; percentile/anomaly vs a **past-only** expanding wet-season distribution at the same point — **context, never the event label**.

Fallback to district centroid weather only with `mapping_uncertainty=high`.

---

## 7. Geographic alignment

Priority (stop at the first available, record the method):

1. Event coordinates  
2. Named community matched to `flood_zones.json` (flag unmatched names)  
3. District polygon (frontend GeoJSON now; OCHA COD-AB later, including chiefdom)  
4. **Last resort:** district centroid — **always flagged**, never silent  

Then optionally list MFL facilities within a documented radius **as exposure**, not as proof of flooding.

---

## 8. Minimum data requirements

These are evidence floors, not fitted magic numbers.

**A. Statistical / rule-based backtesting**

- ≥ **3 wet seasons** (a one-year storm does not define a rule).
- ≥ **~30 day-dated** community/zone events. With 30 events, a miss rate is barely interpretable (5 misses ≈ 17%, still a wide interval). Below ~15 dated events you cannot tell a useless rule from noise.
- Geographic diversity: ≥ **8 districts**, or Western Area **plus** ≥4 inland/coastal districts (Freetown flash flood ≠ Bonthe coastal ≠ inland river).
- Silent days are negatives **only** if the same register would have recorded an event. Missing coverage ≠ non-flood.

**B. Controlled shadow validation**

- All of A, plus daily precip at those coordinates, plus a subset corroborated by IFRC/ReliefWeb, still **isolated** from live CHEWS. Weather without events is not a flood shadow (unlike malaria DHIS2 positivity).

**C. Supervised ML**

- A and B done, with a **published rule baseline**.
- ≥ **5 wet seasons**, ≥ **~100** dated events, ≥ **10 districts**, chronological split, documented negatives.
- ML only if it **beats the rule on lead time and missed-event rate**, not accuracy.
- **Not justified now.** Maybe never.

---

## 9. Future baseline (not implemented)

Once real events exist, the first defensible baseline is a **past-only rainfall accumulation / wet-season percentile at the mapped location**, ending at **t-1**, optionally zone-specific. Recurrence (same community, same calendar month in prior years) is **context**, not a detector.

**No millimetre cut is published in this phase.** Fitting a cut on the same events and calling it validation is forbidden. Any later ML must beat this baseline.

---

## 10. Community-report requirements

Current CHEWS community CSV is **not ground truth**.

To become useful later: GPS or a stable community id; ISO timestamp (report time ≠ event time); reporter role/id; verification flag; space-time dedup; explicit confidence; impact fields **not** used as features if they define the label.

Even then, CHW reports are detection/confirmation, not a substitute for the NDMA historical register.

---

## 11. Operational use case (future, not live)

CHEWS would eventually warn about **likely flooding at a known exposed community**, possible **facility-access disruption**, and **who is exposed**.

A warning would need: location + mapping uncertainty; timing (nowcast vs t-1/t-3 rainfall context — not a fake NWP strip); evidence and source; data quality; nearby facilities if the join is valid; **recommended verification** (NDMA / DHMT / CHW).

It would **not** claim a disease outbreak, AI prediction, or 96% accuracy.

---

## 12. What must happen before modeling

1. Written data-sharing path with NDMA for a dated register extract (and licence).  
2. Ingest into `chews_flood_event_v0` with validation (this module). Missing stays null.  
3. Corroborate a subset with ReliefWeb/IFRC DREF.  
4. Join past-only daily precip at event/zone coordinates.  
5. Only then: rule-based backtest (miss rate, FAR, lead time).  
6. ML remains off the table until that baseline exists and loses for a documented reason.

Stopped after this data-foundation phase.

# Flood early warning — validation audit

**Status:** diagnostics only. **No model was trained. Nothing was integrated into live CHEWS.**

Reproducible report: `backend/data/04_ai/diagnostics/flood_validation_report.json`  
Audit module: `backend/services/flood_validation.py`  
Runner: `backend/training/run_flood_validation_audit.py`

Generated: 2026-09-10T15:41:31Z (re-run after attaching the weather inventory). Protected SHA-256 hashes of `flood_risk.py`, `flood_dashboard.py`, `weather_api.py`, `flood_model.joblib`, `flood_risk_v1_20260731.joblib`, and `train_all_models.py` were identical before and after.

This is **not** a flood forecast, **not** an outbreak or disaster declaration, and **not** evidence that the recorded 96.7% accuracy / 0.991 AUC is real-world performance.

---

## Recommendation

**E. CURRENT FLOOD MODEL IS NOT DEFENSIBLE**

Also true, and required before any later rebuild:

- **B.** Independent historical flood-event data are missing.
- **F.** External validation (NDMA / MoS / IFRC / dated disaster lists, not rainfall-as-flood) is required.
- **D.** If a signal is rebuilt after those data exist, start with a disclosed rainfall / flood-zone rule, not another GBT.

**Not selected**

- **A. READY FOR CONTROLLED SHADOW VALIDATION** — unlike malaria positivity, there is no observed flood-event analogue to DHIS2.
- **C. EXISTING MODEL NEEDS REDESIGN** — redesign is premature until dated events exist; redesigning on the same synthetic table would repeat the error.

**ML is not justified.** The live atlas does not call the GBT. The GBT’s 0.991 AUC is a synthetic holdout. Humidity correlates more strongly with the generated label than water level does. A rainfall threshold on the same table is the honest baseline, and any GBT lift is lift on a generator.

---

## 1. Current architecture

Two disconnected paths exist. A third set of screens uses neither.

```
DATA SOURCE → ingestion → mapping → features → model → risk → API → dashboard
```

### Live Flood Atlas (what users actually see)

1. **Weather:** `services/weather_api.py` Open-Meteo Forecast `current.precipitation` + last 24h hourly precip at **district centroids**. 1-hour cache. Timeout 2s.
2. **Fallback:** if Open-Meteo fails, `services/flood_dashboard.py` synthesises intensity and 24h totals from rainy-season climatology (`typical_aug_rainfall_mm`) plus wall-clock jitter.
3. **Other “sensors”:** soil saturation, river stage (% bankfull), and tide stage are **synthesised**. River stage is a function of current 24h rainfall + jitter. Tide is a 12.4-hour sine for a hardcoded coastal district list.
4. **Geography:** `data/reference/flood_zones.json` (23 static communities) loaded by `data/sierra_leone.py`.
5. **Risk:** `models.flood_risk.predict` — weighted heuristic (rainfall 0.30, terrain 0.20, drainage 0.20, proximity 0.15, saturation 0.15), with a 1.25× boost if rain, drainage, and saturation are all high.
6. **API:** `GET /strategic/flood-dashboard`, `POST /strategic/flood-forecast`, `GET /strategic/flood-zone/{id}/forecast` in `routers/strategic.py`.
7. **Also on the heuristic:** `POST /early-warning/assess` (`routers/early_warning.py`) → `alert_engine.evaluate_alert`.
8. **Dashboard:** Flood Atlas / early-warning frontend. `frontend/early-warning.js` additionally ships **hardcoded demo alerts** (e.g. “Severe Flood Surge”, confidence 97%).

The 24-hour “outlook” decays current intensity by 0.85 per hour. It is **not** a numerical weather forecast.

`meta.signals_source` on the snapshot is `synthetic_climatology_anchor`. The module docstring states signals “wobble per-call so the dashboard ticks without a real sensor feed.”

### Trained GBT (not on the live atlas)

1. `data/raw/CHEWS_SierraLeone_Flood_Dataset.csv` — 300 synthetic rows (identical to `01_raw/climate/chews_flood_features_v1.csv`).
2. `training/train_all_models.py` — `GradientBoostingClassifier`, GridSearchCV, **80/20 stratified random split**, `random_state=42`.
3. `data/trained_models/flood_model.joblib` (copy/card at `04_ai/models/flood_risk_v1_20260731.joblib`).
4. `models.flood_risk.predict_ml` exists and is **not called by any router**.

### Other flood-coloured surfaces (not validated)

| Surface | What it actually does |
| ------- | --------------------- |
| `POST /healthcare/ml/community-flood` | Community RF; model card **BLOCKED** for leakage |
| `routers/situation_room.py` | `random.uniform` flood scores |
| `services/facility_mfl.py` district priority | Static zone saturation ≥75% → “High”; 0.70×flood + 0.30×inverse facility density |
| `services/alert_engine.py` | Hardcoded 0.30 / 0.50 / 0.70 / 0.85 on the heuristic score |

---

## 2. Existing flood model

| Item | Value |
| ---- | ----- |
| Algorithm | `GradientBoostingClassifier` |
| Target | `flood_occurred` (binary, synthetic) |
| Rows | 300 (93 positive / 207 negative) |
| Features (11) | `rainfall_mm_24h`, `temperature_c`, `humidity_percent`, `elevation_m`, `water_level_m`, `drainage_encoded`, `soil_saturation`, `community_reports`, `rain_x_saturation`, `rain_x_drainage`, `low_elevation_flag` |
| Preprocessing | drainage `poor/moderate/good` → 0/1/2; interactions on the **same row** |
| Split | random 80/20 stratified — **not chronological** (there is no time column) |
| Card metrics | accuracy **0.9667**, precision **1.0**, recall **0.8947**, F1 **0.9444**, ROC-AUC **0.991** |
| Card status | “Pre-production — pending validation with real data” |
| Top importances (card) | rainfall 0.4367, **humidity 0.3726**, elevation 0.1024; `community_reports` **0.0** |

This audit **reproduced** those holdout numbers on the same synthetic CSV and split (`n_test=60`: TN 41, FP 0, FN 2, TP 17). That is confirmation of the recorded synthetic test, **not** independent real-world validation.

**Unit mismatch:** the CSV stores `soil_saturation` on ~0–1; the live heuristic expects 0–100 percent. The two paths are not the same feature contract.

---

## 3. Available data

| ID | Dataset | Source | Dates | Grain | Real / synthetic | Flood target? |
| -- | ------- | ------ | ----- | ----- | ---------------- | ------------- |
| A | Rainfall | Open-Meteo Forecast (live); Archive API + existing malaria-era JSON; synthetic 24h column | live now; archive files `202307`–`202608`; malaria expansion monthly `201104`–`202306` | hourly live / daily archive / district-month | mix of real reanalysis/forecast and synthetic CSV | **No** |
| B | Temperature | same climate stack + synthetic CSV | same | same | mix | **No** |
| C | Humidity | same | same | same | mix | **No** |
| D | River / water level | **no gauges**; CSV `water_level_m`; live `river_stage_pct_bankfull` from rainfall + jitter | none observed | n/a | synthetic / derived | **No** |
| E | Flood-event observations | **none** | — | — | — | **No** |
| F | Flood zones | `flood_zones.json` | static; narrative history 2015–2024 | 23 points | manually compiled catalog | **No** (exposure, not events) |
| G | Facilities | MoH MFL join | snapshot | facility point, flood join at **district** | real coordinates, static flood overlay | **No** |
| H | Population | integers on zone records | static | community | catalog | exposure only |
| I | Community reports | `community_reports_chews_202607.csv` (1000 rows; catalog still says 500) | 2026-07-01–30 | row | **synthetic** | **No** |
| J | Historical labels | `flood_occurred` on the 300-row table | none | none | **synthetic** | **No** |

**There is no reliable historical flood-event target in this repository.** Rainfall was not converted into a flood event.

---

## 4. Data quality

- Training table: 0 missing labels, 0 duplicate rows, **no date, no district, no coordinates**.
- Completeness of a synthetic table is not evidence of surveillance completeness.
- Missing flood observations, if they existed, would **not** be filled with 0 / non-flood (enforced in the diagnostic helpers and tests).
- Community table: **632 / 1000** rows place Freetown community names (Kissy, Kroo Bay, Susan’s Bay, Regent, …) in inland districts (Tonkolili, Kono, Bo, …).
- Six districts have **no** flood-zone records: Bombali, Falaba, Kailahun, Karene, Koinadugu, Kono. “Data not available” on MFL is a catalog hole, not “no flood.”
- Live soil / river / tide have no observational completeness — they are generated every request.
- Open-Meteo failure is silent to the user except logs; the atlas keeps moving via jitter.

---

## 5. Flood target assessment

| Candidate | What it is | In repo? | Grain | Lead time | Limitation |
| --------- | ---------- | -------- | ----- | --------- | ---------- |
| A. Observed flood event | Dated inundation at a place | **No** | would need community/catchment + day | requires pre-event features | blocker |
| B. Zone inundation | Water on a mapped community | **No** time series | 23 static points | none | catalog ≠ inundation |
| C. Facility-access disruption | Clinic unreachable | **No** | MFL point | none | no closure outcomes |
| D. Rainfall-triggered condition | Rain above a policy gate in an exposed zone | rainfall **partially** | district centroid today | possible if disclosed as rainfall, not “flood” | **not adopted** as a supervised label (circular) |
| E. P(flood in next N days) | The product goal | **No** | undefined | the goal | cannot train/backtest |

**Conclusion:** current data **cannot support supervised flood prediction.**

---

## 6. Temporal alignment

| Feature | Available when, relative to a flood |
| ------- | ----------------------------------- |
| Open-Meteo current/24h precip | during / past 24h of the *request*, not of an event |
| Archive daily precip | could be *before* an event **if dates existed** — not used as a flood model feature today |
| Monthly malaria climate rainfall | too coarse for flash flood; not a flood label |
| `water_level_m`, `soil_saturation`, `community_reports` on the GBT row | **same row as `flood_occurred`** — contemporaneous, not lead-time |
| 24h atlas outlook | invented future, not NWP; must not be treated as t+1 truth |
| Zone `flood_history` | **year** (13/41 narratives mention a calendar month; 0 have a day field) |

Horizons same-day / 1-day / 3-day / 7-day **cannot be evaluated**. Using future rainfall to “predict” a historical flood did not occur in training because training has no timestamps — the failure mode is the opposite: **no time at all**, plus same-row hydrology.

---

## 7. Geographic alignment

| Pair | Method | Flag |
| ---- | ------ | ---- |
| Weather → zone | **District centroid** precip copied to every zone in the district | Zone `lat`/`lng` unused for Open-Meteo |
| Zone → district | `flood_zones.json` `district` id ∈ `admin_hierarchy.csv` | 6 districts have zero zones |
| Facility → flood | name map `western_area_urban` → “Western Urban”, then district saturation | not point-in-polygon; facilities outside mapped districts look unexposed |
| Community reports → zones | overlapping **names**, random **districts** | 632 mismatches; cannot validate zones |
| Chiefdoms | unused | — |
| Coordinates | 23 zone points fall in a Sierra Leone bounding box | catalog, not a survey |

`flood_zones.json` is a **static, manually defined** exposure list with narrative history. That is a legitimate prototype geography. It is not an event dataset.

---

## 8. Leakage audit

| Issue | Finding |
| ----- | ------- |
| Synthetic labels | **Yes** — catalogued as CHEWS training data |
| Random split of time-dependent data | **Yes** — and there is no time index to split correctly |
| Future rainfall | No timestamps, so not a t+1 leak; still invalid |
| Same-row `water_level_m` / saturation / community_reports | **Contemporaneous with the label** |
| Target-derived interactions | `rain_x_saturation`, `rain_x_drainage` from the same row |
| Geographic leakage | No location on training rows; community RF encodes shuffled place names |
| Duplicates | Training file duplicated under `data/raw/` and `01_raw/climate/` (identical SHA) |
| Community RF | `damage_displacement_index` and `total_impact` built from impact fields; perfect 1.0 metrics; **BLOCKED** |
| 0.991 AUC | **Reproduced on synthetic holdout. Not real-world performance.** |

Point-biserial vs `flood_occurred` on the 300-row table:

- humidity **0.52**
- rainfall_24h **0.42**
- elevation **−0.16**
- water_level **−0.09**
- soil **0.08**
- community_reports **0.06**

A flood label that tracks humidity more than water level is a **generator artifact**, not hydrology.

---

## 9. Baseline comparison (synthetic holdout only)

Universe: same 300-row CSV, 240/60 stratified split, `random_state=42`. **Not Sierra Leone floods.**

| Method | Accuracy | Precision | Recall | F1 | ROC-AUC | FAR | Missed-event rate |
| ------ | -------: | --------: | -----: | -: | ------: | --: | ----------------: |
| Rainfall ≥ **125 mm** (cut chosen on **train** among 50/75/100/125/150) | 0.767 | 0.586 | **0.895** | 0.708 | **0.782** (rain as score) | 0.293 | 0.105 |
| Live heuristic `predict`, High gate 0.60 (soil rescaled ×100) | 0.683 | 0.00 | **0.00** | 0.00 | 0.709 (score) | 0.00 | **1.00** |
| Existing GBT `flood_model.joblib` | 0.967 | 1.00 | 0.895 | 0.944 | **0.991** | 0.00 | 0.105 |

The rainfall rule matches the GBT’s **recall** (17/19) with 12 false alarms. The GBT’s extra accuracy is extra **precision on the generator**.

The live heuristic scored **zero** synthetic positives at the High gate. The atlas rule and the training labels are different objects. Connecting them would not create a validated early-warning system.

**125 mm / 24h is not an operational flood threshold.** It is a diagnostic cut on fake labels.

---

## 10. Threshold audit

Every current flood cut inspected is **D. hardcoded/prototype**. None is data-derived or statistically estimated from Sierra Leone events. None is an NMCP/NDMA policy record.

Examples: intensity 7.5 / 15 / 30 / 50 mm/h; 50 / 100 mm in 24h; elevation 5 / 15 m; composite 0.20 / 0.40 / 0.60 / 0.80; alert 0.30 / 0.50 / 0.70 / 0.85; MFL High if mean zone saturation ≥75%; community RF 0.3 / 0.5 / 0.8.

Whether future gates should be rainfall, accumulation, zone-specific, district-specific, or seasonal **cannot be decided** until dated events exist. **No new thresholds were implemented.**

---

## 11. Early-warning assessment

| Metric | Result |
| ------ | ------ |
| When the signal first activates vs a real event | **unknown** |
| Lead time (mean / median) | **not measurable** |
| Warning stays active | not measurable |
| False alarms on real events | not measurable |
| Missed major events | not measurable |

Without dated events, optimizing accuracy on the GBT is the wrong objective. Lead time and missed-event rate cannot be computed.

The atlas “forecast strip” is a decay of the current snapshot. It does not demonstrate 1-day or 3-day skill.

---

## 12. Community-report assessment

- 1000 synthetic rows, 1–30 July 2026 only.
- `reported_flooding` 249 / 751.
- `damaged_houses` and `displaced_households` correlate **0.84** with the label — impact fields, not independent confirmation.
- Training adds `damage_displacement_index` and `total_impact` from those fields → perfect metrics → **BLOCKED**.
- Geographic pairing is not a real CHW network.

**Not** independent validation, **not** near-real-time confirmation, **not** event labels.

---

## 13. Health linkage opportunities (no causal claims)

| Link | Data that exists | Data that does not |
| ---- | ---------------- | ------------------ |
| Facility access | MFL coordinates; some zone notes mention roads/hospitals | dated closures, ambulance diversions |
| Service disruption | none observed | — |
| Disease risk | DHIS2 malaria track (separate, not flood-conditioned) | flood→malaria or flood→cholera outcomes |
| Displacement / exposure | catalog population; synthetic displaced_households | real displacement counts |
| Community health reports | synthetic fever_reports | real CHW flood-health forms |

No causal climate-health claim is made from this audit.

---

## 14. Limitations

1. No dated flood-event ground truth.
2. Live weather is district-centroid, not catchment or zone.
3. Soil, river, and tide on the atlas are fictional.
4. GBT and atlas do not share a pipeline.
5. Humidity-dominated synthetic labels are physically implausible as a flood target.
6. Frontend and Situation Room still display demo/random flood threat.
7. Existing Open-Meteo Archive files are **monthly malaria climate**, not a flood backtest cube. This audit did **not** download a new daily flood dataset.
8. Year-grain catalog history (including the 2017 Regent mudslide narrative) cannot be aligned to daily rainfall.

---

## 15. What would be required before any later shadow

1. An independent event list with **date, place, and definition** (e.g. NDMA / district disaster records), with missing kept as missing.
2. Daily (or better) precip at **zone or catchment** coordinates, past-only relative to each event.
3. A disclosed **rule** (accumulation + exposure) scored for lead time, miss rate, and false alarms — not a new GBT first.
4. Explicit non-use of live CHEWS until that packet exists.

Stopped after this validation audit. **Did not train. Did not integrate. Did not modify production CHEWS.**

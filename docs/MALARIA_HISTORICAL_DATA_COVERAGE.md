# Malaria historical data coverage

**Status:** DHIS2 extraction + quality + coverage only. **No model was trained.**  
**Not modified:** `malaria_model.joblib`, existing GBT, `malaria_forecast_v1`, `malaria_positivity_forecast_v1`, original 535-row panel, dashboard, risk engine, `/api/healthcare/forecast/live`.

This phase does **not** define an anomaly target and does **not** regenerate the frozen forecast experiments.

---

## 1. Verdict

**A. SUFFICIENT FOR FUTURE ANOMALY DESIGN**

That verdict applies only to the **comparable-era** series:

`202106`–`202608` (expansion `202106`–`202306` plus the frozen v1 panel `202307`–`202608`)

It does **not** apply to the full Analytics download `201104`–`202306`. Pre-`202106` values exist under the same indicator UIDs, but the indicator *objects* for confirmed / tests / u5 were created on this DHIS2 instance on **2021-05-06**. Those earlier years are kept in a **separate** expansion file and must not be pooled silently.

**Expanded history now covers 5.25 years of comparable-era district-months (`202106`–`202608`), with 100% of district-calendar-months having at least 3 prior years (as of `202608`).**

Stop here. Another technical design review is required before defining the anomaly target.

---

## 2. What was extracted (and what was not)

| Item | Result |
| ---- | ------ |
| Source | Live DHIS2 `https://sl.dhis2.org/hmis23`, same authenticated connection |
| Period grain | Explicit `YYYYMM` month-by-month (`DHIS2_HISTORICAL_CHUNK_MONTHS=1`). `LAST_5_YEARS` not used |
| Indicators | Unchanged: `malaria_confirmed` (`XHQqFqfUfIf`), `malaria_confirmed_u5` (`tjRoHuika9k`), `malaria_tests` (`mwrOKePWg2r`), `malaria_rdt_positive` (`VWdhdKpLVof`) |
| Geography | District-month, facilities mapped through the current DHIS2 org-unit / MFL hierarchy (16 districts) |
| Missing Analytics | Left missing. Not filled with 0 |
| Original v1 panel | Read only. Still **535** rows |
| Expansion artifact | `backend/data/04_ai/training_sets/malaria_historical_expansion.json` (**2347** rows) |
| Machine report | `backend/data/04_ai/training_sets/malaria_historical_expansion_report.json` |
| Climate | Open-Meteo Archive, same district centroids; not persisted into `climate_district_month_latest.json` |
| Persist into curated DHIS2 latest | **No** (`extract_historical(..., persist=False)`) |

---

## 3. Earliest and latest available months

Month-by-month Analytics probes (HTTP 200):

| Period | Analytics rows | Interpretation |
| ------ | -------------: | -------------- |
| `200701`, `200801`, `200901`, `201001`, `201007`, `201012` | 0 | Empty. Not treated as zero |
| `201101`, `201102`, `201103` | 0 | Empty. Not treated as zero |
| `201104` | 2312 (all four indicators present) | **Earliest month with data** |
| `201105`–`201112` | non-empty | Recovered into the expansion file |
| `201201`–`202306` | non-empty every requested month | Expansion window |
| `202307`–`202608` | v1 panel (not rewritten) | Two empty months already documented: `202604`, `202607` |

**Earliest reliable malaria period available (same four indicators): `201104`.**

**Latest month in the expansion file: `202306`.**  
**Latest month in the frozen v1 panel: `202608`.**

`201104` is the start of *available* Analytics, not the start of the comparable-era series used for the data-bar check.

---

## 4. Coverage of the expansion file (`201104`–`202306`)

This file is a **new** dataset. It does not overwrite `malaria_district_month_panel_latest.json`.

| Quantity | Value |
| -------- | ----: |
| Earliest month | `201104` |
| Latest month | `202306` |
| Months requested | **147** |
| Months observed | **147** |
| Missing months | **none** |
| Districts | **16** |
| Expected district-months (16 × 147) | **2352** |
| Observed admin district-months | **2347** |
| Missing district-months | **5** |

The five missing district-months are genuine empty district cells (not zero-filled):

| Period | Districts with no row |
| ------ | --------------------- |
| `201207` | `western_area_rural`, `western_area_urban` |
| `201210` | `kono` |
| `201212` | `port_loko`, `western_area_rural` |

Indicator coverage on the 2347 expansion rows:

| Field | Non-null rows | Coverage |
| ----- | ------------: | -------: |
| `malaria_confirmed` | 2347 | 100% |
| `malaria_tests` | 2347 | 100% |
| `malaria_confirmed_u5` | 2347 | 100% |
| `malaria_rdt_positive` | 2295 | 97.8% (52 district-months missing RDT) |
| Climate (`rainfall_mm`, `temperature_c`, `humidity_percent`) | 2347 | 100% of observed expansion rows |

RDT gaps are scattered (Bo 2013–2016, Karene 2020–2022, a few others). They are missing cells, not zeros.

---

## 5. Combined span with the frozen v1 panel (read-only)

v1 remains the validated `202307`–`202608` reference (535 rows). It was **not** regenerated.

| Quantity | Expansion only | Expansion + frozen v1 |
| -------- | -------------: | --------------------: |
| Rows | 2347 | 2882 |
| Observed months | 147 | 183 |
| Missing months in requested windows | 0 (`201104`–`202306`) | `202604`, `202607` (v1 window only) |

v1 still has sparse late-2026 district coverage (`202605` 3 districts, `202606` 4, `202608` 1). Those holes are unchanged.

---

## 6. Facility completeness

Same definition as the existing pipeline:

```
facility_completeness = reporting_facilities / expected_facilities
```

`expected_facilities` comes from the **current** Level-5 org-unit / MFL map (constant per district across the whole series). Missing facility cells are not converted to zero cases. District sums only include facilities that reported a value.

### By year (expansion file)

| Year | District-months | Mean completeness | Min | Share ≥ 0.20 | Mean confirmed | Mean tests | Mean positivity |
| ---- | --------------: | ----------------: | --: | -----------: | -------------: | ---------: | --------------: |
| 2011 (Apr–Dec) | 144 | 0.313 | 0.126 | 0.840 | 2938 | 4230 | 0.700 |
| 2012 | 187 | 0.460 | 0.012 | 0.984 | 7587 | 10554 | 0.718 |
| 2013 | 192 | 0.455 | 0.008 | 0.964 | 8349 | 12048 | 0.697 |
| 2014 | 192 | 0.461 | 0.029 | 0.969 | 7079 | 10835 | 0.654 |
| 2015 | 192 | 0.480 | 0.209 | 1.000 | 7578 | 11450 | 0.662 |
| 2016 | 192 | 0.516 | 0.222 | 1.000 | 8968 | 14822 | 0.605 |
| 2017 | 192 | 0.526 | 0.213 | 1.000 | 8607 | 14829 | 0.582 |
| 2018 | 192 | 0.528 | 0.197 | 0.995 | 8824 | 15067 | 0.586 |
| 2019 | 192 | 0.534 | 0.230 | 1.000 | 9570 | 15684 | 0.611 |
| 2020 | 192 | 0.555 | 0.238 | 1.000 | 8721 | 14375 | 0.607 |
| 2021 | 192 | 0.584 | 0.264 | 1.000 | 9796 | 15501 | 0.628 |
| 2022 | 192 | 0.580 | 0.105 | 0.990 | 9088 | 14541 | 0.631 |
| 2023 (Jan–Jun) | 96 | 0.536 | 0.035 | 0.958 | 9120 | 14129 | 0.653 |

Month-level completeness for all 147 expansion months is in `malaria_historical_expansion_report.json` → `month_stats`.

Every month with **mean** completeness < 0.40 is in **2011**. From 2012 onward, monthly mean completeness stays at or above ~0.43.

### By district (expansion file)

| District | n | Mean completeness | Min | Max | Mean reporting facilities | Expected (current MFL) |
| -------- | -: | ----------------: | --: | --: | ------------------------: | ---------------------: |
| western_area_urban | 146 | 0.231 | 0.013 | 0.318 | 55.2 | 239 |
| koinadugu | 147 | 0.360 | 0.083 | 0.594 | 34.6 | 96 |
| falaba | 147 | 0.416 | 0.105 | 0.523 | 35.8 | 86 |
| kailahun | 147 | 0.476 | 0.255 | 0.533 | 78.5 | 165 |
| kono | 146 | 0.475 | 0.012 | 0.591 | 77.8 | 164 |
| bonthe | 147 | 0.478 | 0.008 | 0.686 | 57.9 | 121 |
| bo | 147 | 0.481 | 0.178 | 0.591 | 118.9 | 247 |
| western_area_rural | 145 | 0.503 | 0.078 | 0.612 | 51.8 | 103 |
| bombali | 147 | 0.517 | 0.029 | 0.591 | 70.9 | 137 |
| pujehun | 147 | 0.528 | 0.035 | 0.732 | 75.0 | 142 |
| port_loko | 146 | 0.555 | 0.308 | 0.660 | 86.6 | 156 |
| karene | 147 | 0.571 | 0.176 | 0.681 | 52.0 | 91 |
| tonkolili | 147 | 0.582 | 0.182 | 0.679 | 92.5 | 159 |
| kenema | 147 | 0.624 | 0.222 | 0.714 | 117.9 | 189 |
| kambia | 147 | 0.627 | 0.214 | 0.689 | 64.5 | 103 |
| moyamba | 147 | 0.652 | 0.172 | 0.745 | 94.6 | 145 |

Western Area Urban is structurally low because the current expected-facility count is 239 and reporting stays near ~55. That is the same completeness definition used in v1, not a new mapping.

### Comparable-era completeness (`202106`+ expansion + frozen v1)

| | |
| - | -: |
| District-months | 935 |
| Observed months | 61 of 63 (`202604`, `202607` empty in v1) |
| Mean facility completeness | 0.581 |
| Share with completeness ≥ 0.20 | 98.1% |
| Min completeness | 0.006 (sparse v1 2026 months) |

---

## 7. Climate coverage

Open-Meteo Archive, same 16 district centroids as the v1 panel.

| Series | Climate non-null |
| ------ | ---------------- |
| Expansion `201104`–`202306` | **2347 / 2347** (rainfall, temperature, humidity) |
| Frozen v1 panel | **535 / 535** (unchanged) |

Climate is reported separately from HMIS completeness. No climate values were fabricated. Archive months are historical relative to each `source_period`. One Archive HTTP 429 on Moyamba was retried and succeeded; the 2011 climate slice was fetched separately after the 2012–2023 join already existed.

---

## 8. Data-bar check: prior years per district-calendar-month

Rule: for each district × calendar month (Jan–Dec), count distinct prior years with non-null `malaria_confirmed` before the as-of year (same definition as the earlier assessment).

Universe: **16 × 12 = 192** keys.

### A. All Analytics (expansion + frozen v1), as of `202608`

| n_prior | Keys |
| ------- | ---: |
| 0 | 0 |
| 1 | 0 |
| 2 | 0 |
| 3 | 0 |
| ≥ 4 | **192** |
| Share with n_prior ≥ 3 | **100%** |

This table **overstates** usable history because it counts pre-`202106` years.

### B. Comparable era only (`source_period` ≥ `202106`), as of `202608`

| n_prior | Keys |
| ------- | ---: |
| 0 | 0 |
| 1 | 0 |
| 2 | 0 |
| 3 | 0 |
| ≥ 4 | **192** |
| Share with n_prior ≥ 3 | **100%** |

This is the table that answers the data bar.

As of `202306` (expansion end, comparable era only) the same 192 keys are **not** ready: 176 have n_prior = 1 and 16 have n_prior = 2. The frozen v1 years `202307`–`202608` are what push every district-calendar-month to ≥ 4 prior years. That is why v1 was joined **read-only** for this count and not rewritten.

---

## 9. Reporting quality: is older data usable?

Older data is **progressively less complete**, not a sudden collapse, when completeness is measured against **today’s** facility universe.

| Era | Rows | Mean completeness | Share ≥ 0.20 |
| --- | ---: | ----------------: | -----------: |
| Pre-indicator-created (`201104`–`202105`) | 1947 | 0.49 | ~0.99 after 2012; 2011 only 0.84 |
| Post-created expansion (`202106`–`202306`) | 400 | 0.570 | 0.985 |
| Frozen v1 (`202307`–`202608`) | 535 | 0.589 | 0.978 |

Observed issues:

1. **2011 (Apr–Dec)** is a different reporting scale: mean confirmed ~2.9k vs ~7.6k in 2012, mean completeness 0.313. Treat as a start-up / low-coverage year, not as a peer of 2021–2026.
2. **Completeness trend 2012 → 2021** is gradual (0.46 → 0.58). That is consistent with more of the current facility list reporting over time, not with a single month where districts vanish.
3. **No entire district is missing** after the five 2012 holes. Falaba and Karene appear from `201104` because facilities are mapped through the **current** 16-district MFL. Those districts were created in 2018; pre-2018 “Falaba/Karene” rows are retrospective assignment, not contemporary admin units.
4. **RDT** is the weakest indicator (52 expansion gaps; RDT/confirmed ratio is unstable, including a drop in 2021–2022). Confirmed and tests are populated on every expansion row.
5. **v1 late-2026** remains structurally thin (`202604`/`202607` empty; other 2026 months sparse). That is a current-period quality issue, not an expansion defect.
6. Mean positivity moves slowly (roughly 0.58–0.72) with season, not a step change at May 2021.

**Do not assume 2011–2020 is automatically suitable** for the same district-season baseline as 2021–2026.

---

## 10. Indicator consistency (definition break)

Live `/api/indicators/{id}` metadata on this instance:

| Key | UID | Created | Last updated | Name |
| --- | --- | ------- | ------------ | ---- |
| `malaria_confirmed` | `XHQqFqfUfIf` | **2021-05-06** | 2024-01-24 | Malaria confirmed (RDT/Microscopy) (sum) |
| `malaria_confirmed_u5` | `tjRoHuika9k` | **2021-05-06** | 2024-01-24 | Malaria confirmed (RDT/Microscopy) 0-4 years (sum) |
| `malaria_tests` | `mwrOKePWg2r` | **2021-05-06** | 2024-01-24 | Malaria test done at OPD (sum) |
| `malaria_rdt_positive` | `VWdhdKpLVof` | **2016-05-25** | 2024-01-24 | Malaria RDT positive (Facility/Community) |

All four are Number (factor 1), not annualized. Descriptions match the v1 mapping. No other UIDs were substituted.

**Break documented, not silently combined:**

- Analytics **does** return pre-2021 values under the 2021-created UIDs (and pre-2016 RDT under the 2016-created UID). That can be a migration / object-recreation, not proof that the formula is identical.
- Positivity does **not** jump at `202105`/`202106` (monthly means stay in the 0.59–0.66 seasonal band through 2020–2022).
- u5 / confirmed **declines gradually** (0.69 in 2012 → 0.53 in 2020 → 0.51 in 2021 → 0.46 in 2025). There is no cliff in May 2021, but the age mix is not stationary.
- RDT / confirmed **is** unstable and is **not** treated as a comparable positivity substitute.

**Rule used here:** comparable-era start = `202106` (first full month after confirmed/tests/u5 object creation). Rows before that are stored with `indicator_object_era = pre_indicator_created`. They must not be mixed into a baseline until a formula/lineage review says they are the same indicator.

No evidence in this extract requires stopping the *download*. It does require stopping any claim that 2011–2026 is one definition.

---

## 11. Geographic grain

Unchanged: **district-month**, 16 current admin districts, facility → district via the existing org-unit map.

No population data. No external district layer. Expected-facility denominators are the current MFL counts (same as v1), so completeness is comparable across years only in that operational sense.

---

## 12. Classification detail

| Option | Applies? |
| ------ | -------- |
| **A. Sufficient for future anomaly design** | **Yes — comparable era only** (`202106`–`202608`): ≥4–5 years, 100% of 192 district-calendar-months have n_prior ≥ 4 as of `202608`, completeness similar to the validated v1 panel |
| B. More historical data still required | No, not for the comparable-era bar. Analytics before `201104` is empty for these indicators |
| C. Historical data available but not comparable | **Yes for `201104`–`202105`**. Available, tagged, not pooled |

Overall label for this phase: **A**, with the pre-`202106` series quarantined (C for that stretch).

Downloading more months will not add comparable prior years: `201101`–`201103` and 2010/earlier probes were empty.

---

## 13. What this does *not* authorize

- No anomaly detector
- No threshold classifier
- No new ML model
- No change to the risk engine, dashboard, or live forecast
- No regeneration of `malaria_forecast_v1` or `malaria_positivity_forecast_v1`

The next step, if approved in a design review, is to define a **past-only district-season anomaly** on the comparable-era panel — not to train another regressor.

---

## 14. Protection check

| Artifact | Status |
| -------- | ------ |
| `backend/data/trained_models/malaria_model.joblib` | Unchanged (SHA-256 `08a66c59…c5f7`) |
| Existing GBT / `malaria_predictor.py` | Unchanged |
| `malaria_forecast_v1` model | Unchanged (SHA-256 `bf106536…e95b`) |
| `malaria_positivity_forecast_v1` model | Unchanged (SHA-256 `b94b7d6f…1114`) |
| `malaria_forecast_v1_filtered.json` | Unchanged (504 rows) |
| `malaria_positivity_forecast_v1.json` | Unchanged (504 rows) |
| Original panel `malaria_district_month_panel_latest.json` | Unchanged (**535** rows, SHA-256 `fde4751b…0afb`) |
| Dashboard | Unchanged |
| Risk engine | Unchanged |
| `/api/healthcare/forecast/live` | Unchanged |
| Curated `dhis2_malaria_district_month_latest.json` | Still the v1 window (`202307`–…); expansion used `persist=False` |
| Model trained this phase | **No** |

Stopped after this historical coverage report.

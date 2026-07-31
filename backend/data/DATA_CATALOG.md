# CHEWS Data Catalog

> Auto-generated: 2026-07-31 · Covers all datasets in the CHEWS data lake

---

## 01_raw — Source Files

### DHIS2 Exports
| File | Rows | Columns | Period | Source |
|---|---|---|---|---|
| `dhis2_malaria_chews_v1.csv` | 500 | 9 | Synthetic | CHEWS training data |

**Key columns**: `district`, `rainfall_mm`, `temperature_c`, `humidity_percent`, `malaria_cases`

---

### Master Facility List
| File | Rows | Columns | Period | Source |
|---|---|---|---|---|
| `mfl_readiness_chews_v1.csv` | 100 | 10 | Synthetic | CHEWS training data |

**Key columns**: `facility_name`, `district`, `facility_type`, `beds_available`, `health_workers`, `readiness_score`

---

### Climate
| File | Rows | Columns | Period | Source |
|---|---|---|---|---|
| `chews_flood_features_v1.csv` | 300 | 9 | Synthetic | CHEWS training data |

**Key columns**: `rainfall_mm_24h`, `elevation_m`, `drainage_quality`, `soil_saturation`, `flood_occurred`

---

### Community Reports
| File | Rows | Columns | Period | Source |
|---|---|---|---|---|
| `community_reports_chews_202607.csv` | 500 | 9 | 2026-07 | CHEWS training data |

**Key columns**: `date`, `district`, `community`, `reported_flooding`, `fever_reports`, `damaged_houses`

---

## Reference Tables

| File | Description | Rows | Format |
|---|---|---|---|
| `admin_hierarchy.csv` | All 16 Sierra Leone districts with regions, centroids, and rainfall | 16 | CSV |
| `flood_zones.json` | 23 flood-prone communities with coordinates, history, and risk factors | 23 | JSON |
| `facility_type_mapping.csv` | Maps MFL facility types to CHEWS tier levels | 8 | CSV |

---

## Schemas (Data Contracts)

| Schema | Validates | Required columns |
|---|---|---|
| `dhis2_weekly_epi.schema.json` | DHIS2 malaria surveillance data | district, rainfall_mm, malaria_cases + 6 more |
| `master_facility_list.schema.json` | MFL facility records | facility_name, district, facility_type + 7 more |
| `community_reports.schema.json` | CHW field reports | date, district, community, reported_flooding + 5 more |

---

## 04_ai/models — ML Artifacts

| Model | Type | Task | Key Metric | Status |
|---|---|---|---|---|
| `flood_risk_v1` | GradientBoostingClassifier | Flood prediction | AUC = 0.991 | Pre-production |
| `malaria_predictor_v1` | GradientBoostingRegressor | Case count forecast | R² = 0.618 | Pre-production |
| `healthcare_readiness_v1` | RandomForestRegressor | Readiness scoring | R² = 0.881 | Pre-production |
| `community_reports_v1` | RandomForestClassifier | Flood report triage | F1 = 1.0 ⚠️ | BLOCKED — data leakage |

> ⚠️ **community_reports_v1** has perfect metrics (1.0 across all measures), which strongly
> indicates data leakage. See its model card for details. Do NOT deploy to production.

---

## Data Lineage

```
DHIS2 API ──────────► 01_raw/dhis2/ ──────► 02_staging/dhis2/ ──────► 03_curated/surveillance/
                                                                                │
MFL + Geopoints ───► 01_raw/master_facility_list/ ► 02_staging/facilities/ ► 03_curated/facility_readiness/
                                                                                │
Climate (CHIRPS/ERA5) ► 01_raw/climate/ ────► 02_staging/climate/ ──► 03_curated/climate_health/
                                                                                │
Census / WorldPop ──► 01_raw/population/ ──► 02_staging/population/             │
                                                                                ▼
OCHA CODs ──────────► 01_raw/admin_boundaries/ ► 02_staging/admin_boundaries/ ► 03_curated/geospatial/
                                                                                │
CHW Reports ────────► 01_raw/community_reports/ ► 02_staging/community_reports/ │
                                                                                ▼
                                                              04_ai/features/ ──► training_sets/ ──► models/ ──► predictions/
                                                                                                        │
                                                                                                        ▼
                                                                                                   Live CHEWS API
```

---

## Adding New Data

1. Drop the raw file into the appropriate `01_raw/{domain}/` folder
2. Follow the naming convention: `{source}_{dataset}_{period}.{ext}`
3. If a schema exists in `schemas/`, validate the file against it
4. Create or update the staging pipeline in `backend/pipelines/`
5. Update this catalog with the new dataset entry

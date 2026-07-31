# CHEWS Data Architecture

> **Version**: 1.0 · **Last updated**: 2026-07-31

## Overview

This directory implements a **4-layer data lake** architecture for the Climate Health
Early Warning System (CHEWS). Data flows through clearly separated stages from raw
ingestion to production AI predictions.

```
backend/data/
├── 01_raw/           ← Untouched source files (immutable, append-only)
├── 02_staging/       ← Validated, schema-checked, lightly cleaned (Parquet)
├── 03_curated/       ← Analysis-ready, joined, feature-engineered (Parquet)
├── 04_ai/            ← ML artifacts: features, training sets, models, predictions
├── reference/        ← Static lookup tables (CSV/JSON, git-tracked)
├── schemas/          ← JSON Schema data contracts for each dataset
├── raw/              ← [LEGACY] Original flat CSVs — do not add new files here
└── trained_models/   ← [LEGACY] Original model artifacts — see 04_ai/models/
```

## Layer Rules

| Layer | Mutability | Format | Who reads it |
|---|---|---|---|
| `01_raw/` | **Immutable** — never modify, only append | CSV, GeoJSON, NetCDF | Ingestion scripts only |
| `02_staging/` | Reproducible from raw + pipeline script | Parquet, GeoJSON | Data engineers, QA |
| `03_curated/` | Versioned, derived from staging | Parquet, GeoJSON | API, dashboards, data scientists |
| `04_ai/` | Versioned per training run | Parquet, Joblib, JSON | ML pipeline, prediction service |
| `reference/` | Slowly changing, PR-reviewed | CSV, JSON | All layers |
| `schemas/` | Updated with each new dataset | JSON Schema | Validation scripts |

## File Naming Convention

```
{source}_{dataset}_{period_or_version}.{ext}
```

- All lowercase, underscores only
- No spaces, parentheses, or special characters
- Dates in ISO 8601: `20260731` or `2024W01`
- Versions: `v1`, `v2`, etc.

## Quick Reference

| Data Domain | Raw Location | Key Schema |
|---|---|---|
| DHIS2 exports | `01_raw/dhis2/` | `schemas/dhis2_weekly_epi.schema.json` |
| Master Facility List | `01_raw/master_facility_list/` | `schemas/master_facility_list.schema.json` |
| Climate data | `01_raw/climate/` | — |
| Population | `01_raw/population/` | — |
| Admin boundaries | `01_raw/admin_boundaries/` | — |
| Community reports | `01_raw/community_reports/` | `schemas/community_reports.schema.json` |

## Model Cards

Every model in `04_ai/models/` has a companion `*_model_card.json` documenting:
- Training data source and version
- Feature list and importance
- Evaluation metrics
- Known limitations
- Review status

## Legacy Directories

The `raw/` and `trained_models/` directories contain the original project files.
They are preserved for backward compatibility but **no new files should be added there**.
All new data goes into the `01_raw/` → `04_ai/` pipeline.

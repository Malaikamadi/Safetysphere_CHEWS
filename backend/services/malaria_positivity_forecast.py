"""
Malaria positivity forecast — derived training table only.

Target: confirmed(t+1) / tests(t+1) when tests(t+1) > 0.

Does NOT train a model.
Does NOT modify malaria_forecast_v1_filtered.json.
Does NOT modify the original 535-row panel.
Does NOT overwrite malaria_model.joblib or malaria_forecast_v1 model artifacts.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Optional

from config import dhis2 as cfg
from services.dhis2_pipeline import _write_json
from services.malaria_forecast import (
    COMPLETENESS_MIN,
    calendar_next,
    calendar_prev,
    index_panel,
    load_original_panel,
    original_panel_path,
)

logger = logging.getLogger("chews.malaria_positivity_forecast")

POSITIVITY_DATASET_NAME = "malaria_positivity_forecast_v1.json"
POSITIVITY_REPORT_NAME = "malaria_positivity_forecast_v1_filter_report.json"
TARGET_NAME = "target_malaria_positivity_next_period"
TARGET_DESCRIPTION = "Next-calendar-month malaria positivity: confirmed(t+1) / tests(t+1)."

# Columns allowed in X. None are constructed from month t+1.
FEATURE_COLUMNS: tuple[str, ...] = (
    "malaria_confirmed",
    "lag1_malaria_confirmed",
    "lag2_malaria_confirmed",
    "rolling_3_malaria_confirmed",
    "confirmed_change",
    "confirmed_pct_change",
    "malaria_tests",
    "lag1_malaria_tests",
    "testing_change",
    "testing_pct_change",
    "malaria_positivity",
    "lag1_malaria_positivity",
    "positivity_change",
    "rainfall_mm",
    "lag1_rainfall_mm",
    "lag2_rainfall_mm",
    "three_month_rainfall_accumulation",
    "temperature_c",
    "lag1_temperature_c",
    "humidity_percent",
    "lag1_humidity_percent",
    "calendar_month",
    "district_slug",
)

PROHIBITED_IN_X: tuple[str, ...] = (
    TARGET_NAME,
    "malaria_confirmed_next",
    "target_malaria_confirmed_next_period",
    "target_malaria_confirmed",
    "target_malaria_tests",
    "target_positivity",
    "malaria_tests_next",
    "positivity_next",
    "target_period_climate",
)


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _completeness(row: Optional[dict]) -> Optional[float]:
    if not row:
        return None
    return _float(row.get("facility_completeness"))


def positivity(confirmed: Any, tests: Any) -> Optional[float]:
    """confirmed / tests only when tests > 0. Never fill missing with zero."""
    tests_f = _float(tests)
    confirmed_f = _float(confirmed)
    if tests_f is None or confirmed_f is None:
        return None
    if tests_f <= 0:
        return None
    return confirmed_f / tests_f


def _change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    return current - previous


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / previous


def _period(row: dict) -> Optional[str]:
    return row.get("source_period") or row.get("period")


def calendar_lookup(
    index: dict[tuple[str, str], dict],
    slug: str,
    period: str,
    steps: int,
) -> Optional[dict]:
    key_period = period if steps == 0 else calendar_prev(period, steps)
    return index.get((slug, key_period))


def calendar_field(
    index: dict[tuple[str, str], dict],
    slug: str,
    period: str,
    steps: int,
    field: str,
) -> Optional[float]:
    src = calendar_lookup(index, slug, period, steps)
    if not src:
        return None
    return _float(src.get(field))


def rolling_3_confirmed(index: dict[tuple[str, str], dict], slug: str, period: str) -> Optional[float]:
    values = []
    for steps in (0, 1, 2):
        value = calendar_field(index, slug, period, steps, "malaria_confirmed")
        if value is None:
            return None
        values.append(value)
    return sum(values) / 3.0


def three_month_rainfall(index: dict[tuple[str, str], dict], slug: str, period: str) -> Optional[float]:
    values = []
    for steps in (0, 1, 2):
        value = calendar_field(index, slug, period, steps, "rainfall_mm")
        if value is None:
            return None
        values.append(value)
    return sum(values)


def classify_exclusion(row: dict, index: dict[tuple[str, str], dict]) -> Optional[str]:
    slug = row.get("district_slug")
    period = _period(row)
    if not slug or not period:
        return "missing_identity"
    try:
        target_period = calendar_next(period)
    except ValueError:
        return "invalid_period"
    target = index.get((slug, target_period))
    if target is None:
        return "non_consecutive_or_missing_target"
    feature_c = _completeness(row)
    target_c = _completeness(target)
    if feature_c is None or feature_c < COMPLETENESS_MIN:
        return "low_completeness_feature"
    if target_c is None or target_c < COMPLETENESS_MIN:
        return "low_completeness_target"
    if _float(row.get("malaria_confirmed")) is None:
        return "missing_feature_malaria_confirmed"
    if _float(target.get("malaria_confirmed")) is None:
        return "missing_target_malaria_confirmed"
    target_tests = _float(target.get("malaria_tests"))
    if target_tests is None:
        return "missing_target_malaria_tests"
    if target_tests <= 0:
        return "target_malaria_tests_not_positive"
    return None


def build_training_row(row: dict, index: dict[tuple[str, str], dict]) -> dict:
    period = _period(row)
    slug = row["district_slug"]
    target_period = calendar_next(period)
    target = index[(slug, target_period)]

    confirmed_t = _float(row.get("malaria_confirmed"))
    tests_t = _float(row.get("malaria_tests"))
    lag1_confirmed = calendar_field(index, slug, period, 1, "malaria_confirmed")
    lag2_confirmed = calendar_field(index, slug, period, 2, "malaria_confirmed")
    lag1_tests = calendar_field(index, slug, period, 1, "malaria_tests")
    pos_t = positivity(confirmed_t, tests_t)
    lag1_pos = positivity(
        calendar_field(index, slug, period, 1, "malaria_confirmed"),
        calendar_field(index, slug, period, 1, "malaria_tests"),
    )
    rain_t = calendar_field(index, slug, period, 0, "rainfall_mm")
    rain_l1 = calendar_field(index, slug, period, 1, "rainfall_mm")
    rain_l2 = calendar_field(index, slug, period, 2, "rainfall_mm")

    target_pos = positivity(target.get("malaria_confirmed"), target.get("malaria_tests"))
    if target_pos is None:
        raise ValueError("Internal error: target positivity missing after inclusion filter")

    return {
        "district_slug": slug,
        "district_id": row.get("district_id"),
        "district_name": row.get("district_name"),
        "feature_period": period,
        "target_period": target_period,
        "calendar_month": int(str(period)[4:6]),
        "malaria_confirmed": confirmed_t,
        "lag1_malaria_confirmed": lag1_confirmed,
        "lag2_malaria_confirmed": lag2_confirmed,
        "rolling_3_malaria_confirmed": rolling_3_confirmed(index, slug, period),
        "confirmed_change": _change(confirmed_t, lag1_confirmed),
        "confirmed_pct_change": _pct_change(confirmed_t, lag1_confirmed),
        "malaria_tests": tests_t,
        "lag1_malaria_tests": lag1_tests,
        "testing_change": _change(tests_t, lag1_tests),
        "testing_pct_change": _pct_change(tests_t, lag1_tests),
        "malaria_positivity": pos_t,
        "lag1_malaria_positivity": lag1_pos,
        "positivity_change": _change(pos_t, lag1_pos),
        "rainfall_mm": rain_t,
        "lag1_rainfall_mm": rain_l1,
        "lag2_rainfall_mm": rain_l2,
        "three_month_rainfall_accumulation": three_month_rainfall(index, slug, period),
        "temperature_c": calendar_field(index, slug, period, 0, "temperature_c"),
        "lag1_temperature_c": calendar_field(index, slug, period, 1, "temperature_c"),
        "humidity_percent": calendar_field(index, slug, period, 0, "humidity_percent"),
        "lag1_humidity_percent": calendar_field(index, slug, period, 1, "humidity_percent"),
        "feature_facility_completeness": _completeness(row),
        "target_facility_completeness": _completeness(target),
        "feature_reporting_facilities": row.get("reporting_facilities"),
        "target_reporting_facilities": target.get("reporting_facilities"),
        "expected_facilities": row.get("expected_facilities"),
        TARGET_NAME: target_pos,
        "target_description": TARGET_DESCRIPTION,
        "target_defined_when": "malaria_tests(t+1) > 0",
        "health_source": row.get("health_source"),
        "climate_source": row.get("climate_source"),
        "calendar_consecutive": True,
        "completeness_min": COMPLETENESS_MIN,
    }


def leakage_audit(rows: list[dict]) -> dict:
    """Fail closed if target-period fields appear in the feature contract."""
    feature_set = set(FEATURE_COLUMNS)
    prohibited_hit = sorted(feature_set & set(PROHIBITED_IN_X))
    name_hits = [c for c in FEATURE_COLUMNS if "next" in c.lower() or c.startswith("target_")]
    sample_keys = set(rows[0].keys()) if rows else set()
    stored_prohibited = sorted(k for k in sample_keys if k in {
        "malaria_confirmed_next",
        "malaria_tests_next",
        "positivity_next",
        "target_malaria_confirmed",
        "target_malaria_tests",
        "target_malaria_confirmed_next_period",
    })
    # Target column may exist on the row but must not be in FEATURE_COLUMNS.
    target_in_x = TARGET_NAME in feature_set
    return {
        "feature_columns": list(FEATURE_COLUMNS),
        "target_in_feature_columns": target_in_x,
        "prohibited_names_in_feature_columns": prohibited_hit + name_hits,
        "stored_target_period_counts_on_row": stored_prohibited,
        "passed": (not target_in_x) and (not prohibited_hit) and (not name_hits) and (not stored_prohibited),
    }


def _distribution(values: list[float]) -> dict:
    finite = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not finite:
        return {"n": 0, "minimum": None, "median": None, "mean": None, "maximum": None}
    ordered = sorted(finite)
    n = len(ordered)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "n": n,
        "minimum": ordered[0],
        "median": median,
        "mean": sum(ordered) / n,
        "maximum": ordered[-1],
    }


def _availability(rows: list[dict], fields: tuple[str, ...]) -> dict[str, dict]:
    n = len(rows) or 1
    out = {}
    for field in fields:
        present = sum(1 for r in rows if r.get(field) is not None and r.get(field) != "")
        out[field] = {"non_null": present, "null": len(rows) - present, "fraction": present / n if rows else 0.0}
    return out


def filter_positivity_rows(panel: list[dict]) -> tuple[list[dict], dict]:
    index = index_panel(panel)
    reasons: dict[str, int] = {
        "low_completeness_feature": 0,
        "low_completeness_target": 0,
        "non_consecutive_or_missing_target": 0,
        "missing_identity": 0,
        "invalid_period": 0,
        "missing_feature_malaria_confirmed": 0,
        "missing_target_malaria_confirmed": 0,
        "missing_target_malaria_tests": 0,
        "target_malaria_tests_not_positive": 0,
    }
    kept: list[dict] = []
    out_of_range: list[dict] = []

    for row in panel:
        reason = classify_exclusion(row, index)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        built = build_training_row(row, index)
        target = built[TARGET_NAME]
        if target < 0 or target > 1:
            out_of_range.append({
                "district_slug": built["district_slug"],
                "feature_period": built["feature_period"],
                "target_period": built["target_period"],
                TARGET_NAME: target,
            })
        kept.append(built)

    if out_of_range:
        raise ValueError(
            "STOP: positivity target outside [0, 1] "
            f"({len(out_of_range)} rows). Example: {out_of_range[0]}. Do not clip."
        )

    kept.sort(key=lambda r: (r.get("feature_period") or "", r.get("district_slug") or ""))
    audit = leakage_audit(kept)
    if kept and not audit["passed"]:
        raise ValueError(f"STOP: leakage audit failed: {audit}")

    periods = sorted({r["feature_period"] for r in kept})
    target_periods = sorted({r["target_period"] for r in kept})
    districts = sorted({r["district_slug"] for r in kept})
    report = {
        "original_panel_rows": len(panel),
        "final_training_rows": len(kept),
        "exclusion_reasons": reasons,
        "rows_removed_low_completeness_feature": reasons["low_completeness_feature"],
        "rows_removed_low_completeness_target": reasons["low_completeness_target"],
        "rows_removed_non_consecutive_target": reasons["non_consecutive_or_missing_target"],
        "rows_removed_target_tests_not_positive": reasons["target_malaria_tests_not_positive"],
        "rows_removed_missing_target_tests": reasons["missing_target_malaria_tests"],
        "final_districts": districts,
        "final_district_count": len(districts),
        "final_feature_months": periods,
        "final_feature_month_count": len(periods),
        "final_target_months": target_periods,
        "final_date_range": {
            "feature_start": periods[0] if periods else None,
            "feature_end": periods[-1] if periods else None,
            "target_start": target_periods[0] if target_periods else None,
            "target_end": target_periods[-1] if target_periods else None,
        },
        "completeness_min": COMPLETENESS_MIN,
        "feature_completeness_distribution": _distribution(
            [r["feature_facility_completeness"] for r in kept]
        ),
        "target_completeness_distribution": _distribution(
            [r["target_facility_completeness"] for r in kept]
        ),
        "feature_availability": _availability(kept, FEATURE_COLUMNS),
        "target": TARGET_NAME,
        "target_description": TARGET_DESCRIPTION,
        "target_formula": "malaria_confirmed(t+1) / malaria_tests(t+1) where malaria_tests(t+1) > 0",
        "prediction_horizon": "one calendar month",
        "prediction_cutoff": "end of feature month t",
        "missing_value_policy": "preserve legitimate NaN values",
        "district_encoding": "deferred_train_fold_only",
        "original_panel_unmodified": True,
        "count_filtered_dataset_unmodified": True,
        "imputed_missing_months": False,
        "missing_filled_as_zero": False,
        "existing_gbt_untouched": True,
        "model_trained": False,
        "leakage_audit": audit,
        "positivity_outside_0_1": 0,
    }
    return kept, report


def persist_positivity(rows: list[dict], report: dict, *, directory: Optional[Path] = None) -> dict[str, str]:
    out_dir = directory or cfg.AI_TRAINING_SETS_DIR
    data_path = out_dir / POSITIVITY_DATASET_NAME
    report_path = out_dir / POSITIVITY_REPORT_NAME
    count_filtered = out_dir / "malaria_forecast_v1_filtered.json"
    if data_path.name == "malaria_forecast_v1_filtered.json":
        raise ValueError("Refusing to write positivity table over the count filtered dataset")
    _write_json(data_path, rows)
    _write_json(report_path, report)
    if not count_filtered.exists():
        logger.warning("Count filtered dataset missing at %s (not created here)", count_filtered)
    return {"dataset": str(data_path), "report": str(report_path)}


def build_positivity_training_set(
    *,
    panel_path: Optional[Path] = None,
    persist: bool = True,
) -> dict:
    panel = load_original_panel(panel_path)
    if len(panel) != 535:
        logger.warning("Original panel row count is %s, expected 535", len(panel))
    rows, report = filter_positivity_rows(panel)
    result = {"rows": rows, "report": report, "paths": {}}
    if persist:
        result["paths"] = persist_positivity(
            rows,
            report,
            directory=(panel_path.parent if panel_path else None),
        )
        logger.info(
            "Malaria positivity table: panel=%s kept=%s (no training)",
            len(panel),
            len(rows),
        )
    return result

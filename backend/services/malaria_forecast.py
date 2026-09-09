"""
Malaria forecast v1 — training-quality filter and shared feature contract.

Predicts next-calendar-month confirmed malaria (malaria_confirmed at t+1).

Does NOT train a model.
Does NOT call or overwrite malaria_predictor / malaria_model.joblib.
Does NOT modify the original district-month panel JSON.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Optional

from config import dhis2 as cfg
from services.dhis2_periods import add_months, format_yyyymm, parse_yyyymm
from services.dhis2_pipeline import _write_json

logger = logging.getLogger("chews.malaria_forecast")

ORIGINAL_PANEL_NAME = "malaria_district_month_panel_latest.json"
FILTERED_PANEL_NAME = "malaria_forecast_v1_filtered.json"
FILTER_REPORT_NAME = "malaria_forecast_v1_filter_report.json"

COMPLETENESS_MIN = 0.20
TARGET_NAME = "target_malaria_confirmed_next_period"
TARGET_DESCRIPTION = "Next-calendar-month confirmed malaria count."

# Features known at the end of month t (or when month-t HMIS + Archive climate are in).
# None of these are constructed from month t+1.
CANDIDATE_FEATURES = (
    "malaria_confirmed",
    "lag1_malaria_confirmed",
    "lag2_malaria_confirmed",
    "rolling_3_malaria_confirmed",
    "malaria_tests",
    "malaria_rdt_positive",
    "rdt_positivity",
    "rainfall_mm",
    "temperature_c",
    "humidity_percent",
    "calendar_month",
    "district_slug",
)

PROHIBITED_FEATURES = (
    "water_stagnation_index",
    "mosquito_breeding_sites",
    "reported_fever_cases",
    "population_density",
    "malaria_cases",
    "child_malaria_death",
)


def calendar_next(period: str) -> str:
    year, month = parse_yyyymm(period)
    ny, nm = add_months(year, month, 1)
    return format_yyyymm(ny, nm)


def calendar_prev(period: str, steps: int = 1) -> str:
    year, month = parse_yyyymm(period)
    py, pm = add_months(year, month, -steps)
    return format_yyyymm(py, pm)


def _period(row: dict) -> Optional[str]:
    return row.get("source_period") or row.get("period")


def _completeness(row: Optional[dict]) -> Optional[float]:
    if not row:
        return None
    value = row.get("facility_completeness")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _rdt_positivity(tests: Any, rdt: Any) -> Optional[float]:
    if tests is None or rdt is None:
        return None
    try:
        tests_f = float(tests)
        rdt_f = float(rdt)
    except (TypeError, ValueError):
        return None
    if tests_f == 0:
        return None
    return rdt_f / tests_f


def index_panel(rows: list[dict]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for row in rows:
        slug = row.get("district_slug")
        period = _period(row)
        if slug and period:
            index[(slug, period)] = row
    return index


def classify_exclusion(row: dict, index: dict[tuple[str, str], dict]) -> Optional[str]:
    """
    Return an exclusion reason or None if the row is a valid training pair.

    Uses calendar t+1 from the original panel. Does not invent missing months.
    """
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
    if row.get("malaria_confirmed") is None:
        return "missing_feature_malaria_confirmed"
    if target.get("malaria_confirmed") is None:
        return "missing_target_malaria_confirmed"
    return None


def calendar_lag_confirmed(index: dict[tuple[str, str], dict], slug: str, period: str, steps: int) -> Optional[float]:
    prev = index.get((slug, calendar_prev(period, steps)))
    if not prev:
        return None
    value = prev.get("malaria_confirmed")
    return float(value) if value is not None else None


def rolling_3_confirmed(index: dict[tuple[str, str], dict], slug: str, period: str) -> Optional[float]:
    values = []
    for steps in (0, 1, 2):
        src = index.get((slug, period if steps == 0 else calendar_prev(period, steps)))
        if not src or src.get("malaria_confirmed") is None:
            return None
        values.append(float(src["malaria_confirmed"]))
    return sum(values) / 3.0


def build_training_row(row: dict, index: dict[tuple[str, str], dict]) -> dict:
    """Assemble one training example. Target is calendar t+1 only."""
    period = _period(row)
    slug = row["district_slug"]
    target_period = calendar_next(period)
    target = index[(slug, target_period)]
    tests = row.get("malaria_tests")
    rdt = row.get("malaria_rdt_positive")
    return {
        "district_slug": slug,
        "district_id": row.get("district_id"),
        "district_name": row.get("district_name"),
        "feature_period": period,
        "target_period": target_period,
        "calendar_month": int(str(period)[4:6]),
        "malaria_confirmed": row.get("malaria_confirmed"),
        "lag1_malaria_confirmed": calendar_lag_confirmed(index, slug, period, 1),
        "lag2_malaria_confirmed": calendar_lag_confirmed(index, slug, period, 2),
        "rolling_3_malaria_confirmed": rolling_3_confirmed(index, slug, period),
        "malaria_tests": tests,
        "malaria_rdt_positive": rdt,
        "rdt_positivity": _rdt_positivity(tests, rdt),
        "rainfall_mm": row.get("rainfall_mm"),
        "temperature_c": row.get("temperature_c"),
        "humidity_percent": row.get("humidity_percent"),
        "feature_facility_completeness": _completeness(row),
        "target_facility_completeness": _completeness(target),
        "feature_reporting_facilities": row.get("reporting_facilities"),
        "target_reporting_facilities": target.get("reporting_facilities"),
        "expected_facilities": row.get("expected_facilities"),
        TARGET_NAME: target.get("malaria_confirmed"),
        "target_description": TARGET_DESCRIPTION,
        "health_source": row.get("health_source"),
        "climate_source": row.get("climate_source"),
        "calendar_consecutive": True,
        "completeness_min": COMPLETENESS_MIN,
    }


def filter_training_rows(panel: list[dict]) -> tuple[list[dict], dict]:
    """
    Derive a training table from the complete panel without mutating it.

    Exclusion reasons are counted; missing months stay missing.
    """
    index = index_panel(panel)
    reasons: dict[str, int] = {
        "low_completeness_feature": 0,
        "low_completeness_target": 0,
        "non_consecutive_or_missing_target": 0,
        "missing_identity": 0,
        "invalid_period": 0,
        "missing_feature_malaria_confirmed": 0,
        "missing_target_malaria_confirmed": 0,
    }
    kept: list[dict] = []
    original_trainable = sum(1 for r in panel if r.get("trainable"))

    for row in panel:
        reason = classify_exclusion(row, index)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        kept.append(build_training_row(row, index))

    kept.sort(key=lambda r: (r.get("feature_period") or "", r.get("district_slug") or ""))
    feature_completeness = [r["feature_facility_completeness"] for r in kept]
    target_completeness = [r["target_facility_completeness"] for r in kept]
    periods = sorted({r["feature_period"] for r in kept})
    target_periods = sorted({r["target_period"] for r in kept})
    districts = sorted({r["district_slug"] for r in kept})

    report = {
        "original_panel_rows": len(panel),
        "original_trainable_rows": original_trainable,
        "rows_removed_low_completeness_feature": reasons["low_completeness_feature"],
        "rows_removed_low_completeness_target": reasons["low_completeness_target"],
        "rows_removed_low_completeness_total": (
            reasons["low_completeness_feature"] + reasons["low_completeness_target"]
        ),
        "rows_removed_non_consecutive_target": reasons["non_consecutive_or_missing_target"],
        "rows_removed_other": (
            reasons["missing_identity"]
            + reasons["invalid_period"]
            + reasons["missing_feature_malaria_confirmed"]
            + reasons["missing_target_malaria_confirmed"]
        ),
        "exclusion_reasons": reasons,
        "final_training_rows": len(kept),
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
        "feature_completeness_distribution": _distribution(feature_completeness),
        "target_completeness_distribution": _distribution(target_completeness),
        "feature_availability": _availability(kept, CANDIDATE_FEATURES),
        "target": TARGET_NAME,
        "target_description": TARGET_DESCRIPTION,
        "original_panel_unmodified": True,
        "imputed_missing_months": False,
        "missing_filled_as_zero": False,
        "existing_gbt_untouched": True,
        "model_trained": False,
    }
    return kept, report


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "minimum": None, "median": None, "mean": None, "maximum": None}
    ordered = sorted(values)
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
        out[field] = {"non_null": present, "fraction": present / n if rows else 0.0}
    return out


def original_panel_path() -> Path:
    return cfg.AI_TRAINING_SETS_DIR / ORIGINAL_PANEL_NAME


def load_original_panel(path: Optional[Path] = None) -> list[dict]:
    panel_path = path or original_panel_path()
    payload = json.loads(panel_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Original malaria panel must be a JSON list")
    return payload


def persist_filtered(
    rows: list[dict],
    report: dict,
    *,
    directory: Optional[Path] = None,
) -> dict[str, str]:
    out_dir = directory or cfg.AI_TRAINING_SETS_DIR
    filtered_path = out_dir / FILTERED_PANEL_NAME
    report_path = out_dir / FILTER_REPORT_NAME
    _write_json(filtered_path, rows)
    _write_json(report_path, report)
    return {"filtered": str(filtered_path), "report": str(report_path)}


def build_filtered_training_set(
    *,
    panel_path: Optional[Path] = None,
    persist: bool = True,
) -> dict:
    panel = load_original_panel(panel_path)
    rows, report = filter_training_rows(panel)
    result = {"rows": rows, "report": report, "paths": {}}
    if persist:
        result["paths"] = persist_filtered(rows, report, directory=(panel_path.parent if panel_path else None))
        logger.info(
            "Malaria forecast filter: panel=%s kept=%s (no training)",
            len(panel),
            len(rows),
        )
    return result

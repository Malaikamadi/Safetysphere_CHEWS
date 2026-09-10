"""
Flood early-warning VALIDATION / DIAGNOSTICS.

Read-only audit of the existing CHEWS flood path.
Does NOT train a model.
Does NOT overwrite flood_model.joblib.
Does NOT modify flood_risk.py, flood_dashboard.py, weather_api.py,
the risk engine, dashboard UI, or live APIs.
Does NOT invent flood-event labels.
Does NOT convert missing observations into non-flood.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parent.parent

PROTECTED_PATHS = {
    "flood_risk_py": BACKEND / "models" / "flood_risk.py",
    "flood_dashboard_py": BACKEND / "services" / "flood_dashboard.py",
    "weather_api_py": BACKEND / "services" / "weather_api.py",
    "flood_model_joblib": BACKEND / "data" / "trained_models" / "flood_model.joblib",
    "flood_risk_v1_joblib": BACKEND / "data" / "04_ai" / "models" / "flood_risk_v1_20260731.joblib",
    "train_all_models_py": BACKEND / "training" / "train_all_models.py",
}

FLOOD_CSV_RAW = BACKEND / "data" / "raw" / "CHEWS_SierraLeone_Flood_Dataset.csv"
FLOOD_CSV_CATALOG = BACKEND / "data" / "01_raw" / "climate" / "chews_flood_features_v1.csv"
FLOOD_ZONES = BACKEND / "data" / "reference" / "flood_zones.json"
ADMIN_HIERARCHY = BACKEND / "data" / "reference" / "admin_hierarchy.csv"
COMMUNITY_CSV = BACKEND / "data" / "01_raw" / "community_reports" / "community_reports_chews_202607.csv"
COMMUNITY_CSV_RAW = BACKEND / "data" / "raw" / "CHEWS_Community_Reports_Dataset(1).csv"
FLOOD_MODEL_CARD = BACKEND / "data" / "04_ai" / "models" / "flood_risk_v1_model_card.json"
COMMUNITY_MODEL_CARD = BACKEND / "data" / "04_ai" / "models" / "community_reports_v1_model_card.json"
ARCHIVE_DIR = BACKEND / "data" / "01_raw" / "climate" / "open_meteo_archive"
MOCK_CLIMATE = BACKEND / "data" / "01_raw" / "climate" / "mock" / "archive_monthly_sample.json"
EXPANSION = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion.json"

TEMPORAL_COLUMN_NAMES = frozenset({
    "date", "datetime", "timestamp", "period", "source_period",
    "year", "month", "day", "valid_time", "event_date",
})
FREETOWN_PLACE_NAMES = frozenset({
    "kissy", "kroo bay", "susan's bay", "susans bay", "regent",
    "aberdeen", "calaba", "calaba town", "cline town", "dworzark",
    "waterloo", "mabella", "granville brook",
})
WESTERN_DISTRICTS = frozenset({
    "western urban", "western rural", "western area urban", "western area rural",
})
RAINFALL_THRESHOLD_CANDIDATES_MM = (50.0, 75.0, 100.0, 125.0, 150.0)
HEURISTIC_HIGH_GATE = 0.60
SPLIT_RANDOM_STATE = 42
SPLIT_TEST_SIZE = 0.20

VERDICT_E = "E"
VERDICT_E_LABEL = "CURRENT FLOOD MODEL IS NOT DEFENSIBLE"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def temporal_columns(columns: list[str]) -> list[str]:
    found = []
    for col in columns:
        key = str(col).strip().lower()
        if key in TEMPORAL_COLUMN_NAMES or key.endswith("_date") or key.endswith("_time"):
            found.append(col)
    return found


def missing_not_nonflood(values: list[Any]) -> list[Any]:
    """Preserve missing flood labels. Never coerce None/'' to 0 (non-flood)."""
    out = []
    for value in values:
        if value is None or value == "":
            out.append(None)
            continue
        if isinstance(value, str) and value.strip().lower() in {"na", "nan", "null", "none"}:
            out.append(None)
            continue
        out.append(value)
    return out


def classify_threshold(name: str, value: Any, origin: str) -> dict[str, Any]:
    """
    origin:
      data_derived | statistically_estimated | policy_configured | hardcoded_prototype
    """
    allowed = {
        "data_derived",
        "statistically_estimated",
        "policy_configured",
        "hardcoded_prototype",
    }
    if origin not in allowed:
        raise ValueError(f"unknown threshold origin: {origin}")
    return {"name": name, "value": value, "origin": origin, "validated_against_flood_events": False}


def point_biserial(values: list[float], binary: list[int]) -> Optional[float]:
    pairs = [
        (float(x), int(y))
        for x, y in zip(values, binary)
        if x is not None and y is not None
    ]
    if len(pairs) < 5:
        return None
    xs = [p[0] for p in pairs]
    ys = [float(p[1]) for p in pairs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def binary_metrics(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    n = len(y_true)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    far = fp / (fp + tn) if (fp + tn) else None
    miss = fn / (fn + tp) if (fn + tp) else None
    return {
        "n": n,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_alarm_rate": None if far is None else round(far, 4),
        "missed_event_rate": None if miss is None else round(miss, 4),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def roc_auc_score_simple(y_true: list[int], scores: list[float]) -> Optional[float]:
    pairs = [(s, t) for s, t in zip(scores, y_true) if s is not None and t is not None]
    positives = [s for s, t in pairs if t == 1]
    negatives = [s for s, t in pairs if t == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def rainfall_rule_predict(rainfall: list[float], threshold_mm: float) -> list[int]:
    return [1 if (r is not None and r >= threshold_mm) else 0 for r in rainfall]


def select_rainfall_threshold_on_train(
    rainfall_train: list[float],
    y_train: list[int],
    candidates: tuple[float, ...] = RAINFALL_THRESHOLD_CANDIDATES_MM,
) -> dict[str, Any]:
    """Pick a round rainfall cut on TRAIN only. Not an operational flood threshold."""
    ranked = []
    for cut in candidates:
        pred = rainfall_rule_predict(rainfall_train, cut)
        metrics = binary_metrics(y_train, pred)
        ranked.append({"threshold_mm": cut, **metrics})
    ranked.sort(key=lambda row: (row["f1"], row["recall"]), reverse=True)
    return {
        "selected_on": "train_split_only",
        "purpose": "diagnostic_baseline_not_operational_policy",
        "candidates_mm": list(candidates),
        "selected_threshold_mm": ranked[0]["threshold_mm"] if ranked else None,
        "train_ranking": ranked,
    }


def flood_history_temporal_grain(events: list[dict]) -> dict[str, Any]:
    years = []
    has_month = 0
    has_day = 0
    for event in events:
        year = event.get("year")
        if year is not None:
            years.append(int(year))
        text = " ".join(str(event.get(k) or "") for k in ("description", "impact", "date"))
        if any(m in text.lower() for m in (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        )):
            has_month += 1
        if event.get("date") or event.get("day"):
            has_day += 1
    return {
        "n_events": len(events),
        "years": sorted(set(years)),
        "year_only": True,
        "n_with_named_month_in_text": has_month,
        "n_with_day_field": has_day,
        "usable_as_dated_flood_target": False,
        "reason": (
            "Catalog narratives are year-grain (sometimes a calendar month in prose). "
            "They cannot be aligned to daily rainfall or used as supervised labels."
        ),
    }


def community_geo_mismatches(
    rows: list[dict],
    *,
    community_field: str = "community",
    district_field: str = "district",
) -> list[dict]:
    mismatches = []
    for i, row in enumerate(rows):
        community = str(row.get(community_field) or "").strip()
        district = str(row.get(district_field) or "").strip()
        if community.lower() in FREETOWN_PLACE_NAMES and district.lower() not in WESTERN_DISTRICTS:
            mismatches.append({
                "row_index": i,
                "community": community,
                "district": district,
                "issue": "freetown_or_western_place_name_assigned_to_non_western_district",
            })
    return mismatches


def candidate_targets() -> list[dict[str, Any]]:
    return [
        {
            "id": "A",
            "name": "observed_flood_event",
            "represents": "A dated inundation or flood disaster at a known place.",
            "available_in_repo": False,
            "spatial_grain": "unknown — would need community/catchment/district",
            "temporal_grain": "at least daily, preferably hourly for flash flood",
            "lead_time": "requires observations before/during event",
            "limitations": "No NDMA/MoS/IFRC/EM-DAT event list with dates is in the repository.",
        },
        {
            "id": "B",
            "name": "flood_zone_inundation",
            "represents": "Water covering a mapped flood-prone community.",
            "available_in_repo": False,
            "spatial_grain": "23 static catalog points",
            "temporal_grain": "none",
            "lead_time": "not supported",
            "limitations": "flood_zones.json is a static exposure catalog, not a time series of inundation.",
        },
        {
            "id": "C",
            "name": "facility_access_disruption",
            "represents": "Health facility unreachable because of flood.",
            "available_in_repo": False,
            "spatial_grain": "MFL facility",
            "temporal_grain": "none",
            "lead_time": "not supported",
            "limitations": "MFL join uses static zone saturation, not observed access closures.",
        },
        {
            "id": "D",
            "name": "rainfall_triggered_flood_condition",
            "represents": "Rainfall (or accumulation) above a policy gate in an exposed zone.",
            "available_in_repo": "partial — Open-Meteo can supply rainfall; flood occurrence is not observed",
            "spatial_grain": "district centroid today; zone lat/lng unused for weather",
            "temporal_grain": "hourly realtime or daily archive",
            "lead_time": "same-day to ~1–7 day forecast if forecast precip were used and disclosed",
            "limitations": (
                "Rainfall is not a flood event. Using it as a label would circularly validate "
                "a rainfall rule. Not adopted as a supervised target in this audit."
            ),
        },
        {
            "id": "E",
            "name": "flood_probability_in_future_window",
            "represents": "P(flood in next N days).",
            "available_in_repo": False,
            "spatial_grain": "undefined",
            "temporal_grain": "undefined",
            "lead_time": "the product goal, not an available label",
            "limitations": "Cannot train or backtest without dated events.",
        },
    ]


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _int_label(value: Any) -> Optional[int]:
    cleaned = missing_not_nonflood([value])[0]
    if cleaned is None:
        return None
    number = _float(cleaned)
    if number is None:
        return None
    return int(number)


def _audit_flood_table(rows: list[dict], source: str) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    labels = [_int_label(r.get("flood_occurred")) for r in rows]
    present = [v for v in labels if v is not None]
    rainfall = [_float(r.get("rainfall_mm_24h")) for r in rows]
    water = [_float(r.get("water_level_m")) for r in rows]
    elevation = [_float(r.get("elevation_m")) for r in rows]
    humidity = [_float(r.get("humidity_percent")) for r in rows]
    temp = [_float(r.get("temperature_c")) for r in rows]
    soil = [_float(r.get("soil_saturation")) for r in rows]
    reports = [_float(r.get("community_reports")) for r in rows]
    labeled = [(i, lab) for i, lab in enumerate(labels) if lab is not None]
    y = [lab for _, lab in labeled]
    idx = [i for i, _ in labeled]
    corr = {
        "rainfall_mm_24h": point_biserial([rainfall[i] for i in idx], y),
        "water_level_m": point_biserial([water[i] for i in idx], y),
        "elevation_m": point_biserial([elevation[i] for i in idx], y),
        "humidity_percent": point_biserial([humidity[i] for i in idx], y),
        "temperature_c": point_biserial([temp[i] for i in idx], y),
        "soil_saturation": point_biserial([soil[i] for i in idx], y),
        "community_reports": point_biserial([reports[i] for i in idx], y),
    }
    key_set = {tuple(sorted((k, str(v)) for k, v in row.items())) for row in rows}
    return {
        "source": source,
        "n_rows": len(rows),
        "columns": columns,
        "temporal_columns": temporal_columns(columns),
        "spatial_columns": [c for c in columns if c.lower() in {"district", "community", "lat", "lon", "lng", "latitude", "longitude"}],
        "n_missing_labels": sum(1 for v in labels if v is None),
        "class_counts": dict(Counter(present)),
        "positive_rate": (sum(present) / len(present)) if present else None,
        "completeness": {
            col: round(sum(1 for r in rows if r.get(col) not in (None, "")) / len(rows), 4)
            for col in columns
        } if rows else {},
        "rainfall_mm_24h": _describe(rainfall),
        "water_level_m": _describe(water),
        "soil_saturation": _describe(soil),
        "soil_saturation_unit_guess": (
            "fraction_0_1" if soil and max(v for v in soil if v is not None) <= 1.5 else "percent_or_unknown"
        ),
        "duplicate_row_count": len(rows) - len(key_set),
        "feature_target_point_biserial": {
            k: None if v is None else round(v, 4) for k, v in corr.items()
        },
        "real_or_synthetic": "synthetic_chews_training_table",
        "can_serve_as_flood_target": False,
        "cannot_serve_reason": (
            "No date, no location, catalogued as synthetic. flood_occurred is a generated "
            "label, not an observed Sierra Leone flood event."
        ),
    }


def _describe(values: list[Optional[float]]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    if not present:
        return {"n": 0, "missing": len(values)}
    ordered = sorted(present)
    n = len(ordered)
    return {
        "n": n,
        "missing": len(values) - n,
        "min": round(ordered[0], 4),
        "p50": round(ordered[n // 2], 4),
        "max": round(ordered[-1], 4),
        "mean": round(sum(ordered) / n, 4),
    }


def _split_indices(n: int, y: list[int], *, random_state: int = SPLIT_RANDOM_STATE) -> tuple[list[int], list[int]]:
    from sklearn.model_selection import train_test_split

    idx = list(range(n))
    train_idx, test_idx = train_test_split(
        idx, test_size=SPLIT_TEST_SIZE, random_state=random_state, stratify=y,
    )
    return list(train_idx), list(test_idx)


def _ml_feature_row(row: dict) -> list[float]:
    drainage_map = {"poor": 0, "moderate": 1, "good": 2}
    rainfall = float(row["rainfall_mm_24h"])
    drainage = drainage_map.get(str(row.get("drainage_quality") or "").lower().strip(), 1)
    elevation = float(row["elevation_m"])
    soil = float(row["soil_saturation"])
    return [
        rainfall,
        float(row["temperature_c"]),
        float(row["humidity_percent"]),
        elevation,
        float(row["water_level_m"]),
        float(drainage),
        soil,
        float(row["community_reports"]),
        rainfall * soil,
        rainfall * (2 - drainage),
        1.0 if elevation < 50 else 0.0,
    ]


def _evaluate_existing_ml_and_baselines(rows: list[dict]) -> dict[str, Any]:
    usable = []
    for row in rows:
        label = _int_label(row.get("flood_occurred"))
        if label is None:
            continue
        try:
            features = _ml_feature_row(row)
        except (TypeError, ValueError, KeyError):
            continue
        usable.append((row, features, label))
    y = [item[2] for item in usable]
    train_idx, test_idx = _split_indices(len(usable), y)
    rain_train = [float(usable[i][0]["rainfall_mm_24h"]) for i in train_idx]
    y_train = [usable[i][2] for i in train_idx]
    rain_test = [float(usable[i][0]["rainfall_mm_24h"]) for i in test_idx]
    y_test = [usable[i][2] for i in test_idx]
    threshold = select_rainfall_threshold_on_train(rain_train, y_train)
    cut = threshold["selected_threshold_mm"]
    rain_pred = rainfall_rule_predict(rain_test, cut)
    rain_metrics = binary_metrics(y_test, rain_pred)
    rain_metrics["roc_auc_using_rainfall_as_score"] = round(
        roc_auc_score_simple(y_test, rain_test) or 0.0, 4,
    )
    rain_metrics["threshold_mm"] = cut

    heuristic_pred = []
    heuristic_scores = []
    from models.flood_risk import predict as heuristic_predict

    for i in test_idx:
        row = usable[i][0]
        soil = float(row["soil_saturation"])
        soil_pct = soil * 100.0 if soil <= 1.5 else soil
        result = heuristic_predict(
            rainfall_intensity=0.0,
            rainfall_24h=float(row["rainfall_mm_24h"]),
            elevation=float(row["elevation_m"]),
            drainage_quality=str(row.get("drainage_quality") or "moderate"),
            proximity_water=2.0,
            soil_saturation=soil_pct,
        )
        heuristic_scores.append(result.risk_score)
        heuristic_pred.append(1 if result.risk_score >= HEURISTIC_HIGH_GATE else 0)
    heur_metrics = binary_metrics(y_test, heuristic_pred)
    heur_metrics["roc_auc_using_heuristic_score"] = round(
        roc_auc_score_simple(y_test, heuristic_scores) or 0.0, 4,
    )
    heur_metrics["binary_gate"] = HEURISTIC_HIGH_GATE
    heur_metrics["note"] = (
        "Heuristic expects soil_saturation in percent; CSV stores ~0–1. "
        "This diagnostic rescales CSV soil ×100 so the comparison is not an accident of units."
    )

    ml_metrics = {
        "evaluated": False,
        "reason": "flood_model.joblib missing or unloadable",
    }
    model_path = PROTECTED_PATHS["flood_model_joblib"]
    if model_path.exists():
        try:
            import joblib
            import pandas as pd

            model = joblib.load(model_path)

            feature_names = [
                "rainfall_mm_24h", "temperature_c", "humidity_percent",
                "elevation_m", "water_level_m", "drainage_encoded",
                "soil_saturation", "community_reports",
                "rain_x_saturation", "rain_x_drainage", "low_elevation_flag",
            ]
            X_test = pd.DataFrame(
                [usable[i][1] for i in test_idx],
                columns=feature_names,
            )
            pred = [int(v) for v in model.predict(X_test)]
            if hasattr(model, "predict_proba"):
                scores = [float(p[1]) for p in model.predict_proba(X_test)]
            else:
                scores = [float(v) for v in pred]
            ml_metrics = binary_metrics(y_test, pred)
            ml_metrics["roc_auc"] = round(roc_auc_score_simple(y_test, scores) or 0.0, 4)
            ml_metrics["evaluated"] = True
            ml_metrics["model_type"] = type(model).__name__
            ml_metrics["split"] = "80/20 stratified random_state=42 — NOT chronological"
            ml_metrics["universe"] = "synthetic_chews_flood_csv_holdout"
            ml_metrics["real_world_performance"] = False
        except Exception as exc:  # noqa: BLE001 — audit must not fail closed into training
            ml_metrics = {"evaluated": False, "reason": str(exc)}

    return {
        "n_scored_rows": len(usable),
        "n_train": len(train_idx),
        "n_test": len(test_idx),
        "split": {
            "method": "sklearn.train_test_split",
            "test_size": SPLIT_TEST_SIZE,
            "random_state": SPLIT_RANDOM_STATE,
            "stratify": True,
            "chronological": False,
            "leakage_risk": "random_split_of_iid_synthetic_rows_with_no_time_index",
        },
        "rainfall_threshold_baseline": {
            "selection": threshold,
            "test_metrics": rain_metrics,
        },
        "heuristic_flood_risk_predict": heur_metrics,
        "existing_gbt_synthetic_holdout": ml_metrics,
        "comparison_caveat": (
            "All three comparisons are on the SYNTHETIC flood CSV. They do not measure "
            "skill on real Sierra Leone floods. High GBT AUC here must not be reported "
            "as operational early-warning performance."
        ),
    }


def _audit_zones() -> dict[str, Any]:
    zones = json.loads(FLOOD_ZONES.read_text(encoding="utf-8"))
    admin = list(csv.DictReader(ADMIN_HIERARCHY.open(newline="", encoding="utf-8")))
    admin_ids = {row["district_id"] for row in admin}
    zone_districts = {z["district"] for z in zones}
    events = []
    lats, lngs, elevations = [], [], []
    for zone in zones:
        events.extend(zone.get("flood_history") or [])
        lats.append(float(zone["lat"]))
        lngs.append(float(zone["lng"]))
        elevations.append(float(zone["elevation_m"]))
    return {
        "source": "reference/flood_zones.json",
        "n_zones": len(zones),
        "static_manually_defined": True,
        "districts_with_zones": sorted(zone_districts),
        "districts_without_zones": sorted(admin_ids - zone_districts),
        "unmapped_zone_districts": sorted(zone_districts - admin_ids),
        "coordinates_in_sierra_leone_bbox": all(
            6.9 <= lat <= 10.1 and -13.6 <= lng <= -10.2
            for lat, lng in zip(lats, lngs)
        ),
        "elevation_m": _describe(elevations),
        "flood_history": flood_history_temporal_grain(events),
        "population_in_catalog": sum(int(z.get("population") or 0) for z in zones),
        "can_serve_as_flood_target": False,
        "limitation": (
            "Static NDMA/IFRC-aligned community catalog with narrative yearly history. "
            "Not a flood-extent time series and not linked to gauges or satellite inundation."
        ),
    }


def _audit_community() -> dict[str, Any]:
    path = COMMUNITY_CSV if COMMUNITY_CSV.exists() else COMMUNITY_CSV_RAW
    rows = _read_csv(path)
    labels = [_int_label(r.get("reported_flooding")) for r in rows]
    present = [v for v in labels if v is not None]
    dates = sorted({r.get("date") for r in rows if r.get("date")})
    mismatches = community_geo_mismatches(rows)
    damaged = [_float(r.get("damaged_houses")) for r in rows]
    displaced = [_float(r.get("displaced_households")) for r in rows]
    y = [lab for lab in labels if lab is not None]
    idx = [i for i, lab in enumerate(labels) if lab is not None]
    card = json.loads(COMMUNITY_MODEL_CARD.read_text(encoding="utf-8")) if COMMUNITY_MODEL_CARD.exists() else {}
    return {
        "source": str(path.relative_to(BACKEND)),
        "n_rows": len(rows),
        "date_range": {"min": dates[0] if dates else None, "max": dates[-1] if dates else None},
        "unique_dates": len(dates),
        "class_counts": dict(Counter(present)),
        "n_missing_labels": sum(1 for v in labels if v is None),
        "n_geo_mismatches": len(mismatches),
        "geo_mismatch_examples": mismatches[:8],
        "point_biserial_damaged_houses": (
            None if not idx else round(point_biserial([damaged[i] for i in idx], y) or 0.0, 4)
        ),
        "point_biserial_displaced_households": (
            None if not idx else round(point_biserial([displaced[i] for i in idx], y) or 0.0, 4)
        ),
        "model_card_review_status": card.get("review_status"),
        "leakage_features_in_training": [
            "damage_displacement_index = damaged_houses * displaced_households",
            "total_impact = damaged_houses + displaced_households + water_contamination",
        ],
        "real_or_synthetic": "synthetic_chews_training_table",
        "can_serve_as_independent_validation": False,
        "can_serve_as_event_labels": False,
        "reason": (
            "July-2026 synthetic rows; Freetown place names randomly paired with inland "
            "districts; community RF is BLOCKED for leakage. Not ground truth."
        ),
    }


def _audit_weather() -> dict[str, Any]:
    archive_files = [
        p.name for p in ARCHIVE_DIR.glob("*")
        if p.is_file() and p.name != ".gitkeep"
    ] if ARCHIVE_DIR.exists() else []
    expansion_note = None
    if EXPANSION.exists():
        expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
        periods = sorted({r.get("source_period") for r in expansion if r.get("source_period")})
        expansion_note = {
            "present": True,
            "n_rows": len(expansion),
            "period_min": periods[0] if periods else None,
            "period_max": periods[-1] if periods else None,
            "has_rainfall_mm": any("rainfall_mm" in r for r in expansion[:5]),
            "usable_as_flood_target": False,
            "note": "District-month malaria climate join. Monthly rainfall is not a flood event.",
        }
    else:
        expansion_note = {"present": False, "usable_as_flood_target": False}
    return {
        "realtime": {
            "module": "services/weather_api.py",
            "provider": "Open-Meteo Forecast API",
            "url_pattern": "https://api.open-meteo.com/v1/forecast",
            "variables": ["current.precipitation", "hourly.precipitation past_hours=24"],
            "temporal_resolution": "hourly / current",
            "spatial_resolution": "Open-Meteo grid at requested lat/lon",
            "coordinates_used": "district centroids from admin_hierarchy.csv, not flood-zone lat/lng",
            "cache_ttl_seconds": 3600,
            "on_failure": "flood_dashboard falls back to synthetic climatology jitter",
            "alignable_to_flood_observations": False,
            "reason": "No dated flood observations exist to align against.",
        },
        "historical_archive": {
            "module": "services/climate_archive.py",
            "provider": "Open-Meteo Archive",
            "base_url": "https://archive-api.open-meteo.com/v1/archive",
            "daily_variables": [
                "temperature_2m_mean", "precipitation_sum", "relative_humidity_2m_mean",
            ],
            "default_mock_mode": True,
            "downloaded_archive_files": archive_files,
            "large_download_performed": False,
            "current_aggregation": "daily → district-month for malaria join",
            "flood_would_need": "daily or sub-daily precip at zone coordinates plus an event target",
            "historical_rainfall_retrievable": True,
            "historical_rainfall_retrieved_for_this_audit": False,
            "mock_fixture": str(MOCK_CLIMATE.relative_to(BACKEND)) if MOCK_CLIMATE.exists() else None,
        },
        "malaria_monthly_climate_reuse": expansion_note,
        "river_gauges": {"available": False},
        "soil_moisture_observations": {"available": False, "live_path": "synthesised in flood_dashboard"},
        "tide_observations": {"available": False, "live_path": "12.4h sine heuristic for coastal districts"},
    }


def _threshold_audit() -> list[dict[str, Any]]:
    return [
        classify_threshold("heuristic_rainfall_intensity_50mm_h", 50, "hardcoded_prototype"),
        classify_threshold("heuristic_rainfall_intensity_30mm_h", 30, "hardcoded_prototype"),
        classify_threshold("heuristic_rainfall_intensity_15mm_h", 15, "hardcoded_prototype"),
        classify_threshold("heuristic_rainfall_intensity_7_5mm_h", 7.5, "hardcoded_prototype"),
        classify_threshold("heuristic_rainfall_24h_100mm", 100, "hardcoded_prototype"),
        classify_threshold("heuristic_rainfall_24h_50mm", 50, "hardcoded_prototype"),
        classify_threshold("heuristic_elevation_5m", 5, "hardcoded_prototype"),
        classify_threshold("heuristic_elevation_15m", 15, "hardcoded_prototype"),
        classify_threshold("heuristic_composite_low_0.20", 0.20, "hardcoded_prototype"),
        classify_threshold("heuristic_composite_moderate_0.40", 0.40, "hardcoded_prototype"),
        classify_threshold("heuristic_composite_high_0.60", 0.60, "hardcoded_prototype"),
        classify_threshold("heuristic_composite_severe_0.80", 0.80, "hardcoded_prototype"),
        classify_threshold("dashboard_population_at_risk_0.40", 0.40, "hardcoded_prototype"),
        classify_threshold("alert_engine_flood_advisory_0.30", 0.30, "hardcoded_prototype"),
        classify_threshold("alert_engine_flood_watch_0.50", 0.50, "hardcoded_prototype"),
        classify_threshold("alert_engine_flood_warning_0.70", 0.70, "hardcoded_prototype"),
        classify_threshold("alert_engine_flood_emergency_0.85", 0.85, "hardcoded_prototype"),
        classify_threshold("mfl_high_saturation_75pct", 75, "hardcoded_prototype"),
        classify_threshold("community_rf_critical_0.80", 0.80, "hardcoded_prototype"),
        classify_threshold("gbt_predict_class_0.5", 0.5, "hardcoded_prototype"),
        classify_threshold("drainage_poor_score_0.85", 0.85, "hardcoded_prototype"),
    ]


def _architecture() -> dict[str, Any]:
    return {
        "live_path": [
            "Open-Meteo realtime precip (district centroid) OR synthetic climatology jitter",
            "services/flood_dashboard._district_signal (soil/river/tide synthesised)",
            "reference/flood_zones.json static geomorphology",
            "models.flood_risk.predict heuristic composite",
            "GET /strategic/flood-dashboard and /flood-zone/{id}/forecast",
            "frontend Flood Atlas / early-warning pages",
        ],
        "ml_path": [
            "data/raw/CHEWS_SierraLeone_Flood_Dataset.csv (synthetic)",
            "training/train_all_models.py GradientBoostingClassifier, random 80/20 split",
            "data/trained_models/flood_model.joblib",
            "models.flood_risk.predict_ml — NOT called by routers",
        ],
        "parallel_unvalidated_paths": [
            "POST /early-warning/assess uses the same heuristic + alert_engine hardcoded cuts",
            "POST /healthcare/ml/community-flood uses BLOCKED community RF",
            "routers/situation_room.py uses random.uniform flood scores",
            "frontend/early-warning.js ships hardcoded demo flood alerts",
        ],
        "live_uses_trained_gbt": False,
        "spatial_grain_live": "23 catalog communities nested in 16 districts",
        "temporal_grain_live": "nowcast snapshot; 24h hourly outlook is a decay heuristic, not NWP",
        "training_period": "none — synthetic rows have no dates",
        "inference_period": "wall-clock time at request",
    }


def build_flood_validation_report(*, generated_at: Optional[str] = None) -> dict[str, Any]:
    generated_at = generated_at or _now()
    hashes_before = {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}
    raw_rows = _read_csv(FLOOD_CSV_RAW)
    catalog_rows = _read_csv(FLOOD_CSV_CATALOG) if FLOOD_CSV_CATALOG.exists() else []
    identical_csvs = sha256_file(FLOOD_CSV_RAW) == sha256_file(FLOOD_CSV_CATALOG)
    card = json.loads(FLOOD_MODEL_CARD.read_text(encoding="utf-8")) if FLOOD_MODEL_CARD.exists() else {}
    comparison = _evaluate_existing_ml_and_baselines(raw_rows)
    weather = _audit_weather()
    ml_holdout = comparison["existing_gbt_synthetic_holdout"]
    rain_auc = comparison["rainfall_threshold_baseline"]["test_metrics"].get("roc_auc_using_rainfall_as_score")
    gbt_auc = ml_holdout.get("roc_auc") if ml_holdout.get("evaluated") else None
    ml_adds_value = bool(
        ml_holdout.get("evaluated")
        and gbt_auc is not None
        and rain_auc is not None
        and gbt_auc > rain_auc + 0.05
    )

    report = {
        "generated_at": generated_at,
        "diagnostic_only": True,
        "model_trained_this_phase": False,
        "integrated_into_chews": False,
        "invented_flood_labels": False,
        "missing_converted_to_nonflood": False,
        "large_weather_download": False,
        "architecture": _architecture(),
        "existing_model": {
            "algorithm": "GradientBoostingClassifier",
            "artifact": "data/trained_models/flood_model.joblib",
            "duplicate_artifact": "data/04_ai/models/flood_risk_v1_20260731.joblib",
            "features": card.get("features", {}).get("list"),
            "target": "flood_occurred",
            "training_rows": 300,
            "split": "80/20 stratified random_state=42",
            "card_metrics": card.get("metrics"),
            "card_limitations": card.get("known_limitations"),
            "review_status": card.get("review_status"),
            "live_dashboard_calls_predict_ml": False,
        },
        "weather": weather,
        "available_data": {
            "A_rainfall": {
                "realtime_open_meteo": True,
                "historical_archive_api": True,
                "historical_archive_downloaded": bool(
                    weather["historical_archive"]["downloaded_archive_files"]
                ),
                "historical_archive_files": weather["historical_archive"]["downloaded_archive_files"],
                "synthetic_csv_rainfall_24h": True,
                "is_flood_event": False,
            },
            "B_temperature": {"synthetic_csv": True, "archive_api": True, "is_flood_event": False},
            "C_humidity": {"synthetic_csv": True, "archive_api": True, "is_flood_event": False},
            "D_river_water_level": {
                "observed_gauges": False,
                "synthetic_csv_water_level_m": True,
                "live_river_stage": "derived from rainfall_24h + jitter",
            },
            "E_flood_event_observations": {"available": False},
            "F_flood_zone_geographic": _audit_zones(),
            "G_facility_location": {
                "mfl_present": True,
                "flood_join": "district name map onto static zones; saturation≥75 → High",
            },
            "H_population_exposure": {
                "zone_population_field": True,
                "source": "static catalog integers, not census time series",
            },
            "I_community_flood_reports": _audit_community(),
            "J_historical_flood_labels": {
                "synthetic_flood_occurred": True,
                "observed_event_labels": False,
            },
        },
        "flood_training_tables": {
            "raw_csv": _audit_flood_table(raw_rows, str(FLOOD_CSV_RAW.relative_to(BACKEND))),
            "catalog_csv_identical_to_raw": identical_csvs,
            "catalog_n_rows": len(catalog_rows),
        },
        "data_quality": {
            "rule_missing_is_not_nonflood": True,
            "synthetic_table_has_no_missing_labels": _audit_flood_table(raw_rows, "raw")["n_missing_labels"] == 0,
            "no_temporal_index": True,
            "no_spatial_index_on_training_rows": True,
            "duplicate_training_rows": _audit_flood_table(raw_rows, "raw")["duplicate_row_count"],
        },
        "target_assessment": {
            "candidates": candidate_targets(),
            "selected_supervised_target": None,
            "supervised_flood_prediction_supported": False,
            "conclusion": (
                "The repository has no defensible observed flood-event target. "
                "Current data cannot support supervised flood prediction."
            ),
        },
        "temporal_alignment": {
            "training_csv_time": None,
            "zone_history_grain": "year",
            "live_features_timing": {
                "open_meteo_precip": "contemporaneous / past 24h",
                "soil_saturation": "synthesised now",
                "river_stage": "synthesised from current rainfall_24h",
                "24h_outlook": "heuristic decay of current intensity — uses no future NWP",
                "water_level_m_in_gbt": "same-row as flood_occurred; contemporaneous, not lead-time",
            },
            "horizons_supported_by_event_data": [],
            "horizons_not_evaluable": ["same-day", "1-day", "3-day", "7-day"],
        },
        "geographic_alignment": {
            "weather_to_zone": (
                "District centroid weather is applied to every zone in that district. "
                "Zone lat/lng are unused for Open-Meteo."
            ),
            "community_reports_to_zones": "names overlap some catalog places but pairing is random",
            "facilities_to_zones": "district-level, not point-in-polygon",
            "chiefdoms": "not used",
        },
        "leakage_audit": {
            "synthetic_labels": True,
            "random_split_without_time": True,
            "water_level_same_row_as_target": True,
            "soil_saturation_same_row_as_target": True,
            "community_reports_count_same_row": True,
            "interaction_features_from_same_row": True,
            "future_rainfall_in_training": False,
            "duplicate_training_files": identical_csvs,
            "community_rf_target_derived_features": True,
            "card_auc_0_991_is_not_real_world": True,
            "passed_as_operationally_valid": False,
        },
        "baseline_comparison": comparison,
        "ml_justified": False,
        "ml_adds_value_on_synthetic_holdout": ml_adds_value,
        "ml_justification": (
            "ML is not justified. Labels are synthetic, the split is random, several features "
            "are contemporaneous with the label, and the live atlas does not even call the GBT. "
            "A rainfall threshold on the same table is the honest baseline; any GBT lift is "
            "lift on a generator, not on Sierra Leone floods."
        ),
        "early_warning": {
            "lead_time_evidence": None,
            "average_lead_time": None,
            "median_lead_time": None,
            "recall_on_real_events": None,
            "false_alarm_rate_on_real_events": None,
            "missed_event_rate_on_real_events": None,
            "reason": "No dated historical flood events are available to measure lead time.",
        },
        "thresholds": _threshold_audit(),
        "health_linkage_opportunities": {
            "facility_access": "MFL coordinates exist; no flood-closure outcomes.",
            "service_disruption": "not observed",
            "disease_risk": "malaria DHIS2 is a separate track; no flood→malaria causal claim.",
            "displacement": "only synthetic community fields and catalog impact prose",
            "causal_claim_made": False,
        },
        "verdict": {
            "classification": VERDICT_E,
            "label": VERDICT_E_LABEL,
            "also_true": [
                "B. NEEDS MORE HISTORICAL FLOOD DATA",
                "D. SIMPLE STATISTICAL/RULE-BASED METHOD IS PREFERABLE (if rebuilt after data exist)",
                "F. MORE DATA/EXTERNAL VALIDATION REQUIRED",
            ],
            "not_selected": [
                "A. READY FOR CONTROLLED SHADOW VALIDATION — no event target analogous to DHIS2 positivity",
                "C. EXISTING MODEL NEEDS REDESIGN — redesign is premature until independent events exist",
            ],
        },
        "protected_hashes_before": hashes_before,
        "disclaimer": (
            "Diagnostic audit only. Not a flood forecast. Not an outbreak or disaster declaration. "
            "Card accuracy 0.9667 / ROC-AUC 0.991 is synthetic-holdout and is not real-world performance."
        ),
    }
    return report


def assert_protected_unchanged(before: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    after = {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}
    if after != before:
        changed = [k for k in after if after[k] != before.get(k)]
        raise RuntimeError(f"protected flood artifacts changed: {changed}")
    return after

"""
Build a district-month malaria training panel from DHIS2 + Archive climate.

Target: malaria_confirmed at t+1, using information available at t.

Does not retrain or invoke malaria_predictor.predict().
The synthetic GBT contract (fever, stagnation, breeding sites) is not required here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from config import dhis2 as cfg
from services.climate_archive import ingest_historical_climate, load_latest_climate
from services.dhis2_historical import extract_historical, load_latest_district_month
from services.dhis2_pipeline import _write_json
from services.dhis2_service import Dhis2Client
from services.district_names import district_slug

logger = logging.getLogger("chews.training_panel")

_cache: dict[str, Any] = {"panel": None}

NOT_READY = "NOT READY FOR MODEL TRAINING"
READY = "READY FOR MODEL TRAINING"


def _calendar_month(period: Optional[str]) -> Optional[int]:
    if not period or len(str(period)) < 6:
        return None
    try:
        month = int(str(period)[4:6])
    except ValueError:
        return None
    if 1 <= month <= 12:
        return month
    return None


def join_district_month(
    health: list[dict],
    climate: list[dict],
) -> list[dict]:
    climate_index = {}
    for row in climate:
        key = (row.get("source_period") or row.get("period"), district_slug(row.get("district_slug") or row.get("district_name")))
        climate_index[key] = row

    joined = []
    for health_row in health:
        period = health_row.get("source_period") or health_row.get("period")
        slug = district_slug(health_row.get("district_slug") or health_row.get("district_name"))
        clim = climate_index.get((period, slug)) or {}
        joined.append({
            "source_period": period,
            "period": period,
            "period_type": "monthly",
            "district_slug": slug,
            "district_id": health_row.get("district_id") or clim.get("district_id"),
            "district_name": health_row.get("district_name") or clim.get("district_name"),
            "malaria_confirmed": health_row.get("malaria_confirmed"),
            "malaria_confirmed_u5": health_row.get("malaria_confirmed_u5"),
            "malaria_tests": health_row.get("malaria_tests"),
            "malaria_rdt_positive": health_row.get("malaria_rdt_positive"),
            "expected_facilities": health_row.get("expected_facilities"),
            "reporting_facilities": health_row.get("reporting_facilities"),
            "facility_completeness": health_row.get("completeness"),
            "rainfall_mm": clim.get("rainfall_mm"),
            "temperature_c": clim.get("temperature_c"),
            "humidity_percent": clim.get("humidity_percent"),
            "climate_source": clim.get("source"),
            "health_source": health_row.get("source"),
            "calendar_month": _calendar_month(period),
        })
    return joined


def engineer_training_features(joined: list[dict]) -> list[dict]:
    """
    Per district, add lag-1/lag-2 health+climate and malaria_confirmed_next.

    Rows without a next month are kept but are not trainable.
    """
    by_district: dict[str, list[dict]] = {}
    for row in joined:
        by_district.setdefault(row.get("district_slug") or "", []).append(row)

    out = []
    for slug, rows in by_district.items():
        ordered = sorted(rows, key=lambda r: r.get("source_period") or "")
        for i, row in enumerate(ordered):
            prev1 = ordered[i - 1] if i >= 1 else None
            prev2 = ordered[i - 2] if i >= 2 else None
            nxt = ordered[i + 1] if i + 1 < len(ordered) else None
            tests = row.get("malaria_tests")
            rdt = row.get("malaria_rdt_positive")
            positivity = None
            if tests is not None and rdt is not None and tests != 0:
                positivity = rdt / tests
            feat = dict(row)
            feat["lag1_malaria_confirmed"] = prev1.get("malaria_confirmed") if prev1 else None
            feat["lag2_malaria_confirmed"] = prev2.get("malaria_confirmed") if prev2 else None
            feat["lag1_rainfall_mm"] = prev1.get("rainfall_mm") if prev1 else None
            feat["lag1_temperature_c"] = prev1.get("temperature_c") if prev1 else None
            feat["lag1_humidity_percent"] = prev1.get("humidity_percent") if prev1 else None
            feat["rdt_positivity"] = positivity
            feat["malaria_confirmed_next"] = nxt.get("malaria_confirmed") if nxt else None
            feat["has_next_period"] = nxt is not None
            feat["trainable"] = _is_trainable(feat)
            out.append(feat)
    out.sort(key=lambda r: (r.get("source_period") or "", r.get("district_slug") or ""))
    return out


def _is_trainable(row: dict) -> bool:
    required = (
        row.get("malaria_confirmed"),
        row.get("lag1_malaria_confirmed"),
        row.get("rainfall_mm"),
        row.get("temperature_c"),
        row.get("humidity_percent"),
        row.get("malaria_confirmed_next"),
        row.get("calendar_month"),
        row.get("district_slug"),
    )
    return all(v is not None and v != "" for v in required)


def assess_training_readiness(
    features: list[dict],
    *,
    health_source: Optional[str],
    climate_source: Optional[str],
    mock_health: bool,
    mock_climate: bool,
    requested_months: list[str],
) -> dict:
    trainable = [r for r in features if r.get("trainable")]
    districts = sorted({r.get("district_slug") for r in features if r.get("district_slug") and r.get("district_slug") != "_unmapped"})
    observed_months = sorted({r.get("source_period") for r in features if r.get("source_period")})
    with_confirmed = [r for r in features if r.get("malaria_confirmed") is not None]
    with_climate = [
        r for r in features
        if r.get("rainfall_mm") is not None
        and r.get("temperature_c") is not None
        and r.get("humidity_percent") is not None
    ]
    cartesian = len(districts) * len(requested_months) if districts and requested_months else 0
    filled = 0
    if cartesian:
        have = {(r.get("district_slug"), r.get("source_period")) for r in with_confirmed}
        for slug in districts:
            for month in requested_months:
                if (slug, month) in have:
                    filled += 1
    completeness = (filled / cartesian) if cartesian else 0.0
    climate_coverage = (len(with_climate) / len(features)) if features else 0.0

    checks = [
        {
            "id": "live_dhis2",
            "ok": (not mock_health) and health_source == "dhis2_live",
            "detail": f"health_source={health_source} mock={mock_health}",
        },
        {
            "id": "live_climate",
            "ok": (not mock_climate) and climate_source == "open_meteo_archive",
            "detail": f"climate_source={climate_source} mock={mock_climate}",
        },
        {
            "id": "min_requested_months",
            "ok": len(requested_months) >= cfg.TRAINING_MIN_MONTHS,
            "detail": f"{len(requested_months)} requested (min {cfg.TRAINING_MIN_MONTHS})",
        },
        {
            "id": "min_observed_months",
            "ok": len(observed_months) >= cfg.TRAINING_MIN_MONTHS,
            "detail": f"{len(observed_months)} observed (min {cfg.TRAINING_MIN_MONTHS})",
        },
        {
            "id": "min_districts",
            "ok": len(districts) >= cfg.TRAINING_MIN_DISTRICTS,
            "detail": f"{len(districts)} districts (min {cfg.TRAINING_MIN_DISTRICTS})",
        },
        {
            "id": "district_month_completeness",
            "ok": completeness >= cfg.TRAINING_MIN_DISTRICT_MONTH_COMPLETENESS,
            "detail": f"{completeness:.3f} (min {cfg.TRAINING_MIN_DISTRICT_MONTH_COMPLETENESS})",
        },
        {
            "id": "climate_coverage",
            "ok": climate_coverage >= cfg.TRAINING_MIN_CLIMATE_COVERAGE,
            "detail": f"{climate_coverage:.3f} (min {cfg.TRAINING_MIN_CLIMATE_COVERAGE})",
        },
        {
            "id": "min_trainable_rows",
            "ok": len(trainable) >= cfg.TRAINING_MIN_TRAINABLE_ROWS,
            "detail": f"{len(trainable)} trainable rows (min {cfg.TRAINING_MIN_TRAINABLE_ROWS})",
        },
        {
            "id": "target_is_malaria_confirmed_next",
            "ok": True,
            "detail": "target variable is malaria_confirmed_next (t+1); not malaria_cases",
        },
        {
            "id": "synthetic_gbt_not_used",
            "ok": True,
            "detail": "panel does not feed malaria_predictor.predict()",
        },
    ]
    ready = all(c["ok"] for c in checks if c["id"] not in {"target_is_malaria_confirmed_next", "synthetic_gbt_not_used"})
    # The last two are documentation checks and are always ok; readiness depends on data bars.
    blocking = [c for c in checks if not c["ok"]]
    verdict = READY if ready else NOT_READY
    return {
        "verdict": verdict,
        "ready": ready,
        "trainable_rows": len(trainable),
        "feature_rows": len(features),
        "districts": districts,
        "observed_months": observed_months,
        "requested_months": requested_months,
        "district_month_completeness": completeness,
        "climate_coverage": climate_coverage,
        "checks": checks,
        "blocking_checks": [c["id"] for c in blocking],
        "target": "malaria_confirmed_next",
        "prototype_gbt": {
            "retrained": False,
            "connected_to_this_panel": False,
            "note": "Existing malaria GBT remains a synthetic-data prototype.",
        },
    }


def build_training_panel(
    *,
    refresh_health: bool = True,
    refresh_climate: bool = True,
    persist: bool = True,
    dhis2_client: Optional[Dhis2Client] = None,
    climate_mock: Optional[bool] = None,
    climate_opener=None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    months: Optional[int] = None,
) -> dict:
    health_extract = None
    if refresh_health:
        health_extract = extract_historical(
            client=dhis2_client,
            start=start,
            end=end,
            months=months,
            persist=persist,
        )
        health_rows = health_extract.get("district_month") or []
    else:
        health_rows = load_latest_district_month() or []
        health_extract = {"source": None, "mock": True, "requested_months": []}

    if refresh_climate:
        climate_extract = ingest_historical_climate(
            start=start or (health_extract or {}).get("period_start"),
            end=end or (health_extract or {}).get("period_end"),
            months=months,
            mock=climate_mock,
            persist=persist,
            opener=climate_opener,
        )
        climate_rows = climate_extract.get("district_month") or []
    else:
        climate_extract = {"source": None, "mock": True}
        climate_rows = load_latest_climate() or []

    requested = list(
        (health_extract or {}).get("requested_months")
        or (climate_extract or {}).get("requested_months")
        or []
    )
    joined = join_district_month(health_rows, climate_rows)
    features = engineer_training_features(joined)
    readiness = assess_training_readiness(
        features,
        health_source=(health_extract or {}).get("source"),
        climate_source=(climate_extract or {}).get("source"),
        mock_health=bool((health_extract or {}).get("mock")),
        mock_climate=bool((climate_extract or {}).get("mock")),
        requested_months=requested,
    )
    result = {
        "health": {
            "source": (health_extract or {}).get("source"),
            "mock": (health_extract or {}).get("mock"),
            "completeness": (health_extract or {}).get("completeness"),
            "period_start": (health_extract or {}).get("period_start"),
            "period_end": (health_extract or {}).get("period_end"),
            "district_month_rows": len(health_rows),
        },
        "climate": {
            "source": (climate_extract or {}).get("source"),
            "mock": (climate_extract or {}).get("mock"),
            "row_count": len(climate_rows),
            "realtime_weather_untouched": True,
        },
        "joined_rows": len(joined),
        "feature_rows": len(features),
        "trainable_preview": [r for r in features if r.get("trainable")][:5],
        "features": features,
        "readiness": readiness,
        "verdict": readiness["verdict"],
    }
    if persist:
        _write_json(cfg.AI_TRAINING_SETS_DIR / "malaria_district_month_panel_latest.json", features)
        _write_json(cfg.AI_TRAINING_SETS_DIR / "training_readiness_latest.json", readiness)
        result["paths"] = {
            "panel": str(cfg.AI_TRAINING_SETS_DIR / "malaria_district_month_panel_latest.json"),
            "readiness": str(cfg.AI_TRAINING_SETS_DIR / "training_readiness_latest.json"),
        }
    _cache["panel"] = result
    logger.info("Training panel verdict=%s trainable=%s", readiness["verdict"], readiness["trainable_rows"])
    return result


def cached_panel() -> Optional[dict]:
    return _cache.get("panel")


def load_latest_readiness() -> Optional[dict]:
    path = cfg.AI_TRAINING_SETS_DIR / "training_readiness_latest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    cached = cached_panel()
    if cached:
        return cached.get("readiness")
    return None

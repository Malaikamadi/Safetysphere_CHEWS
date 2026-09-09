"""
DHIS2 ingest pipeline using the existing CHEWS data lake.

01_raw/dhis2      original Analytics + org-unit JSON (immutable)
02_staging/dhis2  normalized rows + quality report
03_curated/surveillance  long + wide tables joined to org units / MFL
04_ai/features    DHIS2-only temporal features (lags/rolling) — not a second malaria GBT
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import dhis2 as cfg
from services import dhis2_orgunits, dhis2_service
from services.dhis2_service import Dhis2Client, parse_analytics_rows
from services.dhis2_periods import classify_period
from services.chews_feature_join import join_feature_rows

logger = logging.getLogger("chews.dhis2")

_cache: dict[str, Any] = {
    "ingest": None,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return _utcnow().strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def period_sort_key(period: str) -> str:
    return period or ""


def is_valid_period(period: str) -> bool:
    """Row periods must be concrete DHIS2 calendars, not relative query tokens."""
    info = classify_period(period)
    return info["period_type"] in {"monthly", "weekly", "daily", "quarterly", "yearly"}


def validate_records(
    records: list[dict],
    mapped_units: list[dict],
    *,
    expected_level: int = 5,
    stale_days: Optional[int] = None,
) -> dict:
    """Quality report. Missing values are not filled with zero."""
    stale_days = cfg.DHIS2_STALE_DAYS if stale_days is None else stale_days
    mapped_index = {m.get("dhis2_org_unit_id"): m for m in mapped_units}
    issues: list[dict] = []
    seen: dict[tuple, int] = {}
    duplicates = 0
    missing_indicator = 0
    missing_ou = 0
    invalid_numeric = 0
    invalid_period = 0
    negative_counts = 0
    unmapped_facilities = 0
    unexpected_level = 0
    missing_values = 0

    count_ids = set(cfg.DHIS2_INDICATORS[k] for k in cfg.DHIS2_COUNT_INDICATORS)

    for rec in records:
        key = (rec.get("indicator_id"), rec.get("period"), rec.get("org_unit_id"))
        if key in seen:
            duplicates += 1
            issues.append({"code": "duplicate", "record": key})
        else:
            seen[key] = 1
        if not rec.get("indicator_id"):
            missing_indicator += 1
            issues.append({"code": "missing_indicator_id", "period": rec.get("period")})
        if not rec.get("org_unit_id"):
            missing_ou += 1
            issues.append({"code": "missing_org_unit_id", "indicator_id": rec.get("indicator_id")})
        if rec.get("invalid_numeric"):
            invalid_numeric += 1
            issues.append({"code": "invalid_numeric", "key": key})
        if rec.get("value") is None:
            missing_values += 1
        if not is_valid_period(str(rec.get("period") or "")):
            invalid_period += 1
            issues.append({"code": "invalid_period", "period": rec.get("period")})
        val = rec.get("value")
        if val is not None and rec.get("indicator_id") in count_ids and val < 0:
            negative_counts += 1
            issues.append({"code": "negative_count", "key": key, "value": val})
        meta = mapped_index.get(rec.get("org_unit_id"))
        if meta:
            if meta.get("is_facility_level") and meta.get("unmapped"):
                unmapped_facilities += 1
            if meta.get("level") not in (None, expected_level):
                unexpected_level += 1
                issues.append({
                    "code": "unexpected_org_unit_level",
                    "org_unit_id": rec.get("org_unit_id"),
                    "level": meta.get("level"),
                    "expected": expected_level,
                })
        elif rec.get("org_unit_id"):
            unmapped_facilities += 1

    periods = sorted({r.get("period") for r in records if r.get("period")})
    stale = False
    newest = periods[-1] if periods else None
    if newest and newest[:6].isdigit() and len(newest) >= 6:
        try:
            year, month = int(newest[:4]), int(newest[4:6])
            now = _utcnow()
            age_months = (now.year - year) * 12 + (now.month - month)
            stale = age_months > max(1, stale_days // 30)
        except ValueError:
            stale = False
    if not records:
        issues.append({"code": "empty_extract"})

    report = {
        "record_count": len(records),
        "unique_keys": len(seen),
        "duplicates": duplicates,
        "missing_indicator_ids": missing_indicator,
        "missing_org_unit_ids": missing_ou,
        "invalid_numeric_values": invalid_numeric,
        "invalid_periods": invalid_period,
        "negative_counts": negative_counts,
        "missing_values": missing_values,
        "unmapped_org_units": unmapped_facilities,
        "unexpected_levels": unexpected_level,
        "stale": stale,
        "newest_period": newest,
        "periods": periods,
        "reporting_gap_periods": _gap_periods(periods),
        "issues_truncated": issues[:200],
        "missing_not_zero_filled": True,
    }
    return report


def _gap_periods(periods: list[str]) -> list[str]:
    """Detect missing YYYYMM months in an otherwise monthly series. Unknown calendars → []."""
    monthly = [p for p in periods if isinstance(p, str) and re.fullmatch(r"\d{6}", p)]
    if len(monthly) < 2:
        return []
    monthly = sorted(monthly)
    missing: list[str] = []
    y, m = int(monthly[0][:4]), int(monthly[0][4:6])
    end_y, end_m = int(monthly[-1][:4]), int(monthly[-1][4:6])
    have = set(monthly)
    while (y, m) <= (end_y, end_m):
        token = f"{y:04d}{m:02d}"
        if token not in have:
            missing.append(token)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return missing


def build_long_rows(records: list[dict], mapped_units: list[dict], *, source: str, ingested_at: str) -> list[dict]:
    index = {m.get("dhis2_org_unit_id"): m for m in mapped_units}
    id_to_key = cfg.indicator_id_to_key()
    long_rows = []
    for rec in records:
        meta = index.get(rec.get("org_unit_id")) or {}
        uid = rec.get("indicator_id")
        long_rows.append({
            "indicator_id": uid,
            "indicator_key": id_to_key.get(uid),
            "indicator_name": cfg.indicator_name_for_id(uid) if uid else None,
            "period": rec.get("source_period") or rec.get("period"),
            "source_period": rec.get("source_period") or rec.get("period"),
            "period_type": rec.get("period_type"),
            "normalized_period": rec.get("normalized_period"),
            "org_unit_id": rec.get("org_unit_id"),
            "facility_name": meta.get("mfl_facility_name") or meta.get("display_name"),
            "facility_level": meta.get("level"),
            "district_id": meta.get("district_id"),
            "district_name": meta.get("mfl_district") or meta.get("district_name"),
            "council_id": meta.get("council_id"),
            "council_name": meta.get("council_name"),
            "zone_id": meta.get("zone_id"),
            "zone_name": meta.get("zone_name"),
            "latitude": meta.get("latitude"),
            "longitude": meta.get("longitude"),
            "value": rec.get("value"),
            "mfl_mapped": bool(meta.get("mfl_mapped")),
            "unmapped": bool(meta.get("unmapped")),
            "source": source,
            "ingested_at": ingested_at,
        })
    return long_rows


def build_wide_table(long_rows: list[dict]) -> list[dict]:
    """
    Pivot count indicators for aggregation (sums). Percentage indicators are omitted
    so they are never treated as counts. See build_curated_malaria() for the health contract.
    Missing cells remain None (not 0).
    """
    count_keys = set(cfg.DHIS2_COUNT_INDICATORS)
    buckets: dict[tuple, dict] = {}
    for row in long_rows:
        key_name = row.get("indicator_key")
        if key_name not in count_keys:
            continue
        bucket_key = (row.get("period"), row.get("org_unit_id"))
        slot = buckets.get(bucket_key)
        if slot is None:
            slot = {
                "period": row.get("source_period") or row.get("period"),
                "source_period": row.get("source_period") or row.get("period"),
                "period_type": row.get("period_type"),
                "normalized_period": row.get("normalized_period"),
                "org_unit_id": row.get("org_unit_id"),
                "facility_name": row.get("facility_name"),
                "district_id": row.get("district_id"),
                "district_name": row.get("district_name"),
                "council_id": row.get("council_id"),
                "council_name": row.get("council_name"),
                "zone_id": row.get("zone_id"),
                "zone_name": row.get("zone_name"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "mfl_mapped": row.get("mfl_mapped"),
                "source": row.get("source"),
                "ingested_at": row.get("ingested_at"),
            }
            for ck in cfg.DHIS2_COUNT_INDICATORS:
                slot[ck] = None
            buckets[bucket_key] = slot
        slot[key_name] = row.get("value")
    return [buckets[k] for k in sorted(buckets.keys(), key=lambda t: (t[0] or "", t[1] or ""))]


def build_curated_malaria(long_rows: list[dict]) -> list[dict]:
    """Facility-period health contract including percentage indicators as nullable fields."""
    value_keys = tuple(cfg.DHIS2_COUNT_INDICATORS) + tuple(cfg.DHIS2_PERCENT_INDICATORS)
    buckets: dict[tuple, dict] = {}
    for row in long_rows:
        key_name = row.get("indicator_key")
        if key_name not in value_keys:
            continue
        bucket_key = (row.get("source_period") or row.get("period"), row.get("org_unit_id"))
        slot = buckets.get(bucket_key)
        if slot is None:
            slot = {
                "source_period": row.get("source_period") or row.get("period"),
                "period": row.get("source_period") or row.get("period"),
                "period_type": row.get("period_type"),
                "normalized_period": row.get("normalized_period"),
                "org_unit_id": row.get("org_unit_id"),
                "facility_name": row.get("facility_name"),
                "facility_level": row.get("facility_level"),
                "district_id": row.get("district_id"),
                "district_name": row.get("district_name"),
                "council_id": row.get("council_id"),
                "council_name": row.get("council_name"),
                "zone_id": row.get("zone_id"),
                "zone_name": row.get("zone_name"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "mfl_mapped": row.get("mfl_mapped"),
                "source": row.get("source"),
                "ingested_at": row.get("ingested_at"),
            }
            for vk in value_keys:
                slot[vk] = None
            buckets[bucket_key] = slot
        slot[key_name] = row.get("value")
    return [buckets[k] for k in sorted(buckets.keys(), key=lambda t: (t[0] or "", t[1] or ""))]


def engineer_features(wide_rows: list[dict]) -> list[dict]:
    """
    DHIS2 temporal features only.

    The prototype malaria GBT is trained on synthetic climate columns
    (see training/train_all_models.py). Those columns are not created here
    and are not invented from DHIS2.
    """
    by_ou: dict[str, list[dict]] = {}
    for row in wide_rows:
        by_ou.setdefault(row.get("org_unit_id") or "", []).append(row)
    features = []
    for ou, rows in by_ou.items():
        ordered = sorted(rows, key=lambda r: period_sort_key(r.get("period") or ""))
        for i, row in enumerate(ordered):
            prev = ordered[i - 1] if i else None
            window = ordered[max(0, i - 2): i + 1]
            confirmed = row.get("malaria_confirmed")
            tests = row.get("malaria_tests")
            rdt = row.get("malaria_rdt_positive")
            prev_confirmed = prev.get("malaria_confirmed") if prev else None
            change = None
            if confirmed is not None and prev_confirmed is not None:
                change = confirmed - prev_confirmed
            roll_vals = [r.get("malaria_confirmed") for r in window if r.get("malaria_confirmed") is not None]
            positivity = None
            if tests is not None and rdt is not None and tests != 0:
                positivity = rdt / tests
            feat = dict(row)
            feat["lag1_malaria_confirmed"] = prev_confirmed
            feat["delta_malaria_confirmed"] = change
            feat["rolling_sum_malaria_confirmed"] = sum(roll_vals) if roll_vals else None
            feat["rolling_avg_malaria_confirmed"] = (sum(roll_vals) / len(roll_vals)) if roll_vals else None
            feat["rdt_positivity"] = positivity
            feat["child_malaria_burden"] = row.get("malaria_confirmed_u5")
            feat["testing_volume"] = tests
            features.append(feat)
    return features


def reporting_completeness(wide_rows: list[dict], period: Optional[str] = None) -> Optional[float]:
    subset = [r for r in wide_rows if period is None or r.get("period") == period]
    if not subset:
        return None
    reported = sum(1 for r in subset if r.get("malaria_confirmed") is not None)
    return reported / len(subset)


def live_case_overlay(admin: str) -> Optional[dict]:
    """
    Optional malaria case counts for the existing healthcare live forecast.
    Returns None when no curated DHIS2 extract is loaded (prototype constants remain).
    """
    ingest = _cache.get("ingest")
    if not ingest:
        latest = cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_wide_latest.json"
        if latest.exists():
            try:
                ingest = {"wide": json.loads(latest.read_text(encoding="utf-8")), "source": "disk"}
            except json.JSONDecodeError:
                return None
        else:
            return None
    wide = ingest.get("wide") or []
    if not wide:
        return None
    periods = sorted({r.get("period") for r in wide if r.get("period")})
    if not periods:
        return None
    current_p = periods[-1]
    previous_p = periods[-2] if len(periods) >= 2 else None

    def _sum_period(p: str) -> Optional[float]:
        rows = [r for r in wide if r.get("period") == p]
        if admin and admin not in ("national", ""):
            want = admin.casefold()
            rows = [
                r for r in rows
                if (r.get("district_name") or "").casefold() == want
                or (r.get("district_name") or "").casefold().replace(" district", "") == want.replace(" district", "")
            ]
        vals = [r.get("malaria_confirmed") for r in rows if r.get("malaria_confirmed") is not None]
        if not vals:
            return None
        return float(sum(vals))

    current = _sum_period(current_p)
    if current is None:
        return None
    previous = _sum_period(previous_p) if previous_p else None
    return {
        "current_cases": int(round(current)),
        "previous_cases": int(round(previous)) if previous is not None else None,
        "period": current_p,
        "previous_period": previous_p,
        "admin_unit": admin,
        "source": "DHIS2 Analytics (CHEWS ingest)",
    }


def risk_engine_inputs_from_dhis2(admin: str = "national") -> Optional[dict]:
    """Map DHIS2 confirmed malaria onto the existing risk_engine.assess() arguments."""
    overlay = live_case_overlay(admin)
    if not overlay:
        return None
    current = overlay["current_cases"]
    previous = overlay.get("previous_cases")
    trend = "stable"
    if previous is not None:
        if current > previous * 1.1:
            trend = "increasing"
        elif current < previous * 0.9:
            trend = "decreasing"
    return {
        "reported_cases": current,
        "trend": trend,
        "dhis2": overlay,
        "gaps": {
            "rainfall": "Not provided by DHIS2 Analytics — supply from climate source or prototype constants",
            "temperature": "Not provided by DHIS2 Analytics",
            "humidity": "Not provided by DHIS2 Analytics",
            "vulnerable_population": "Not provided by DHIS2 Analytics",
            "exposure_level": "Not provided by DHIS2 Analytics",
        },
        "prototype_malaria_gbt_gaps": [
            "rainfall_mm", "temperature_c", "humidity_percent",
            "water_stagnation_index", "mosquito_breeding_sites",
            "reported_fever_cases", "population_density",
        ],
    }


def ingest(
    *,
    client: Optional[Dhis2Client] = None,
    period: Optional[str] = None,
    ou_dimension: Optional[str] = None,
    include_supporting: Optional[bool] = None,
    persist: bool = True,
) -> dict:
    client = client or Dhis2Client()
    ingested_at = _utcnow().isoformat()
    source = "dhis2_mock" if client.mock else "dhis2_live"
    indicator_ids = cfg.analytics_indicator_ids(include_supporting=include_supporting)
    pe = period or cfg.DHIS2_PERIOD
    ou = ou_dimension or cfg.DHIS2_OU_DIMENSION

    analytics = client.fetch_analytics(
        indicator_ids=indicator_ids, period=pe, ou_dimension=ou,
        include_supporting=include_supporting,
    )
    org_units = client.fetch_organisation_units()
    records = parse_analytics_rows(analytics)
    mapped = dhis2_orgunits.map_organisation_units(org_units)
    quality = validate_records(records, mapped)
    long_rows = build_long_rows(records, mapped, source=source, ingested_at=ingested_at)
    wide = build_wide_table(long_rows)
    curated = build_curated_malaria(long_rows)
    features = engineer_features(wide)
    joined = join_feature_rows(curated, climate=None, environment=None, population=None)
    completeness = {
        p: reporting_completeness(wide, p) for p in quality.get("periods") or []
    }

    result = {
        "ingested_at": ingested_at,
        "source": source,
        "period_query": pe,
        "ou_query": ou,
        "indicator_ids": indicator_ids,
        "quality": quality,
        "records": records,
        "mapped_org_units": mapped,
        "long": long_rows,
        "wide": wide,
        "curated": curated,
        "features": features,
        "joined_features": joined,
        "reporting_completeness": completeness,
        "mock": client.mock,
    }

    if persist:
        stamp = _stamp()
        raw_payload = {
            "analytics": analytics,
            "organisationUnits": {"organisationUnits": org_units} if isinstance(org_units, list) else org_units,
        }
        raw_path = cfg.RAW_DHIS2_DIR / "analytics" / f"dhis2_analytics_{stamp}.json"
        meta_path = cfg.RAW_DHIS2_DIR / "analytics" / f"dhis2_analytics_{stamp}.meta.json"
        _write_json(raw_path, raw_payload)
        _write_json(meta_path, {
            "ingestion_timestamp": ingested_at,
            "source": source,
            "endpoint": "/api/analytics",
            "org_units_endpoint": "/api/organisationUnits",
            "indicator_ids": indicator_ids,
            "period_query": pe,
            "organisation_unit_query": ou,
            "raw_path": str(raw_path.relative_to(cfg.DATA_DIR)),
            "note": "Raw DHIS2 JSON is stored unmodified inside the analytics key.",
        })
        _write_json(cfg.STAGING_DHIS2_DIR / "dhis2_analytics_normalized_latest.json", {
            "ingested_at": ingested_at,
            "records": records,
            "quality": quality,
        })
        _write_json(cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_long_latest.json", long_rows)
        _write_json(cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_wide_latest.json", wide)
        _write_json(cfg.CURATED_SURVEILLANCE_DIR / "dhis2_org_units_mapped_latest.json", mapped)
        _write_json(cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_latest.json", curated)
        _write_json(cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_long_latest.json", long_rows)
        _write_json(cfg.AI_FEATURES_DIR / "dhis2_malaria_features_latest.json", features)
        _write_json(cfg.AI_FEATURES_DIR / "chews_malaria_features_latest.json", joined)
        result["paths"] = {
            "raw": str(raw_path),
            "staging": str(cfg.STAGING_DHIS2_DIR / "dhis2_analytics_normalized_latest.json"),
            "curated_long": str(cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_long_latest.json"),
            "curated_malaria": str(cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_latest.json"),
            "curated_wide_compat": str(cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_wide_latest.json"),
            "features": str(cfg.AI_FEATURES_DIR / "dhis2_malaria_features_latest.json"),
            "joined_features": str(cfg.AI_FEATURES_DIR / "chews_malaria_features_latest.json"),
        }
        logger.info(
            "DHIS2 ingest stored source=%s records=%s wide=%s duplicates=%s",
            source, len(records), len(wide), quality.get("duplicates"),
        )

    _cache["ingest"] = result
    return result


def cached_ingest() -> Optional[dict]:
    return _cache.get("ingest")


def load_latest_curated() -> Optional[dict]:
    malaria_path = cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_latest.json"
    wide_path = cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_wide_latest.json"
    long_path = cfg.CURATED_DHIS2_MALARIA_DIR / "dhis2_malaria_long_latest.json"
    if not long_path.exists():
        long_path = cfg.CURATED_SURVEILLANCE_DIR / "dhis2_malaria_long_latest.json"
    fac_path = cfg.CURATED_SURVEILLANCE_DIR / "dhis2_org_units_mapped_latest.json"
    if not malaria_path.exists() and not wide_path.exists():
        return None
    try:
        wide = json.loads(wide_path.read_text(encoding="utf-8")) if wide_path.exists() else []
        curated = json.loads(malaria_path.read_text(encoding="utf-8")) if malaria_path.exists() else wide
        long_rows = json.loads(long_path.read_text(encoding="utf-8")) if long_path.exists() else []
        mapped = json.loads(fac_path.read_text(encoding="utf-8")) if fac_path.exists() else []
    except json.JSONDecodeError:
        return None
    payload = {
        "wide": wide or curated,
        "curated": curated,
        "long": long_rows,
        "mapped_org_units": mapped,
        "source": "disk",
    }
    _cache["ingest"] = {**(_cache.get("ingest") or {}), **payload}
    return payload

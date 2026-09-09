"""
Historical DHIS2 malaria extract for a future training panel.

Flow:
  explicit YYYYMM months
  → raw Analytics (facility LEVEL-5)
  → validation (does not fill 0)
  → facility → district mapping
  → district-month aggregation
  → completeness report

Does not call malaria_predictor.predict().
Does not retrain the synthetic GBT.
Uses core count indicators only (not child_malaria_death percentages).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from config import dhis2 as cfg
from services import dhis2_orgunits
from services.dhis2_periods import chunk_months, classify_period, historical_window
from services.dhis2_pipeline import (
    _write_json,
    build_long_rows,
    build_wide_table,
    validate_records,
)
from services.dhis2_service import Dhis2Client, parse_analytics_rows
from services.district_names import display_name, district_slug

logger = logging.getLogger("chews.dhis2.historical")

CORE_HISTORICAL_KEYS = (
    "malaria_confirmed",
    "malaria_confirmed_u5",
    "malaria_tests",
    "malaria_rdt_positive",
)

_cache: dict[str, Any] = {"extract": None}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def core_indicator_ids() -> list[str]:
    return [cfg.DHIS2_INDICATORS[key] for key in CORE_HISTORICAL_KEYS]


def fetch_historical_analytics(
    client: Dhis2Client,
    months: list[str],
    *,
    ou_dimension: Optional[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Fetch Analytics for an explicit monthly list.

    Live mode chunks YYYYMM tokens so URLs stay bounded.
    Mock mode is a single fixture read (the fixture ignores the requested range).
    """
    ids = core_indicator_ids()
    ou = ou_dimension or cfg.DHIS2_OU_DIMENSION
    if client.mock:
        payload = client.fetch_analytics(indicator_ids=ids, period=",".join(months), ou_dimension=ou)
        return [payload], parse_analytics_rows(payload)

    payloads: list[dict] = []
    records: list[dict] = []
    chunks = chunk_months(months, cfg.DHIS2_HISTORICAL_CHUNK_MONTHS)
    for group in chunks:
        pe = ",".join(group)
        payload = client.fetch_analytics(indicator_ids=ids, period=pe, ou_dimension=ou)
        payloads.append(payload)
        records.extend(parse_analytics_rows(payload))
    return payloads, records


def expected_facilities_by_district(mapped_units: list[dict]) -> dict[str, dict]:
    """Count Level-5 facilities per district slug from the org-unit map."""
    out: dict[str, dict] = {}
    for unit in mapped_units:
        if not unit.get("is_facility_level"):
            continue
        raw_name = unit.get("mfl_district") or unit.get("district_name")
        slug = district_slug(raw_name)
        if not slug:
            slug = "_unmapped"
        slot = out.setdefault(slug, {
            "district_slug": slug,
            "district_name": display_name(slug, raw_name),
            "district_id": unit.get("district_id"),
            "facility_ids": set(),
        })
        if unit.get("dhis2_org_unit_id"):
            slot["facility_ids"].add(unit["dhis2_org_unit_id"])
        if not slot.get("district_id"):
            slot["district_id"] = unit.get("district_id")
    for slot in out.values():
        slot["expected_facilities"] = len(slot["facility_ids"])
        slot["facility_ids"] = sorted(slot["facility_ids"])
    return out


def aggregate_district_month(
    wide_rows: list[dict],
    expected: dict[str, dict],
) -> list[dict]:
    """
    Sum facility-period counts to district-month.

    Missing facility cells stay out of the sum (not treated as 0).
    A district-month with zero reporting facilities has null counts.
    """
    buckets: dict[tuple, dict] = {}
    for row in wide_rows:
        period = row.get("source_period") or row.get("period")
        info = classify_period(str(period or ""))
        if info["period_type"] != "monthly":
            continue
        slug = district_slug(row.get("district_name"))
        if not slug:
            slug = "_unmapped"
        key = (period, slug)
        slot = buckets.get(key)
        if slot is None:
            exp = expected.get(slug) or {}
            slot = {
                "source_period": period,
                "period": period,
                "period_type": "monthly",
                "normalized_period": period,
                "district_slug": slug,
                "district_name": display_name(slug, row.get("district_name")),
                "district_id": row.get("district_id") or exp.get("district_id"),
                "expected_facilities": exp.get("expected_facilities", 0),
                "reporting_facilities": 0,
                "reporting_facility_ids": [],
                "source": row.get("source"),
                "ingested_at": row.get("ingested_at"),
            }
            for ck in CORE_HISTORICAL_KEYS:
                slot[ck] = None
                slot[f"{ck}_n"] = 0
            buckets[key] = slot
        ou = row.get("org_unit_id")
        if row.get("malaria_confirmed") is not None and ou:
            if ou not in slot["reporting_facility_ids"]:
                slot["reporting_facility_ids"].append(ou)
                slot["reporting_facilities"] = len(slot["reporting_facility_ids"])
        for ck in CORE_HISTORICAL_KEYS:
            val = row.get(ck)
            if val is None:
                continue
            if slot[ck] is None:
                slot[ck] = 0.0
            slot[ck] += float(val)
            slot[f"{ck}_n"] += 1

    rows = []
    for key in sorted(buckets.keys(), key=lambda t: (t[0] or "", t[1] or "")):
        slot = buckets[key]
        expected_n = slot.get("expected_facilities") or 0
        reported_n = slot.get("reporting_facilities") or 0
        slot["completeness"] = (reported_n / expected_n) if expected_n else None
        slot.pop("reporting_facility_ids", None)
        rows.append(slot)
    return rows


def completeness_report(
    *,
    requested_months: list[str],
    district_month: list[dict],
    quality: dict,
    expected: dict[str, dict],
    source: str,
    mock: bool,
) -> dict:
    observed_months = sorted({r.get("source_period") for r in district_month if r.get("source_period")})
    missing_months = [m for m in requested_months if m not in set(observed_months)]
    districts = sorted({r.get("district_slug") for r in district_month if r.get("district_slug") and r.get("district_slug") != "_unmapped"})
    known_admin = {district_slug(n) for n in (
        "Western Area Urban", "Western Area Rural", "Bo", "Pujehun", "Bonthe",
        "Kenema", "Port Loko", "Kambia", "Tonkolili", "Moyamba", "Bombali",
        "Kailahun", "Kono", "Koinadugu", "Falaba", "Karene",
    )}
    with_confirmed = [r for r in district_month if r.get("malaria_confirmed") is not None]
    denom = max(1, len(districts) * len(requested_months)) if districts else len(requested_months)
    # Completeness vs the requested cartesian product (district × requested month)
    filled = 0
    for slug in districts:
        have = {r["source_period"] for r in district_month if r.get("district_slug") == slug and r.get("malaria_confirmed") is not None}
        filled += sum(1 for m in requested_months if m in have)
    cartesian = len(districts) * len(requested_months) if districts else 0
    district_month_completeness = (filled / cartesian) if cartesian else 0.0

    mean_facility_completeness = None
    comps = [r.get("completeness") for r in district_month if r.get("completeness") is not None]
    if comps:
        mean_facility_completeness = sum(comps) / len(comps)

    return {
        "source": source,
        "mock": mock,
        "requested_months": requested_months,
        "requested_month_count": len(requested_months),
        "observed_months": observed_months,
        "observed_month_count": len(observed_months),
        "missing_months": missing_months,
        "districts": districts,
        "district_count": len(districts),
        "admin_districts_expected": 16,
        "admin_districts_present": len([d for d in districts if d in known_admin]),
        "district_month_rows": len(district_month),
        "district_months_with_malaria_confirmed": len(with_confirmed),
        "district_month_completeness": district_month_completeness,
        "mean_facility_reporting_completeness": mean_facility_completeness,
        "expected_facilities_by_district": {
            k: v.get("expected_facilities") for k, v in expected.items() if k != "_unmapped"
        },
        "cell_quality": {
            "duplicates": quality.get("duplicates"),
            "invalid_numeric_values": quality.get("invalid_numeric_values"),
            "negative_counts": quality.get("negative_counts"),
            "missing_values": quality.get("missing_values"),
            "unmapped_org_units": quality.get("unmapped_org_units"),
            "missing_not_zero_filled": True,
        },
        "notes": [
            "Mock Analytics fixtures ignore the requested historical range.",
            "LAST_5_YEARS is not used; months are explicit YYYYMM tokens.",
            "Facility missing values are not imputed as zero before district sums.",
        ],
    }


def extract_historical(
    *,
    client: Optional[Dhis2Client] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    months: Optional[int] = None,
    ou_dimension: Optional[str] = None,
    persist: bool = True,
) -> dict:
    client = client or Dhis2Client()
    start_m, end_m, month_list = historical_window(
        start=start or cfg.DHIS2_HISTORICAL_START,
        end=end or cfg.DHIS2_HISTORICAL_END,
        months=months or cfg.DHIS2_HISTORICAL_MONTHS,
    )
    ingested_at = _utcnow_iso()
    source = "dhis2_mock" if client.mock else "dhis2_live"
    ou = ou_dimension or cfg.DHIS2_OU_DIMENSION

    payloads, records = fetch_historical_analytics(client, month_list, ou_dimension=ou)
    org_units = client.fetch_organisation_units()
    mapped = dhis2_orgunits.map_organisation_units(org_units)
    quality = validate_records(records, mapped)
    long_rows = build_long_rows(records, mapped, source=source, ingested_at=ingested_at)
    wide = build_wide_table(long_rows)
    expected = expected_facilities_by_district(mapped)
    district_month = aggregate_district_month(wide, expected)
    completeness = completeness_report(
        requested_months=month_list,
        district_month=district_month,
        quality=quality,
        expected=expected,
        source=source,
        mock=client.mock,
    )

    result = {
        "ingested_at": ingested_at,
        "source": source,
        "mock": client.mock,
        "period_start": start_m,
        "period_end": end_m,
        "period_query": ",".join(month_list),
        "requested_months": month_list,
        "ou_query": ou,
        "indicator_ids": core_indicator_ids(),
        "indicator_keys": list(CORE_HISTORICAL_KEYS),
        "quality": quality,
        "completeness": completeness,
        "records": records,
        "mapped_org_units": mapped,
        "wide": wide,
        "district_month": district_month,
        "prototype_gbt": {
            "retrained": False,
            "connected": False,
            "note": "Historical extract is a data foundation only. malaria_predictor.predict() is not called.",
        },
    }

    if persist:
        stamp = _stamp()
        raw_dir = cfg.RAW_DHIS2_HISTORICAL_DIR
        raw_path = raw_dir / f"dhis2_analytics_historical_{stamp}.json"
        _write_json(raw_path, {"chunks": payloads, "organisationUnits": org_units})
        _write_json(raw_dir / f"dhis2_analytics_historical_{stamp}.meta.json", {
            "ingestion_timestamp": ingested_at,
            "source": source,
            "period_start": start_m,
            "period_end": end_m,
            "requested_months": month_list,
            "indicator_ids": core_indicator_ids(),
            "ou_query": ou,
            "note": "Raw DHIS2 JSON stored unmodified inside chunks[].",
        })
        _write_json(cfg.STAGING_DHIS2_DIR / "dhis2_historical_normalized_latest.json", {
            "ingested_at": ingested_at,
            "records": records,
            "quality": quality,
        })
        _write_json(cfg.CURATED_DISTRICT_MONTH_DIR / "dhis2_malaria_district_month_latest.json", district_month)
        _write_json(cfg.CURATED_DISTRICT_MONTH_DIR / "dhis2_malaria_historical_completeness_latest.json", completeness)
        result["paths"] = {
            "raw": str(raw_path),
            "district_month": str(cfg.CURATED_DISTRICT_MONTH_DIR / "dhis2_malaria_district_month_latest.json"),
            "completeness": str(cfg.CURATED_DISTRICT_MONTH_DIR / "dhis2_malaria_historical_completeness_latest.json"),
        }
        logger.info(
            "DHIS2 historical extract source=%s requested_months=%s observed=%s districts=%s",
            source,
            len(month_list),
            completeness.get("observed_month_count"),
            completeness.get("district_count"),
        )

    _cache["extract"] = result
    return result


def cached_extract() -> Optional[dict]:
    return _cache.get("extract")


def load_latest_district_month() -> Optional[list[dict]]:
    path = cfg.CURATED_DISTRICT_MONTH_DIR / "dhis2_malaria_district_month_latest.json"
    if not path.exists():
        cached = cached_extract()
        if cached:
            return cached.get("district_month")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

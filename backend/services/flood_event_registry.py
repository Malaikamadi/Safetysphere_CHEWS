"""
Flood-event acquisition and normalization.

Purpose: enlarge chews_flood_event_v0 from dated, attributed observations.

Does NOT train, create flood_occurred, invent rainfall thresholds, assign
district centroids, convert unmatched places into catalog zones, or treat
silence as a non-flood.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

SOURCE_TYPE_MAP = {
    "ndma_register": "government_ndma",
    "ndma_assessment": "government_ndma",
    "ifrc_dref": "humanitarian_ifrc",
    "copernicus_ems": "remote_sensing_copernicus",
    "un_spider": "humanitarian_un",
    "un_ocha": "humanitarian_ocha",
    "reliefweb": "humanitarian_reliefweb",
    "government_local": "government_local",
    "flood_zones_catalog_narrative": "compiled_catalog",
}

SOURCE_STRENGTH = {
    "ndma_register": 100,
    "copernicus_ems": 90,
    "ndma_assessment": 80,
    "un_ocha": 70,
    "un_spider": 65,
    "ifrc_dref": 60,
    "government_local": 55,
    "reliefweb": 40,
    "flood_zones_catalog_narrative": 10,
}

CONFIDENCE_STRENGTH = {"high": 3, "medium": 2, "low": 1}

LOCATION_MERGE_ALIASES = {
    "kroobay": "kroo bay",
    "kroo-bay": "kroo bay",
    "mabela": "mabella",
    "barthurst": "bathurst",
    "colleh town": "colleh town",
    "collen town": "colleh town",
    "koleh town": "colleh town",
    "kolleh town": "colleh town",
    "koleh community": "colleh town",
    "mount auorel": "mount aurel",
    "bumbuna dam": "bumbuna",
    "water street": "wellington",
    "water street wellington": "wellington",
    "wellington water street": "wellington",
}

WESTERN_AREA_DISTRICTS = {"western_area_urban", "western_area_rural"}


def source_type_for(event_source: Any, explicit: Any = None) -> Optional[str]:
    if explicit:
        return str(explicit)
    if not event_source:
        return None
    return SOURCE_TYPE_MAP.get(str(event_source), str(event_source))


def normalize_merge_location(name: Any) -> str:
    from services.chews_flood_event_v0 import _norm_name

    text = _norm_name(name)
    return LOCATION_MERGE_ALIASES.get(text, text)


def merge_key(record: dict) -> Optional[tuple]:
    start = record.get("event_start_date") or record.get("event_date")
    if not start:
        return None
    location = normalize_merge_location(
        record.get("event_location_name") or record.get("location_name")
    )
    if not location:
        return None
    district = str(record.get("district") or "").strip().lower() or None
    return (str(start), location, district)


def _source_rank(record: dict) -> tuple:
    source = record.get("event_source") or record.get("source")
    confidence = record.get("confidence")
    return (
        SOURCE_STRENGTH.get(str(source), 0),
        CONFIDENCE_STRENGTH.get(str(confidence), 0),
        1 if record.get("source_url") else 0,
    )


def _as_source_ref(record: dict, *, note: Optional[str] = None) -> dict[str, Any]:
    ref = {
        "event_source": record.get("event_source") or record.get("source"),
        "source_type": source_type_for(record.get("event_source"), record.get("source_type")),
        "source_url": record.get("source_url"),
        "source_document": record.get("source_document"),
        "source_record_id": record.get("source_record_id"),
    }
    if note:
        ref["note"] = note
    return {key: value for key, value in ref.items() if value not in (None, "")}


def merge_corroborated_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """One canonical event per date+location; preserve all corroborating sources."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    passthrough: list[dict] = []
    for record in records:
        key = merge_key(record)
        if key is None or record.get("exclude_from_daily_target"):
            passthrough.append(record)
            continue
        groups[key].append(record)

    merged: list[dict] = []
    duplicate_candidates: list[dict] = []
    for key, items in groups.items():
        if len(items) == 1:
            record = dict(items[0])
            existing = list(record.get("corroborating_sources") or [])
            record["corroborating_sources"] = existing
            record["corroboration_count"] = 1 + len(existing)
            record["merged_from_record_ids"] = [record.get("source_record_id")]
            merged.append(record)
            continue

        ranked = sorted(items, key=_source_rank, reverse=True)
        canonical = dict(ranked[0])
        refs = list(canonical.get("corroborating_sources") or [])
        seen = {
            (
                ref.get("event_source"),
                ref.get("source_url"),
                ref.get("source_record_id"),
            )
            for ref in refs
            if isinstance(ref, dict)
        }
        for extra in ranked[1:]:
            ref = _as_source_ref(extra, note="Merged as the same dated location; not a second flood.")
            marker = (ref.get("event_source"), ref.get("source_url"), ref.get("source_record_id"))
            if marker not in seen:
                refs.append(ref)
                seen.add(marker)
            extra_text = extra.get("description") or extra.get("evidence_text")
            canonical_text = canonical.get("description") or ""
            if extra_text and extra_text not in canonical_text:
                canonical["description"] = f"{canonical_text} | Corroboration: {extra_text}".strip(" |")
            if _source_rank(extra) >= _source_rank(canonical):
                for field in ("source_url", "source_document", "confidence"):
                    if extra.get(field) and not canonical.get(field):
                        canonical[field] = extra[field]
        canonical["corroborating_sources"] = refs
        canonical["corroboration_count"] = 1 + len(refs)
        canonical["merged_from_record_ids"] = [item.get("source_record_id") for item in ranked]
        if canonical.get("latitude") in (None, "") or canonical.get("longitude") in (None, ""):
            for item in ranked:
                if item.get("latitude") not in (None, "") and item.get("longitude") not in (None, ""):
                    canonical["latitude"] = item.get("latitude")
                    canonical["longitude"] = item.get("longitude")
                    break
        merged.append(canonical)
        duplicate_candidates.append({
            "key": {"event_date": key[0], "location": key[1], "district": key[2]},
            "record_ids": [item.get("source_record_id") for item in ranked],
            "canonical_id": canonical.get("source_record_id"),
            "action": "merged_to_one_event",
        })

    return merged + passthrough, duplicate_candidates


def geographic_floor_met(districts: set[str]) -> dict[str, Any]:
    named = {item for item in districts if item}
    n_districts = len(named)
    has_western_area = bool(named & WESTERN_AREA_DISTRICTS)
    other_regimes = named - WESTERN_AREA_DISTRICTS
    eight_districts = n_districts >= 8
    western_plus_four = has_western_area and len(other_regimes) >= 4
    return {
        "n_districts": n_districts,
        "has_western_area": has_western_area,
        "n_other_geographic_regimes": len(other_regimes),
        "other_geographic_regimes": sorted(other_regimes),
        "eight_districts_met": eight_districts,
        "western_area_plus_four_regimes_met": western_plus_four,
        "met": eight_districts or western_plus_four,
    }


def wet_season_year(event_date: Optional[str]) -> Optional[str]:
    if not event_date or len(event_date) < 7:
        return None
    try:
        month = int(event_date[5:7])
    except ValueError:
        return None
    if 5 <= month <= 11:
        return event_date[:4]
    return None

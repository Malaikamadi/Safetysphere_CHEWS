"""
CHEWS flood event registry v0 — observation registry, not a model.

Does NOT train.
Does NOT create flood_occurred from rainfall.
Does NOT fabricate NDMA register rows.
Does NOT convert year-only catalog narratives into daily events.
Does NOT silently assign district centroids.
Does NOT create negative/non-event days.
Does NOT modify flood_weather_history_v1 or production CHEWS.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parent.parent
FLOOD_ZONES = BACKEND / "data" / "reference" / "flood_zones.json"
PUBLIC_ASSESSMENTS = BACKEND / "data" / "01_raw" / "flood_events" / "public_assessments_v0.json"
NDMA_EXTRACT = BACKEND / "data" / "01_raw" / "flood_events" / "ndma_extract.json"
WEATHER_CSV = BACKEND / "data" / "04_ai" / "training_sets" / "flood_weather_history_v1.csv"

PROTECTED_PATHS = {
    "flood_risk_py": BACKEND / "models" / "flood_risk.py",
    "flood_dashboard_py": BACKEND / "services" / "flood_dashboard.py",
    "weather_api_py": BACKEND / "services" / "weather_api.py",
    "flood_model_joblib": BACKEND / "data" / "trained_models" / "flood_model.joblib",
    "weather_history_csv": WEATHER_CSV,
}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLANNING_MIN_DATED_EVENTS = 30
PLANNING_MIN_WET_SEASONS = 3
PLANNING_MIN_DISTRICTS = 8

FORBIDDEN_LABEL_FIELDS = ("flood_occurred", "is_flood", "flood_label", "negative_label")
LEAD_SAFE_WEATHER = (
    "rainfall_prev_24h",
    "rainfall_prev_72h",
    "rainfall_prev_7d",
    "rainfall_prev_14d",
)

NAME_ALIASES = {
    "kroo bay": "kroo_bay",
    "kroobay": "kroo_bay",
    "kroo-bay": "kroo_bay",
    "susan's bay": "susans_bay",
    "susans bay": "susans_bay",
    "mabella": "mabella",
    "granville brook": "granville_brook",
    "kingtom": "granville_brook",
    "regent": "regent",
    "sugar loaf": "regent",
    "regent / sugar loaf": "regent",
    "kissy": "kissy",
    "wellington": "wellington",
    "calaba town": "calaba_town",
    "lumley": "lumley",
    "waterloo": "waterloo",
    "hastings": "hastings_jui",
    "jui": "hastings_jui",
    "bo town": "bo_town",
    "sumbuya": "sumbuya",
    "pujehun town": "pujehun_town",
    "bonthe island": "bonthe_island",
    "sherbro island": "bonthe_island",
    "mattru jong": "mattru_jong",
    "kenema town": "kenema_town",
    "lungi": "lungi_tagrin",
    "tagrin": "lungi_tagrin",
    "kambia town": "kambia_town",
    "rokupr": "rokupr",
    "magburaka": "magburaka",
    "bumbuna": "bumbuna",
    "bumbuna dam": "bumbuna",
    "shenge": "shenge",
}

EVENT_FIELDS = [
    "event_id", "event_source", "source_url", "source_document", "source_record_id",
    "event_start_date", "event_end_date", "temporal_grain",
    "event_location_name", "event_location_type", "district",
    "latitude", "longitude",
    "location_match_status", "matched_flood_zone_id", "matched_flood_zone_name",
    "location_match_method", "centroid_assigned_silently",
    "observation_status", "confidence",
    "description", "corroborating_sources",
    "weather_join_status",
    "rainfall_prev_24h", "rainfall_prev_72h", "rainfall_prev_7d", "rainfall_prev_14d",
    "event_day_precipitation_mm", "event_day_rainfall_24h",
    "lead_time_eligible", "in_daily_target",
]


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


def protected_hashes() -> dict[str, Optional[str]]:
    return {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}


def assert_protected_unchanged(before: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    after = protected_hashes()
    if after != before:
        changed = [k for k in after if after[k] != before.get(k)]
        raise RuntimeError(f"protected artifacts changed: {changed}")
    return after


def _blank(value: Any) -> bool:
    return value is None or value == ""


def parse_iso_date(value: Any) -> Optional[date]:
    if _blank(value):
        return None
    text = str(value).strip()
    if not ISO_DATE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _norm_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "").replace("\u2019", "")
    text = re.sub(r"[^a-z0-9\s/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_flood_zones() -> list[dict]:
    return json.loads(FLOOD_ZONES.read_text(encoding="utf-8"))


def historical_context_from_catalog(zones: Optional[list[dict]] = None) -> list[dict]:
    """Year-only catalog narratives. Not daily events. Not labels."""
    zones = zones or load_flood_zones()
    rows = []
    for zone in zones:
        for item in zone.get("flood_history") or []:
            year = item.get("year")
            if year is None:
                continue
            rows.append({
                "context_id": f"catalog-{zone['id']}-{year}",
                "flood_zone_id": f"zone:{zone['id']}",
                "flood_zone_name": zone.get("name"),
                "district": zone.get("district"),
                "year": int(year),
                "description": item.get("description"),
                "impact": item.get("impact"),
                "source": "reference/flood_zones.json",
                "temporal_grain": "year",
                "in_daily_target": False,
                "note": "Year-only compiled narrative. Not a calendar-day event and not a flood label.",
            })
    return rows


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def match_event_location(event: dict, zones: list[dict]) -> dict[str, Any]:
    """Match to catalog flood zones. Never silent centroid."""
    lat = event.get("latitude")
    lon = event.get("longitude")
    name = _norm_name(event.get("event_location_name"))

    if lat is not None and lon is not None:
        best = None
        best_km = None
        for zone in zones:
            kilometres = haversine_km(float(lat), float(lon), float(zone["lat"]), float(zone["lng"]))
            if best_km is None or kilometres < best_km:
                best, best_km = zone, kilometres
        if best is not None and best_km is not None and best_km <= 0.5:
            return {
                "location_match_status": "matched",
                "matched_flood_zone_id": f"zone:{best['id']}",
                "matched_flood_zone_name": best.get("name"),
                "location_match_method": "exact_coordinates",
                "centroid_assigned_silently": False,
            }

    if name:
        alias = NAME_ALIASES.get(name)
        for zone in zones:
            zid = zone["id"]
            zname = _norm_name(zone.get("name"))
            tokens = [part.strip() for part in zname.split("/") if part.strip()]
            if alias == zid or name == zid.replace("_", " ") or name == zname or name in tokens:
                method = "exact_community_name" if name == zname or name in tokens else "verified_alternative_name"
                return {
                    "location_match_status": "matched",
                    "matched_flood_zone_id": f"zone:{zid}",
                    "matched_flood_zone_name": zone.get("name"),
                    "location_match_method": method,
                    "centroid_assigned_silently": False,
                }

    return {
        "location_match_status": "unmatched",
        "matched_flood_zone_id": None,
        "matched_flood_zone_name": None,
        "location_match_method": "unmatched_no_centroid",
        "centroid_assigned_silently": False,
        "unmatched_reason": (
            "Named place/district was not matched to the 23 catalog flood zones. "
            "District centroid was not assigned."
        ),
    }


def load_acquired_records() -> list[dict]:
    records = json.loads(PUBLIC_ASSESSMENTS.read_text(encoding="utf-8"))
    if NDMA_EXTRACT.exists():
        extra = json.loads(NDMA_EXTRACT.read_text(encoding="utf-8"))
        if extra:
            records = list(records) + list(extra)
    return records


def canonicalize_record(raw: dict, zones: list[dict]) -> dict[str, Any]:
    start = parse_iso_date(raw.get("event_start_date"))
    end = parse_iso_date(raw.get("event_end_date"))
    exclude = bool(raw.get("exclude_from_daily_target"))
    if start is None:
        temporal_grain = "year_or_month" if raw.get("event_year") else "unknown"
        in_daily = False
    else:
        temporal_grain = "day"
        in_daily = not exclude
    match = match_event_location(raw, zones)
    event = {
        "event_id": raw.get("source_record_id"),
        "event_source": raw.get("event_source"),
        "source_url": raw.get("source_url"),
        "source_document": raw.get("source_document"),
        "source_record_id": raw.get("source_record_id"),
        "event_start_date": start.isoformat() if start else None,
        "event_end_date": end.isoformat() if end else None,
        "temporal_grain": temporal_grain,
        "event_location_name": raw.get("event_location_name"),
        "event_location_type": raw.get("event_location_type"),
        "district": raw.get("district"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "location_match_status": match["location_match_status"],
        "matched_flood_zone_id": match.get("matched_flood_zone_id"),
        "matched_flood_zone_name": match.get("matched_flood_zone_name"),
        "location_match_method": match.get("location_match_method"),
        "centroid_assigned_silently": False,
        "observation_status": raw.get("observation_status") or "observed",
        "confidence": raw.get("confidence"),
        "description": raw.get("description"),
        "corroborating_sources": raw.get("corroborating_sources") or [],
        "in_daily_target": in_daily,
        "unmatched_reason": match.get("unmatched_reason"),
        "flood_occurred_created": False,
        "negative_label_created": False,
        "rainfall_threshold_applied": False,
    }
    for field in FORBIDDEN_LABEL_FIELDS:
        event.pop(field, None)
    return event


def detect_duplicates(events: list[dict]) -> list[dict]:
    groups: dict[tuple, list[str]] = defaultdict(list)
    for event in events:
        if not event.get("in_daily_target"):
            continue
        key = (
            event.get("event_start_date"),
            _norm_name(event.get("event_location_name")),
            event.get("event_source"),
        )
        groups[key].append(event["event_id"])
    return [
        {"key": {"date": key[0], "location": key[1], "source": key[2]}, "event_ids": ids}
        for key, ids in groups.items() if len(ids) > 1
    ]


def load_weather_index(path: Optional[Path] = None) -> dict[tuple[str, str], dict]:
    path = path or WEATHER_CSV
    index: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return index
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            loc = row.get("location_id")
            day = row.get("date")
            if loc and day and str(loc).startswith("zone:"):
                index[(loc, day)] = row
    return index


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def join_weather(event: dict, weather: dict[tuple[str, str], dict]) -> dict[str, Any]:
    """Past-only windows from weather history. Event-day rain is context only."""
    start = event.get("event_start_date")
    zone = event.get("matched_flood_zone_id")
    result = {
        "weather_join_status": "not_attempted",
        "rainfall_prev_24h": None,
        "rainfall_prev_72h": None,
        "rainfall_prev_7d": None,
        "rainfall_prev_14d": None,
        "event_day_precipitation_mm": None,
        "event_day_rainfall_24h": None,
        "lead_safe_uses_event_day": False,
        "missing_lead_safe_fields": [],
    }
    if not event.get("in_daily_target") or not start:
        result["weather_join_status"] = "not_daily_event"
        return result
    if event.get("location_match_status") != "matched" or not zone:
        result["weather_join_status"] = "unmatched_location_no_centroid_weather"
        return result
    row = weather.get((zone, start))
    if row is None:
        result["weather_join_status"] = "missing_weather_row"
        return result
    for field in LEAD_SAFE_WEATHER:
        result[field] = _num(row.get(field))
    result["event_day_precipitation_mm"] = _num(row.get("precipitation_mm"))
    result["event_day_rainfall_24h"] = _num(row.get("rainfall_24h"))
    missing = [field for field in LEAD_SAFE_WEATHER if result[field] is None]
    result["missing_lead_safe_fields"] = missing
    result["weather_join_status"] = "complete" if not missing else "incomplete_windows"
    result["lead_safe_uses_event_day"] = False
    return result


def quality_audit(events: list[dict], context: list[dict], duplicates: list[dict]) -> dict[str, Any]:
    daily = [event for event in events if event.get("in_daily_target")]
    dated = [event for event in daily if event.get("temporal_grain") == "day"]
    matched = [event for event in daily if event.get("location_match_status") == "matched"]
    unmatched = [event for event in daily if event.get("location_match_status") == "unmatched"]
    years = sorted({(event.get("event_start_date") or "")[:4] for event in dated if event.get("event_start_date")})
    n_dated = len(dated)
    n_matched = len(matched)
    n_districts = len({event.get("district") for event in dated if event.get("district")})
    n_wet_seasons = len(years)
    enough = (
        n_dated >= PLANNING_MIN_DATED_EVENTS
        and n_wet_seasons >= PLANNING_MIN_WET_SEASONS
        and n_districts >= PLANNING_MIN_DISTRICTS
        and n_matched >= PLANNING_MIN_DATED_EVENTS
    )
    ndma_acquired = False
    if NDMA_EXTRACT.exists():
        ndma_acquired = bool(json.loads(NDMA_EXTRACT.read_text(encoding="utf-8")))
    if enough:
        classification, label = "A", "REAL FLOOD EVENT DATA READY FOR WEATHER JOIN"
    elif n_dated == 0 and not ndma_acquired:
        classification, label = "D", "SOURCE ACCESS BLOCKED"
    elif n_dated > 0 and not enough:
        classification, label = "C", "INSUFFICIENT REAL EVENTS FOR BACKTEST"
    else:
        classification, label = "B", "REAL FLOOD EVENT DATA INCOMPLETE"
    return {
        "n_records_loaded": len(events),
        "n_daily_target_events": len(daily),
        "n_unique_event_ids": len({event["event_id"] for event in daily}),
        "events_by_source": dict(Counter(event.get("event_source") for event in daily)),
        "events_by_year": dict(Counter((event.get("event_start_date") or "")[:4] for event in daily)),
        "events_by_district": dict(Counter(event.get("district") or "unknown" for event in daily)),
        "events_by_flood_zone": dict(Counter(event.get("matched_flood_zone_id") or "unmatched" for event in daily)),
        "n_events_with_exact_dates": n_dated,
        "n_events_year_or_month_only": sum(1 for event in events if not event.get("in_daily_target")),
        "n_catalog_year_only_context": len(context),
        "n_events_with_coordinates": sum(
            1 for event in daily if event.get("latitude") is not None and event.get("longitude") is not None
        ),
        "n_matched_to_catalog": n_matched,
        "n_unmatched": len(unmatched),
        "n_duplicate_groups": len(duplicates),
        "n_with_corroborating_sources": sum(1 for event in daily if event.get("corroborating_sources")),
        "n_unverified_reports": sum(1 for event in daily if event.get("observation_status") == "reported_unverified"),
        "n_events_complete_weather": sum(1 for event in daily if event.get("weather_join_status") == "complete"),
        "n_events_missing_weather_windows": sum(
            1 for event in daily if event.get("weather_join_status") in {
                "missing_weather_row", "incomplete_windows", "unmatched_location_no_centroid_weather",
            }
        ),
        "unmatched_review": [
            {
                "event_id": event["event_id"],
                "event_location_name": event.get("event_location_name"),
                "district": event.get("district"),
                "event_start_date": event.get("event_start_date"),
                "reason": event.get("unmatched_reason"),
            }
            for event in unmatched
        ],
        "duplicates": duplicates,
        "ndma_register_acquired": ndma_acquired,
        "negative_labels_created": False,
        "rainfall_threshold_labels_created": False,
        "flood_occurred_created": False,
        "planning_criteria": {
            "min_dated_events": PLANNING_MIN_DATED_EVENTS,
            "min_wet_seasons": PLANNING_MIN_WET_SEASONS,
            "min_districts": PLANNING_MIN_DISTRICTS,
            "n_dated_events": n_dated,
            "n_wet_seasons_with_dated_events": n_wet_seasons,
            "n_districts_with_dated_events": n_districts,
            "n_catalog_matched_dated_events": n_matched,
            "met": enough,
        },
        "classification": classification,
        "classification_label": label,
        "disclaimer": "Historical weather data does not constitute historical flood-event ground truth.",
    }


def build_registry(*, weather: Optional[dict] = None) -> dict[str, Any]:
    zones = load_flood_zones()
    events = [canonicalize_record(item, zones) for item in load_acquired_records()]
    weather_index = weather if weather is not None else load_weather_index()
    for event in events:
        joined = join_weather(event, weather_index)
        event.update(joined)
        event["lead_time_eligible"] = bool(
            event.get("in_daily_target")
            and event.get("location_match_status") == "matched"
            and joined.get("weather_join_status") in {"complete", "incomplete_windows"}
        )
    context = historical_context_from_catalog(zones)
    duplicates = detect_duplicates(events)
    audit = quality_audit(events, context, duplicates)
    return {
        "version": "chews_flood_event_v0",
        "generated_at": _now(),
        "disclaimer": "Historical weather data does not constitute historical flood-event ground truth.",
        "model_trained": False,
        "integrated_into_chews": False,
        "flood_occurred_created": False,
        "negative_labels_created": False,
        "rainfall_threshold_applied": False,
        "events": [event for event in events if event.get("in_daily_target")],
        "held_out_without_calendar_day": [event for event in events if not event.get("in_daily_target")],
        "historical_context_year_only": context,
        "audit": audit,
    }


def write_event_csv(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for event in events:
            row = {key: event.get(key) for key in EVENT_FIELDS}
            if isinstance(row.get("corroborating_sources"), list):
                row["corroborating_sources"] = json.dumps(row["corroborating_sources"])
            writer.writerow(row)

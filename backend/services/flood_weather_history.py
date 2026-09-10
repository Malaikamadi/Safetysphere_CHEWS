"""
CHEWS Historical Flood Weather Dataset v1 — isolated weather foundation.

Does NOT create flood_occurred or any rainfall-derived flood label.
Does NOT train a model.
Does NOT modify weather_api.py, flood_dashboard.py, flood_risk.py,
malaria climate extracts, or live CHEWS paths.
Missing precipitation stays missing. Zero means no rain, not no observation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

BACKEND = Path(__file__).resolve().parent.parent
FLOOD_ZONES = BACKEND / "data" / "reference" / "flood_zones.json"
ADMIN_HIERARCHY = BACKEND / "data" / "reference" / "admin_hierarchy.csv"
MALARIA_CLIMATE = BACKEND / "data" / "03_curated" / "climate" / "climate_district_month_latest.json"

DATASET_VERSION = "flood_weather_history_v1"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "Africa/Abidjan"
PERIOD_START = date(2015, 1, 1)
PERIOD_END = date(2026, 8, 31)
MIN_PRIOR_YEARS_BASELINE = 3
WET_SEASON_MONTHS = frozenset({5, 6, 7, 8, 9, 10})
SL_LAT = (6.9, 10.1)
SL_LON = (-13.6, -10.2)

DAILY_VARIABLES = (
    "precipitation_sum",
    "rain_sum",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "soil_moisture_0_to_7cm_mean",
    "wind_speed_10m_mean",
)

UNAVAILABLE_REQUESTED = (
    "soil_moisture_0_to_10cm_mean",  # Open-Meteo returned unit=undefined
)

PROTECTED_PATHS = {
    "flood_risk_py": BACKEND / "models" / "flood_risk.py",
    "flood_dashboard_py": BACKEND / "services" / "flood_dashboard.py",
    "weather_api_py": BACKEND / "services" / "weather_api.py",
    "flood_model_joblib": BACKEND / "data" / "trained_models" / "flood_model.joblib",
    "malaria_climate": MALARIA_CLIMATE,
    "flood_validation_report": BACKEND / "data" / "04_ai" / "diagnostics" / "flood_validation_report.json",
    "flood_foundation": BACKEND / "data" / "04_ai" / "diagnostics" / "flood_data_foundation.json",
}

FORBIDDEN_LABEL_FIELDS = (
    "flood_occurred",
    "flood_event",
    "is_flood",
    "flood_label",
    "flood_predicted",
)


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


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def daterange(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def validate_coordinates(lat: Optional[float], lon: Optional[float]) -> dict[str, Any]:
    if lat is None or lon is None:
        return {"ok": False, "reason": "missing_coordinates"}
    if not (SL_LAT[0] <= lat <= SL_LAT[1] and SL_LON[0] <= lon <= SL_LON[1]):
        return {"ok": False, "reason": "outside_sierra_leone_bbox"}
    return {"ok": True, "reason": None}


def load_canonical_locations() -> list[dict[str, Any]]:
    locations = []
    zones = json.loads(FLOOD_ZONES.read_text(encoding="utf-8"))
    for zone in zones:
        lat = _num(zone.get("lat"))
        lon = _num(zone.get("lng"))
        check = validate_coordinates(lat, lon)
        locations.append({
            "location_id": f"zone:{zone['id']}",
            "location_name": zone.get("name"),
            "location_type": "flood_zone",
            "district": zone.get("district"),
            "latitude": lat,
            "longitude": lon,
            "source": "reference/flood_zones.json",
            "coordinate_quality": "catalog_point" if check["ok"] else "invalid",
            "coordinate_ok": check["ok"],
            "coordinate_issue": check["reason"],
            "represents_all_flood_prone_communities": False,
        })
    with ADMIN_HIERARCHY.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            lat = _num(row.get("centroid_lat"))
            lon = _num(row.get("centroid_lng"))
            check = validate_coordinates(lat, lon)
            locations.append({
                "location_id": f"district_centroid:{row['district_id']}",
                "location_name": row.get("district_name"),
                "location_type": "district_centroid",
                "district": row.get("district_id"),
                "latitude": lat,
                "longitude": lon,
                "source": "reference/admin_hierarchy.csv",
                "coordinate_quality": "admin_centroid_fallback" if check["ok"] else "invalid",
                "coordinate_ok": check["ok"],
                "coordinate_issue": check["reason"],
                "represents_all_flood_prone_communities": False,
            })
    return locations


def rolling_sum(
    values: list[Optional[float]],
    end_index: int,
    window: int,
    *,
    include_end: bool,
) -> Optional[float]:
    """Sum `window` daily values. Missing any day → None (not zero-filled)."""
    if window < 1 or end_index < 0:
        return None
    last = end_index if include_end else end_index - 1
    first = last - window + 1
    if first < 0 or last < 0 or last >= len(values):
        return None
    total = 0.0
    for i in range(first, last + 1):
        value = values[i]
        if value is None:
            return None
        total += value
    return total


def attach_rainfall_features(rows: list[dict]) -> None:
    """In-place contemporaneous and lead-safe rainfall features. No future days."""
    by_loc: dict[str, list[dict]] = {}
    for row in rows:
        by_loc.setdefault(row["location_id"], []).append(row)
    for group in by_loc.values():
        group.sort(key=lambda r: r["date"])
        precip = [r.get("precipitation_mm") for r in group]
        for i, row in enumerate(group):
            row["rainfall_24h"] = rolling_sum(precip, i, 1, include_end=True)
            row["rainfall_72h"] = rolling_sum(precip, i, 3, include_end=True)
            row["rainfall_7d"] = rolling_sum(precip, i, 7, include_end=True)
            row["rainfall_14d"] = rolling_sum(precip, i, 14, include_end=True)
            row["rainfall_prev_24h"] = rolling_sum(precip, i, 1, include_end=False)
            row["rainfall_prev_72h"] = rolling_sum(precip, i, 3, include_end=False)
            row["rainfall_prev_7d"] = rolling_sum(precip, i, 7, include_end=False)
            row["rainfall_prev_14d"] = rolling_sum(precip, i, 14, include_end=False)


def attach_baselines_efficient(rows: list[dict]) -> None:
    """Same rules as attach_baselines, without O(n²) year counting."""
    by_loc_month: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        row["_year"] = day.year
        row["_month"] = day.month
        by_loc_month.setdefault((row["location_id"], day.month), []).append(row)

    for group in by_loc_month.values():
        group.sort(key=lambda r: r["date"])
        all_precip = [r.get("precipitation_mm") for r in group if r.get("precipitation_mm") is not None]
        descriptive = statistics.median(all_precip) if all_precip else None
        prior: list[float] = []
        years_seen: set[int] = set()
        current_year = None
        year_start_prior: dict[int, tuple[list[float], int]] = {}
        for row in group:
            year = row["_year"]
            if year != current_year:
                if current_year is not None:
                    pass
                year_start_prior[year] = (list(prior), len(years_seen))
                current_year = year
            row["rainfall_historical_median_descriptive"] = descriptive
            cached_prior, n_years = year_start_prior[year]
            if n_years < MIN_PRIOR_YEARS_BASELINE or not cached_prior:
                row["rainfall_historical_median_past_only"] = None
                row["rainfall_historical_percentile_past_only"] = None
                row["rainfall_anomaly_past_only"] = None
                row["baseline_prior_years"] = n_years
            else:
                median = statistics.median(cached_prior)
                current = row.get("precipitation_mm")
                row["rainfall_historical_median_past_only"] = median
                row["rainfall_anomaly_past_only"] = None if current is None else current - median
                if current is None:
                    row["rainfall_historical_percentile_past_only"] = None
                else:
                    below = sum(1 for v in cached_prior if v <= current)
                    row["rainfall_historical_percentile_past_only"] = below / len(cached_prior)
                row["baseline_prior_years"] = n_years
            value = row.get("precipitation_mm")
            if value is not None:
                prior.append(value)
                years_seen.add(year)
        for row in group:
            row.pop("_year", None)
            row.pop("_month", None)


def fetch_archive_daily(
    lat: float,
    lon: float,
    start: date,
    end: date,
    *,
    opener: Optional[Callable[[str], dict]] = None,
    timeout: int = 60,
) -> dict[str, Any]:
    query = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
    }
    url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(query)}"
    retrieved_at = _now()
    if opener:
        payload = opener(url)
        status = 200
    else:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "CHEWS-Flood-Weather-History/1.0",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo Archive JSON root must be an object")
    payload["_chews_request"] = {
        "url_without_secrets": f"{ARCHIVE_URL}?latitude={lat:.4f}&longitude={lon:.4f}&start_date={start}&end_date={end}",
        "http_status": status,
        "retrieved_at": retrieved_at,
        "variables_requested": list(DAILY_VARIABLES),
    }
    return payload


def payload_to_daily_rows(location: dict, payload: dict, start: date, end: date) -> list[dict]:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    by_date = {}
    for i, raw in enumerate(times):
        by_date[raw] = {
            "precipitation_mm": _num((daily.get("precipitation_sum") or [None] * len(times))[i] if i < len(daily.get("precipitation_sum") or []) else None),
            "rain_mm": _num((daily.get("rain_sum") or [None] * len(times))[i] if i < len(daily.get("rain_sum") or []) else None),
            "temperature_mean_c": _num((daily.get("temperature_2m_mean") or [None] * len(times))[i] if i < len(daily.get("temperature_2m_mean") or []) else None),
            "temperature_min_c": _num((daily.get("temperature_2m_min") or [None] * len(times))[i] if i < len(daily.get("temperature_2m_min") or []) else None),
            "temperature_max_c": _num((daily.get("temperature_2m_max") or [None] * len(times))[i] if i < len(daily.get("temperature_2m_max") or []) else None),
            "relative_humidity": _num((daily.get("relative_humidity_2m_mean") or [None] * len(times))[i] if i < len(daily.get("relative_humidity_2m_mean") or []) else None),
            "soil_moisture": _num((daily.get("soil_moisture_0_to_7cm_mean") or [None] * len(times))[i] if i < len(daily.get("soil_moisture_0_to_7cm_mean") or []) else None),
            "wind_speed_10m": _num((daily.get("wind_speed_10m_mean") or [None] * len(times))[i] if i < len(daily.get("wind_speed_10m_mean") or []) else None),
        }
    rows = []
    for day in daterange(start, end):
        observed = by_date.get(day.isoformat())
        rec = {
            "location_id": location["location_id"],
            "location_name": location["location_name"],
            "location_type": location["location_type"],
            "district": location["district"],
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "date": day.isoformat(),
            "calendar_month": day.month,
            "day_of_year": day.timetuple().tm_yday,
            "wet_season_indicator": day.month in WET_SEASON_MONTHS,
            "observation_present": observed is not None,
        }
        for field in (
            "precipitation_mm", "rain_mm", "temperature_mean_c", "temperature_min_c",
            "temperature_max_c", "relative_humidity", "soil_moisture", "wind_speed_10m",
        ):
            rec[field] = None if observed is None else observed.get(field)
        rows.append(rec)
    return rows


def quality_audit(rows: list[dict], locations: list[dict], start: date, end: date) -> dict[str, Any]:
    expected = len(locations) * len(daterange(start, end))
    keys = [(r["location_id"], r["date"]) for r in rows]
    dups = len(keys) - len(set(keys))
    precip = [r.get("precipitation_mm") for r in rows]
    missing_dates = sum(1 for r in rows if not r.get("observation_present"))
    neg_precip = sum(1 for v in precip if v is not None and v < 0)
    wet = [r for r in rows if r.get("wet_season_indicator")]
    dry = [r for r in rows if not r.get("wet_season_indicator")]

    def miss(field: str) -> int:
        return sum(1 for r in rows if r.get(field) is None)

    gaps_by_location = {}
    for loc in locations:
        loc_rows = [r for r in rows if r["location_id"] == loc["location_id"]]
        gaps_by_location[loc["location_id"]] = sum(1 for r in loc_rows if r.get("precipitation_mm") is None)

    outliers = {
        "precip_gt_400mm": sum(1 for v in precip if v is not None and v > 400),
        "temp_mean_lt_10_or_gt_45": sum(
            1 for r in rows
            if r.get("temperature_mean_c") is not None
            and (r["temperature_mean_c"] < 10 or r["temperature_mean_c"] > 45)
        ),
        "humidity_outside_0_100": sum(
            1 for r in rows
            if r.get("relative_humidity") is not None
            and not (0 <= r["relative_humidity"] <= 100)
        ),
        "soil_moisture_outside_0_1": sum(
            1 for r in rows
            if r.get("soil_moisture") is not None
            and not (0 <= r["soil_moisture"] <= 1)
        ),
    }
    return {
        "n_rows": len(rows),
        "n_expected": expected,
        "n_missing_calendar_days": missing_dates,
        "n_duplicate_location_dates": dups,
        "missing_precipitation": miss("precipitation_mm"),
        "missing_temperature_mean": miss("temperature_mean_c"),
        "missing_humidity": miss("relative_humidity"),
        "missing_soil_moisture": miss("soil_moisture"),
        "negative_precipitation": neg_precip,
        "wet_season_rows": len(wet),
        "dry_season_rows": len(dry),
        "wet_season_precip_missing": sum(1 for r in wet if r.get("precipitation_mm") is None),
        "dry_season_precip_missing": sum(1 for r in dry if r.get("precipitation_mm") is None),
        "gaps_by_location": gaps_by_location,
        "outliers": outliers,
        "forbidden_label_fields_present": [f for f in FORBIDDEN_LABEL_FIELDS if any(f in r for r in rows)],
        "missing_not_replaced_with_zero": True,
    }


def compare_malaria_climate(rows: list[dict]) -> dict[str, Any]:
    if not MALARIA_CLIMATE.exists():
        return {"compared": False, "reason": "malaria_climate_district_month_latest_missing"}
    malaria = json.loads(MALARIA_CLIMATE.read_text(encoding="utf-8"))
    monthly: dict[tuple[str, str], dict] = {}
    for row in rows:
        if row.get("location_type") != "district_centroid":
            continue
        if row.get("precipitation_mm") is None and row.get("temperature_mean_c") is None:
            continue
        period = row["date"][:4] + row["date"][5:7]
        key = (row["district"], period)
        slot = monthly.setdefault(key, {"precip": [], "temp": [], "hum": [], "lat": row["latitude"], "lon": row["longitude"]})
        if row.get("precipitation_mm") is not None:
            slot["precip"].append(row["precipitation_mm"])
        if row.get("temperature_mean_c") is not None:
            slot["temp"].append(row["temperature_mean_c"])
        if row.get("relative_humidity") is not None:
            slot["hum"].append(row["relative_humidity"])

    rain_pairs = []
    temp_pairs = []
    coord_notes = []
    for item in malaria:
        key = (item.get("district_slug"), item.get("source_period") or item.get("period"))
        slot = monthly.get(key)
        if not slot:
            continue
        if item.get("rainfall_mm") is not None and slot["precip"]:
            rain_pairs.append((float(item["rainfall_mm"]), sum(slot["precip"])))
        if item.get("temperature_c") is not None and slot["temp"]:
            temp_pairs.append((float(item["temperature_c"]), sum(slot["temp"]) / len(slot["temp"])))
        mlat, mlon = _num(item.get("latitude")), _num(item.get("longitude"))
        if mlat is not None and slot["lat"] is not None:
            if abs(mlat - slot["lat"]) > 0.01 or abs((mlon or 0) - (slot["lon"] or 0)) > 0.01:
                coord_notes.append(key[0])

    def mae(pairs):
        if not pairs:
            return None
        return sum(abs(a - b) for a, b in pairs) / len(pairs)

    return {
        "compared": True,
        "malaria_source": str(MALARIA_CLIMATE.relative_to(BACKEND)),
        "malaria_not_overwritten": True,
        "n_overlapping_district_months": len(rain_pairs),
        "rainfall_mae_mm_month": None if not rain_pairs else round(mae(rain_pairs), 3),
        "temperature_mae_c": None if not temp_pairs else round(mae(temp_pairs), 3),
        "units": {"this_dataset_daily_precip": "mm", "malaria_monthly_rainfall": "mm (daily sum)"},
        "coordinate_note": (
            "Malaria climate uses district centroids. Flood-zone rows use catalog lat/lng "
            "and are not expected to match centroid monthly totals. Comparison uses "
            "district_centroid rows only."
        ),
        "districts_with_coord_mismatch": sorted(set(coord_notes)),
    }


def lead_safe_for_event_date(row: dict) -> dict[str, Any]:
    """Weather allowed for a flood event on this row's date T: previous windows only."""
    return {
        "event_date": row["date"],
        "usable_for_lead_time": {
            "rainfall_prev_24h": row.get("rainfall_prev_24h"),
            "rainfall_prev_72h": row.get("rainfall_prev_72h"),
            "rainfall_prev_7d": row.get("rainfall_prev_7d"),
            "rainfall_prev_14d": row.get("rainfall_prev_14d"),
        },
        "contemporaneous_context_not_lead_time": {
            "rainfall_24h": row.get("rainfall_24h"),
            "precipitation_mm": row.get("precipitation_mm"),
        },
        "forbidden_for_lead_time": "any precipitation on T or after T",
    }


def build_dataset(
    *,
    start: date = PERIOD_START,
    end: date = PERIOD_END,
    opener: Optional[Callable[[str], dict]] = None,
    sleep_seconds: float = 0.25,
    locations: Optional[list[dict]] = None,
) -> dict[str, Any]:
    locations = locations or load_canonical_locations()
    fetchable = [loc for loc in locations if loc.get("coordinate_ok")]
    rows: list[dict] = []
    extracts = []
    for i, loc in enumerate(fetchable):
        payload = fetch_archive_daily(loc["latitude"], loc["longitude"], start, end, opener=opener)
        daily_keys = list((payload.get("daily") or {}).keys())
        extracts.append({
            "location_id": loc["location_id"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "returned_dates": {
                "first": ((payload.get("daily") or {}).get("time") or [None])[0],
                "last": ((payload.get("daily") or {}).get("time") or [None])[-1],
                "n": len((payload.get("daily") or {}).get("time") or []),
            },
            "daily_variables_returned": [k for k in daily_keys if k != "time"],
            "daily_units": payload.get("daily_units"),
            "timezone": payload.get("timezone"),
            "elevation_m": payload.get("elevation"),
            "http_status": (payload.get("_chews_request") or {}).get("http_status"),
            "retrieved_at": (payload.get("_chews_request") or {}).get("retrieved_at"),
            "api": ARCHIVE_URL,
            "provider": "Open-Meteo Archive",
            "model_note": "Open-Meteo Archive historical reanalysis (ERA5-family as served by the API)",
        })
        rows.extend(payload_to_daily_rows(loc, payload, start, end))
        if opener is None and i < len(fetchable) - 1:
            time.sleep(sleep_seconds)

    attach_rainfall_features(rows)
    attach_baselines_efficient(rows)
    quality = quality_audit(rows, fetchable, start, end)
    comparison = compare_malaria_climate(rows)
    generated_at = _now()
    return {
        "version": DATASET_VERSION,
        "generated_at": generated_at,
        "flood_labels_created": False,
        "model_trained": False,
        "locations": locations,
        "rows": rows,
        "extracts": extracts,
        "quality": quality,
        "malaria_climate_comparison": comparison,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "disclaimer": (
            "Historical weather data does not constitute historical flood-event ground truth."
        ),
    }


ROW_FIELDS = [
    "location_id", "location_name", "location_type", "district",
    "latitude", "longitude", "date",
    "precipitation_mm", "rain_mm",
    "temperature_mean_c", "temperature_min_c", "temperature_max_c",
    "relative_humidity", "soil_moisture", "wind_speed_10m",
    "rainfall_24h", "rainfall_72h", "rainfall_7d", "rainfall_14d",
    "rainfall_prev_24h", "rainfall_prev_72h", "rainfall_prev_7d", "rainfall_prev_14d",
    "calendar_month", "day_of_year", "wet_season_indicator",
    "rainfall_historical_median_descriptive",
    "rainfall_historical_median_past_only",
    "rainfall_historical_percentile_past_only",
    "rainfall_anomaly_past_only",
    "baseline_prior_years",
    "observation_present",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in ROW_FIELDS})


def build_manifest(payload: dict) -> dict[str, Any]:
    quality = payload["quality"]
    return {
        "dataset_version": DATASET_VERSION,
        "generated_at": payload["generated_at"],
        "source": "Open-Meteo Archive",
        "api": ARCHIVE_URL,
        "model_dataset": "Open-Meteo Archive historical daily (ERA5-family as served)",
        "timezone": TIMEZONE,
        "units": {
            "precipitation_mm": "mm/day",
            "rain_mm": "mm/day",
            "temperature_*_c": "°C",
            "relative_humidity": "%",
            "soil_moisture": "m³/m³ (0–7 cm)",
            "wind_speed_10m": "km/h",
        },
        "period": payload["period"],
        "locations": [
            {k: loc[k] for k in (
                "location_id", "location_name", "location_type", "district",
                "latitude", "longitude", "source", "coordinate_quality",
            )}
            for loc in payload["locations"]
        ],
        "n_locations": len(payload["locations"]),
        "n_flood_zones": sum(1 for loc in payload["locations"] if loc["location_type"] == "flood_zone"),
        "n_district_centroids": sum(1 for loc in payload["locations"] if loc["location_type"] == "district_centroid"),
        "n_rows": quality["n_rows"],
        "variables_requested": list(DAILY_VARIABLES),
        "variables_unavailable": list(UNAVAILABLE_REQUESTED),
        "extracts": payload["extracts"],
        "missingness": {
            "precipitation": quality["missing_precipitation"],
            "temperature_mean": quality["missing_temperature_mean"],
            "humidity": quality["missing_humidity"],
            "soil_moisture": quality["missing_soil_moisture"],
            "calendar_days_without_api_row": quality["n_missing_calendar_days"],
        },
        "transformations": {
            "rainfall_24h": "precipitation on date D (includes D)",
            "rainfall_72h": "sum of D, D-1, D-2; missing any day → null",
            "rainfall_7d": "sum of D through D-6; missing any day → null",
            "rainfall_14d": "sum of D through D-13; missing any day → null",
            "rainfall_prev_24h": "precipitation on D-1 (excludes D)",
            "rainfall_prev_72h": "sum of D-1, D-2, D-3 (excludes D)",
            "rainfall_prev_7d": "sum of D-1 through D-7 (excludes D)",
            "rainfall_prev_14d": "sum of D-1 through D-14 (excludes D)",
            "missing_precip_not_zero_filled": True,
            "flood_occurred_not_created": True,
        },
        "baselines": {
            "descriptive_median": (
                "Median of all daily precip for location × calendar month in this extract. "
                "Uses later years. Descriptive only — not leakage-safe for backtesting an event in-sample."
            ),
            "past_only_median": (
                f"Median of daily precip for the same location × calendar month in years strictly "
                f"before the row year; requires ≥{MIN_PRIOR_YEARS_BASELINE} prior years."
            ),
            "past_only_percentile": "Share of prior same-month daily values ≤ current day's precip",
            "past_only_anomaly": "current precip − past-only median",
        },
        "quality": quality,
        "malaria_climate_comparison": payload["malaria_climate_comparison"],
        "flood_event_join": {
            "target_table": "chews_flood_event_v0 (not yet populated)",
            "join": "event location → weather location_id; event_start T → weather date T",
            "lead_time_features": [
                "rainfall_prev_24h", "rainfall_prev_72h", "rainfall_prev_7d", "rainfall_prev_14d",
            ],
            "do_not_use_for_lead_time": ["precipitation_mm", "rainfall_24h", "any day > T"],
        },
        "limitations": [
            "23 flood zones do not represent all flood-prone communities in Sierra Leone.",
            "District centroids are fallback geography, not catchment pour points.",
            "Weather is not flood ground truth.",
            "Archive reanalysis is not a rain-gauge observation.",
            "soil_moisture_0_to_10cm was requested in a probe but returned undefined units and was dropped.",
        ],
        "disclaimer": payload["disclaimer"],
        "flood_labels_created": False,
        "model_trained": False,
        "integrated_into_chews": False,
    }

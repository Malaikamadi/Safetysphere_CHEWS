"""
Historical climate from the Open-Meteo Archive API.

This module does not replace services/weather_api.py (realtime flood precipitation).
Archive daily series are aggregated to district + YYYYMM for join with DHIS2.

Mock mode reads a monthly fixture — it is not ERA5 and must not be labelled live.
"""

from __future__ import annotations

import csv
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from config import climate_archive as clim_cfg
from config import dhis2 as dhis2_cfg
from services.dhis2_periods import historical_window, yyyymm_to_date_bounds
from services.district_names import display_name, district_slug

logger = logging.getLogger("chews.climate.archive")

_cache: dict[str, Any] = {"climate": None}


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def load_district_centroids() -> list[dict]:
    path = dhis2_cfg.DATA_DIR / "reference" / "admin_hierarchy.csv"
    rows = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            name = raw.get("district_name")
            slug = district_slug(name)
            try:
                lat = float(raw["centroid_lat"])
                lon = float(raw["centroid_lng"])
            except (TypeError, ValueError, KeyError):
                continue
            rows.append({
                "district_id": raw.get("district_id") or slug,
                "district_slug": slug,
                "district_name": name,
                "latitude": lat,
                "longitude": lon,
            })
    return rows


def month_from_iso_date(iso_date: str) -> Optional[str]:
    text = (iso_date or "").strip()
    if len(text) >= 7 and text[4] == "-":
        yyyy, mm = text[:4], text[5:7]
        if yyyy.isdigit() and mm.isdigit():
            return f"{yyyy}{mm}"
    return None


def aggregate_daily_to_monthly(
    *,
    dates: list,
    precipitation: list,
    temperature: list,
    humidity: list,
) -> dict[str, dict]:
    buckets: dict[str, dict] = {}
    for i in range(len(dates)):
        period = month_from_iso_date(str(dates[i]))
        if not period:
            continue
        slot = buckets.setdefault(period, {
            "source_period": period,
            "precip_sum": 0.0,
            "precip_n": 0,
            "temp_sum": 0.0,
            "temp_n": 0,
            "humidity_sum": 0.0,
            "humidity_n": 0,
        })
        precip = _num(precipitation[i] if i < len(precipitation) else None)
        temp = _num(temperature[i] if i < len(temperature) else None)
        humid = _num(humidity[i] if i < len(humidity) else None)
        if precip is not None:
            slot["precip_sum"] += precip
            slot["precip_n"] += 1
        if temp is not None:
            slot["temp_sum"] += temp
            slot["temp_n"] += 1
        if humid is not None:
            slot["humidity_sum"] += humid
            slot["humidity_n"] += 1
    monthly = {}
    for period, slot in buckets.items():
        monthly[period] = {
            "source_period": period,
            "period": period,
            "period_type": "monthly",
            "rainfall_mm": slot["precip_sum"] if slot["precip_n"] else None,
            "temperature_c": (slot["temp_sum"] / slot["temp_n"]) if slot["temp_n"] else None,
            "humidity_percent": (slot["humidity_sum"] / slot["humidity_n"]) if slot["humidity_n"] else None,
            "days_with_precip": slot["precip_n"],
            "days_with_temp": slot["temp_n"],
            "days_with_humidity": slot["humidity_n"],
        }
    return monthly


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def fetch_archive_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    *,
    opener: Optional[Callable[[str], dict]] = None,
) -> dict:
    query = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(clim_cfg.DAILY_VARIABLES),
        "timezone": clim_cfg.TIMEZONE,
    }
    url = f"{clim_cfg.ARCHIVE_BASE_URL}?{urllib.parse.urlencode(query)}"
    if opener:
        return opener(url)
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "CHEWS-Climate-Archive/1.0",
    })
    timeout = max(1, clim_cfg.CLIMATE_ARCHIVE_TIMEOUT_SECONDS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo Archive JSON root must be an object")
    return payload


def _load_mock_monthly() -> list[dict]:
    path = clim_cfg.mock_fixture_path()
    if not path.exists():
        raise FileNotFoundError(f"Climate archive mock fixture missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Climate mock fixture must contain a rows list")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = district_slug(row.get("district_slug") or row.get("district_name") or row.get("district"))
        out.append({
            "source_period": row.get("source_period") or row.get("period"),
            "period": row.get("source_period") or row.get("period"),
            "period_type": "monthly",
            "district_slug": slug,
            "district_id": row.get("district_id") or slug,
            "district_name": display_name(slug, row.get("district_name")),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "rainfall_mm": _num(row.get("rainfall_mm")),
            "temperature_c": _num(row.get("temperature_c")),
            "humidity_percent": _num(row.get("humidity_percent")),
            "source": "open_meteo_archive_mock",
        })
    return out


def ingest_historical_climate(
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    months: Optional[int] = None,
    mock: Optional[bool] = None,
    persist: bool = True,
    opener: Optional[Callable[[str], dict]] = None,
) -> dict:
    start_m, end_m, month_list = historical_window(
        start=start or dhis2_cfg.DHIS2_HISTORICAL_START,
        end=end or dhis2_cfg.DHIS2_HISTORICAL_END,
        months=months or dhis2_cfg.DHIS2_HISTORICAL_MONTHS,
    )
    use_mock = clim_cfg.CLIMATE_ARCHIVE_MOCK if mock is None else mock
    start_date, end_date = yyyymm_to_date_bounds(start_m, end_m)

    if use_mock:
        district_month = _load_mock_monthly()
        raw_by_district = {"mock": {"note": "fixture; not Open-Meteo Archive"}}
        source = "open_meteo_archive_mock"
    else:
        centroids = load_district_centroids()
        district_month = []
        raw_by_district = {}
        for i, district in enumerate(centroids):
            payload = fetch_archive_daily(
                district["latitude"],
                district["longitude"],
                start_date,
                end_date,
                opener=opener,
            )
            raw_by_district[district["district_slug"]] = payload
            daily = payload.get("daily") or {}
            monthly = aggregate_daily_to_monthly(
                dates=daily.get("time") or [],
                precipitation=daily.get("precipitation_sum") or [],
                temperature=daily.get("temperature_2m_mean") or [],
                humidity=daily.get("relative_humidity_2m_mean") or [],
            )
            for period, values in monthly.items():
                if period not in month_list:
                    continue
                district_month.append({
                    **values,
                    "district_slug": district["district_slug"],
                    "district_id": district["district_id"],
                    "district_name": district["district_name"],
                    "latitude": district["latitude"],
                    "longitude": district["longitude"],
                    "source": "open_meteo_archive",
                })
            if i + 1 < len(centroids) and clim_cfg.CLIMATE_ARCHIVE_SLEEP_SECONDS > 0:
                time.sleep(clim_cfg.CLIMATE_ARCHIVE_SLEEP_SECONDS)
        district_month.sort(key=lambda r: (r.get("source_period") or "", r.get("district_slug") or ""))
        source = "open_meteo_archive"

    observed_months = sorted({r.get("source_period") for r in district_month if r.get("source_period")})
    result = {
        "source": source,
        "mock": use_mock,
        "period_start": start_m,
        "period_end": end_m,
        "start_date": start_date,
        "end_date": end_date,
        "requested_months": month_list,
        "observed_months": observed_months,
        "district_month": district_month,
        "district_count": len({r.get("district_slug") for r in district_month}),
        "row_count": len(district_month),
        "realtime_weather_untouched": True,
        "note": "Not used by weather_api.fetch_realtime_weather (flood atlas).",
    }

    if persist:
        if not use_mock:
            _write_json(
                clim_cfg.RAW_CLIMATE_ARCHIVE_DIR / f"open_meteo_archive_{start_m}_{end_m}.json",
                raw_by_district,
            )
        _write_json(clim_cfg.CURATED_CLIMATE_DIR / "climate_district_month_latest.json", district_month)
        result["paths"] = {
            "curated": str(clim_cfg.CURATED_CLIMATE_DIR / "climate_district_month_latest.json"),
        }

    _cache["climate"] = result
    return result


def cached_climate() -> Optional[dict]:
    return _cache.get("climate")


def load_latest_climate() -> Optional[list[dict]]:
    path = clim_cfg.CURATED_CLIMATE_DIR / "climate_district_month_latest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    cached = cached_climate()
    if cached:
        return cached.get("district_month")
    return None

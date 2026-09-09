"""
Expand DHIS2 malaria history before 202307 into a separate dataset.

Does NOT overwrite malaria_district_month_panel_latest.json.
Does NOT regenerate malaria_forecast_v1 or malaria_positivity_forecast_v1.
Does NOT train a model.
Does NOT persist into dhis2_malaria_district_month_latest.json.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.climate_archive import (  # noqa: E402
    aggregate_daily_to_monthly,
    fetch_archive_daily,
    load_district_centroids,
)
from services.dhis2_historical import extract_historical  # noqa: E402
from services.dhis2_periods import expand_monthly_range, yyyymm_to_date_bounds  # noqa: E402
from services.dhis2_service import Dhis2Client  # noqa: E402
from services.training_panel import join_district_month  # noqa: E402

EXPANSION_START = "201104"
EXPANSION_END = "202306"
COMPARABLE_START = "202106"
V1_PANEL = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_district_month_panel_latest.json"
OUT_PATH = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion.json"
REPORT_PATH = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion_report.json"
CHUNK_DIR = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion_chunks"
COUNT_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1" / "model.joblib"
POS_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_positivity_forecast_v1" / "model.joblib"
GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
COUNT_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
POS_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_positivity_forecast_v1.json"

KNOWN_ADMIN = {
    "western_area_urban", "western_area_rural", "bo", "pujehun", "bonthe",
    "kenema", "port_loko", "kambia", "tonkolili", "moyamba", "bombali",
    "kailahun", "kono", "koinadugu", "falaba", "karene",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _year_chunks(start: str, end: str) -> list[tuple[str, str]]:
    months = expand_monthly_range(start, end)
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    for m in months:
        if not current:
            current = [m]
            continue
        if m[:4] != current[0][:4]:
            chunks.append((current[0], current[-1]))
            current = [m]
        else:
            current.append(m)
    if current:
        chunks.append((current[0], current[-1]))
    return chunks


def fetch_climate_with_retry(start: str, end: str) -> list[dict]:
    start_date, end_date = yyyymm_to_date_bounds(start, end)
    month_list = set(expand_monthly_range(start, end))
    rows: list[dict] = []
    for i, district in enumerate(load_district_centroids()):
        payload = None
        last_exc: Exception | None = None
        for attempt in range(1, 8):
            try:
                payload = fetch_archive_daily(
                    district["latitude"],
                    district["longitude"],
                    start_date,
                    end_date,
                )
                break
            except urllib.error.HTTPError as exc:
                last_exc = exc
                wait = 15 * attempt
                print(
                    f"climate 429/HTTP {exc.code} {district['district_slug']} "
                    f"attempt {attempt}, sleep {wait}s",
                    flush=True,
                )
                time.sleep(wait)
        if payload is None:
            raise RuntimeError(f"climate fetch failed for {district['district_slug']}: {last_exc}")
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
            rows.append({
                **values,
                "district_slug": district["district_slug"],
                "district_id": district["district_id"],
                "district_name": district["district_name"],
                "latitude": district["latitude"],
                "longitude": district["longitude"],
                "source": "open_meteo_archive",
            })
        if i + 1 < 16:
            time.sleep(3.0)
    rows.sort(key=lambda r: (r.get("source_period") or "", r.get("district_slug") or ""))
    return rows


def n_prior_histogram(rows: list[dict], as_of: str | None = None) -> dict:
    by_key: dict[tuple[str, int], list[str]] = defaultdict(list)
    periods = []
    for r in rows:
        slug = r.get("district_slug")
        period = r.get("source_period") or r.get("period")
        if not slug or not period or slug not in KNOWN_ADMIN:
            continue
        if r.get("malaria_confirmed") is None:
            continue
        by_key[(slug, int(period[4:6]))].append(period[:4])
        periods.append(period)
    if not periods:
        return {"as_of": as_of, "keys": 0}
    as_of = as_of or max(periods)
    as_of_year = int(as_of[:4])
    as_of_month = int(as_of[4:6])
    counts = {0: 0, 1: 0, 2: 0, 3: 0, "ge4": 0}
    details = []
    for (slug, month), years in sorted(by_key.items()):
        uniq = sorted(set(int(y) for y in years))
        cutoff_year = as_of_year if month <= as_of_month else as_of_year - 1
        prior = [y for y in uniq if y < cutoff_year]
        n = len(prior)
        if n >= 4:
            counts["ge4"] += 1
        elif n in counts:
            counts[n] += 1
        details.append({"district": slug, "calendar_month": month, "n_prior": n, "years": prior})
    n_keys = len(details)
    n_ge3 = sum(1 for d in details if d["n_prior"] >= 3)
    return {
        "as_of": as_of,
        "district_calendar_month_keys": n_keys,
        "n_prior_0": counts[0],
        "n_prior_1": counts[1],
        "n_prior_2": counts[2],
        "n_prior_3": counts[3],
        "n_prior_ge_4": counts["ge4"],
        "share_with_n_prior_ge_3": (n_ge3 / n_keys) if n_keys else 0.0,
        "keys_with_n_prior_ge_3": n_ge3,
    }


def month_stats(rows: list[dict], requested: list[str]) -> list[dict]:
    by_p = defaultdict(list)
    for r in rows:
        by_p[r.get("source_period") or r.get("period")].append(r)
    out = []
    for p in requested:
        group = by_p.get(p, [])
        comps = [r.get("facility_completeness") for r in group if r.get("facility_completeness") is not None]
        districts = {r.get("district_slug") for r in group if r.get("district_slug") in KNOWN_ADMIN}
        out.append({
            "period": p,
            "districts": len(districts),
            "rows": len(group),
            "mean_completeness": (sum(comps) / len(comps)) if comps else None,
            "min_completeness": min(comps) if comps else None,
            "n_confirmed": sum(1 for r in group if r.get("malaria_confirmed") is not None),
            "n_tests": sum(1 for r in group if r.get("malaria_tests") is not None),
            "n_u5": sum(1 for r in group if r.get("malaria_confirmed_u5") is not None),
            "n_rdt": sum(1 for r in group if r.get("malaria_rdt_positive") is not None),
            "n_climate": sum(1 for r in group if r.get("rainfall_mm") is not None),
        })
    return out


def main() -> None:
    hashes_before = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
    }
    v1 = json.loads(V1_PANEL.read_text(encoding="utf-8"))
    if len(v1) != 535:
        raise SystemExit(f"STOP: v1 panel is {len(v1)} rows, expected 535")

    client = Dhis2Client(mock=False)
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    health_rows: list[dict] = []
    chunk_reports = []
    for start, end in _year_chunks(EXPANSION_START, EXPANSION_END):
        chunk_path = CHUNK_DIR / f"health_{start}_{end}.json"
        if chunk_path.exists():
            payload = json.loads(chunk_path.read_text(encoding="utf-8"))
            health_rows.extend(payload["district_month"])
            chunk_reports.append({**payload.get("report", {}), "cached": True})
            print(f"DHIS2 cached {start}-{end} rows={len(payload['district_month'])}", flush=True)
            continue
        print(f"DHIS2 extract {start}-{end} persist=False", flush=True)
        result = extract_historical(client=client, start=start, end=end, persist=False)
        health_rows.extend(result["district_month"])
        report = {
            "start": start,
            "end": end,
            "source": result.get("source"),
            "mock": result.get("mock"),
            "observed_months": result["completeness"].get("observed_month_count"),
            "districts": result["completeness"].get("district_count"),
            "rows": len(result["district_month"]),
            "cached": False,
        }
        chunk_reports.append(report)
        chunk_path.write_text(
            json.dumps({"report": report, "district_month": result["district_month"]}, default=str),
            encoding="utf-8",
        )

    existing_joined = []
    if OUT_PATH.exists():
        existing_joined = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    have = {
        (r.get("source_period"), r.get("district_slug"))
        for r in existing_joined
        if r.get("rainfall_mm") is not None
    }
    new_health = [
        r for r in health_rows
        if (r.get("source_period"), r.get("district_slug")) not in have
    ]
    if new_health:
        new_periods = sorted({r.get("source_period") for r in new_health if r.get("source_period")})
        print(
            f"Open-Meteo Archive climate persist=False for {new_periods[0]}-{new_periods[-1]} "
            f"({len(new_health)} new district-months)",
            flush=True,
        )
        climate_rows = fetch_climate_with_retry(new_periods[0], new_periods[-1])
        joined_new = join_district_month(new_health, climate_rows)
        joined = existing_joined + joined_new
    else:
        print("Open-Meteo Archive climate reused from existing expansion file", flush=True)
        joined = existing_joined
    climate = {"source": "open_meteo_archive", "mock": False}
    for row in joined:
        period = row.get("source_period") or ""
        row["expansion_window"] = True
        row["indicator_object_era"] = (
            "post_indicator_created" if period >= COMPARABLE_START else "pre_indicator_created"
        )
        row["v1_reference_panel"] = False
    joined.sort(key=lambda r: (r.get("source_period") or "", r.get("district_slug") or ""))

    OUT_PATH.write_text(json.dumps(joined, indent=2, default=str), encoding="utf-8")

    requested = expand_monthly_range(EXPANSION_START, EXPANSION_END)
    observed = sorted({r.get("source_period") for r in joined if r.get("source_period")})
    districts = sorted({r.get("district_slug") for r in joined if r.get("district_slug") in KNOWN_ADMIN})
    expected_dm = 16 * len(requested)
    observed_dm = sum(
        1 for r in joined
        if r.get("district_slug") in KNOWN_ADMIN and r.get("source_period") in set(requested)
    )

    combined = []
    for r in joined:
        combined.append({
            "source_period": r.get("source_period"),
            "district_slug": r.get("district_slug"),
            "malaria_confirmed": r.get("malaria_confirmed"),
            "malaria_tests": r.get("malaria_tests"),
            "malaria_confirmed_u5": r.get("malaria_confirmed_u5"),
            "malaria_rdt_positive": r.get("malaria_rdt_positive"),
            "facility_completeness": r.get("facility_completeness"),
            "rainfall_mm": r.get("rainfall_mm"),
            "era": r.get("indicator_object_era"),
        })
    for r in v1:
        combined.append({
            "source_period": r.get("source_period"),
            "district_slug": r.get("district_slug"),
            "malaria_confirmed": r.get("malaria_confirmed"),
            "malaria_tests": r.get("malaria_tests"),
            "malaria_confirmed_u5": r.get("malaria_confirmed_u5"),
            "malaria_rdt_positive": r.get("malaria_rdt_positive"),
            "facility_completeness": r.get("facility_completeness"),
            "rainfall_mm": r.get("rainfall_mm"),
            "era": "v1_reference",
        })

    comparable = [
        r for r in combined
        if (r.get("source_period") or "") >= COMPARABLE_START
        and r.get("district_slug") in KNOWN_ADMIN
    ]

    def coverage_counts(rows):
        return {
            "rows": len(rows),
            "malaria_confirmed": sum(1 for r in rows if r.get("malaria_confirmed") is not None),
            "malaria_tests": sum(1 for r in rows if r.get("malaria_tests") is not None),
            "malaria_confirmed_u5": sum(1 for r in rows if r.get("malaria_confirmed_u5") is not None),
            "malaria_rdt_positive": sum(1 for r in rows if r.get("malaria_rdt_positive") is not None),
            "climate": sum(1 for r in rows if r.get("rainfall_mm") is not None),
        }

    report = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expansion_start": EXPANSION_START,
        "expansion_end": EXPANSION_END,
        "comparable_start": COMPARABLE_START,
        "v1_panel_rows_unmodified": 535,
        "chunk_reports": chunk_reports,
        "climate_source": climate.get("source"),
        "climate_mock": climate.get("mock"),
        "expansion_rows": len(joined),
        "requested_months": requested,
        "requested_month_count": len(requested),
        "observed_months": observed,
        "observed_month_count": len(observed),
        "missing_months": [m for m in requested if m not in set(observed)],
        "districts": districts,
        "district_count": len(districts),
        "expected_district_months_16x_months": expected_dm,
        "observed_district_months_admin": observed_dm,
        "missing_district_months": expected_dm - observed_dm,
        "month_stats": month_stats(joined, requested),
        "expansion_indicator_coverage": coverage_counts(joined),
        "combined_n_prior_all_analytics": n_prior_histogram(combined),
        "combined_n_prior_comparable_from_202106": n_prior_histogram(comparable),
        "hashes_before": hashes_before,
        "note": "v1 panel was read, not rewritten. extract_historical persist=False.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    hashes_after = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
    }
    if hashes_after != hashes_before:
        raise SystemExit(f"STOP: protected file hash changed: {hashes_before} vs {hashes_after}")
    if len(json.loads(V1_PANEL.read_text())) != 535:
        raise SystemExit("STOP: v1 panel row count changed")
    print(json.dumps({
        "expansion_rows": len(joined),
        "observed_months": len(observed),
        "missing_months": report["missing_months"],
        "districts": len(districts),
        "n_prior_all": report["combined_n_prior_all_analytics"],
        "n_prior_comparable": report["combined_n_prior_comparable_from_202106"],
        "out": str(OUT_PATH),
        "protected_hashes_ok": True,
    }, indent=2))


if __name__ == "__main__":
    main()

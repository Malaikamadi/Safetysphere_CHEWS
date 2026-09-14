"""
Build CHEWS Historical Flood Weather Dataset v1.

Isolated Open-Meteo Archive ingest + validation + temporal features.
Does NOT train a flood model, create flood labels, or modify production CHEWS.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.flood_weather_history import (  # noqa: E402
    PERIOD_END,
    PERIOD_START,
    ROW_FIELDS,
    assert_protected_unchanged,
    build_dataset,
    build_manifest,
    ingest_settings,
    protected_hashes,
    resume_plan,
    write_csv,
)

TRAINING = BACKEND / "data" / "04_ai" / "training_sets"
DIAG = BACKEND / "data" / "04_ai" / "diagnostics"
CSV_OUT = TRAINING / "flood_weather_history_v1.csv"
JSON_OUT = TRAINING / "flood_weather_history_v1.json"
MANIFEST_OUT = TRAINING / "flood_weather_history_v1_manifest.json"
MANIFEST_REVIEW = DIAG / "flood_weather_history_v1_manifest.json"
LOCATIONS_OUT = DIAG / "flood_weather_history_v1_locations.json"


def _write_dataset_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "version": payload["version"],
        "generated_at": payload["generated_at"],
        "disclaimer": payload["disclaimer"],
        "flood_labels_created": False,
        "model_trained": False,
        "integrated_into_chews": False,
        "period": payload["period"],
        "locations": payload["locations"],
        "quality": payload["quality"],
        "malaria_climate_comparison": payload["malaria_climate_comparison"],
        "row_fields": ROW_FIELDS,
        "n_rows": len(payload["rows"]),
        "rows": payload["rows"],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(slim, handle, separators=(",", ":"), default=str)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build flood weather history v1 (no training, no flood labels).")
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Skip cached locations and fetch only missing ones (default).",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Do not call Open-Meteo; use cached raw extracts only.",
    )
    args = parser.parse_args()
    before = protected_hashes()
    settings = ingest_settings()
    plan = resume_plan()
    live_fetch = not args.cache_only
    print(json.dumps({
        "resume": True,
        "cache_only": args.cache_only,
        "completed_cached": [loc["location_id"] for loc in plan["completed"]],
        "missing": [loc["location_id"] for loc in plan["missing"]],
        "n_completed": len(plan["completed"]),
        "n_missing": len(plan["missing"]),
        "ingest_settings": settings,
        "disclaimer": "Historical weather data does not constitute historical flood-event ground truth.",
    }, indent=2), flush=True)
    if args.cache_only:
        print(f"[flood_weather_v1] cache-only: {len(plan['missing'])} locations will remain missing", flush=True)
    elif plan["missing"]:
        print(
            f"[flood_weather_v1] resume: fetching {len(plan['missing'])} missing; "
            f"skipping {len(plan['completed'])} cached; delay={settings['request_delay_seconds']}s",
            flush=True,
        )
    payload = build_dataset(
        start=PERIOD_START,
        end=PERIOD_END,
        persist_raw=True,
        reuse_raw=True,
        live_fetch=live_fetch,
        sleep_seconds=float(settings["request_delay_seconds"]),
    )
    TRAINING.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)
    write_csv(CSV_OUT, payload["rows"])
    _write_dataset_json(JSON_OUT, payload)
    manifest = build_manifest(payload)
    manifest["outputs"] = {
        "csv": str(CSV_OUT.relative_to(BACKEND.parent)),
        "json": str(JSON_OUT.relative_to(BACKEND.parent)),
        "manifest": str(MANIFEST_OUT.relative_to(BACKEND.parent)),
        "note": "training_sets/*.json is gitignored; diagnostics copy is the reviewable manifest.",
    }
    text = json.dumps(manifest, indent=2, default=str)
    MANIFEST_OUT.write_text(text, encoding="utf-8")
    MANIFEST_REVIEW.write_text(text, encoding="utf-8")
    LOCATIONS_OUT.write_text(
        json.dumps(payload["locations"], indent=2, default=str),
        encoding="utf-8",
    )
    after = assert_protected_unchanged(before)
    quality = payload["quality"]
    print(json.dumps({
        "dataset": payload["version"],
        "period": payload["period"],
        "n_locations": len(payload["locations"]),
        "n_rows": quality["n_rows"],
        "n_expected": quality["n_expected"],
        "missing_precipitation": quality["missing_precipitation"],
        "n_duplicate_location_dates": quality["n_duplicate_location_dates"],
        "n_fetch_failures": quality.get("n_fetch_failures", 0),
        "n_locations_with_series": quality.get("n_locations_with_series"),
        "integrity_ok": all(item.get("ok") for item in quality.get("location_series_integrity") or [True]),
        "flood_labels_created": False,
        "model_trained": False,
        "csv": str(CSV_OUT),
        "json": str(JSON_OUT),
        "manifest": str(MANIFEST_REVIEW),
        "protected_unchanged": after == before,
        "disclaimer": payload["disclaimer"],
    }, indent=2))


if __name__ == "__main__":
    main()

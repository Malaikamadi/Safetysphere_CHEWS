"""
Build CHEWS Historical Flood Weather Dataset v1.

Isolated Open-Meteo Archive ingest + validation + temporal features.
Does NOT train a flood model, create flood labels, or modify production CHEWS.
"""

from __future__ import annotations

import json
import sys
import time
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
    load_cached_payload,
    load_canonical_locations,
    protected_hashes,
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
    before = protected_hashes()
    needed = [
        loc for loc in load_canonical_locations()
        if loc.get("coordinate_ok")
        and load_cached_payload(loc["location_id"], PERIOD_START, PERIOD_END) is None
    ]
    if needed:
        print(f"[flood_weather_v1] {len(needed)} locations need live fetch; 90s rate-limit cooldown", flush=True)
        time.sleep(90)
    payload = build_dataset(
        start=PERIOD_START,
        end=PERIOD_END,
        persist_raw=True,
        reuse_raw=True,
        sleep_seconds=8.0,
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

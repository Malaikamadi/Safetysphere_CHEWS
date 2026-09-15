"""
Acquire and normalize dated flood observations into chews_flood_event_v0.

Does NOT train, create rainfall labels, modify weather history, or touch production CHEWS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.chews_flood_event_v0 import (  # noqa: E402
    assert_protected_unchanged,
    build_registry,
    protected_hashes,
    write_event_csv,
)

TRAINING = BACKEND / "data" / "04_ai" / "training_sets"
DIAG = BACKEND / "data" / "04_ai" / "diagnostics"
JSON_OUT = TRAINING / "chews_flood_event_v0.json"
CSV_OUT = TRAINING / "chews_flood_event_v0.csv"
AUDIT_OUT = DIAG / "chews_flood_event_v0_audit.json"


def main() -> None:
    before = protected_hashes()
    payload = build_registry()
    TRAINING.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)
    slim = {
        "version": payload["version"],
        "generated_at": payload["generated_at"],
        "disclaimer": payload["disclaimer"],
        "model_trained": False,
        "integrated_into_chews": False,
        "flood_occurred_created": False,
        "negative_labels_created": False,
        "rainfall_threshold_applied": False,
        "n_events": len(payload["events"]),
        "events": payload["events"],
        "held_out_without_calendar_day": payload["held_out_without_calendar_day"],
        "n_historical_context_year_only": len(payload["historical_context_year_only"]),
        "historical_context_year_only": payload["historical_context_year_only"],
        "duplicate_candidates": payload.get("duplicate_candidates") or [],
        "audit": payload["audit"],
    }
    JSON_OUT.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
    write_event_csv(CSV_OUT, payload["events"])
    AUDIT_OUT.write_text(json.dumps(payload["audit"], indent=2, default=str), encoding="utf-8")
    after = assert_protected_unchanged(before)
    audit = payload["audit"]
    planning = audit["planning_criteria"]
    print(json.dumps({
        "version": payload["version"],
        "classification": audit["classification"],
        "classification_label": audit["classification_label"],
        "n_daily_target_events": audit["n_daily_target_events"],
        "n_unique_dated_events": audit.get("n_unique_dated_events"),
        "n_matched_to_catalog": audit["n_matched_to_catalog"],
        "n_unmatched": audit["n_unmatched"],
        "n_events_complete_weather": audit["n_events_complete_weather"],
        "n_corroborated_events": audit.get("n_corroborated_events"),
        "ndma_register_acquired": audit["ndma_register_acquired"],
        "event_data_floor_met": planning.get("event_data_floor_met"),
        "planning_criteria": planning,
        "stopping_rule": audit.get("stopping_rule"),
        "flood_occurred_created": False,
        "model_trained": False,
        "protected_unchanged": after == before,
        "json": str(JSON_OUT),
        "csv": str(CSV_OUT),
        "audit": str(AUDIT_OUT),
        "disclaimer": payload["disclaimer"],
    }, indent=2))


if __name__ == "__main__":
    main()

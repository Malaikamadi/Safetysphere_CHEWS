"""
Write flood-event data-foundation diagnostics.

Does NOT train, download event tables, or modify production flood files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.flood_data_foundation import (  # noqa: E402
    assert_protected_unchanged,
    build_foundation_report,
)

OUT = BACKEND / "data" / "04_ai" / "diagnostics" / "flood_data_foundation.json"


def main() -> None:
    report = build_foundation_report()
    after = assert_protected_unchanged(report["protected_hashes_before"])
    report["protected_hashes_after"] = after
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    assert_protected_unchanged(report["protected_hashes_before"])
    print(json.dumps({
        "report": str(OUT),
        "verdict": report["verdict"]["classification"],
        "recommended_target": report["recommended_target"]["name"],
        "in_repo_dated_flood_events": report["coverage"]["in_repo_dated_flood_events"],
        "primary_source_acquired": report["coverage"]["external_primary_source_acquired"],
        "model_trained": report["model_trained"],
        "protected_unchanged": True,
    }, indent=2))


if __name__ == "__main__":
    main()

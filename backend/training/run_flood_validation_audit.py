"""
Run the isolated flood early-warning validation audit.

Writes:
  backend/data/04_ai/diagnostics/flood_validation_report.json

Does NOT train a flood model.
Does NOT overwrite flood_model.joblib.
Does NOT modify flood_risk.py, flood_dashboard.py, weather_api.py,
or any live CHEWS path.
Does NOT download Open-Meteo Archive.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.flood_validation import (  # noqa: E402
    assert_protected_unchanged,
    build_flood_validation_report,
)

OUT = BACKEND / "data" / "04_ai" / "diagnostics" / "flood_validation_report.json"


def main() -> None:
    report = build_flood_validation_report()
    after = assert_protected_unchanged(report["protected_hashes_before"])
    report["protected_hashes_after"] = after
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    assert_protected_unchanged(report["protected_hashes_before"])
    summary = {
        "report": str(OUT),
        "verdict": report["verdict"]["classification"],
        "supervised_flood_prediction_supported": report["target_assessment"]["supervised_flood_prediction_supported"],
        "ml_justified": report["ml_justified"],
        "model_trained_this_phase": report["model_trained_this_phase"],
        "gbt_evaluated": report["baseline_comparison"]["existing_gbt_synthetic_holdout"].get("evaluated"),
        "gbt_synthetic_auc": report["baseline_comparison"]["existing_gbt_synthetic_holdout"].get("roc_auc"),
        "rainfall_baseline_auc": report["baseline_comparison"]["rainfall_threshold_baseline"]["test_metrics"].get(
            "roc_auc_using_rainfall_as_score"
        ),
        "protected_unchanged": True,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

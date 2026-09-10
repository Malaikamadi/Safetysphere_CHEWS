"""
Run the isolated malaria anomaly shadow pilot.

Writes:
  backend/data/04_ai/shadow/malaria_anomaly_shadow_latest.json
  backend/data/04_ai/shadow/malaria_anomaly_shadow_audit.json

Does NOT overwrite malaria_anomaly_backtest.json.
Does NOT persist DHIS2 extracts.
Does NOT train or touch production CHEWS paths.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.malaria_anomaly_shadow import build_shadow_pilot  # noqa: E402

EXPANSION = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion.json"
V1_PANEL = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_district_month_panel_latest.json"
SHADOW_DIR = BACKEND / "data" / "04_ai" / "shadow"
SHADOW_LATEST = SHADOW_DIR / "malaria_anomaly_shadow_latest.json"
SHADOW_AUDIT = SHADOW_DIR / "malaria_anomaly_shadow_audit.json"
BACKTEST = BACKEND / "data" / "04_ai" / "diagnostics" / "malaria_anomaly_backtest.json"
COUNT_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_forecast_v1" / "model.joblib"
POS_V1 = BACKEND / "data" / "04_ai" / "models" / "malaria_positivity_forecast_v1" / "model.joblib"
GBT = BACKEND / "data" / "trained_models" / "malaria_model.joblib"
COUNT_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_forecast_v1_filtered.json"
POS_FILTERED = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_positivity_forecast_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BACKEND.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def main() -> None:
    hashes_before = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
        "backtest_json": _sha256(BACKTEST),
    }
    v1 = json.loads(V1_PANEL.read_text(encoding="utf-8"))
    if len(v1) != 535:
        raise SystemExit(f"STOP: v1 panel is {len(v1)} rows, expected 535")
    expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
    payload = build_shadow_pilot(
        expansion,
        v1,
        software={
            "component": "malaria_anomaly_shadow",
            "python": platform.python_version(),
            "git_head": _git_head(),
            "live_analytics_called": False,
        },
    )
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    SHADOW_LATEST.write_text(
        json.dumps(payload["records"], indent=2, default=str),
        encoding="utf-8",
    )
    audit = dict(payload["audit"])
    audit["protected_hashes_before"] = hashes_before
    SHADOW_AUDIT.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    hashes_after = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
        "backtest_json": _sha256(BACKTEST),
    }
    if hashes_after != hashes_before:
        raise SystemExit("STOP: protected file hash changed")
    print(json.dumps({
        "shadow_latest": str(SHADOW_LATEST),
        "shadow_audit": str(SHADOW_AUDIT),
        "n_shadow_observations": audit["n_shadow_observations"],
        "n_anomaly_flags": audit["n_anomaly_flags"],
        "n_blocked_by_data_quality": audit["n_blocked_by_data_quality"],
        "n_confirmed_case_support": audit["n_confirmed_case_support"],
        "n_testing_down": audit["n_testing_down"],
        "n_sustained_anomalies": audit["n_sustained_anomalies"],
        "leakage_passed": audit["leakage_audit"]["passed"],
        "backtest_json_unchanged": True,
        "model_trained": False,
        "integrated_into_chews": False,
    }, indent=2))


if __name__ == "__main__":
    main()

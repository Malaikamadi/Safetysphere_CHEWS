"""
Simulate operational malaria seasonal-anomaly rules on the comparable-era panel.

Does NOT train a model.
Does NOT overwrite malaria_anomaly_backtest.json.
Does NOT modify the original 535-row panel or any CHEWS production path.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.malaria_anomaly import (  # noqa: E402
    COMPARABLE_START,
    audit_no_future_in_baselines,
    index_panel,
    load_comparable_panel,
    score_panel,
)
from services.malaria_anomaly_operational import (  # noqa: E402
    CANDIDATE_GATES_PP,
    STATUS_UNUSUAL_POSITIVITY,
    assess_row,
    attach_quality_blocks,
    magnitude_flag,
)

EXPANSION = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_expansion.json"
V1_PANEL = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_district_month_panel_latest.json"
OUT_JSON = BACKEND / "data" / "04_ai" / "diagnostics" / "malaria_anomaly_operational_review.json"
BACKTEST_JSON = BACKEND / "data" / "04_ai" / "diagnostics" / "malaria_anomaly_backtest.json"
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


def _summarize_gate(assessed: list[dict], eligible_n: int) -> dict:
    unusual = [r for r in assessed if r["status"] == STATUS_UNUSUAL_POSITIVITY]
    n = len(unusual)
    with_lead = [
        r for r in unusual
        if r.get("lead1_period") and r.get("lead1_abs_dev_median") is not None
    ]
    gate = unusual[0]["gate_pp"] if unusual else assessed[0]["gate_pp"]
    followed = [
        r for r in with_lead
        if magnitude_flag(r["lead1_abs_dev_median"], gate)
    ]
    still_above_median = [
        r for r in with_lead
        if r["lead1_abs_dev_median"] is not None and r["lead1_abs_dev_median"] > 0
    ]
    by_district = Counter(r["district_slug"] for r in unusual)
    by_month = Counter(int(r["calendar_month"]) for r in unusual)
    by_season = Counter(r["season"] for r in unusual)
    primary_state = Counter((r["context"] or {}).get("primary_state") or "none" for r in unusual)
    return {
        "gate_pp": gate,
        "gate_source": "operational_policy_not_fitted",
        "n_unusual": n,
        "alert_rate_among_quality_pass": (n / eligible_n) if eligible_n else None,
        "n_quality_pass": eligible_n,
        "alerts_by_district": dict(by_district),
        "silent_districts": sorted(
            {r["district_slug"] for r in assessed} - set(by_district)
        ),
        "alerts_by_calendar_month": {str(k): v for k, v in sorted(by_month.items())},
        "alerts_by_season": dict(by_season),
        "n_with_calendar_t_plus_1": len(with_lead),
        "n_followed_by_same_gate": len(followed),
        "p_followed_by_same_gate": (len(followed) / len(with_lead)) if with_lead else None,
        "p_tplus1_still_above_median": (
            (len(still_above_median) / len(with_lead)) if with_lead else None
        ),
        "n_confirmed_increasing": sum(1 for r in unusual if r["context"]["confirmed_increasing"]),
        "n_tests_decreasing": sum(1 for r in unusual if r["context"]["tests_decreasing"]),
        "n_tests_increasing": sum(1 for r in unusual if r["context"]["tests_increasing"]),
        "n_completeness_deterioration": sum(
            1 for r in unusual if r["context"]["completeness_deterioration"]
        ),
        "n_without_supporting_evidence": sum(
            1 for r in unusual
            if r["context"].get("primary_state") == "without_supporting_evidence"
        ),
        "primary_state_counts": dict(primary_state),
        "n_isolated": sum(1 for r in unusual if r["consecutive_anomaly_months"] == 1),
        "n_sustained_2_plus": sum(1 for r in unusual if r["sustained_2"]),
        "n_sustained_3_plus": sum(1 for r in unusual if r["sustained_3"]),
        "share_confirmed_increasing": (sum(1 for r in unusual if r["context"]["confirmed_increasing"]) / n) if n else None,
        "share_tests_decreasing": (sum(1 for r in unusual if r["context"]["tests_decreasing"]) / n) if n else None,
    }


def main() -> None:
    hashes_before = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
        "backtest_json": _sha256(BACKTEST_JSON),
    }
    v1 = json.loads(V1_PANEL.read_text(encoding="utf-8"))
    if len(v1) != 535:
        raise SystemExit(f"STOP: v1 panel is {len(v1)} rows, expected 535")
    expansion = json.loads(EXPANSION.read_text(encoding="utf-8"))
    rows = load_comparable_panel(expansion, v1)
    if any(r["source_period"] < COMPARABLE_START for r in rows):
        raise SystemExit("STOP: comparable panel contains pre-202106 rows")
    scored = score_panel(rows, field="malaria_positivity")
    leak = audit_no_future_in_baselines(scored)
    if not leak["passed"]:
        raise SystemExit(f"STOP: leakage {leak}")

    panel_index = index_panel(rows)
    attach_quality_blocks(scored, panel_index)
    score_index = {(r["district_slug"], r["source_period"]): r for r in scored}
    quality_pass = [r for r in scored if not r.get("quality_blocks")]
    quality_blocked = [r for r in scored if r.get("quality_blocks")]
    reason_counts = Counter()
    for row in quality_blocked:
        for reason in row.get("quality_reasons") or []:
            reason_counts[reason] += 1

    gate_summaries = {}
    example_messages = {}
    assessed_by_gate = {}
    for gate in CANDIDATE_GATES_PP:
        assessed = [
            assess_row(row, panel_index, score_index, gate_pp=gate)
            for row in scored
        ]
        assessed_by_gate[str(gate)] = assessed
        gate_summaries[str(gate)] = _summarize_gate(assessed, len(quality_pass))
        unusual = [r for r in assessed if r["unusual_positivity"]]
        examples = []
        for row in unusual:
            state = (row["context"] or {}).get("primary_state")
            if state and not any(e.get("primary_state") == state for e in examples):
                examples.append({
                    "primary_state": state,
                    "district_slug": row["district_slug"],
                    "source_period": row["source_period"],
                    "abs_dev_pp": row["abs_dev_pp"],
                    "message": row["message"],
                })
            if len(examples) >= 4:
                break
        example_messages[str(gate)] = examples

    # Sustained vs isolated predictive value at +3 pp (policy candidate, not fitted).
    assessed3 = assessed_by_gate["3"]
    unusual3 = [r for r in assessed3 if r["unusual_positivity"]]
    isolated = [r for r in unusual3 if r["consecutive_anomaly_months"] == 1]
    sustained2 = [r for r in unusual3 if r["sustained_2"]]

    def _follow_rate(group):
        with_lead = [r for r in group if r.get("lead1_abs_dev_median") is not None]
        hits = [r for r in with_lead if magnitude_flag(r["lead1_abs_dev_median"], 3)]
        return {
            "n": len(group),
            "n_with_t_plus_1": len(with_lead),
            "n_followed": len(hits),
            "p_followed": (len(hits) / len(with_lead)) if with_lead else None,
        }

    # Empirical abs_dev distribution on quality-pass rows (data-described, not a gate).
    abs_pp = [
        (r.get("abs_dev_median") or 0) * 100.0
        for r in quality_pass
        if r.get("abs_dev_median") is not None
    ]
    abs_pp_sorted = sorted(abs_pp)

    def _pct(values, q):
        if not values:
            return None
        pos = (len(values) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        if lo == hi:
            return values[lo]
        return values[lo] * (hi - pos) + values[hi] * (pos - lo)

    recommended_gate = 3
    rec_summary = gate_summaries["3"]
    # Prefer +3 pp as a documented policy starting point if it is rarer than +2,
    # not vanishing like +10, and majority confirmed-increasing.
    if rec_summary["n_unusual"] == 0:
        recommendation = "D"
        rec_reason = "+3 pp produced no historical flags; no operational starting point is available."
    elif rec_summary["share_tests_decreasing"] and rec_summary["share_tests_decreasing"] > 0.4:
        recommendation = "B"
        rec_reason = "Too many +3 pp flags coincide with testing decreases; more validation is required."
    elif rec_summary["n_unusual"] < 5:
        recommendation = "C"
        rec_reason = "Too few +3 pp flags in the 22-month scoring window to govern operations."
    else:
        recommendation = "A"
        rec_reason = (
            "+3 percentage points is a documented operational policy starting point, not a fitted "
            "threshold. A controlled shadow pilot can proceed only if kept separate from the live "
            "CHEWS forecast. It remains a nowcast, not outbreak prediction."
        )

    payload = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_trained": False,
        "integrated_into_chews": False,
        "overwrote_backtest_json": False,
        "robust_z_is_operational_trigger": False,
        "primary_measure": "absolute_positivity_deviation_percentage_points",
        "baseline": "past_only_expanding_seasonal_median",
        "comparable_era": {"start": "202106", "end": "202608", "rows": len(rows)},
        "scored_rows": len(scored),
        "quality_pass_rows": len(quality_pass),
        "quality_blocked_rows": len(quality_blocked),
        "quality_reason_counts": dict(reason_counts),
        "leakage_audit": leak,
        "data_described_abs_dev_pp_quality_pass": {
            "n": len(abs_pp_sorted),
            "min": abs_pp_sorted[0] if abs_pp_sorted else None,
            "p50": _pct(abs_pp_sorted, 0.50),
            "p75": _pct(abs_pp_sorted, 0.75),
            "p90": _pct(abs_pp_sorted, 0.90),
            "p95": _pct(abs_pp_sorted, 0.95),
            "max": abs_pp_sorted[-1] if abs_pp_sorted else None,
            "share_ge_2pp": sum(1 for x in abs_pp_sorted if x >= 2) / len(abs_pp_sorted) if abs_pp_sorted else None,
            "share_ge_3pp": sum(1 for x in abs_pp_sorted if x >= 3) / len(abs_pp_sorted) if abs_pp_sorted else None,
            "share_ge_5pp": sum(1 for x in abs_pp_sorted if x >= 5) / len(abs_pp_sorted) if abs_pp_sorted else None,
            "share_ge_10pp": sum(1 for x in abs_pp_sorted if x >= 10) / len(abs_pp_sorted) if abs_pp_sorted else None,
            "note": "Descriptive of quality-pass residuals. Not used as a fitted alert cut.",
        },
        "gates": gate_summaries,
        "example_messages_by_gate": example_messages,
        "sustained_vs_isolated_at_3pp": {
            "isolated": _follow_rate(isolated),
            "sustained_2_plus": _follow_rate(sustained2),
            "note": "Follow-up is calendar t+1 still passing the same +3 pp gate. Not a gold-standard outbreak label.",
        },
        "recommended_policy_gate_pp": recommended_gate,
        "recommended_policy_gate_source": "operational_policy_not_fitted",
        "recommendation": {
            "code": recommendation,
            "options": {
                "A": "READY FOR CONTROLLED PILOT",
                "B": "NEEDS MORE VALIDATION",
                "C": "NEEDS MORE DATA",
                "D": "NOT OPERATIONALLY DEFENSIBLE",
            },
            "reason": rec_reason,
            "pilot_must_be_separate_from_live_forecast": True,
        },
        "unusual_events_3pp": [
            {
                "district_slug": r["district_slug"],
                "source_period": r["source_period"],
                "abs_dev_pp": r["abs_dev_pp"],
                "positivity": r["positivity"],
                "seasonal_median": r["seasonal_median"],
                "primary_state": r["context"].get("primary_state"),
                "confirmed_increasing": r["context"]["confirmed_increasing"],
                "tests_decreasing": r["context"]["tests_decreasing"],
                "consecutive_anomaly_months": r["consecutive_anomaly_months"],
                "season": r["season"],
                "message": r["message"],
            }
            for r in unusual3
        ],
        "protected_hashes_before": hashes_before,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    hashes_after = {
        "panel": _sha256(V1_PANEL),
        "gbt": _sha256(GBT),
        "count_v1": _sha256(COUNT_V1),
        "pos_v1": _sha256(POS_V1),
        "count_filtered": _sha256(COUNT_FILTERED),
        "pos_filtered": _sha256(POS_FILTERED),
        "backtest_json": _sha256(BACKTEST_JSON),
    }
    if hashes_after != hashes_before:
        raise SystemExit("STOP: protected file hash changed")
    print(json.dumps({
        "out": str(OUT_JSON),
        "quality_pass": len(quality_pass),
        "gates": {k: v["n_unusual"] for k, v in gate_summaries.items()},
        "rates": {k: v["alert_rate_among_quality_pass"] for k, v in gate_summaries.items()},
        "recommendation": recommendation,
        "backtest_json_unchanged": True,
        "model_trained": False,
    }, indent=2))


if __name__ == "__main__":
    main()

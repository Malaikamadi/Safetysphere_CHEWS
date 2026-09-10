"""
Isolated malaria seasonal-anomaly SHADOW PILOT.

Replay / observer path only. Does not train a model.
Does not call the dashboard, risk engine, or /api/healthcare/forecast/live.
Does not overwrite malaria_anomaly_backtest.json or the 535-row panel.
Does not send notifications or create production alerts.

Policy gate +3 pp is operational/policy, not a learned outbreak threshold.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from services.dhis2_periods import expand_monthly_range
from services.district_names import display_name
from services.malaria_forecast import calendar_prev
from services.malaria_anomaly import (
    COMPARABLE_END,
    COMPARABLE_START,
    COMPLETENESS_MIN,
    KNOWN_ADMIN,
    audit_no_future_in_baselines,
    index_panel,
    load_comparable_panel,
    period_month,
    score_panel,
)
from services.malaria_anomaly_operational import (
    STATUS_DATA_QUALITY,
    STATUS_INSUFFICIENT_HISTORY,
    STATUS_NO_OBSERVATION,
    STATUS_UNUSUAL_POSITIVITY,
    assess_row,
    attach_quality_blocks,
)

SHADOW_GATE_PP = 3.0
SHADOW_GATE_SOURCE = "operational_policy_not_fitted"
INCOMPLETE_PERIOD_DISTRICT_MIN = 8

CONTEXT_A = "A_anomaly_confirmed_increasing"
CONTEXT_B = "B_anomaly_testing_increasing"
CONTEXT_C = "C_anomaly_testing_decreasing"
CONTEXT_D = "D_anomaly_reporting_completeness_issue"
CONTEXT_E = "E_positivity_anomaly_without_supporting_evidence"

INDICATORS_USED = (
    "malaria_confirmed",
    "malaria_tests",
    "malaria_confirmed_u5",
    "malaria_rdt_positive",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _change_label(increasing: bool, decreasing: bool, pct: Optional[float]) -> str:
    if increasing:
        return "increasing"
    if decreasing:
        return "decreasing"
    if pct is None:
        return "unavailable"
    return "unchanged"


def shadow_context_class(assessed: dict) -> Optional[str]:
    """A–E labels. None when there is no positivity anomaly to interpret."""
    status = assessed.get("status")
    reasons = (assessed.get("quality") or {}).get("reasons") or []
    if status in {STATUS_DATA_QUALITY, STATUS_NO_OBSERVATION} and (
        "low_completeness" in reasons
        or "reporting_collapse" in reasons
        or "missing_observation" in reasons
    ):
        return CONTEXT_D
    if status != STATUS_UNUSUAL_POSITIVITY:
        return None
    primary = (assessed.get("context") or {}).get("primary_state")
    if primary == "completeness_deterioration":
        return CONTEXT_D
    if primary == "tests_decreasing":
        return CONTEXT_C
    if primary == "confirmed_increasing":
        return CONTEXT_A
    if primary == "tests_increasing":
        return CONTEXT_B
    return CONTEXT_E


def _baseline_years(periods: Optional[list]) -> list[str]:
    years = []
    for period in periods or []:
        if period and len(str(period)) >= 4:
            years.append(str(period)[:4])
    return years


def to_shadow_record(assessed: dict, panel_row: Optional[dict], *, generated_at: str) -> dict[str, Any]:
    context = assessed.get("context") or {}
    quality = assessed.get("quality") or {}
    periods = assessed.get("baseline_periods") or []
    status = assessed.get("status")
    anomaly = bool(assessed.get("unusual_positivity"))
    consecutive = int(assessed.get("consecutive_anomaly_months") or 0)
    return {
        "district": assessed.get("district_name") or assessed.get("district_slug"),
        "district_slug": assessed.get("district_slug"),
        "calendar_month": assessed.get("calendar_month"),
        "current_period": assessed.get("source_period"),
        "malaria_confirmed": assessed.get("malaria_confirmed"),
        "malaria_tests": assessed.get("malaria_tests"),
        "malaria_confirmed_u5": None if panel_row is None else panel_row.get("malaria_confirmed_u5"),
        "malaria_rdt_positive": None if panel_row is None else panel_row.get("malaria_rdt_positive"),
        "positivity": assessed.get("positivity"),
        "seasonal_median": assessed.get("seasonal_median"),
        "deviation_pp": assessed.get("abs_dev_pp"),
        "gate_threshold_pp": SHADOW_GATE_PP,
        "gate_source": SHADOW_GATE_SOURCE,
        "anomaly_flag": anomaly,
        "confirmed_change_context": _change_label(
            bool(context.get("confirmed_increasing")),
            bool(context.get("confirmed_decreasing")),
            context.get("d_confirmed_pct"),
        ),
        "testing_change_context": _change_label(
            bool(context.get("tests_increasing")),
            bool(context.get("tests_decreasing")),
            context.get("d_tests_pct"),
        ),
        "context_class": shadow_context_class(assessed),
        "completeness": assessed.get("facility_completeness"),
        "data_quality_status": status,
        "data_quality_reasons": list(quality.get("reasons") or []),
        "sustained_anomaly": bool(anomaly and consecutive >= 2),
        "consecutive_anomaly_months": consecutive if anomaly else 0,
        "baseline_years_used": _baseline_years(periods),
        "baseline_observation_count": len(periods),
        "baseline_periods": list(periods),
        "robust_z_used_as_trigger": False,
        "is_ai": False,
        "is_forecast": False,
        "is_outbreak_label": False,
        "shadow_pilot": True,
        "interpretation": assessed.get("message"),
        "generated_at": generated_at,
    }


def missing_month_placeholder(district: str, period: str, *, generated_at: str) -> dict[str, Any]:
    assessed = {
        "district_slug": district,
        "district_name": display_name(district, district),
        "source_period": period,
        "calendar_month": period_month(period),
        "malaria_confirmed": None,
        "malaria_tests": None,
        "positivity": None,
        "seasonal_median": None,
        "abs_dev_pp": None,
        "unusual_positivity": False,
        "consecutive_anomaly_months": 0,
        "status": STATUS_NO_OBSERVATION,
        "quality": {
            "blocks_malaria_alert": True,
            "reasons": ["missing_observation"],
            "status_if_blocked": STATUS_NO_OBSERVATION,
        },
        "context": {},
        "baseline_periods": [],
        "message": (
            f"No malaria observation is available for {display_name(district, district)} "
            f"in {period}. Missing DHIS2 values are not treated as zero cases."
        ),
    }
    record = to_shadow_record(assessed, None, generated_at=generated_at)
    record["context_class"] = CONTEXT_D
    return record


def build_shadow_pilot(
    expansion_rows: list[dict],
    v1_rows: list[dict],
    *,
    generated_at: Optional[str] = None,
    software: Optional[dict] = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now()
    rows = load_comparable_panel(expansion_rows, v1_rows)
    if any((r.get("source_period") or "") < COMPARABLE_START for r in rows):
        raise ValueError("shadow panel leaked pre-202106 rows")
    scored = score_panel(rows)
    leak = audit_no_future_in_baselines(scored)
    if not leak["passed"]:
        raise ValueError(f"shadow baseline leakage: {leak}")

    panel_index = index_panel(rows)
    attach_quality_blocks(scored, panel_index)
    score_index = {(r["district_slug"], r["source_period"]): r for r in scored}

    assessed_rows = [
        assess_row(row, panel_index, score_index, gate_pp=SHADOW_GATE_PP)
        for row in scored
    ]
    records = [
        to_shadow_record(
            assessed,
            panel_index.get((assessed["district_slug"], assessed["source_period"])),
            generated_at=generated_at,
        )
        for assessed in assessed_rows
    ]

    requested = expand_monthly_range(COMPARABLE_START, COMPARABLE_END)
    have = {(r["district_slug"], r["current_period"]) for r in records}
    missing = []
    for period in requested:
        for slug in sorted(KNOWN_ADMIN):
            if (slug, period) not in have:
                missing.append(missing_month_placeholder(slug, period, generated_at=generated_at))
    records.extend(missing)
    records.sort(key=lambda r: (r.get("current_period") or "", r.get("district_slug") or ""))

    observed_districts = {
        r["district_slug"] for r in records if r.get("malaria_confirmed") is not None
    }
    by_period = Counter(
        r["current_period"] for r in records if r.get("malaria_confirmed") is not None
    )
    # Only a near-national panel can be judged structurally incomplete.
    # Unit-test panels with a few districts must not be demoted by this rule.
    incomplete_periods: list[str] = []
    if len(observed_districts) >= INCOMPLETE_PERIOD_DISTRICT_MIN:
        incomplete_periods = sorted(
            p for p, n in by_period.items() if n < INCOMPLETE_PERIOD_DISTRICT_MIN
        )
    for record in records:
        if record["current_period"] in incomplete_periods and record.get("anomaly_flag"):
            record["data_quality_reasons"] = list(record.get("data_quality_reasons") or []) + [
                "incomplete_period"
            ]
            # Do not silently keep an anomaly on a structurally incomplete month.
            record["anomaly_flag"] = False
            record["sustained_anomaly"] = False
            record["consecutive_anomaly_months"] = 0
            record["data_quality_status"] = STATUS_DATA_QUALITY
            record["context_class"] = CONTEXT_D

    _recompute_consecutive_from_flags(records)

    anomalies = [r for r in records if r.get("anomaly_flag")]
    quality_blocked = [
        r for r in records
        if r.get("data_quality_status") in {
            STATUS_DATA_QUALITY, STATUS_INSUFFICIENT_HISTORY, STATUS_NO_OBSERVATION,
        }
    ]

    audit = {
        "generated_at": generated_at,
        "shadow_pilot": True,
        "model_trained": False,
        "integrated_into_chews": False,
        "notifications_sent": False,
        "input_period": {"start": COMPARABLE_START, "end": COMPARABLE_END},
        "dhis2_source": "comparable_era_replay_expansion_plus_frozen_v1_panel",
        "live_analytics_called": False,
        "indicators_used": list(INDICATORS_USED),
        "baseline_methodology": (
            "past-only expanding seasonal median of positivity for the same "
            "district and calendar month; years strictly before the evaluation month; "
            "pre-202106 excluded"
        ),
        "threshold_pp": SHADOW_GATE_PP,
        "threshold_source": SHADOW_GATE_SOURCE,
        "n_evaluated_districts": len({r["district_slug"] for r in records}),
        "n_shadow_observations": len(records),
        "n_observed_district_months": sum(1 for r in records if r.get("malaria_confirmed") is not None),
        "n_missing_placeholders": len(missing),
        "n_anomaly_flags": len(anomalies),
        "n_blocked_by_data_quality": len(quality_blocked),
        "n_confirmed_case_support": sum(
            1 for r in anomalies if r.get("context_class") == CONTEXT_A
        ),
        "n_testing_down": sum(1 for r in anomalies if r.get("context_class") == CONTEXT_C),
        "n_testing_up": sum(1 for r in anomalies if r.get("context_class") == CONTEXT_B),
        "n_without_supporting_evidence": sum(
            1 for r in anomalies if r.get("context_class") == CONTEXT_E
        ),
        "n_sustained_anomalies": sum(1 for r in anomalies if r.get("sustained_anomaly")),
        "n_isolated_anomalies": sum(
            1 for r in anomalies if r.get("consecutive_anomaly_months") == 1
        ),
        "n_sustained_3": sum(
            1 for r in anomalies if (r.get("consecutive_anomaly_months") or 0) >= 3
        ),
        "baseline_years_span": sorted({
            y for r in records for y in (r.get("baseline_years_used") or [])
        }),
        "incomplete_periods": incomplete_periods,
        "reporting_completeness_min": COMPLETENESS_MIN,
        "data_freshness": "frozen_comparable_era_replay",
        "stale_check": "not_applicable_replay_no_live_analytics",
        "leakage_audit": leak,
        "software": software or {"component": "malaria_anomaly_shadow"},
        "disclaimer": (
            "Statistical seasonal positivity nowcast for shadow review only. "
            "Not AI, not a forecast, not an outbreak detector."
        ),
    }
    return {"records": records, "audit": audit}


def _recompute_consecutive_from_flags(records: list[dict]) -> None:
    """Recount consecutive calendar months after incomplete-period demotion."""
    index = {(r["district_slug"], r["current_period"]): r for r in records}
    for record in records:
        if not record.get("anomaly_flag"):
            record["consecutive_anomaly_months"] = 0
            record["sustained_anomaly"] = False
            continue
        run = 0
        current = record["current_period"]
        slug = record["district_slug"]
        while True:
            row = index.get((slug, current))
            if row is None or not row.get("anomaly_flag"):
                break
            run += 1
            current = calendar_prev(current)
        record["consecutive_anomaly_months"] = run
        record["sustained_anomaly"] = run >= 2

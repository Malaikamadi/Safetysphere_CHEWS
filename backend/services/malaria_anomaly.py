"""
Past-only seasonal malaria positivity anomaly — diagnostics only.

Does NOT train a model.
Does NOT write malaria_model.joblib or GBT artifacts.
Does NOT modify malaria_forecast_v1 / malaria_positivity_forecast_v1.
Does NOT overwrite the original 535-row panel.
Does NOT connect to the dashboard, risk engine, or live forecast.

Comparable era only: 202106–202608. Pre-202106 rows are rejected.
Baselines use the same district × calendar month from strictly earlier years.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional

from services.malaria_forecast import calendar_next, calendar_prev
from services.malaria_positivity_forecast import positivity as positivity_ratio

COMPARABLE_START = "202106"
COMPARABLE_END = "202608"
MIN_PRIOR_YEARS_PRIMARY = 3
COMPLETENESS_MIN = 0.20
MAD_TO_SD = 1.4826  # normal consistency constant
ROBUST_Z_CONVENTION = 2.0  # statistical convention, not a fitted threshold
MILD_Z_CONVENTION = 1.5

KNOWN_ADMIN = {
    "western_area_urban", "western_area_rural", "bo", "pujehun", "bonthe",
    "kenema", "port_loko", "kambia", "tonkolili", "moyamba", "bombali",
    "kailahun", "kono", "koinadugu", "falaba", "karene",
}

BASELINE_METHODS = (
    "prior_year",
    "expanding_mean",
    "expanding_median",
    "expanding_robust",
)


def positivity(confirmed: Any, tests: Any) -> Optional[float]:
    """confirmed / tests only when tests > 0. Missing or non-positive tests → None."""
    return positivity_ratio(confirmed, tests)


def period_year(period: str) -> int:
    return int(period[:4])


def period_month(period: str) -> int:
    return int(period[4:6])


def _float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _stdev(values: list[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = _mean(values)
    if mean is None:
        return None
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


def _mad(values: list[float], center: Optional[float] = None) -> Optional[float]:
    if not values:
        return None
    mid = center if center is not None else _median(values)
    if mid is None:
        return None
    return _median([abs(x - mid) for x in values])


def pearson(xs: Iterable[Optional[float]], ys: Iterable[Optional[float]]) -> Optional[float]:
    pairs = [
        (float(x), float(y))
        for x, y in zip(xs, ys)
        if x is not None and y is not None
        and not math.isnan(float(x)) and not math.isnan(float(y))
    ]
    n = len(pairs)
    if n < 5:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    dx = math.sqrt(sum((p[0] - mx) ** 2 for p in pairs))
    dy = math.sqrt(sum((p[1] - my) ** 2 for p in pairs))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def mae(pairs: list[tuple[float, float]]) -> Optional[float]:
    if not pairs:
        return None
    return sum(abs(a - b) for a, b in pairs) / len(pairs)


def assert_comparable_period(period: str) -> None:
    if period < COMPARABLE_START or period > COMPARABLE_END:
        raise ValueError(f"period {period} is outside comparable era {COMPARABLE_START}-{COMPARABLE_END}")


def normalize_row(row: dict) -> Optional[dict]:
    period = row.get("source_period") or row.get("period")
    slug = row.get("district_slug")
    if not period or not slug or slug not in KNOWN_ADMIN:
        return None
    if period < COMPARABLE_START or period > COMPARABLE_END:
        return None
    confirmed = _float(row.get("malaria_confirmed"))
    tests = _float(row.get("malaria_tests"))
    pos = positivity(confirmed, tests)
    return {
        "district_slug": slug,
        "district_name": row.get("district_name") or slug,
        "source_period": period,
        "calendar_month": period_month(period),
        "year": period_year(period),
        "malaria_confirmed": confirmed,
        "malaria_tests": tests,
        "malaria_confirmed_u5": _float(row.get("malaria_confirmed_u5")),
        "malaria_rdt_positive": _float(row.get("malaria_rdt_positive")),
        "malaria_positivity": pos,
        "facility_completeness": _float(row.get("facility_completeness")),
        "reporting_facilities": _float(row.get("reporting_facilities")),
        "expected_facilities": _float(row.get("expected_facilities")),
        "rainfall_mm": _float(row.get("rainfall_mm")),
        "temperature_c": _float(row.get("temperature_c")),
        "humidity_percent": _float(row.get("humidity_percent")),
        "panel_source": row.get("panel_source"),
        "indicator_object_era": row.get("indicator_object_era"),
    }


def load_comparable_panel(expansion_rows: list[dict], v1_rows: list[dict]) -> list[dict]:
    """
    Comparable-era union. v1 wins on district-period overlap.
    Pre-202106 expansion rows are dropped, never pooled.
    """
    by_key: dict[tuple[str, str], dict] = {}
    for source, rows in (("expansion", expansion_rows), ("v1_reference", v1_rows)):
        for raw in rows:
            tagged = dict(raw)
            tagged["panel_source"] = source
            row = normalize_row(tagged)
            if row is None:
                continue
            by_key[(row["district_slug"], row["source_period"])] = row
    return sorted(by_key.values(), key=lambda r: (r["source_period"], r["district_slug"]))


def index_panel(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(r["district_slug"], r["source_period"]): r for r in rows}


def prior_same_month_rows(
    panel_index: dict[tuple[str, str], dict],
    district: str,
    period: str,
) -> list[dict]:
    """Same district × calendar month, strictly earlier years. No current, no future."""
    month = period_month(period)
    year = period_year(period)
    out = []
    for (slug, pe), row in panel_index.items():
        if slug != district:
            continue
        if period_month(pe) != month:
            continue
        if period_year(pe) >= year:
            continue
        if pe >= period:
            continue
        out.append(row)
    out.sort(key=lambda r: r["source_period"])
    return out


def _values(rows: list[dict], field: str) -> list[float]:
    out = []
    for row in rows:
        value = row.get(field)
        if value is not None:
            out.append(float(value))
    return out


def expanding_baselines(prior_values: list[float]) -> dict[str, Any]:
    n = len(prior_values)
    mean = _mean(prior_values)
    median = _median(prior_values)
    stdev = _stdev(prior_values)
    mad = _mad(prior_values, median)
    prior_year = prior_values[-1] if prior_values else None
    return {
        "n_prior": n,
        "prior_year": prior_year,
        "expanding_mean": mean,
        "expanding_median": median,
        "expanding_stdev": stdev,
        "expanding_mad": mad,
        "zero_dispersion": bool(n >= 2 and mad == 0 and stdev == 0),
        "prior_values": list(prior_values),
    }


def anomaly_measures(observed: Optional[float], baselines: dict[str, Any]) -> dict[str, Any]:
    if observed is None:
        return {
            "observed": None,
            "abs_dev_median": None,
            "rel_dev_median": None,
            "ratio_median": None,
            "abs_dev_mean": None,
            "rel_dev_mean": None,
            "ratio_mean": None,
            "abs_dev_prior_year": None,
            "z_mean": None,
            "robust_z": None,
        }
    median = baselines.get("expanding_median")
    mean = baselines.get("expanding_mean")
    prior_year = baselines.get("prior_year")
    stdev = baselines.get("expanding_stdev")
    mad = baselines.get("expanding_mad")

    def _rel(value: Optional[float], base: Optional[float]) -> Optional[float]:
        if value is None or base is None or base == 0:
            return None
        return (value - base) / base

    def _ratio(value: Optional[float], base: Optional[float]) -> Optional[float]:
        if value is None or base is None or base == 0:
            return None
        return value / base

    z_mean = None
    if mean is not None and stdev not in (None, 0):
        z_mean = (observed - mean) / stdev
    robust_z = None
    if median is not None and mad not in (None, 0):
        robust_z = (observed - median) / (MAD_TO_SD * mad)
    elif median is not None and mad == 0:
        robust_z = 0.0 if observed == median else None

    return {
        "observed": observed,
        "abs_dev_median": None if median is None else observed - median,
        "rel_dev_median": _rel(observed, median),
        "ratio_median": _ratio(observed, median),
        "abs_dev_mean": None if mean is None else observed - mean,
        "rel_dev_mean": _rel(observed, mean),
        "ratio_mean": _ratio(observed, mean),
        "abs_dev_prior_year": None if prior_year is None else observed - prior_year,
        "z_mean": z_mean,
        "robust_z": robust_z,
    }


def leakage_check(period: str, prior_rows: list[dict], district: str) -> dict[str, Any]:
    """Fail if any baseline row is current, future, other district, or other calendar month."""
    month = period_month(period)
    violations = []
    for row in prior_rows:
        pe = row.get("source_period")
        slug = row.get("district_slug")
        if slug != district:
            violations.append({"type": "other_district", "period": pe, "district": slug})
        if pe is None or pe >= period:
            violations.append({"type": "not_strictly_before", "period": pe})
        if pe and period_month(pe) != month:
            violations.append({"type": "other_calendar_month", "period": pe})
        if pe and period_year(pe) >= period_year(period):
            violations.append({"type": "same_or_future_year", "period": pe})
    return {
        "passed": len(violations) == 0,
        "n_prior_rows": len(prior_rows),
        "violations": violations,
    }


def classify_testing_bias(
    *,
    positivity_abs_dev: Optional[float],
    confirmed: Optional[float],
    tests: Optional[float],
    prior_confirmed: Optional[float],
    prior_tests: Optional[float],
    completeness: Optional[float],
    prior_completeness: Optional[float],
) -> str:
    """
    Descriptive class for a positivity movement vs the previous same-calendar-month.

    Not an outbreak label. Missing comparators → insufficient_comparator.
    """
    if positivity_abs_dev is None:
        return "no_positivity_anomaly"
    if tests is None or tests <= 0 or confirmed is None:
        return "tests_not_positive"
    if prior_tests is None or prior_tests <= 0 or prior_confirmed is None:
        return "insufficient_comparator"

    d_conf = confirmed - prior_confirmed
    d_tests = tests - prior_tests
    d_tests_pct = d_tests / prior_tests
    d_comp = None
    if completeness is not None and prior_completeness is not None:
        d_comp = completeness - prior_completeness

    if d_comp is not None and d_comp <= -0.15:
        return "reporting_artifact"

    if positivity_abs_dev > 0:
        if d_tests_pct <= -0.15 and d_conf <= 0:
            return "testing_down"
        if d_conf > 0 and d_tests_pct >= -0.05:
            return "genuine_increased_positivity"
        return "mixed"
    if positivity_abs_dev < 0:
        if d_tests_pct >= 0.15 and d_conf >= 0:
            return "testing_up_dilution"
        if d_conf < 0 and d_tests_pct <= 0.05:
            return "genuine_decreased_positivity"
        return "mixed"
    return "unchanged"


def score_observation(
    row: dict,
    panel_index: dict[tuple[str, str], dict],
    *,
    field: str = "malaria_positivity",
) -> dict[str, Any]:
    district = row["district_slug"]
    period = row["source_period"]
    prior = prior_same_month_rows(panel_index, district, period)
    leak = leakage_check(period, prior, district)
    if not leak["passed"]:
        raise ValueError(f"baseline leakage for {district} {period}: {leak['violations']}")

    prior_values = _values(prior, field)
    baselines = expanding_baselines(prior_values)
    observed = row.get(field)
    measures = anomaly_measures(observed, baselines)
    n_prior = baselines["n_prior"]
    completeness = row.get("facility_completeness")
    tests = row.get("malaria_tests")
    insufficient_history = n_prior < MIN_PRIOR_YEARS_PRIMARY
    tests_not_positive = tests is None or tests <= 0 or observed is None
    low_completeness = completeness is None or completeness < COMPLETENESS_MIN
    primary_eligible = (
        not insufficient_history
        and not tests_not_positive
        and not low_completeness
        and leak["passed"]
    )

    prior_year_row = prior[-1] if prior else None
    bias = classify_testing_bias(
        positivity_abs_dev=measures.get("abs_dev_median") if field == "malaria_positivity" else None,
        confirmed=row.get("malaria_confirmed"),
        tests=tests,
        prior_confirmed=None if prior_year_row is None else prior_year_row.get("malaria_confirmed"),
        prior_tests=None if prior_year_row is None else prior_year_row.get("malaria_tests"),
        completeness=completeness,
        prior_completeness=None if prior_year_row is None else prior_year_row.get("facility_completeness"),
    )

    conventional_alert = bool(
        primary_eligible
        and measures.get("robust_z") is not None
        and measures["robust_z"] >= ROBUST_Z_CONVENTION
    )
    mild_alert = bool(
        primary_eligible
        and measures.get("robust_z") is not None
        and measures["robust_z"] >= MILD_Z_CONVENTION
    )

    return {
        "district_slug": district,
        "source_period": period,
        "calendar_month": row["calendar_month"],
        "year": row["year"],
        "field": field,
        "observed": observed,
        "malaria_confirmed": row.get("malaria_confirmed"),
        "malaria_tests": tests,
        "facility_completeness": completeness,
        "rainfall_mm": row.get("rainfall_mm"),
        "temperature_c": row.get("temperature_c"),
        "humidity_percent": row.get("humidity_percent"),
        "n_prior": n_prior,
        "baseline_periods": [r["source_period"] for r in prior],
        "max_baseline_period": prior[-1]["source_period"] if prior else None,
        "leakage_passed": leak["passed"],
        "insufficient_history": insufficient_history,
        "tests_not_positive": tests_not_positive,
        "low_completeness": low_completeness,
        "primary_eligible": primary_eligible,
        "zero_dispersion": baselines["zero_dispersion"],
        "prior_year": baselines["prior_year"],
        "expanding_mean": baselines["expanding_mean"],
        "expanding_median": baselines["expanding_median"],
        "expanding_stdev": baselines["expanding_stdev"],
        "expanding_mad": baselines["expanding_mad"],
        **{k: v for k, v in measures.items() if k != "observed"},
        "testing_bias_class": bias,
        "conventional_alert": conventional_alert,
        "mild_alert": mild_alert,
        "alert_rule": (
            "robust_z >= 2.0 AND n_prior >= 3 AND completeness >= 0.20 AND tests > 0"
            if conventional_alert else None
        ),
        "alert_rule_source": "statistical_convention",
    }


def score_panel(rows: list[dict], *, field: str = "malaria_positivity") -> list[dict]:
    panel_index = index_panel(rows)
    scored = [score_observation(row, panel_index, field=field) for row in rows]
    scored.sort(key=lambda r: (r["source_period"], r["district_slug"]))
    _attach_lags_and_climate(scored, rows, panel_index)
    return scored


def _attach_lags_and_climate(
    scored: list[dict],
    rows: list[dict],
    panel_index: dict[tuple[str, str], dict],
) -> None:
    score_index = {(r["district_slug"], r["source_period"]): r for r in scored}
    for row in scored:
        district = row["district_slug"]
        period = row["source_period"]
        prev = calendar_prev(period)
        nxt = calendar_next(period)
        lag1 = score_index.get((district, prev))
        lead1 = score_index.get((district, nxt))
        lag2_period = calendar_prev(period, 2)
        lag2_raw = panel_index.get((district, lag2_period))
        row["lag1_period"] = prev if lag1 is not None else None
        row["lead1_period"] = nxt if lead1 is not None else None
        row["lag1_observed"] = None if lag1 is None else lag1.get("observed")
        row["lag1_robust_z"] = None if lag1 is None else lag1.get("robust_z")
        row["lag1_conventional_alert"] = None if lag1 is None else lag1.get("conventional_alert")
        row["lead1_observed"] = None if lead1 is None else lead1.get("observed")
        row["lead1_robust_z"] = None if lead1 is None else lead1.get("robust_z")
        row["lead1_confirmed"] = None if lead1 is None else lead1.get("malaria_confirmed")
        row["lead1_tests"] = None if lead1 is None else lead1.get("malaria_tests")
        row["lead1_primary_eligible"] = None if lead1 is None else lead1.get("primary_eligible")
        row["sustained_mild_alert"] = bool(
            row.get("mild_alert") and lag1 is not None and lag1.get("mild_alert")
        )
        row["consecutive_conventional_alert"] = bool(
            row.get("conventional_alert") and lag1 is not None and lag1.get("conventional_alert")
        )

        rain_prior = prior_same_month_rows(panel_index, district, period)
        rain_base = expanding_baselines(_values(rain_prior, "rainfall_mm"))
        temp_base = expanding_baselines(_values(rain_prior, "temperature_c"))
        hum_base = expanding_baselines(_values(rain_prior, "humidity_percent"))
        rain = row.get("rainfall_mm")
        temp = row.get("temperature_c")
        hum = row.get("humidity_percent")
        row["rainfall_baseline_median"] = rain_base["expanding_median"]
        row["rainfall_anomaly"] = (
            None if rain is None or rain_base["expanding_median"] is None
            else rain - rain_base["expanding_median"]
        )
        row["temperature_anomaly"] = (
            None if temp is None or temp_base["expanding_median"] is None
            else temp - temp_base["expanding_median"]
        )
        row["humidity_anomaly"] = (
            None if hum is None or hum_base["expanding_median"] is None
            else hum - hum_base["expanding_median"]
        )
        lag1_raw = panel_index.get((district, prev))
        parts = [row.get("rainfall_mm")]
        if lag1_raw:
            parts.append(lag1_raw.get("rainfall_mm"))
        else:
            parts.append(None)
        if lag2_raw:
            parts.append(lag2_raw.get("rainfall_mm"))
        else:
            parts.append(None)
        row["three_month_rainfall"] = (
            sum(parts) if all(p is not None for p in parts) else None
        )
        row["lag1_rainfall_mm"] = None if lag1_raw is None else lag1_raw.get("rainfall_mm")
        row["lag1_rainfall_anomaly"] = None if lag1 is None else lag1.get("rainfall_anomaly")
        # Explicit: t+1 climate is never attached.
        row["lead1_rainfall_mm"] = None


def baseline_stability_table(scored: list[dict]) -> list[dict]:
    """How much the expanding seasonal median moves when another year is added."""
    by_key: dict[tuple[str, int], list[dict]] = {}
    for row in scored:
        if row.get("observed") is None:
            continue
        by_key.setdefault((row["district_slug"], row["calendar_month"]), []).append(row)
    out = []
    for (slug, month), group in sorted(by_key.items()):
        group = sorted(group, key=lambda r: r["source_period"])
        medians = [
            r["expanding_median"]
            for r in group
            if r.get("n_prior", 0) >= MIN_PRIOR_YEARS_PRIMARY and r.get("expanding_median") is not None
        ]
        deltas = [abs(medians[i] - medians[i - 1]) for i in range(1, len(medians))]
        mads = [
            r["expanding_mad"]
            for r in group
            if r.get("n_prior", 0) >= MIN_PRIOR_YEARS_PRIMARY and r.get("expanding_mad") is not None
        ]
        n_priors = [r["n_prior"] for r in group if r.get("observed") is not None]
        out.append({
            "district_slug": slug,
            "calendar_month": month,
            "n_scored_months": len(group),
            "max_n_prior": max(n_priors) if n_priors else 0,
            "min_n_prior_when_primary": (
                min(
                    r["n_prior"] for r in group
                    if r.get("n_prior", 0) >= MIN_PRIOR_YEARS_PRIMARY
                ) if any(r.get("n_prior", 0) >= MIN_PRIOR_YEARS_PRIMARY for r in group) else None
            ),
            "median_of_expanding_medians": _median(medians),
            "max_abs_median_step": max(deltas) if deltas else None,
            "mean_abs_median_step": _mean(deltas),
            "mean_mad": _mean(mads),
            "unstable_high_step": bool(deltas and max(deltas) >= 0.05),
            "high_mad": bool(mads and (_mean(mads) or 0) >= 0.05),
        })
    return out


def percentile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if q <= 0:
        return ordered[0]
    if q >= 1:
        return ordered[-1]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def audit_no_future_in_baselines(scored: list[dict]) -> dict[str, Any]:
    violations = []
    for row in scored:
        period = row["source_period"]
        for pe in row.get("baseline_periods") or []:
            if pe >= period:
                violations.append({
                    "district": row["district_slug"],
                    "period": period,
                    "illegal_baseline_period": pe,
                })
        if row.get("lead1_rainfall_mm") is not None:
            violations.append({
                "district": row["district_slug"],
                "period": period,
                "illegal": "t+1 climate attached",
            })
    return {"passed": len(violations) == 0, "n_violations": len(violations), "violations": violations[:20]}

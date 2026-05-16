"""
Flood Dashboard Service
========================

Translates the static Sierra Leone flood zone catalog into the
real-time view that powers the Flood Atlas dashboard.

Responsibilities
----------------
1. **Synthesise district-level live signals** — current rainfall
   intensity, rainfall in the last 24 hours, soil saturation, river
   stage and tide stage. The values follow the Sierra Leone rainy-
   season climatology (May–October peak, August driest in Bo/Kenema
   on the coast pattern, deep wet season for Kambia / Bonthe). They
   wobble per-call so the dashboard "ticks" without a real sensor
   feed, but stay inside plausible ranges.
2. **Run the flood-risk model per zone** — combines each zone's
   static inputs (elevation, drainage, distance to water, typical
   saturation) with its district's live signals and dispatches to
   ``models.flood_risk.predict``.
3. **Produce a 24-hour outlook** — short hourly trajectory derived
   from the current signal state and a simple decay/growth heuristic
   so the UI can display a forecast strip per zone without us claiming
   numerical precision we can't deliver from a static dataset.

This module is deliberately deterministic-ish: it accepts an optional
``seed`` and an optional ``signal_overrides`` dict so the
``/strategic/flood-forecast`` endpoint can run "what-if" scenarios
(e.g. "double the rainfall in Western Area Urban"). When no overrides
are supplied, signals jitter using the wall clock so a polling
dashboard sees movement.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from data import sierra_leone as sl
from models import flood_risk


# ----------------------------------------------------------------------
# District-level signal synthesis
# ----------------------------------------------------------------------

def _seasonal_factor(now: datetime, district: dict) -> float:
    """Return a 0..1 factor describing how 'in season' we are.

    Climatology peaks in August (month 8). Outside the rainy-season
    window we return a small floor so dry-season checks still produce
    plausible (low) signals.
    """
    start, end = district["rainy_season_months"]
    m = now.month
    if not (start <= m <= end):
        # Dry season — small residual moisture
        return 0.10
    # Triangle peak around mid-season
    span = end - start
    mid = (start + end) / 2.0
    distance_from_peak = abs(m - mid)
    return max(0.25, 1.0 - distance_from_peak / max(1.0, span / 2.0))


def _district_signal(
    district_id: str,
    now: datetime,
    rng: random.Random,
    overrides: Optional[dict] = None,
) -> dict:
    """Compose a synthetic but plausible live-signal vector for a
    district. ``overrides`` is a dict like
    ``{"rainfall_intensity_mult": 1.5, "saturation_offset": 10}``
    used by the scenario simulator.
    """
    district = sl.DISTRICTS[district_id]
    season = _seasonal_factor(now, district)

    # Daily rhythm: tropical convective storms peak mid-afternoon.
    hour = now.hour + now.minute / 60.0
    diurnal = 0.4 + 0.6 * max(0.0, math.sin(math.pi * (hour - 6) / 12))
    if hour < 6 or hour > 22:
        diurnal *= 0.4

    base_intensity = 30.0 * season * diurnal       # mm/hr
    base_24h = district["typical_aug_rainfall_mm"] / 31 * (0.7 + season)
    base_saturation = 35 + 50 * season             # %

    # Wobble per call — 12-minute granularity to look "live" in UI.
    minute_bucket = (now.minute // 12) + now.day
    wobble_rng = random.Random(hash((district_id, now.hour, minute_bucket, rng.random())))

    rainfall_intensity = base_intensity * wobble_rng.uniform(0.65, 1.35)
    rainfall_24h = base_24h * wobble_rng.uniform(0.75, 1.30)
    soil_saturation = min(100.0, max(5.0, base_saturation + wobble_rng.uniform(-12, 14)))

    # Coastal districts get a tide-stage signal (purely indicative).
    coastal = district_id in {
        "western_area_urban", "western_area_rural",
        "bonthe", "moyamba", "port_loko",
    }
    tide_stage = "n/a"
    if coastal:
        # 12.4-hour semi-diurnal tide.
        phase = ((hour / 12.4) * 2 * math.pi) % (2 * math.pi)
        tide_height = math.sin(phase)
        if tide_height > 0.6:
            tide_stage = "high"
        elif tide_height < -0.6:
            tide_stage = "low"
        else:
            tide_stage = "rising" if math.cos(phase) > 0 else "falling"

    # River stage (relative to bankfull) — climbs with rainfall_24h.
    river_stage_pct = min(120.0, 40 + 0.45 * rainfall_24h + wobble_rng.uniform(-5, 8))

    if overrides:
        if "rainfall_intensity_mult" in overrides:
            rainfall_intensity *= float(overrides["rainfall_intensity_mult"])
        if "rainfall_24h_mult" in overrides:
            rainfall_24h *= float(overrides["rainfall_24h_mult"])
        if "saturation_offset" in overrides:
            soil_saturation = min(100.0, max(0.0,
                soil_saturation + float(overrides["saturation_offset"])))

    return {
        "district_id": district_id,
        "district_name": district["name"],
        "rainfall_intensity_mm_h": round(rainfall_intensity, 1),
        "rainfall_24h_mm": round(rainfall_24h, 1),
        "soil_saturation_pct": round(soil_saturation, 1),
        "river_stage_pct_bankfull": round(river_stage_pct, 1),
        "tide_stage": tide_stage,
        "season_factor": round(season, 2),
    }


def _zone_prediction(zone: dict, signal: dict) -> dict:
    """Run flood_risk.predict for one zone using its static
    geomorphology + the district's live signals (with the zone's
    typical baseline saturation taken into account)."""
    saturation = max(signal["soil_saturation_pct"], zone["typical_saturation_pct"] - 5)
    result = flood_risk.predict(
        rainfall_intensity=signal["rainfall_intensity_mm_h"],
        rainfall_24h=signal["rainfall_24h_mm"],
        elevation=zone["elevation_m"],
        drainage_quality=zone["drainage_quality"],
        proximity_water=zone["distance_to_water_km"],
        soil_saturation=saturation,
    )
    return {
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "factors": list(result.factors),
        "recommendations": list(result.recommendations),
        "estimated_impact": result.estimated_impact,
        "contributions": {
            "rainfall": result.rainfall_contrib,
            "terrain": result.terrain_contrib,
            "drainage": result.drainage_contrib,
            "proximity": result.proximity_contrib,
            "saturation": result.saturation_contrib,
        },
    }


def _zone_forecast(zone: dict, signal: dict, hours: int = 24) -> list[dict]:
    """Hourly outlook for one zone over the next ``hours`` hours.

    The trajectory follows a simple physical heuristic:
    * Rainfall intensity decays exponentially toward 30% of current.
    * Soil saturation rises while it's raining and drains slowly
      afterwards.
    * Risk is recomputed with these projected inputs each hour.
    """
    hourly = []
    decay = 0.85
    intensity = signal["rainfall_intensity_mm_h"]
    saturation = signal["soil_saturation_pct"]
    rainfall_24h = signal["rainfall_24h_mm"]
    for h in range(1, hours + 1):
        intensity = max(0.4, intensity * decay)
        saturation = max(0.0, saturation + intensity * 0.10 - 0.6)
        # Slide rainfall_24h forward: drop oldest hour, add new.
        rainfall_24h = max(0.0, rainfall_24h - rainfall_24h / 24 + intensity)
        result = flood_risk.predict(
            rainfall_intensity=intensity,
            rainfall_24h=rainfall_24h,
            elevation=zone["elevation_m"],
            drainage_quality=zone["drainage_quality"],
            proximity_water=zone["distance_to_water_km"],
            soil_saturation=saturation,
        )
        hourly.append({
            "hour_offset": h,
            "rainfall_intensity_mm_h": round(intensity, 1),
            "soil_saturation_pct": round(saturation, 1),
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
        })
    return hourly


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def snapshot(overrides: Optional[dict] = None, seed: Optional[int] = None) -> dict:
    """Return the full Flood Atlas snapshot.

    Parameters
    ----------
    overrides:
        Either a flat dict applied to every district, or a nested
        dict ``{district_id: {...}}`` with per-district override
        knobs. Recognised keys per district:
        ``rainfall_intensity_mult`` (float, default 1.0),
        ``rainfall_24h_mult`` (float, default 1.0),
        ``saturation_offset`` (float, default 0.0).
    seed:
        Optional seed for the live-signal jitter so callers can pin a
        snapshot for screenshots / tests.
    """
    now = datetime.now(timezone.utc)
    rng = random.Random(seed) if seed is not None else random.Random()

    overrides = overrides or {}
    nested = any(isinstance(v, dict) for v in overrides.values())

    signals = {}
    for did in sl.DISTRICTS:
        district_overrides = overrides.get(did, {}) if nested else overrides
        signals[did] = _district_signal(did, now, rng, district_overrides)

    zones = []
    for zone in sl.list_zones():
        signal = signals[zone["district"]]
        prediction = _zone_prediction(zone, signal)
        zones.append({
            "id": zone["id"],
            "name": zone["name"],
            "district": zone["district"],
            "district_name": signal["district_name"],
            "region": zone["region"],
            "lat": zone["lat"],
            "lng": zone["lng"],
            "elevation_m": zone["elevation_m"],
            "drainage_quality": zone["drainage_quality"],
            "distance_to_water_km": zone["distance_to_water_km"],
            "water_body": zone["water_body"],
            "urban_type": zone["urban_type"],
            "population": zone["population"],
            "signal": signal,
            "prediction": prediction,
        })

    # Aggregate KPIs for the dashboard header.
    risk_scores = [z["prediction"]["risk_score"] for z in zones]
    population_at_risk = sum(
        z["population"] for z in zones if z["prediction"]["risk_score"] >= 0.40
    )
    high_risk_zones = [z for z in zones if z["prediction"]["risk_score"] >= 0.60]
    severe_zones = [z for z in zones if z["prediction"]["risk_score"] >= 0.80]
    avg_rain_intensity = round(sum(
        s["rainfall_intensity_mm_h"] for s in signals.values()
    ) / len(signals), 1)
    avg_saturation = round(sum(
        s["soil_saturation_pct"] for s in signals.values()
    ) / len(signals), 1)
    river_stage_avg = round(sum(
        s["river_stage_pct_bankfull"] for s in signals.values()
    ) / len(signals), 1)

    return {
        "generated_at": now.isoformat(),
        "country": "Sierra Leone",
        "bounds": sl.country_bounds(),
        "kpis": {
            "zones_monitored": len(zones),
            "districts_monitored": len(signals),
            "population_in_catalog": sum(z["population"] for z in zones),
            "population_at_risk": population_at_risk,
            "high_risk_zones": len(high_risk_zones),
            "severe_zones": len(severe_zones),
            "avg_rainfall_intensity_mm_h": avg_rain_intensity,
            "avg_soil_saturation_pct": avg_saturation,
            "avg_river_stage_pct_bankfull": river_stage_avg,
            "max_zone_risk": round(max(risk_scores), 4) if risk_scores else 0.0,
            "mean_zone_risk": round(sum(risk_scores) / len(risk_scores), 4) if risk_scores else 0.0,
        },
        "districts": list(signals.values()),
        "zones": zones,
    }


def zone_forecast(zone_id: str, hours: int = 24, overrides: Optional[dict] = None) -> dict:
    """Return a 24h hourly outlook for a single zone."""
    zone = sl.get_zone(zone_id)
    if not zone:
        return {"error": "unknown_zone", "zone_id": zone_id}
    now = datetime.now(timezone.utc)
    signal = _district_signal(
        zone["district"], now,
        random.Random(),
        (overrides or {}),
    )
    return {
        "zone_id": zone_id,
        "name": zone["name"],
        "generated_at": now.isoformat(),
        "current": {**signal, **_zone_prediction(zone, signal)},
        "hourly": _zone_forecast(zone, signal, hours=hours),
        "horizon_end": (now + timedelta(hours=hours)).isoformat(),
    }

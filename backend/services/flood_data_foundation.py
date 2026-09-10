"""
Flood-event DATA FOUNDATION — specification and schema validation only.

Does NOT train a model.
Does NOT create rainfall-derived flood labels.
Does NOT convert missing observations into non-flood.
Does NOT modify flood_risk.py, flood_dashboard.py, weather_api.py,
flood_model.joblib, the risk engine, dashboard, or live APIs.
Does NOT treat synthetic CHEWS tables as observations.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parent.parent

PROTECTED_PATHS = {
    "flood_risk_py": BACKEND / "models" / "flood_risk.py",
    "flood_dashboard_py": BACKEND / "services" / "flood_dashboard.py",
    "weather_api_py": BACKEND / "services" / "weather_api.py",
    "flood_model_joblib": BACKEND / "data" / "trained_models" / "flood_model.joblib",
    "flood_risk_v1_joblib": BACKEND / "data" / "04_ai" / "models" / "flood_risk_v1_20260731.joblib",
}

FLOOD_ZONES = BACKEND / "data" / "reference" / "flood_zones.json"
MFL_CORE = BACKEND / "data" / "01_raw" / "master_facility_list" / "moh_dhis2_core_health_facilities.csv"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_YEAR = re.compile(r"^\d{4}$")

FIELD_PROVENANCE = {
    "event_id": "observed",
    "event_start": "observed",
    "event_end": "observed",
    "location_id": "derived",
    "location_name": "observed",
    "district": "observed",
    "chiefdom": "observed",
    "latitude": "observed",
    "longitude": "observed",
    "geographic_precision": "derived",
    "mapping_method": "derived",
    "mapping_uncertainty": "derived",
    "event_type": "observed",
    "severity": "estimated",
    "source": "observed",
    "source_url": "observed",
    "source_confidence": "estimated",
    "verified": "observed",
    "verification_date": "observed",
    "reported_by": "observed",
    "affected_population": "observed",
    "affected_households": "observed",
    "affected_facilities": "observed",
    "deaths": "observed",
    "displacement": "observed",
    "infrastructure_damage": "observed",
    "inundation_area_km2": "estimated",
    "notes": "observed",
    "label_origin": "observed",
}

REQUIRED_FOR_LEAD_TIME = ("event_id", "event_start", "district", "source", "event_type")
SYNTHETIC_SOURCE_MARKERS = ("synthetic", "chews_training", "generated", "rainfall_threshold")
FORBIDDEN_LABEL_ORIGINS = frozenset({
    "rainfall_threshold",
    "rainfall_percentile",
    "synthetic_flood_occurred",
    "missing_as_nonflood",
    "community_csv_chews_202607",
})
EVENT_TYPES = frozenset({
    "flood", "flash_flood", "riverine_flood", "coastal_flood",
    "landslide_with_flood", "unknown",
})
GEO_JOIN_PRIORITY = (
    "event_coordinates",
    "named_community_match_to_flood_zone",
    "named_community_unmatched",
    "district_polygon",
    "district_centroid_fallback",
)

VERDICT_B = "B"
VERDICT_B_LABEL = "REAL EVENT DATA SOURCE IDENTIFIED — ACQUISITION REQUIRED"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missing_not_nonflood(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().lower() in {"na", "nan", "null", "none", "unknown"}:
        return None
    return value


def parse_iso_date(value: Any) -> Optional[date]:
    text = missing_not_nonflood(value)
    if text is None:
        return None
    text = str(text).strip()
    if not ISO_DATE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def weather_alignment_windows(event_start: date) -> dict[str, Any]:
    """
    Past-only weather windows relative to event_start (local calendar day t0).

    Lead-time features use days strictly before t0.
    Same-day rainfall is contemporaneous context, not a forecast feature.
    Days after t0 are forbidden.
    """
    t0 = event_start
    t_minus_1 = t0 - timedelta(days=1)
    t_minus_3_start = t0 - timedelta(days=3)
    t_minus_7_start = t0 - timedelta(days=7)
    return {
        "t0_event_start": t0.isoformat(),
        "lead_time_features": {
            "t-1": {
                "start": t_minus_1.isoformat(),
                "end": t_minus_1.isoformat(),
                "includes_t0": False,
                "variables": ["precipitation_sum"],
            },
            "t-3": {
                "start": t_minus_3_start.isoformat(),
                "end": t_minus_1.isoformat(),
                "includes_t0": False,
                "variables": ["precipitation_sum"],
            },
            "t-7": {
                "start": t_minus_7_start.isoformat(),
                "end": t_minus_1.isoformat(),
                "includes_t0": False,
                "variables": ["precipitation_sum"],
            },
        },
        "contemporaneous_context_not_lead_time": {
            "t0": {
                "start": t0.isoformat(),
                "end": t0.isoformat(),
                "use": "same-day detection context only; not a next-day forecast feature",
            }
        },
        "forbidden": {
            "t+1_and_later": True,
            "reason": "Future rainfall cannot enter a historical early-warning feature.",
        },
        "preferred_coordinates": "event latitude/longitude or matched flood-zone lat/lng",
        "fallback_coordinates": "district centroid — must set mapping_uncertainty=high",
        "do_not_use_as_event_label": True,
    }


def geographic_join_plan(event: dict) -> dict[str, Any]:
    lat = missing_not_nonflood(event.get("latitude"))
    lon = missing_not_nonflood(event.get("longitude"))
    location_name = missing_not_nonflood(event.get("location_name"))
    district = missing_not_nonflood(event.get("district"))
    if lat is not None and lon is not None:
        method = "event_coordinates"
        uncertainty = "low"
    elif location_name:
        method = "named_community_match_to_flood_zone"
        uncertainty = "medium"
    elif district:
        method = "district_centroid_fallback"
        uncertainty = "high"
    else:
        method = "unmapped"
        uncertainty = "unusable"
    return {
        "method": method,
        "mapping_uncertainty": uncertainty,
        "priority": list(GEO_JOIN_PRIORITY),
        "centroid_used_silently": False,
        "notes": (
            "Do not assign every event to a district centroid. "
            "Centroid weather is a last-resort fallback and must be flagged."
        ),
    }


def validate_flood_event(event: dict) -> dict[str, Any]:
    """Validate a future canonical event record. Does not invent values."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(event, dict):
        return {"ok": False, "lead_time_eligible": False, "errors": ["record_not_an_object"], "warnings": []}

    origin = missing_not_nonflood(event.get("label_origin"))
    if origin in FORBIDDEN_LABEL_ORIGINS:
        errors.append("rainfall_or_synthetic_label_origin_forbidden")

    source = str(missing_not_nonflood(event.get("source")) or "").lower()
    if any(marker in source for marker in SYNTHETIC_SOURCE_MARKERS):
        errors.append("synthetic_source_cannot_be_an_observation")
        if event.get("verified") is True:
            errors.append("synthetic_source_cannot_be_verified")

    event_id = missing_not_nonflood(event.get("event_id"))
    if not event_id:
        errors.append("event_id_required")

    start = parse_iso_date(event.get("event_start"))
    start_raw = missing_not_nonflood(event.get("event_start"))
    temporal_grain = "unknown"
    if start is not None:
        temporal_grain = "day"
    elif start_raw and ISO_YEAR.match(str(start_raw).strip()):
        temporal_grain = "year"
        warnings.append("year_only_start_not_usable_for_lead_time")
    elif start_raw:
        errors.append("event_start_must_be_iso_date_or_year")
    else:
        errors.append("event_start_required")

    end = parse_iso_date(event.get("event_end"))
    if end is not None and start is not None and end < start:
        errors.append("event_end_before_event_start")

    district = missing_not_nonflood(event.get("district"))
    location_name = missing_not_nonflood(event.get("location_name"))
    lat = missing_not_nonflood(event.get("latitude"))
    lon = missing_not_nonflood(event.get("longitude"))
    if district is None and location_name is None and (lat is None or lon is None):
        errors.append("location_required_district_or_name_or_coordinates")

    event_type = missing_not_nonflood(event.get("event_type"))
    if event_type is None:
        errors.append("event_type_required")
    elif event_type not in EVENT_TYPES:
        errors.append("event_type_unknown")

    if missing_not_nonflood(event.get("source")) is None:
        errors.append("source_required")

    for field in (
        "affected_population", "affected_households", "deaths",
        "displacement", "inundation_area_km2",
    ):
        if field in event and event[field] == 0 and event.get("label_origin") == "missing_as_nonflood":
            errors.append(f"{field}_zero_from_missing_forbidden")

    if event.get("flood_occurred") is not None:
        errors.append("do_not_store_synthetic_flood_occurred_on_canonical_events")

    geo = geographic_join_plan(event)
    lead_time_eligible = (
        not errors
        and temporal_grain == "day"
        and district is not None
        and geo["method"] != "unmapped"
    )
    return {
        "ok": len(errors) == 0,
        "lead_time_eligible": lead_time_eligible,
        "temporal_grain": temporal_grain,
        "geographic_join": geo,
        "errors": errors,
        "warnings": warnings,
    }


def target_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "A",
            "name": "dated_observed_flood_event",
            "definition": (
                "A flood, flash flood, riverine flood, coastal flood, or flood-associated "
                "landslide that a named authority recorded at a place with a calendar date."
            ),
            "spatial_grain": "community / named settlement, falling back to district only if flagged",
            "temporal_grain": "calendar day (start; end if known)",
            "lead_time": "hours–days before event_start using past-only rainfall windows",
            "required_data": "NDMA register or equivalent dated assessment; location at least district",
            "limitations": "Register access required; under-reporting of minor events; delayed assessments",
            "recommended": True,
        },
        {
            "id": "B",
            "name": "geographic_inundation_event",
            "definition": "Satellite-mapped surface water beyond permanent water over a known interval.",
            "spatial_grain": "raster (e.g. 250 m MODIS GFD) or Copernicus EMS polygons",
            "temporal_grain": "event window (often days), cloud-limited",
            "lead_time": "poor for Freetown flash floods; better for prolonged riverine water",
            "required_data": "GFD / DFO / Copernicus EMS activations",
            "limitations": "Misses many urban flash floods; 2017 Freetown event was mudflow/landslide mapping",
            "recommended": False,
            "role": "independent spatial corroboration, not the primary CHEWS target",
        },
        {
            "id": "C",
            "name": "community_level_flood_occurrence",
            "definition": "Same as A, restricted to a named community matching flood_zones or NDMA place names.",
            "spatial_grain": "community",
            "temporal_grain": "day",
            "lead_time": "same as A",
            "required_data": "community names in the source, not synthetic CHW CSV",
            "limitations": "Name matching is uncertain; 23 CHEWS zones do not cover all NDMA places",
            "recommended": True,
            "role": "preferred grain of target A when the source names a community",
        },
        {
            "id": "D",
            "name": "facility_accessibility_disruption",
            "definition": "A health facility unreachable or damaged because of flood.",
            "spatial_grain": "MFL facility point",
            "temporal_grain": "day",
            "lead_time": "operational overlay after an event is known",
            "required_data": "dated facility closure/damage records joined to MFL coordinates",
            "limitations": "No such outcomes exist in CHEWS today",
            "recommended": False,
            "role": "future health-connection layer, not the first target",
        },
        {
            "id": "E",
            "name": "district_level_flood_occurrence",
            "definition": "At least one documented flood in a district on a date.",
            "spatial_grain": "district (admin-2)",
            "temporal_grain": "day or multi-day window",
            "lead_time": "weaker: centroid weather, mixed event types",
            "required_data": "district named in NDMA/IFRC reports",
            "limitations": "Hides intra-district differences; centroid weather is a high-uncertainty fallback",
            "recommended": False,
            "role": "fallback when community is unknown",
        },
        {
            "id": "F",
            "name": "flood_severity_category",
            "definition": "Ordinal impact class (e.g. NDMA/IFRC assessment grade).",
            "spatial_grain": "inherits from A/C/E",
            "temporal_grain": "event",
            "lead_time": "not a detection target",
            "required_data": "source-provided grade; otherwise estimated and labelled as such",
            "limitations": "CHEWS must not invent severity from rainfall",
            "recommended": False,
            "role": "optional observed field if the source grades the event",
        },
    ]


def sufficiency_requirements() -> dict[str, Any]:
    return {
        "A_statistical_rule_backtesting": {
            "purpose": "Estimate miss rate, false-alarm rate, and lead time of a disclosed rainfall/zone rule.",
            "minimum": {
                "wet_seasons": 3,
                "dated_community_or_zone_events": 30,
                "districts_or_distinct_regimes": (
                    "≥8 districts, or Western Area plus ≥4 inland/coastal districts "
                    "so Freetown flash flood is not the only regime"
                ),
                "event_types": "at least flash vs riverine/coastal if claiming a national rule",
                "non_event_rule": (
                    "Silent days are negatives ONLY if the same source would have recorded "
                    "an event. Missing register coverage is not a non-flood label."
                ),
            },
            "why": (
                "Three wet seasons prevent fitting a rule to one unusual year. "
                "About 30 dated events is the smallest count where a miss rate is even "
                "interpretable (e.g. 5 misses in 30 is 17%, with a still-wide confidence "
                "interval). Fewer than ~15 day-dated events cannot tell a useless rule "
                "from noise. Geographic diversity is required because coastal Bonthe, "
                "inland rivers, and Freetown informal settlements are different processes."
            ),
        },
        "B_controlled_shadow_validation": {
            "purpose": "Observe a frozen rainfall/zone rule on refreshed weather without live CHEWS alerts.",
            "minimum": {
                "includes": "all of A",
                "weather": "daily precip at event/zone coordinates covering those seasons (past-only)",
                "corroboration": "subset of events also in IFRC DREF / ReliefWeb or equivalent",
                "isolation": "no dashboard, risk engine, or notifications",
            },
            "why": (
                "Malaria shadow was possible because DHIS2 positivity already existed. "
                "Flood shadow requires the event list first; weather without events is not a flood shadow."
            ),
        },
        "C_supervised_ml": {
            "purpose": "Only if a rule baseline is already backtested and remaining error is not a simple rain cut.",
            "minimum": {
                "includes": "A and B completed, with a published rule baseline",
                "wet_seasons": 5,
                "dated_events": 100,
                "districts": 10,
                "negatives": "documented daily surveillance, never missing-as-zero",
                "split": "chronological, never random",
                "must_beat": "lead time and missed-event rate of the rule, not accuracy",
            },
            "why": (
                "Flood days are rare. A classifier rewarded for accuracy will predict non-flood. "
                "Five seasons and ~100 events still may not justify ML; they are a floor for "
                "even asking the question. Default remains the simpler rule if ML does not win "
                "on lead time and misses."
            ),
            "currently_justified": False,
        },
    }


def potential_external_sources() -> list[dict[str, Any]]:
    return [
        {
            "name": "NDMA disaster register and field assessments",
            "url": "https://ndma.gov.sl/",
            "examples": [
                "https://ndma.gov.sl/2024/09/24/4259-zsqong/",
                "https://ndma.gov.sl/2023/09/15/3818-draunc/",
                "https://ndma.gov.sl/2022/09/20/ndma-responds-to-bonthe-district-flood-victims-assesses-impact-on-livelihoods-and-infrastructure/",
            ],
            "years_publicly_illustrated": "2022–2024 posts; register exists from NDMA creation (2021) per Audit Service SL 2025",
            "geography": "national; community and chiefdom names in assessments",
            "attributes": "households, people affected, buildings, farmland, dates of incident and assessment",
            "accessibility": "Assessment pages are public; the disaster register is NOT a bulk public download — partnership/acquisition required",
            "ground_truth": "Best primary source if a dated extract can be obtained. Not in the CHEWS repo.",
            "in_repo": False,
        },
        {
            "name": "IFRC DREF / Sierra Leone Red Cross situation reports on ReliefWeb",
            "url": "https://reliefweb.int/report/sierra-leone/sierra-leone-floods-2024-dref-final-report-mdrsl016",
            "examples": [
                "https://reliefweb.int/report/sierra-leone/sierra-leone-floods-2024-dref-final-report-mdrsl016",
            ],
            "years_publicly_illustrated": "at least 2022 (MDRSL013) and 2024 (MDRSL016)",
            "geography": "named communities and districts",
            "attributes": "start window, people/households, deaths, joint NDMA assessments",
            "accessibility": "Public humanitarian reports. Not a complete national register.",
            "ground_truth": "Independent corroboration of major events. Too sparse alone for backtesting.",
            "in_repo": False,
        },
        {
            "name": "EM-DAT (CRED/UCLouvain)",
            "url": "https://public.emdat.be/",
            "years": "1900–present, weekly updates",
            "geography": "country-level; optional lat/lon and river basin, often missing for floods",
            "attributes": "start/end when known, deaths, affected, disaster subtype",
            "accessibility": "Free non-commercial after registration; HDX country profiles are yearly aggregates only",
            "ground_truth": "Independent check on HIGH-IMPACT events. Not community EWS grain.",
            "in_repo": False,
        },
        {
            "name": "Dartmouth Flood Observatory / Global Flood Database (MODIS 2000–2018)",
            "url": "https://floodobservatory.colorado.edu/",
            "secondary": "https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1",
            "years": "DFO large-flood archive from 1985; GFD mapped subset 2000–2018",
            "geography": "event polygons / 250 m raster; large floods only",
            "accessibility": "Research/Earth Engine; HDX hosts an older DFO extract",
            "ground_truth": "Supporting inundation, not CHEWS primary target. Urban flash floods often unmapped.",
            "in_repo": False,
        },
        {
            "name": "Copernicus EMS Rapid Mapping",
            "url": "https://emergency.copernicus.eu/",
            "examples": ["EMSR222 Regent mudflow 15 Aug 2017"],
            "years": "activation-based, not a continuous Sierra Leone series",
            "geography": "AOI polygons for activated disasters",
            "accessibility": "Public map products",
            "ground_truth": "High-value for 2017 landslide/mudflow; not a national flood time series",
            "in_repo": False,
        },
        {
            "name": "NWRMA hydrometric / SLMet climate archives",
            "url": "https://nwrma.gov.sl/data/",
            "secondary": "https://slmet.gov.sl/our-services/climate/",
            "years": "rainfall records cited from 1921; gaps during the war; monitoring restarted ~2010",
            "geography": "sparse stations; Rokel-Seli focus for Water Security Project",
            "accessibility": "Agency portals; not confirmed as bulk open flood-event tables",
            "ground_truth": "Weather/water-level context if obtained — not flood labels",
            "in_repo": False,
        },
        {
            "name": "CIDMEWS-SL GeoPortal",
            "url": "https://www.cidmews-sl.solutions/index.php/early-warning-systems/cidmews",
            "years": "project layers ~2016–2017 documented",
            "geography": "Western Area disaster-prone areas cited",
            "accessibility": "Web geoportal; bulk historical flood events not verified as downloadable",
            "ground_truth": "Potential exposure layer after access review — not used here",
            "in_repo": False,
        },
        {
            "name": "HDX COD-AB Sierra Leone and CHIRPS subnational rainfall",
            "url": "https://data.humdata.org/dataset/cod-ab-sle",
            "secondary": "https://data.humdata.org/dataset/sle-rainfall-subnational",
            "years": "admin COD current; CHIRPS dekadal time series",
            "geography": "admin 0–4 polygons; rainfall averaged to admin units",
            "accessibility": "Public HDX",
            "ground_truth": "Join geometry and rainfall context only — not flood events",
            "in_repo": False,
        },
    ]


def current_inventory() -> list[dict[str, Any]]:
    zones = json.loads(FLOOD_ZONES.read_text(encoding="utf-8")) if FLOOD_ZONES.exists() else []
    mfl_n = None
    if MFL_CORE.exists():
        mfl_n = sum(1 for _ in MFL_CORE.open(encoding="utf-8")) - 1
    return [
        {
            "asset": "flood_zones.json",
            "source": "CHEWS static catalog (NDMA/IFRC-aligned narratives)",
            "date_coverage": "history years 2015–2024 in prose; layer itself is undated",
            "geographic_coverage": f"{len(zones)} communities; 10 of 16 districts",
            "temporal_resolution": "year (sometimes month in text)",
            "spatial_resolution": "point lat/lng",
            "real_vs_synthetic": "real place names / compiled history; not an event time series",
            "can_be_target": False,
            "can_be_context": True,
            "limitations": "No day field; 6 districts have zero zones",
        },
        {
            "asset": "Open-Meteo realtime + archive",
            "source": "weather_api.py / climate_archive.py",
            "date_coverage": "live nowcast; archive JSON on disk ~202307–202608; malaria monthly climate from 201104",
            "geographic_coverage": "district centroids today; archive API can take any lat/lng",
            "temporal_resolution": "hourly live / daily archive / monthly malaria join",
            "spatial_resolution": "Open-Meteo grid at requested point",
            "real_vs_synthetic": "real reanalysis/forecast; live fallback is synthetic jitter",
            "can_be_target": False,
            "can_be_context": True,
            "limitations": "Rainfall is not a flood event; live weather ignores zone coordinates",
        },
        {
            "asset": "synthetic flood CSV",
            "source": "CHEWS_SierraLeone_Flood_Dataset.csv",
            "date_coverage": "none",
            "geographic_coverage": "none",
            "temporal_resolution": "none",
            "spatial_resolution": "none",
            "real_vs_synthetic": "synthetic",
            "can_be_target": False,
            "can_be_context": False,
            "limitations": "300 rows; flood_occurred is generated; 0.991 AUC is not real-world",
        },
        {
            "asset": "synthetic community reports",
            "source": "community_reports_chews_202607.csv",
            "date_coverage": "2026-07-01 to 2026-07-30",
            "geographic_coverage": "shuffled Freetown names × inland districts",
            "temporal_resolution": "day (fake)",
            "spatial_resolution": "invalid",
            "real_vs_synthetic": "synthetic",
            "can_be_target": False,
            "can_be_context": False,
            "limitations": "632 geo mismatches; BLOCKED RF leakage",
        },
        {
            "asset": "MoH DHIS2 core MFL",
            "source": str(MFL_CORE.relative_to(BACKEND)) if MFL_CORE.exists() else "missing",
            "date_coverage": "snapshot",
            "geographic_coverage": f"{mfl_n} facilities with lat/lng" if mfl_n is not None else "unknown",
            "temporal_resolution": "none",
            "spatial_resolution": "facility point",
            "real_vs_synthetic": "real identity and coordinates",
            "can_be_target": False,
            "can_be_context": True,
            "limitations": "No flood-closure outcomes",
        },
        {
            "asset": "admin_hierarchy.csv + sierra-leone-districts.geojson",
            "source": "CHEWS reference / frontend",
            "date_coverage": "static",
            "geographic_coverage": "16 districts; GeoJSON polygons in frontend",
            "temporal_resolution": "none",
            "spatial_resolution": "district",
            "real_vs_synthetic": "reference geography",
            "can_be_target": False,
            "can_be_context": True,
            "limitations": "admin_boundaries staging folders are empty; OCHA COD-AB not ingested",
        },
        {
            "asset": "river gauges / inundation extents / NDMA register",
            "source": "not in repository",
            "date_coverage": None,
            "geographic_coverage": None,
            "temporal_resolution": None,
            "spatial_resolution": None,
            "real_vs_synthetic": "absent",
            "can_be_target": False,
            "can_be_context": False,
            "limitations": "Primary gap from the validation audit",
        },
    ]


def canonical_schema() -> dict[str, Any]:
    fields = []
    for name, provenance in FIELD_PROVENANCE.items():
        fields.append({
            "name": name,
            "provenance": provenance,
            "required_for_lead_time": name in REQUIRED_FOR_LEAD_TIME,
            "missing_policy": "null — never 0 / non-flood",
        })
    return {
        "name": "chews_flood_event_v0",
        "grain": "one row = one dated flood at one place",
        "not_a_daily_panel": True,
        "fields": fields,
        "forbidden": list(FORBIDDEN_LABEL_ORIGINS),
        "weather_columns_on_this_table": False,
        "weather_join": "separate past-only extract keyed by event_id after acquisition",
    }


def future_baseline() -> dict[str, Any]:
    return {
        "implemented_now": False,
        "threshold_invented_now": False,
        "first_defensible_baseline_once_events_exist": {
            "type": "zone_or_community past-only rainfall accumulation",
            "candidates_to_evaluate_later": [
                "t-1 / t-3 / t-7 precipitation sum vs that location's expanding wet-season percentile",
                "rolling accumulation ending at t-1 (not t0) in mapped flood zones",
                "event recurrence calendar (same community, same calendar month in prior years) as context only",
            ],
            "must_not": [
                "fit a mm cut on the same events then call it validation",
                "use future rainfall",
                "treat missing register days as non-flood without a coverage statement",
            ],
            "ml_rule": "An ML model is only justified if it beats this baseline on lead time and missed-event rate.",
        },
    }


def community_report_requirements() -> dict[str, Any]:
    return {
        "current_synthetic_csv_is_ground_truth": False,
        "required_to_become_useful": {
            "location": "GPS or verified community id matching MFL/COD/flood zone",
            "timestamp": "ISO datetime, timezone Africa/Abidjan; report time vs event time distinguished",
            "reporter": "stable CHW/NDMA officer id; role; organisation",
            "verification": "second source or supervisor flag; unverified reports stay unverified",
            "duplicates": "space-time clustering (same community, same 24h) before counting events",
            "confidence": "explicit low/medium/high; never implied by damaged_houses",
            "spatial_accuracy": "record GPS error or admin-level if GPS absent",
            "impact_fields": "optional observed impact; must not be model features if they define the label",
        },
        "roles_if_quality_met": {
            "event_detection": "possible near-real-time signal, still not the historical target",
            "independent_validation": "only if independent of the NDMA row being validated",
            "confirmation": "yes, with timestamps after the event",
        },
    }


def operational_use_case() -> dict[str, Any]:
    return {
        "would_warn_about": [
            "likely flooding at a known exposed community or zone",
            "possible disruption of access to listed nearby health facilities",
            "community exposure (population in catalog / MFL catchment)",
        ],
        "would_not_claim": [
            "disease outbreak caused by the flood",
            "AI prediction",
            "96% accuracy",
        ],
        "warning_contents": [
            "location (community/zone/district) and mapping uncertainty",
            "expected timing (nowcast vs t-1/t-3 rainfall context — not a false NWP strip)",
            "evidence (which source would confirm; rainfall window used)",
            "confidence/data quality",
            "affected facilities/communities if a spatial join is valid",
            "recommended verification (NDMA / DHMT / CHW), not automatic public-health action",
        ],
    }


def build_foundation_report(*, generated_at: Optional[str] = None) -> dict[str, Any]:
    generated_at = generated_at or _now()
    hashes = {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}
    return {
        "generated_at": generated_at,
        "phase": "flood_event_data_foundation",
        "model_trained": False,
        "integrated_into_chews": False,
        "rainfall_derived_labels_created": False,
        "missing_converted_to_nonflood": False,
        "sources": potential_external_sources(),
        "current_inventory": current_inventory(),
        "coverage": {
            "in_repo_dated_flood_events": 0,
            "in_repo_observed_gauges": 0,
            "in_repo_inundation_extents": 0,
            "external_primary_source_identified": True,
            "external_primary_source_acquired": False,
        },
        "data_quality": {
            "synthetic_training_table_unusable_as_target": True,
            "synthetic_community_reports_unusable_as_target": True,
            "zone_history_year_grain_only": True,
            "card_auc_not_real_world": True,
        },
        "target_candidates": target_candidates(),
        "recommended_target": {
            "id": "A+C",
            "name": "dated_observed_flood_event_at_community_grain",
            "fallback": "E district-day if community unknown, with mapping_uncertainty=high",
            "not_selected_as_primary": ["B", "D", "F"],
        },
        "canonical_schema": canonical_schema(),
        "weather_alignment": {
            "windows": "t-1, t-3, t-7 ending the day before event_start; t0 contemporaneous only",
            "future_forbidden": True,
            "variables": [
                "precipitation_sum",
                "optional temperature_2m_mean",
                "optional relative_humidity_2m_mean",
                "later: percentile/anomaly vs past-only expanding wet-season distribution at the same point",
            ],
            "percentile_is_context_not_label": True,
        },
        "geographic_alignment": {
            "priority": list(GEO_JOIN_PRIORITY),
            "silent_centroid_assignment_forbidden": True,
        },
        "minimum_data_requirements": sufficiency_requirements(),
        "future_baseline": future_baseline(),
        "community_report_requirements": community_report_requirements(),
        "operational_use_case": operational_use_case(),
        "known_gaps": [
            "NDMA disaster register not in CHEWS",
            "No river-gauge time series",
            "No inundation time series",
            "No facility-closure outcomes",
            "OCHA COD-AB not ingested (frontend has a district GeoJSON only)",
            "Zone catalog missing 6 districts",
        ],
        "verdict": {
            "classification": VERDICT_B,
            "label": VERDICT_B_LABEL,
        },
        "protected_hashes_before": hashes,
        "disclaimer": (
            "Specification only. No flood events were fabricated. "
            "Existing 0.9667 accuracy / 0.991 AUC remains synthetic-holdout, not real-world performance."
        ),
    }


def assert_protected_unchanged(before: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    after = {name: sha256_file(path) for name, path in PROTECTED_PATHS.items()}
    if after != before:
        changed = [k for k in after if after[k] != before.get(k)]
        raise RuntimeError(f"protected flood artifacts changed: {changed}")
    return after

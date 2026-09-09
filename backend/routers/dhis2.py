"""
DHIS2 ingestion API — read-only views of HMIS Analytics plus an explicit ingest trigger.

Does not expose credentials. Follows existing FastAPI router conventions
(prefix mounted at /dhis2 and /api/dhis2).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import dhis2 as cfg
from services import climate_archive, dhis2_historical, dhis2_pipeline, training_panel
from services.dhis2_service import (
    Dhis2AuthError,
    Dhis2Client,
    Dhis2Error,
    Dhis2HttpError,
    Dhis2ParseError,
)

router = APIRouter(prefix="/dhis2", tags=["DHIS2"])


class IngestRequest(BaseModel):
    period: Optional[str] = Field(default=None, description="LAST_12_MONTHS, LAST_12_WEEKS, or 202509,202510")
    ou_dimension: Optional[str] = Field(default=None, description="e.g. LEVEL-5 or a DHIS2 org unit UID")
    include_supporting: Optional[bool] = Field(default=None)
    persist: bool = Field(default=True)


class HistoricalExtractRequest(BaseModel):
    start: Optional[str] = Field(default=None, description="YYYYMM inclusive start")
    end: Optional[str] = Field(default=None, description="YYYYMM inclusive end")
    months: Optional[int] = Field(default=None, ge=1, le=120)
    persist: bool = Field(default=True)


class TrainingPanelRequest(HistoricalExtractRequest):
    refresh_health: bool = True
    refresh_climate: bool = True
    climate_mock: Optional[bool] = None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, Dhis2AuthError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, Dhis2HttpError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, Dhis2ParseError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, Dhis2Error):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail="DHIS2 ingest failed")


def _public_ingest(result: dict) -> dict:
    return {
        "ingested_at": result.get("ingested_at"),
        "source": result.get("source"),
        "mock": result.get("mock"),
        "period_query": result.get("period_query"),
        "ou_query": result.get("ou_query"),
        "indicator_ids": result.get("indicator_ids"),
        "quality": result.get("quality"),
        "record_count": len(result.get("records") or []),
        "facility_count": len(result.get("mapped_org_units") or []),
        "wide_row_count": len(result.get("wide") or []),
        "reporting_completeness": result.get("reporting_completeness"),
        "paths": result.get("paths"),
    }


@router.get("/status")
async def dhis2_status():
    """Connection configuration (no secrets) and last ingest summary if any."""
    cached = dhis2_pipeline.cached_ingest() or dhis2_pipeline.load_latest_curated()
    payload = cfg.public_status()
    payload["last_ingest"] = None
    if cached:
        payload["last_ingest"] = {
            "ingested_at": cached.get("ingested_at"),
            "source": cached.get("source"),
            "wide_row_count": len(cached.get("wide") or []),
            "record_count": len(cached.get("records") or cached.get("long") or []),
        }
    return payload


@router.post("/ingest")
async def dhis2_ingest(body: IngestRequest | None = None):
    """Pull Analytics + organisation units (live or mock) into the data lake."""
    body = body or IngestRequest()
    try:
        result = dhis2_pipeline.ingest(
            period=body.period,
            ou_dimension=body.ou_dimension,
            include_supporting=body.include_supporting,
            persist=body.persist,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return _public_ingest(result)


@router.get("/malaria")
async def dhis2_malaria(
    district: Optional[str] = Query(default=None),
    period: Optional[str] = Query(default=None),
    refresh: bool = Query(default=False),
):
    """Curated malaria series from DHIS2 (long + wide). Does not retrain the prototype GBT."""
    try:
        result = _ensure_data(refresh=refresh)
    except Exception as exc:
        raise _http_error(exc) from exc
    long_rows = result.get("long") or []
    wide = result.get("wide") or []
    if district:
        want = district.casefold()
        long_rows = [r for r in long_rows if (r.get("district_name") or "").casefold().find(want) >= 0]
        wide = [r for r in wide if (r.get("district_name") or "").casefold().find(want) >= 0]
    if period:
        long_rows = [r for r in long_rows if r.get("period") == period]
        wide = [r for r in wide if r.get("period") == period]
    overlay = dhis2_pipeline.live_case_overlay(district or "national")
    return {
        "source": result.get("source"),
        "ingested_at": result.get("ingested_at"),
        "quality": result.get("quality"),
        "overlay": overlay,
        "risk_engine_inputs": dhis2_pipeline.risk_engine_inputs_from_dhis2(district or "national"),
        "long": long_rows,
        "wide": wide,
        "features": result.get("features") or [],
        "prototype_model": {
            "retrained": False,
            "note": "Existing GradientBoosting malaria predictor still uses synthetic climate features. DHIS2 confirmed counts can feed risk_engine.assess(reported_cases=...).",
        },
    }


@router.get("/facilities")
async def dhis2_facilities(
    unmapped_only: bool = Query(default=False),
    refresh: bool = Query(default=False),
):
    """DHIS2 organisation units joined to the existing MFL (no second master list)."""
    try:
        result = _ensure_data(refresh=refresh)
    except Exception as exc:
        raise _http_error(exc) from exc
    units = result.get("mapped_org_units") or []
    if unmapped_only:
        units = [u for u in units if u.get("unmapped")]
    return {
        "source": result.get("source"),
        "count": len(units),
        "unmapped_count": sum(1 for u in (result.get("mapped_org_units") or []) if u.get("unmapped")),
        "organisation_units": units,
    }


@router.get("/health-data")
async def dhis2_health_data(refresh: bool = Query(default=False)):
    """Combined health extract: quality, hierarchy sample, malaria overlay, feature gaps."""
    try:
        result = _ensure_data(refresh=refresh)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        "status": cfg.public_status(),
        "ingest": _public_ingest(result),
        "quality": result.get("quality"),
        "reporting_completeness": result.get("reporting_completeness"),
        "malaria_overlay": dhis2_pipeline.live_case_overlay("national"),
        "risk_engine_inputs": dhis2_pipeline.risk_engine_inputs_from_dhis2("national"),
        "wide_preview": (result.get("wide") or [])[:20],
        "hierarchy_example": next(
            (u for u in (result.get("mapped_org_units") or []) if u.get("dhis2_org_unit_id") == "dar4XkzRmN0"),
            None,
        ),
    }


@router.get("/risk")
async def dhis2_risk(
    admin: str = Query(default="national"),
    rainfall: float = Query(default=186, ge=0, le=500),
    temperature: float = Query(default=27.4, ge=-10, le=55),
    humidity: float = Query(default=84, ge=0, le=100),
    refresh: bool = Query(default=False),
):
    """
    Run the EXISTING risk_engine.assess() using DHIS2 confirmed malaria as reported_cases.
    Climate arguments still come from the caller (defaults match the prototype live constants).
    """
    try:
        _ensure_data(refresh=refresh)
    except Exception as exc:
        raise _http_error(exc) from exc
    mapped = dhis2_pipeline.risk_engine_inputs_from_dhis2(admin)
    if not mapped:
        raise HTTPException(
            status_code=404,
            detail="No DHIS2 malaria confirmed values available. Run POST /dhis2/ingest or enable mock mode.",
        )
    try:
        from models import risk_engine
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"risk_engine unavailable: {exc}") from exc
    assessment = risk_engine.assess(
        rainfall=rainfall,
        temperature=temperature,
        humidity=humidity,
        reported_cases=mapped["reported_cases"],
        trend=mapped["trend"],
    )
    return {
        "admin_unit": admin,
        "dhis2": mapped["dhis2"],
        "trend": mapped["trend"],
        "reported_cases": mapped["reported_cases"],
        "climate_source": "query_parameters_or_prototype_defaults",
        "gaps": mapped["gaps"],
        "assessment": assessment._asdict(),
    }


def _public_historical(result: dict) -> dict:
    completeness = result.get("completeness") or {}
    return {
        "ingested_at": result.get("ingested_at"),
        "source": result.get("source"),
        "mock": result.get("mock"),
        "period_start": result.get("period_start"),
        "period_end": result.get("period_end"),
        "requested_month_count": len(result.get("requested_months") or []),
        "indicator_keys": result.get("indicator_keys"),
        "quality": result.get("quality"),
        "completeness": completeness,
        "district_month_count": len(result.get("district_month") or []),
        "district_month_preview": (result.get("district_month") or [])[:20],
        "prototype_gbt": result.get("prototype_gbt"),
        "paths": result.get("paths"),
    }


@router.post("/historical/extract")
async def dhis2_historical_extract(body: HistoricalExtractRequest | None = None):
    """
    Explicit monthly DHIS2 extract → validation → district-month → completeness.

    Does not retrain or call the synthetic malaria GBT.
    """
    body = body or HistoricalExtractRequest()
    try:
        result = dhis2_historical.extract_historical(
            start=body.start,
            end=body.end,
            months=body.months,
            persist=body.persist,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return _public_historical(result)


@router.post("/historical/climate")
async def dhis2_historical_climate(body: HistoricalExtractRequest | None = None):
    """Open-Meteo Archive monthly climate. Does not change realtime flood weather."""
    body = body or HistoricalExtractRequest()
    try:
        result = climate_archive.ingest_historical_climate(
            start=body.start,
            end=body.end,
            months=body.months,
            persist=body.persist,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "source": result.get("source"),
        "mock": result.get("mock"),
        "period_start": result.get("period_start"),
        "period_end": result.get("period_end"),
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "requested_month_count": len(result.get("requested_months") or []),
        "observed_months": result.get("observed_months"),
        "district_count": result.get("district_count"),
        "row_count": result.get("row_count"),
        "preview": (result.get("district_month") or [])[:20],
        "realtime_weather_untouched": True,
        "paths": result.get("paths"),
    }


@router.post("/historical/panel")
async def dhis2_training_panel(body: TrainingPanelRequest | None = None):
    """
    Align DHIS2 district-month with Archive climate, engineer lags, emit READY / NOT READY.

    Never calls malaria_predictor.predict().
    """
    body = body or TrainingPanelRequest()
    try:
        result = training_panel.build_training_panel(
            refresh_health=body.refresh_health,
            refresh_climate=body.refresh_climate,
            persist=body.persist,
            climate_mock=body.climate_mock,
            start=body.start,
            end=body.end,
            months=body.months,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    readiness = result.get("readiness") or {}
    return {
        "verdict": result.get("verdict"),
        "ready": readiness.get("ready"),
        "readiness": readiness,
        "health": result.get("health"),
        "climate": result.get("climate"),
        "joined_rows": result.get("joined_rows"),
        "feature_rows": result.get("feature_rows"),
        "trainable_preview": result.get("trainable_preview"),
        "paths": result.get("paths"),
        "prototype_gbt": {
            "retrained": False,
            "connected": False,
            "note": "Synthetic malaria GBT is not used on this panel.",
        },
    }


@router.get("/historical/readiness")
async def dhis2_training_readiness():
    """Last training-readiness verdict, or a reminder to run POST /dhis2/historical/panel."""
    readiness = training_panel.load_latest_readiness()
    if not readiness:
        return {
            "verdict": training_panel.NOT_READY,
            "ready": False,
            "note": "No panel has been built. POST /dhis2/historical/panel first.",
        }
    return readiness


def _ensure_data(*, refresh: bool) -> dict:
    cached = dhis2_pipeline.cached_ingest()
    if cached and not refresh:
        return cached
    disk = dhis2_pipeline.load_latest_curated()
    if disk and not refresh and disk.get("wide"):
        return {**(cached or {}), **disk}
    return dhis2_pipeline.ingest(client=Dhis2Client(), persist=True)

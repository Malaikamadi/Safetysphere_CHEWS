

import sys
from pathlib import Path

# Ensure backend directory is in sys.path
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum
import traceback

# Resilient imports — capture failures per-module instead of crashing
_import_errors = []

# Individual model imports
risk_engine = environmental = flood_risk = malaria_predictor = healthcare_readiness = community_reports = None
try:
    from models import risk_engine
except Exception as e:
    _import_errors.append(f"risk_engine: {e}")
try:
    from models import environmental
except Exception as e:
    _import_errors.append(f"environmental: {e}")
try:
    from models import flood_risk
except Exception as e:
    _import_errors.append(f"flood_risk: {e}")
try:
    from models import malaria_predictor
except Exception as e:
    _import_errors.append(f"malaria_predictor: {e}")
try:
    from models import healthcare_readiness
except Exception as e:
    _import_errors.append(f"healthcare_readiness: {e}")
try:
    from models import community_reports
except Exception as e:
    _import_errors.append(f"community_reports: {e}")

# Individual router imports
strategic = early_warning = healthcare = point_of_care = situation_room = None
try:
    from routers import strategic
except Exception as e:
    _import_errors.append(f"strategic router: {e}")
try:
    from routers import early_warning
except Exception as e:
    _import_errors.append(f"early_warning router: {e}")
try:
    from routers import healthcare
except Exception as e:
    _import_errors.append(f"healthcare router: {e}")
try:
    from routers import point_of_care
except Exception as e:
    _import_errors.append(f"point_of_care router: {e}")
try:
    from routers import situation_room
except Exception as e:
    _import_errors.append(f"situation_room router: {e}")

# Services
facility_mfl = None
try:
    from services import facility_mfl
except Exception as e:
    _import_errors.append(f"facility_mfl: {e}")

# ========================== App Initialisation =============================

app = FastAPI(
    title="CHEWS — Climate-Health Intelligence System",
    description=(
        "Multi-layer AI-powered climate-health intelligence for NGOs and "
        "public health organisations in low-resource settings. Combines "
        "environmental, epidemiological, exposure, hazard and readiness "
        "models with a real-time flood atlas for Sierra Leone."
    ),
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount domain routers under both /api and root to guarantee compatibility
if strategic:
    app.include_router(strategic.router, prefix="/api")
    app.include_router(strategic.router)
if early_warning:
    app.include_router(early_warning.router, prefix="/api")
    app.include_router(early_warning.router)
if healthcare:
    app.include_router(healthcare.router, prefix="/api")
    app.include_router(healthcare.router)
if point_of_care:
    app.include_router(point_of_care.router, prefix="/api")
    app.include_router(point_of_care.router)
if situation_room:
    app.include_router(situation_room.router, prefix="/api")
    app.include_router(situation_room.router)


# ========================== Startup Event ==================================

@app.on_event("startup")
async def startup():
    """Initialise ML models at server start."""
    if environmental:
        try:
            environmental.initialize()
        except Exception as e:
            _import_errors.append(f"env init: {e}")
    if flood_risk:
        try:
            flood_risk.initialize()
        except Exception as e:
            _import_errors.append(f"flood init: {e}")
    if malaria_predictor:
        try:
            malaria_predictor.initialize()
        except Exception as e:
            _import_errors.append(f"malaria init: {e}")
    if healthcare_readiness:
        try:
            healthcare_readiness.initialize()
        except Exception as e:
            _import_errors.append(f"hr init: {e}")
    if community_reports:
        try:
            community_reports.initialize()
        except Exception as e:
            _import_errors.append(f"cr init: {e}")
    if facility_mfl:
        try:
            facility_mfl.initialize()
        except Exception as e:
            _import_errors.append(f"mfl init: {e}")
    if _import_errors:
        print(f"[CHEWS] Startup warnings: {_import_errors}")
    print("[CHEWS] All models initialised. System ready.")


@app.get("/api/debug")
async def debug_info():
    """Temporary debug endpoint to diagnose Vercel runtime issues."""
    import os
    from pathlib import Path
    base = Path(__file__).resolve().parent
    data_dir = base / "data"
    mfl_path = data_dir / "01_raw" / "master_facility_list" / "mfl_readiness_chews_v1.csv"
    return {
        "python": sys.version,
        "cwd": os.getcwd(),
        "base_dir": str(base),
        "data_dir_exists": data_dir.exists(),
        "mfl_exists": mfl_path.exists(),
        "data_contents": os.listdir(str(data_dir)) if data_dir.exists() else "NOT FOUND",
        "import_errors": _import_errors,
        "mfl_initialized": facility_mfl._initialized if facility_mfl else False,
        "facilities_count": len(facility_mfl._facilities) if facility_mfl else 0,
    }


# ========================== Data Models ====================================

class TrendEnum(str, Enum):
    increasing = "increasing"
    stable = "stable"
    decreasing = "decreasing"


class ExposureLevelEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PredictionInput(BaseModel):
    """Full input schema for the multi-layer /predict endpoint."""

    # Environmental inputs
    rainfall: float = Field(
        ..., ge=0, le=500,
        description="Rainfall in mm (monthly total)"
    )
    temperature: float = Field(
        ..., ge=-10, le=55,
        description="Temperature in °C"
    )
    humidity: float = Field(
        ..., ge=0, le=100,
        description="Relative humidity (%)"
    )

    # Epidemiological inputs
    reported_cases: int = Field(
        ..., ge=0,
        description="Number of confirmed/suspected malaria cases in the reporting period"
    )
    trend: TrendEnum = Field(
        default=TrendEnum.stable,
        description="Direction of recent case trend"
    )

    # Exposure inputs
    vulnerable_population: int = Field(
        default=0, ge=0,
        description="Count of high-risk individuals (children <5 + pregnant women)"
    )
    exposure_level: ExposureLevelEnum = Field(
        default=ExposureLevelEnum.medium,
        description="Community exposure level (housing, nets, proximity to water)"
    )


class PredictionOutput(BaseModel):
    """Output schema for the /predict endpoint."""
    final_risk: float
    risk_level: str
    breakdown: dict
    explanation: str
    factors: list[str]
    recommendations: list[str]


class AskInput(BaseModel):
    """Input schema for the /ask health assistant."""
    question: str = Field(..., min_length=1, description="User question")
    risk_score: float | None = Field(
        default=None, ge=0, le=1,
        description="Optional latest risk score for contextual answer"
    )


# ========================== API Endpoints ==================================

@app.get("/health", tags=["System"])
async def health_check():
    """System health check."""
    return {
        "status": "ok",
        "service": "CHEWS Climate-Health Intelligence System",
        "version": "4.0.0",
        "models": [
            "environmental", "epidemiological", "exposure", "risk_engine",
            "flood_risk", "heat_stress", "air_quality", "carbon_accounting",
        ],
        "routers": [
            "/strategic", "/early-warning", "/healthcare", "/poc",
        ],
    }


# NOTE: /situation-room endpoints now handled by routers/situation_room.py


@app.post("/predict", response_model=PredictionOutput, tags=["Prediction"])
async def predict_risk(data: PredictionInput):
    """
    Run the full multi-layer risk assessment pipeline.

    Combines three specialised models:
    1. **Environmental** — climate suitability for transmission
    2. **Epidemiological** — disease spread probability from surveillance
    3. **Exposure** — population vulnerability assessment

    Returns a composite risk score, breakdown, natural-language explanation,
    and actionable recommendations.
    """
    result = risk_engine.assess(
        rainfall=data.rainfall,
        temperature=data.temperature,
        humidity=data.humidity,
        reported_cases=data.reported_cases,
        trend=data.trend.value,
        vulnerable_population=data.vulnerable_population,
        exposure_level=data.exposure_level.value,
    )

    return PredictionOutput(
        final_risk=result.final_risk,
        risk_level=result.risk_level,
        breakdown=result.breakdown,
        explanation=result.explanation,
        factors=result.factors,
        recommendations=result.recommendations,
    )


@app.post("/ask", tags=["Assistant"])
async def ask_assistant(data: AskInput):
    """
    Simple health assistant endpoint.
    Answers common questions about malaria, prevention, and risk.
    """
    question = data.question.lower()

    responses = {
        "what is malaria": (
            "Malaria is a life-threatening disease caused by Plasmodium parasites, "
            "transmitted through bites of infected female Anopheles mosquitoes. "
            "In Sierra Leone, P. falciparum is the most common and deadly species. "
            "It is both preventable and curable with prompt treatment."
        ),
        "how to prevent": (
            "Key malaria prevention measures:\n"
            "• Sleep under long-lasting insecticidal nets (LLINs) every night\n"
            "• Support indoor residual spraying (IRS) programmes\n"
            "• Eliminate standing water near homes\n"
            "• Wear long sleeves and trousers during evening hours\n"
            "• Ensure pregnant women receive intermittent preventive treatment (IPTp)\n"
            "• Seek treatment within 24 hours of fever onset"
        ),
        "symptoms": (
            "Common malaria symptoms:\n"
            "• Fever and chills (often cyclical)\n"
            "• Severe headache\n"
            "• Muscle and joint pain\n"
            "• Nausea, vomiting, and diarrhoea\n"
            "• Fatigue and weakness\n"
            "• In severe cases: convulsions, confusion, difficulty breathing\n\n"
            "⚠️ Seek medical care immediately — untreated P. falciparum malaria "
            "can become life-threatening within 24 hours, especially in children."
        ),
        "risk score": (
            "The CHEWS risk score combines three models:\n\n"
            "🌍 Environmental (40%): rainfall, temperature, humidity\n"
            "📊 Epidemiological (40%): case counts and trend direction\n"
            "👥 Exposure (20%): vulnerable population and protection level\n\n"
            "Score ranges:\n"
            "• Below 0.30 → Low risk\n"
            "• 0.30 to 0.60 → Medium risk\n"
            "• Above 0.60 → High risk"
        ),
        "children": (
            "Children under 5 are the most vulnerable to malaria:\n"
            "• They account for ~80% of malaria deaths in Africa\n"
            "• Their immune systems haven't developed malaria resistance\n"
            "• Symptoms can progress rapidly to severe/cerebral malaria\n\n"
            "Priority actions:\n"
            "• Ensure every child sleeps under an ITN\n"
            "• Seek care within 24 hours of fever onset\n"
            "• Complete full course of prescribed antimalarials"
        ),
        "pregnant": (
            "Pregnant women face heightened malaria risk:\n"
            "• 3x more likely to develop severe disease\n"
            "• Malaria in pregnancy can cause anaemia, low birth weight, "
            "and premature delivery\n\n"
            "Key interventions:\n"
            "• Intermittent preventive treatment (IPTp-SP) at every ANC visit\n"
            "• Sleep under ITN throughout pregnancy\n"
            "• Attend all antenatal care appointments"
        ),
    }

    # Find best matching response
    answer = None
    for key, response in responses.items():
        if key in question:
            answer = response
            break

    if answer is None:
        answer = (
            "I can help with questions about:\n"
            "• Malaria symptoms and treatment\n"
            "• Prevention methods\n"
            "• Risk score interpretation\n"
            "• Protection for children and pregnant women\n\n"
            "Try asking about 'symptoms', 'prevention', 'children', "
            "'pregnant women', or 'risk score'."
        )

    # Add context from latest risk assessment
    if data.risk_score is not None:
        if data.risk_score >= 0.6:
            level = "High"
        elif data.risk_score >= 0.3:
            level = "Medium"
        else:
            level = "Low"
        answer += (
            f"\n\n📊 Your latest risk assessment: {data.risk_score:.2f} ({level})"
        )

    return {"question": data.question, "answer": answer}

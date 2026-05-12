"""
CHEWS v3.0 — Climate-Health Early Warning System
===================================================
Comprehensive multi-hazard, multi-disease climate-health intelligence platform.

4 Operational Areas:
    Area 1: Strategic Planning    — hazard mapping, vulnerability, pollution, carbon
    Area 2: Early Warning         — real-time alerts, sensor data, triggers
    Area 3: Healthcare Readiness  — disease forecasting, anomaly detection, surge planning
    Area 4: Point-of-Care         — multilingual triage, health assistant

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    FastAPI Application                       │
    ├──────────┬──────────┬──────────────┬────────────────────────┤
    │ Strategic │  Early   │  Healthcare  │   Point-of-Care        │
    │ Planning  │  Warning │  Readiness   │   Support              │
    ├──────────┴──────────┴──────────────┴────────────────────────┤
    │                    Service Layer                             │
    │  risk_engine | alert_engine | forecast_engine | triage      │
    ├─────────────────────────────────────────────────────────────┤
    │                    Model Layer                               │
    │  environmental | epidemiological | exposure | air_quality    │
    │  flood_risk | heat_stress | carbon_accounting               │
    └─────────────────────────────────────────────────────────────┘
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from enum import Enum

from models import environmental
from models import risk_engine
from routers import strategic, early_warning, healthcare, point_of_care

# ========================== App Initialisation =============================

app = FastAPI(
    title="CHEWS v3.0 — Climate-Health Intelligence Platform",
    description=(
        "Comprehensive multi-hazard, multi-disease climate-health early warning system. "
        "Covers strategic planning, early warning, healthcare readiness, and point-of-care support."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================== Register Routers ===============================

app.include_router(strategic.router)
app.include_router(early_warning.router)
app.include_router(healthcare.router)
app.include_router(point_of_care.router)


# ========================== Startup Event ==================================

@app.on_event("startup")
async def startup():
    """Initialise ML models at server start."""
    environmental.initialize()
    print("[CHEWS v3.0] All models initialised. Platform ready.")
    print("[CHEWS v3.0] Areas: Strategic Planning | Early Warning | Healthcare Readiness | Point-of-Care")


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


# ========================== Core Endpoints =================================

@app.get("/health", tags=["System"])
async def health_check():
    """System health check."""
    return {
        "status": "ok",
        "service": "CHEWS Climate-Health Intelligence Platform",
        "version": "3.0.0",
        "areas": [
            "Strategic Planning",
            "Early Warning",
            "Healthcare Readiness",
            "Point-of-Care",
        ],
        "models": [
            "environmental", "epidemiological", "exposure",
            "air_quality", "flood_risk", "heat_stress", "carbon_accounting",
        ],
        "services": [
            "risk_engine", "alert_engine", "forecast_engine",
            "vulnerability", "triage_assistant",
        ],
    }


@app.post("/predict", response_model=PredictionOutput, tags=["Malaria Risk"])
async def predict_risk(data: PredictionInput):
    """
    Run the full multi-layer malaria risk assessment pipeline.
    (Legacy endpoint — maintained for backward compatibility)
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
    """Simple health assistant endpoint."""
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

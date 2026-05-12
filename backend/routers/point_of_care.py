"""
Point-of-Care Router — Area 4
================================
Endpoints for multilingual triage, health assistant, and community data tools.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import triage_assistant

router = APIRouter(prefix="/poc", tags=["Area 4: Point-of-Care"])


class TriageInput(BaseModel):
    symptoms: list[str] = Field(default=["fever", "headache"])
    patient_group: str = Field(default="adult")
    language: str = Field(default="en")
    heat_risk: float = Field(default=0.0, ge=0, le=1)
    air_quality_risk: float = Field(default=0.0, ge=0, le=1)
    flood_risk: float = Field(default=0.0, ge=0, le=1)


class AskInput(BaseModel):
    question: str = Field(..., min_length=1)
    language: str = Field(default="en")
    risk_score: float | None = Field(default=None, ge=0, le=1)
    context: str = Field(default="general")


@router.post("/triage")
async def run_triage(data: TriageInput):
    """Run climate-sensitive triage assessment for a patient."""
    result = triage_assistant.triage(
        symptoms=data.symptoms, patient_group=data.patient_group,
        language=data.language, heat_risk=data.heat_risk,
        air_quality_risk=data.air_quality_risk, flood_risk=data.flood_risk,
    )
    return result._asdict()


@router.post("/ask")
async def ask_health_assistant(data: AskInput):
    """Multilingual health assistant — answers questions about climate and health."""
    question = data.question.lower()

    # Expanded knowledge base
    responses = {
        "malaria": (
            "Malaria is caused by Plasmodium parasites transmitted by Anopheles mosquitoes. "
            "P. falciparum is most common in Africa and can be fatal without treatment. "
            "Prevention: sleep under ITNs, eliminate standing water, seek care within 24h of fever."
        ),
        "dengue": (
            "Dengue is a viral disease spread by Aedes mosquitoes. Symptoms: high fever, severe headache, "
            "pain behind eyes, joint pain, rash. No specific treatment — supportive care is essential. "
            "Prevention: eliminate standing water containers, use repellent."
        ),
        "cholera": (
            "Cholera is caused by contaminated water/food. Symptoms: severe watery diarrhea, vomiting. "
            "Treatment: ORS and IV fluids. Prevention: safe water, sanitation, hygiene (WASH). "
            "Climate link: flooding increases cholera risk through water contamination."
        ),
        "heat": (
            "Heat-related illness ranges from heat exhaustion to life-threatening heat stroke. "
            "Signs: confusion, hot/dry skin, rapid pulse, collapse. "
            "Action: move to shade, cool with water, give fluids (if conscious). "
            "Children and elderly are most vulnerable."
        ),
        "air quality": (
            "Poor air quality affects respiratory health, especially in children. "
            "Sources: cooking fires, vehicle exhaust, industrial emissions, dust storms, wildfires. "
            "Protection: stay indoors during high-pollution periods, use masks, improve ventilation."
        ),
        "flood": (
            "Flooding increases risk of waterborne diseases (cholera, typhoid), injuries, "
            "and displacement. After floods: avoid floodwater contact, boil all drinking water, "
            "watch for snakes and debris, monitor for disease outbreaks."
        ),
        "prevent": (
            "Key prevention strategies:\n"
            "• Malaria: ITNs, IRS, eliminate breeding sites\n"
            "• Waterborne disease: safe water, sanitation, hygiene\n"
            "• Heat illness: hydration, shade, limit exertion\n"
            "• Respiratory: reduce indoor air pollution, masks during poor AQ"
        ),
        "symptom": (
            "Common climate-sensitive symptoms:\n"
            "• Fever + chills → malaria, dengue\n"
            "• Diarrhea + vomiting → cholera, typhoid\n"
            "• Difficulty breathing → respiratory infection, asthma from air pollution\n"
            "• Confusion + hot skin → heat stroke (EMERGENCY)\n"
            "Seek care immediately for any severe symptoms."
        ),
        "children": (
            "Children under 5 are most vulnerable to climate-health risks:\n"
            "• 80% of malaria deaths in Africa are children <5\n"
            "• Breathe 50% more air per kg body weight (more pollution exposure)\n"
            "• Higher surface-area-to-mass ratio (more heat stress)\n"
            "• Immature immune systems (more susceptible to infections)\n"
            "Priority: nets, vaccination, nutrition, clean water, indoor air quality."
        ),
    }

    answer = None
    for key, response in responses.items():
        if key in question:
            answer = response
            break

    if answer is None:
        answer = (
            "I can help with questions about:\n"
            "• Malaria, dengue, cholera prevention and treatment\n"
            "• Heat illness and protection\n"
            "• Air quality and respiratory health\n"
            "• Flood safety and waterborne disease\n"
            "• Children's health and climate vulnerability\n\n"
            "Try asking about any of these topics."
        )

    return {"question": data.question, "answer": answer, "language": data.language}


@router.get("/languages")
async def supported_languages():
    """Get list of supported triage languages."""
    return {"languages": triage_assistant.get_supported_languages()}


@router.get("/symptoms")
async def available_symptoms():
    """Get list of recognized symptoms for triage."""
    return {
        "symptoms": list(triage_assistant.SYMPTOM_SCORES.keys()),
        "patient_groups": list(triage_assistant.VULNERABILITY_MODIFIERS.keys()) + ["adult"],
    }

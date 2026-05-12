"""
Triage Assistant Service
=========================
Multilingual, climate-sensitive triage and health guidance system.
Supports community health workers with case management recommendations.
"""

from __future__ import annotations
from typing import NamedTuple


class TriageResult(NamedTuple):
    urgency: str          # Green / Yellow / Orange / Red
    category: str         # Self-care / Routine / Urgent / Emergency
    assessment: str
    actions: list[str]
    referral_needed: bool
    climate_context: str
    language: str


# Symptom severity mappings
SYMPTOM_SCORES = {
    "fever": 3, "high_fever": 5, "convulsions": 8, "unconscious": 10,
    "difficulty_breathing": 7, "chest_pain": 6, "cough": 2, "severe_cough": 4,
    "diarrhea": 3, "bloody_diarrhea": 7, "vomiting": 3, "severe_vomiting": 5,
    "headache": 2, "severe_headache": 4, "rash": 2, "body_pain": 2,
    "dehydration": 6, "weakness": 3, "confusion": 7, "bleeding": 6,
    "heat_exhaustion": 5, "heat_stroke": 9, "sunburn": 2,
    "eye_irritation": 2, "wheezing": 5, "asthma_attack": 7,
}

VULNERABILITY_MODIFIERS = {
    "child_under5": 1.5,
    "pregnant": 1.4,
    "elderly": 1.3,
    "chronic_illness": 1.3,
    "malnourished": 1.4,
}

# Multilingual templates
TRANSLATIONS = {
    "en": {
        "green": "Low urgency — can be managed at home",
        "yellow": "Moderate — visit health facility within 24 hours",
        "orange": "Urgent — seek care immediately",
        "red": "EMERGENCY — life-threatening, transport to facility NOW",
        "climate_heat": "Current heat conditions may worsen symptoms. Ensure shade, hydration, and rest.",
        "climate_air": "Poor air quality detected. Keep patient indoors, minimize exertion.",
        "climate_flood": "Flooding increases waterborne disease risk. Use only treated/boiled water.",
        "climate_normal": "No additional climate-related health concerns at this time.",
    },
    "kri": {  # Sierra Leonean Krio
        "green": "I nɔ tɔ bad — yu kin tek kia na os",
        "yellow": "I so-so — go ospitul bifo tumara",
        "orange": "I ɔjɛnt — go kwik kwik fɔ gɛt ɛp",
        "red": "IMAJƐNSI — i denjɛrus, tek am go ospitul NAW",
        "climate_heat": "Di ɛt de bad. Mek i sidɔm na shed, drink wata plɛnti.",
        "climate_air": "Di ɛya nɔ klin. Mek i de insay, nɔ du ad wɔk.",
        "climate_flood": "Wata de flɔd. Yuz klin wata we yu bɔyl.",
        "climate_normal": "Nɔ ɛni ɛkstra klaymet prɔblɛm naw.",
    },
    "fr": {  # French
        "green": "Faible urgence — peut être géré à domicile",
        "yellow": "Modéré — consulter un centre de santé dans les 24h",
        "orange": "Urgent — consulter immédiatement",
        "red": "URGENCE — danger de mort, transporter au centre de santé MAINTENANT",
        "climate_heat": "La chaleur actuelle peut aggraver les symptômes. Assurez ombre et hydratation.",
        "climate_air": "Mauvaise qualité de l'air. Gardez le patient à l'intérieur.",
        "climate_flood": "Les inondations augmentent le risque de maladies hydriques. Utilisez de l'eau traitée.",
        "climate_normal": "Pas de préoccupation climatique supplémentaire actuellement.",
    },
}


def triage(
    symptoms: list[str],
    patient_group: str = "adult",
    language: str = "en",
    heat_risk: float = 0.0,
    air_quality_risk: float = 0.0,
    flood_risk: float = 0.0,
) -> TriageResult:
    """Run climate-sensitive triage assessment."""
    lang = TRANSLATIONS.get(language, TRANSLATIONS["en"])

    # Score symptoms
    total_score = sum(SYMPTOM_SCORES.get(s, 1) for s in symptoms)

    # Apply vulnerability modifier
    modifier = VULNERABILITY_MODIFIERS.get(patient_group, 1.0)
    adjusted = total_score * modifier

    # Classify urgency
    if adjusted >= 15:
        urgency, category = "Red", "Emergency"
        assessment = lang["red"]
        referral = True
    elif adjusted >= 10:
        urgency, category = "Orange", "Urgent"
        assessment = lang["orange"]
        referral = True
    elif adjusted >= 5:
        urgency, category = "Yellow", "Routine"
        assessment = lang["yellow"]
        referral = False
    else:
        urgency, category = "Green", "Self-care"
        assessment = lang["green"]
        referral = False

    # Climate context
    if heat_risk > 0.5:
        climate_context = lang["climate_heat"]
    elif air_quality_risk > 0.5:
        climate_context = lang["climate_air"]
    elif flood_risk > 0.5:
        climate_context = lang["climate_flood"]
    else:
        climate_context = lang["climate_normal"]

    # Generate actions
    actions = _get_actions(symptoms, urgency, patient_group)

    return TriageResult(
        urgency=urgency, category=category, assessment=assessment,
        actions=actions, referral_needed=referral,
        climate_context=climate_context, language=language,
    )


def _get_actions(symptoms, urgency, patient_group):
    actions = []
    if "fever" in symptoms or "high_fever" in symptoms:
        actions.append("Give paracetamol for fever. Monitor temperature every 4 hours.")
        actions.append("Test for malaria with RDT if available.")
    if "diarrhea" in symptoms or "bloody_diarrhea" in symptoms:
        actions.append("Start oral rehydration salts (ORS) immediately.")
    if "difficulty_breathing" in symptoms or "wheezing" in symptoms:
        actions.append("Position patient upright. Give bronchodilator if available.")
    if "dehydration" in symptoms:
        actions.append("ORS: 200ml after each loose stool for children, 400ml for adults.")
    if "heat_exhaustion" in symptoms or "heat_stroke" in symptoms:
        actions.append("Move to shade immediately. Cool with wet cloths. Give cool water.")
    if urgency == "Red":
        actions.append("Transport to nearest health facility IMMEDIATELY.")
        actions.append("Keep patient stable during transport.")
    if patient_group == "child_under5":
        actions.append("CAUTION: Children under 5 can deteriorate rapidly. Monitor closely.")
    if patient_group == "pregnant":
        actions.append("CAUTION: Pregnant patient — avoid certain medications. Refer if uncertain.")
    if not actions:
        actions = ["Monitor symptoms", "Ensure adequate rest and hydration"]
    return actions


def get_supported_languages():
    return [{"code": k, "name": {"en": "English", "kri": "Krio", "fr": "French"}.get(k, k)} for k in TRANSLATIONS]

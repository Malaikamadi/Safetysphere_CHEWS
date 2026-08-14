"""
Situation Room Router — National Command Center
=================================================
Endpoints powering the CHEWS National Situation Room dashboard:
map layers, timeline forecasts, scenario simulation, AI explainability,
community intelligence, sensor network, healthcare digital twins,
and decision support.

All data is simulated/demo for Sierra Leone.
"""

import math
import random
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from services import weather_api
from typing import Optional

router = APIRouter(prefix="/situation-room", tags=["Situation Room"])

# ───────────────────────────── Seed data ──────────────────────────────

DISTRICTS = [
    {"id": "bo", "name": "Bo", "lat": 7.9647, "lng": -11.7383, "population": 575478},
    {"id": "bonthe", "name": "Bonthe", "lat": 7.5264, "lng": -12.505, "population": 200730},
    {"id": "bombali", "name": "Bombali", "lat": 9.0531, "lng": -12.2918, "population": 606544},
    {"id": "kailahun", "name": "Kailahun", "lat": 8.2774, "lng": -10.5719, "population": 526379},
    {"id": "kambia", "name": "Kambia", "lat": 9.1261, "lng": -12.9186, "population": 345474},
    {"id": "kenema", "name": "Kenema", "lat": 7.8767, "lng": -11.1876, "population": 609873},
    {"id": "koinadugu", "name": "Koinadugu", "lat": 9.5, "lng": -11.5, "population": 409372},
    {"id": "kono", "name": "Kono", "lat": 8.6449, "lng": -10.9715, "population": 506100},
    {"id": "moyamba", "name": "Moyamba", "lat": 8.1588, "lng": -12.4312, "population": 318588},
    {"id": "port_loko", "name": "Port Loko", "lat": 8.7667, "lng": -12.7874, "population": 615376},
    {"id": "pujehun", "name": "Pujehun", "lat": 7.3581, "lng": -11.7208, "population": 346461},
    {"id": "tonkolili", "name": "Tonkolili", "lat": 8.7, "lng": -11.8, "population": 531435},
    {"id": "western_area_rural", "name": "Western Area Rural", "lat": 8.3842, "lng": -13.0935, "population": 444270},
    {"id": "western_area_urban", "name": "Western Area Urban", "lat": 8.484, "lng": -13.2299, "population": 1055964},
]

FACILITIES = [
    {"id": "f1", "name": "Connaught Hospital", "district": "western_area_urban", "lat": 8.484, "lng": -13.232, "type": "hospital", "beds": 300, "staff": 120},
    {"id": "f2", "name": "Princess Christian Maternity Hospital", "district": "western_area_urban", "lat": 8.488, "lng": -13.228, "type": "hospital", "beds": 150, "staff": 65},
    {"id": "f3", "name": "Ola During Children's Hospital", "district": "western_area_urban", "lat": 8.486, "lng": -13.235, "type": "hospital", "beds": 100, "staff": 48},
    {"id": "f4", "name": "Bo Government Hospital", "district": "bo", "lat": 7.964, "lng": -11.738, "type": "hospital", "beds": 200, "staff": 80},
    {"id": "f5", "name": "Kenema Government Hospital", "district": "kenema", "lat": 7.877, "lng": -11.188, "type": "hospital", "beds": 180, "staff": 72},
    {"id": "f6", "name": "Makeni Government Hospital", "district": "bombali", "lat": 8.883, "lng": -12.049, "type": "hospital", "beds": 150, "staff": 55},
    {"id": "f7", "name": "Port Loko Government Hospital", "district": "port_loko", "lat": 8.767, "lng": -12.787, "type": "hospital", "beds": 120, "staff": 42},
    {"id": "f8", "name": "Kailahun Government Hospital", "district": "kailahun", "lat": 8.277, "lng": -10.572, "type": "hospital", "beds": 100, "staff": 35},
    {"id": "f9", "name": "Kambia Government Hospital", "district": "kambia", "lat": 9.126, "lng": -12.919, "type": "hospital", "beds": 80, "staff": 28},
    {"id": "f10", "name": "Moyamba Government Hospital", "district": "moyamba", "lat": 8.159, "lng": -12.431, "type": "hospital", "beds": 90, "staff": 32},
    {"id": "f11", "name": "Pujehun Community Health Centre", "district": "pujehun", "lat": 7.358, "lng": -11.721, "type": "health_centre", "beds": 40, "staff": 18},
    {"id": "f12", "name": "Kono Government Hospital", "district": "kono", "lat": 8.645, "lng": -10.972, "type": "hospital", "beds": 110, "staff": 38},
    {"id": "f13", "name": "Magburaka Hospital", "district": "tonkolili", "lat": 8.723, "lng": -11.947, "type": "hospital", "beds": 100, "staff": 35},
    {"id": "f14", "name": "Bonthe Government Hospital", "district": "bonthe", "lat": 7.526, "lng": -12.505, "type": "hospital", "beds": 60, "staff": 22},
    {"id": "f15", "name": "Waterloo CHC", "district": "western_area_rural", "lat": 8.338, "lng": -13.072, "type": "health_centre", "beds": 30, "staff": 14},
    {"id": "f16", "name": "Lumley Government Hospital", "district": "western_area_urban", "lat": 8.467, "lng": -13.269, "type": "hospital", "beds": 80, "staff": 35},
    {"id": "f17", "name": "Kabala Government Hospital", "district": "koinadugu", "lat": 9.589, "lng": -11.552, "type": "hospital", "beds": 70, "staff": 25},
    {"id": "f18", "name": "Mattru Jong Hospital", "district": "bonthe", "lat": 7.624, "lng": -11.833, "type": "hospital", "beds": 50, "staff": 20},
]

SENSORS = [
    {"id": "s1", "name": "School 12 — Bo", "district": "bo", "lat": 7.97, "lng": -11.74, "type": "school"},
    {"id": "s2", "name": "Kenema CHC", "district": "kenema", "lat": 7.88, "lng": -11.19, "type": "clinic"},
    {"id": "s3", "name": "Port Loko Primary", "district": "port_loko", "lat": 8.77, "lng": -12.79, "type": "school"},
    {"id": "s4", "name": "Makeni Clinic", "district": "bombali", "lat": 8.88, "lng": -12.05, "type": "clinic"},
    {"id": "s5", "name": "Freetown Bridge Sensor", "district": "western_area_urban", "lat": 8.48, "lng": -13.23, "type": "bridge"},
    {"id": "s6", "name": "Kambia River Station", "district": "kambia", "lat": 9.13, "lng": -12.92, "type": "river"},
    {"id": "s7", "name": "Kailahun School", "district": "kailahun", "lat": 8.28, "lng": -10.57, "type": "school"},
    {"id": "s8", "name": "Bonthe Coastal Monitor", "district": "bonthe", "lat": 7.53, "lng": -12.51, "type": "coastal"},
    {"id": "s9", "name": "Moyamba Health Post", "district": "moyamba", "lat": 8.16, "lng": -12.43, "type": "clinic"},
    {"id": "s10", "name": "Kono Mining Area", "district": "kono", "lat": 8.65, "lng": -10.97, "type": "industrial"},
    {"id": "s11", "name": "Tonkolili School", "district": "tonkolili", "lat": 8.72, "lng": -11.95, "type": "school"},
    {"id": "s12", "name": "Pujehun Riverside", "district": "pujehun", "lat": 7.36, "lng": -11.72, "type": "river"},
]

COMMUNITY_REPORT_TYPES = [
    {"type": "mosquitoes", "label": "Mosquitoes increasing", "icon": "bug", "category": "vector"},
    {"type": "flooding", "label": "Bridge/road flooded", "icon": "waves", "category": "flood"},
    {"type": "medicine", "label": "Clinic has no medicine", "icon": "pill", "category": "supply"},
    {"type": "fever", "label": "Children with fever", "icon": "thermometer", "category": "disease"},
    {"type": "water", "label": "Water contaminated", "icon": "droplets", "category": "water"},
    {"type": "livestock", "label": "Dead livestock", "icon": "skull", "category": "environmental"},
]

# ──────────────── Helpers ────────────────

def _seed(seed_val: int = 42):
    """Deterministic but realistic-looking demo data."""
    random.seed(seed_val)

def _risk_level(score: float) -> str:
    if score >= 0.8: return "Extreme"
    if score >= 0.6: return "High"
    if score >= 0.4: return "Moderate"
    if score >= 0.2: return "Low"
    return "Minimal"

def _risk_color(score: float) -> str:
    if score >= 0.8: return "#943d3a"
    if score >= 0.6: return "#c8875c"
    if score >= 0.4: return "#c9a963"
    if score >= 0.2: return "#6b986f"
    return "#4a7a4f"

def _clamp(val, lo=0.0, hi=1.0):
    return max(lo, min(hi, val))


# ───────────────────── 1. Enhanced Situation Room ─────────────────────

@router.get("")
async def get_situation_room():
    """Aggregated national data for the situation room dashboard."""
    _seed()
    return {
        "national_risk_level": "High",
        "last_updated_minutes": 2,
        "ai_confidence_pct": 92,
        "districts_high_risk": 7,
        "facilities_threatened": 18,
        "active_flood_alerts": 12,
        "malaria_forecast_trend": "+23%",
        "children_at_risk": 183000,
        "sensor_online": 10,
        "sensor_total": 12,
        "community_reports_24h": 47,
        "recommended_actions": [
            {"action": "Deploy mosquito nets to Bo and Kenema", "priority": "critical", "icon": "shield"},
            {"action": "Increase ACT stock at 7 district hospitals", "priority": "critical", "icon": "pill"},
            {"action": "Notify 142 CHWs in high-risk districts", "priority": "high", "icon": "bell"},
            {"action": "Open emergency clinic in Pujehun", "priority": "high", "icon": "hospital"},
            {"action": "Pre-position flood supplies in Port Loko", "priority": "high", "icon": "package"},
            {"action": "Issue SMS alerts to 31,000 at-risk population", "priority": "medium", "icon": "message-square"},
        ],
    }


# ───────────────────── 2. Map Data (GeoJSON Layers) ─────────────────────

@router.get("/map-data")
async def get_map_data():
    """GeoJSON feature collections for all 10 map layers."""
    _seed()

    def make_district_features(layer_name: str, score_fn):
        features = []
        for d in DISTRICTS:
            score = score_fn(d)
            features.append({
                "type": "Feature",
                "properties": {
                    "id": d["id"],
                    "name": d["name"],
                    "layer": layer_name,
                    "score": round(score, 2),
                    "risk_level": _risk_level(score),
                    "color": _risk_color(score),
                    "population": d["population"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [d["lng"], d["lat"]],
                },
            })
        return features

    # Flood and Heat layers from real weather data
    def get_weather_scores(d):
        weather = weather_api.fetch_realtime_weather(d["lat"], d["lng"])
        if weather:
            # Map rainfall to flood score: 0-100mm -> 0.1-0.95
            flood = min(0.95, 0.1 + (weather["rainfall_24h"] / 100.0) * 0.85)
            # Map temperature to heat score: 25-40C -> 0.1-0.95
            heat = min(0.95, max(0.1, (weather["temperature_2m"] - 25.0) / 15.0 * 0.85 + 0.1))
            return flood, heat
        return 0.3, 0.3
        
    weather_scores_cache = {d["id"]: get_weather_scores(d) for d in DISTRICTS}

    flood_features = make_district_features("flood", lambda d: weather_scores_cache[d["id"]][0])

    # Malaria layer
    malaria_scores = {"bo": 0.78, "bonthe": 0.55, "bombali": 0.62, "kailahun": 0.82,
                      "kambia": 0.48, "kenema": 0.85, "koinadugu": 0.35, "kono": 0.72,
                      "moyamba": 0.58, "port_loko": 0.65, "pujehun": 0.75, "tonkolili": 0.52,
                      "western_area_rural": 0.42, "western_area_urban": 0.38}

    malaria_features = make_district_features("malaria", lambda d: malaria_scores.get(d["id"], 0.4))

    # Heat layer
    heat_features = make_district_features("heat", lambda d: weather_scores_cache[d["id"]][1])

    # Air quality layer
    aq_features = make_district_features("air_quality", lambda d: random.uniform(0.15, 0.65))

    # Vulnerability layer
    vuln_features = make_district_features("vulnerability", lambda d: random.uniform(0.25, 0.8))

    # Carbon layer
    carbon_features = make_district_features("carbon", lambda d: random.uniform(0.1, 0.5))

    # Facility markers
    facility_features = []
    for f in FACILITIES:
        facility_features.append({
            "type": "Feature",
            "properties": {
                "id": f["id"],
                "name": f["name"],
                "layer": "facilities",
                "type": f["type"],
                "beds": f["beds"],
                "staff": f["staff"],
                "district": f["district"],
            },
            "geometry": {"type": "Point", "coordinates": [f["lng"], f["lat"]]},
        })

    # School markers (subset of sensors that are schools)
    school_features = []
    for s in SENSORS:
        if s["type"] == "school":
            school_features.append({
                "type": "Feature",
                "properties": {
                    "id": s["id"],
                    "name": s["name"],
                    "layer": "schools",
                    "district": s["district"],
                },
                "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
            })

    # Sensor station markers
    sensor_features = []
    for s in SENSORS:
        online = random.random() > 0.15
        sensor_features.append({
            "type": "Feature",
            "properties": {
                "id": s["id"],
                "name": s["name"],
                "layer": "sensors",
                "type": s["type"],
                "online": online,
                "district": s["district"],
            },
            "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
        })

    # Community report markers
    report_features = []
    for i in range(35):
        rtype = random.choice(COMMUNITY_REPORT_TYPES)
        d = random.choice(DISTRICTS)
        report_features.append({
            "type": "Feature",
            "properties": {
                "id": f"cr{i+1}",
                "layer": "community_reports",
                "report_type": rtype["type"],
                "label": rtype["label"],
                "icon": rtype["icon"],
                "category": rtype["category"],
                "district": d["name"],
                "hours_ago": random.randint(1, 24),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    d["lng"] + random.uniform(-0.15, 0.15),
                    d["lat"] + random.uniform(-0.15, 0.15),
                ],
            },
        })

    return {
        "layers": {
            "flood": {"type": "FeatureCollection", "features": flood_features},
            "malaria": {"type": "FeatureCollection", "features": malaria_features},
            "heat": {"type": "FeatureCollection", "features": heat_features},
            "air_quality": {"type": "FeatureCollection", "features": aq_features},
            "facilities": {"type": "FeatureCollection", "features": facility_features},
            "schools": {"type": "FeatureCollection", "features": school_features},
            "community_reports": {"type": "FeatureCollection", "features": report_features},
            "sensors": {"type": "FeatureCollection", "features": sensor_features},
            "vulnerability": {"type": "FeatureCollection", "features": vuln_features},
            "carbon": {"type": "FeatureCollection", "features": carbon_features},
        },
        "center": [8.46, -11.78],
        "zoom": 7,
    }


# ───────────────────── 3. Timeline ─────────────────────

@router.get("/timeline/{day_offset}")
async def get_timeline(day_offset: int):
    """
    Return projected map state for a given day offset.
    -1 = yesterday, 0 = today, 1 = tomorrow, ... 30 = +30 days
    """
    _seed(42 + day_offset)
    factor = 1.0 + (day_offset * 0.035)

    district_states = []
    for d in DISTRICTS:
        base_flood = random.uniform(0.2, 0.7)
        base_malaria = random.uniform(0.3, 0.7)
        base_heat = random.uniform(0.25, 0.6)

        district_states.append({
            "id": d["id"],
            "name": d["name"],
            "lat": d["lat"],
            "lng": d["lng"],
            "flood_risk": round(_clamp(base_flood * factor), 2),
            "malaria_risk": round(_clamp(base_malaria * factor * 1.1), 2),
            "heat_risk": round(_clamp(base_heat * factor * 0.9), 2),
            "flood_color": _risk_color(_clamp(base_flood * factor)),
            "malaria_color": _risk_color(_clamp(base_malaria * factor * 1.1)),
            "heat_color": _risk_color(_clamp(base_heat * factor * 0.9)),
        })

    # Facility status changes with timeline
    facility_states = []
    for f in FACILITIES:
        preparedness = round(_clamp(random.uniform(0.5, 0.95) / max(factor, 0.5)), 2)
        facility_states.append({
            "id": f["id"],
            "name": f["name"],
            "lat": f["lat"],
            "lng": f["lng"],
            "preparedness": preparedness,
            "color": _risk_color(1 - preparedness),
        })

    labels = {
        -1: "Yesterday", 0: "Today", 1: "Tomorrow",
        3: "+3 Days", 7: "+7 Days", 14: "+14 Days", 30: "+30 Days",
    }

    return {
        "day_offset": day_offset,
        "label": labels.get(day_offset, f"+{day_offset} Days"),
        "districts": district_states,
        "facilities": facility_states,
        "summary": {
            "avg_flood_risk": round(sum(d["flood_risk"] for d in district_states) / len(district_states), 2),
            "avg_malaria_risk": round(sum(d["malaria_risk"] for d in district_states) / len(district_states), 2),
            "districts_high_risk": sum(1 for d in district_states if d["flood_risk"] >= 0.6 or d["malaria_risk"] >= 0.6),
            "facilities_at_risk": sum(1 for f in facility_states if f["preparedness"] < 0.6),
        },
    }


# ───────────────────── 4. Scenario Simulator ─────────────────────

class ScenarioInput(BaseModel):
    rainfall_increase_pct: float = Field(default=40, ge=0, le=200)
    temperature_increase_c: float = Field(default=3, ge=0, le=10)
    humidity_pct: float = Field(default=82, ge=0, le=100)
    population_movement: str = Field(default="high")  # low, medium, high

@router.post("/scenario")
async def run_scenario(data: ScenarioInput):
    """Run a what-if scenario and return projected impacts."""
    _seed()

    # Calculate impact multipliers
    rain_mult = 1 + (data.rainfall_increase_pct / 100) * 0.8
    temp_mult = 1 + (data.temperature_increase_c / 10) * 0.5
    humidity_mult = data.humidity_pct / 70
    pop_mult = {"low": 1.0, "medium": 1.3, "high": 1.6}.get(data.population_movement, 1.3)

    flood_risk = _clamp(0.45 * rain_mult * humidity_mult)
    malaria_risk = _clamp(0.4 * rain_mult * temp_mult * humidity_mult)
    combined = _clamp((flood_risk + malaria_risk) / 2 * pop_mult)

    facilities_impacted = min(18, int(combined * 24))
    roads_blocked = min(15, int(flood_risk * 12))
    population_exposed = int(combined * 65000)

    # Facility-level impact
    facility_impacts = []
    for f in FACILITIES[:8]:
        base_prep = random.uniform(0.65, 0.95)
        new_prep = _clamp(base_prep / (rain_mult * 0.7))
        facility_impacts.append({
            "id": f["id"],
            "name": f["name"],
            "lat": f["lat"],
            "lng": f["lng"],
            "baseline_preparedness": round(base_prep * 100),
            "projected_preparedness": round(new_prep * 100),
            "change": round((new_prep - base_prep) * 100),
        })

    # District-level impact
    district_impacts = []
    for d in DISTRICTS:
        base_flood = random.uniform(0.2, 0.7)
        base_malaria = random.uniform(0.3, 0.7)
        d_flood_risk = _clamp(base_flood * rain_mult * humidity_mult)
        d_malaria_risk = _clamp(base_malaria * rain_mult * temp_mult * humidity_mult)
        district_impacts.append({
            "name": d["name"],
            "lat": d["lat"],
            "lng": d["lng"],
            "flood_risk": round(d_flood_risk, 2),
            "malaria_risk": round(d_malaria_risk, 2),
            "flood_color": _risk_color(d_flood_risk),
            "malaria_color": _risk_color(d_malaria_risk),
        })

    suggestions = []
    if flood_risk >= 0.6:
        suggestions.append("Deploy flood supplies before rainfall peaks")
    if malaria_risk >= 0.6:
        suggestions.append("Pre-position ACTs and mosquito nets")
    if facilities_impacted > 5:
        suggestions.append("Activate backup generators at threatened facilities")
    if roads_blocked > 3:
        suggestions.append("Establish alternative supply routes via river transport")
    if population_exposed > 20000:
        suggestions.append("Issue SMS early warnings to at-risk population")
    suggestions.append("Brief District Medical Officers on projected scenario")

    return {
        "inputs": {
            "rainfall_increase": f"+{data.rainfall_increase_pct}%",
            "temperature_increase": f"+{data.temperature_increase_c}°C",
            "humidity": f"{data.humidity_pct}%",
            "population_movement": data.population_movement,
        },
        "outputs": {
            "flood_risk": {"score": round(flood_risk, 2), "level": _risk_level(flood_risk)},
            "malaria_risk": {"score": round(malaria_risk, 2), "level": _risk_level(malaria_risk)},
            "facilities_impacted": facilities_impacted,
            "roads_blocked": roads_blocked,
            "population_exposed": population_exposed,
        },
        "district_impacts": district_impacts,
        "facility_impacts": facility_impacts,
        "suggested_actions": suggestions,
    }


# ───────────────────── 5. AI Explainability ─────────────────────

@router.get("/ai-explain/{hazard_type}")
async def ai_explain(hazard_type: str):
    """
    Return AI explainability data for a hazard type.
    hazard_type: flood, malaria, heat, air_quality
    """
    explanations = {
        "malaria": {
            "hazard": "Malaria Risk",
            "risk_level": "High",
            "confidence": 91,
            "reasoning": [
                {"factor": "Rainfall ↑", "direction": "increasing", "impact": "high"},
                {"factor": "Humidity ↑", "direction": "increasing", "impact": "high"},
                {"factor": "Temperature optimal for transmission", "direction": "stable", "impact": "medium"},
                {"factor": "Community reports of mosquitoes ↑", "direction": "increasing", "impact": "medium"},
                {"factor": "Recent malaria cases ↑", "direction": "increasing", "impact": "high"},
            ],
            "contributors": [
                {"name": "Rainfall", "pct": 42, "color": "#6f8faa"},
                {"name": "Humidity", "pct": 23, "color": "#7d9f86"},
                {"name": "Cases", "pct": 18, "color": "#c9a35c"},
                {"name": "Temperature", "pct": 12, "color": "#c4876a"},
                {"name": "Other", "pct": 5, "color": "#9c7f8f"},
            ],
            "model_version": "CHEWS-Epi v2.1",
            "training_data": "Sierra Leone 2018–2025 surveillance records",
            "last_retrained": "2026-07-15",
        },
        "flood": {
            "hazard": "Flood Risk",
            "risk_level": "High",
            "confidence": 88,
            "reasoning": [
                {"factor": "72-hour rainfall accumulation ↑↑", "direction": "increasing", "impact": "critical"},
                {"factor": "River levels above seasonal norm", "direction": "increasing", "impact": "high"},
                {"factor": "Soil saturation at 94%", "direction": "increasing", "impact": "high"},
                {"factor": "Upstream dam release scheduled", "direction": "stable", "impact": "medium"},
                {"factor": "Urban drainage capacity exceeded", "direction": "increasing", "impact": "high"},
            ],
            "contributors": [
                {"name": "Rainfall", "pct": 38, "color": "#6f8faa"},
                {"name": "River Level", "pct": 28, "color": "#7d9f86"},
                {"name": "Soil Saturation", "pct": 18, "color": "#c9a35c"},
                {"name": "Drainage", "pct": 11, "color": "#c4876a"},
                {"name": "Other", "pct": 5, "color": "#9c7f8f"},
            ],
            "model_version": "CHEWS-Hydro v1.4",
            "training_data": "Sierra Leone hydrological data 2015–2025",
            "last_retrained": "2026-07-10",
        },
        "heat": {
            "hazard": "Heat Stress",
            "risk_level": "Moderate",
            "confidence": 85,
            "reasoning": [
                {"factor": "Daytime temperature +3°C above average", "direction": "increasing", "impact": "medium"},
                {"factor": "Humidity amplifying heat index", "direction": "increasing", "impact": "medium"},
                {"factor": "Urban heat island effect", "direction": "stable", "impact": "low"},
                {"factor": "Limited shade infrastructure", "direction": "stable", "impact": "medium"},
            ],
            "contributors": [
                {"name": "Temperature", "pct": 45, "color": "#c4876a"},
                {"name": "Humidity", "pct": 30, "color": "#7d9f86"},
                {"name": "Urban Effect", "pct": 15, "color": "#c9a35c"},
                {"name": "Other", "pct": 10, "color": "#9c7f8f"},
            ],
            "model_version": "CHEWS-Therm v1.1",
            "training_data": "West Africa meteorological data 2010–2025",
            "last_retrained": "2026-06-28",
        },
        "air_quality": {
            "hazard": "Air Quality",
            "risk_level": "Moderate",
            "confidence": 79,
            "reasoning": [
                {"factor": "PM2.5 elevated in Western Area", "direction": "increasing", "impact": "medium"},
                {"factor": "Seasonal biomass burning detected", "direction": "increasing", "impact": "medium"},
                {"factor": "Vehicle emissions in Freetown", "direction": "stable", "impact": "low"},
            ],
            "contributors": [
                {"name": "PM2.5", "pct": 48, "color": "#c75c54"},
                {"name": "Biomass", "pct": 32, "color": "#c9a35c"},
                {"name": "Vehicles", "pct": 12, "color": "#9c7f8f"},
                {"name": "Other", "pct": 8, "color": "#6f8faa"},
            ],
            "model_version": "CHEWS-AQ v1.0",
            "training_data": "Satellite AOD + ground sensors 2020–2025",
            "last_retrained": "2026-07-01",
        },
    }

    return explanations.get(hazard_type, explanations["malaria"])


# ───────────────────── 6. Community Reports ─────────────────────

@router.get("/community-reports")
async def get_community_reports():
    """Community intelligence — CHEW field reports clustered by type."""
    _seed()

    reports = []
    for i in range(47):
        rtype = random.choice(COMMUNITY_REPORT_TYPES)
        d = random.choice(DISTRICTS)
        reports.append({
            "id": f"cr{i+1}",
            "type": rtype["type"],
            "label": rtype["label"],
            "icon": rtype["icon"],
            "category": rtype["category"],
            "district": d["name"],
            "reporter": f"CHW-{random.randint(100, 999)}",
            "hours_ago": random.randint(1, 48),
            "verified": random.random() > 0.3,
            "lat": d["lat"] + random.uniform(-0.2, 0.2),
            "lng": d["lng"] + random.uniform(-0.2, 0.2),
        })

    # Cluster summary
    clusters = {}
    for r in reports:
        cat = r["category"]
        if cat not in clusters:
            clusters[cat] = {"category": cat, "count": 0, "districts": set()}
        clusters[cat]["count"] += 1
        clusters[cat]["districts"].add(r["district"])

    cluster_summary = []
    for cat, info in clusters.items():
        cluster_summary.append({
            "category": cat,
            "count": info["count"],
            "districts_affected": len(info["districts"]),
            "trending": info["count"] > 8,
        })

    return {
        "total_reports_24h": len([r for r in reports if r["hours_ago"] <= 24]),
        "total_reports_48h": len(reports),
        "reports": sorted(reports, key=lambda r: r["hours_ago"]),
        "clusters": sorted(cluster_summary, key=lambda c: c["count"], reverse=True),
    }


# ───────────────────── 7. Sensor Network ─────────────────────

@router.get("/sensors")
async def get_sensors():
    """Sensor network status — all nodes with readings."""
    _seed()

    sensor_data = []
    for s in SENSORS:
        online = random.random() > 0.15
        sensor_data.append({
            "id": s["id"],
            "name": s["name"],
            "district": s["district"],
            "type": s["type"],
            "lat": s["lat"],
            "lng": s["lng"],
            "online": online,
            "readings": {
                "temperature": round(random.uniform(27, 34), 1),
                "humidity": round(random.uniform(65, 92), 1),
                "rainfall_mm": round(random.uniform(0, 15), 1),
                "river_level": random.choice(["Normal", "Elevated", "High", "Critical"]),
                "aqi": random.randint(30, 150),
                "uv_index": round(random.uniform(5, 12), 1),
                "solar_radiation": round(random.uniform(200, 800), 0),
                "power_available": random.random() > 0.1,
            },
            "battery_pct": random.randint(45, 98) if online else random.randint(5, 30),
            "signal_strength": random.choice(["Strong", "Good", "Weak"]) if online else "None",
            "last_reading": f"{random.randint(1, 60)} min ago" if online else f"{random.randint(2, 24)} hours ago",
            "estimated": not online,
        })

    return {
        "total": len(sensor_data),
        "online": sum(1 for s in sensor_data if s["online"]),
        "offline": sum(1 for s in sensor_data if not s["online"]),
        "sensors": sensor_data,
    }


# ───────────────────── 8. Healthcare Digital Twin ─────────────────────

@router.get("/digital-twin/{facility_id}")
async def get_digital_twin(facility_id: str):
    """Healthcare digital twin — operational readiness model for a facility."""
    _seed()

    facility = next((f for f in FACILITIES if f["id"] == facility_id), None)
    if not facility:
        facility = FACILITIES[0]

    flood_risk_score = random.uniform(0.3, 0.75)
    power_reliability = random.uniform(0.4, 0.9)
    medicine_stock = random.uniform(0.55, 0.95)
    bed_occupancy = random.uniform(0.5, 0.95)
    staff_availability = random.uniform(0.45, 0.85)

    # Calculate preparedness as weighted average
    preparedness = (
        (1 - flood_risk_score) * 0.2
        + power_reliability * 0.2
        + medicine_stock * 0.25
        + (1 - bed_occupancy) * 0.15
        + staff_availability * 0.2
    )

    return {
        "facility": {
            "id": facility["id"],
            "name": facility["name"],
            "type": facility["type"],
            "district": facility["district"],
            "beds": facility["beds"],
            "staff": facility["staff"],
        },
        "metrics": {
            "flood_risk": {"value": round(flood_risk_score * 100), "level": _risk_level(flood_risk_score)},
            "power_reliability": {"value": round(power_reliability * 100), "level": "Low" if power_reliability < 0.5 else "Medium" if power_reliability < 0.75 else "High"},
            "medicine_stock": {"value": round(medicine_stock * 100), "level": "Critical" if medicine_stock < 0.3 else "Low" if medicine_stock < 0.5 else "Adequate"},
            "bed_occupancy": {"value": round(bed_occupancy * 100), "level": "Critical" if bed_occupancy > 0.9 else "High" if bed_occupancy > 0.75 else "Normal"},
            "staff_availability": {"value": round(staff_availability * 100), "level": "Critical" if staff_availability < 0.3 else "Low" if staff_availability < 0.5 else "Adequate"},
            "preparedness": {"value": round(preparedness * 100), "level": _risk_level(preparedness)},
        },
    }


@router.get("/digital-twins")
async def get_all_digital_twins():
    """Summary digital twin data for all facilities."""
    _seed()

    twins = []
    for f in FACILITIES:
        random.seed(hash(f["id"]) + 42)
        flood_risk_score = random.uniform(0.3, 0.75)
        power_reliability = random.uniform(0.4, 0.9)
        medicine_stock = random.uniform(0.55, 0.95)
        bed_occupancy = random.uniform(0.5, 0.95)
        staff_availability = random.uniform(0.45, 0.85)

        preparedness = (
            (1 - flood_risk_score) * 0.2
            + power_reliability * 0.2
            + medicine_stock * 0.25
            + (1 - bed_occupancy) * 0.15
            + staff_availability * 0.2
        )

        twins.append({
            "id": f["id"],
            "name": f["name"],
            "type": f["type"],
            "district": f["district"],
            "lat": f["lat"],
            "lng": f["lng"],
            "flood_risk": round(flood_risk_score * 100),
            "power_reliability": round(power_reliability * 100),
            "medicine_stock": round(medicine_stock * 100),
            "bed_occupancy": round(bed_occupancy * 100),
            "staff_availability": round(staff_availability * 100),
            "preparedness": round(preparedness * 100),
            "preparedness_level": _risk_level(preparedness),
        })

    return {"facilities": twins}


# ───────────────────── 9. Decision Support Engine ─────────────────────

@router.get("/decision-support")
async def get_decision_support():
    """Decision support engine — prioritized actions with generated sitrep."""
    return {
        "actions": [
            {"id": 1, "action": "Deploy 5 CHW teams to Bo and Kenema districts", "priority": "critical", "category": "deployment", "estimated_impact": "Covers 12,000 at-risk children", "timeline": "Immediate"},
            {"id": 2, "action": "Move ACT and RDT supplies to 7 high-risk facilities", "priority": "critical", "category": "supply", "estimated_impact": "Prevents stockout at 7 hospitals", "timeline": "Within 24 hours"},
            {"id": 3, "action": "Issue SMS alerts to 31,000 at-risk population", "priority": "high", "category": "communication", "estimated_impact": "Early warning coverage for 3 districts", "timeline": "Within 2 hours"},
            {"id": 4, "action": "Open temporary clinic in Pujehun", "priority": "high", "category": "infrastructure", "estimated_impact": "Serves 8,000 displaced population", "timeline": "Within 48 hours"},
            {"id": 5, "action": "Notify District Medical Officers in 7 districts", "priority": "high", "category": "coordination", "estimated_impact": "Activates district emergency protocols", "timeline": "Immediate"},
            {"id": 6, "action": "Increase malaria rapid testing at all facilities", "priority": "medium", "category": "clinical", "estimated_impact": "Catches 30% more cases early", "timeline": "Within 72 hours"},
            {"id": 7, "action": "Activate emergency funding mechanism", "priority": "medium", "category": "finance", "estimated_impact": "Unlocks $150,000 emergency response budget", "timeline": "Within 24 hours"},
            {"id": 8, "action": "Pre-position flood rescue equipment in Port Loko", "priority": "medium", "category": "logistics", "estimated_impact": "Response time reduced by 4 hours", "timeline": "Within 48 hours"},
        ],
        "sitrep_summary": {
            "title": "CHEWS Situation Report — Sierra Leone",
            "date": "29 July 2026",
            "overall_risk": "HIGH",
            "key_findings": [
                "7 of 14 districts at HIGH or EXTREME risk level",
                "Malaria forecast shows +23% increase over 30-day baseline",
                "12 active flood alerts across riverine communities",
                "18 health facilities in threatened zones",
                "183,000 children under 5 in at-risk areas",
                "47 community reports received in last 24 hours — mosquito activity trending up",
            ],
            "outlook": "Conditions expected to deteriorate over next 7–14 days as rainy season intensifies. Peak flood risk projected for +7 to +14 day window. Malaria case surge expected 2–4 weeks after peak rainfall.",
        },
    }

"""
Alert Engine Service
=====================
Generates, prioritises, and manages climate-health alerts.
Supports early warning triggers for floods, heat, air quality, disease outbreaks.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import NamedTuple
import uuid


class Alert(NamedTuple):
    id: str
    timestamp: str
    severity: str          # Info / Advisory / Watch / Warning / Emergency
    hazard_type: str       # flood / heat / air_quality / disease / multi
    title: str
    description: str
    affected_area: str
    trigger_value: float
    threshold: float
    actions: list[str]
    auto_trigger: bool     # whether this triggers automatic response


# In-memory alert store (would be DB in production)
_active_alerts: list[dict] = []

SEVERITY_ORDER = {"Info": 0, "Advisory": 1, "Watch": 2, "Warning": 3, "Emergency": 4}

# Alert thresholds
THRESHOLDS = {
    "flood": {"advisory": 0.3, "watch": 0.5, "warning": 0.7, "emergency": 0.85},
    "heat": {"advisory": 0.3, "watch": 0.5, "warning": 0.7, "emergency": 0.85},
    "air_quality": {"advisory": 100, "watch": 150, "warning": 200, "emergency": 300},
    "malaria": {"advisory": 0.3, "watch": 0.5, "warning": 0.6, "emergency": 0.8},
    "disease_cases": {"advisory": 10, "watch": 25, "warning": 50, "emergency": 100},
}


def evaluate_alert(
    hazard_type: str,
    current_value: float,
    location: str = "Unknown",
    context: str = "",
) -> Alert | None:
    """Evaluate whether current conditions warrant an alert."""
    thresholds = THRESHOLDS.get(hazard_type)
    if not thresholds:
        return None

    severity = None
    threshold_val = 0
    if current_value >= thresholds["emergency"]:
        severity = "Emergency"
        threshold_val = thresholds["emergency"]
    elif current_value >= thresholds["warning"]:
        severity = "Warning"
        threshold_val = thresholds["warning"]
    elif current_value >= thresholds["watch"]:
        severity = "Watch"
        threshold_val = thresholds["watch"]
    elif current_value >= thresholds["advisory"]:
        severity = "Advisory"
        threshold_val = thresholds["advisory"]

    if severity is None:
        return None

    titles = {
        "flood": f"Flood {severity}",
        "heat": f"Heat Stress {severity}",
        "air_quality": f"Air Quality {severity}",
        "malaria": f"Malaria Risk {severity}",
        "disease_cases": f"Disease Outbreak {severity}",
    }

    descriptions = {
        "flood": f"Flood risk at {current_value:.2f} exceeds {severity.lower()} threshold ({threshold_val})",
        "heat": f"Heat stress risk at {current_value:.2f} — {severity.lower()} level conditions",
        "air_quality": f"AQI at {current_value:.0f} — {severity.lower()} level air quality",
        "malaria": f"Malaria risk score {current_value:.2f} — {severity.lower()} threshold exceeded",
        "disease_cases": f"{current_value:.0f} cases reported — {severity.lower()} threshold ({threshold_val})",
    }

    actions_map = {
        "Advisory": ["Monitor conditions closely", "Brief community health volunteers"],
        "Watch": ["Prepare response resources", "Alert facility managers", "Review evacuation plans"],
        "Warning": ["Activate response protocols", "Deploy community alerts", "Pre-position supplies"],
        "Emergency": ["ACTIVATE EMERGENCY RESPONSE", "Deploy all available resources", "Coordinate with national authorities"],
    }

    alert = Alert(
        id=str(uuid.uuid4())[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        severity=severity,
        hazard_type=hazard_type,
        title=titles.get(hazard_type, f"{hazard_type} {severity}"),
        description=descriptions.get(hazard_type, context),
        affected_area=location,
        trigger_value=round(current_value, 4),
        threshold=threshold_val,
        actions=actions_map.get(severity, []),
        auto_trigger=severity in ("Warning", "Emergency"),
    )

    # Store alert
    _active_alerts.append(alert._asdict())
    # Keep only last 50
    if len(_active_alerts) > 50:
        _active_alerts.pop(0)

    return alert


def get_active_alerts(min_severity: str = "Advisory") -> list[dict]:
    """Return all active alerts at or above the given severity."""
    min_level = SEVERITY_ORDER.get(min_severity, 0)
    return [
        a for a in _active_alerts
        if SEVERITY_ORDER.get(a["severity"], 0) >= min_level
    ]


def clear_alerts():
    """Clear all alerts (for testing)."""
    _active_alerts.clear()

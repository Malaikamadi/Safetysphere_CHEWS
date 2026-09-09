"""
Map DHIS2 organisation units onto the existing CHEWS Master Facility List.

Does not create a second facility master. Unmapped Level-5 units are flagged;
coordinates and types are not invented.
"""

from __future__ import annotations

from typing import Optional

from config import dhis2 as cfg
from services.dhis2_service import parse_coordinates

try:
    from services import facility_mfl
except Exception:  # pragma: no cover — keep ingest usable if MFL import fails
    facility_mfl = None


def _ensure_mfl() -> None:
    if facility_mfl is None:
        return
    if not getattr(facility_mfl, "_initialized", False):
        facility_mfl.initialize()


def _mfl_by_dhis2(uid: str) -> Optional[dict]:
    _ensure_mfl()
    if facility_mfl is None:
        return None
    return facility_mfl.get_facility(uid)


def _parents_by_id(units: list[dict]) -> dict[str, dict]:
    return {u["id"]: u for u in units if u.get("id")}


def _walk_ancestors(unit: dict, by_id: dict[str, dict]) -> dict[int, dict]:
    """Return {level: {id, displayName}} for the unit and ancestors."""
    found: dict[int, dict] = {}
    current: Optional[dict] = unit
    seen: set[str] = set()
    while current and current.get("id") not in seen:
        seen.add(current["id"])
        level = current.get("level")
        if isinstance(level, int):
            found[level] = {
                "id": current.get("id"),
                "display_name": current.get("displayName") or current.get("name"),
            }
        parent = current.get("parent")
        if not parent:
            break
        if isinstance(parent, dict) and parent.get("id"):
            nxt = by_id.get(parent["id"])
            if nxt:
                current = nxt
            else:
                plevel = parent.get("level")
                if isinstance(plevel, int) and plevel not in found:
                    found[plevel] = {
                        "id": parent.get("id"),
                        "display_name": parent.get("displayName") or parent.get("name"),
                    }
                break
        else:
            break
    return found


def _facility_type_from_groups(unit: dict) -> Optional[str]:
    groups = unit.get("organisationUnitGroups") or []
    names = []
    for g in groups:
        if isinstance(g, dict) and g.get("displayName"):
            names.append(g["displayName"])
    if not names:
        return None
    return names[0]


def is_probable_facility(unit: dict) -> bool:
    """
    Level 5 in the verified SL HMIS tree is the facility level.
    Still require metadata: skip units with no id/name; do not treat other levels as facilities.
    """
    if not unit.get("id") or not (unit.get("displayName") or unit.get("name")):
        return False
    return unit.get("level") == 5


def map_organisation_unit(unit: dict, by_id: dict[str, dict]) -> dict:
    ancestors = _walk_ancestors(unit, by_id)
    lon, lat, geom = parse_coordinates(unit.get("geometry"))
    uid = unit.get("id") or ""
    mfl = _mfl_by_dhis2(uid) if uid else None
    level = unit.get("level")
    mapped = {
        "dhis2_org_unit_id": uid or None,
        "display_name": unit.get("displayName") or unit.get("name"),
        "level": level,
        "level_label": cfg.DHIS2_LEVEL_LABELS.get(level) if isinstance(level, int) else None,
        "parent_id": (unit.get("parent") or {}).get("id") if isinstance(unit.get("parent"), dict) else None,
        "parent_name": (unit.get("parent") or {}).get("displayName") if isinstance(unit.get("parent"), dict) else None,
        "country_id": (ancestors.get(1) or {}).get("id"),
        "country_name": (ancestors.get(1) or {}).get("display_name"),
        "district_id": (ancestors.get(2) or {}).get("id"),
        "district_name": (ancestors.get(2) or {}).get("display_name"),
        "council_id": (ancestors.get(3) or {}).get("id"),
        "council_name": (ancestors.get(3) or {}).get("display_name"),
        "zone_id": (ancestors.get(4) or {}).get("id"),
        "zone_name": (ancestors.get(4) or {}).get("display_name"),
        "longitude": lon,
        "latitude": lat,
        "geometry": geom,
        "feature_type": unit.get("featureType"),
        "facility_type": _facility_type_from_groups(unit),
        "is_facility_level": is_probable_facility(unit),
        "mfl_mapped": bool(mfl),
        "mfl_facility_id": (mfl or {}).get("facility_id"),
        "mfl_facility_name": (mfl or {}).get("facility_name"),
        "mfl_facility_type": (mfl or {}).get("facility_type"),
        "mfl_district": (mfl or {}).get("district"),
        "unmapped": is_probable_facility(unit) and not bool(mfl),
    }
    return mapped


def map_organisation_units(units: list[dict]) -> list[dict]:
    by_id = _parents_by_id(units)
    return [map_organisation_unit(u, by_id) for u in units]


def lookup_mapped(mapped_units: list[dict], org_unit_id: str) -> Optional[dict]:
    for row in mapped_units:
        if row.get("dhis2_org_unit_id") == org_unit_id:
            return row
    return None

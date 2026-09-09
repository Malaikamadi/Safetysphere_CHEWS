"""
Canonical Sierra Leone district keys for joining DHIS2, MFL, and climate.

Does not invent districts. Unknown names keep a slug of the original string.
"""

from __future__ import annotations

import re
from typing import Optional

# Display names used in admin_hierarchy.csv
ADMIN_DISTRICTS: tuple[str, ...] = (
    "Western Area Urban",
    "Western Area Rural",
    "Bo",
    "Pujehun",
    "Bonthe",
    "Kenema",
    "Port Loko",
    "Kambia",
    "Tonkolili",
    "Moyamba",
    "Bombali",
    "Kailahun",
    "Kono",
    "Koinadugu",
    "Falaba",
    "Karene",
)

_ALIAS_TO_SLUG = {
    "western area urban": "western_area_urban",
    "western area urban district": "western_area_urban",
    "western urban": "western_area_urban",
    "western urban district": "western_area_urban",
    "wau": "western_area_urban",
    "western area rural": "western_area_rural",
    "western area rural district": "western_area_rural",
    "western rural": "western_area_rural",
    "western rural district": "western_area_rural",
    "war": "western_area_rural",
    "port loko": "port_loko",
    "port loko district": "port_loko",
    "bo": "bo",
    "bo district": "bo",
    "pujehun": "pujehun",
    "bonthe": "bonthe",
    "kenema": "kenema",
    "kambia": "kambia",
    "tonkolili": "tonkolili",
    "moyamba": "moyamba",
    "bombali": "bombali",
    "kailahun": "kailahun",
    "kono": "kono",
    "koinadugu": "koinadugu",
    "falaba": "falaba",
    "karene": "karene",
}

_SLUG_TO_DISPLAY = {
    "western_area_urban": "Western Area Urban",
    "western_area_rural": "Western Area Rural",
    "bo": "Bo",
    "pujehun": "Pujehun",
    "bonthe": "Bonthe",
    "kenema": "Kenema",
    "port_loko": "Port Loko",
    "kambia": "Kambia",
    "tonkolili": "Tonkolili",
    "moyamba": "Moyamba",
    "bombali": "Bombali",
    "kailahun": "Kailahun",
    "kono": "Kono",
    "koinadugu": "Koinadugu",
    "falaba": "Falaba",
    "karene": "Karene",
}


def district_slug(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    text = str(name).strip()
    if not text:
        return None
    folded = re.sub(r"\s+", " ", text.casefold())
    folded = re.sub(r"\s+district$", "", folded)
    if folded in _ALIAS_TO_SLUG:
        return _ALIAS_TO_SLUG[folded]
    slug = re.sub(r"[^a-z0-9]+", "_", folded).strip("_")
    return slug or None


def display_name(slug: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    if slug and slug in _SLUG_TO_DISPLAY:
        return _SLUG_TO_DISPLAY[slug]
    if fallback:
        return fallback
    if slug:
        return slug.replace("_", " ").title()
    return None

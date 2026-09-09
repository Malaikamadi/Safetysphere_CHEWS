"""
DHIS2 period classification.

Preserves source_period exactly. Does not invent ISO weeks from monthly tokens.
Verified SL Analytics example: 202509 is monthly YYYYMM, not 2025W09.
"""

from __future__ import annotations

import re
from typing import Optional

from config import dhis2 as cfg

_MONTHLY = re.compile(r"^\d{6}$")
_DAILY = re.compile(r"^\d{8}$")
_WEEKLY = re.compile(r"^\d{4}W\d{1,2}$", re.IGNORECASE)
_QUARTER = re.compile(r"^\d{4}Q[1-4]$", re.IGNORECASE)
_YEAR = re.compile(r"^\d{4}$")


def classify_period(period: Optional[str]) -> dict:
    """
    Return source_period, period_type, normalized_period.

    normalized_period equals source_period only when the type is confirmed
    (monthly/weekly/daily/quarterly/yearly). Relative query tokens and
    unknown strings get normalized_period=None.
    """
    source = "" if period is None else str(period).strip()
    result = {
        "source_period": source,
        "period_type": "unknown",
        "normalized_period": None,
    }
    if not source:
        return result
    if source in cfg.RELATIVE_PERIODS or source.startswith("LAST_") or source.startswith("THIS_"):
        result["period_type"] = "relative"
        return result
    if _WEEKLY.match(source):
        result["period_type"] = "weekly"
        result["normalized_period"] = source
        return result
    if _MONTHLY.match(source):
        result["period_type"] = "monthly"
        result["normalized_period"] = source  # keep 202509; never 2025W09
        return result
    if _DAILY.match(source):
        result["period_type"] = "daily"
        result["normalized_period"] = source
        return result
    if _QUARTER.match(source):
        result["period_type"] = "quarterly"
        result["normalized_period"] = source.upper()
        return result
    if _YEAR.match(source):
        result["period_type"] = "yearly"
        result["normalized_period"] = source
        return result
    return result


def is_valid_source_period(period: Optional[str]) -> bool:
    info = classify_period(period)
    if not info["source_period"]:
        return False
    return info["period_type"] != "unknown"

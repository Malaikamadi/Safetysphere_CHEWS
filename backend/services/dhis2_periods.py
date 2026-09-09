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


def parse_yyyymm(period: str) -> tuple[int, int]:
    """Parse YYYYMM. Raises ValueError if not a monthly token."""
    token = str(period).strip()
    if not _MONTHLY.match(token):
        raise ValueError(f"Not a monthly YYYYMM period: {period!r}")
    year, month = int(token[:4]), int(token[4:6])
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month in period: {period!r}")
    return year, month


def format_yyyymm(year: int, month: int) -> str:
    return f"{year:04d}{month:02d}"


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, (idx % 12) + 1


def last_complete_month(now=None) -> str:
    """YYYYMM of the last fully completed calendar month (UTC)."""
    from datetime import datetime, timezone
    current = now or datetime.now(timezone.utc)
    year, month = add_months(current.year, current.month, -1)
    return format_yyyymm(year, month)


def expand_monthly_range(start: str, end: str) -> list[str]:
    """Inclusive list of YYYYMM tokens from start through end. Never uses LAST_5_YEARS."""
    y0, m0 = parse_yyyymm(start)
    y1, m1 = parse_yyyymm(end)
    if (y0, m0) > (y1, m1):
        raise ValueError(f"Monthly range start {start} is after end {end}")
    out: list[str] = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(format_yyyymm(y, m))
        y, m = add_months(y, m, 1)
    return out


def historical_window(
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    months: int = 36,
    now=None,
) -> tuple[str, str, list[str]]:
    """
    Explicit monthly extract window.

    Default: `months` consecutive YYYYMM ending at the last complete month.
    Does not emit DHIS2 relative tokens (LAST_12_MONTHS / LAST_5_YEARS).
    """
    if months < 1:
        raise ValueError("historical months must be >= 1")
    end_token = end.strip() if end else last_complete_month(now)
    if start:
        start_token = start.strip()
    else:
        ey, em = parse_yyyymm(end_token)
        sy, sm = add_months(ey, em, -(months - 1))
        start_token = format_yyyymm(sy, sm)
    tokens = expand_monthly_range(start_token, end_token)
    return start_token, end_token, tokens


def chunk_months(months: list[str], size: int = 12) -> list[list[str]]:
    if size < 1:
        raise ValueError("chunk size must be >= 1")
    return [months[i:i + size] for i in range(0, len(months), size)]


def yyyymm_to_date_bounds(start: str, end: str) -> tuple[str, str]:
    """Inclusive calendar dates for Open-Meteo Archive (YYYY-MM-DD)."""
    y0, m0 = parse_yyyymm(start)
    y1, m1 = parse_yyyymm(end)
    last_day = _days_in_month(y1, m1)
    return f"{y0:04d}-{m0:02d}-01", f"{y1:04d}-{m1:02d}-{last_day:02d}"


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        ny, nm = year + 1, 1
    else:
        ny, nm = year, month + 1
    from datetime import date
    return (date(ny, nm, 1) - date(year, month, 1)).days

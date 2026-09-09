"""
Central DHIS2 configuration for CHEWS.

Credentials are read from the environment only. Never import this module
from frontend code. Never log username, password, or token values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

# Existing data-lake layers (do not introduce a parallel lake)
RAW_DHIS2_DIR = DATA_DIR / "01_raw" / "dhis2"
STAGING_DHIS2_DIR = DATA_DIR / "02_staging" / "dhis2"
CURATED_SURVEILLANCE_DIR = DATA_DIR / "03_curated" / "surveillance"
AI_FEATURES_DIR = DATA_DIR / "04_ai" / "features"
MOCK_DIR = RAW_DHIS2_DIR / "mock"


def _load_dotenv() -> None:
    """Load repo-root or backend .env if python-dotenv is installed. Safe no-op otherwise."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (REPO_ROOT / ".env", BACKEND_DIR / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


_load_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
DHIS2_BASE_URL = (_env("DHIS2_BASE_URL", "https://sl.dhis2.org/hmis23") or "").rstrip("/")
DHIS2_USERNAME = _env("DHIS2_USERNAME")
DHIS2_PASSWORD = _env("DHIS2_PASSWORD")
DHIS2_API_TOKEN = _env("DHIS2_API_TOKEN")
DHIS2_MOCK_MODE = _env_bool("DHIS2_MOCK_MODE", True)
DHIS2_TIMEOUT_SECONDS = _env_int("DHIS2_TIMEOUT_SECONDS", 30)
DHIS2_RETRIES = _env_int("DHIS2_RETRIES", 3)
DHIS2_STALE_DAYS = _env_int("DHIS2_STALE_DAYS", 60)
DHIS2_INCLUDE_SUPPORTING = _env_bool("DHIS2_INCLUDE_SUPPORTING", False)

# Period: LAST_12_MONTHS, LAST_6_MONTHS, THIS_YEAR, LAST_12_WEEKS, or comma-separated DHIS2 periods
DHIS2_PERIOD = _env("DHIS2_PERIOD", "LAST_12_MONTHS") or "LAST_12_MONTHS"
DHIS2_OU_DIMENSION = _env("DHIS2_OU_DIMENSION", "LEVEL-5") or "LEVEL-5"

# ---------------------------------------------------------------------------
# Indicators — core malaria (used in Analytics + curated ML table)
# ---------------------------------------------------------------------------
DHIS2_INDICATORS: dict[str, str] = {
    "malaria_confirmed": "XHQqFqfUfIf",
    "malaria_confirmed_u5": "tjRoHuika9k",
    "malaria_tests": "mwrOKePWg2r",
    "malaria_rdt_positive": "VWdhdKpLVof",
    "child_malaria_death": "MM7wnFwsi7q",
}

DHIS2_INDICATOR_NAMES: dict[str, str] = {
    "malaria_confirmed": "Malaria confirmed (RDT/Microscopy) (sum)",
    "malaria_confirmed_u5": "Malaria confirmed (RDT/Microscopy) 0-4 years (sum)",
    "malaria_tests": "Malaria test done at OPD (sum)",
    "malaria_rdt_positive": "Malaria RDT positive (Facility/Community)",
    "child_malaria_death": "% of Child death - Malaria - DPPI-DHAS",
}

# Count-like indicators eligible for the wide ML feature table.
# child_malaria_death is a percentage — kept in the long table only.
DHIS2_COUNT_INDICATORS: tuple[str, ...] = (
    "malaria_confirmed",
    "malaria_confirmed_u5",
    "malaria_tests",
    "malaria_rdt_positive",
)

DHIS2_PERCENT_INDICATORS: tuple[str, ...] = ("child_malaria_death",)

# Supporting indicators — stored for future use; not sent to the prototype ML model
DHIS2_SUPPORTING_INDICATORS: dict[str, str] = {
    "treatment_within_24h": "Al09gOVkmCz",
    "testing_coverage": "X6rctVtXiAF",
}

DHIS2_SUPPORTING_NAMES: dict[str, str] = {
    "treatment_within_24h": "Treatment within 24 hours",
    "testing_coverage": "Expected malaria cases receiving microscopy/RDT",
}

# Verified Sierra Leone HMIS hierarchy (do not assume other countries match)
DHIS2_LEVEL_LABELS: dict[int, str] = {
    1: "country",
    2: "district",
    3: "council",
    4: "zone",
    5: "facility",
}

# Relative period tokens DHIS2 Analytics accepts
RELATIVE_PERIODS = frozenset({
    "THIS_MONTH", "LAST_MONTH", "LAST_3_MONTHS", "LAST_6_MONTHS", "LAST_12_MONTHS",
    "THIS_BIMONTH", "LAST_BIMONTH", "LAST_6_BIMONTHS",
    "THIS_QUARTER", "LAST_QUARTER", "LAST_4_QUARTERS",
    "THIS_SIX_MONTH", "LAST_SIX_MONTH", "LAST_2_SIXMONTHS",
    "THIS_YEAR", "LAST_YEAR", "LAST_5_YEARS",
    "THIS_WEEK", "LAST_WEEK", "LAST_4_WEEKS", "LAST_12_WEEKS", "LAST_52_WEEKS",
})


def indicator_id_to_key() -> dict[str, str]:
    mapping = {uid: key for key, uid in DHIS2_INDICATORS.items()}
    mapping.update({uid: key for key, uid in DHIS2_SUPPORTING_INDICATORS.items()})
    return mapping


def indicator_name_for_id(uid: str) -> Optional[str]:
    key = indicator_id_to_key().get(uid)
    if not key:
        return None
    return DHIS2_INDICATOR_NAMES.get(key) or DHIS2_SUPPORTING_NAMES.get(key)


def analytics_indicator_ids(*, include_supporting: Optional[bool] = None) -> list[str]:
    ids = list(DHIS2_INDICATORS.values())
    use_supporting = DHIS2_INCLUDE_SUPPORTING if include_supporting is None else include_supporting
    if use_supporting:
        ids.extend(DHIS2_SUPPORTING_INDICATORS.values())
    # preserve order, drop duplicates
    seen: set[str] = set()
    out: list[str] = []
    for uid in ids:
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


def live_credentials_configured() -> bool:
    if DHIS2_API_TOKEN:
        return True
    return bool(DHIS2_USERNAME and DHIS2_PASSWORD)


def credentials_configured() -> bool:
    if DHIS2_MOCK_MODE:
        return True
    return live_credentials_configured()


def public_status() -> dict:
    """Safe-to-return connection status (no secrets)."""
    auth = "none"
    if DHIS2_MOCK_MODE:
        auth = "mock"
    elif DHIS2_API_TOKEN:
        auth = "api_token"
    elif DHIS2_USERNAME and DHIS2_PASSWORD:
        auth = "basic"
    elif DHIS2_USERNAME or DHIS2_PASSWORD:
        auth = "incomplete"
    return {
        "base_url": DHIS2_BASE_URL,
        "mock_mode": DHIS2_MOCK_MODE,
        "auth_method": auth,
        "credentials_configured": credentials_configured(),
        "period": DHIS2_PERIOD,
        "ou_dimension": DHIS2_OU_DIMENSION,
        "include_supporting": DHIS2_INCLUDE_SUPPORTING,
        "timeout_seconds": DHIS2_TIMEOUT_SECONDS,
        "core_indicators": DHIS2_INDICATORS,
        "supporting_indicators": DHIS2_SUPPORTING_INDICATORS,
    }

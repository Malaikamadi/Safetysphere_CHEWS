"""
Open-Meteo Archive configuration.

Separate from the realtime flood weather client in services/weather_api.py.
Historical malaria climate must not use 24-hour forecast precipitation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from config.dhis2 import DATA_DIR, REPO_ROOT, _env, _env_bool, _env_int, _load_dotenv

_load_dotenv()

ARCHIVE_BASE_URL = (_env("OPEN_METEO_ARCHIVE_URL", "https://archive-api.open-meteo.com/v1/archive") or "").rstrip("/")
CLIMATE_ARCHIVE_MOCK = _env_bool("CLIMATE_ARCHIVE_MOCK_MODE", True)
CLIMATE_ARCHIVE_TIMEOUT_SECONDS = _env_int("CLIMATE_ARCHIVE_TIMEOUT_SECONDS", 30)
CLIMATE_ARCHIVE_SLEEP_SECONDS = float(_env("CLIMATE_ARCHIVE_SLEEP_SECONDS", "0.25") or "0.25")

RAW_CLIMATE_ARCHIVE_DIR = DATA_DIR / "01_raw" / "climate" / "open_meteo_archive"
MOCK_CLIMATE_DIR = DATA_DIR / "01_raw" / "climate" / "mock"
CURATED_CLIMATE_DIR = DATA_DIR / "03_curated" / "climate"

DAILY_VARIABLES = (
    "temperature_2m_mean",
    "precipitation_sum",
    "relative_humidity_2m_mean",
)

TIMEZONE = "Africa/Abidjan"


def mock_fixture_path() -> Path:
    return MOCK_CLIMATE_DIR / "archive_monthly_sample.json"

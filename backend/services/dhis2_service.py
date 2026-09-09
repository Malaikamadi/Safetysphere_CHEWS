"""
DHIS2 Analytics / organisation-unit client for CHEWS.

Calls the Sierra Leone HMIS from the backend only. Never expose credentials.
Mock mode reads fixtures under backend/data/01_raw/dhis2/mock/.
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from config import dhis2 as cfg
from services.dhis2_periods import classify_period

logger = logging.getLogger("chews.dhis2")


class Dhis2Error(Exception):
    """Base DHIS2 client error (safe message, no secrets)."""


class Dhis2AuthError(Dhis2Error):
    """Authentication failed or credentials missing."""


class Dhis2HttpError(Dhis2Error):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class Dhis2ParseError(Dhis2Error):
    """Response was not usable Analytics/org-unit JSON."""


def parse_numeric(value: Any) -> Optional[float]:
    """Convert a DHIS2 cell to float. Missing/blank → None (never coerced to 0)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return None
        return float(value)
    text = str(value).strip()
    if text == "" or text.lower() in {"null", "na", "n/a", "none"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_analytics_rows(payload: Any) -> list[dict]:
    """
    Normalize DHIS2 Analytics JSON.

    Rows are [data_dimension, period, organisation_unit, value].
    Missing values stay None.
    """
    if payload is None:
        raise Dhis2ParseError("Analytics payload is empty")
    if not isinstance(payload, dict):
        raise Dhis2ParseError("Analytics payload must be a JSON object")
    rows = payload.get("rows")
    if rows is None:
        raise Dhis2ParseError("Analytics payload missing 'rows'")
    if not isinstance(rows, list):
        raise Dhis2ParseError("Analytics 'rows' must be a list")

    records: list[dict] = []
    for index, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            raise Dhis2ParseError(f"Malformed analytics row at index {index}")
        raw_value = row[3]
        numeric = parse_numeric(raw_value)
        invalid_numeric = raw_value not in (None, "") and numeric is None
        source_period = str(row[1]).strip() if row[1] is not None else ""
        classified = classify_period(source_period)
        records.append({
            "indicator_id": str(row[0]).strip() if row[0] is not None else "",
            "period": source_period,
            "source_period": source_period,
            "period_type": classified["period_type"],
            "normalized_period": classified["normalized_period"],
            "org_unit_id": str(row[2]).strip() if row[2] is not None else "",
            "value": numeric,
            "value_raw": raw_value,
            "invalid_numeric": invalid_numeric,
        })
    return records


def parse_org_unit_payload(payload: Any) -> list[dict]:
    if payload is None:
        raise Dhis2ParseError("Organisation unit payload is empty")
    if isinstance(payload, dict) and "organisationUnits" in payload:
        units = payload["organisationUnits"]
    elif isinstance(payload, dict) and "id" in payload:
        units = [payload]
    elif isinstance(payload, list):
        units = payload
    else:
        raise Dhis2ParseError("Organisation unit payload missing organisationUnits")
    if not isinstance(units, list):
        raise Dhis2ParseError("organisationUnits must be a list")
    return [u for u in units if isinstance(u, dict)]


def parse_coordinates(geometry: Any) -> tuple[Optional[float], Optional[float], Any]:
    """
    DHIS2 geometry coordinates are [longitude, latitude].
    Non-point geometries keep raw geometry and leave lat/lon unset (no centroid guess).
    """
    if geometry is None or geometry == "":
        return None, None, None
    geom = geometry
    if isinstance(geometry, str):
        try:
            geom = json.loads(geometry)
        except json.JSONDecodeError:
            return None, None, geometry
    if not isinstance(geom, dict):
        return None, None, geom
    coords = geom.get("coordinates")
    gtype = (geom.get("type") or "").lower()
    if gtype == "point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        lon = parse_numeric(coords[0])
        lat = parse_numeric(coords[1])
        return lon, lat, geom
    return None, None, geom


class Dhis2Client:
    """HTTP client for /api/analytics and /api/organisationUnits."""

    def __init__(
        self,
        *,
        mock: Optional[bool] = None,
        opener: Optional[Callable[[str], dict]] = None,
    ):
        self.mock = cfg.DHIS2_MOCK_MODE if mock is None else mock
        self._opener = opener

    def fetch_analytics(
        self,
        *,
        indicator_ids: Optional[list[str]] = None,
        period: Optional[str] = None,
        ou_dimension: Optional[str] = None,
        include_supporting: Optional[bool] = None,
    ) -> dict:
        ids = indicator_ids or cfg.analytics_indicator_ids(include_supporting=include_supporting)
        pe = period or cfg.DHIS2_PERIOD
        ou = ou_dimension or cfg.DHIS2_OU_DIMENSION
        if self.mock:
            logger.info("DHIS2 Analytics: mock mode (period=%s ou=%s indicators=%s)", pe, ou, len(ids))
            return self._load_mock_analytics()
        query = {
            "dimension": [
                f"dx:{';'.join(ids)}",
                f"pe:{pe}",
                f"ou:{ou}",
            ],
            "skipMeta": "false",
            "includeMetadataDetails": "false",
        }
        return self._get("/api/analytics", query)

    def fetch_organisation_units(
        self,
        *,
        level: Optional[int] = None,
        fields: str = "id,displayName,level,parent[id,displayName,level],geometry,featureType,organisationUnitGroups[id,displayName]",
        page_size: int = 1000,
    ) -> list[dict]:
        if self.mock:
            logger.info("DHIS2 organisationUnits: mock mode")
            return parse_org_unit_payload(self._load_mock_org_units())
        units: list[dict] = []
        page = 1
        while True:
            query: dict[str, Any] = {
                "fields": fields,
                "paging": "true",
                "pageSize": str(page_size),
                "page": str(page),
            }
            if level is not None:
                query["level"] = str(level)
            payload = self._get("/api/organisationUnits", query)
            batch = parse_org_unit_payload(payload)
            units.extend(batch)
            pager = payload.get("pager") if isinstance(payload, dict) else None
            if not pager or page >= int(pager.get("pageCount") or 1):
                break
            page += 1
        return units

    def _load_mock_analytics(self) -> dict:
        path = cfg.MOCK_DIR / "analytics_sample.json"
        if not path.exists():
            raise Dhis2Error(f"Mock analytics fixture missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_mock_org_units(self) -> dict:
        path = cfg.MOCK_DIR / "organisation_units_sample.json"
        if not path.exists():
            raise Dhis2Error(f"Mock organisationUnits fixture missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _get(self, path: str, query: dict[str, Any]) -> dict:
        if not cfg.live_credentials_configured():
            raise Dhis2AuthError(
                "DHIS2 credentials are not configured. Set DHIS2_USERNAME and "
                "DHIS2_PASSWORD (or DHIS2_API_TOKEN), or enable DHIS2_MOCK_MODE=true."
            )
        if self._opener:
            url = self._build_url(path, query)
            return self._opener(url)
        return self._http_get_json(path, query)

    def _build_url(self, path: str, query: dict[str, Any]) -> str:
        pairs: list[tuple[str, str]] = []
        for key, value in query.items():
            if isinstance(value, list):
                for item in value:
                    pairs.append((key, str(item)))
            else:
                pairs.append((key, str(value)))
        qs = urllib.parse.urlencode(pairs, doseq=False, safe=":;")
        return f"{cfg.DHIS2_BASE_URL}{path}?{qs}"

    def _http_get_json(self, path: str, query: dict[str, Any]) -> dict:
        url = self._build_url(path, query)
        safe_url = url.split("@")[-1] if "@" in url else url
        headers = {
            "Accept": "application/json",
            "User-Agent": "CHEWS-DHIS2/1.0",
        }
        if cfg.DHIS2_API_TOKEN:
            headers["Authorization"] = f"ApiToken {cfg.DHIS2_API_TOKEN}"
        else:
            import base64
            raw = f"{cfg.DHIS2_USERNAME}:{cfg.DHIS2_PASSWORD}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")

        retries = max(1, cfg.DHIS2_RETRIES)
        timeout = max(1, cfg.DHIS2_TIMEOUT_SECONDS)
        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
                    status = getattr(resp, "status", 200)
                    body = resp.read().decode("utf-8")
                    if status < 200 or status >= 300:
                        raise Dhis2HttpError(f"DHIS2 HTTP {status}", status_code=status)
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError as exc:
                        raise Dhis2ParseError("DHIS2 response was not valid JSON") from exc
                    if not isinstance(data, dict):
                        raise Dhis2ParseError("DHIS2 JSON root must be an object")
                    logger.info("DHIS2 GET ok path=%s status=%s attempt=%s", path, status, attempt)
                    return data
            except Dhis2ParseError:
                raise
            except urllib.error.HTTPError as exc:
                code = exc.code
                if code in (401, 403):
                    raise Dhis2AuthError("DHIS2 authentication failed") from None
                last_error = Dhis2HttpError(f"DHIS2 HTTP {code}", status_code=code)
                if code < 500 and code != 429:
                    raise last_error from None
                logger.warning("DHIS2 HTTP %s path=%s attempt=%s/%s", code, path, attempt, retries)
            except urllib.error.URLError as exc:
                last_error = Dhis2HttpError("DHIS2 network error")
                logger.warning("DHIS2 network error path=%s attempt=%s/%s", path, attempt, retries)
                _ = exc
            except TimeoutError:
                last_error = Dhis2HttpError("DHIS2 request timed out")
                logger.warning("DHIS2 timeout path=%s attempt=%s/%s", path, attempt, retries)
            if attempt < retries:
                time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))

        logger.error("DHIS2 GET failed path=%s url_host=%s", path, urllib.parse.urlparse(safe_url).netloc)
        raise last_error or Dhis2HttpError("DHIS2 request failed")

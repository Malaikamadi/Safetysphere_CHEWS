"""
Probe DHIS2 Analytics month-by-month for malaria indicators before 202307.

Does not persist, does not overwrite the 535-row panel, does not train.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import dhis2 as cfg  # noqa: E402
from services.dhis2_historical import CORE_HISTORICAL_KEYS, core_indicator_ids  # noqa: E402
from services.dhis2_service import Dhis2Client, parse_analytics_rows  # noqa: E402

INDICATOR_FIELDS = (
    "id,name,shortName,displayName,created,lastUpdated,description,"
    "numeratorDescription,denominatorDescription,indicatorType[id,displayName]"
)

PROBE_MONTHS = [
    "202306",
    "202301",
    "202207",
    "202201",
    "202107",
    "202101",
    "202007",
    "202001",
    "201907",
    "201901",
    "201807",
    "201801",
    "201707",
    "201701",
    "201607",
    "201601",
]


def fetch_indicator_metadata(client: Dhis2Client) -> dict:
    out = {}
    ids = cfg.DHIS2_INDICATORS
    for key in CORE_HISTORICAL_KEYS:
        iid = ids[key]
        payload = client._get(f"/api/indicators/{iid}", {"fields": INDICATOR_FIELDS})
        out[key] = {
            "id": payload.get("id"),
            "name": payload.get("name") or payload.get("displayName"),
            "shortName": payload.get("shortName"),
            "created": payload.get("created"),
            "lastUpdated": payload.get("lastUpdated"),
            "description": payload.get("description"),
            "numeratorDescription": payload.get("numeratorDescription"),
            "expected_id": iid,
            "id_match": payload.get("id") == iid,
        }
    return out


def probe_month(client: Dhis2Client, month: str) -> dict:
    ids = core_indicator_ids()
    payload = client.fetch_analytics(indicator_ids=ids, period=month, ou_dimension=cfg.DHIS2_OU_DIMENSION)
    records = parse_analytics_rows(payload)
    by_dx: dict[str, int] = {}
    periods = set()
    for rec in records:
        dx = rec.get("data_element") or rec.get("dx") or rec.get("indicator")
        # parse_analytics_rows field names
        dx = rec.get("dx") or rec.get("data_element_id") or rec.get("indicator_id")
        periods.add(rec.get("period") or rec.get("source_period"))
        key = str(dx)
        by_dx[key] = by_dx.get(key, 0) + 1
    # Count by mapped indicator using indicator_id from parser
    by_key = {k: 0 for k in CORE_HISTORICAL_KEYS}
    id_to_key = {cfg.DHIS2_INDICATORS[k]: k for k in CORE_HISTORICAL_KEYS}
    for rec in records:
        iid = rec.get("indicator_id") or rec.get("dx")
        name = id_to_key.get(iid)
        if name:
            by_key[name] += 1
        val = rec.get("value")
        if name == "malaria_confirmed" and val is not None:
            pass
    confirmed_vals = []
    for rec in records:
        iid = rec.get("indicator_id") or rec.get("dx")
        if iid == cfg.DHIS2_INDICATORS["malaria_confirmed"] and rec.get("value") is not None:
            try:
                confirmed_vals.append(float(rec["value"]))
            except (TypeError, ValueError):
                pass
    http_width = payload.get("width")
    height = payload.get("height")
    return {
        "month": month,
        "http_rows_height": height,
        "http_width": http_width,
        "parsed_records": len(records),
        "records_by_indicator": by_key,
        "unique_periods": sorted(p for p in periods if p),
        "malaria_confirmed_nonzero_cells": sum(1 for v in confirmed_vals if v != 0),
        "malaria_confirmed_sum_if_present": sum(confirmed_vals) if confirmed_vals else None,
        "empty": len(records) == 0,
    }


def main() -> None:
    if cfg.DHIS2_MOCK_MODE:
        print("WARNING: DHIS2_MOCK_MODE is true; live probe requires mock=False override")
    client = Dhis2Client(mock=False)
    meta = fetch_indicator_metadata(client)
    probes = []
    for month in PROBE_MONTHS:
        try:
            result = probe_month(client, month)
            probes.append(result)
            print(json.dumps(result), flush=True)
        except Exception as exc:
            probes.append({"month": month, "error": type(exc).__name__, "message": str(exc)[:300]})
            print(json.dumps(probes[-1]), flush=True)
    out = {
        "indicator_metadata": meta,
        "probes": probes,
        "mock": client.mock,
        "base_url": cfg.DHIS2_BASE_URL,
    }
    path = BACKEND / "data" / "04_ai" / "training_sets" / "malaria_historical_probe.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()

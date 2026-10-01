"""Download Chicago open data from the Socrata API into data/raw/.

Pulls three datasets:
  crimes  (ijzp-q8t2)  geolocated, timestamped incidents
  crashes (85ca-t3if)  traffic crashes
  lights  (zuxi-7xem)  reported street-light outages

Works with or without a Socrata app token (the token just raises rate limits). Hits the
plain REST endpoint with requests, so sodapy isn't a hard dependency.

Run:  python -m scripts.ingest_socrata
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

import requests

from backend.app import config


def _since_iso(months: int) -> str:
    """ISO date `months` before today, in a format Socrata SoQL accepts."""
    days = int(months * 30.44)
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")


def _fetch(dataset: str, params: dict) -> list:
    """Page through a Socrata dataset up to MAX_ROWS rows."""
    url = f"https://{config.SOCRATA_DOMAIN}/resource/{dataset}.json"
    headers = {}
    if config.SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = config.SOCRATA_APP_TOKEN

    rows: list = []
    page_size = 50000
    offset = 0
    while len(rows) < config.MAX_ROWS:
        page = dict(params)
        page["$limit"] = min(page_size, config.MAX_ROWS - len(rows))
        page["$offset"] = offset
        resp = requests.get(url, params=page, headers=headers, timeout=120)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        print(f"    fetched {len(rows):,} rows...", flush=True)
        if len(batch) < page["$limit"]:
            break
    return rows


def ingest_crimes() -> None:
    import pandas as pd

    since = _since_iso(config.MONTHS)
    print(f"[crimes] downloading since {since} ...")
    rows = _fetch(
        config.DATASET_CRIMES,
        {
            "$select": "date,primary_type,latitude,longitude,community_area",
            "$where": f"date > '{since}' AND latitude IS NOT NULL",
            "$order": "date",
        },
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.dropna(subset=["latitude", "longitude"])
    df.to_csv(config.CRIMES_RAW_PATH, index=False)
    print(f"[crimes] saved {len(df):,} rows -> {config.CRIMES_RAW_PATH}")


def ingest_crashes() -> None:
    import pandas as pd

    since = _since_iso(config.MONTHS)
    print(f"[crashes] downloading since {since} ...")
    rows = _fetch(
        config.DATASET_CRASHES,
        {
            "$select": "crash_date,latitude,longitude,first_crash_type,prim_contributory_cause",
            "$where": f"crash_date > '{since}' AND latitude IS NOT NULL",
            "$order": "crash_date",
        },
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.dropna(subset=["latitude", "longitude"])
    df.to_csv(config.CRASHES_RAW_PATH, index=False)
    print(f"[crashes] saved {len(df):,} rows -> {config.CRASHES_RAW_PATH}")


def ingest_lights() -> None:
    import pandas as pd

    print("[lights] downloading street-light outage reports ...")
    rows = _fetch(
        config.DATASET_LIGHTS,
        {
            "$select": "creation_date,latitude,longitude",
            "$where": "latitude IS NOT NULL",
            "$order": "creation_date DESC",
        },
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.dropna(subset=["latitude", "longitude"])
    df.to_csv(config.LIGHTS_RAW_PATH, index=False)
    print(f"[lights] saved {len(df):,} rows -> {config.LIGHTS_RAW_PATH}")


def main() -> None:
    print(f"Socrata token: {'set' if config.SOCRATA_APP_TOKEN else 'NOT set (rate-limited)'}")
    ingest_crimes()
    ingest_crashes()
    ingest_lights()
    print("Ingest complete.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as exc:
        print(f"HTTP error from Socrata: {exc}", file=sys.stderr)
        sys.exit(1)

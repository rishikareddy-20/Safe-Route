"""Shared paths and settings. Everything imports from here so artifact locations
live in one place."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional
    pass

# config.py lives at <root>/backend/app/config.py, so parents[2] is the repo root.
BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

for _d in (RAW_DIR, PROCESSED_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Generated artifacts
GRAPH_PATH = PROCESSED_DIR / "chicago.graphml"
SEGMENT_FEATURES_PATH = PROCESSED_DIR / "segment_features.parquet"
TRAIN_TABLE_PATH = PROCESSED_DIR / "train.parquet"
EDGES_GEOJSON_PATH = PROCESSED_DIR / "edges.geojson"

CRIMES_RAW_PATH = RAW_DIR / "crimes.csv"
CRASHES_RAW_PATH = RAW_DIR / "crashes.csv"
LIGHTS_RAW_PATH = RAW_DIR / "lights.csv"

MODEL_PATH = MODELS_DIR / "risk_model.txt"
MODEL_META_PATH = MODELS_DIR / "model_meta.json"
METRICS_PATH = MODELS_DIR / "metrics.json"

# Runtime settings (override via environment / .env)
SOCRATA_DOMAIN = "data.cityofchicago.org"
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "").strip() or None

PLACE = os.getenv("SAFEROUTE_PLACE", "Chicago, Illinois")
MONTHS = int(os.getenv("SAFEROUTE_MONTHS", "12"))
MAX_ROWS = int(os.getenv("SAFEROUTE_MAX_ROWS", "200000"))

# Socrata dataset ids
DATASET_CRIMES = "ijzp-q8t2"
DATASET_CRASHES = "85ca-t3if"
DATASET_LIGHTS = "zuxi-7xem"

# UTM zone 16N: a metric CRS for Chicago so buffered spatial joins are in meters.
METRIC_CRS = "EPSG:26916"
WGS84 = "EPSG:4326"

# How close (meters) an incident has to be to count toward a street segment.
INCIDENT_BUFFER_M = 50.0

# Crime severity weights, higher meaning more relevant to pedestrian safety.
CRIME_SEVERITY = {
    "HOMICIDE": 5.0,
    "CRIMINAL SEXUAL ASSAULT": 5.0,
    "CRIM SEXUAL ASSAULT": 5.0,
    "ROBBERY": 4.0,
    "BATTERY": 3.0,
    "ASSAULT": 3.0,
    "WEAPONS VIOLATION": 3.0,
    "KIDNAPPING": 4.0,
    "THEFT": 1.5,
    "MOTOR VEHICLE THEFT": 1.5,
    "BURGLARY": 1.5,
    "NARCOTICS": 1.0,
}
DEFAULT_CRIME_SEVERITY = 1.0

# Hours treated as night (8pm to 6am), used as a feature and for lighting weight.
NIGHT_HOURS = set(range(20, 24)) | set(range(0, 6))

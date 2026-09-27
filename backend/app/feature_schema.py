"""One place that defines the model's feature layout."""
from __future__ import annotations

from typing import List, Tuple

from . import config

# Per-segment static features (don't depend on time of day).
STATIC_MODEL_COLUMNS: List[str] = [
    "crime_density",    # severity-weighted incidents per 100m of segment
    "area_crime_norm",  # community-area baseline crime (relative), reduces bias
    "accident_count",   # nearby pedestrian/vehicle crashes
    "light_out_count",  # nearby reported street-light outages
    "lit",              # 1 if OSM says the segment is lit, else 0
    "length",           # segment length in meters
    "road_class",       # ordinal: bigger road = higher class number
]

# Time-of-day features, recomputed per request.
TEMPORAL_COLUMNS: List[str] = [
    "hour",         # 0-23
    "is_night",     # 1 if hour in config.NIGHT_HOURS
    "hour_weight",  # fraction of this segment's historical incidents at this hour
]

FEATURE_COLUMNS: List[str] = STATIC_MODEL_COLUMNS + TEMPORAL_COLUMNS

# Hourly-histogram columns in the static table. Used to derive hour_weight; not fed
# to the model directly.
HIST_COLUMNS: List[str] = [f"hist_{h}" for h in range(24)]

_EPS = 1e-9


def make_feature_frame(static_df, hour: int):
    """Build the model feature matrix for a given hour.

    Parameters
    ----------
    static_df : pandas.DataFrame
        Per-segment static features. Must contain STATIC_MODEL_COLUMNS + HIST_COLUMNS
        + a ``seg_id`` column.
    hour : int
        Hour of day (0-23).

    Returns
    -------
    (X, seg_ids) : Tuple[pandas.DataFrame, pandas.Series]
        ``X`` has exactly FEATURE_COLUMNS in order; ``seg_ids`` aligns row-for-row.
    """
    import numpy as np

    df = static_df.copy()

    hist = df[HIST_COLUMNS].to_numpy(dtype="float64")
    totals = hist.sum(axis=1) + _EPS
    df["hour"] = int(hour)
    df["is_night"] = 1 if hour in config.NIGHT_HOURS else 0
    df["hour_weight"] = hist[:, int(hour)] / totals

    X = df[FEATURE_COLUMNS].astype("float64")
    return X, df["seg_id"]

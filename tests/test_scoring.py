"""Feature assembly and the model-free heuristic scorer."""
from __future__ import annotations

import pandas as pd

from backend.app import config
from backend.app.feature_schema import (
    FEATURE_COLUMNS,
    HIST_COLUMNS,
    STATIC_MODEL_COLUMNS,
    make_feature_frame,
)
from backend.app.scoring import SegmentScorer


def _static_df() -> pd.DataFrame:
    rows = []
    # seg X: dangerous, incidents concentrated at hour 22 (night)
    # seg Y: quiet, incidents spread thin at hour 9 (day)
    base = {c: 0.0 for c in STATIC_MODEL_COLUMNS + HIST_COLUMNS}
    x = dict(base, seg_id="X", crime_density=50.0, length=100.0, road_class=3)
    x["hist_22"] = 40.0
    y = dict(base, seg_id="Y", crime_density=1.0, length=100.0, road_class=1)
    y["hist_9"] = 2.0
    rows = [x, y]
    return pd.DataFrame(rows)[["seg_id"] + STATIC_MODEL_COLUMNS + HIST_COLUMNS]


def test_make_feature_frame_columns_and_temporal():
    df = _static_df()
    X, seg_ids = make_feature_frame(df, hour=22)
    assert list(X.columns) == FEATURE_COLUMNS
    assert list(seg_ids) == ["X", "Y"]
    # Hour 22 is night.
    assert X["is_night"].iloc[0] == 1
    # For seg X all its incidents are at hour 22 -> hour_weight ~ 1.
    assert X["hour_weight"].iloc[0] > 0.9
    # A daytime hour is not night.
    X_day, _ = make_feature_frame(df, hour=9)
    assert X_day["is_night"].iloc[0] == 0


def test_heuristic_risk_bounds_and_ordering():
    scorer = SegmentScorer()
    scorer.static_df = _static_df()
    scorer.loaded = True  # skip disk load; use heuristic (no model)

    risk = scorer.risk_for_hour(22)
    assert set(risk) == {"X", "Y"}
    for v in risk.values():
        assert 0.0 <= v <= 1.0
    # The dangerous segment should score higher than the quiet one.
    assert risk["X"] > risk["Y"]


def test_night_hours_config():
    assert 22 in config.NIGHT_HOURS
    assert 9 not in config.NIGHT_HOURS

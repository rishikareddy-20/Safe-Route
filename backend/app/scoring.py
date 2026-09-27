"""Per-segment risk scoring.

Loads the static feature table plus the trained LightGBM model and returns a
{seg_id: risk} map for a given hour, with risk in [0, 1]. Results are cached per hour.

If no model is present it falls back to a crime-density heuristic, so the app still
works before anything is trained.
"""
from __future__ import annotations

import json
from typing import Dict, Optional

from . import config
from .feature_schema import HIST_COLUMNS, make_feature_frame


class SegmentScorer:
    def __init__(self) -> None:
        self.static_df = None          # pandas DataFrame of per-segment features
        self.model = None              # lightgbm Booster
        self.p_min: float = 0.0        # prediction normalization bounds
        self.p_max: float = 1.0
        self.loaded = False
        self._cache: Dict[int, Dict[str, float]] = {}

    def load(self) -> bool:
        """Load static features (required) and the model (optional)."""
        if not config.SEGMENT_FEATURES_PATH.exists():
            self.loaded = False
            return False

        import pandas as pd

        self.static_df = pd.read_parquet(config.SEGMENT_FEATURES_PATH)
        self.static_df["seg_id"] = self.static_df["seg_id"].astype(str)

        if config.MODEL_PATH.exists():
            try:
                import lightgbm as lgb

                self.model = lgb.Booster(model_file=str(config.MODEL_PATH))
                if config.MODEL_META_PATH.exists():
                    meta = json.loads(config.MODEL_META_PATH.read_text())
                    self.p_min = float(meta.get("pred_min", 0.0))
                    self.p_max = float(meta.get("pred_max", 1.0))
            except Exception:
                self.model = None

        self.loaded = True
        return True

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    def risk_for_hour(self, hour: int) -> Dict[str, float]:
        """Return {seg_id: risk in [0,1]} for the given hour, cached per hour."""
        if not self.loaded:
            raise RuntimeError("Scorer not loaded")
        hour = int(hour) % 24
        if hour in self._cache:
            return self._cache[hour]

        risk = self._predict(hour) if self.model is not None else self._heuristic(hour)
        self._cache[hour] = risk
        return risk

    def _predict(self, hour: int) -> Dict[str, float]:
        import numpy as np

        X, seg_ids = make_feature_frame(self.static_df, hour)
        preds = self.model.predict(X)
        denom = (self.p_max - self.p_min) or 1.0
        norm = np.clip((preds - self.p_min) / denom, 0.0, 1.0)
        return dict(zip(seg_ids.astype(str), norm.astype(float)))

    def _heuristic(self, hour: int) -> Dict[str, float]:
        """Model-free fallback: crime density, nudged by this hour's incident share."""
        import numpy as np

        df = self.static_df
        density = df["crime_density"].to_numpy(dtype="float64")
        # Normalize to [0,1] against the 95th percentile so outliers don't dominate.
        top = np.percentile(density, 95) or 1.0
        base = np.clip(density / top, 0.0, 1.0)

        hist = df[HIST_COLUMNS].to_numpy(dtype="float64")
        totals = hist.sum(axis=1) + 1e-9
        hour_weight = hist[:, int(hour)] / totals
        night_boost = 0.15 if hour in config.NIGHT_HOURS else 0.0

        risk = np.clip(0.7 * base + 0.3 * (base * hour_weight * 24) + night_boost, 0, 1)
        return dict(zip(df["seg_id"].astype(str), risk.astype(float)))

    def risk_geojson(self, hour: int, bbox: Optional[tuple] = None) -> dict:
        """GeoJSON FeatureCollection of segments with risk, for the heatmap layer.

        Needs edges.geojson (written by build_features). bbox is
        (min_lng, min_lat, max_lng, max_lat) to limit the features returned.
        """
        if not config.EDGES_GEOJSON_PATH.exists():
            return {"type": "FeatureCollection", "features": []}

        risk = self.risk_for_hour(hour)
        data = json.loads(config.EDGES_GEOJSON_PATH.read_text())
        out = []
        for feat in data.get("features", []):
            seg_id = str(feat.get("properties", {}).get("seg_id"))
            if seg_id not in risk:
                continue
            if bbox and not _feature_in_bbox(feat, bbox):
                continue
            feat = dict(feat)
            feat["properties"] = {"seg_id": seg_id, "risk": round(risk[seg_id], 4)}
            out.append(feat)
        return {"type": "FeatureCollection", "features": out}


def _feature_in_bbox(feat: dict, bbox: tuple) -> bool:
    min_lng, min_lat, max_lng, max_lat = bbox
    coords = feat.get("geometry", {}).get("coordinates", [])
    for lng, lat in coords:
        if min_lng <= lng <= max_lng and min_lat <= lat <= max_lat:
            return True
    return False

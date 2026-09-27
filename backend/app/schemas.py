"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LatLng(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    origin: LatLng
    destination: LatLng
    # 0.0 = safest possible, 1.0 = fastest possible.
    alpha: float = Field(0.5, ge=0.0, le=1.0)
    # Hour of day (0-23) the trip is taken; risk is time-dependent.
    hour: int = Field(18, ge=0, le=23)


class RouteStats(BaseModel):
    label: str  # "fastest" | "safest" | "balanced"
    alpha: float
    distance_m: float
    travel_time_s: float
    mean_risk: float  # length-weighted mean risk over the route, 0-1
    # Polyline as [[lat, lng], ...].
    geometry: List[List[float]]


class RouteResponse(BaseModel):
    routes: List[RouteStats]
    hour: int


class HealthResponse(BaseModel):
    status: str
    graph_loaded: bool
    model_loaded: bool
    n_nodes: Optional[int] = None
    n_edges: Optional[int] = None
    place: str

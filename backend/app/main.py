"""FastAPI application: loads artifacts at startup and serves routing + risk endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .graph_loader import GraphContext
from .routing import Router
from .schemas import HealthResponse, RouteRequest, RouteResponse
from .scoring import SegmentScorer

app = FastAPI(
    title="Safe-Route Recommendation API",
    version="0.1.0",
    description="Routes ranked by a tunable blend of travel time and learned risk.",
)

# Allow the Vite dev server (and any localhost port) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared, process-wide state.
_graph = GraphContext()
_scorer = SegmentScorer()
_router: Optional[Router] = None


@app.on_event("startup")
def _load_artifacts() -> None:
    global _router
    graph_ok = _graph.load()
    scorer_ok = _scorer.load()
    if graph_ok and scorer_ok:
        _router = Router(_graph, _scorer)


def _require_ready() -> Router:
    if _router is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Artifacts not loaded. Run the offline pipeline first: "
                "`python -m scripts.run_pipeline` (need graph + segment features)."
            ),
        )
    return _router


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok" if _router is not None else "not_ready",
        graph_loaded=_graph.loaded,
        model_loaded=_scorer.model_loaded,
        n_nodes=_graph.n_nodes,
        n_edges=_graph.n_edges,
        place=config.PLACE,
    )


@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest) -> RouteResponse:
    router = _require_ready()
    routes = router.route(
        origin=(req.origin.lat, req.origin.lng),
        destination=(req.destination.lat, req.destination.lng),
        alpha=req.alpha,
        hour=req.hour,
    )
    if not routes:
        raise HTTPException(
            status_code=422,
            detail="No path found between the given points within the loaded graph.",
        )
    return RouteResponse(routes=routes, hour=req.hour)


@app.get("/segment-risk")
def segment_risk(
    hour: int = Query(18, ge=0, le=23),
    min_lng: Optional[float] = None,
    min_lat: Optional[float] = None,
    max_lng: Optional[float] = None,
    max_lat: Optional[float] = None,
) -> dict:
    """GeoJSON of segments with risk for the given hour (optionally within a bbox)."""
    _require_ready()
    bbox = None
    if None not in (min_lng, min_lat, max_lng, max_lat):
        bbox = (min_lng, min_lat, max_lng, max_lat)
    return _scorer.risk_geojson(hour, bbox)

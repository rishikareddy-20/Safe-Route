"""Routing engine behaviour on the synthetic graph."""
from __future__ import annotations

from backend.app.routing import Router

ORIGIN = (0.0, 0.0)       # node 1 (lat, lng)
DESTINATION = (1.0, 1.0)  # node 4


def _by_label(routes):
    return {r["label"]: r for r in routes}


def test_fastest_takes_risky_short_path(graph_ctx, scorer):
    router = Router(graph_ctx, scorer)
    routes = _by_label(router.route(ORIGIN, DESTINATION, alpha=1.0, hour=18))
    fastest = routes["fastest"]
    # Fast path is 1->2->4, total travel_time 60s, length 200m.
    assert fastest["travel_time_s"] == 60.0
    assert fastest["distance_m"] == 200.0
    # It traverses the high-risk segments.
    assert fastest["mean_risk"] > 0.5


def test_safest_takes_low_risk_detour(graph_ctx, scorer):
    router = Router(graph_ctx, scorer)
    routes = _by_label(router.route(ORIGIN, DESTINATION, alpha=0.0, hour=18))
    safest = routes["safest"]
    # Safe path is 1->3->4, longer (600m) but low risk.
    assert safest["distance_m"] == 600.0
    assert safest["mean_risk"] < 0.2


def test_fastest_and_safest_differ(graph_ctx, scorer):
    router = Router(graph_ctx, scorer)
    routes = _by_label(router.route(ORIGIN, DESTINATION, alpha=0.5, hour=18))
    assert "fastest" in routes and "safest" in routes
    assert routes["fastest"]["geometry"] != routes["safest"]["geometry"]


def test_geometry_is_latlng_pairs(graph_ctx, scorer):
    router = Router(graph_ctx, scorer)
    routes = router.route(ORIGIN, DESTINATION, alpha=0.5, hour=18)
    for r in routes:
        assert len(r["geometry"]) >= 2
        for pt in r["geometry"]:
            assert len(pt) == 2  # [lat, lng]

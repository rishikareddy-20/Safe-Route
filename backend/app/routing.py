"""Multi-objective routing.

Given origin/destination coordinates, a weight `alpha` (safety vs speed) and an hour,
find paths that minimize `alpha * travel_time + (1 - alpha) * risk` per edge. Both terms
are normalized to [0, 1], so alpha slides smoothly between the fastest and safest route.
The optimizer is plain Dijkstra rather than a learned policy, which keeps routes
explainable and tunable.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from .graph_loader import GraphContext
from .scoring import SegmentScorer


class Router:
    def __init__(self, graph: GraphContext, scorer: SegmentScorer) -> None:
        self.graph = graph
        self.scorer = scorer

    def route(
        self,
        origin: tuple,       # (lat, lng)
        destination: tuple,  # (lat, lng)
        alpha: float,
        hour: int,
    ) -> List[dict]:
        """Return the fastest, safest and balanced (user-alpha) routes."""
        import networkx as nx

        G = self.graph.G
        risk = self.scorer.risk_for_hour(hour)

        src = self.graph.nearest_node(*origin)
        dst = self.graph.nearest_node(*destination)

        plans = [("fastest", 1.0), ("safest", 0.0), ("balanced", float(alpha))]
        results: List[dict] = []
        seen_paths: Dict[tuple, str] = {}

        for label, a in plans:
            weight = self._make_weight(risk, a)
            try:
                path = nx.shortest_path(G, src, dst, weight=weight)
            except nx.NetworkXNoPath:
                continue
            except nx.NodeNotFound:
                continue

            key = tuple(path)
            # If two plans produce the same path, keep only the first label.
            if key in seen_paths:
                continue
            seen_paths[key] = label

            results.append(self._path_stats(path, label, a, risk))

        return results

    def _make_weight(self, risk: Dict[str, float], alpha: float):
        def weight(u, v, d):
            # d is a key->attr mapping (MultiDiGraph) or an attr dict (simple graph).
            candidates = _edge_candidates(d)
            best = math.inf
            for attr in candidates:
                tt = float(attr.get("tt_norm", 0.0) or 0.0)
                r = risk.get(str(attr.get("seg_id")), 0.0)
                cost = alpha * tt + (1.0 - alpha) * r
                # Tiny length term breaks ties and avoids zero-cost cycles.
                cost += 1e-6 * (float(attr.get("length", 0.0) or 0.0) / 1000.0)
                best = min(best, cost)
            return best

        return weight

    def _best_edge(self, u, v, alpha, risk):
        """Pick the edge between u and v that this alpha would actually take."""
        edges = self.graph.G.get_edge_data(u, v)
        if edges is None:
            return None
        best_attr, best_cost = None, math.inf
        candidates = _edge_candidates(edges)
        for attr in candidates:
            tt = float(attr.get("tt_norm", 0.0) or 0.0)
            r = risk.get(str(attr.get("seg_id")), 0.0)
            cost = alpha * tt + (1.0 - alpha) * r
            if cost < best_cost:
                best_cost, best_attr = cost, attr
        return best_attr

    def _path_stats(self, path: List[int], label: str, alpha: float, risk) -> dict:
        total_len = 0.0
        total_tt = 0.0
        risk_len_sum = 0.0
        coords: List[List[float]] = []

        for u, v in zip(path[:-1], path[1:]):
            attr = self._best_edge(u, v, alpha, risk)
            if attr is None:
                continue
            length = float(attr.get("length", 0.0) or 0.0)
            total_len += length
            total_tt += float(attr.get("travel_time", 0.0) or 0.0)
            risk_len_sum += risk.get(str(attr.get("seg_id")), 0.0) * length

            seg_coords = self.graph.edge_geometry_latlng(u, v, attr)
            if coords and seg_coords and coords[-1] == seg_coords[0]:
                coords.extend(seg_coords[1:])
            else:
                coords.extend(seg_coords)

        mean_risk = (risk_len_sum / total_len) if total_len else 0.0
        return {
            "label": label,
            "alpha": round(alpha, 3),
            "distance_m": round(total_len, 1),
            "travel_time_s": round(total_tt, 1),
            "mean_risk": round(mean_risk, 4),
            "geometry": coords,
        }


def _edge_candidates(d):
    """Turn whatever NetworkX hands the weight callable into a list of attr dicts.

    A MultiGraph gives a key->attr mapping (a dict from get_edge_data, or an AtlasView
    during traversal); a simple graph gives a single attr dict.
    """
    from collections.abc import Mapping

    if isinstance(d, Mapping) and len(d):
        first = next(iter(d.values()))
        if isinstance(first, Mapping):
            return list(d.values())
    return [d]

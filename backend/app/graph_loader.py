"""Load the street graph and expose the helpers the router needs.

build_graph.py produces the graph offline and saves it as GraphML. Each edge carries
length (m), travel_time (s, from OSMnx speed imputation), a stable seg_id used to join
risk scores, and tt_norm (travel_time scaled to [0, 1], computed here). Edges may also
carry a shapely geometry for nicer polylines.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from . import config


class GraphContext:
    """Holds the loaded graph plus derived lookups. One instance per process."""

    def __init__(self) -> None:
        self.G = None
        self.loaded = False
        self._node_xy: Dict[int, Tuple[float, float]] = {}
        self._max_tt: float = 1.0

    def load(self) -> bool:
        """Load the graph from disk. True on success, False if the file is missing."""
        if not config.GRAPH_PATH.exists():
            self.loaded = False
            return False

        import osmnx as ox  # lazy import so this module loads without geo libs

        G = ox.load_graphml(config.GRAPH_PATH)

        # Scale travel_time to [0, 1] so it's comparable with risk scores.
        max_tt = 0.0
        for _u, _v, data in G.edges(data=True):
            tt = _as_float(data.get("travel_time"))
            if tt is None:
                # No speed: assume ~30 km/h (8.33 m/s) from length.
                length = _as_float(data.get("length")) or 1.0
                tt = length / 8.33
                data["travel_time"] = tt
            max_tt = max(max_tt, tt)
            # GraphML stores everything as strings; coerce length back to float.
            data["length"] = _as_float(data.get("length")) or 0.0
        max_tt = max_tt or 1.0
        for _u, _v, data in G.edges(data=True):
            data["tt_norm"] = data["travel_time"] / max_tt

        # Cache node coordinates (x = lon, y = lat).
        self._node_xy = {
            n: (_as_float(d.get("x")), _as_float(d.get("y")))
            for n, d in G.nodes(data=True)
        }

        self.G = G
        self._max_tt = max_tt
        self.loaded = True
        return True

    @property
    def n_nodes(self) -> Optional[int]:
        return self.G.number_of_nodes() if self.loaded else None

    @property
    def n_edges(self) -> Optional[int]:
        return self.G.number_of_edges() if self.loaded else None

    def nearest_node(self, lat: float, lng: float) -> int:
        """Id of the graph node closest to (lat, lng)."""
        if not self.loaded:
            raise RuntimeError("Graph not loaded")
        try:
            import osmnx as ox

            return int(ox.nearest_nodes(self.G, X=lng, Y=lat))
        except Exception:
            # Pure-Python fallback for tests, or if osmnx nearest is unavailable.
            best_n, best_d = None, math.inf
            for n, (x, y) in self._node_xy.items():
                if x is None or y is None:
                    continue
                d = (x - lng) ** 2 + (y - lat) ** 2
                if d < best_d:
                    best_n, best_d = n, d
            if best_n is None:
                raise RuntimeError("No nodes with coordinates in graph")
            return int(best_n)

    def node_latlng(self, node: int) -> Tuple[float, float]:
        x, y = self._node_xy[node]
        return (y, x)  # (lat, lng)

    def edge_geometry_latlng(self, u: int, v: int, data: dict) -> List[List[float]]:
        """[[lat,lng], ...] polyline for an edge, using its geometry when present."""
        geom = data.get("geometry")
        if geom is not None and hasattr(geom, "coords"):
            return [[lat, lng] for lng, lat in geom.coords]
        # No geometry: straight line between the endpoints.
        return [list(self.node_latlng(u)), list(self.node_latlng(v))]


def _as_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

"""Build the routable street graph from OpenStreetMap via OSMnx.

Downloads the network for config.PLACE, imputes edge speeds and travel times, gives each
edge a stable seg_id, and saves it as GraphML.

Run:  python -m scripts.build_graph
"""
from __future__ import annotations

from backend.app import config


def main() -> None:
    import osmnx as ox

    print(f"[graph] downloading OSM network for: {config.PLACE}")
    # 'drive' gives a routable road network; use 'walk' for a pedestrian graph.
    G = ox.graph_from_place(config.PLACE, network_type="drive")

    print(f"[graph] {G.number_of_nodes():,} nodes / {G.number_of_edges():,} edges")

    # Impute speeds (km/h) from road type, then travel times (seconds).
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    # Give every edge a stable string seg_id for joining risk scores later.
    for i, (_u, _v, _k, data) in enumerate(G.edges(keys=True, data=True)):
        data["seg_id"] = str(i)
        # Normalize a 'lit' flag from OSM tags (missing on most edges).
        lit = data.get("lit")
        data["lit"] = 1 if str(lit).lower() in ("yes", "true", "1") else 0

    ox.save_graphml(G, config.GRAPH_PATH)
    print(f"[graph] saved -> {config.GRAPH_PATH}")
    print("Graph build complete.")


if __name__ == "__main__":
    main()

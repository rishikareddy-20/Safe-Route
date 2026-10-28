"""Shared test fixtures: a tiny synthetic street graph and a mock scorer.

The graph has two ways from node 1 to node 4:
  * risky/fast : 1 -> 2 -> 4  (low travel time, high risk)
  * safe/slow  : 1 -> 3 -> 4  (high travel time, low risk)

so the fastest and safest routes are provably different.
"""
from __future__ import annotations

import networkx as nx
import pytest

from backend.app.graph_loader import GraphContext


@pytest.fixture
def graph_ctx() -> GraphContext:
    G = nx.MultiDiGraph()
    # (node, lng, lat)
    coords = {1: (0.0, 0.0), 2: (0.0, 1.0), 3: (1.0, 0.0), 4: (1.0, 1.0)}
    for n, (x, y) in coords.items():
        G.add_node(n, x=x, y=y)

    def add(u, v, seg_id, length, travel_time, tt_norm):
        G.add_edge(u, v, key=0, seg_id=seg_id, length=length,
                   travel_time=travel_time, tt_norm=tt_norm)

    # risky/fast path
    add(1, 2, "A", 100.0, 30.0, 0.30)
    add(2, 4, "B", 100.0, 30.0, 0.30)
    # safe/slow path
    add(1, 3, "C", 300.0, 90.0, 0.90)
    add(3, 4, "D", 300.0, 90.0, 0.90)

    ctx = GraphContext()
    ctx.G = G
    ctx._node_xy = {n: (x, y) for n, (x, y) in coords.items()}
    ctx.loaded = True
    return ctx


class MockScorer:
    """seg_id -> risk. Risky path (A,B) high; safe path (C,D) low."""

    RISK = {"A": 0.9, "B": 0.9, "C": 0.05, "D": 0.05}

    def risk_for_hour(self, hour):
        return dict(self.RISK)


@pytest.fixture
def scorer() -> MockScorer:
    return MockScorer()

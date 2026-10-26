"""
terrain_edges.py — Procedural geographic edge connectivity & trade barriers.

Backward-compatible facade re-exporting from terrain.edges.terrain_edges.
"""

from __future__ import annotations

import terrain.edges.terrain_edges as _impl
from terrain.edges.terrain_edges import (
    EdgeType,
    TerrainEdge,
    TerrainEdgeManager,
    _EDGE_MANAGER,
    get_edge_manager,
    reset_edge_manager,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'EdgeType',
    'TerrainEdge',
    'TerrainEdgeManager',
    '_EDGE_MANAGER',
    'get_edge_manager',
    'reset_edge_manager',
]

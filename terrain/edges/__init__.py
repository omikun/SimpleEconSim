"""
terrain/edges — Terrain Edge Tracing & Cliffs.
"""

from terrain.edges.terrain_edges import (
    EdgeType,
    TerrainEdge,
    TerrainEdgeManager,
    get_edge_manager,
    reset_edge_manager,
)

__all__ = [
    "EdgeType",
    "TerrainEdge",
    "TerrainEdgeManager",
    "get_edge_manager",
    "reset_edge_manager",
]

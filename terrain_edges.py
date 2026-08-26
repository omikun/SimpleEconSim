"""
terrain_edges.py — Procedural Geographic Edge Connectivity & Trade Barriers for REGNUM.

Dictates overland and fluvial trade connectivity between adjacent hex tiles based on
procedural 3D elevation relief, sheer cliffs, alpine ridges, natural passes, and river flows.

Key Rules:
1. Sheer Cliffs: delta elevation |H_a - H_b| >= 0.40 (~1300m vertical cliff) blocks overland trade.
2. Alpine Mountain Ridges: both tiles in high mountains (H > 0.68) are blocked unless identified
   as a natural saddle pass or engineered via a Mountain Pass Road.
3. River Corridors: Downstream fluvial drainage from highlands to oceans provides a 0.4x friction
   multiplier (+50% to +100% trade throughput).
4. Friction Matrix:
   - River downstream: 0.4x
   - Plains / Lowlands: 1.0x (baseline)
   - Forest: 1.3x
   - Hills: 1.8x
   - Mountain Pass: 2.2x
   - Sheer Cliff / Impassable Alpine: Infinity (blocked)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum
from hexmap import axial_neighbors, axial_to_offset


class EdgeType(str, Enum):
    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAIN_PASS = "mountain_pass"
    RIVER_DOWNSTREAM = "river_downstream"
    RIVER_UPSTREAM = "river_upstream"
    CLIFF_BLOCKED = "cliff_blocked"
    ALPINE_BLOCKED = "alpine_blocked"
    WATER_CROSSING = "water_crossing"


@dataclass
class TerrainEdge:
    tile_a: str
    tile_b: str
    passable: bool
    edge_type: EdgeType
    friction: float
    elevation_delta: float
    is_river: bool = False
    has_road: bool = False
    has_bridge: bool = False
    has_mountain_pass: bool = False

    def edge_key(self) -> tuple[str, str]:
        return tuple(sorted((self.tile_a, self.tile_b)))


class TerrainEdgeManager:
    """Manages geographic edge connectivity across the entire world grid."""

    def __init__(self, tiles: list, layout: dict):
        self.tiles_by_name = {t.name: t for t in tiles}
        self.layout = layout
        # (tile_a_name, tile_b_name) -> TerrainEdge
        self.edges: dict[tuple[str, str], TerrainEdge] = {}
        # Built infrastructure: set of edge_keys
        self.mountain_passes: set[tuple[str, str]] = set()
        self.river_bridges: set[tuple[str, str]] = set()
        self.built_roads: set[tuple[str, str]] = set()
        
        self.compute_all_edges()

    def _pair_key(self, name_a: str, name_b: str) -> tuple[str, str]:
        return tuple(sorted((name_a, name_b)))

    def compute_edge(self, tile_a, tile_b) -> TerrainEdge:
        """Compute the baseline geographic passability between two adjacent tiles."""
        key = self._pair_key(tile_a.name, tile_b.name)
        
        # Check if engineered infrastructure already exists
        has_pass = key in self.mountain_passes
        has_bridge = key in self.river_bridges
        has_road = key in self.built_roads

        h_a = getattr(tile_a, 'elevation', 0.0)
        h_b = getattr(tile_b, 'elevation', 0.0)
        dh = abs(h_a - h_b)

        is_ocean_a = h_a < 0.0 or getattr(tile_a, 'is_ocean', False)
        is_ocean_b = h_b < 0.0 or getattr(tile_b, 'is_ocean', False)

        # 1. Land-to-Water or Water-to-Water Crossing
        if is_ocean_a or is_ocean_b:
            if is_ocean_a and is_ocean_b:
                return TerrainEdge(
                    tile_a=tile_a.name, tile_b=tile_b.name,
                    passable=True, edge_type=EdgeType.WATER_CROSSING,
                    friction=0.5, elevation_delta=dh
                )
            else:
                # Coastal Land-Water boundary: passable for coastal fishing/harbors
                return TerrainEdge(
                    tile_a=tile_a.name, tile_b=tile_b.name,
                    passable=True, edge_type=EdgeType.WATER_CROSSING,
                    friction=0.8, elevation_delta=dh
                )

        # 2. Sheer Elevation Cliff (Vertical drop >= 0.40)
        if dh >= 0.40 and not has_pass and not has_road:
            return TerrainEdge(
                tile_a=tile_a.name, tile_b=tile_b.name,
                passable=False, edge_type=EdgeType.CLIFF_BLOCKED,
                friction=float('inf'), elevation_delta=dh,
                has_road=has_road, has_mountain_pass=has_pass
            )

        # 3. Alpine Mountain Ridge (Both peaks high elevation >= 0.68)
        if h_a >= 0.68 and h_b >= 0.68:
            # Check for natural saddle pass (average height dips below 0.74 or moderate dh)
            avg_h = (h_a + h_b) / 2.0
            if (avg_h < 0.74 or dh > 0.08) or has_pass:
                return TerrainEdge(
                    tile_a=tile_a.name, tile_b=tile_b.name,
                    passable=True, edge_type=EdgeType.MOUNTAIN_PASS,
                    friction=1.8 if has_pass else 2.4, elevation_delta=dh,
                    has_mountain_pass=has_pass, has_road=has_road
                )
            else:
                # Solid impassable alpine ridge
                return TerrainEdge(
                    tile_a=tile_a.name, tile_b=tile_b.name,
                    passable=False, edge_type=EdgeType.ALPINE_BLOCKED,
                    friction=float('inf'), elevation_delta=dh,
                    has_mountain_pass=has_pass, has_road=has_road
                )

        # 4. River Drainage Corridors (Downhill gradient flow & river valleys)
        is_river = False
        if dh >= 0.04 and (h_a > 0.06 or h_b > 0.06) and (h_a < 0.78 or h_b < 0.78):
            is_river = True

        if is_river:
            edge_t = EdgeType.RIVER_DOWNSTREAM if h_a > h_b else EdgeType.RIVER_UPSTREAM
            frict = 0.4 if h_a > h_b else 0.85
            return TerrainEdge(
                tile_a=tile_a.name, tile_b=tile_b.name,
                passable=True, edge_type=edge_t,
                friction=frict, elevation_delta=dh,
                is_river=True, has_bridge=has_bridge, has_road=has_road
            )

        # 5. Standard Biome Friction
        max_h = max(h_a, h_b)
        if max_h >= 0.48:
            e_type = EdgeType.HILLS
            frict = 1.6
        elif max_h >= 0.24:
            e_type = EdgeType.FOREST
            frict = 1.3
        else:
            e_type = EdgeType.PLAINS
            frict = 1.0

        if has_road:
            frict = max(0.5, frict * 0.6)

        return TerrainEdge(
            tile_a=tile_a.name, tile_b=tile_b.name,
            passable=True, edge_type=e_type,
            friction=frict, elevation_delta=dh,
            has_road=has_road, has_bridge=has_bridge
        )

    def compute_all_edges(self):
        """Analyze and populate all adjacent hex edges across the layout."""
        self.edges.clear()
        for name, tile in self.tiles_by_name.items():
            if name not in self.layout:
                continue
            q, axr = self.layout[name]
            for nq, nar in axial_neighbors(q, axr):
                nc, nr = axial_to_offset(nq, nar)
                other_name = f"r{nr}c{nc}"
                if other_name in self.tiles_by_name:
                    other_tile = self.tiles_by_name[other_name]
                    key = self._pair_key(name, other_name)
                    if key not in self.edges:
                        edge = self.compute_edge(tile, other_tile)
                        self.edges[key] = edge

    def get_edge(self, name_a: str, name_b: str) -> TerrainEdge | None:
        """Return the TerrainEdge object between two tiles."""
        return self.edges.get(self._pair_key(name_a, name_b))

    def is_passable(self, name_a: str, name_b: str) -> bool:
        """Return True if overland commerce can cross between tile_a and tile_b."""
        edge = self.get_edge(name_a, name_b)
        return edge.passable if edge is not None else True

    def get_friction(self, name_a: str, name_b: str) -> float:
        """Return transport friction multiplier between two adjacent tiles."""
        edge = self.get_edge(name_a, name_b)
        return edge.friction if edge is not None else 1.0

    def unblock_mountain_pass(self, name_a: str, name_b: str) -> bool:
        """Construct a mountain pass road between two mountain tiles."""
        key = self._pair_key(name_a, name_b)
        self.mountain_passes.add(key)
        if name_a in self.tiles_by_name and name_b in self.tiles_by_name:
            self.edges[key] = self.compute_edge(self.tiles_by_name[name_a], self.tiles_by_name[name_b])
            return True
        return False

    def build_river_bridge(self, name_a: str, name_b: str) -> bool:
        """Construct a bridge across a river edge."""
        key = self._pair_key(name_a, name_b)
        self.river_bridges.add(key)
        if name_a in self.tiles_by_name and name_b in self.tiles_by_name:
            self.edges[key] = self.compute_edge(self.tiles_by_name[name_a], self.tiles_by_name[name_b])
            return True
        return False


_EDGE_MANAGER: TerrainEdgeManager | None = None

def get_edge_manager(tiles: list = None, layout: dict = None) -> TerrainEdgeManager:
    """Return singleton TerrainEdgeManager instance."""
    global _EDGE_MANAGER
    if _EDGE_MANAGER is None and tiles is not None and layout is not None:
        _EDGE_MANAGER = TerrainEdgeManager(tiles, layout)
    elif tiles is not None and layout is not None and len(_EDGE_MANAGER.tiles_by_name) != len(tiles):
        _EDGE_MANAGER = TerrainEdgeManager(tiles, layout)
    return _EDGE_MANAGER

def reset_edge_manager(tiles: list, layout: dict) -> TerrainEdgeManager:
    """Force re-initialization of the edge manager with fresh world tiles."""
    global _EDGE_MANAGER
    _EDGE_MANAGER = TerrainEdgeManager(tiles, layout)
    return _EDGE_MANAGER

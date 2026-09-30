"""
terrain — Modular Geography, Cartography, Elevation, Biomes, and Meshes for REGNUM.
"""

from terrain.mesh import Center, Corner, Edge, NoisyEdges
from terrain.biomes import BIOME_COLORS, mapgen2_biome, whittaker_biome
from terrain.generator import PolygonMapGenerator, ParallelPolygonMapGenerator, apply_polygon_map_to_world
from terrain.elevation import (
    HeightMapGenerator,
    apply_heightmap_to_world,
    sample_terrain_to_tiles,
    _TOPOGRAPHIC_SURFACE_CACHE,
    get_cached_topographic_surface,
    _generate_topographic_surface_impl,
)
from terrain.erosion import HydraulicErosionSim, HydraulicErosionResult
from terrain.edges import EdgeType, TerrainEdge, TerrainEdgeManager
from terrain.wilderness import (
    enter_wilderness,
    enter_claimed,
    forage,
    step_wilderness,
)
from terrain.hex import (
    rectangular_hex_layout,
    axial_to_offset,
    offset_to_axial,
    axial_to_pixel,
    pixel_to_axial,
    axial_neighbors,
    hex_distance,
    adjacent,
    hex_corners,
    hex_bbox,
)

__all__ = [
    # Mesh
    'Center',
    'Corner',
    'Edge',
    'NoisyEdges',
    # Biomes
    'BIOME_COLORS',
    'mapgen2_biome',
    'whittaker_biome',
    # Generator
    'PolygonMapGenerator',
    'ParallelPolygonMapGenerator',
    'apply_polygon_map_to_world',
    # Elevation
    'HeightMapGenerator',
    'apply_heightmap_to_world',
    'sample_terrain_to_tiles',
    '_TOPOGRAPHIC_SURFACE_CACHE',
    'get_cached_topographic_surface',
    '_generate_topographic_surface_impl',
    # Erosion
    'HydraulicErosionSim',
    'HydraulicErosionResult',
    # Edges
    'EdgeType',
    'TerrainEdge',
    'TerrainEdgeManager',
    # Wilderness
    'enter_wilderness',
    'enter_claimed',
    'forage',
    'step_wilderness',
    # Hex
    'rectangular_hex_layout',
    'axial_to_offset',
    'offset_to_axial',
    'axial_to_pixel',
    'pixel_to_axial',
    'axial_neighbors',
    'hex_distance',
    'adjacent',
    'hex_corners',
    'hex_bbox',
]

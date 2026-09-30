"""
polygon_map.py — Amit Patel (Red Blob Games) Polygonal Map Generation.

Facade module re-exporting from terrain.mesh, terrain.biomes, and terrain.generator.
"""

from terrain.mesh.graph import Center, Corner, Edge
from terrain.mesh.noisy_edges import NoisyEdges
from terrain.biomes.whittaker import BIOME_COLORS, whittaker_biome, mapgen2_biome
from terrain.generator.polygon import PolygonMapGenerator
from terrain.generator.parallel import ParallelPolygonMapGenerator, apply_polygon_map_to_world

__all__ = [
    'Center',
    'Corner',
    'Edge',
    'NoisyEdges',
    'BIOME_COLORS',
    'whittaker_biome',
    'mapgen2_biome',
    'PolygonMapGenerator',
    'ParallelPolygonMapGenerator',
    'apply_polygon_map_to_world',
]

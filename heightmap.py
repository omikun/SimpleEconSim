"""
heightmap.py — Continuous Landmass, Elevation, and Biomes for REGNUM.

Facade module re-exporting from terrain.elevation.
"""

from terrain.elevation.heightmap import (
    HeightMapGenerator,
    apply_heightmap_to_world,
    sample_terrain_to_tiles,
)
from terrain.elevation.topographic import (
    _TOPOGRAPHIC_SURFACE_CACHE,
    get_cached_topographic_surface,
    _generate_topographic_surface_impl,
)

__all__ = [
    'HeightMapGenerator',
    'apply_heightmap_to_world',
    'sample_terrain_to_tiles',
    '_TOPOGRAPHIC_SURFACE_CACHE',
    'get_cached_topographic_surface',
    '_generate_topographic_surface_impl',
]

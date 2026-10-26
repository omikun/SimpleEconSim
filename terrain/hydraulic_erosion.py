"""
hydraulic_erosion.py — Particle-based hydraulic & thermal erosion simulation for island meshes.

Backward-compatible facade re-exporting from terrain.erosion.hydraulic.
"""

from __future__ import annotations

import terrain.erosion.hydraulic as _impl
from terrain.erosion.hydraulic import (
    HydraulicErosionSim,
    HydraulicErosionResult,
    build_continuous_island_heightmap,
    _droplet_worker_chunk,
    simulate_global_erosion,
    apply_erosion_to_polygon_mesh,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'HydraulicErosionSim',
    'HydraulicErosionResult',
    'build_continuous_island_heightmap',
    '_droplet_worker_chunk',
    'simulate_global_erosion',
    'apply_erosion_to_polygon_mesh',
]

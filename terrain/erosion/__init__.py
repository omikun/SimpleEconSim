"""
terrain/erosion — Hydraulic & Fluvial Erosion Simulation.
"""

from terrain.erosion.hydraulic import (
    HydraulicErosionResult,
    HydraulicErosionSim,
    apply_erosion_to_polygon_mesh,
    simulate_global_erosion,
)

__all__ = [
    "HydraulicErosionSim",
    "HydraulicErosionResult",
    "apply_erosion_to_polygon_mesh",
    "simulate_global_erosion",
]

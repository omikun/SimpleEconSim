"""
render_engine/gpu/fallback_pipeline.py — CPU NumPy fallback pipeline.
"""

from typing import Any, Dict, Optional, Tuple
import pygame
from heightmap import get_cached_topographic_surface
from render_engine.gpu.base import BaseGPUTerrainPipeline


class CPUFallbackPipeline(BaseGPUTerrainPipeline):
    """CPU-based fallback terrain generator utilizing existing NumPy/SciPy algorithms."""

    def __init__(self):
        pass

    def is_available(self) -> bool:
        return True

    def render_topographic_surface(
        self,
        seed: int,
        bbox: Tuple[float, float, float, float],
        tiles: Optional[list] = None,
        layout: Optional[dict] = None,
        width: int = 2400,
        height: int = 1800,
        uniforms: Optional[Dict[str, Any]] = None,
        progress_callback=None,
    ) -> pygame.Surface:
        return get_cached_topographic_surface(
            seed=seed,
            bbox=bbox,
            tiles=tiles,
            layout=layout,
            canvas_w=width,
            canvas_h=height,
            progress_callback=progress_callback,
        )

    def release(self):
        pass

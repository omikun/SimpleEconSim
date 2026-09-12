"""
render_engine/gpu/base.py — Abstract interface for GPU terrain pipelines.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
import pygame


class BaseGPUTerrainPipeline(ABC):
    """Abstract base class for GPU terrain synthesis pipelines."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the GPU context and shaders are available and initialized."""
        pass

    @abstractmethod
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
        """Render the complete 2400x1800 topographic surface into a Pygame surface."""
        pass

    @abstractmethod
    def release(self):
        """Release any GPU buffers, textures, or contexts."""
        pass

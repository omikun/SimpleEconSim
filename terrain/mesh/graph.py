"""
terrain/mesh/graph.py — Dual Graph Data Structures: Center, Corner, Edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np


@dataclass(eq=False)
class Center:
    """Voronoi polygon cell (Delaunay vertex)."""
    index: int
    point: np.ndarray  # (x, y) coordinates

    # Topological connectivity
    neighbors: List[Center] = field(default_factory=list)
    borders: List[Edge] = field(default_factory=list)
    corners: List[Corner] = field(default_factory=list)

    # Physical properties
    water: bool = False
    ocean: bool = False
    coast: bool = False
    border: bool = False
    elevation: float = 0.0
    moisture: float = 0.0
    temperature: float = 0.5
    biome: str = 'OCEAN'
    normal: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0], dtype=np.float64))
    total_light: float = 1.0
    brdf_color: Tuple[int, int, int] = (44, 78, 122)

    # Mapgen2 features: contour zone & watershed drainage basin
    contour: int = 1
    watershed: Optional[Corner] = None
    watershed_size: int = 0
    lowest_corner: Optional[Corner] = None

    @property
    def x(self) -> float:
        return float(self.point[0])

    @property
    def y(self) -> float:
        return float(self.point[1])


@dataclass(eq=False)
class Corner:
    """Voronoi vertex / Delaunay triangle circumcenter."""
    index: int
    point: np.ndarray  # (x, y) coordinates

    # Topological connectivity
    touches: List[Center] = field(default_factory=list)
    protrudes: List[Edge] = field(default_factory=list)
    adjacent: List[Corner] = field(default_factory=list)

    # Physical properties
    water: bool = False
    ocean: bool = False
    coast: bool = False
    border: bool = False
    elevation: float = 0.0
    moisture: float = 0.0

    # Hydrology & Watersheds
    river: int = 0  # River flow volume / flux
    downslope: Optional[Corner] = None  # Pointer to steepest downhill neighbor
    watershed: Optional[Corner] = None
    watershed_size: int = 0
    contour: int = 1

    @property
    def x(self) -> float:
        return float(self.point[0])

    @property
    def y(self) -> float:
        return float(self.point[1])


@dataclass(eq=False)
class Edge:
    """Connection between Delaunay centers and Voronoi corners."""
    index: int
    d0: Optional[Center] = None  # Delaunay edge start center
    d1: Optional[Center] = None  # Delaunay edge end center
    v0: Optional[Corner] = None  # Voronoi edge start corner
    v1: Optional[Corner] = None  # Voronoi edge end corner
    midpoint: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float64))
    river: int = 0  # River volume flowing along edge
    road: int = 0   # Contour road level (0 = none, 1, 2, 3...)
    lava: bool = False  # Volcanic lava fissure along this edge

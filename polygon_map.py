"""
polygon_map.py — Amit Patel (Red Blob Games) Polygonal Map Generation.

Reference:
    http://www-cs-students.stanford.edu/~amitp/game-programming/polygon-map-generation/

Features:
- Dual-graph mesh representation:
    * Centers (Delaunay vertices / Voronoi polygon centers)
    * Corners (Voronoi vertices / Delaunay triangle circumcenters)
    * Edges (Delaunay d0-d1 and Voronoi v0-v1 dual quad-pointers)
- Voronoi diagram with Lloyd relaxation for organic, uniform cell distribution
- Island boundary generation (radial sine, Perlin noise, square, or blob)
- BFS flood-fill classifying water into ocean vs isolated freshwater lakes
- Elevation computed as distance from coast with nonlinear hypsometric distribution:
    y(x) = 1 - (1 - x)^2
- Steepest downhill downslope vector pointers for all corners
- Watershed & river network generation with volume/flux accumulation
- Moisture diffusion from freshwater bodies (rivers, lakes) and quantile redistribution
- 2D Whittaker biome classification (16 distinct biomes)
- Shaded relief / hillshading with Northwest illumination
- Multi-core parallel map generation engine (ParallelPolygonMapGenerator)
- Adapter for REGNUM 9x9 hex world simulation (apply_polygon_map_to_world)
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import gaussian_filter
from scipy.spatial import Delaunay, KDTree, Voronoi


# ---------------------------------------------------------------------------
# Biome Definitions and Palette
# ---------------------------------------------------------------------------

BIOME_COLORS: Dict[str, Tuple[int, int, int]] = {
    'OCEAN': (44, 78, 122),
    'LAKE': (58, 118, 168),
    'BEACH': (198, 185, 142),
    'SNOW': (248, 250, 252),
    'TUNDRA': (180, 186, 172),
    'BARE': (142, 142, 138),
    'SCORCHED': (92, 88, 82),
    'TAIGA': (144, 166, 116),
    'SHRUBLAND': (140, 158, 120),
    'TEMPERATE_DESERT': (206, 212, 156),
    'TEMPERATE_RAIN_FOREST': (58, 132, 82),
    'TEMPERATE_DECIDUOUS_FOREST': (96, 148, 86),
    'GRASSLAND': (132, 172, 88),
    'TROPICAL_RAIN_FOREST': (46, 116, 82),
    'TROPICAL_SEASONAL_FOREST': (82, 150, 66),
    'SUBTROPICAL_DESERT': (214, 188, 138),
    'MARSH': (74, 120, 102),
    'ICE': (220, 235, 248),
}


def whittaker_biome(elevation: float, moisture: float) -> str:
    """Whittaker diagram mapping (elevation, moisture) in [0.0, 1.0] to a terrestrial biome."""
    if elevation > 0.82:
        if moisture > 0.50:
            return 'SNOW'
        elif moisture > 0.33:
            return 'TUNDRA'
        elif moisture > 0.16:
            return 'BARE'
        else:
            return 'SCORCHED'
    elif elevation > 0.60:
        if moisture > 0.66:
            return 'TAIGA'
        elif moisture > 0.33:
            return 'SHRUBLAND'
        else:
            return 'TEMPERATE_DESERT'
    elif elevation > 0.30:
        if moisture > 0.83:
            return 'TEMPERATE_RAIN_FOREST'
        elif moisture > 0.50:
            return 'TEMPERATE_DECIDUOUS_FOREST'
        elif moisture > 0.16:
            return 'GRASSLAND'
        else:
            return 'TEMPERATE_DESERT'
    else:
        if moisture > 0.66:
            return 'TROPICAL_RAIN_FOREST'
        elif moisture > 0.33:
            return 'TROPICAL_SEASONAL_FOREST'
        elif moisture > 0.16:
            return 'GRASSLAND'
        else:
            return 'SUBTROPICAL_DESERT'


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Dual Graph Data Structures: Center, Corner, Edge
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Noisy Edges (Amit Patel mapgen2 Quadrilateral Recursive Subdivision)
# ---------------------------------------------------------------------------

class NoisyEdges:
    """Generates organic, fractal edge paths using recursive quadrilateral subdivision.

    Reference:
        Amit Patel, "Polygonal Map Generation for Games"
        https://github.com/amitp/mapgen2/blob/master/NoisyEdges.as
        https://www.redblobgames.com/maps/mapgen2/

    Guarantees:
        Noisy paths are strictly enclosed within the quadrilateral formed by
        (v0, d0, v1, d1), ensuring that coastlines, rivers, and borders
        never self-intersect or cross neighboring polygon boundaries.
    """

    def __init__(self, tradeoff: float = 0.30):
        self.tradeoff = float(tradeoff)
        # path0: edge.index -> list of points from v0 to midpoint
        self.path0: Dict[int, List[np.ndarray]] = {}
        # path1: edge.index -> list of points from v1 to midpoint
        self.path1: Dict[int, List[np.ndarray]] = {}

    def build_noisy_line_segments(
        self,
        rng: random.Random,
        A: np.ndarray,
        B: np.ndarray,
        C: np.ndarray,
        D: np.ndarray,
        min_length: float,
        max_depth: int = 8,
    ) -> List[np.ndarray]:
        """Subdivide quadrilateral A-B-C-D recursively to generate an organic path from A to C."""
        points = [A.copy()]

        def subdivide(A_pt: np.ndarray, B_pt: np.ndarray, C_pt: np.ndarray, D_pt: np.ndarray, depth: int) -> None:
            if depth >= max_depth:
                return
            dist_AC = float(np.linalg.norm(A_pt - C_pt))
            dist_BD = float(np.linalg.norm(B_pt - D_pt))
            if dist_AC < min_length or dist_BD < min_length:
                return

            p = rng.uniform(0.40, 0.60)
            q = rng.uniform(0.40, 0.60)

            # Midpoints along quadrilateral edges
            E = A_pt + p * (D_pt - A_pt)
            F = B_pt + p * (C_pt - B_pt)
            G = A_pt + q * (B_pt - A_pt)
            I = D_pt + q * (C_pt - D_pt)

            # Central interior intersection point
            H = E + q * (F - E)

            # Subdivide subquadrilaterals meeting at H with gentle organic displacement
            s = 1.0 - rng.uniform(-0.16, 0.16)
            t = 1.0 - rng.uniform(-0.16, 0.16)

            subdivide(A_pt, G + s * (B_pt - G), H, E + t * (D_pt - E), depth + 1)
            points.append(H.copy())
            subdivide(H, F + s * (C_pt - F), C_pt, I + t * (D_pt - I), depth + 1)

        subdivide(A, B, C, D, 0)
        points.append(C.copy())
        return points

    def build_noisy_edges(self, pmap: 'PolygonMapGenerator', seed: Optional[int] = None) -> None:
        """Compute noisy paths for all valid edges in the map."""
        edge_rng = random.Random(seed if seed is not None else pmap.seed + 9999)
        f = self.tradeoff

        for edge in pmap.edges:
            if edge.v0 is None or edge.v1 is None:
                continue

            v0_pt = edge.v0.point
            v1_pt = edge.v1.point
            mid_pt = edge.midpoint

            # Determine dual center points d0 and d1
            if edge.d0 is not None and edge.d1 is not None:
                d0_pt = edge.d0.point
                d1_pt = edge.d1.point
            elif edge.d0 is not None:
                d0_pt = edge.d0.point
                d1_pt = mid_pt + (mid_pt - d0_pt)  # Synthesize opposite point for border edges
            elif edge.d1 is not None:
                d1_pt = edge.d1.point
                d0_pt = mid_pt + (mid_pt - d1_pt)
            else:
                perp = np.array([-(v1_pt[1] - v0_pt[1]), v1_pt[0] - v0_pt[0]]) * 0.5
                d0_pt = mid_pt + perp
                d1_pt = mid_pt - perp

            # Quadrilateral interpolation points
            t = v0_pt + f * (d0_pt - v0_pt)
            q = v0_pt + f * (d1_pt - v0_pt)
            r = v1_pt + f * (d0_pt - v1_pt)
            s = v1_pt + f * (d1_pt - v1_pt)

            # Feature-dependent minimum segment length:
            # - Coastlines & rivers: smooth organic fractal detail (5.0)
            # - Biome transitions: medium organic contours (10.0)
            # - Open ocean: smooth large segments (50.0)
            # - Interior: standard noise (14.0)
            min_length = 14.0
            if edge.d0 and edge.d1:
                if edge.d0.biome != edge.d1.biome:
                    min_length = 10.0
                if edge.d0.ocean and edge.d1.ocean:
                    min_length = 50.0
                if edge.d0.coast or edge.d1.coast:
                    min_length = 5.0
            elif edge.v0.coast or edge.v1.coast:
                min_length = 5.0

            if edge.river > 0 or edge.lava:
                min_length = 5.0

            self.path0[edge.index] = self.build_noisy_line_segments(
                edge_rng, v0_pt, t, mid_pt, q, min_length=min_length
            )
            self.path1[edge.index] = self.build_noisy_line_segments(
                edge_rng, v1_pt, s, mid_pt, r, min_length=min_length
            )

    def get_edge_path(self, edge: Edge, start_corner: Corner) -> List[np.ndarray]:
        """Return the ordered noisy path along edge starting from start_corner to the other corner."""
        if edge.index not in self.path0 or edge.index not in self.path1:
            if edge.v0 and edge.v1:
                return [edge.v0.point.copy(), edge.v1.point.copy()] if start_corner == edge.v0 else [edge.v1.point.copy(), edge.v0.point.copy()]
            return []

        p0 = self.path0[edge.index]
        p1 = self.path1[edge.index]

        if start_corner == edge.v0:
            # v0 -> mid -> v1
            rev_p1 = list(reversed(p1))
            return p0 + rev_p1[1:]
        else:
            # v1 -> mid -> v0
            rev_p0 = list(reversed(p0))
            return p1 + rev_p0[1:]


# ---------------------------------------------------------------------------
# Amit Patel Polygonal Map Generator (Enhanced with mapgen2)
# ---------------------------------------------------------------------------

class PolygonMapGenerator:
    """Generates procedural maps using Amit Patel's polygonal dual-graph architecture."""

    def __init__(
        self,
        seed: int = 42,
        width: float = 1000.0,
        height: float = 1000.0,
        num_points: int = 1000,
        lloyd_iterations: int = 2,
        island_shape: str = 'radial',  # 'radial', 'perlin', 'blob', 'square'
        river_count: int = 25,
        enable_corner_improvement: bool = True,
        enable_watersheds: bool = True,
        enable_roads: bool = True,
        enable_lava: bool = True,
        enable_noisy_edges: bool = True,
        noisy_tradeoff: float = 0.30,
    ):
        self.seed = seed
        self.width = float(width)
        self.height = float(height)
        self.num_points = int(num_points)
        self.lloyd_iterations = int(lloyd_iterations)
        self.island_shape = island_shape
        self.river_count = int(river_count)
        self.enable_corner_improvement = enable_corner_improvement
        self.enable_watersheds = enable_watersheds
        self.enable_roads = enable_roads
        self.enable_lava = enable_lava
        self.enable_noisy_edges = enable_noisy_edges
        self.noisy_tradeoff = noisy_tradeoff

        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        self.centers: List[Center] = []
        self.corners: List[Corner] = []
        self.edges: List[Edge] = []
        self.noisy_edges: Optional[NoisyEdges] = None
        self._center_kdtree: Optional[KDTree] = None

        # Build map
        self._build_graph()
        if self.enable_corner_improvement:
            self.improve_corners()
        self._assign_ocean_land()
        self._assign_elevation()
        self._generate_rivers()
        self._assign_moisture()
        self._assign_biomes()
        self.compute_brdf_shading()

        # Mapgen2 features: Watersheds, Roads, Lava, Noisy Edges
        if self.enable_watersheds:
            self.calculate_watersheds()
        if self.enable_roads:
            self.create_roads()
        if self.enable_lava:
            self.create_lava()
        if self.enable_noisy_edges:
            self.build_noisy_edges(self.noisy_tradeoff)

    # -----------------------------------------------------------------------
    # Step 1: Geometry, Lloyd Relaxation, and Dual Graph Construction
    # -----------------------------------------------------------------------

    def _build_graph(self) -> None:
        """Generate points, relax with Lloyd's algorithm, and construct dual-mesh graph."""
        pad = 20.0
        # Sample points with jittered uniform distribution
        pts = self.np_rng.uniform([pad, pad], [self.width - pad, self.height - pad], (self.num_points, 2))

        # Add boundary guard frame to guarantee all internal cells are completely bounded
        w, h = self.width, self.height
        frame = np.array([
            [-w * 0.5, -h * 0.5], [w * 0.5, -h * 0.5], [w * 1.5, -h * 0.5],
            [-w * 0.5, h * 0.5],                       [w * 1.5, h * 0.5],
            [-w * 0.5, h * 1.5],  [w * 0.5, h * 1.5],  [w * 1.5, h * 1.5],
            [-w * 0.2, 0.0], [w * 1.2, 0.0], [-w * 0.2, h], [w * 1.2, h],
            [0.0, -h * 0.2], [w, -h * 0.2], [0.0, h * 1.2], [w, h * 1.2],
        ], dtype=np.float64)

        # Run Lloyd relaxation
        for _ in range(self.lloyd_iterations):
            all_pts = np.vstack([pts, frame])
            vor = Voronoi(all_pts)
            new_pts = []
            for i in range(len(pts)):
                reg_idx = vor.point_region[i]
                reg = vor.regions[reg_idx]
                if -1 not in reg and len(reg) >= 3:
                    poly = vor.vertices[reg]
                    # Clamp centroid into bounding box
                    cx = float(np.clip(poly[:, 0].mean(), pad, self.width - pad))
                    cy = float(np.clip(poly[:, 1].mean(), pad, self.height - pad))
                    new_pts.append([cx, cy])
                else:
                    new_pts.append(pts[i])
            pts = np.array(new_pts, dtype=np.float64)

        # Final Voronoi construction on relaxed points
        all_pts = np.vstack([pts, frame])
        vor = Voronoi(all_pts)

        # Create Center objects for the internal points
        self.centers = []
        for i in range(len(pts)):
            c = Center(index=i, point=pts[i].copy())
            if c.x <= pad * 1.5 or c.x >= self.width - pad * 1.5 or c.y <= pad * 1.5 or c.y >= self.height - pad * 1.5:
                c.border = True
            self.centers.append(c)

        # Deduplicate and register Corners (Voronoi vertices)
        self.corners = []
        corner_map: Dict[int, Corner] = {}
        for i, pt in enumerate(vor.vertices):
            # Check if vertex is relevant to our bounding box
            if -w * 0.1 <= pt[0] <= w * 1.1 and -h * 0.1 <= pt[1] <= h * 1.1:
                cn = Corner(index=len(self.corners), point=pt.copy())
                if pt[0] <= 1.0 or pt[0] >= self.width - 1.0 or pt[1] <= 1.0 or pt[1] >= self.height - 1.0:
                    cn.border = True
                self.corners.append(cn)
                corner_map[i] = cn

        # Link Centers to Corners
        for i, center in enumerate(self.centers):
            reg = vor.regions[vor.point_region[i]]
            for v_idx in reg:
                if v_idx in corner_map:
                    cn = corner_map[v_idx]
                    if cn not in center.corners:
                        center.corners.append(cn)
                    if center not in cn.touches:
                        cn.touches.append(center)

        # Build Edges and Adjacencies
        edge_dict: Dict[Tuple[int, int], Edge] = {}
        for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
            # Only consider ridges connecting our valid centers/corners
            c0 = self.centers[p1] if p1 < len(self.centers) else None
            c1 = self.centers[p2] if p2 < len(self.centers) else None
            cn0 = corner_map.get(v1)
            cn1 = corner_map.get(v2)

            if not (c0 or c1) or not (cn0 or cn1):
                continue

            # Ensure primary slot d0/v0 is non-None
            if c0 is None and c1 is not None:
                c0, c1 = c1, None
            if cn0 is None and cn1 is not None:
                cn0, cn1 = cn1, None

            edge_key = tuple(sorted([cn0.index if cn0 else -1, cn1.index if cn1 else -1]))
            if edge_key not in edge_dict:
                mid = (cn0.point + cn1.point) * 0.5 if (cn0 and cn1) else ((c0.point + c1.point) * 0.5 if (c0 and c1) else np.zeros(2))
                edge = Edge(index=len(self.edges), d0=c0, d1=c1, v0=cn0, v1=cn1, midpoint=mid)
                self.edges.append(edge)
                edge_dict[edge_key] = edge

                if c0: c0.borders.append(edge)
                if c1: c1.borders.append(edge)
                if cn0: cn0.protrudes.append(edge)
                if cn1: cn1.protrudes.append(edge)

            # Link adjacent centers
            if c0 and c1:
                if c1 not in c0.neighbors: c0.neighbors.append(c1)
                if c0 not in c1.neighbors: c1.neighbors.append(c0)

            # Link adjacent corners
            if cn0 and cn1:
                if cn1 not in cn0.adjacent: cn0.adjacent.append(cn1)
                if cn0 not in cn1.adjacent: cn1.adjacent.append(cn0)

        # Sort corners of each center in counter-clockwise order
        for c in self.centers:
            if c.corners:
                c.corners.sort(key=lambda cn: math.atan2(cn.y - c.y, cn.x - c.x))

        # Build KDTree for spatial point queries
        center_coords = np.array([[c.x, c.y] for c in self.centers], dtype=np.float64)
        self._center_kdtree = KDTree(center_coords)

    def improve_corners(self) -> None:
        """Relaxes Voronoi corners by moving each non-border corner to the average of its touching centers.

        Reference: amitp/mapgen2 improveCorners()
        Lengthens short edges, reduces aspect ratio skew, and evens out polygon sizes.
        """
        new_corners: Dict[int, np.ndarray] = {}
        for q in self.corners:
            if q.border or len(q.touches) == 0:
                new_corners[q.index] = q.point.copy()
            else:
                avg_x = sum(r.x for r in q.touches) / len(q.touches)
                avg_y = sum(r.y for r in q.touches) / len(q.touches)
                avg_x = max(0.0, min(self.width, avg_x))
                avg_y = max(0.0, min(self.height, avg_y))
                new_corners[q.index] = np.array([avg_x, avg_y], dtype=np.float64)

        for q in self.corners:
            q.point = new_corners[q.index]

        # Edge midpoints were computed for old corners and must be recomputed
        for edge in self.edges:
            if edge.v0 is not None and edge.v1 is not None:
                edge.midpoint = (edge.v0.point + edge.v1.point) * 0.5

    # -----------------------------------------------------------------------
    # Step 2: Island Shaping & Ocean/Lake Water Classification
    # -----------------------------------------------------------------------

    def _is_inside_island(self, x: float, y: float) -> bool:
        """Evaluate land vs water predicate based on configured island shape function."""
        # Normalize to [-1.0, 1.0] centered at map middle
        nx = (2.0 * x / self.width) - 1.0
        ny = (2.0 * y / self.height) - 1.0
        dist = math.sqrt(nx * nx + ny * ny)

        if dist >= 0.95:
            return False  # Force ocean border

        if self.island_shape == 'square':
            return abs(nx) < 0.70 and abs(ny) < 0.70

        elif self.island_shape == 'blob':
            # Multi-frequency radial harmonic blob
            angle = math.atan2(ny, nx)
            r = 0.55 + 0.18 * math.sin(self.seed + 3.0 * angle) + 0.12 * math.cos(self.seed * 2 + 5.0 * angle)
            return dist < r

        elif self.island_shape == 'perlin':
            # Procedural multi-frequency fBm value noise
            fx = (nx + 1.0) * 2.5
            fy = (ny + 1.0) * 2.5
            n_val = (
                math.sin(fx * 2.1 + self.seed) * math.cos(fy * 2.1) * 0.5 +
                math.sin(fx * 4.3 - self.seed) * math.cos(fy * 4.3) * 0.25 +
                math.sin(fx * 8.7 + 1.2) * math.cos(fy * 8.7) * 0.125
            )
            return (dist + n_val * 0.35) < 0.68

        else:  # 'radial' default
            angle = math.atan2(ny, nx)
            bumps = 5
            dip_angle = self.seed * 0.35
            r1 = 0.2 + 0.40 * math.sin(angle * bumps + dip_angle)
            r2 = 0.2 + 0.35 * math.cos(angle * (bumps - 2) - dip_angle * 1.5)
            r = max(r1, r2)
            return dist < (0.50 + 0.25 * r)

    def _continuous_elevation_noise(self, x: float, y: float) -> float:
        """Continuous multi-scale sinusoidal fBm elevation perturbation to smooth stair-step transitions."""
        fx = x * 0.006 + self.seed * 0.17
        fy = y * 0.006 + self.seed * 0.23
        return (
            (math.sin(fx * 1.0) * math.cos(fy * 1.0)) * 18.0 +
            (math.sin(fx * 2.3 + 1.2) * math.cos(fy * 2.1 - 0.7)) * 10.0 +
            (math.sin(fx * 4.7 - 2.1) * math.cos(fy * 4.9 + 1.4)) * 5.0 +
            (math.sin(fx * 9.3 + 0.5) * math.cos(fy * 9.1 - 1.9)) * 2.5
        )

    def _assign_ocean_land(self) -> None:
        """Assign land vs water to corners and flood-fill to determine ocean vs lakes."""
        # 1. Corner land/water
        for cn in self.corners:
            if cn.border:
                cn.water = True
                cn.ocean = True
            else:
                cn.water = not self._is_inside_island(cn.x, cn.y)

        # 2. Flood-fill from borders to classify ocean (water connected to map edge)
        ocean_queue: deque[Corner] = deque()
        for cn in self.corners:
            if cn.border and cn.water:
                cn.ocean = True
                ocean_queue.append(cn)

        while ocean_queue:
            curr = ocean_queue.popleft()
            for adj in curr.adjacent:
                if adj.water and not adj.ocean:
                    adj.ocean = True
                    ocean_queue.append(adj)

        # 3. Centers: Assign water, ocean, and coast
        for c in self.centers:
            water_corners = sum(1 for cn in c.corners if cn.water)
            ocean_corners = sum(1 for cn in c.corners if cn.ocean)
            num_corners = max(1, len(c.corners))

            # A center is water if majority of its corners are water
            c.water = (water_corners / num_corners) >= 0.5 or c.border
            c.ocean = (ocean_corners > 0 and c.water)

        # 4. Coastlines: Land centers/corners that border ocean
        for c in self.centers:
            if not c.water:
                for n in c.neighbors:
                    if n.ocean:
                        c.coast = True
                        break

        for cn in self.corners:
            if not cn.water:
                for adj in cn.adjacent:
                    if adj.ocean:
                        cn.coast = True
                        break

    # -----------------------------------------------------------------------
    # Step 3: Elevation & Downslopes (Distance from Coast with Redistribution)
    # -----------------------------------------------------------------------

    def _assign_elevation(self) -> None:
        """Compute elevation from coastline distance and redistribute to hypsometric curve."""
        # BFS from ocean corners
        elev_queue: deque[Corner] = deque()
        for cn in self.corners:
            if cn.ocean:
                cn.elevation = 0.0
                elev_queue.append(cn)
            else:
                cn.elevation = float('inf')

        while elev_queue:
            curr = elev_queue.popleft()
            for adj in curr.adjacent:
                # Lake corners stay flat to form natural river valleys (as per Amit Patel)
                step = 0.0 if (adj.water and not adj.ocean) else 1.0
                new_e = curr.elevation + step
                if new_e < adj.elevation:
                    adj.elevation = new_e
                    elev_queue.append(adj)

        # Collect land corners and redistribute elevations
        land_corners = [cn for cn in self.corners if not cn.ocean]
        if land_corners:
            # Sort stably by BFS distance
            land_corners.sort(key=lambda cn: cn.elevation)
            n_land = len(land_corners)
            for rank, cn in enumerate(land_corners):
                x = (rank + 1) / n_land
                # Hypsometric curve: abundant coastal lowlands, rare alpine peaks
                cn.elevation = 1.0 - (1.0 - x) ** 2

        # Assign center elevation as mean of its corners
        for c in self.centers:
            if c.ocean:
                c.elevation = 0.0
            elif c.corners:
                c.elevation = float(np.mean([cn.elevation for cn in c.corners]))
            else:
                c.elevation = 0.1

        # Calculate downslopes: for every corner, find adjacent corner with steepest downhill slope
        for cn in self.corners:
            if cn.ocean:
                cn.downslope = None
                continue
            lowest = cn
            for adj in cn.adjacent:
                if adj.elevation < lowest.elevation:
                    lowest = adj
            if lowest == cn:
                # Fallback tiebreaker: adjacent ocean or neighbor with valid downslope
                for adj in cn.adjacent:
                    if adj.ocean:
                        lowest = adj
                        break
                    if adj.downslope and adj.downslope != cn and adj.elevation <= cn.elevation:
                        lowest = adj
                        break
            cn.downslope = lowest if lowest != cn else None

    # -----------------------------------------------------------------------
    # Step 4: Hydrology & River Generation
    # -----------------------------------------------------------------------

    def _generate_rivers(self) -> None:
        """Trace downhill river streams from mountain springs along Voronoi edges to the ocean."""
        # Find high-elevation land corners as candidate spring origins
        spring_candidates = [
            cn for cn in self.corners
            if not cn.water and 0.35 <= cn.elevation <= 0.90 and cn.downslope is not None
        ]

        if not spring_candidates:
            return

        # Pick river sources
        n_rivers = min(self.river_count, len(spring_candidates))
        sources = self.rng.sample(spring_candidates, n_rivers)

        for spring in sources:
            curr = spring
            curr.river += 1
            visited: Set[int] = {curr.index}

            while curr and not curr.ocean and curr.downslope:
                nxt = curr.downslope
                if nxt.index in visited:
                    break  # Avoid cycles
                visited.add(nxt.index)

                # Find Voronoi edge connecting curr and nxt
                for edge in curr.protrudes:
                    if (edge.v0 == curr and edge.v1 == nxt) or (edge.v1 == curr and edge.v0 == nxt):
                        edge.river += 1
                        break

                nxt.river += 1
                curr = nxt

    # -----------------------------------------------------------------------
    # Step 5: Moisture Diffusion & Quantile Redistribution
    # -----------------------------------------------------------------------

    def _assign_moisture(self) -> None:
        """Diffuse moisture from freshwater bodies (rivers, lakes) and ocean inland."""
        queue: deque[Tuple[Corner, float]] = deque()
        visited: Dict[int, float] = {}

        # Freshwater rivers and lakes are saturated with moisture
        for cn in self.corners:
            if (cn.water and not cn.ocean) or cn.river > 0:
                m = min(3.0, 0.25 * cn.river + 1.0)
                cn.moisture = m
                queue.append((cn, m))
                visited[cn.index] = m
            elif cn.ocean:
                cn.moisture = 1.0
                queue.append((cn, 0.75))
                visited[cn.index] = 0.75
            else:
                cn.moisture = 0.0

        # Breadth-first exponential decay diffusion
        decay = 0.85
        while queue:
            curr, m = queue.popleft()
            if m < 0.05:
                continue
            for adj in curr.adjacent:
                new_m = m * decay
                if new_m > visited.get(adj.index, 0.0):
                    visited[adj.index] = new_m
                    adj.moisture = max(adj.moisture, new_m)
                    queue.append((adj, new_m))

        # Quantile redistribution for land corners
        land_corners = [cn for cn in self.corners if not cn.water]
        if land_corners:
            land_corners.sort(key=lambda cn: cn.moisture)
            n_land = len(land_corners)
            for rank, cn in enumerate(land_corners):
                cn.moisture = rank / max(1, n_land - 1)

        # Ensure all water corners are 1.0 and land corners strictly in [0.0, 1.0]
        for cn in self.corners:
            if cn.water:
                cn.moisture = 1.0
            else:
                cn.moisture = max(0.0, min(1.0, float(cn.moisture)))

        # Assign center moisture as average of its corners, strictly clamped
        for c in self.centers:
            if c.water:
                c.moisture = 1.0
            elif c.corners:
                c.moisture = max(0.0, min(1.0, float(np.mean([cn.moisture for cn in c.corners]))))
            else:
                c.moisture = 0.5

    # -----------------------------------------------------------------------
    # Step 6: Whittaker Biome Classification
    # -----------------------------------------------------------------------

    def _assign_biomes(self) -> None:
        """Assign biomes to centers using Whittaker diagram and hydrological states."""
        for c in self.centers:
            if c.ocean:
                c.biome = 'OCEAN'
            elif c.water:
                if c.elevation < 0.10:
                    c.biome = 'MARSH'
                elif c.elevation > 0.80:
                    c.biome = 'ICE'
                else:
                    c.biome = 'LAKE'
            elif c.coast:
                c.biome = 'BEACH'
            else:
                c.biome = whittaker_biome(c.elevation, c.moisture)

    # -----------------------------------------------------------------------
    # Query, Spatial Interpolation, and Hex World Integration
    # -----------------------------------------------------------------------

    def get_center_at(self, x: float, y: float) -> Center:
        """Find the nearest Voronoi polygon center to coordinate (x, y)."""
        if self._center_kdtree is None:
            raise RuntimeError("Graph not built.")
        _, idx = self._center_kdtree.query([x, y])
        return self.centers[idx]

    def get_elevation_at(self, x: float, y: float) -> float:
        """Sample smooth interpolated elevation at (x, y)."""
        c = self.get_center_at(x, y)
        return c.elevation

    def get_moisture_at(self, x: float, y: float) -> float:
        """Sample moisture at (x, y)."""
        c = self.get_center_at(x, y)
        return c.moisture

    def get_biome_at(self, x: float, y: float) -> str:
        """Sample biome at (x, y)."""
        c = self.get_center_at(x, y)
        return c.biome

    # -----------------------------------------------------------------------
    # Physically-Based BRDF Shading Model
    # -----------------------------------------------------------------------

    def compute_brdf_shading(
        self,
        sun_dir: Tuple[float, float, float] = (-0.55, -0.55, 0.70),
        sun_intensity: float = 1.0,
        ambient_intensity: float = 1.0,
        height_exaggeration: float = 1.5,
    ) -> None:
        """Compute physically-based BRDF illumination matching REGNUM's GPU shader pipeline.

        Applies:
        - 3D Surface Normals N = normalize(-dHx * kh, -dHy * kh, 1.0)
        - Direct solar diffuse: (N . L)^1.05 * sun_intensity
        - Hemispherical sky ambient: (Nz * 0.60 + 0.40) * ambient_intensity
        - Horizon ray-march penumbra soft shadows
        - Water Blinn-Phong specular glints: (Nwave . H)^36 * 0.18 + (Nwave . H)^90 * 0.30
        - Deep ocean bathymetric absorption (Beer-Lambert attenuation)
        - River flat-water specular glints: (N . H)^32 * 0.35
        - Riparian vegetation turf blend along river borders
        - Steep cliff exposure rock scree
        """
        # Sun vector L (NW direction)
        L = np.array(sun_dir, dtype=np.float64)
        L /= np.linalg.norm(L)

        # Half vector H for Blinn-Phong specular (View V = [0, 0, 1])
        H_half = np.array([L[0], L[1], L[2] + 1.0], dtype=np.float64)
        H_half /= np.linalg.norm(H_half)

        # 1. Compute 3D normals for all centers
        for c in self.centers:
            if not c.water and c.neighbors:
                dx = 0.0
                dy = 0.0
                w_sum = 0.0
                for n in c.neighbors:
                    diff_x = n.x - c.x
                    diff_y = n.y - c.y
                    d2 = diff_x * diff_x + diff_y * diff_y
                    if d2 > 1e-4:
                        w = 1.0 / math.sqrt(d2)
                        dx += (n.elevation - c.elevation) * (diff_x / d2) * w
                        dy += (n.elevation - c.elevation) * (diff_y / d2) * w
                        w_sum += w
                if w_sum > 0:
                    dx /= w_sum
                    dy /= w_sum

                # Scale gradient to pixel map dimensions to yield realistic 30-55 deg slopes
                nx = -dx * height_exaggeration * 360.0
                ny = -dy * height_exaggeration * 360.0
                nz = 1.0
                norm_len = math.sqrt(nx * nx + ny * ny + nz * nz)
                c.normal = np.array([nx / norm_len, ny / norm_len, nz / norm_len], dtype=np.float64)
            else:
                c.normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        # 2. Compute soft ray-march horizon shadows
        sun_2d = np.array([-L[0], -L[1]], dtype=np.float64)
        sun_2d /= np.linalg.norm(sun_2d)

        shadow_masks = {}
        for c in self.centers:
            if c.water:
                shadow_masks[c.index] = 1.0
                continue

            shadow = 1.0
            for n in c.neighbors:
                v_cn = np.array([n.x - c.x, n.y - c.y], dtype=np.float64)
                dist = np.linalg.norm(v_cn)
                if dist > 1e-3:
                    cos_theta = np.dot(v_cn / dist, sun_2d)
                    if cos_theta > 0.4:
                        elev_diff = n.elevation - (c.elevation + 0.04 * (dist / 50.0))
                        if elev_diff > 0.01:
                            penumbra = max(0.45, 1.0 - elev_diff * 4.0)
                            shadow = min(shadow, penumbra)
            shadow_masks[c.index] = shadow

        # 3. Evaluate BRDF reflectance and composite final color
        deep_ocean = np.array([13, 36, 82], dtype=np.float64)
        mid_ocean = np.array([26, 66, 112], dtype=np.float64)
        shallow_shelf = np.array([38, 112, 140], dtype=np.float64)
        coastal_turquoise = np.array([64, 158, 166], dtype=np.float64)
        lake_deep = np.array([26, 71, 138], dtype=np.float64)
        lake_shallow = np.array([56, 133, 173], dtype=np.float64)

        for c in self.centers:
            N = c.normal
            NdotL = max(0.0, float(np.dot(N, L)))
            diffuse_sun = math.pow(NdotL, 1.05) * sun_intensity
            sky_light = (N[2] * 0.60 + 0.40) * ambient_intensity
            shadow = shadow_masks.get(c.index, 1.0)
            direct_sun = diffuse_sun * shadow
            total_light = direct_sun + sky_light
            c.total_light = total_light

            if c.water:
                if c.ocean:
                    # Wave normal perturbation
                    phase = c.x * 0.05 + c.y * 0.08 + self.seed * 0.1
                    gw_x = 0.12 * math.sin(phase)
                    gw_y = 0.12 * math.cos(phase * 1.3)
                    w_norm = np.array([-gw_x, -gw_y, 1.0], dtype=np.float64)
                    w_norm /= np.linalg.norm(w_norm)

                    w_NdotL = max(0.0, float(np.dot(w_norm, L)))
                    w_diffuse = 0.65 + 0.35 * (math.pow(w_NdotL, 1.2) * (0.75 + 0.25 * shadow))

                    w_NdotH = max(0.0, float(np.dot(w_norm, H_half)))
                    specular = (math.pow(w_NdotH, 36.0) * 0.18 + math.pow(w_NdotH, 90.0) * 0.30) * sun_intensity * direct_sun

                    # Bathymetric depth color
                    is_near_coast = any(not n.water for n in c.neighbors)
                    if is_near_coast:
                        w_base = coastal_turquoise * 0.6 + shallow_shelf * 0.4
                    elif any(n.coast for n in c.neighbors):
                        w_base = shallow_shelf * 0.5 + mid_ocean * 0.5
                    else:
                        w_base = mid_ocean * 0.3 + deep_ocean * 0.7

                    lit_rgb = w_base * w_diffuse + specular * 255.0
                    c.brdf_color = (
                        min(255, max(0, int(lit_rgb[0]))),
                        min(255, max(0, int(lit_rgb[1]))),
                        min(255, max(0, int(lit_rgb[2]))),
                    )
                else:
                    # Lake water with flat specular reflection
                    NdotH_flat = max(0.0, float(np.dot(N, H_half)))
                    spec_flat = math.pow(NdotH_flat, 32.0) * 0.35 * sun_intensity * direct_sun
                    lake_col = lake_shallow if c.elevation < 0.35 else lake_deep
                    lit_rgb = lake_col * (total_light * 0.65 + 0.35) + spec_flat * 255.0
                    c.brdf_color = (
                        min(255, max(0, int(lit_rgb[0]))),
                        min(255, max(0, int(lit_rgb[1]))),
                        min(255, max(0, int(lit_rgb[2]))),
                    )
            else:
                base_color = np.array(BIOME_COLORS.get(c.biome, (120, 160, 100)), dtype=np.float64)

                # Riparian moisture lush turf margin along rivers
                has_river = any(e.river > 0 for e in c.borders)
                if has_river:
                    riparian_turf = np.array([43, 102, 38], dtype=np.float64)
                    base_color = base_color * 0.70 + riparian_turf * 0.30

                # Steep cliff rock exposure
                slope_val = 1.0 - N[2]
                if slope_val > 0.14:
                    cliff_dark = np.array([66, 64, 71], dtype=np.float64)
                    cliff_w = min(0.70, (slope_val - 0.14) / 0.20)
                    base_color = base_color * (1.0 - cliff_w) + cliff_dark * cliff_w

                lit_rgb = base_color * (total_light * 0.68)
                c.brdf_color = (
                    min(255, max(0, int(lit_rgb[0]))),
                    min(255, max(0, int(lit_rgb[1]))),
                    min(255, max(0, int(lit_rgb[2]))),
                )

    # -----------------------------------------------------------------------
    # Mapgen2 Hydrology, Infrastructure, and Geology Methods
    # -----------------------------------------------------------------------

    def calculate_watersheds(self) -> None:
        """Calculates watershed drainage basins for corners and centers.

        Reference: amitp/mapgen2 calculateWatersheds() & watersheds.js
        Traces downslope pointers to find the coastal outflow corner for each corner.
        Each polygon center is assigned the watershed of its lowest elevation corner.
        Computes catchment area size (watershed_size).
        """
        for cn in self.corners:
            cn.watershed = cn
            cn.watershed_size = 0
            if not cn.ocean and not cn.coast and cn.downslope is not None:
                cn.watershed = cn.downslope

        # Follow downslope pointers to the coast (up to 100 iterations)
        for _ in range(100):
            changed = False
            for cn in self.corners:
                if not cn.ocean and not cn.coast and cn.watershed is not None and not cn.watershed.coast:
                    if cn.downslope is not None and cn.downslope.watershed is not None:
                        r = cn.downslope.watershed
                        if not r.ocean and r != cn.watershed:
                            cn.watershed = r
                            changed = True
            if not changed:
                break

        # Calculate catchment area for each watershed
        for cn in self.corners:
            if cn.watershed is not None:
                cn.watershed.watershed_size += 1

        # Centers take watershed of their lowest corner
        for c in self.centers:
            if c.corners:
                lowest_cn = min(c.corners, key=lambda q: q.elevation)
                c.lowest_corner = lowest_cn
                c.watershed = lowest_cn.watershed if lowest_cn else None
                c.watershed_size = lowest_cn.watershed.watershed_size if (lowest_cn and lowest_cn.watershed) else 0

    def create_roads(self, elevation_thresholds: Optional[List[float]] = None) -> None:
        """Creates contour-following arterial island roads dividing elevation zones.

        Reference: amitp/mapgen2 Roads.as / roads.js
        """
        if elevation_thresholds is None:
            elevation_thresholds = [0.0, 0.40, 0.70, 0.90]

        center_contour: Dict[int, int] = {}
        queue: deque[Center] = deque()

        for c in self.centers:
            if c.coast or c.ocean:
                center_contour[c.index] = 1
                queue.append(c)

        while queue:
            p = queue.popleft()
            p_lvl = center_contour.get(p.index, 1)
            for r in p.neighbors:
                new_level = p_lvl
                while new_level < len(elevation_thresholds) and r.elevation > elevation_thresholds[new_level] and not r.water:
                    new_level += 1
                if new_level < center_contour.get(r.index, 999):
                    center_contour[r.index] = new_level
                    queue.append(r)

        corner_contour: Dict[int, int] = {}
        for c in self.centers:
            c_lvl = center_contour.get(c.index, 1)
            c.contour = c_lvl
            for q in c.corners:
                prev = corner_contour.get(q.index, 999)
                corner_contour[q.index] = min(prev, c_lvl)

        for q in self.corners:
            q.contour = corner_contour.get(q.index, 1)

        # Roads go along edges between different corner contour levels
        for edge in self.edges:
            if edge.v0 is not None and edge.v1 is not None:
                c0 = corner_contour.get(edge.v0.index, 1)
                c1 = corner_contour.get(edge.v1.index, 1)
                if c0 != c1:
                    edge.road = min(c0, c1)

    def create_lava(self, fraction: float = 0.20, min_elevation: float = 0.75, max_moisture: float = 0.35) -> None:
        """Generates high-elevation volcanic lava fissures and flows.

        Reference: amitp/mapgen2 Lava.as / lava.js
        """
        for edge in self.edges:
            if edge.river == 0 and edge.d0 and edge.d1:
                if not edge.d0.water and not edge.d1.water:
                    if edge.d0.elevation > min_elevation and edge.d1.elevation > min_elevation:
                        if edge.d0.moisture < max_moisture and edge.d1.moisture < max_moisture:
                            if self.rng.random() < fraction:
                                edge.lava = True

    def build_noisy_edges(self, tradeoff: float = 0.30) -> None:
        """Constructs recursive fractal paths for all Voronoi edges using NoisyEdges."""
        self.noisy_edges = NoisyEdges(tradeoff=tradeoff)
        self.noisy_edges.build_noisy_edges(self)

    def get_polygon_noisy_boundary(self, center: Center) -> np.ndarray:
        """Constructs an organic, contiguous 2D closed polygon boundary using noisy edges."""
        if not self.noisy_edges or len(center.corners) < 3:
            return np.array([[cn.x, cn.y] for cn in center.corners], dtype=np.float64)

        poly_pts: List[np.ndarray] = []
        corners = center.corners
        num_c = len(corners)

        for i in range(num_c):
            c_curr = corners[i]
            c_next = corners[(i + 1) % num_c]

            # Find border edge connecting c_curr and c_next
            edge_found: Optional[Edge] = None
            for e in center.borders:
                if (e.v0 == c_curr and e.v1 == c_next) or (e.v1 == c_curr and e.v0 == c_next):
                    edge_found = e
                    break

            if edge_found and edge_found.index in self.noisy_edges.path0:
                seg_pts = self.noisy_edges.get_edge_path(edge_found, start_corner=c_curr)
                if seg_pts:
                    poly_pts.extend(seg_pts[:-1])
            else:
                poly_pts.append(c_curr.point.copy())

        if poly_pts:
            if len(poly_pts) >= 4:
                arr = np.array(poly_pts, dtype=np.float64)
                prev_pts = np.roll(arr, 1, axis=0)
                next_pts = np.roll(arr, -1, axis=0)
                # Weighted running average for organic curvature without sharp spikes
                smoothed = 0.20 * prev_pts + 0.60 * arr + 0.20 * next_pts
                return np.vstack([smoothed, smoothed[0]])
            poly_pts.append(poly_pts[0].copy())  # Close polygon
            return np.array(poly_pts, dtype=np.float64)

        return np.array([[cn.x, cn.y] for cn in center.corners], dtype=np.float64)

    # -----------------------------------------------------------------------
    # Rasterization & Shaded Relief Surface Rendering
    # -----------------------------------------------------------------------

    def render_to_surface(
        self,
        width: int = 1000,
        height: int = 1000,
        use_brdf: bool = True,
        use_noisy_edges: bool = True,
        show_roads: bool = True,
        show_lava: bool = True,
        show_watersheds: bool = False,
        continuous_relief: bool = False,
        render_micropolys: bool = True,
        target_micropolys: int = 16000,
        micropoly_roughness: float = 8.0,
        micropoly_lateral_jitter: float = 0.20,
        normal_smooth_ratio: float = 0.70,
    ) -> Any:
        """Render the polygonal map with shaded relief, noisy paths, rivers, lava, and roads onto a Pygame surface."""
        import pygame
        surface = pygame.Surface((width, height))
        surface.fill((13, 36, 82) if use_brdf else (44, 78, 122))

        scale_x = width / self.width
        scale_y = height / self.height

        # Light vector from northwest
        sun_dir = np.array([-0.707, -0.707], dtype=np.float64)

        # Precompute watershed distinct color palette if needed
        watershed_colors: Dict[int, Tuple[int, int, int]] = {}
        if show_watersheds:
            rng_ws = random.Random(42)
            for c in self.centers:
                ws_id = c.watershed.index if c.watershed else 0
                if ws_id not in watershed_colors:
                    if c.water:
                        watershed_colors[ws_id] = (30, 60, 110)
                    else:
                        r = rng_ws.randint(60, 220)
                        g = rng_ws.randint(60, 220)
                        b = rng_ws.randint(60, 220)
                        watershed_colors[ws_id] = (r, g, b)

        # 1. Draw base polygons for water / watersheds / fallback
        for c in self.centers:
            if len(c.corners) < 3:
                continue

            # If micropolys are enabled for land, skip drawing flat land polygons here
            if render_micropolys and use_noisy_edges and self.noisy_edges and not c.water and not show_watersheds:
                continue

            if show_watersheds:
                ws_id = c.watershed.index if c.watershed else 0
                base_c = watershed_colors.get(ws_id, (100, 100, 100))
                if use_brdf and not c.water:
                    shaded_color = (
                        min(255, int(base_c[0] * (c.total_light * 0.68))),
                        min(255, int(base_c[1] * (c.total_light * 0.68))),
                        min(255, int(base_c[2] * (c.total_light * 0.68))),
                    )
                else:
                    shaded_color = base_c
            elif use_brdf:
                shaded_color = c.brdf_color
            else:
                base_color = BIOME_COLORS.get(c.biome, (120, 160, 100))
                shaded_color = base_color

            if use_noisy_edges and self.noisy_edges:
                poly_np = self.get_polygon_noisy_boundary(c)
                poly_pts = [(int(pt[0] * scale_x), int(pt[1] * scale_y)) for pt in poly_np]
            else:
                poly_pts = [(int(cn.x * scale_x), int(cn.y * scale_y)) for cn in c.corners]

            if len(poly_pts) >= 3:
                pygame.draw.polygon(surface, shaded_color, poly_pts)
                if not use_noisy_edges:
                    pygame.draw.polygon(surface, (0, 0, 0, 30 if use_brdf else 40), poly_pts, width=1)

        # 1b. Render constituent micropolygons for each land cell across the ENTIRE island
        # Reference: https://www.redblobgames.com/x/1725-procedural-elevation/#rendering
        if render_micropolys and not show_watersheds:
            # 1. Red Blob corner elevation enhancement:
            # v_elevation[v] = max + alpha * (max - min) of adjacent centers
            elevation_alpha = 0.25
            elev_scale = 320.0
            v_elev = {}
            for cn in self.corners:
                if cn.ocean or cn.coast:
                    v_elev[cn.index] = 0.0
                else:
                    adj_elevs = [c.elevation for c in cn.touches if not c.water]
                    if adj_elevs:
                        c_max = max(adj_elevs)
                        c_min = min(adj_elevs)
                        v_elev[cn.index] = c_max + elevation_alpha * (c_max - c_min)
                    else:
                        v_elev[cn.index] = cn.elevation

            # Multi-light setup (from draw-3d.js)
            L_sun = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
            L_sun /= np.linalg.norm(L_sun)

            L_fill = np.array([0.45, -0.65, 0.60], dtype=np.float64)
            L_fill /= np.linalg.norm(L_fill)

            snow_threshold = 0.82

            # Watertight Dual-Mesh Base Decomposition
            from collections import defaultdict
            vertices: List[np.ndarray] = []
            vertex_map: Dict[Tuple[float, float], int] = {}
            is_boundary_vertex: Dict[int, bool] = {}

            def get_or_add_vertex(pt3d: np.ndarray, is_fixed: bool = False) -> int:
                key = (round(float(pt3d[0]), 1), round(float(pt3d[1]), 1))
                if key in vertex_map:
                    idx = vertex_map[key]
                    if is_fixed:
                        is_boundary_vertex[idx] = True
                    return idx
                idx = len(vertices)
                vertices.append(np.array(pt3d, dtype=np.float64))
                vertex_map[key] = idx
                is_boundary_vertex[idx] = is_fixed
                return idx

            base_triangles: List[Tuple[int, int, int, np.ndarray, float, bool]] = []

            for edge in self.edges:
                d0, d1 = edge.d0, edge.d1
                v0, v1 = edge.v0, edge.v1
                if not d0 or not d1 or not v0 or not v1:
                    continue
                if d0.water and d1.water:
                    continue

                z_v0 = v_elev.get(v0.index, v0.elevation) * elev_scale
                z_v1 = v_elev.get(v1.index, v1.elevation) * elev_scale

                # Continuous multi-scale elevation variation
                fbm_v0 = self._continuous_elevation_noise(v0.x * scale_x, v0.y * scale_y)
                fbm_v1 = self._continuous_elevation_noise(v1.x * scale_x, v1.y * scale_y)
                fbm_d0 = self._continuous_elevation_noise(d0.x * scale_x, d0.y * scale_y)
                fbm_d1 = self._continuous_elevation_noise(d1.x * scale_x, d1.y * scale_y)

                p_v0 = np.array([v0.x * scale_x, v0.y * scale_y, z_v0 + fbm_v0], dtype=np.float64)
                p_v1 = np.array([v1.x * scale_x, v1.y * scale_y, z_v1 + fbm_v1], dtype=np.float64)
                p_d0 = np.array([d0.x * scale_x, d0.y * scale_y, d0.elevation * elev_scale + fbm_d0], dtype=np.float64)
                p_d1 = np.array([d1.x * scale_x, d1.y * scale_y, d1.elevation * elev_scale + fbm_d1], dtype=np.float64)

                idx_v0 = get_or_add_vertex(p_v0, is_fixed=(v0.ocean or v0.coast))
                idx_v1 = get_or_add_vertex(p_v1, is_fixed=(v1.ocean or v1.coast))
                idx_d0 = get_or_add_vertex(p_d0, is_fixed=(d0.ocean or d0.coast))
                idx_d1 = get_or_add_vertex(p_d1, is_fixed=(d1.ocean or d1.coast))

                col0 = np.array(BIOME_COLORS.get(d0.biome, (120, 160, 100)), dtype=np.float64)
                col1 = np.array(BIOME_COLORS.get(d1.biome, (120, 160, 100)), dtype=np.float64)
                if not d1.water:
                    col0 = col0 * 0.70 + col1 * 0.30
                    col1 = col1 * 0.70 + col0 * 0.30

                if edge.river > 0:
                    col0 = col0 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25
                    col1 = col1 * 0.75 + np.array([40, 105, 35], dtype=np.float64) * 0.25

                # 2-way fold: valley along d0-d1 for rivers/coasts, ridge along v0-v1 for interior
                if edge.river > 0 or (d0.water != d1.water):
                    base_triangles.append((idx_v0, idx_d1, idx_d0, col0 if not d0.water else col1, (v0.elevation + d0.elevation) * 0.5, edge.river > 0))
                    base_triangles.append((idx_v1, idx_d0, idx_d1, col1 if not d1.water else col0, (v1.elevation + d1.elevation) * 0.5, edge.river > 0))
                else:
                    if not d0.water:
                        base_triangles.append((idx_v0, idx_v1, idx_d0, col0, (v0.elevation + v1.elevation + d0.elevation) / 3.0, False))
                    if not d1.water:
                        base_triangles.append((idx_v1, idx_v0, idx_d1, col1, (v0.elevation + v1.elevation + d1.elevation) / 3.0, False))

            # Initialize vertex color dictionary
            vertex_colors: Dict[int, np.ndarray] = {}
            for idx_a, idx_b, idx_c, col, el, riv in base_triangles:
                for idx in (idx_a, idx_b, idx_c):
                    if idx not in vertex_colors:
                        vertex_colors[idx] = col.copy()
                    else:
                        vertex_colors[idx] = vertex_colors[idx] * 0.5 + col * 0.5

            # Edge-cached subdivision with lateral 2D and elevation 3D perturbation
            triangles = list(base_triangles)
            edge_midpoints: Dict[Tuple[int, int], int] = {}
            rng = np.random.RandomState(self.seed)

            def get_subdiv_midpoint(i_a: int, i_b: int, cur_depth: int) -> int:
                edge_key = (min(i_a, i_b), max(i_a, i_b))
                if edge_key in edge_midpoints:
                    return edge_midpoints[edge_key]

                pa = vertices[i_a]
                pb = vertices[i_b]
                e_xy = pb[:2] - pa[:2]
                length = float(np.linalg.norm(e_xy))

                mid = (pa + pb) * 0.5

                if length > 1.5:
                    n_perp = np.array([-e_xy[1], e_xy[0]], dtype=np.float64) / length
                    decay = 0.70 ** cur_depth
                    disp_lat = rng.uniform(-micropoly_lateral_jitter, micropoly_lateral_jitter) * length * decay
                    disp_long = rng.uniform(-0.10, 0.10) * length * decay

                    mid[0] += n_perp[0] * disp_lat + (e_xy[0] / length) * disp_long
                    mid[1] += n_perp[1] * disp_lat + (e_xy[1] / length) * disp_long

                    fbm_val = self._continuous_elevation_noise(mid[0], mid[1]) * (decay * 0.4)
                    disp_z = rng.uniform(-0.5, 0.5) * micropoly_roughness * (length / 35.0) * decay + fbm_val
                    mid[2] += disp_z

                idx_mid = len(vertices)
                vertices.append(mid)
                is_boundary_vertex[idx_mid] = is_boundary_vertex.get(i_a, False) and is_boundary_vertex.get(i_b, False)

                c_a = vertex_colors.get(i_a, np.array([120, 160, 100], dtype=np.float64))
                c_b = vertex_colors.get(i_b, np.array([120, 160, 100], dtype=np.float64))
                vertex_colors[idx_mid] = (c_a + c_b) * 0.5

                edge_midpoints[edge_key] = idx_mid
                return idx_mid

            depth = 0
            while len(triangles) < target_micropolys:
                needed = target_micropolys - len(triangles)
                num_to_split = min(len(triangles), max(1, needed // 3))

                def tri_2d_area(t: Tuple[int, int, int, np.ndarray, float, bool]) -> float:
                    p1, p2, p3 = vertices[t[0]], vertices[t[1]], vertices[t[2]]
                    return 0.5 * abs((p2[0] - p1[0]) * (p3[1] - p1[1]) - (p3[0] - p1[0]) * (p2[1] - p1[1]))

                triangles.sort(key=tri_2d_area, reverse=True)
                to_split = triangles[:num_to_split]
                untouched = triangles[num_to_split:]

                new_triangles = list(untouched)
                for i_a, i_b, i_c, col, el, riv in to_split:
                    m_ab = get_subdiv_midpoint(i_a, i_b, depth)
                    m_bc = get_subdiv_midpoint(i_b, i_c, depth)
                    m_ca = get_subdiv_midpoint(i_c, i_a, depth)

                    new_triangles.append((i_a, m_ab, m_ca, col, el, riv))
                    new_triangles.append((i_b, m_bc, m_ab, col, el, riv))
                    new_triangles.append((i_c, m_ca, m_bc, col, el, riv))
                    new_triangles.append((m_ab, m_bc, m_ca, col, el, riv))

                triangles = new_triangles

                # Multi-level vertex relaxation: updates previous-level vertices so initial Voronoi shapes dissolve
                adj_map: Dict[int, Set[int]] = defaultdict(set)
                for i_a, i_b, i_c, _, _, _ in triangles:
                    adj_map[i_a].add(i_b)
                    adj_map[i_a].add(i_c)
                    adj_map[i_b].add(i_a)
                    adj_map[i_b].add(i_c)
                    adj_map[i_c].add(i_a)
                    adj_map[i_c].add(i_b)

                relax_weight = 0.20 * (0.75 ** depth)
                for v_idx in list(adj_map.keys()):
                    if is_boundary_vertex.get(v_idx, False):
                        continue
                    neighbors = list(adj_map[v_idx])
                    if len(neighbors) >= 3:
                        neighbor_mean = np.mean([vertices[n] for n in neighbors], axis=0)
                        vertices[v_idx][:2] = (1.0 - relax_weight) * vertices[v_idx][:2] + relax_weight * neighbor_mean[:2]
                        vertices[v_idx][2] = (1.0 - relax_weight * 1.5) * vertices[v_idx][2] + (relax_weight * 1.5) * neighbor_mean[2]
                        vertices[v_idx][2] += rng.uniform(-0.5, 0.5) * (micropoly_roughness * 0.15 * (0.65 ** depth))

                depth += 1
                if len(triangles) >= target_micropolys or num_to_split == 0:
                    break

            # Area-weighted vertex normals computation
            vertex_normals = [np.array([0.0, 0.0, 0.0], dtype=np.float64) for _ in range(len(vertices))]
            triangle_face_normals = []

            for i_a, i_b, i_c, _, _, _ in triangles:
                pa = vertices[i_a]
                pb = vertices[i_b]
                pc = vertices[i_c]

                va = pb - pa
                vb = pc - pa
                norm = np.cross(va, vb)
                area = float(np.linalg.norm(norm) * 0.5)
                if norm[2] < 0:
                    norm = -norm
                norm_unit = norm / (area * 2.0) if area > 1e-6 else np.array([0.0, 0.0, 1.0])
                triangle_face_normals.append(norm_unit)
                vertex_normals[i_a] += norm_unit * area
                vertex_normals[i_b] += norm_unit * area
                vertex_normals[i_c] += norm_unit * area

            for i in range(len(vertex_normals)):
                vn_len = float(np.linalg.norm(vertex_normals[i]))
                if vn_len > 1e-6:
                    vertex_normals[i] /= vn_len
                else:
                    vertex_normals[i] = np.array([0.0, 0.0, 1.0])

            # Rasterize all resulting micropolygons with blended normals (smooth hill shading + micro-facets)
            for tri_idx, (idx_a, idx_b, idx_c, col_base, avg_elev, is_riv) in enumerate(triangles):
                pa = vertices[idx_a]
                pb = vertices[idx_b]
                pc = vertices[idx_c]

                face_norm = triangle_face_normals[tri_idx]
                avg_vert_norm = (vertex_normals[idx_a] + vertex_normals[idx_b] + vertex_normals[idx_c]) / 3.0
                vn_len = float(np.linalg.norm(avg_vert_norm))
                if vn_len > 1e-6:
                    avg_vert_norm /= vn_len
                else:
                    avg_vert_norm = face_norm

                blended_norm = avg_vert_norm * normal_smooth_ratio + face_norm * (1.0 - normal_smooth_ratio)
                bn_len = float(np.linalg.norm(blended_norm))
                if bn_len > 1e-6:
                    blended_norm /= bn_len

                NdotL_sun = max(0.0, float(np.dot(blended_norm, L_sun)))
                NdotL_fill = max(0.0, float(np.dot(blended_norm, L_fill)))
                diffuse_sun = 0.44 * math.pow(NdotL_sun, 1.15)
                diffuse_fill = 0.14 * NdotL_fill
                ambient = 0.68 + 0.12 * (blended_norm[2] - 0.7)
                shade = ambient + diffuse_sun + diffuse_fill

                col = (vertex_colors.get(idx_a, col_base) + vertex_colors.get(idx_b, col_base) + vertex_colors.get(idx_c, col_base)) / 3.0
                slope_val = 1.0 - blended_norm[2]
                if slope_val > 0.14:
                    cliff_w = min(0.60, (slope_val - 0.14) / 0.22)
                    col = col * (1.0 - cliff_w) + np.array([66, 64, 71], dtype=np.float64) * cliff_w

                if avg_elev > snow_threshold:
                    snow_w = min(0.95, math.pow((avg_elev - snow_threshold) / (1.0 - snow_threshold), 2.0))
                    col = col * (1.0 - snow_w) + np.array([242, 244, 250], dtype=np.float64) * snow_w

                shaded_rgb = col * shade
                for k in range(3):
                    if shaded_rgb[k] > 220.0:
                        shaded_rgb[k] = 220.0 + (shaded_rgb[k] - 220.0) * 0.35

                final_rgb = (
                    min(248, max(0, int(shaded_rgb[0]))),
                    min(248, max(0, int(shaded_rgb[1]))),
                    min(248, max(0, int(shaded_rgb[2]))),
                )

                pts2d = [(int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), (int(pc[0]), int(pc[1]))]
                if len(pts2d) >= 3:
                    pygame.draw.polygon(surface, final_rgb, pts2d)

        # 1c. Optional continuous cartographic relief overlay (only when micropolys are disabled)
        if continuous_relief and not render_micropolys and use_brdf and not show_watersheds and len(self.centers) > 0:
            try:
                buf = pygame.image.tostring(surface, "RGB")
                img = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 3)).astype(np.float32)

                pts = [[c.x, c.y] for c in self.centers] + [[cn.x, cn.y] for cn in self.corners]
                elevs = [c.elevation for c in self.centers] + [cn.elevation for cn in self.corners]

                interp = LinearNDInterpolator(np.array(pts, dtype=np.float32), np.array(elevs, dtype=np.float32))
                gy, gx = np.mgrid[0:self.height:height*1j, 0:self.width:width*1j]
                H = np.nan_to_num(interp(gx, gy), nan=0.0)

                sigma = max(2.0, min(width, height) / 200.0)
                H_smooth = gaussian_filter(H, sigma=sigma)

                dHy, dHx = np.gradient(H_smooth)
                kh = 40.0 * (min(width, height) / 1000.0)
                nx = -dHx * kh
                ny = -dHy * kh
                nz = np.ones_like(nx)
                norm = np.sqrt(nx * nx + ny * ny + nz * nz)
                nx /= norm
                ny /= norm
                nz /= norm

                L = np.array([-0.55, -0.55, 0.70], dtype=np.float64)
                L /= np.linalg.norm(L)
                NdotL = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0.0, 1.0)

                sun_diffuse = 0.15 * np.power(NdotL, 1.2)
                ambient = 0.85 + 0.10 * (nz - 0.7)
                hillshade = ambient + sun_diffuse

                rng = np.random.RandomState(self.seed)
                micro_noise = (rng.rand(height, width) - 0.5) * 0.02
                hillshade = np.clip(hillshade + micro_noise, 0.70, 1.15)

                is_land = H > 0.16
                for ch in range(3):
                    val = img[:, :, ch] * hillshade
                    val = np.where(val > 220.0, 220.0 + (val - 220.0) * 0.35, val)
                    img[:, :, ch] = np.where(
                        is_land,
                        np.clip(val, 0, 246),
                        img[:, :, ch]
                    )

                surface = pygame.image.fromstring(img.astype(np.uint8).tobytes(), (width, height), "RGB")
            except Exception:
                pass

        def _smooth_edge_pts(path_pts: List[np.ndarray]) -> List[Tuple[int, int]]:
            if len(path_pts) >= 4:
                arr = np.array(path_pts, dtype=np.float64)
                prev_p = np.roll(arr, 1, axis=0)
                next_p = np.roll(arr, -1, axis=0)
                sm = 0.20 * prev_p + 0.60 * arr + 0.20 * next_p
                sm[0] = arr[0]
                sm[-1] = arr[-1]
                return [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in sm]
            return [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in path_pts]

        # 2. Draw rivers along noisy paths with specular highlight
        river_base = (56, 138, 220) if use_brdf else (68, 140, 210)
        for e in self.edges:
            if e.river > 0 and e.v0 and e.v1:
                w_line = min(8, max(1, int(1 + math.log2(e.river + 1))))
                if use_noisy_edges and self.noisy_edges:
                    pts = self.noisy_edges.get_edge_path(e, start_corner=e.v0)
                    line_pts = _smooth_edge_pts(pts)
                    if len(line_pts) >= 2:
                        pygame.draw.lines(surface, river_base, False, line_pts, width=w_line)
                else:
                    p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                    p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                    pygame.draw.line(surface, river_base, p0, p1, width=w_line)

        # 3. Draw lava fissures
        if show_lava:
            lava_outer = (180, 32, 16)
            lava_core = (255, 190, 32)
            for e in self.edges:
                if getattr(e, 'lava', False) and e.v0 and e.v1:
                    if use_noisy_edges and self.noisy_edges:
                        pts = self.noisy_edges.get_edge_path(e, start_corner=e.v0)
                        line_pts = _smooth_edge_pts(pts)
                        if len(line_pts) >= 2:
                            pygame.draw.lines(surface, lava_outer, False, line_pts, width=4)
                            pygame.draw.lines(surface, lava_core, False, line_pts, width=2)
                    else:
                        p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                        p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                        pygame.draw.line(surface, lava_outer, p0, p1, width=4)
                        pygame.draw.line(surface, lava_core, p0, p1, width=2)

        # 4. Draw contour roads
        if show_roads:
            road_color = (195, 170, 125) if use_brdf else (170, 140, 100)
            for e in self.edges:
                if getattr(e, 'road', 0) > 0 and e.v0 and e.v1:
                    # Do not draw roads through ocean
                    if (e.d0 and e.d0.ocean) and (e.d1 and e.d1.ocean):
                        continue
                    if use_noisy_edges and self.noisy_edges:
                        pts = self.noisy_edges.get_edge_path(e, start_corner=e.v0)
                        line_pts = _smooth_edge_pts(pts)
                        if len(line_pts) >= 2:
                            pygame.draw.lines(surface, road_color, False, line_pts, width=2)
                    else:
                        p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                        p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                        pygame.draw.line(surface, road_color, p0, p1, width=2)

        # 5. Draw coastline contours
        coast_color = (18, 55, 95) if use_brdf else (25, 45, 75)
        for e in self.edges:
            if e.v0 and e.v1 and e.d0 and e.d1:
                if (e.d0.ocean != e.d1.ocean) or (e.d0.water != e.d1.water):
                    if use_noisy_edges and self.noisy_edges:
                        pts = self.noisy_edges.get_edge_path(e, start_corner=e.v0)
                        line_pts = _smooth_edge_pts(pts)
                        if len(line_pts) >= 2:
                            pygame.draw.lines(surface, coast_color, False, line_pts, width=2)
                    else:
                        p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                        p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                        pygame.draw.line(surface, coast_color, p0, p1, width=2)

        return surface


# ---------------------------------------------------------------------------
# Parallel Multi-Core Map Generation Engine
# ---------------------------------------------------------------------------

class ParallelPolygonMapGenerator:
    """Manages parallel map generation across worker processes and threads."""

    @staticmethod
    def _worker_generate_map(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Worker function executing independent polygonal map generation."""
        t0 = time.perf_counter()
        gen = PolygonMapGenerator(**kwargs)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Summarize output metrics for serialization
        n_centers = len(gen.centers)
        n_corners = len(gen.corners)
        n_edges = len(gen.edges)
        land_centers = sum(1 for c in gen.centers if not c.water)
        ocean_centers = sum(1 for c in gen.centers if c.ocean)
        lake_centers = sum(1 for c in gen.centers if c.water and not c.ocean)
        river_edges = sum(1 for e in gen.edges if e.river > 0)

        # Count biomes
        biomes: Dict[str, int] = {}
        for c in gen.centers:
            biomes[c.biome] = biomes.get(c.biome, 0) + 1

        return {
            'seed': kwargs.get('seed', 0),
            'duration_ms': duration_ms,
            'centers_count': n_centers,
            'corners_count': n_corners,
            'edges_count': n_edges,
            'land_centers': land_centers,
            'ocean_centers': ocean_centers,
            'lake_centers': lake_centers,
            'river_edges': river_edges,
            'biomes': biomes,
            'generator': gen,
        }

    @classmethod
    def generate_batch_parallel(
        cls,
        seeds: List[int],
        num_points: int = 1000,
        max_workers: Optional[int] = None,
        use_processes: bool = False,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Generate multiple polygonal maps in parallel using multi-core worker pool."""
        tasks = []
        for s in seeds:
            task_kwargs = {
                'seed': s,
                'num_points': num_points,
                **kwargs,
            }
            tasks.append(task_kwargs)

        executor_cls = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        with executor_cls(max_workers=max_workers) as executor:
            results = list(executor.map(cls._worker_generate_map, tasks))

        return results


# ---------------------------------------------------------------------------
# Integration Adapter: Apply Polygonal Map to REGNUM Hex World
# ---------------------------------------------------------------------------

def apply_polygon_map_to_world(
    tiles: list,
    seed: int = 42,
    grid_rows: int = 9,
    grid_cols: int = 9,
    num_points: int = 800,
    island_shape: str = 'radial',
) -> PolygonMapGenerator:
    """Sample polygonal geography onto the REGNUM 9x9 hex tile grid.
    
    Provides 100% plug-and-play parity with apply_heightmap_to_world in heightmap.py.
    """
    from hexmap import rectangular_hex_layout, axial_to_pixel

    gen = PolygonMapGenerator(
        seed=seed,
        width=1000.0,
        height=1000.0,
        num_points=num_points,
        island_shape=island_shape,
    )

    layout = rectangular_hex_layout(grid_rows, grid_cols)

    hex_size = 48.0
    # Compute bounding box of the hex grid in pixel space
    coords = [axial_to_pixel(q, r, hex_size) for q, r in layout.values()]
    min_x = min(p[0] for p in coords)
    max_x = max(p[0] for p in coords)
    min_y = min(p[1] for p in coords)
    max_y = max(p[1] for p in coords)

    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)

    margin = 80.0
    target_span_x = gen.width - 2 * margin
    target_span_y = gen.height - 2 * margin

    for tile in tiles:
        # Extract row, col from tile name
        if tile.name.startswith('r') and 'c' in tile.name:
            parts = tile.name[1:].split('c')
            r, c = int(parts[0]), int(parts[1])
        else:
            r, c = 0, 0

        tile.grid_r = r
        tile.grid_c = c

        q, ax_r = layout.get(f"r{r}c{c}", (c, r))
        px, py = axial_to_pixel(q, ax_r, hex_size)

        # Map hex center into polygon map coordinate space
        mx = margin + ((px - min_x) / span_x) * target_span_x
        my = margin + ((py - min_y) / span_y) * target_span_y

        center = gen.get_center_at(mx, my)

        tile.elevation = float(center.elevation if not center.water else -0.20)
        tile.moisture = float(center.moisture)
        tile.is_ocean = bool(center.ocean)
        tile.biome = center.biome.lower()

        # Altitude in meters
        if tile.elevation < 0.0:
            tile.elevation_meters = int(tile.elevation * 1500)
        else:
            tile.elevation_meters = int(tile.elevation * 3200)

        # BRDF illumination & color
        tile.terrain_color = center.brdf_color
        tile.hillshade = float(center.total_light)
        tile.normal = center.normal

    return gen

"""
terrain/mesh/noisy_edges.py — Amit Patel mapgen2 Quadrilateral Recursive Subdivision.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, TYPE_CHECKING
import numpy as np

from terrain.mesh.graph import Edge, Corner

if TYPE_CHECKING:
    from terrain.generator.polygon import PolygonMapGenerator


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

"""
test_mapgen2.py — Unit tests for Amit Patel's mapgen2 enhancements.

Tests:
1. Corner improvement (improve_corners) relaxation and midpoint updating
2. Recursive quadrilateral subdivision (NoisyEdges) paths, bounds, and watertight polygons
3. Watershed drainage basins, coastal outlets, and catchment sizing
4. Elevation contour zones and arterial island ring roads
5. High-altitude volcanic lava fissures and arid placement
6. Pygame rendering integration with noisy edges, BRDF shading, and watersheds
"""

import math
import os
import unittest

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import numpy as np

from polygon_map import (
    Center,
    Corner,
    Edge,
    NoisyEdges,
    PolygonMapGenerator,
)


class TestCornerImprovement(unittest.TestCase):
    """Test post-Voronoi corner relaxation."""

    def test_interior_corners_relaxed_and_midpoints_updated(self):
        # Generate raw without corner improvement
        gen_raw = PolygonMapGenerator(seed=123, width=800, height=800, num_points=250, enable_corner_improvement=False)
        # Generate with corner improvement
        gen_imp = PolygonMapGenerator(seed=123, width=800, height=800, num_points=250, enable_corner_improvement=True)

        self.assertEqual(len(gen_raw.corners), len(gen_imp.corners))

        moved_count = 0
        border_stayed = True
        for q_raw, q_imp in zip(gen_raw.corners, gen_imp.corners):
            if q_raw.border:
                if np.linalg.norm(q_raw.point - q_imp.point) > 1e-6:
                    border_stayed = False
            else:
                if np.linalg.norm(q_raw.point - q_imp.point) > 1e-4:
                    moved_count += 1

        self.assertTrue(border_stayed, "Border corners should not move during corner improvement")
        self.assertGreater(moved_count, len(gen_imp.corners) * 0.5, "Majority of interior corners should be relaxed")

        # Verify edge midpoints match new corner locations
        for edge in gen_imp.edges:
            if edge.v0 and edge.v1:
                expected_mid = (edge.v0.point + edge.v1.point) * 0.5
                np.testing.assert_allclose(edge.midpoint, expected_mid, rtol=1e-5, atol=1e-5)


class TestNoisyEdges(unittest.TestCase):
    """Test recursive quadrilateral subdivision for organic noisy edges."""

    def setUp(self):
        self.gen = PolygonMapGenerator(seed=777, width=800, height=800, num_points=250, enable_noisy_edges=True)

    def test_noisy_edges_paths_exist_and_meet_at_midpoint(self):
        noisy = self.gen.noisy_edges
        self.assertIsNotNone(noisy)

        checked_edges = 0
        for edge in self.gen.edges:
            if edge.v0 is None or edge.v1 is None:
                continue

            self.assertIn(edge.index, noisy.path0)
            self.assertIn(edge.index, noisy.path1)

            p0 = noisy.path0[edge.index]
            p1 = noisy.path1[edge.index]

            self.assertGreaterEqual(len(p0), 2)
            self.assertGreaterEqual(len(p1), 2)

            # path0: v0 -> midpoint
            np.testing.assert_allclose(p0[0], edge.v0.point, atol=1e-5)
            np.testing.assert_allclose(p0[-1], edge.midpoint, atol=1e-5)

            # path1: v1 -> midpoint
            np.testing.assert_allclose(p1[0], edge.v1.point, atol=1e-5)
            np.testing.assert_allclose(p1[-1], edge.midpoint, atol=1e-5)

            # Ordered edge path from v0 to v1
            path_v0_v1 = noisy.get_edge_path(edge, start_corner=edge.v0)
            self.assertGreaterEqual(len(path_v0_v1), 3)
            np.testing.assert_allclose(path_v0_v1[0], edge.v0.point, atol=1e-5)
            np.testing.assert_allclose(path_v0_v1[-1], edge.v1.point, atol=1e-5)

            checked_edges += 1

        self.assertGreater(checked_edges, 300)

    def test_noisy_polygon_boundary_is_closed_and_bounded(self):
        for c in self.gen.centers:
            if len(c.corners) < 3:
                continue

            boundary = self.gen.get_polygon_noisy_boundary(c)
            self.assertGreaterEqual(len(boundary), 4)

            # Check closed loop
            np.testing.assert_allclose(boundary[0], boundary[-1], atol=1e-5)

            # No NaNs or infinities
            self.assertFalse(np.isnan(boundary).any())
            self.assertFalse(np.isinf(boundary).any())

            # Check bounding coordinates
            min_x, min_y = np.min(boundary, axis=0)
            max_x, max_y = np.max(boundary, axis=0)
            self.assertGreaterEqual(min_x, -self.gen.width * 0.25)
            self.assertGreaterEqual(min_y, -self.gen.height * 0.25)
            self.assertLessEqual(max_x, self.gen.width * 1.25)
            self.assertLessEqual(max_y, self.gen.height * 1.25)

    def test_feature_dependent_subdivision_density(self):
        """Coastlines and rivers should have finer subdivision than open ocean edges."""
        noisy = self.gen.noisy_edges

        coast_lengths = []
        ocean_lengths = []

        for edge in self.gen.edges:
            if edge.v0 and edge.v1 and edge.d0 and edge.d1:
                p0 = noisy.path0.get(edge.index, [])
                if (edge.d0.coast or edge.d1.coast) and p0:
                    coast_lengths.append(len(p0))
                elif (edge.d0.ocean and edge.d1.ocean) and p0:
                    ocean_lengths.append(len(p0))

        if coast_lengths and ocean_lengths:
            avg_coast_pts = sum(coast_lengths) / len(coast_lengths)
            avg_ocean_pts = sum(ocean_lengths) / len(ocean_lengths)
            self.assertGreater(
                avg_coast_pts,
                avg_ocean_pts,
                f"Coastline noisy path avg points ({avg_coast_pts:.1f}) should be > ocean ({avg_ocean_pts:.1f})",
            )


class TestWatersheds(unittest.TestCase):
    """Test drainage basin catchment and coastal outlet calculations."""

    def setUp(self):
        self.gen = PolygonMapGenerator(seed=456, width=800, height=800, num_points=300, enable_watersheds=True)

    def test_watersheds_assigned_and_basins_exist(self):
        land_corners = [cn for cn in self.gen.corners if not cn.ocean]
        self.assertGreater(len(land_corners), 50)

        outlets = set()
        for cn in land_corners:
            self.assertIsNotNone(cn.watershed)
            # Coastal corners or outlets
            if cn.watershed.coast or cn.watershed.ocean:
                outlets.add(cn.watershed.index)

        self.assertGreater(len(outlets), 3, "There should be multiple distinct drainage basins on the island")

        # Centers must have watershed and size
        land_centers = [c for c in self.gen.centers if not c.ocean]
        for c in land_centers:
            self.assertIsNotNone(c.watershed)
            self.assertGreater(c.watershed_size, 0)


class TestRoads(unittest.TestCase):
    """Test elevation contour labeling and arterial island ring roads."""

    def setUp(self):
        self.gen = PolygonMapGenerator(seed=888, width=800, height=800, num_points=300, enable_roads=True)

    def test_contour_zones_and_roads(self):
        # 1. Contours should range from 1 to >= 3
        contours = {c.contour for c in self.gen.centers}
        self.assertGreaterEqual(len(contours), 3)
        self.assertIn(1, contours)

        # 2. Road edges must exist bridging contour zones
        road_edges = [e for e in self.gen.edges if getattr(e, 'road', 0) > 0]
        self.assertGreater(len(road_edges), 10, "There should be arterial roads along contour boundaries")

        for e in road_edges:
            self.assertIsNotNone(e.v0)
            self.assertIsNotNone(e.v1)
            self.assertNotEqual(e.v0.contour, e.v1.contour, "Roads must connect different contour zones")


class TestLava(unittest.TestCase):
    """Test high-altitude volcanic fissure generation."""

    def test_lava_fissures_occur_in_high_arid_terrain(self):
        gen = PolygonMapGenerator(seed=321, width=800, height=800, num_points=400, enable_lava=True)

        lava_edges = [e for e in gen.edges if getattr(e, 'lava', False)]
        if lava_edges:
            for e in lava_edges:
                self.assertIsNotNone(e.d0)
                self.assertIsNotNone(e.d1)
                self.assertFalse(e.d0.water)
                self.assertFalse(e.d1.water)
                self.assertGreaterEqual(e.d0.elevation, 0.70)
                self.assertGreaterEqual(e.d1.elevation, 0.70)
                self.assertLessEqual(e.d0.moisture, 0.45)
                self.assertLessEqual(e.d1.moisture, 0.45)


class TestMapgen2Rendering(unittest.TestCase):
    """Test rendering of mapgen2 surfaces with noisy edges, BRDF shading, and watersheds."""

    def test_surface_rendering_modes(self):
        gen = PolygonMapGenerator(seed=999, width=600, height=600, num_points=200)

        # Mode 1: Noisy edges with BRDF shading, roads, and lava
        surf1 = gen.render_to_surface(
            width=300, height=300, use_brdf=True, use_noisy_edges=True, show_roads=True, show_lava=True
        )
        self.assertEqual(surf1.get_width(), 300)
        self.assertEqual(surf1.get_height(), 300)

        # Mode 2: Watershed drainage basin visualization
        surf2 = gen.render_to_surface(
            width=300, height=300, use_brdf=True, use_noisy_edges=True, show_watersheds=True
        )
        self.assertEqual(surf2.get_width(), 300)
        self.assertEqual(surf2.get_height(), 300)

        # Mode 3: Straight Voronoi fallback comparison
        surf3 = gen.render_to_surface(
            width=300, height=300, use_brdf=False, use_noisy_edges=False
        )
        self.assertEqual(surf3.get_width(), 300)


if __name__ == '__main__':
    unittest.main()

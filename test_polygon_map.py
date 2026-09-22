"""
test_polygon_map.py — Unit tests for Amit Patel Polygonal Map Generation.

Verifies:
- Dual-graph topological connectivity (Center-Corner-Edge cross-pointers)
- Lloyd relaxation uniformity & finite cell boundaries
- Ocean flood-fill and freshwater lake classification
- Hydrological invariants: downhill monotonicity, river accumulation, zero land sinks
- Moisture diffusion & Whittaker biome distribution
- Spatial KD-Tree queries
- Determinism and multi-core parallel generation
- REGNUM hex grid adapter compatibility
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
    PolygonMapGenerator,
    ParallelPolygonMapGenerator,
    apply_polygon_map_to_world,
    whittaker_biome,
    mapgen2_biome,
    BIOME_COLORS,
)
from render_dev_viewer import create_mock_island_tiles


class TestPolygonMapGraph(unittest.TestCase):
    """Test dual-graph construction, Lloyd relaxation, and topological consistency."""

    def setUp(self):
        self.gen = PolygonMapGenerator(seed=101, width=800, height=800, num_points=300, lloyd_iterations=2)

    def test_dual_graph_invariants(self):
        """Verify Center, Corner, and Edge reciprocal topological connectivity."""
        self.assertGreater(len(self.gen.centers), 200)
        self.assertGreater(len(self.gen.corners), 400)
        self.assertGreater(len(self.gen.edges), 600)

        # 1. Center <-> Corner reciprocity
        for c in self.gen.centers:
            self.assertGreater(len(c.corners), 2, f"Center {c.index} has fewer than 3 corners")
            for cn in c.corners:
                self.assertIn(c, cn.touches, f"Corner {cn.index} does not list Center {c.index} in touches")

        # 2. Corner <-> Center reciprocity
        for cn in self.gen.corners:
            self.assertGreater(len(cn.touches), 0, f"Corner {cn.index} touches no centers")
            for c in cn.touches:
                self.assertIn(cn, c.corners, f"Center {c.index} does not list Corner {cn.index} in corners")

        # 3. Corner adjacency reciprocity
        for cn in self.gen.corners:
            for adj in cn.adjacent:
                self.assertIn(cn, adj.adjacent, f"Corner {adj.index} not reciprocal neighbor of {cn.index}")

        # 4. Center neighbor reciprocity
        for c in self.gen.centers:
            for n in c.neighbors:
                self.assertIn(c, n.neighbors, f"Center {n.index} not reciprocal neighbor of {c.index}")

        # 5. Edge connectivity
        for e in self.gen.edges:
            self.assertIsNotNone(e.d0)
            self.assertIsNotNone(e.v0)
            if e.v1 is not None:
                self.assertIn(e.v1, e.v0.adjacent)
                self.assertIn(e.v0, e.v1.adjacent)

    def test_lloyd_relaxation_variance_reduction(self):
        """Lloyd relaxation should produce more evenly spaced centers with reduced spacing variance."""
        raw_gen = PolygonMapGenerator(seed=42, width=800, height=800, num_points=400, lloyd_iterations=0)
        relaxed_gen = PolygonMapGenerator(seed=42, width=800, height=800, num_points=400, lloyd_iterations=3)

        def min_neighbor_distances(gen):
            pts = np.array([c.point for c in gen.centers])
            diff = pts[:, np.newaxis, :] - pts[np.newaxis, :, :]
            dist = np.linalg.norm(diff, axis=-1)
            np.fill_diagonal(dist, np.inf)
            return np.min(dist, axis=1)

        raw_dists = min_neighbor_distances(raw_gen)
        rel_dists = min_neighbor_distances(relaxed_gen)

        raw_std = float(np.std(raw_dists))
        rel_std = float(np.std(rel_dists))

        self.assertLess(rel_std, raw_std, f"Relaxed spacing std {rel_std} should be < raw std {raw_std}")


class TestPolygonMapHydrologyAndElevation(unittest.TestCase):
    """Test elevation assignment, downslope monotonicity, and river accumulation."""

    def setUp(self):
        self.gen = PolygonMapGenerator(
            seed=777,
            width=1000,
            height=1000,
            num_points=500,
            lloyd_iterations=2,
            island_shape='radial',
            river_count=30,
        )

    def test_boundary_ocean_classification(self):
        """Perimeter cells and corners must be ocean."""
        for c in self.gen.centers:
            if c.border:
                self.assertTrue(c.ocean, f"Border center {c.index} must be ocean")
                self.assertTrue(c.water, f"Border center {c.index} must be water")

        for cn in self.gen.corners:
            if cn.border:
                self.assertTrue(cn.ocean, f"Border corner {cn.index} must be ocean")
                self.assertTrue(cn.water, f"Border corner {cn.index} must be water")

    def test_elevation_bounds_and_coast(self):
        """Elevation should be 0.0 at ocean, low at coast, and normalized in [0.0, 1.0]."""
        for cn in self.gen.corners:
            self.assertGreaterEqual(cn.elevation, 0.0)
            self.assertLessEqual(cn.elevation, 1.0)
            if cn.ocean:
                self.assertAlmostEqual(cn.elevation, 0.0, delta=1e-5)
            elif cn.coast:
                self.assertGreater(cn.elevation, 0.0)
                self.assertLess(cn.elevation, 0.35)

        for c in self.gen.centers:
            self.assertGreaterEqual(c.elevation, 0.0)
            self.assertLessEqual(c.elevation, 1.0)
            if c.ocean:
                self.assertAlmostEqual(c.elevation, 0.0, delta=1e-5)

    def test_downslope_monotonicity_and_zero_sinks(self):
        """Every land corner must flow downhill strictly terminating in ocean/lake (no sinks or cycles)."""
        land_corners = [cn for cn in self.gen.corners if not cn.water]
        self.assertGreater(len(land_corners), 50)

        for start_cn in land_corners:
            curr = start_cn
            visited = set()
            steps = 0
            while not curr.water:
                self.assertNotIn(curr.index, visited, f"Cycle detected in downhill downslope flow at corner {curr.index}")
                visited.add(curr.index)

                down = curr.downslope
                self.assertIsNotNone(down, f"Land corner {curr.index} has no downslope pointer (unconnected sink)")
                self.assertLessEqual(
                    down.elevation,
                    curr.elevation + 1e-6,
                    f"Downslope corner {down.index} (elv {down.elevation}) is uphill from {curr.index} (elv {curr.elevation})"
                )
                curr = down
                steps += 1
                self.assertLess(steps, 200, "Downslope path exceeded maximum allowable hops without reaching water")

            # Final destination reached water
            self.assertTrue(curr.water or curr.ocean)

    def test_river_network_accumulation(self):
        """Rivers must have positive flux along Voronoi edges and accumulate volume downhill."""
        river_edges = [e for e in self.gen.edges if e.river > 0]
        self.assertGreater(len(river_edges), 0, "Expected at least one river edge generated")

        river_corners = [cn for cn in self.gen.corners if cn.river > 0]
        self.assertGreater(len(river_corners), 0, "Expected corners with river flow")

        # Downhill river corners should have at least the river flux of upstream
        for cn in river_corners:
            if not cn.water and cn.downslope and cn.downslope.river > 0:
                self.assertGreaterEqual(
                    cn.downslope.river,
                    cn.river,
                    f"Downstream corner {cn.downslope.index} river {cn.downslope.river} < upstream {cn.index} river {cn.river}"
                )


class TestPolygonMapBiomesAndQueries(unittest.TestCase):
    """Test Whittaker diagram biomes, moisture redistribution, and KDTree querying."""

    def setUp(self):
        self.gen = PolygonMapGenerator(seed=42, width=1000, height=1000, num_points=600, island_shape='perlin')

    def test_moisture_distribution_and_biomes(self):
        """Moisture must be in [0.0, 1.0], and all land biomes must be valid Whittaker types."""
        valid_biomes = set(BIOME_COLORS.keys())

        for c in self.gen.centers:
            self.assertGreaterEqual(c.moisture, 0.0)
            self.assertLessEqual(c.moisture, 1.0)
            self.assertIn(c.biome, valid_biomes)
            if c.ocean:
                self.assertEqual(c.biome, 'OCEAN')
            elif c.water:
                self.assertEqual(c.biome, 'LAKE')

    def test_whittaker_biome_lookup_table(self):
        """Verify standard Whittaker biome boundaries."""
        self.assertEqual(whittaker_biome(0.9, 0.7), 'SNOW')
        self.assertEqual(whittaker_biome(0.9, 0.25), 'BARE')
        self.assertEqual(whittaker_biome(0.9, 0.05), 'SCORCHED')
        self.assertEqual(whittaker_biome(0.7, 0.8), 'TAIGA')
        self.assertEqual(whittaker_biome(0.7, 0.5), 'SHRUBLAND')
        self.assertEqual(whittaker_biome(0.7, 0.1), 'TEMPERATE_DESERT')
        self.assertEqual(whittaker_biome(0.4, 0.9), 'TEMPERATE_RAIN_FOREST')
        self.assertEqual(whittaker_biome(0.4, 0.6), 'TEMPERATE_DECIDUOUS_FOREST')
        self.assertEqual(whittaker_biome(0.4, 0.2), 'GRASSLAND')
        self.assertEqual(whittaker_biome(0.1, 0.8), 'TROPICAL_RAIN_FOREST')
        self.assertEqual(whittaker_biome(0.1, 0.4), 'TROPICAL_SEASONAL_FOREST')
        self.assertEqual(whittaker_biome(0.1, 0.05), 'SUBTROPICAL_DESERT')

    def test_mapgen2_climate_and_persistence(self):
        """Verify Mapgen2 temperature gradient, moisture bias, and persistence knobs."""
        # 1. Mapgen2 biome matrix
        self.assertEqual(mapgen2_biome(0.10, 0.70), 'SNOW')
        self.assertEqual(mapgen2_biome(0.10, 0.05), 'SCORCHED')
        self.assertEqual(mapgen2_biome(0.30, 0.80), 'TAIGA')
        self.assertEqual(mapgen2_biome(0.60, 0.90), 'TEMPERATE_RAIN_FOREST')
        self.assertEqual(mapgen2_biome(0.85, 0.80), 'TROPICAL_RAIN_FOREST')
        self.assertEqual(mapgen2_biome(0.85, 0.05), 'SUBTROPICAL_DESERT')

        # 2. Temperature gradient: N-Cold / S-Hot
        gen_ncold_shot = PolygonMapGenerator(
            seed=42, width=800, height=800, num_points=300,
            north_temperature=-1.0, south_temperature=1.0,
        )
        north_land = [c for c in gen_ncold_shot.centers if not c.water and c.y < 300]
        south_land = [c for c in gen_ncold_shot.centers if not c.water and c.y > 500]
        if north_land and south_land:
            avg_north_t = np.mean([c.temperature for c in north_land])
            avg_south_t = np.mean([c.temperature for c in south_land])
            self.assertLess(avg_north_t, avg_south_t)

        # 3. Moisture bias: Dry vs Wet
        gen_dry = PolygonMapGenerator(seed=42, width=800, height=800, num_points=300, moisture_bias=-0.5)
        gen_wet = PolygonMapGenerator(seed=42, width=800, height=800, num_points=300, moisture_bias=0.5)
        dry_land = [c.moisture for c in gen_dry.centers if not c.water]
        wet_land = [c.moisture for c in gen_wet.centers if not c.water]
        self.assertLess(np.mean(dry_land), np.mean(wet_land))

        # 4. Persistence parameter creates valid dual mesh and edges
        gen_jagged = PolygonMapGenerator(seed=42, width=800, height=800, num_points=300, persistence=-1.0)
        gen_smooth = PolygonMapGenerator(seed=42, width=800, height=800, num_points=300, persistence=1.0)
        self.assertGreater(len(gen_jagged.centers), 100)
        self.assertGreater(len(gen_smooth.centers), 100)

    def test_spatial_kdtree_queries(self):
        """Spatial KDTree lookups should return nearest center and consistent properties."""
        c = self.gen.get_center_at(500.0, 500.0)
        self.assertIsInstance(c, Center)
        self.assertAlmostEqual(self.gen.get_elevation_at(500.0, 500.0), c.elevation)
        self.assertAlmostEqual(self.gen.get_moisture_at(500.0, 500.0), c.moisture)
        self.assertEqual(self.gen.get_biome_at(500.0, 500.0), c.biome)


class TestParallelAndWorldIntegration(unittest.TestCase):
    """Test seed determinism, parallel batch generation, and REGNUM hex world adapter."""

    def test_seed_determinism(self):
        """Identical seeds must yield identical dual graphs and statistics."""
        gen1 = PolygonMapGenerator(seed=1234, width=600, height=600, num_points=250)
        gen2 = PolygonMapGenerator(seed=1234, width=600, height=600, num_points=250)

        self.assertEqual(len(gen1.centers), len(gen2.centers))
        self.assertEqual(len(gen1.corners), len(gen2.corners))
        self.assertEqual(len(gen1.edges), len(gen2.edges))

        for c1, c2 in zip(gen1.centers[:20], gen2.centers[:20]):
            np.testing.assert_allclose(c1.point, c2.point)
            self.assertEqual(c1.biome, c2.biome)
            self.assertAlmostEqual(c1.elevation, c2.elevation, places=6)
            self.assertAlmostEqual(c1.moisture, c2.moisture, places=6)

    def test_parallel_batch_generator(self):
        """Parallel generator should execute across worker threads and processes."""
        seeds = [101, 102, 103, 104]
        # Test thread pool
        res_threads = ParallelPolygonMapGenerator.generate_batch_parallel(
            seeds=seeds,
            num_points=150,
            max_workers=2,
            use_processes=False,
        )
        self.assertEqual(len(res_threads), 4)
        for r in res_threads:
            self.assertIn('duration_ms', r)
            self.assertGreater(r['centers_count'], 80)
            self.assertIn('biomes', r)

        # Test process pool
        res_procs = ParallelPolygonMapGenerator.generate_batch_parallel(
            seeds=[201, 202],
            num_points=150,
            max_workers=2,
            use_processes=True,
        )
        self.assertEqual(len(res_procs), 2)
        for r in res_procs:
            self.assertGreater(r['centers_count'], 80)

    def test_all_island_shapes_and_zero_sinks_robustness(self):
        """Test radial, blob, square, perlin shapes and verify zero sinks across all."""
        shapes = ['radial', 'blob', 'square', 'perlin']
        for shape in shapes:
            gen = PolygonMapGenerator(seed=42, width=800, height=800, num_points=250, island_shape=shape)
            land_corners = [cn for cn in gen.corners if not cn.water]
            self.assertGreater(len(land_corners), 20, f"Shape {shape} generated too few land corners")

            # Check zero sinks
            for cn in land_corners:
                curr = cn
                visited = set()
                while not curr.water:
                    self.assertNotIn(curr.index, visited)
                    visited.add(curr.index)
                    self.assertIsNotNone(curr.downslope, f"Sink found in shape {shape} at corner {curr.index}")
                    curr = curr.downslope
                self.assertTrue(curr.water or curr.ocean)

    def test_apply_polygon_map_to_world(self):
        """Adapter must successfully populate REGNUM hex tiles with terrain attributes."""
        tiles = create_mock_island_tiles(seed=999, rows=9, cols=9)
        gen = apply_polygon_map_to_world(tiles, seed=999, grid_rows=9, grid_cols=9, num_points=300)

        self.assertIsInstance(gen, PolygonMapGenerator)
        self.assertEqual(len(tiles), 81)

        ocean_count = 0
        land_count = 0
        for t in tiles:
            self.assertTrue(hasattr(t, 'elevation'))
            self.assertTrue(hasattr(t, 'moisture'))
            self.assertTrue(hasattr(t, 'is_ocean'))
            self.assertTrue(hasattr(t, 'biome'))
            self.assertTrue(hasattr(t, 'elevation_meters'))
            self.assertTrue(hasattr(t, 'terrain_color'))

            if t.is_ocean:
                ocean_count += 1
            else:
                land_count += 1

        self.assertGreater(ocean_count, 0, "World grid should have ocean tiles")
        self.assertGreater(land_count, 0, "World grid should have land tiles")


if __name__ == '__main__':
    unittest.main()

"""
test_voronoi_world.py — Test suite for Architecture B: Native Voronoi Cell Geopolitics.

Validates:
1. Procedural Voronoi World Generation (clustering, provinces, geography, connectivity).
2. Degree caps and mountain passes on irregular Voronoi polygons.
3. Conserved economic turn stepping (30 turns, 0 currency supply shifts).
4. Top-level rollback switch (switching between "voronoi" and "hex" topology).
"""

import unittest
import random
from world_config import (
    get_map_topology,
    set_map_topology,
    is_voronoi_topology,
    is_hex_topology,
    VORONOI_POINTS
)
from sim_world import build_world
import sim_engine
import forex as fx


class TestVoronoiWorld(unittest.TestCase):

    def setUp(self):
        # Ensure tests start in Voronoi topology
        set_map_topology("voronoi")

    def tearDown(self):
        # Reset to default
        set_map_topology("voronoi")

    def test_voronoi_generation_structure(self):
        """Test that build_world in Voronoi mode returns valid tiles, nations, and generator."""
        tiles, nations, gen = build_world(seed=42, terrain_seed=123, nation_seed=456)
        self.assertEqual(len(tiles), VORONOI_POINTS)
        self.assertEqual(len(nations), 3)
        self.assertIsNotNone(gen)

        # Check tile attributes
        land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False)]
        self.assertTrue(len(land_tiles) > 0)
        for t in tiles:
            self.assertTrue(hasattr(t, 'polygon'))
            self.assertTrue(hasattr(t, 'centroid'))
            self.assertTrue(hasattr(t, 'elevation'))
            self.assertTrue(hasattr(t, 'elevation_meters'))
            self.assertTrue(hasattr(t, 'biome'))
            self.assertTrue(hasattr(t, 'display_name'))

    def test_voronoi_nation_and_province_clustering(self):
        """Test that nations claim contiguous Voronoi clusters and have balanced provinces."""
        tiles, nations, gen = build_world(seed=101, terrain_seed=101, nation_seed=202)
        total_claimed = 0
        claimed_names = set()

        for nation in nations:
            self.assertTrue(len(nation.tiles) >= 3)
            total_claimed += len(nation.tiles)
            for t in nation.tiles:
                self.assertNotIn(t.name, claimed_names)
                claimed_names.add(t.name)
                self.assertEqual(t.owner_nation, nation)
                self.assertFalse(getattr(t, 'wilderness', False))

            # Province checks
            self.assertTrue(len(nation.provinces) >= 1)
            prov_tiles = []
            for prov in nation.provinces:
                self.assertTrue(len(prov.tiles) >= 2 or len(nation.tiles) < 4)
                prov_tiles.extend(prov.tiles)
                # Verify bank/gov/charity shared
                for t in prov.tiles:
                    self.assertEqual(t.bank, prov.bank)
                    self.assertEqual(t.gov, prov.gov)
                    self.assertEqual(t.charity, prov.charity)
            self.assertEqual(len(prov_tiles), len(nation.tiles))

    def test_voronoi_global_connectivity_and_degree_caps(self):
        """Test that land tiles form a single connected component and respect degree caps."""
        for seed in (42, 777):
            tiles, nations, gen = build_world(seed=seed, terrain_seed=seed, nation_seed=seed)
            land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False)]

            # Check single connected component
            visited = set()
            queue = [land_tiles[0]]
            visited.add(land_tiles[0].name)
            while queue:
                curr = queue.pop(0)
                for n in curr.neighbors.values():
                    if n.name not in visited and not getattr(n, 'is_ocean', False):
                        visited.add(n.name)
                        queue.append(n)

            self.assertEqual(len(visited), len(land_tiles),
                             f"Seed {seed}: land disconnected ({len(visited)} / {len(land_tiles)})")

            # Check degree caps (max 3 for land, max 2 for peaks)
            for t in land_tiles:
                elev = getattr(t, 'elevation', 0.20)
                biome = getattr(t, 'biome', 'PLAINS').upper()
                is_mountain = (elev >= 0.72) or (biome in ('MOUNTAINS', 'SNOW_PEAKS', 'SNOW', 'BARE'))
                max_deg = 2 if is_mountain else 3
                self.assertLessEqual(len(t.neighbors), max_deg,
                                     f"Tile {t.name} exceeded degree cap: {len(t.neighbors)} > {max_deg}")

    def test_voronoi_sim_stepping_and_conservation(self):
        """Step 30 turns of the simulation on Voronoi world and verify zero currency leaks."""
        tiles, nations, gen = build_world(seed=42, terrain_seed=42, nation_seed=42)
        currencies = [n.currency for n in nations]
        pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                       and r.neighbors.get(o.name) is not None
                       and not getattr(o, 'wilderness', False)
                       and not getattr(r, 'wilderness', False)]

        all_violations = []
        for t in range(1, 31):
            violations, _ = sim_engine.step_turn(
                t, tiles, nations=nations, pair_orders=pair_orders,
                currencies=currencies, ledger_exempt=True
            )
            all_violations.extend(violations)

        self.assertEqual(len(all_violations), 0,
                         f"Currency conservation violated: {all_violations}")

    def test_topology_rollback_switch(self):
        """Verify seamless toggle between Voronoi and Hex modes via top-level config."""
        # 1. Switch to Hex
        set_map_topology("hex")
        self.assertTrue(is_hex_topology())
        self.assertFalse(is_voronoi_topology())
        tiles_hex, nations_hex, grid_hex = build_world(seed=42)
        self.assertEqual(len(tiles_hex), 81)
        self.assertEqual(len(grid_hex), 9)
        self.assertEqual(len(grid_hex[0]), 9)

        # 2. Switch back to Voronoi
        set_map_topology("voronoi")
        self.assertTrue(is_voronoi_topology())
        self.assertFalse(is_hex_topology())
        tiles_v, nations_v, gen_v = build_world(seed=42)
        self.assertEqual(len(tiles_v), VORONOI_POINTS)

    def test_voronoi_worldview_integration(self):
        """Verify worldview state, camera centering, tile picking, and stepping in Voronoi mode."""
        from worldview_engine import build_world_view, step_world
        from worldview_camera import reset_cam, hex_px, tile_at, MAP_RIGHT, TOP_BAR_H, HEIGHT, TICKER_H
        from world_config import VORONOI_WIDTH, VORONOI_HEIGHT

        world = build_world_view(seed=42)
        self.assertEqual(world['bbox'], (0.0, 0.0, VORONOI_WIDTH, VORONOI_HEIGHT))
        self.assertIsNotNone(world.get('gen'))
        self.assertEqual(len(world['tiles']), VORONOI_POINTS)

        # Camera reset fits Voronoi world
        reset_cam(world)
        self.assertGreater(world['cam']['zoom'], 0.0)

        # Tile picking via screen coords
        sample_tile = world['tiles'][0]
        cx, cy = world['layout'][sample_tile.name]
        sx, sy = hex_px(world, cx, cy)
        picked = tile_at(world, sx, sy)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.name, sample_tile.name)

        # Step world 1 turn
        step_world(world)
        self.assertEqual(world['turn'], 1)
        self.assertEqual(len(world['violations']), 0)


if __name__ == '__main__':
    unittest.main()


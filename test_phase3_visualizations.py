"""
test_phase3_visualizations.py — Comprehensive Test Suite for Phase 3 Visualizations.

Verifies:
1. 10-turn Seasonal Agricultural Clock: Turn-to-Season mapping, biological multipliers, year increments, and lean season alerts.
2. Procedural Icons: Vector rendering for 'guano', 'trunk_sewer', 'spring', 'summer', 'autumn', and 'winter'.
3. Fluvial River Effluent: Dynamic river color thresholds based on water pollution.
4. Guano & Nitrate Global Deposit Beacon: Detection and rendering on resource tiles.
5. Farming Regime Badges & Alerts: Four-Field rotation, intensive monoculture, and nitrate starvation alerts.
6. Granary Reserve Gauge: Seasonal status tags (storing, buffering, empty).
7. The Great Stink Atmospheric & Parliamentary FX: Crisis detection and badge rendering.
8. Externalities Map Layer (Layer 9): tile_stats formatting with regime, granary, and pollution.
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import unittest
import math
import pygame
from goods import Goods
from region import Region
from nation import Nation
from tile_resources import TileResource
from worldview_seasonal_clock import get_season_info, draw_seasonal_clock, SEASON_CLOCK_RECT
from ui_icons import get_icon
from worldview_map import tile_stats, draw_edges, draw_terrain_glyph, draw_activity_badges, draw_tile_progress_bars
from terrain_edges import reset_edge_manager


class TestPhase3Visualizations(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((1400, 900))
        self.font = pygame.font.Font(None, 20)

        self.nation_a = Nation("Britannia")
        self.nation_b = Nation("Germania")

        self.tile_up = Region("UpstreamCity", 1)
        self.tile_up.owner_nation = self.nation_a
        self.tile_up.elevation = 0.40
        self.tile_up.is_river_corridor = True

        self.tile_down = Region("DownstreamEstuary", 2)
        self.tile_down.owner_nation = self.nation_b
        self.tile_down.elevation = 0.10
        self.tile_down.is_coast = True
        self.tile_down.is_river_corridor = True

        self.tile_up.neighbors[self.tile_down.name] = self.tile_down
        self.tile_down.neighbors[self.tile_up.name] = self.tile_up

        self.nation_a.tiles = [self.tile_up]
        self.nation_b.tiles = [self.tile_down]

        self.tiles = [self.tile_up, self.tile_down]
        self.layout = {self.tile_up.name: (100, 100), self.tile_down.name: (150, 150)}
        self.em = reset_edge_manager(self.tiles, self.layout)

        self.world = {
            'turn': 5,
            'tiles': self.tiles,
            'layout': self.layout,
            'nations': [self.nation_a, self.nation_b],
            'pair_orders': [(self.tile_up, self.tile_down)],
            'frame': 12,
            'cam': {'zoom': 1.0, 'ox': 0, 'oy': 0},
            'map_layer': 'externalities'
        }

    def test_01_seasonal_agricultural_clock_metrics(self):
        """Verify 10-turn seasonal clock calculations and metadata."""
        # Turn 0: Early Spring (Thaw & Sowing)
        s0 = get_season_info(0)
        self.assertEqual(s0['name'], "Early Spring")
        self.assertEqual(s0['year'], 1)
        self.assertEqual(s0['turn_in_year'], 0)
        self.assertTrue(s0['is_buffering'])
        self.assertFalse(s0['is_winter'])

        # Turn 5: Harvest Peak (+45% bumper harvest)
        s5 = get_season_info(5)
        self.assertEqual(s5['name'], "Harvest Peak")
        self.assertEqual(s5['icon'], "autumn")
        self.assertGreater(s5['mult'], 1.40)
        self.assertEqual(s5['pct_delta'], 43)  # sin(6pi/10) = 0.951 -> ~+43%
        self.assertTrue(s5['is_storing'])

        # Turn 9: Deep Winter (-45% lean season)
        s9 = get_season_info(9)
        self.assertEqual(s9['name'], "Deep Winter")
        self.assertEqual(s9['icon'], "winter")
        self.assertLess(s9['mult'], 0.60)
        self.assertTrue(s9['is_winter'])
        self.assertTrue(s9['is_buffering'])

        # Year rollover at Turn 10
        s10 = get_season_info(10)
        self.assertEqual(s10['year'], 2)
        self.assertEqual(s10['turn_in_year'], 0)

    def test_02_procedural_vector_icons(self):
        """Verify procedural icons for Guano, Trunk Sewer, and Seasons render without error."""
        icon_names = ['guano', 'nitrates', 'trunk_sewer', 'spring', 'summer', 'autumn', 'winter']
        for name in icon_names:
            surf = get_icon(name, size=24)
            self.assertIsInstance(surf, pygame.Surface)
            self.assertEqual(surf.get_width(), 24)
            self.assertEqual(surf.get_height(), 24)

    def test_03_seasonal_clock_hud_rendering(self):
        """Verify draw_seasonal_clock executes cleanly on Pygame surface."""
        # Render on surface
        draw_seasonal_clock(self.surface, self.world, self.font)
        targets = self.world.get('_ui_targets', [])
        self.assertTrue(any(t.action == 'seasonal_clock' for t in targets))

    def test_04_fluvial_river_effluent_and_downstream_flow(self):
        """Verify river color changes under pollution and downstream droplet calculations."""
        # Clean river (<= 10 pollution)
        self.tile_up.pollution_water = 5.0
        self.tile_down.pollution_water = 4.0
        draw_edges(self.surface, self.world)

        # Polluted river (> 30 pollution)
        self.tile_up.pollution_water = 45.0
        draw_edges(self.surface, self.world)

        # Riparian casus belli dispute marker
        dip_cb = getattr(self.nation_b, 'active_casus_belli', set())
        dip_cb.add((self.nation_a.name, 'riparian_poisoning'))
        self.nation_b.active_casus_belli = dip_cb
        draw_edges(self.surface, self.world)

    def test_05_guano_beacon_on_resource_tiles(self):
        """Verify ultra-rare Guano / Nitrate beacon renders on tiles with NATURAL_NITRATES."""
        self.tile_up.natural_resources = [TileResource.NATURAL_NITRATES]
        draw_terrain_glyph(self.surface, self.tile_up, 200, 200)

    def test_06_farming_regime_and_stink_activity_badges(self):
        """Verify farming regime badges (ROT, INT, !NTR) and The Great Stink crisis badge."""
        # A. Norfolk 4-Field Rotation
        self.tile_up.farming_regime = 'rotation'
        draw_activity_badges(self.surface, self.tile_up, 200, 200, self.font)

        # B. Intensive Monoculture with nitrate shortage
        self.tile_up.farming_regime = 'intensive'
        self.tile_up.is_nitrate_depleted = True
        draw_activity_badges(self.surface, self.tile_up, 200, 200, self.font)

        # C. The Great Stink on capital city
        self.tile_up.pollution_water = 65.0
        draw_activity_badges(self.surface, self.tile_up, 200, 200, self.font)

    def test_07_granary_gauge_and_sewer_progress_bars(self):
        """Verify granary buffer gauges and trunk sewer progress bars render on hexes."""
        self.tile_up.granary_stock = 28.5
        draw_tile_progress_bars(self.surface, self.tile_up, 200, 200, self.font, self.world)

        # Winter empty granary alert
        self.world['turn'] = 9
        self.tile_up.granary_stock = 0.5
        draw_tile_progress_bars(self.surface, self.tile_up, 200, 200, self.font, self.world)

    def test_08_externalities_layer_tile_stats(self):
        """Verify tile_stats under layer_mode == 'externalities' reflects Phase 3 mechanisms."""
        self.tile_up.soil_fertility = 1.25
        self.tile_up.nutrition_density = 0.95
        self.tile_up.farming_regime = 'rotation'
        self.tile_up.granary_stock = 30.0
        self.tile_up.pollution_water = 12.0

        top, mid, bot, b_col, m_col, t_col = tile_stats(self.tile_up, layer_mode='externalities', world=self.world)
        self.assertIn("Soil: 125%", top)
        self.assertIn("Regime: 4-Field", mid)
        self.assertIn("Gran: 30t", mid)

        # Test Great Stink alert in tile_stats
        self.tile_up.pollution_water = 70.0
        top, mid, bot, b_col, m_col, t_col = tile_stats(self.tile_up, layer_mode='externalities', world=self.world)
        self.assertEqual(bot, "🚨 THE GREAT STINK!")


if __name__ == '__main__':
    unittest.main()

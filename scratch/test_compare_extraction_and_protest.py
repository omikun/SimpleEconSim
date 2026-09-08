"""
test_compare_extraction_and_protest.py — Automated test for Comparison Modal Tabs 4 & 5.

Verifies:
1. Feudal tribute, multi-tier taxes, and grievance sources logging across stepping.
2. Tab 4: Class Wealth Extraction, Surplus Value, Taxes, and Attrition rendering across:
   - Country scope
   - Province scope
   - City / Tile scope
3. Tab 5: Protest Energy & Grievance Sources Breakdown rendering across:
   - Country scope
   - Province scope
   - City / Tile scope
4. compare_tab_hit for tabs 1..5 and sub-scope switches.
"""

import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('MPLCONFIGDIR', '/tmp')

import unittest
import pygame
from worldview_engine import build_world_view, step_world
from worldview_compare import draw_nations_comparison, compare_tab_hit
from worldview_compare_extraction import draw_tab4_extraction, _get_tile_stats
from worldview_compare_protest import draw_tab5_protest, _extract_tile_grievances
from worldview_ui import get_font


class TestCompareExtractionAndProtest(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.surface = pygame.Surface((1440, 900))
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 16)
        self.world = build_world_view(seed=42)

    def tearDown(self):
        pygame.quit()

    def test_logging_and_stepping(self):
        """Verify that stepping populates tribute, tax distribution, and grievance logs."""
        world = self.world
        for t in range(5):
            step_world(world)

        tile = world['nations'][0].tiles[0]
        self.assertGreater(len(tile.tribute_collected_log), 0)
        self.assertGreater(len(tile.tax_distribution_log), 0)
        self.assertGreater(len(tile.grievance_sources_log), 0)

        # Check structure of tax distribution log
        tax_entry = tile.tax_distribution_log[-1]
        self.assertIn('total', tax_entry)
        self.assertIn('municipal', tax_entry)
        self.assertIn('provincial', tax_entry)
        self.assertIn('national', tax_entry)

        # Check structure of grievance sources log
        g_entry = tile.grievance_sources_log[-1]
        self.assertIn('raw', g_entry)
        self.assertIn('pct', g_entry)
        self.assertIn('overworked', g_entry['raw'])
        self.assertIn('rent_enclosure', g_entry['raw'])

    def test_tab4_extraction_rendering(self):
        """Verify Tab 4 renders across all 3 sub-scopes without errors."""
        world = self.world
        for _ in range(3):
            step_world(world)

        world['compare_open'] = True
        world['compare_tab'] = 4

        # 1. Country scope
        world['compare_ext_scope'] = 'country'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

        # 2. Province scope
        world['compare_ext_scope'] = 'province'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

        # 3. City scope
        world['compare_ext_scope'] = 'city'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

    def test_tab5_protest_rendering(self):
        """Verify Tab 5 renders across all 3 sub-scopes without errors."""
        world = self.world
        for _ in range(3):
            step_world(world)

        world['compare_open'] = True
        world['compare_tab'] = 5

        # 1. Country scope
        world['compare_protest_scope'] = 'country'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

        # 2. Province scope
        world['compare_protest_scope'] = 'province'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

        # 3. City scope
        world['compare_protest_scope'] = 'city'
        draw_nations_comparison(self.surface, world, self.font, self.font_small)

    def test_tab_and_scope_hits(self):
        """Verify compare_tab_hit handles tabs 1..5 and scope buttons."""
        world = self.world
        world['compare_open'] = True

        # Test tab hits 1..5
        box_x = 30
        box_y = 20
        start_x = box_x + 20
        y = box_y + 48
        tab_w = 250

        for t_id in range(1, 6):
            click_pos = (start_x + tab_w // 2, y + 16)
            hit = compare_tab_hit(click_pos, box_x, box_y, world=world)
            self.assertEqual(hit, ('tab', t_id))
            start_x += tab_w + 10

        # Test Tab 4 scope selectors: y = box_y + 88, height 24, width 120
        world['compare_tab'] = 4
        # Scope 1: Country (gx = box_x + 20)
        hit = compare_tab_hit((box_x + 30, box_y + 95), box_x, box_y, world=world)
        self.assertEqual(hit, ('scope_ext', 'country'))
        self.assertEqual(world.get('compare_ext_scope'), 'country')

        # Scope 2: Province (gx = box_x + 20 + 130 = box_x + 150)
        hit = compare_tab_hit((box_x + 160, box_y + 95), box_x, box_y, world=world)
        self.assertEqual(hit, ('scope_ext', 'province'))
        self.assertEqual(world.get('compare_ext_scope'), 'province')

        # Scope 3: City (gx = box_x + 20 + 260 = box_x + 280)
        hit = compare_tab_hit((box_x + 290, box_y + 95), box_x, box_y, world=world)
        self.assertEqual(hit, ('scope_ext', 'city'))
        self.assertEqual(world.get('compare_ext_scope'), 'city')

        # Test Tab 5 scope selectors
        world['compare_tab'] = 5
        hit = compare_tab_hit((box_x + 160, box_y + 95), box_x, box_y, world=world)
        self.assertEqual(hit, ('scope_protest', 'province'))
        self.assertEqual(world.get('compare_protest_scope'), 'province')


if __name__ == '__main__':
    unittest.main()

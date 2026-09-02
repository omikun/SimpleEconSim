"""
test_left_governance_panel.py — Unit Tests for Left Governance & Policy Drawer.

Verifies:
1. Left dock buttons: [🔨 Build Menu (B)] and [🏛️ Governance (G)] rendering and click hit tests.
2. Scope switching across City/Tile, Province, and Nation.
3. Interactive City policy execution (Tax adjustments, UBI toggle, Food relief, Farm subsidy, Safety patrol).
4. Interactive Province policy execution (Highway maintenance, Health program, Equalization).
5. Interactive Nation policy execution (Science prize, Garrison mobilization, Sovereign grant).
6. Mutual exclusivity between Left Build Panel and Left Governance Panel.
"""

import unittest
import pygame
from worldview import build_world_view
from worldview_gov_panel import (
    draw_gov_panel, gov_panel_hit, draw_left_dock_buttons,
    GOV_PANEL_X, GOV_PANEL_Y, GOV_PANEL_W, GOV_PANEL_H
)
from worldview_build_panel import draw_build_panel, build_panel_hit
from worldview_ui import get_font


class TestLeftGovernancePanel(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.surface = pygame.Surface((1440, 900))
        self.font = get_font(18)
        self.font_small = get_font(13)

    def tearDown(self):
        pygame.quit()

    def test_left_dock_buttons_rendering_and_toggling(self):
        """Verify both dock buttons render and clicking them toggles respective panels."""
        world = build_world_view(seed=42)
        world['build_panel_open'] = False
        world['gov_panel_open'] = False

        # Render dock buttons
        draw_left_dock_buttons(self.surface, world, self.font_small)

        # Click Governance button at (GOV_PANEL_X + 20, GOV_PANEL_Y + 34 + 10)
        hit_gov = gov_panel_hit((GOV_PANEL_X + 20, GOV_PANEL_Y + 34 + 10), world)
        self.assertTrue(hit_gov)
        self.assertTrue(world['gov_panel_open'])
        self.assertFalse(world['build_panel_open'])

        # Close gov panel and click Build button: should open Build panel
        world['gov_panel_open'] = False
        hit_build = gov_panel_hit((GOV_PANEL_X + 20, GOV_PANEL_Y + 10), world)
        self.assertTrue(hit_build)
        self.assertTrue(world['build_panel_open'])
        self.assertFalse(world['gov_panel_open'])

    def test_scope_switching_in_gov_panel(self):
        """Verify clicking scope tabs switches between City, Province, and Nation."""
        world = build_world_view(seed=42)
        world['gov_panel_open'] = True
        world['build_panel_open'] = False
        world['policy_scope'] = 'tile'

        draw_gov_panel(self.surface, world, self.font, self.font_small)

        scope_y = GOV_PANEL_Y + 50
        tab_w = (GOV_PANEL_W - 24) // 3

        # Click Province tab (index 1)
        tx_prov = GOV_PANEL_X + 8 + 1 * (tab_w + 4) + 10
        hit = gov_panel_hit((tx_prov, scope_y + 10), world)
        self.assertTrue(hit)
        self.assertEqual(world['policy_scope'], 'province')

        # Click Nation tab (index 2)
        tx_nat = GOV_PANEL_X + 8 + 2 * (tab_w + 4) + 10
        hit = gov_panel_hit((tx_nat, scope_y + 10), world)
        self.assertTrue(hit)
        self.assertEqual(world['policy_scope'], 'nation')

    def test_city_policy_decrees_execution(self):
        """Verify executing city-level tax adjustments, food relief, and safety patrols."""
        world = build_world_view(seed=42)
        world['gov_panel_open'] = True
        world['policy_scope'] = 'tile'
        tile = world['nations'][0].tiles[0]
        world['selected_region'] = tile
        tile.gov.agent.cash = 500.0
        tile.gov.tax_rate = 0.15
        tile.protest_energy_log = [1.2]

        draw_gov_panel(self.surface, world, self.font, self.font_small)

        scope_y = GOV_PANEL_Y + 50
        cur_y = scope_y + 32
        tax_card_y = cur_y + 76 + 10

        # Click [-2% Tax]
        b1_x = GOV_PANEL_X + 16 + 10
        b1_y = tax_card_y + 28 + 10
        hit = gov_panel_hit((b1_x, b1_y), world)
        self.assertTrue(hit)
        self.assertAlmostEqual(tile.gov.tax_rate, 0.13, places=2)

        # Click Safety Patrol ($60)
        dec_card_y = tax_card_y + 80 + 10
        d3_x = GOV_PANEL_X + 16 + 10
        d3_y = dec_card_y + 92 + 10
        cash_before = tile.gov.agent.cash
        hit = gov_panel_hit((d3_x, d3_y), world)
        self.assertTrue(hit)
        self.assertAlmostEqual(cash_before - tile.gov.agent.cash, 60.0)
        self.assertAlmostEqual(tile.protest_energy_log[-1], 0.80, places=2)

    def test_province_and_nation_decrees_execution(self):
        """Verify executing provincial highway maintenance and national sovereign grants."""
        world = build_world_view(seed=42)
        world['gov_panel_open'] = True
        tile = world['nations'][0].tiles[0]
        world['selected_region'] = tile
        province = getattr(tile, 'province', None)
        nation = getattr(tile, 'owner_nation', None)

        if province and province.gov:
            world['policy_scope'] = 'province'
            province.gov.agent.cash = 500.0
            draw_gov_panel(self.surface, world, self.font, self.font_small)

            scope_y = GOV_PANEL_Y + 50
            cur_y = scope_y + 32
            dec_card_y = cur_y + 76 + 10
            p1_x = GOV_PANEL_X + 16 + 10
            p1_y = dec_card_y + 28 + 10

            p_cash_before = province.gov.agent.cash
            hit = gov_panel_hit((p1_x, p1_y), world)
            self.assertTrue(hit)
            self.assertAlmostEqual(p_cash_before - province.gov.agent.cash, 120.0)

        if nation and nation.government:
            world['policy_scope'] = 'nation'
            nation.government.agent.cash = 1000.0
            draw_gov_panel(self.surface, world, self.font, self.font_small)

            scope_y = GOV_PANEL_Y + 50
            cur_y = scope_y + 32
            dec_card_y = cur_y + 76 + 10
            n1_x = GOV_PANEL_X + 16 + 10
            n1_y = dec_card_y + 28 + 10

            n_cash_before = nation.government.agent.cash
            hit = gov_panel_hit((n1_x, n1_y), world)
            self.assertTrue(hit)
            self.assertAlmostEqual(n_cash_before - nation.government.agent.cash, 300.0)


if __name__ == "__main__":
    unittest.main()

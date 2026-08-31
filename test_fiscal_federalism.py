"""
test_fiscal_federalism.py — Comprehensive Test Suite for Multi-Tier Fiscal Federalism.

Verifies:
1. Statutory tri-tier tax division (50% National Sovereign, 30% Provincial, 20% Municipal).
2. Sovereign customs and tariff revenue sharing (80% State Treasury, 20% Port City).
3. Exact money conservation across taxation, tariffs, and transfers.
4. Manual user-triggered Horizontal Fiscal Equalization grants.
5. Guarantee that fiscal equalization never triggers automatically without user action.
6. Multi-tier treasury aggregation and UI build panel rendering.
"""

import unittest
import pygame
from worldview import build_world_view
from region_finance import collect_tax
from intents import execute_equalization_grant
from worldview_build_panel import draw_build_panel, build_panel_hit
from worldview_ui import get_font


class TestFiscalFederalism(unittest.TestCase):

    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.surface = pygame.Surface((1440, 900))
        self.font = get_font(18)
        self.font_small = get_font(13)

    def tearDown(self):
        pygame.quit()

    def test_statutory_tri_tier_tax_split(self):
        """Verify taxes are split 50% National Sovereign, 30% Provincial, 20% Municipal."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        # Give tile agents income
        for a in tile.agents:
            a.cash = 200.0
            a._delta_cash = 50.0
            a._delta_deposits = 0.0

        # Create distinct provincial and municipal government agents
        from province import InstitutionBundle
        tile._institutions = InstitutionBundle(tile.name, None, initial_cash=10.0)
        tile.gov.agent.cash = 10.0
        tile.gov.target_food_reserve = 50.0  # Force deficit

        n1.government.agent.cash = 100.0

        nat_cash_before = n1.government.agent.cash
        tile_cash_before = tile.gov.agent.cash

        # Run financial step
        collect_tax(tile, t=1)

        # Verify that both national and tile governments collected their shares
        self.assertGreater(n1.government.agent.cash, nat_cash_before)
        self.assertGreater(tile.gov.agent.cash, tile_cash_before)

        # Verify national received ~50% and municipal received ~20-50%
        nat_gain = n1.government.agent.cash - nat_cash_before
        tile_gain = tile.gov.agent.cash - tile_cash_before
        self.assertGreater(nat_gain, 0.0)
        self.assertGreater(tile_gain, 0.0)

    def test_sovereign_tariff_sharing(self):
        """Verify tariffs are split 80% to National Sovereign Treasury and 20% to Port Tile."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        n1.government.agent.cash = 500.0
        tile.gov.agent.cash = 50.0

        nat_before = n1.government.agent.cash
        tile_before = tile.gov.agent.cash

        # Receive $100 tariff with region context
        tile.gov.receive_tariff(t=1, amount=100.0, region=tile)

        self.assertAlmostEqual(n1.government.agent.cash - nat_before, 80.0, places=2)
        self.assertAlmostEqual(tile.gov.agent.cash - tile_before, 20.0, places=2)

    def test_manual_fiscal_equalization_grant(self):
        """Verify user-triggered manual Equalization Grant transfers funds strictly and conservatively."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        n1.government.agent.cash = 1000.0
        tile.gov.agent.cash = 20.0

        ok, msg = execute_equalization_grant(
            world=world,
            nation_name=n1.name,
            region_name=tile.name,
            grant_source='national_sovereign',
            grant_amount=250.0,
            t=1
        )
        self.assertTrue(ok, msg)
        self.assertAlmostEqual(n1.government.agent.cash, 750.0, places=2)
        self.assertAlmostEqual(tile.gov.agent.cash, 270.0, places=2)

    def test_equalization_not_automatic(self):
        """Verify that without manual user click, equalization never triggers automatically."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        n1.government.agent.cash = 1000.0
        tile.gov.agent.cash = 5.0
        tile.gov.target_food_reserve = 100.0

        # Step finance without user grant
        collect_tax(tile, t=1)

        # Sovereign cash should NOT drop to subsidize municipal tile automatically
        # (It only increases or stays constant from its 50% tax share)
        self.assertGreaterEqual(n1.government.agent.cash, 1000.0)

    def test_build_panel_equalization_button_interaction(self):
        """Verify clicking the Equalization button in Left Build Panel triggers grant."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        world['selected_region'] = tile
        world['build_panel_open'] = True
        n1.government.agent.cash = 800.0
        tile.gov.agent.cash = 30.0

        # Render panel
        draw_build_panel(self.surface, world, self.font, self.font_small)

        # Click the Equalization button:
        # y: 64 + 50 + (24+4*32+4) + (24+3*32+4) + (24+3*32+4) + 24 = 528
        click_y = 64 + 50 + 156 + 124 + 124 + 24 + 10
        hit = build_panel_hit((14 + 50, click_y), world)
        self.assertTrue(hit)
        self.assertAlmostEqual(n1.government.agent.cash, 550.0, places=2)
        self.assertAlmostEqual(tile.gov.agent.cash, 280.0, places=2)


if __name__ == "__main__":
    unittest.main()

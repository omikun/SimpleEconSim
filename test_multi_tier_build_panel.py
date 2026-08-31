"""
test_multi_tier_build_panel.py — Test Suite for Multi-Tier Build Panel & Fiscal Transfers.
"""

import unittest
import pygame
from buildings import BUILDING_RECIPES, BuildingRecipe
from worldview_engine import build_world_view
from worldview_build_panel import draw_build_panel, build_panel_hit
from worldview_transfer_dialog import draw_transfer_dialog, transfer_dialog_hit
from intents import execute_fiscal_transfer_and_build, BuildIntent
from worldview import render_frame


class TestMultiTierBuildPanel(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((1400, 720))
        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)

    def test_multi_tier_recipe_registry(self):
        """Verify recipes are properly categorized across Municipal, Provincial, and National tiers."""
        self.assertIn('farm', BUILDING_RECIPES)
        self.assertIn('granary', BUILDING_RECIPES)
        self.assertIn('paved_road', BUILDING_RECIPES)
        self.assertIn('mountain_pass', BUILDING_RECIPES)
        self.assertIn('central_mint', BUILDING_RECIPES)
        self.assertIn('military_citadel', BUILDING_RECIPES)

        self.assertEqual(BUILDING_RECIPES['farm'].tier, 'tile')
        self.assertEqual(BUILDING_RECIPES['granary'].tier, 'tile')
        self.assertEqual(BUILDING_RECIPES['paved_road'].tier, 'province')
        self.assertEqual(BUILDING_RECIPES['sanatorium'].tier, 'province')
        self.assertEqual(BUILDING_RECIPES['mountain_pass'].tier, 'nation')
        self.assertEqual(BUILDING_RECIPES['central_mint'].tier, 'nation')
        self.assertEqual(BUILDING_RECIPES['military_citadel'].tier, 'nation')

    def test_build_panel_and_transfer_dialog_rendering(self):
        """Verify headless rendering of the multi-tier build panel and transfer dialog."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        world['selected_region'] = tile
        world['build_panel_open'] = True

        # Render build panel
        draw_build_panel(self.surface, world, self.font, self.font_small)

        # Trigger transfer dialog
        world['transfer_dialog'] = {
            'open': True,
            'building_type': 'sawmill',
            'region': tile,
            'nation': n1,
            'on_hand': 120.0
        }

        # Render transfer dialog
        draw_transfer_dialog(self.surface, world, self.font, self.font_small)

        # Full frame render
        render_frame(self.surface, world)

    def test_provincial_grant_transfer_and_construction(self):
        """Verify resolving shortfall via Provincial Equalization Grant."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        # Ensure sibling tile has distinct government bundle with funds
        if len(n1.tiles) > 1:
            sibling = n1.tiles[1]
            from province import InstitutionBundle
            sibling._institutions = InstitutionBundle(sibling.name, None, initial_cash=500.0)
            sibling.gov.agent.cash = 500.0
        tile.gov.agent.cash = 50.0

        ok, msg = execute_fiscal_transfer_and_build(
            world=world,
            nation_name=n1.name,
            region_name=tile.name,
            building_type='farm',
            transfer_source='province_grant',
            transfer_amount=200.0,
            t=0
        )
        self.assertTrue(ok, msg)
        self.assertEqual(len(tile.construction_projects), 1)

    def test_sovereign_national_bailout_transfer(self):
        """Verify resolving shortfall via Sovereign National Bailout."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        n1.government.agent.cash = 1000.0
        tile.gov.agent.cash = 0.0

        ok, msg = execute_fiscal_transfer_and_build(
            world=world,
            nation_name=n1.name,
            region_name=tile.name,
            building_type='granary',
            transfer_source='national_bailout',
            transfer_amount=250.0,
            t=0
        )
        self.assertTrue(ok, msg)
        self.assertEqual(len(tile.construction_projects), 1)

    def test_municipal_bank_loan_transfer(self):
        """Verify resolving shortfall via Municipal Bank Loan."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        tile.bank.capital = 800.0
        tile.gov.agent.cash = 20.0

        ok, msg = execute_fiscal_transfer_and_build(
            world=world,
            nation_name=n1.name,
            region_name=tile.name,
            building_type='workshop',
            transfer_source='bank_loan',
            transfer_amount=380.0,
            t=0
        )
        self.assertTrue(ok, msg)
        self.assertEqual(len(tile.construction_projects), 1)

    def test_build_panel_click_hitboxes_and_layer_auto_collapse(self):
        """Verify build panel clicks match exact button positions and collapse layers."""
        world = build_world_view(seed=42)
        nations = world['nations']
        n1 = nations[0]
        tile = n1.tiles[0]

        world['selected_region'] = tile
        world['build_panel_open'] = True
        world['layers_collapsed'] = False

        # Drawing build panel must collapse layer dock
        draw_build_panel(self.surface, world, self.font, self.font_small)
        self.assertTrue(world['layers_collapsed'])

        # Test clicking the 2nd button in Municipal tier (Granary)
        # y: 64 + 50 + 24 + 32 = 170
        tile.gov.agent.cash = 1000.0
        hit = build_panel_hit((14 + 50, 64 + 50 + 24 + 32 + 10), world)
        self.assertTrue(hit)
        self.assertTrue(any(p.recipe.name == 'granary' for p in tile.construction_projects))


if __name__ == "__main__":
    unittest.main()

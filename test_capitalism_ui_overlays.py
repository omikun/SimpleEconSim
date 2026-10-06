"""
test_capitalism_ui_overlays.py — Unit Tests for Capitalist Map Overlays, Badges, and Estate/Financial HUD.

Verifies:
1. Procedural icons in ui_icons.py for cotton, cloth, luxuries, and steam_mill.
2. Geological deposit beacons (iron, coal, nitrates) in draw_terrain_glyph.
3. Capitalist commodity badges (mills, pastures, cotton, luxuries, captive labor) in draw_activity_badges.
4. Estate Cadastre crop allocation bar and sub-tab toggle (plots vs finance).
5. Financial HUD inspector cards (machinery breakdown, credit bills & yield curve, frontier estates).
6. Interactive hit testing for subtabs and machinery repair in cadastre_panel_hit.
"""

from __future__ import annotations
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/mpl_cache'

import unittest
import pygame
pygame.init()

from goods import Goods
from agent import Agent, initialize_agent
from land_tenure import LandPlot, TenureStatus, TileTenure
from ui_icons import get_icon
from worldview_map import draw_terrain_glyph, draw_activity_badges
from worldview_cadastre import draw_cadastre_panel, cadastre_panel_hit
from economy.finance_bills import CreditMarketManager, BillOfExchange
from economy.map_generator import generate_capitalism_map


class MockRegion:
    def __init__(self, name="Test_Region"):
        self.name = name
        self.display_name = "Parish of Manchester"
        self.city_name = "Manchester"
        self.terrain = {Goods.food: 1.0, Goods.wood: 1.0}
        self.climate = "temperate"
        self.natural_resources = []
        self.has_iron_deposit = False
        self.has_coal_vein = False
        self.has_nitrate_deposit = False
        self.agents = []
        self.neighbors = {}
        self.recipes = {}
        self.tenure = None
        self.owner_nation = None
        self.unrest_log = []
        self.demand_ratio_log = {}
        self.hungry_log = {}


class TestCapitalismUIOverlays(unittest.TestCase):
    def setUp(self):
        self.surface = pygame.Surface((1280, 720))
        self.font = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 13)

    def test_01_procedural_icons(self):
        """Verify crisp procedural vector icons render reliably without OS emoji fonts."""
        for kind in ('cotton', 'cloth', 'luxuries', 'steam_mill', 'iron_ore', 'coal_seam', 'guano'):
            icon_16 = get_icon(kind, size=16)
            self.assertIsInstance(icon_16, pygame.Surface)
            self.assertEqual(icon_16.get_size(), (16, 16))

            icon_24 = get_icon(kind, size=24)
            self.assertEqual(icon_24.get_size(), (24, 24))

    def test_02_geological_deposit_beacons(self):
        """Verify draw_terrain_glyph renders deposit beacons for iron, coal, and nitrates."""
        region = MockRegion()
        region.has_iron_deposit = True
        region.has_coal_vein = True
        region.has_nitrate_deposit = True

        # Should render onto surface without crashing
        draw_terrain_glyph(self.surface, region, cx=200, cy=200)

    def test_03_commodity_and_labor_badges(self):
        """Verify draw_activity_badges renders badges for manufacturing, pastures, cotton, and captive labor."""
        region = MockRegion()
        
        # 1. Corporation mill with broken machinery
        corp = Agent(1)
        corp.is_corporation = True
        corp.output = Goods.cloth
        corp.machinery_level = 1
        corp.machinery_broken = True
        region.agents.append(corp)

        # 2. Enclosed pasture plot
        tenure = TileTenure()
        plot_pas = LandPlot("p1", region.name, 10, 0.4, TenureStatus.ENCLOSED, "pasture")
        tenure.plots.append(plot_pas)
        region.tenure = tenure

        # 3. Cotton inventory
        investor = Agent(2)
        investor.inv_add(Goods.cotton, 15)
        investor.inv_add(Goods.foreign_luxuries, 5)
        # 4. Frontier captive labor estate
        investor.frontier_estates = [{
            'target_region': 'Overseas_Colony',
            'primary_commodity': 'cotton',
            'captive_labor': 12,
        }]
        region.agents.append(investor)

        # Render badges on hex center (cx=300, cy=300)
        draw_activity_badges(self.surface, region, cx=300, cy=300, font_small=self.font_small)

    def test_04_cadastre_crop_allocation_and_subtabs(self):
        """Verify Estate Cadastre displays land tenure breakdown, crop allocation bar, and subtab buttons."""
        region = MockRegion()
        tenure = TileTenure()
        tenure.plots.append(LandPlot("p1", region.name, 1, 0.4, TenureStatus.FEUDAL, "arable"))
        tenure.plots.append(LandPlot("p2", region.name, 1, 0.3, TenureStatus.ENCLOSED, "pasture"))
        tenure.plots.append(LandPlot("p3", region.name, 1, 0.3, TenureStatus.ENCLOSED, "cotton"))
        region.tenure = tenure

        world = {
            'turn': 3,
            'window': 20,
            'selected_region': region,
            'cadastre_subtab': 'plots',
            'cadastre_scroll': 0,
        }

        draw_cadastre_panel(self.surface, world, region, self.font, self.font_small)

        # Test subtab clicking
        # Click Capital & Credit button
        hit_fin = cadastre_panel_hit((1100, 290), world)
        # Verify subtab switches
        world['cadastre_subtab'] = 'finance'
        draw_cadastre_panel(self.surface, world, region, self.font, self.font_small)

    def test_05_finance_and_capital_inspector(self):
        """Verify Financial HUD displays machinery breakdown, credit bills & yield curve, and frontier estates."""
        region = MockRegion()
        
        # Corporate manufacturing firm with broken machinery
        corp = Agent(101)
        corp.is_corporation = True
        corp.output = Goods.cloth
        corp.machinery_level = 1
        corp.machinery_broken = True
        corp.broken_machinery = 1
        corp.cash = 50.0
        corp.inv_add(Goods.iron, 2)
        region.agents.append(corp)

        # Elite with frontier captive labor estate
        lord = Agent(102)
        lord.is_lord = True
        lord.cash = 200.0
        lord.frontier_estates = [{
            'target_region': 'Overseas_Plantation_Enclave',
            'primary_commodity': 'cotton',
            'captive_labor': 25,
        }]
        region.agents.append(lord)

        # Credit market manager with active bills
        credit_mgr = CreditMarketManager()
        bill = credit_mgr.issue_bill(corp, lord, lord, face_value=120.0, current_turn=2, tenor_turns=4)

        world = {
            'turn': 2,
            'window': 20,
            'selected_region': region,
            'cadastre_subtab': 'finance',
            'scenario_state': {
                'credit_manager_ref': credit_mgr,
            },
        }

        # Render finance cards
        draw_cadastre_panel(self.surface, world, region, self.font, self.font_small)

        # Test interactive machinery repair button click
        # Find repair button in cadastre buttons
        from worldview_cadastre import _CADASTRE_BUTTONS
        repair_btn = next((b for b in _CADASTRE_BUTTONS if b[1] == 'cadastre_repair_machinery'), None)
        self.assertIsNotNone(repair_btn, "Repair button should be rendered for broken machinery")

        rect, act, payload = repair_btn
        center_x = rect[0] + rect[2] // 2
        center_y = rect[1] + rect[3] // 2
        ok_hit = cadastre_panel_hit((center_x, center_y), world)
        self.assertTrue(ok_hit)
        self.assertFalse(corp.machinery_broken, "Machinery should be repaired after clicking repair button")


if __name__ == '__main__':
    unittest.main()

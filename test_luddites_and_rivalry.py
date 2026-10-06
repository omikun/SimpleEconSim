"""
test_luddites_and_rivalry.py — Unit Tests for Luddite Machine-Breaking and AI Nation Geopolitical Rivalry.

Verifies:
1. Luddite tension accumulation from statutory wage caps, mechanization, and starvation wages.
2. Nocturnal machine-breaking raids destroying factory machinery levels.
3. Armed factory guard defense contesting and repelling raids with strict cash conservation.
4. Parish bread relief pacifying combinations and reducing restiveness.
5. AI Nation Mercantilist Tariff adoption protecting domestic artisans against foreign cloth.
6. AI Nation Subsidized Industrial Emulation founding competing corporate steam mills.
7. AI Nation Peripheral Agrarian Dependency converting estate plots to raw cotton monoculture.
8. Cadastre HUD Card 1 Luddite actions and World Map LUD badges.
"""

from __future__ import annotations
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/mpl_cache'

import unittest
import pygame
pygame.init()

from goods import Goods
from agent import Agent
from land_tenure import LandPlot, TenureStatus, TileTenure
from economy.transformation_graph import initialize_default_transformation_ontology
from economy.luddite_resistance import LudditeMovementManager, LudditeState
from economy.geopolitical_rivalry import (
    GeopoliticalRivalryManager,
    RivalNationState,
    StrategicPosture,
)
from worldview_cadastre import draw_cadastre_panel, cadastre_panel_hit, _CADASTRE_BUTTONS
from worldview_map import draw_activity_badges


class MockNation:
    def __init__(self, name="Prussia"):
        self.name = name
        self.tiles = []
        self.gov = MockGovernment()


class MockGovernment:
    def __init__(self):
        self.agent = Agent(999)
        self.agent.is_government = True
        self.agent.cash = 100.0
        self.treasury = self.agent


class MockRegion:
    def __init__(self, name="Manchester"):
        self.name = name
        self.display_name = "Parish of Manchester"
        self.city_name = "Manchester"
        self.terrain = {Goods.food: 1.0, Goods.wood: 1.0}
        self.climate = "temperate"
        self.natural_resources = []
        self.has_iron_deposit = True
        self.has_coal_vein = True
        self.has_nitrate_deposit = False
        self.statute_of_laborers = False
        self.agents = []
        self.neighbors = {}
        self.recipes = {
            Goods.food: {'price': 1.0, 'production': 3.0, 'numInput': 0},
            Goods.cloth: {'price': 18.0, 'production': 2.0, 'input': Goods.cotton, 'numInput': 1},
            Goods.iron: {'price': 16.0, 'production': 1.0, 'input': Goods.iron_ore, 'numInput': 1},
        }
        self.goods = list(self.recipes.keys())
        self.gov = MockGovernment()
        self.tenure = None
        self.luddite_manager = None


class TestLudditesAndRivalry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_default_transformation_ontology()

    def setUp(self):
        self.surface = pygame.Surface((1280, 720))
        self.font = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 13)

    def test_01_luddite_tension_accumulation(self):
        """Verify Luddite tensions accumulate from wage caps, starvation wages, and mechanization."""
        region = MockRegion()
        ludd_mgr = LudditeMovementManager()
        region.luddite_manager = ludd_mgr

        corp = Agent(1)
        corp.is_corporation = True
        corp.machinery_level = 2
        corp.wage = 1.0  # Starvation wage (< 1.5 * food_price)
        region.agents.append(corp)

        worker = Agent(2)
        worker.hungry_steps = 2
        region.agents.append(worker)

        # 1. Base tension accumulates
        t1 = ludd_mgr.evaluate_tensions(region, t=1)
        self.assertGreater(t1, 0.0)

        # 2. Statutory wage cap accelerates tension
        region.statute_of_laborers = True
        t2 = ludd_mgr.evaluate_tensions(region, t=2)
        self.assertGreater(t2, t1)
        st = ludd_mgr.get_state(region.name)
        self.assertIn(st.active_threat_level, ("FERMENTING", "ACUTE_COMBINATION", "ACTIVE_RAIDS"))

    def test_02_nocturnal_machine_breaking_raid(self):
        """Verify nocturnal raids break machinery and degrade machinery levels when tension is high."""
        region = MockRegion()
        ludd_mgr = LudditeMovementManager()

        corp = Agent(1)
        corp.is_corporation = True
        corp.machinery_level = 2
        corp.machinery_broken = False
        region.agents.append(corp)

        st = ludd_mgr.get_state(region.name)
        st.combination_strength = 65.0  # Acute combination threshold

        raid_res = ludd_mgr.execute_nocturnal_raid(region, t=10)
        self.assertIsNotNone(raid_res)
        self.assertEqual(raid_res['type'], 'LUDDITE_MACHINE_BROKEN')
        self.assertTrue(corp.machinery_broken, "Machinery should be broken after raid")
        self.assertEqual(corp.machinery_level, 1, "Machinery level should be reduced from 2 to 1")
        self.assertEqual(st.machines_broken, 1)

    def test_03_armed_factory_guards_defense(self):
        """Verify hiring armed guards successfully repels machine-breaking raids with strict cash conservation."""
        region = MockRegion()
        ludd_mgr = LudditeMovementManager()

        employer = Agent(10)
        employer.cash = 60.0
        region.agents.append(employer)

        worker = Agent(20)
        worker.cash = 5.0
        region.agents.append(worker)

        corp = Agent(1)
        corp.is_corporation = True
        corp.machinery_level = 2
        corp.machinery_broken = False
        region.agents.append(corp)

        init_emp_cash = employer.cash
        init_wrk_cash = worker.cash

        # 1. Hire 3 guards
        hire_res = ludd_mgr.hire_factory_guards(employer, region, count=3)
        self.assertTrue(hire_res['success'])
        cost = hire_res['cost']
        self.assertEqual(employer.cash, init_emp_cash - cost)
        self.assertEqual(worker.cash, init_wrk_cash + cost, "Guard pay strictly conserved to local worker")

        # 2. Raid contested and repelled by guards
        st = ludd_mgr.get_state(region.name)
        st.combination_strength = 60.0
        raid_res = ludd_mgr.execute_nocturnal_raid(region, t=11)

        self.assertEqual(raid_res['type'], 'LUDDITE_RAID_REPELLED')
        self.assertFalse(corp.machinery_broken, "Machinery should NOT be broken when guarded")
        self.assertEqual(corp.machinery_level, 2)
        self.assertEqual(st.factory_guards, 2, "1 guard absorbed fatigue")

    def test_04_bread_relief_pacification(self):
        """Verify emergency bread relief pacifies combinations and clears worker hunger."""
        region = MockRegion()
        ludd_mgr = LudditeMovementManager()

        lord = Agent(50)
        lord.is_lord = True
        lord.cash = 100.0
        region.agents.append(lord)

        poor_worker = Agent(51)
        poor_worker.hungry_steps = 3
        poor_worker.cash = 0.0
        region.agents.append(poor_worker)

        st = ludd_mgr.get_state(region.name)
        st.combination_strength = 50.0

        # Grant $20 bread relief
        init_lord_cash = lord.cash
        init_poor_cash = poor_worker.cash

        res = ludd_mgr.grant_parish_bread_relief(lord, region, amount=20.0)
        self.assertTrue(res['success'])
        self.assertEqual(lord.cash, init_lord_cash - 20.0)
        self.assertEqual(poor_worker.cash, init_poor_cash + 20.0, "Relief cash strictly conserved to poor worker")
        self.assertLess(poor_worker.hungry_steps, 3)
        self.assertLess(st.combination_strength, 50.0, "Combination strength pacified")

    def test_05_geopolitical_mercantilist_tariff(self):
        """Verify rival nation adopts high mercantilist tariffs when metropolitan cloth floods its markets."""
        rival_nat = MockNation("France")
        rival_tile = MockRegion("Normandy")
        rival_nat.tiles.append(rival_tile)

        # Metropolitan cloth flooded into rival market
        merchant = Agent(88)
        merchant.inv_add(Goods.cloth, 15)
        rival_tile.agents.append(merchant)

        world = {
            'player_nation_name': "Lancashire_Metropole",
            'nations': [rival_nat],
        }

        riv_mgr = GeopoliticalRivalryManager()
        events = riv_mgr.evaluate_and_step_rivals(world, t=5)

        st = riv_mgr.get_state("France")
        self.assertEqual(st.posture, StrategicPosture.MERCANTILIST_TARIFF)
        self.assertAlmostEqual(st.tariff_rate, 0.40, places=2)
        self.assertTrue(any(e['type'] == 'MERCANTILIST_TARIFF_ENACTED' for e in events))

    def test_06_geopolitical_industrial_emulation(self):
        """Verify rival nation subsidizes domestic steam mills when mineral base and treasury exist."""
        rival_nat = MockNation("Prussia")
        rival_tile = MockRegion("Silesia")
        rival_tile.has_iron_deposit = True
        rival_tile.has_coal_vein = True
        rival_nat.tiles.append(rival_tile)
        rival_nat.gov.treasury.cash = 150.0

        world = {
            'player_nation_name': "Lancashire_Metropole",
            'nations': [rival_nat],
        }

        riv_mgr = GeopoliticalRivalryManager()
        events = riv_mgr.evaluate_and_step_rivals(world, t=6)

        st = riv_mgr.get_state("Prussia")
        self.assertEqual(st.posture, StrategicPosture.INDUSTRIAL_EMULATION)
        self.assertEqual(st.emulated_mills_count, 1)

        # Verify rival nation incorporated competing steam mill on its tile
        rival_firms = [a for a in rival_tile.agents if getattr(a, 'is_corporation', False)]
        self.assertEqual(len(rival_firms), 1)
        self.assertEqual(rival_firms[0].output, Goods.cloth)

    def test_07_geopolitical_agrarian_dependency(self):
        """Verify warm-climate rival without minerals adopts peripheral agrarian monoculture."""
        rival_nat = MockNation("Egypt")
        rival_tile = MockRegion("Delta")
        rival_tile.climate = "subtropical"
        rival_tile.has_iron_deposit = False
        rival_tile.has_coal_vein = False

        tenure = TileTenure()
        tenure.plots.append(LandPlot("plot_1", rival_tile.name, 1, 0.5, TenureStatus.FEUDAL, "arable"))
        rival_tile.tenure = tenure
        rival_nat.tiles.append(rival_tile)

        world = {
            'player_nation_name': "Lancashire_Metropole",
            'nations': [rival_nat],
        }

        riv_mgr = GeopoliticalRivalryManager()
        events = riv_mgr.evaluate_and_step_rivals(world, t=7)

        st = riv_mgr.get_state("Egypt")
        self.assertEqual(st.posture, StrategicPosture.AGRARIAN_DEPENDENCY)
        self.assertEqual(st.dependency_crop, "cotton")
        self.assertEqual(tenure.plots[0].production_type, "cotton", "Estate plots converted to cotton monoculture")

    def test_08_cadastre_hud_and_map_overlays(self):
        """Verify Cadastre Card 1 renders Luddite warnings & buttons and map renders LUD badge."""
        region = MockRegion()
        ludd_mgr = LudditeMovementManager()
        region.luddite_manager = ludd_mgr

        corp = Agent(1)
        corp.is_corporation = True
        corp.machinery_level = 2
        corp.cash = 50.0
        region.agents.append(corp)

        st = ludd_mgr.get_state(region.name)
        st.combination_strength = 60.0  # Trigger display & LUD badge

        world = {
            'turn': 3,
            'window': 20,
            'selected_region': region,
            'cadastre_subtab': 'finance',
            'scenario_state': {
                'luddite_manager_ref': ludd_mgr,
            }
        }

        # 1. Render Cadastre Panel
        draw_cadastre_panel(self.surface, world, region, self.font, self.font_small)

        # 2. Check interactive buttons
        hire_btn = next((b for b in _CADASTRE_BUTTONS if b[1] == 'cadastre_hire_guards'), None)
        relief_btn = next((b for b in _CADASTRE_BUTTONS if b[1] == 'cadastre_bread_relief'), None)
        self.assertIsNotNone(hire_btn, "Hire Guards button should be rendered")
        self.assertIsNotNone(relief_btn, "Bread Relief button should be rendered")

        # 3. Simulate click to hire guards
        rect, act, payload = hire_btn
        center_x = rect[0] + rect[2] // 2
        center_y = rect[1] + rect[3] // 2
        ok_hit = cadastre_panel_hit((center_x, center_y), world)
        self.assertTrue(ok_hit)
        self.assertGreater(st.factory_guards, 0)

        # 4. Render map badges (should render LUD badge without error)
        draw_activity_badges(self.surface, region, cx=500, cy=500, font_small=self.font_small)


if __name__ == '__main__':
    unittest.main()

"""
test_triangular_trade_and_luxuries.py — Unit Tests for Transatlantic Trade Triangle, Gating, and Prestige Cycles.

Verifies:
1. Startup graph-theoretic cycle discovery (Option A) and JSON serialization.
2. Geological and technological gating (RESOURCE_LOCKED, TECH_LOCKED, DORMANT_UNEXPLORED, ACTIVATED_ROUTE).
3. Dynamic negative-cycle arbitrage and multi-turn merchant voyage lifecycle with strict economic conservation.
4. Crown customs tariffs and luxury cargo delivery.
5. Conspicuous consumption, prestige accumulation, status tiers, and decay.
6. Elite capitalist planner autonomous voyage chartering.
7. Cadastre HUD Card 4 rendering and interactive click handling.
"""

from __future__ import annotations
import os
import tempfile
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['MPLCONFIGDIR'] = '/tmp/mpl_cache'

import unittest
import pygame
pygame.init()

from goods import Goods
from agent import Agent
from economy.transformation_graph import (
    TransformationGraph,
    CommoditySpec,
    initialize_default_transformation_ontology,
)
from economy.trade_circuit_discovery import (
    TradeCircuitSpec,
    TradeCircuitGraphSearch,
    CircuitGatingEvaluator,
    CircuitStatus,
)
from economy.triangular_trade import (
    MerchantVoyage,
    TradeTriangleManager,
)
from economy.conspicuous_consumption import (
    PrestigeTier,
    ConspicuousConsumptionManager,
)
from economy.capitalist_planner import EliteCapitalistPlanner
from worldview_cadastre import draw_cadastre_panel, cadastre_panel_hit, _CADASTRE_BUTTONS
from worldview_map import draw_activity_badges


class MockGovernment:
    def __init__(self):
        self.agent = Agent(999)
        self.agent.is_government = True
        self.agent.cash = 100.0


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
        self.agents = []
        self.neighbors = {}
        self.recipes = {
            Goods.food: {'price': 1.0, 'production': 3.0, 'numInput': 0},
            Goods.cloth: {'price': 18.0, 'production': 2.0, 'input': Goods.cotton, 'numInput': 1},
            Goods.iron: {'price': 16.0, 'production': 1.0, 'input': Goods.iron_ore, 'numInput': 1},
            Goods.foreign_luxuries: {'price': 90.0, 'is_luxury': True},
            Goods.porcelain: {'price': 55.0, 'is_luxury': True},
            Goods.fine_textiles: {'price': 50.0, 'is_luxury': True},
        }
        self.goods = list(self.recipes.keys())
        self.gov = MockGovernment()
        self.tenure = None
        self.trade_manager = None


class TestTriangularTradeAndLuxuries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_default_transformation_ontology()

    def setUp(self):
        self.surface = pygame.Surface((1280, 720))
        self.font = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 13)

    def test_01_startup_circuit_discovery_and_json(self):
        """Verify startup graph search discovers viable circuits and encodes them into JSON."""
        circuits = TradeCircuitGraphSearch.discover_circuits()
        self.assertGreaterEqual(len(circuits), 30, "Should discover at least 30 closed commodity circuits")

        # Verify attributes on discovered circuits
        c0 = circuits[0]
        self.assertIsInstance(c0, TradeCircuitSpec)
        self.assertIn(c0.export_good, ('cloth', 'iron', 'rum'))
        self.assertIn(c0.import_luxury, ('foreign_luxuries', 'porcelain', 'fine_textiles', 'tea'))

        # Test JSON serialization round-trip
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            temp_path = tf.name
        try:
            TradeCircuitGraphSearch.save_to_json(circuits, temp_path)
            loaded = TradeCircuitGraphSearch.load_from_json(temp_path)
            self.assertEqual(len(loaded), len(circuits))
            self.assertEqual(loaded[0].circuit_id, circuits[0].circuit_id)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_02_resource_and_technological_gating(self):
        """Verify circuits are gated by geological deposits, workshop recipes, and exploration state."""
        region = MockRegion()
        circuits = TradeCircuitGraphSearch.discover_circuits()
        iron_circuit = next((c for c in circuits if c.export_good == 'iron'), None)
        self.assertIsNotNone(iron_circuit)

        # 1. Active with both iron deposit and iron recipe
        status = CircuitGatingEvaluator.evaluate_circuit_status(iron_circuit, region)
        self.assertEqual(status, CircuitStatus.DORMANT_UNEXPLORED)

        # 2. Resource locked if region lacks iron deposit
        region.has_iron_deposit = False
        status_no_res = CircuitGatingEvaluator.evaluate_circuit_status(iron_circuit, region)
        self.assertEqual(status_no_res, CircuitStatus.RESOURCE_LOCKED)
        region.has_iron_deposit = True

        # 3. Tech locked if region lacks industrial recipe
        del region.recipes[Goods.iron]
        status_no_tech = CircuitGatingEvaluator.evaluate_circuit_status(iron_circuit, region)
        self.assertEqual(status_no_tech, CircuitStatus.TECH_LOCKED)

    def test_03_voyage_lifecycle_and_strict_conservation(self):
        """Verify voyage charter, multi-turn travel, tariff collection, and cargo delivery with strict conservation."""
        region = MockRegion()
        mariner = Agent(10)
        mariner.cash = 5.0
        region.agents.append(mariner)

        investor = Agent(20)
        investor.cash = 60.0
        investor.inv_add(Goods.cloth, 5)
        region.agents.append(investor)

        trade_mgr = TradeTriangleManager()
        region.trade_manager = trade_mgr

        # Pick cloth-cotton-foreign_luxuries triangle
        cid = next((c.circuit_id for c in trade_mgr.circuits.values() if c.export_good == 'cloth' and c.import_luxury == 'foreign_luxuries'), None)
        self.assertIsNotNone(cid)
        circuit = trade_mgr.get_circuit(cid)

        # Initial balances
        init_investor_cash = investor.cash
        init_gov_cash = region.gov.agent.cash
        init_mariner_cash = mariner.cash

        # 1. Charter Voyage
        res = trade_mgr.charter_voyage(investor, region, cid, is_pioneer=True)
        self.assertTrue(res['success'])
        self.assertEqual(investor.inv_get(Goods.cloth, 0), 0, "5 units of cloth loaded onto ship")
        self.assertEqual(circuit.status, CircuitStatus.ACTIVATED_ROUTE, "Route activated by pioneer")

        # Freight cash strictly conserved
        freight = circuit.base_freight_cost
        self.assertEqual(investor.cash, init_investor_cash - freight)
        self.assertEqual(mariner.cash, init_mariner_cash + freight, "Freight paid strictly to mariner")

        # 2. Advance Voyage through all legs
        world = {'selected_region': region, 'regions': [region], 'turn': 1}
        for t in range(circuit.base_voyage_turns):
            trade_mgr.step_all_voyages(world, t + 1)

        # 3. Verify Docking and Cargo Delivery
        self.assertEqual(len(trade_mgr.active_voyages), 0)
        self.assertEqual(len(trade_mgr.completed_voyages), 1)
        self.assertGreater(investor.inv_get(Goods.foreign_luxuries, 0), 0, "Luxury cargo delivered to investor")

        # Verify Crown Customs Tariff collected & conserved
        tariffs_paid = trade_mgr.total_tariffs_collected
        self.assertGreater(tariffs_paid, 0.0)
        self.assertAlmostEqual(region.gov.agent.cash, init_gov_cash + tariffs_paid, places=2)

    def test_04_conspicuous_consumption_and_prestige(self):
        """Verify luxury consumption awards prestige, upgrades status tiers, and decays naturally."""
        region = MockRegion()
        lord = Agent(101)
        lord.is_lord = True
        lord.prestige_score = 0.0
        lord.inv_add(Goods.foreign_luxuries, 3)
        region.agents.append(lord)

        # Initial tier: Provincial Gentry
        self.assertEqual(ConspicuousConsumptionManager.get_status_tier(lord.prestige_score), PrestigeTier.PROVINCIAL)

        # Step 1: Consumes 1 foreign luxury (base rating 25.0)
        rep1 = ConspicuousConsumptionManager.consume_luxuries_for_agent(lord, region, t=1)
        self.assertEqual(lord.inv_get(Goods.foreign_luxuries, 0), 2)
        self.assertGreater(lord.prestige_score, 20.0)
        self.assertEqual(lord.status_tier, PrestigeTier.BURGHER)

        # Step 2: Consumes 2nd luxury -> upgrades to Lord of the Manor (40+)
        rep2 = ConspicuousConsumptionManager.consume_luxuries_for_agent(lord, region, t=2)
        self.assertEqual(lord.inv_get(Goods.foreign_luxuries, 0), 1)
        self.assertGreaterEqual(lord.prestige_score, 40.0)
        self.assertEqual(lord.status_tier, PrestigeTier.LORD_OF_MANOR)

        # Step 3: Run out of luxuries -> natural status decay
        lord.inv_add(Goods.foreign_luxuries, -1)  # empty inventory
        prev_score = lord.prestige_score
        rep3 = ConspicuousConsumptionManager.consume_luxuries_for_agent(lord, region, t=3)
        self.assertLess(lord.prestige_score, prev_score, "Status decays when luxuries are exhausted")

    def test_05_planner_autonomous_voyage_dispatch(self):
        """Verify EliteCapitalistPlanner charters oceanic voyages when cloth and capital are abundant."""
        region = MockRegion()
        trade_mgr = TradeTriangleManager()
        region.trade_manager = trade_mgr

        commoner = Agent(1)
        region.agents.append(commoner)

        elite = Agent(50)
        elite.cash = 100.0
        elite.inv_add(Goods.cloth, 10)
        region.agents.append(elite)

        planner = EliteCapitalistPlanner()
        res = planner.plan_and_execute_elite(elite, region, t=5)

        self.assertEqual(res['action_taken'], 'CHARTER_MERCHANT_VOYAGE')
        self.assertEqual(len(trade_mgr.active_voyages), 1)

    def test_06_hud_inspector_and_interactive_charter(self):
        """Verify Cadastre Panel Card 4 renders trade info, prestige, and responds to click charters."""
        region = MockRegion()
        trade_mgr = TradeTriangleManager()
        region.trade_manager = trade_mgr

        lord = Agent(99)
        lord.is_lord = True
        lord.cash = 80.0
        lord.inv_add(Goods.cloth, 5)
        lord.prestige_score = 45.0
        lord.status_tier = PrestigeTier.LORD_OF_MANOR
        region.agents.append(lord)

        world = {
            'turn': 2,
            'window': 20,
            'selected_region': region,
            'cadastre_subtab': 'finance',
            'scenario_state': {
                'trade_manager_ref': trade_mgr,
            }
        }

        # 1. Render Cadastre Panel
        draw_cadastre_panel(self.surface, world, region, self.font, self.font_small)

        # 2. Check interactive Charter button rendered
        charter_btn = next((b for b in _CADASTRE_BUTTONS if b[1] == 'cadastre_charter_voyage'), None)
        self.assertIsNotNone(charter_btn, "Charter voyage button should be present in Card 4")

        # 3. Simulate click on button
        rect, act, payload = charter_btn
        center_x = rect[0] + rect[2] // 2
        center_y = rect[1] + rect[3] // 2
        hit_ok = cadastre_panel_hit((center_x, center_y), world)
        self.assertTrue(hit_ok)
        self.assertEqual(len(trade_mgr.active_voyages), 1, "Clicking button should launch voyage")

        # 4. Verify TRG badge on world map
        draw_activity_badges(self.surface, region, cx=400, cy=400, font_small=self.font_small)


if __name__ == '__main__':
    unittest.main()

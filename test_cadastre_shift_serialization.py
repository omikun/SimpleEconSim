"""
test_cadastre_shift_serialization.py — Verification Suite for:
1. Recalibrated Enclosure Charter Fees ($25 instead of $500).
2. Granular Shift Length Regulation (+/- 2 hours) and Class Faction Dynamics.
3. Money Conservation in Provincial Equalization Grants.
4. Estate Cadastre & Plot Inspector UI hit targets.
5. Headless SimServer Serialization Payload (JSON-serializable).
"""

import unittest
import json
from region import Region
from agent import Agent
from nation import Nation
from land_tenure import TenureStatus, LandPlot, TileTenure
from enclosure import calculate_charter_fee, execute_enclosure, CHARTER_FEE_PER_TENTH
from labor_politics import adjust_workday_hours
from worldview_ui import panel_tab_hit, CADASTRE_TAB_RECT, CHARTS_TAB_RECT, CITIZENS_TAB_RECT
from worldview_cadastre import cadastre_panel_hit
from sim_server import SimServer, CommandType
from sim_server.protocol import CommandMessage


class TestCadastreShiftSerialization(unittest.TestCase):

    def test_01_enclosure_fee_recalibration(self):
        """Verify enclosure fee is recalibrated to $5 per tenth ($25 for 0.5 plot)."""
        self.assertEqual(CHARTER_FEE_PER_TENTH, 5.0)

        plot = LandPlot("plot_half", "TestTile", 1, 0.5, TenureStatus.FEUDAL)
        fee = calculate_charter_fee(plot)
        self.assertAlmostEqual(fee, 25.0)

        # A lord with only $50 can easily afford $25 without being bankrupted
        tile = Region("EstateTile", 0, 0)
        nation = Nation("Monarchy", initial_cash=500.0)
        nation.add_tile(tile)

        lord = Agent(1)
        lord.is_lord = True
        lord.cash = 60.0
        tile.agents.append(lord)

        plot.lord_id = lord.id
        tile.tenure = TileTenure(plots=[plot])
        gov_cash_before = tile.gov.agent.cash

        ok, msg, evs = execute_enclosure(tile, plot.plot_id, t=1)
        self.assertTrue(ok)
        self.assertAlmostEqual(lord.cash, 35.0)  # 60 - 25 = 35
        self.assertAlmostEqual(tile.gov.agent.cash - gov_cash_before, 25.0)  # Conserved transfer to Crown

    def test_02_shift_length_adjustments_and_ten_hour_act(self):
        """Verify +/- 2h shift adjustments, clamping, and Ten-Hour Act flag toggling."""
        nation = Nation("IndustrialistEmpire")
        tile1 = Region("MillTile1", 0, 0)
        tile2 = Region("MillTile2", 0, 1)
        nation.add_tile(tile1)
        nation.add_tile(tile2)

        # Baseline shift cap is 12.0h
        nation.max_workday_hours = 12.0
        tile1.max_workday_hours = 12.0
        tile2.max_workday_hours = 12.0

        # 1. Reduce shift by -2h (12.0 -> 10.0)
        ok, msg = adjust_workday_hours(nation, -2.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nation.max_workday_hours, 10.0)
        self.assertAlmostEqual(tile1.max_workday_hours, 10.0)
        self.assertTrue(nation.ten_hour_act)
        self.assertTrue(tile1.ten_hour_act)
        self.assertIn("Ten-Hour Act achieved", msg)

        # 2. Reduce shift by another -2h (10.0 -> 8.0)
        ok, msg = adjust_workday_hours(nation, -2.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nation.max_workday_hours, 8.0)
        self.assertTrue(nation.ten_hour_act)

        # 3. Clamping at minimum (8.0h)
        ok, msg = adjust_workday_hours(nation, -2.0)
        self.assertFalse(ok)
        self.assertIn("minimum", msg)
        self.assertAlmostEqual(nation.max_workday_hours, 8.0)

        # 4. Expand shift by +2h (8.0 -> 10.0)
        ok, msg = adjust_workday_hours(nation, +2.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nation.max_workday_hours, 10.0)
        self.assertTrue(nation.ten_hour_act)

        # 5. Expand shift past 10h (10.0 -> 12.0): deactivates Ten-Hour Act
        ok, msg = adjust_workday_hours(nation, +2.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nation.max_workday_hours, 12.0)
        self.assertFalse(nation.ten_hour_act)
        self.assertFalse(tile1.ten_hour_act)

        # 6. Expand to 16.0h max
        adjust_workday_hours(nation, +2.0) # 14.0
        adjust_workday_hours(nation, +2.0) # 16.0
        self.assertAlmostEqual(nation.max_workday_hours, 16.0)

        # Clamping at maximum (16.0h)
        ok, msg = adjust_workday_hours(nation, +2.0)
        self.assertFalse(ok)
        self.assertIn("maximum", msg)

    def test_03_provincial_equalization_grant_money_conservation(self):
        """Verify prov_equalization_grant strictly deducts from treasury and rejects without funds."""
        from worldview_policies import _execute_policy_action

        class MockProvince:
            def __init__(self, name, cash):
                self.name = name
                self.tiles = []
                self.gov = type('Gov', (), {'agent': type('Agent', (), {'cash': cash})()})()

        # Case A: Insolvent province ($50 < $200)
        prov_poor = MockProvince("PoorProv", 50.0)
        tile_a = Region("TileA", 0, 0)
        tile_b = Region("TileB", 0, 1)
        prov_poor.tiles = [tile_a, tile_b]
        tile_a_cash_before = tile_a.gov.agent.cash

        world = {'turn': 1, 'policy_feedback': None}
        _execute_policy_action(world, 'prov_equalization_grant', prov_poor)
        self.assertIn("Insufficient", world['policy_feedback'][0])
        self.assertAlmostEqual(prov_poor.gov.agent.cash, 50.0)  # No money spent
        self.assertAlmostEqual(tile_a.gov.agent.cash, tile_a_cash_before)  # No money created

        # Case B: Solvent province ($300 >= $200)
        prov_rich = MockProvince("RichProv", 300.0)
        tile_c = Region("TileC", 0, 2)
        tile_d = Region("TileD", 0, 3)
        prov_rich.tiles = [tile_c, tile_d]
        tile_cash_before = tile_c.gov.agent.cash + tile_d.gov.agent.cash

        _execute_policy_action(world, 'prov_equalization_grant', prov_rich)
        self.assertIn("Disbursed $200 grant", world['policy_feedback'][0])
        self.assertAlmostEqual(prov_rich.gov.agent.cash, 100.0)  # 300 - 200 = 100
        # Poorest tile received exactly $200
        tile_cash_after = tile_c.gov.agent.cash + tile_d.gov.agent.cash
        self.assertAlmostEqual(tile_cash_after - tile_cash_before, 200.0)
        # Total money in system strictly conserved: delta province + delta tiles = 0
        self.assertAlmostEqual((prov_rich.gov.agent.cash - 300.0) + (tile_cash_after - tile_cash_before), 0.0)

    def test_04_cadastre_tab_hit_and_panel_actions(self):
        """Verify cadastre tab hit detection and panel actions dispatch."""
        # 1. Tab hit detection
        tab_hit = panel_tab_hit((CADASTRE_TAB_RECT[0] + 5, CADASTRE_TAB_RECT[1] + 5))
        self.assertEqual(tab_hit, 'cadastre')

        charts_hit = panel_tab_hit((CHARTS_TAB_RECT[0] + 5, CHARTS_TAB_RECT[1] + 5))
        self.assertEqual(charts_hit, 'charts')

        cit_hit = panel_tab_hit((CITIZENS_TAB_RECT[0] + 5, CITIZENS_TAB_RECT[1] + 5))
        self.assertEqual(cit_hit, 'citizens')

        # 2. Cadastre action hit (toggle pasture)
        tile = Region("CadastreTile", 0, 0)
        plot = LandPlot("p1", tile.name, 1, 0.5, TenureStatus.ENCLOSED, production_type='arable')
        plot.name = "St. Jude's Common Strip"
        tile.tenure = TileTenure(plots=[plot])

        world = {'turn': 1, 'policy_feedback': None, 'cadastre_scroll': 0}
        # Simulate button hit payload
        from worldview_cadastre import _CADASTRE_BUTTONS
        _CADASTRE_BUTTONS.append(((100, 100, 50, 20), 'cadastre_toggle_pasture', (tile, plot.plot_id)))

        hit = cadastre_panel_hit((110, 110), world)
        self.assertTrue(hit)
        self.assertEqual(plot.production_type, 'pasture')
        self.assertIn("PASTURE", world['policy_feedback'][0])

    def test_05_sim_server_serialization_payload(self):
        """Verify SimServer serialize_world produces valid JSON-serializable payloads."""
        server = SimServer(seed=4242, terrain_seed=4242, nation_seed=1234)

        # Verify command dispatch GET_STATE
        cmd = CommandMessage(cmd_type=CommandType.GET_STATE)
        res = server.execute_command(cmd)
        self.assertTrue(res['success'])
        self.assertIn('world', res)

        world_data = res['world']
        self.assertIn('tiles', world_data)
        self.assertIn('nations', world_data)
        self.assertGreater(len(world_data['tiles']), 0)

        # Check tile data fields
        first_tile = world_data['tiles'][0]
        self.assertIn('name', first_tile)
        self.assertIn('tenure', first_tile)
        self.assertIn('plots', first_tile['tenure'])
        self.assertIn('workhouse', first_tile)
        self.assertIn('labor', first_tile)

        # Verify plots have authentic names and production types
        if first_tile['tenure']['plots']:
            p0 = first_tile['tenure']['plots'][0]
            self.assertIn('name', p0)
            self.assertIn('production_type', p0)
            self.assertIn('fraction', p0)
            self.assertIn('tenure', p0)

        # Test single tile query
        cmd_tile = CommandMessage(cmd_type=CommandType.GET_STATE, payload={'tile': first_tile['name']})
        res_tile = server.execute_command(cmd_tile)
        self.assertTrue(res_tile['success'])
        self.assertEqual(res_tile['tile']['name'], first_tile['name'])

        # Verify 100% JSON serializability
        serialized_json = json.dumps(world_data)
        self.assertIsInstance(serialized_json, str)
        self.assertGreater(len(serialized_json), 1000)


if __name__ == '__main__':
    unittest.main()

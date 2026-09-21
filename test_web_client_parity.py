import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage, CommandType


class TestWebClientParity(unittest.TestCase):
    def setUp(self):
        import random
        random.seed(4242)
        import diplomacy
        from diplomacy import DiplomacySystem
        diplomacy.diplomacy_instance = DiplomacySystem()
        import innovation
        from innovation import InnovationSystem
        innovation._INNOVATION_SYSTEM = InnovationSystem()
        self.sim = SimServer(seed=4242, terrain_seed=4242, nation_seed=4242)

    def test_macro_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('macro', w)
        macro = w['macro']
        self.assertIn('treasury_cash', macro)
        self.assertIn('population', macro)
        self.assertIn('gdp', macro)
        self.assertIn('unrest_energy', macro)
        self.assertIn('unrest_stage', macro)
        self.assertIn('gini', macro)
        self.assertIn('cost_of_living', macro)
        self.assertIn('trade_balance', macro)
        self.assertIn('tax_rate', macro)
        self.assertIn('tariff_rate', macro)
        self.assertIn('credit_rating', macro)

    def test_history_series(self):
        # Step a few turns
        for _ in range(3):
            self.sim.step()
        w = self.sim.serialize_world()
        self.assertIn('history', w)
        hist = w['history']
        self.assertGreaterEqual(len(hist['turns']), 3)
        self.assertEqual(len(hist['turns']), len(hist['treasury']))
        self.assertEqual(len(hist['turns']), len(hist['gdp']))

    def test_tile_deep_inspection(self):
        inhabited = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) is not None][0]
        data = self.sim.serialize_tile(inhabited, turn=self.sim.turn)
        self.assertIn('market_prices', data)
        self.assertIn('stockpiles', data)
        self.assertIn('buildings', data)
        self.assertIn('construction_projects', data)
        self.assertIn('ecology', data)
        self.assertIn('citizens', data)
        self.assertGreater(len(data['citizens']), 0)
        c0 = data['citizens'][0]
        self.assertIn('id', c0)
        self.assertIn('career', c0)
        self.assertIn('cash', c0)

    def test_build_command(self):
        p_nat = self.sim.player_nation_name
        tile = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) and t.owner_nation.name == p_nat][0]
        res = self.sim.execute_command(CommandMessage(CommandType.BUILD_PROJECT, {
            'tile': tile.name, 'building': 'granary'
        }))
        self.assertTrue(res['success'], res)

    def test_policy_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.SET_POLICY, {
            'key': 'tax_rate', 'val': 0.25
        }))
        self.assertTrue(res['success'], res)
        p_nat = self.sim.player_nation_name
        nation = next(n for n in self.sim.nations if n.name == p_nat)
        self.assertEqual(nation.tax_rate, 0.25)

    def test_diplomacy_command(self):
        p_nat = self.sim.player_nation_name
        other = next(n.name for n in self.sim.nations if n.name != p_nat)
        res = self.sim.execute_command(CommandMessage(CommandType.DIPLOMATIC_ACTION, {
            'action': 'propose_trade', 'target': other
        }))
        self.assertTrue(res['success'], res)

    def test_bond_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.SOVEREIGN_BOND, {
            'action': 'issue_bond', 'amount': 1000, 'duration': 50
        }))
        self.assertTrue(res['success'], res)

    def test_science_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.RESEARCH_TECH, {
            'action': 'pledge_prize', 'tech_id': 'crop_rotation', 'amount': 300
        }))
        self.assertTrue(res['success'], res)

    def test_recruit_command(self):
        p_nat = self.sim.player_nation_name
        tile = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) and t.owner_nation.name == p_nat][0]
        res = self.sim.execute_command(CommandMessage(CommandType.RECRUIT_UNIT, {
            'tile': tile.name, 'soldiers': 10
        }))
        self.assertTrue(res['success'], res)

    def test_select_nation_command(self):
        target = self.sim.nations[1].name
        res = self.sim.execute_command(CommandMessage(CommandType.SELECT_NATION, {
            'nation': target
        }))
        self.assertTrue(res['success'], res)
        self.assertEqual(self.sim.player_nation_name, target)


    def test_charts_and_comparison_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('comparison_suite', w)
        cs = w['comparison_suite']
        self.assertIn('tab1_macro', cs)
        self.assertIn('tab2_goods', cs)
        self.assertIn('tab3_forex', cs)
        self.assertIn('tab4_extraction', cs)
        self.assertIn('tab5_protest', cs)
        self.assertIn('tab6_ecology', cs)

        # Verify tile chart series
        inhabited = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) is not None][0]
        data = self.sim.serialize_tile(inhabited, turn=self.sim.turn)
        self.assertIn('charts', data)
        charts = data['charts']
        self.assertIn('economic', charts)
        self.assertIn('ecological', charts)
        self.assertIn('labor', charts)
        self.assertIn('citizens', charts)

    def test_cadastre_actions(self):
        tile = [t for t in self.sim.tiles if getattr(t, 'tenure', None) and t.tenure.plots][0]
        plot = tile.tenure.plots[0]

        # Toggle land use
        res = self.sim.execute_command(CommandMessage(CommandType.CADASTRE_TOGGLE_LAND_USE, {
            'tile': tile.name, 'plot_id': plot.plot_id, 'production_type': 'pasture'
        }))
        self.assertTrue(res['success'], res)

        # Restore commons
        res = self.sim.execute_command(CommandMessage(CommandType.RESTORE_COMMONS, {
            'tile': tile.name, 'plot_id': plot.plot_id
        }))
        self.assertTrue(res['success'], res)

    def test_province_decree_command(self):
        prov = self.sim.nations[0].provinces[0]
        prov.gov.agent.cash = 500.0
        res = self.sim.execute_command(CommandMessage(CommandType.PROVINCE_DECREE, {
            'province': prov.name, 'decree': 'standardize_routes'
        }))
        self.assertTrue(res['success'], res)

    def test_labor_and_border_policies(self):
        res1 = self.sim.execute_command(CommandMessage(CommandType.SET_BORDER_POLICY, {
            'open_borders': False
        }))
        self.assertTrue(res1['success'], res1)

        res2 = self.sim.execute_command(CommandMessage(CommandType.SET_FACTORY_SAFETY, {
            'enabled': True
        }))
        self.assertTrue(res2['success'], res2)

        res3 = self.sim.execute_command(CommandMessage(CommandType.SET_TRUCK_ACT, {
            'enabled': True
        }))
        self.assertTrue(res3['success'], res3)


    def test_comparison_suite_drilldowns(self):
        w = self.sim.serialize_world()
        self.assertIn('comparison_suite', w)
        cs = w['comparison_suite']
        self.assertIn('tab1_macro', cs)
        self.assertIn('tab2_goods', cs)
        self.assertIn('tab3_forex', cs)
        self.assertIn('tab4_extraction', cs)
        self.assertIn('tab5_protest', cs)
        self.assertIn('tab6_ecology', cs)

        for tab_key in ['tab1_macro', 'tab2_goods', 'tab4_extraction', 'tab5_protest', 'tab6_ecology']:
            self.assertIn('by_country', cs[tab_key])
            self.assertIn('by_province', cs[tab_key])
            self.assertIn('by_tile', cs[tab_key])
            self.assertGreater(len(cs[tab_key]['by_country']), 0)
            self.assertGreater(len(cs[tab_key]['by_province']), 0)
            self.assertGreater(len(cs[tab_key]['by_tile']), 0)

        # Tab 3 FX Matrix & Banking
        self.assertIn('banking', cs['tab3_forex'])
        self.assertIn('fx_matrix', cs['tab3_forex'])
        self.assertGreater(len(cs['tab3_forex']['banking']), 0)
        self.assertGreater(len(cs['tab3_forex']['fx_matrix']), 0)


if __name__ == '__main__':
    unittest.main()


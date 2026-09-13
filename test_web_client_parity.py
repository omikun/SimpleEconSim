import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage, CommandType


class TestWebClientParity(unittest.TestCase):
    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()

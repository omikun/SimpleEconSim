"""Focused behavior checks for the authored labor and border rivalry slice."""

import unittest

from goods import Goods
import forex as fx
from scenario_labor_frontier_rivalry import DISTRICTS, create_world, step_world


class LaborFrontierRivalryTest(unittest.TestCase):
    def test_world_has_four_inhabited_districts(self):
        world = create_world(seed=612)
        self.assertEqual([tile.name for tile in world["tiles"]], list(DISTRICTS))
        self.assertEqual([len(nation.tiles) for nation in world["nations"]], [2, 2])
        self.assertTrue(all(tile.agents and tile.owner_nation for tile in world["tiles"]))
        self.assertTrue(all(nation.currency == "Frontier Crown" for nation in world["nations"]))
        self.assertTrue(any(a.is_corporation and a.output == Goods.cloth
                            for a in world["tiles"][0].agents))

    def test_one_world_turn_uses_single_engine_tick(self):
        world = create_world(seed=613)
        people_before = {agent.id for tile in world['tiles'] for agent in tile.agents
                         if not agent.is_corporation and not agent.is_government}
        cash_before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        violations = step_world(world)
        self.assertEqual(world["turn"], 1)
        self.assertEqual(violations, [])
        self.assertTrue(all(tile._last_turn == 1 for tile in world["tiles"]))
        self.assertEqual(people_before, {agent.id for tile in world['tiles'] for agent in tile.agents
                                         if not agent.is_corporation and not agent.is_government})
        self.assertAlmostEqual(cash_before, world['currency_totals'][world['currencies'][0]], places=4)

    def test_desktop_and_server_use_authored_world(self):
        from client.desktop.engine import build_world_view
        from sim_server.sim_server import SimServer
        desktop = build_world_view(seed=614, scenario_id='labor_frontier_rivalry')
        server = SimServer(seed=614, scenario_id='labor_frontier_rivalry')
        self.assertEqual([tile.name for tile in desktop['tiles']], list(DISTRICTS))
        self.assertEqual([tile.name for tile in server.tiles], list(DISTRICTS))
        server.step()
        self.assertEqual(server.turn, 1)
        self.assertTrue(all(tile._last_turn == 1 for tile in server.tiles))


if __name__ == "__main__":
    unittest.main()

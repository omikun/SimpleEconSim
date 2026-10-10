"""Focused behavior checks for the authored labor and border rivalry slice."""

import unittest

from goods import Goods
import forex as fx
from labor_frontier_market import settle_markets, start_machinery_project
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

    def test_funded_cloth_orders_choose_available_lower_price(self):
        world = create_world(seed=615)
        player_firm = next(a for a in world['tiles'][0].agents
                           if a.is_corporation and a.output == Goods.cloth)
        rival_firm = next(a for a in world['tiles'][3].agents
                          if a.is_corporation and a.output == Goods.cloth)
        player_firm.wage = 3.5
        rival_firm.wage = 1.5
        player_firm.inv_add(Goods.cloth, 20)
        rival_firm.inv_add(Goods.cloth, 20)
        cash_before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        sales = settle_markets(world, 1)
        player_market = [row for row in sales if row['market'] == 'Meridian Works']
        self.assertTrue(player_market)
        self.assertTrue(all(row['seller_nation'] == 'Vesper' for row in player_market))
        self.assertAlmostEqual(cash_before,
                               fx.audit_currency_total(world['tiles'], world['currencies'][0]))
        self.assertGreater(world['scenario_state']['market_summary']['Vesper']['public_tax'], 0)

        world = create_world(seed=615)
        player_firm = next(a for a in world['tiles'][0].agents
                           if a.is_corporation and a.output == Goods.cloth)
        player_firm.inv_add(Goods.cloth, 20)
        sales = settle_markets(world, 1)
        self.assertTrue(sales)
        self.assertTrue(all(row['seller_nation'] == 'Meridian' for row in sales))
        self.assertEqual(world['scenario_state']['market_summary']['Vesper']['sales_receipts'], 0)

    def test_machinery_project_pays_people_and_consumes_inputs(self):
        world = create_world(seed=616)
        firm = next(a for a in world['tiles'][0].agents
                    if a.is_corporation and a.output == Goods.cloth)
        before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        ok, _ = start_machinery_project(world, 'Meridian', 0)
        self.assertTrue(ok)
        self.assertAlmostEqual(before,
                               fx.audit_currency_total(world['tiles'], world['currencies'][0]))
        self.assertEqual(firm.inv_get(Goods.iron, 0), 2)
        settle_markets(world, 1)
        self.assertEqual(firm.machinery_level, 1)
        settle_markets(world, 2)
        self.assertEqual(firm.machinery_level, 2)
        self.assertEqual(firm.inv_get(Goods.iron, 0), 0)
        self.assertEqual(world['scenario_state']['machinery_projects'][0]['status'], 'complete')


if __name__ == "__main__":
    unittest.main()

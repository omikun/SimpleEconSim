"""Focused behavior checks for the authored labor and border rivalry slice."""

import unittest

from goods import Goods
import forex as fx
from labor_frontier_market import settle_markets, start_machinery_project
from labor_frontier_labor import apply_action
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

    def test_petition_closes_only_named_rights_after_paid_patrol_and_repeals(self):
        world = create_world(seed=612)
        step_world(world)
        record = world['scenario_state']['restrictions']['Meridian']
        self.assertEqual(record['status'], 'proposed')
        border = world['tiles'][1]
        initial_rights = sum(right.usable_share > 0 for rights in border.access_rights.values()
                             for right in rights if right.resource == 'commons_food')
        ok, _ = apply_action(world, 'approve_petition')
        self.assertTrue(ok)
        self.assertFalse(apply_action(world, 'protect_access')[0])
        self.assertEqual(initial_rights, sum(right.usable_share > 0
                                              for rights in border.access_rights.values()
                                              for right in rights if right.resource == 'commons_food'))
        step_world(world)
        self.assertEqual(record['status'], 'active')
        self.assertEqual(record['last_patrol_paid_turn'], 2)
        self.assertEqual(0, sum(right.usable_share > 0 for rights in border.access_rights.values()
                                for right in rights if right.resource == 'commons_food'))
        self.assertTrue(apply_action(world, 'protect_access')[0])
        self.assertEqual(initial_rights, sum(right.usable_share > 0
                                              for rights in border.access_rights.values()
                                              for right in rights if right.resource == 'commons_food'))
        self.assertEqual(border.police_employed, 0)

    def test_protective_choices_use_real_owner_public_and_food_reserves(self):
        world = create_world(seed=617)
        nation = world['nations'][0]
        firm = next(a for a in world['tiles'][0].agents
                    if a.is_corporation and a.output == Goods.cloth)
        owner_cash, public_cash = firm.owner.cash, nation.government.agent.cash
        ok, _ = apply_action(world, 'cofund_machinery')
        self.assertTrue(ok)
        self.assertEqual(firm.owner.cash, owner_cash - 30)
        self.assertEqual(nation.government.agent.cash, public_cash - 15)
        self.assertFalse(apply_action(world, 'release_relief')[0])
        step_world(world)
        food_before = nation.government.food_inventory
        self.assertTrue(apply_action(world, 'release_relief')[0])
        self.assertEqual(nation.government.food_inventory, food_before - 6)

    def test_coercion_and_protection_change_labor_and_paid_orders(self):
        results = {}
        for choice in ('approve_petition', 'protect_access'):
            world = create_world(seed=612)
            step_world(world)
            self.assertTrue(apply_action(world, choice)[0])
            for _ in range(5):
                step_world(world)
            border = world['tiles'][1]
            estate = next(a for a in border.agents
                          if a.is_corporation and a.output == Goods.cotton)
            results[choice] = (len(estate.employees),
                               world['scenario_state']['market_summary']['Meridian']['units_sold'],
                               sum(right.usable_share > 0 for rights in border.access_rights.values()
                                   for right in rights if right.resource == 'commons_food'))
        self.assertGreater(results['approve_petition'][0], results['protect_access'][0])
        self.assertGreater(results['approve_petition'][1], results['protect_access'][1])
        self.assertLess(results['approve_petition'][2], results['protect_access'][2])

    def test_protected_machinery_path_regains_orders(self):
        world = create_world(seed=612)
        step_world(world)
        self.assertTrue(apply_action(world, 'protect_access')[0])
        step_world(world)
        self.assertTrue(apply_action(world, 'cofund_machinery')[0])
        step_world(world)
        step_world(world)
        self.assertGreater(world['scenario_state']['market_summary']['Meridian']['units_sold'], 0)
        self.assertEqual(world['scenario_state']['restrictions']['Meridian']['status'], 'rejected')
        self.assertEqual(world['scenario_state']['machinery_projects'][0]['status'], 'complete')

    def test_enlisted_pay_food_and_desertion_keep_person_ids(self):
        from army import step_armies
        world = create_world(seed=618)
        nation, border = world['nations'][0], world['tiles'][1]
        unit = nation.military_units[0]
        original_ids = {a.id for tile in world['tiles'] for a in tile.agents}
        soldier_cash = {a.id: a.cash for a in border.agents if a.id in unit.person_ids}
        food_before = nation.government.food_inventory
        events = step_armies(world['tiles'], world['nations'], 1)
        self.assertEqual(nation.government.food_inventory, food_before - 4)
        self.assertTrue(all(a.cash == soldier_cash[a.id] + 2 for a in border.agents
                            if a.id in unit.person_ids))
        self.assertTrue(any(event['event'] == 'ARMY_UPKEEP' for event in events))
        nation.government.agent.cash = 0
        nation.government.food_inventory = 0
        for turn in range(2, 8):
            step_armies(world['tiles'], world['nations'], turn)
        self.assertEqual(original_ids, {a.id for tile in world['tiles'] for a in tile.agents})
        self.assertTrue(any(a.military_unit_id is None for a in border.agents
                            if a.id in soldier_cash))

    def test_battle_casualties_pass_through_probate(self):
        from army import resolve_battle, settle_battle_casualties
        world = create_world(seed=619)
        player_unit = world['nations'][0].military_units[0]
        rival_unit = world['nations'][1].military_units[0]
        cash_before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        battle = resolve_battle([player_unit], [rival_unit])
        lost_ids = set(player_unit.casualty_ids + rival_unit.casualty_ids)
        self.assertEqual(len(lost_ids), battle['atk_losses'] + battle['def_losses'])
        self.assertEqual(set(settle_battle_casualties(
            [player_unit, rival_unit], world['tiles'], world['nations'], 1)), lost_ids)
        self.assertTrue(lost_ids.isdisjoint({a.id for tile in world['tiles'] for a in tile.agents}))
        self.assertAlmostEqual(cash_before,
                               fx.audit_currency_total(world['tiles'], world['currencies'][0]))

    def test_adjacent_unit_move_carries_the_same_people_and_assets(self):
        from intents import MoveArmyIntent
        world = create_world(seed=620)
        nation = world['nations'][0]
        unit = nation.military_units[0]
        border, capital = world['tiles'][1], world['tiles'][0]
        selected = list(unit.person_ids)
        cash_before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        ok, _ = MoveArmyIntent(nation.name, unit.unit_id, border.name,
                               capital.name).execute(world['by_name'],
                                                     {n.name: n for n in world['nations']}, 1)
        self.assertTrue(ok)
        self.assertEqual(unit.region_name, capital.name)
        self.assertTrue(set(selected).issubset({a.id for a in capital.agents}))
        self.assertTrue(set(selected).isdisjoint({a.id for a in border.agents}))
        self.assertAlmostEqual(cash_before,
                               fx.audit_currency_total(world['tiles'], world['currencies'][0]))


if __name__ == "__main__":
    unittest.main()

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

    def test_border_attack_requires_declaration_and_paid_local_force(self):
        from army import recruit_unit
        from labor_frontier_rivalry import apply_border_action
        world = create_world(seed=621)
        player, rival = world['nations']
        self.assertFalse(apply_border_action(world, 'attack_border', player.name, 0)[0])
        self.assertIsNotNone(recruit_unit(player, world['tiles'][1], 4, wage=2, t=0))
        original_ids = {a.id for tile in world['tiles'] for a in tile.agents}
        cash_before = fx.audit_currency_total(world['tiles'], world['currencies'][0])
        self.assertTrue(apply_border_action(world, 'declare_border_war', player.name, 0)[0])
        self.assertFalse(apply_border_action(world, 'attack_border', player.name, 0)[0])
        ok, message = apply_border_action(world, 'attack_border', player.name, 1)
        self.assertTrue(ok, message)
        self.assertIs(world['tiles'][2].owner_nation, player)
        self.assertFalse(rival.military_units)
        surviving_ids = {a.id for tile in world['tiles'] for a in tile.agents}
        self.assertTrue(surviving_ids.issubset(original_ids))
        self.assertAlmostEqual(cash_before,
                               fx.audit_currency_total(world['tiles'], world['currencies'][0]))

    def test_standstill_and_rival_restraint_have_a_visible_reason(self):
        from labor_frontier_rivalry import apply_border_action
        world = create_world(seed=622)
        self.assertTrue(apply_border_action(world, 'propose_standstill', 'Meridian', 0)[0])
        self.assertFalse(apply_border_action(world, 'declare_border_war', 'Meridian', 0)[0])
        step_world(world)
        self.assertIn(world['scenario_state']['rival_plan']['goal'],
                      ('hold', 'invest', 'approve_petition', 'protect_access'))
        self.assertTrue(world['scenario_state']['rival_plan']['reason'])

    def test_rival_announces_mobilization_before_war(self):
        from army import recruit_unit
        from labor_frontier_rivalry import advance_rival
        from diplomacy import get_diplomacy
        world = create_world(seed=623)
        rival = world['nations'][1]
        self.assertIsNotNone(recruit_unit(rival, world['tiles'][2], 4, wage=2, t=0))
        advance_rival(world, 1)
        self.assertEqual(world['scenario_state']['rival_plan']['goal'], 'mobilize')
        self.assertFalse(get_diplomacy().are_at_war('Meridian', 'Vesper'))
        advance_rival(world, 2)
        self.assertTrue(get_diplomacy().are_at_war('Meridian', 'Vesper'))
        self.assertEqual(world['scenario_state']['war_declared_turn'], 2)

    def test_captured_cotton_pays_new_sovereign_only_when_sold(self):
        from army import recruit_unit
        from labor_frontier_rivalry import apply_border_action
        world = create_world(seed=624)
        player = world['nations'][0]
        self.assertIsNotNone(recruit_unit(player, world['tiles'][1], 4, wage=2, t=0))
        self.assertTrue(apply_border_action(world, 'declare_border_war', 'Meridian', 0)[0])
        self.assertTrue(apply_border_action(world, 'attack_border', 'Meridian', 1)[0])
        for grower in world['tiles'][1].agents:
            if grower.output == Goods.cotton:
                grower.inv_add(Goods.cotton, -grower.inv_get(Goods.cotton, 0))
        cash_before = player.government.agent.cash
        settle_markets(world, 2)
        captured_sales = [row for row in world['scenario_state']['cotton_purchases']
                          if row['origin'] == 'Vesper Fields']
        self.assertTrue(captured_sales)
        self.assertTrue(all(row['tax_nation'] == 'Meridian' for row in captured_sales))
        self.assertGreater(player.government.agent.cash, cash_before)

    def test_clients_share_projection_actions_and_server_budget(self):
        from client.desktop.panels.scenario_ui import scenario_pressures
        from labor_frontier_projection import project
        from sim_server.sim_server import SimServer
        from sim_server.protocol import CommandMessage, CommandType
        desktop = create_world(seed=625)
        self.assertEqual(scenario_pressures(desktop), project(desktop)['pressures'])
        server = SimServer(seed=625, scenario_id='labor_frontier_rivalry')
        info = server._collect_scenario_info()
        self.assertEqual([card['title'] for card in info['pressures']],
                         ['Livelihoods', 'Economic position', 'Border power'])
        self.assertEqual({a['id'] for a in info['actions']},
                         {a['id'] for a in project(desktop)['actions']})
        first = server.execute_command(CommandMessage(
            CommandType.SCENARIO_ACTION, {'action_id': 'release_relief'}))
        self.assertTrue(first['success'], first)
        second = server.execute_command(CommandMessage(
            CommandType.SCENARIO_ACTION, {'action_id': 'cofund_machinery'}))
        self.assertFalse(second['success'])
        bypass = server.execute_command(CommandMessage(
            CommandType.RECRUIT_UNIT, {'tile': 'Meridian Fields', 'soldiers': 50}))
        self.assertFalse(bypass['success'])


if __name__ == "__main__":
    unittest.main()

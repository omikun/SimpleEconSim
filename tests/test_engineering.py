"""Behavioral contracts for operation-driven and resource-funded engineering."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import tempfile

from goods import Goods
from tile_resources import TileResource
from innovation import InnovationSystem, TECH_CATALOG
from buildings import BUILDING_RECIPES, Building
from engineering import (quote_recipe, refinement_rates, production_work_share,
                         record_operation, deliver_engineering)


class Actor(SimpleNamespace):
    def inv_get(self, good, default=0):
        return self.stock.get(good, default)

    def inv_add(self, good, delta):
        self.stock[good] = self.inv_get(good, 0) + delta


def engineering_nation(name='Test', cash=5000):
    people = [Actor(id=i, cash=100.0, stock={g: 100 for g in Goods}, wage=2,
                    output=Goods.furniture, alive=True, employer=None)
              for i in range(1, 7)]
    tile = SimpleNamespace(name=name + '_Capital', agents=people, natural_resources=list(TileResource),
                           recipes={g: {'price': 1.0} for g in Goods},
                           buildings=[Building('engineering_workshop', BUILDING_RECIPES['engineering_workshop'], 0, name)],
                           production_log={}, resources={r: 1 for r in TileResource})
    nation = SimpleNamespace(name=name, tiles=[tile], currency='USD',
                             government=SimpleNamespace(name=name + '_Treasury',
                                                        agent=Actor(id=999, cash=float(cash), stock={})))
    tile.owner_nation = nation
    return nation


def grant(system, nation, tid='steam_engines', xp=1):
    system.get_discovered_techs(nation.name).update({tid, *TECH_CATALOG[tid].required_techs})
    for prerequisite in TECH_CATALOG[tid].required_techs:
        system.tech_refinement_xp.setdefault(nation.name, {})[prerequisite] = 60.0
    system.tech_refinement_xp.setdefault(nation.name, {})[tid] = xp
    system.get_guild_blockade(nation, tid)['active'] = False


def operation(system, nation, turn, work=1, capacity=1, generation=1):
    tile = nation.tiles[0]
    tile._technology_usage_turn = turn
    tile.technology_usage = {'engine': {'tech_id': 'steam_engines', 'generation': generation,
                                       'work': work, 'capacity': capacity,
                                       'owner_ids': [1], 'cause_event_ids': []}}


class EngineeringTests(TestCase):
    def setUp(self):
        self.system = InnovationSystem()
        self.nation = engineering_nation()
        grant(self.system, self.nation)

    def test_idle_blueprint_and_unfunded_mode_produce_no_refinement(self):
        for turn in range(1, 80):
            self.system.step_refinement([self.nation], turn)
        self.assertEqual(self.system.get_refinement_xp(self.nation.name, 'steam_engines'), 1)
        self.assertEqual(self.system.get_commercial_maturity(self.nation.name, 'steam_engines'), 0)

    def test_sustained_operation_reaches_next_tier_and_intensity_matters(self):
        for turn in range(1, 40):
            operation(self.system, self.nation, turn)
            self.system.step_refinement([self.nation], turn)
        self.assertGreaterEqual(self.system.get_tech_tier(self.nation.name, 'steam_engines'), 2)
        low = refinement_rates(installations=1, utilization=0.1)
        high = refinement_rates(installations=1, utilization=1)
        self.assertAlmostEqual(high['capability'], 10 * low['capability'])
        scale = refinement_rates(installations=10, utilization=1)
        self.assertGreater(scale['capability'], high['capability'])
        self.assertLess(scale['capability'], 10 * high['capability'])

    def test_operation_attribution_requires_installed_design(self):
        tile = self.nation.tiles[0]
        recipe = quote_recipe(self.nation, BUILDING_RECIPES['steam_engines_prototype'], self.system)
        building = Building(recipe.name, recipe, 0, tile.name)
        tile.buildings.append(building)
        record_operation(tile, tile.agents[0], Goods.gov, 2, 2, 1)
        self.assertEqual(tile.technology_usage, {})
        record_operation(tile, tile.agents[0], Goods.furniture, 2, 4, 1)
        row = next(iter(tile.technology_usage.values()))
        self.assertEqual((row['work'], row['capacity']), (2, 4))

    def test_funded_experiments_conserve_cash_consume_goods_and_reserve_work(self):
        nation, tile = self.nation, self.nation.tiles[0]
        self.system.set_engineering_program(nation, 'steam_engines', 100, 'performance', t=0)
        total = nation.government.agent.cash + sum(a.cash for a in tile.agents)
        stocks = {g: sum(a.inv_get(g) for a in tile.agents) for g in Goods}
        self.system.prepare_region_engineering(nation, tile, 1)
        delivery = tile.engineering_deliveries['steam_engines']
        self.assertEqual(delivery['public_effort'], 3)
        self.assertGreater(delivery['public_spent'], 0)
        self.assertAlmostEqual(total, nation.government.agent.cash + sum(a.cash for a in tile.agents))
        self.assertEqual(stocks[Goods.coal] - sum(a.inv_get(Goods.coal) for a in tile.agents), 3)
        self.assertEqual(sum(production_work_share(a, 1) for a in tile.agents), 1.5)
        self.assertEqual(sum(production_work_share(a, 2) for a in tile.agents), 0)
        self.system.step_refinement([nation], 1)
        self.assertGreater(self.system.get_refinement_xp(nation.name, 'steam_engines'), 1)
        before = nation.government.agent.cash
        self.system.prepare_region_engineering(nation, tile, 1)
        self.assertEqual(nation.government.agent.cash, before)

    def test_no_supplies_or_no_workshop_means_no_spend_and_no_progress(self):
        for no_workshop in (True, False):
            nation = engineering_nation('Empty')
            tile = nation.tiles[0]
            system = InnovationSystem()
            grant(system, nation)
            system.set_engineering_program(nation, 'steam_engines', 100, 'performance')
            if no_workshop:
                tile.buildings.clear()
            else:
                for actor in tile.agents:
                    actor.stock.clear()
            system.prepare_region_engineering(nation, tile, 1)
            system.step_refinement([nation], 1)
            self.assertEqual(nation.government.agent.cash, 5000)
            self.assertEqual(system.get_refinement_xp(nation.name, 'steam_engines'), 1)
            self.assertTrue(system.engineering_status(nation, 'steam_engines', 1)['constraint'])

    def test_no_double_booking_across_technologies(self):
        tile = self.nation.tiles[0]
        # Enough workshops, only one skilled person.
        tile.agents = tile.agents[:1]
        tile.buildings *= 3
        payer = self.nation.government.agent
        first = deliver_engineering(tile, self.nation, TECH_CATALOG['steam_engines'], payer, 100, 1)
        second = deliver_engineering(tile, self.nation, TECH_CATALOG['coal_coking'], payer, 100, 1)
        self.assertEqual(first['effort'], 1)
        self.assertEqual(second['effort'], 0)

    def test_private_engineering_requires_recent_use_and_real_money(self):
        tile = self.nation.tiles[0]
        self.system.prepare_region_engineering(self.nation, tile, 1)
        self.assertEqual(tile.engineering_deliveries, {})
        operation(self.system, self.nation, 1)
        tile.agents[0].cash = 1000
        before = sum(a.cash for a in tile.agents)
        self.system.prepare_region_engineering(self.nation, tile, 2)
        self.assertGreater(tile.engineering_deliveries['steam_engines']['private_effort'], 0)
        self.assertAlmostEqual(before, sum(a.cash for a in tile.agents))

    def test_budget_is_a_ceiling_and_spending_is_capacity_limited(self):
        self.system.set_engineering_program(self.nation, 'steam_engines', 100, 'performance')
        status = self.system.engineering_status(self.nation, 'steam_engines', 0)
        self.assertLess(status['expected_spend'], 100)
        self.assertGreater(status['expected_spend'], 0)
        self.assertIn('limit', status['constraint'])
        self.nation.government.agent.cash = 1
        self.system.prepare_region_engineering(self.nation, self.nation.tiles[0], 1)
        self.assertEqual(self.nation.government.agent.cash, 1)

    def test_capability_and_cost_objectives_diverge(self):
        performance = refinement_rates(public_effort=3, objective='performance')
        economy = refinement_rates(public_effort=3, objective='economy')
        self.assertGreater(performance['capability'], economy['capability'])
        self.assertGreater(economy['maturity'], performance['maturity'])

    def test_new_generation_inherits_only_part_of_maturity_and_existing_equipment_stays(self):
        n, s = self.nation, self.system
        s.tech_commercial_maturity = {n.name: {'steam_engines': {1: 80}}}
        recipe = quote_recipe(n, BUILDING_RECIPES['steam_engines_prototype'], s)
        old = Building(recipe.name, recipe, 0, n.tiles[0].name)
        old_bonus = old.production_bonuses
        s.tech_refinement_xp[n.name]['steam_engines'] = 60
        self.assertAlmostEqual(s.get_commercial_maturity(n.name, 'steam_engines', 3), 80 * 0.35 ** 2)
        new_recipe = quote_recipe(n, BUILDING_RECIPES['steam_engines_prototype'], s)
        self.assertGreater(new_recipe.cost, recipe.cost)
        self.assertEqual(old.technology_designs['steam_engines'], 1)
        self.assertEqual(old.production_bonuses, old_bonus)

    def test_prerequisite_cap_never_erases_existing_knowledge(self):
        s, n = self.system, self.nation
        s.tech_refinement_xp[n.name]['coal_coking'] = 1
        s.tech_refinement_xp[n.name]['steam_engines'] = 58.9
        operation(s, n, 1)
        s.step_refinement([n], 1)
        self.assertEqual(s.get_refinement_xp(n.name, 'steam_engines'), 59)
        s.tech_refinement_xp[n.name]['steam_engines'] = 75
        operation(s, n, 2)
        s.step_refinement([n], 2)
        self.assertEqual(s.get_refinement_xp(n.name, 'steam_engines'), 75)

    def test_forecast_is_read_only_and_uses_the_delivered_effort_rule(self):
        s, n = self.system, self.nation
        s.set_engineering_program(n, 'steam_engines', 25, 'performance')
        before = deepcopy(s.__dict__)
        status = s.engineering_status(n, 'steam_engines', 0)
        self.assertEqual(before, s.__dict__)
        s.prepare_region_engineering(n, n.tiles[0], 1)
        s.step_refinement([n], 1)
        self.assertAlmostEqual(s.get_refinement_xp(n.name, 'steam_engines') - 1,
                               status['rates']['capability'])
        self.assertIsNone(status['forecast']['capability_turns_without_program'])

    def test_program_stops_at_milestone_and_idle_knowledge_does_not_spend(self):
        s, n = self.system, self.nation
        s.tech_refinement_xp[n.name]['steam_engines'] = 24
        s.set_engineering_program(n, 'steam_engines', 25, 'performance')
        s.prepare_region_engineering(n, n.tiles[0], 1)
        s.step_refinement([n], 1)
        self.assertEqual(s.get_engineering_program(n.name, 'steam_engines')['status'], 'completed')
        cash = n.government.agent.cash
        s.prepare_region_engineering(n, n.tiles[0], 2)
        self.assertEqual(n.government.agent.cash, cash)

    def test_balanced_program_finishes_cost_target_on_its_original_design(self):
        s, n = self.system, self.nation
        s.tech_refinement_xp[n.name]['steam_engines'] = 24
        s.set_engineering_program(n, 'steam_engines', 25, 'balanced')
        for turn in range(1, 14):
            s.prepare_region_engineering(n, n.tiles[0], turn)
            s.step_refinement([n], turn)
        self.assertGreaterEqual(s.get_tech_tier(n.name, 'steam_engines'), 2)
        self.assertGreaterEqual(s.get_commercial_maturity(n.name, 'steam_engines', 1), 20)
        self.assertEqual(s.get_engineering_program(n.name, 'steam_engines')['status'], 'completed')

    def test_imported_stocks_can_support_a_prototype_without_domestic_geology(self):
        s, n = self.system, self.nation
        s.get_discovered_techs(n.name).remove('steam_engines')
        s.tech_refinement_xp[n.name].pop('steam_engines')
        n.tiles[0].natural_resources = []
        s.set_engineering_program(n, 'steam_engines', 25, 'performance')
        s.prepare_region_engineering(n, n.tiles[0], 1)
        s.step_refinement([n], 1)
        self.assertGreater(s.engineering_discovery[n.name]['steam_engines'], 0)

    def test_staff_expertise_increases_real_effort_not_announced_budget(self):
        n, s = self.nation, self.system
        for actor in n.tiles[0].agents:
            actor.engineering_skill = 2
        s.set_engineering_program(n, 'steam_engines', 100, 'performance')
        forecast = s.engineering_status(n, 'steam_engines', 0)
        s.prepare_region_engineering(n, n.tiles[0], 1)
        delivery = n.tiles[0].engineering_deliveries['steam_engines']
        self.assertEqual(delivery['public_effort'], 6)
        self.assertEqual(delivery['public_spent'], forecast['expected_spend'])
        s.step_refinement([n], 1)
        self.assertAlmostEqual(s.get_refinement_xp(n.name, 'steam_engines') - 1,
                               forecast['rates']['capability'])

    def test_public_experiments_can_invent_without_commercial_operation(self):
        s, n = self.system, self.nation
        s.discovered_techs[n.name].remove('steam_engines')
        s.tech_refinement_xp[n.name].pop('steam_engines')
        s.set_engineering_program(n, 'steam_engines', 100, 'performance')
        for turn in range(1, 14):
            s.prepare_region_engineering(n, n.tiles[0], turn)
            s.step_refinement([n], turn)
        self.assertTrue(s.has_tech(n.name, 'steam_engines'))
        self.assertEqual(s.get_refinement_xp(n.name, 'steam_engines'), 1)

    def test_invalid_programs_leave_state_untouched(self):
        before = deepcopy(self.system.__dict__)
        for budget, objective, host in ((float('nan'), 'balanced', None), (-1, 'balanced', None),
                                        (25, 'magic', None), (25, 'balanced', 'Enemy')):
            ok, _ = self.system.set_engineering_program(self.nation, 'steam_engines', budget, objective, host)
            self.assertFalse(ok)
        self.assertEqual(before, self.system.__dict__)

    def test_delivered_work_has_replayable_trace_and_explicit_payees(self):
        from run_trace import RunTrace
        from innovation_trace import replay_formula
        n, s = self.nation, self.system
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'engineering.ctr', 'engineering')
            tile = n.tiles[0]
            tile._run_trace = trace
            tile._collective_trace_clock = {'turn': 1, 'phase': 'production', 'next': 1}
            s.set_engineering_program(n, 'steam_engines', 100, 'balanced')
            s.prepare_region_engineering(n, tile, 1)
            s.step_refinement([n], 1)
            rows = list(trace.recent)
            payments = [r for r in rows if r['kind'] == 'engineering_wage_payment']
            self.assertEqual(len(payments), 3)
            self.assertTrue(all(p['inputs']['transfer_contract']['payee_account']['id'] for p in payments))
            for row in rows:
                if row.get('formula_id') in ('innovation.refinement_xp.v1', 'engineering.maturity.v1'):
                    self.assertAlmostEqual(replay_formula(row['formula_id'], row['inputs']), row['value_after'])
            self.assertTrue(any(r['kind'] == 'engineering_work_delivered' for r in rows))


class EngineeringConstructionTests(TestCase):
    def test_real_construction_and_retrofit_conserve_cash_and_preserve_design_versions(self):
        from nation import Nation
        from region import Region
        from intents import BuildIntent
        n = Nation('Engineering', initial_cash=10000)
        tile = Region('Workshop', 0, 0)
        n.add_tile(tile)
        tile.natural_resources = list(TileResource)
        n.government.agent.cash = 10000
        for a in tile.agents:
            for g in (Goods.wood, Goods.furniture, Goods.iron, Goods.coal):
                a.inv_add(g, 100)
        s = InnovationSystem()
        grant(s, n)
        with patch('innovation._INNOVATION_SYSTEM', s):
            intent = BuildIntent(n.name, tile.name, 'steam_engines_prototype')
            ok, msg = intent.execute({tile.name: tile}, {n.name: n}, 0)
            self.assertTrue(ok, msg)
            s.tech_refinement_xp[n.name]['steam_engines'] = 90
            actors = {id(a): a for a in [*tile.agents, n.government.agent]}
            before = sum(a.cash for a in actors.values())
            stocks = sum(a.inv_get(Goods.coal) for a in tile.agents)
            for t in range(1, 12):
                if intent.project.step(t):
                    break
            self.assertEqual(intent.project.status, 'completed')
            self.assertAlmostEqual(sum(a.cash for a in actors.values()), before)
            self.assertLess(sum(a.inv_get(Goods.coal) for a in tile.agents), stocks)
            target = tile.buildings[-1]
            self.assertEqual(target.technology_designs['steam_engines'], 1)
            count = len(tile.buildings)
            ok, msg = s.commission_retrofit(n, 'steam_engines', tile.name, count - 1, t=12)
            self.assertTrue(ok, msg)
            self.assertEqual(target.production_bonuses, {})
            retrofit = tile.construction_projects[-1]
            for t in range(13, 26):
                if retrofit.step(t):
                    break
            self.assertEqual(retrofit.status, 'completed')
            self.assertEqual(len(tile.buildings), count)
            self.assertEqual(target.technology_designs['steam_engines'], 4)
            self.assertTrue(target.production_bonuses)
            self.assertFalse(s.commission_retrofit(n, 'steam_engines', tile.name, count - 1, t=26)[0])


class EngineeringDesktopTests(TestCase):
    def test_detail_controls_scroll_and_fund_the_displayed_program(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        import pygame
        import ui_icons
        from client.desktop.panels.science_panel import draw_science_panel, science_panel_hit
        from ui_targets import clear_targets
        icon_cache_before = dict(ui_icons._ICON_CACHE)
        pygame.init()
        try:
            surface = pygame.Surface((1400, 900))
            font, small = pygame.font.Font(None, 24), pygame.font.Font(None, 16)
            n, s = engineering_nation(), InnovationSystem()
            grant(s, n)
            world = {'nations': [n], 'player_nation_name': n.name, 'turn': 0,
                     'science_panel_open': True, 'innovation_era': 3,
                     'science_detail_tech': 'steam_engines'}
            def draw():
                clear_targets(world)
                draw_science_panel(surface, world, font, small)
            def click(action):
                draw()
                target = next((target for target in world['_ui_targets']
                               if target.action == ('science_btn', 'sci_eng_' + action)), None)
                self.assertIsNotNone(target, action)
                self.assertTrue(science_panel_hit(target.rect.center, world))
            with patch('innovation._INNOVATION_SYSTEM', s):
                draw()
                click('budget')
                self.assertEqual(world['engineering_drafts'][n.name, 'steam_engines']['budget'], 50)
                for _ in range(8):
                    draw()
                    if any(target.action == ('science_btn', 'sci_eng_apply') for target in world['_ui_targets']):
                        break
                    click('down')
                click('apply')
                self.assertEqual(s.get_engineering_program(n.name, 'steam_engines')['budget'], 50)
                self.assertEqual(s.get_engineering_program(n.name, 'steam_engines')['objective'], 'performance')
                world['engineering_detail_scroll'] = 0
                draw()
                pygame.image.save(surface, '/private/tmp/engineering-desktop-drawer.png')
        finally:
            ui_icons._ICON_CACHE.clear()
            ui_icons._ICON_CACHE.update(icon_cache_before)
            pygame.quit()

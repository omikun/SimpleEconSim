"""Behavioral coverage for slow soil loss and installed sector productivity."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from agent import Agent, seed_traits
from buildings import Building, BUILDING_RECIPES
from engineering import quote_recipe
from externalities import step_tile_externalities
from goods import Goods
from innovation import InnovationSystem, TECH_CATALOG, TechDomain
from productivity_technologies import PRODUCTION_GOODS
from region import Region
from region_production import produce_corporation, terrain_bonus
from soil_dynamics import soil_change
from tests.test_engineering import engineering_nation, grant


class SoilTimingTests(TestCase):
    def test_negative_net_balance_is_ten_times_slower_and_recovery_is_preserved(self):
        self.assertAlmostEqual(soil_change(.27, .05), (.05 - .27) / 10)
        self.assertAlmostEqual(soil_change(.003, .05), .05 - .003)
        self.assertEqual(soil_change(.05, .05), 0)

    def test_live_soil_transition_and_both_trace_versions_replay(self):
        from economic_replay import replay
        from tests.test_fertilizer_supply_and_blockade import MemoryTrace
        region = Region('Soil test', 0, 0)
        region.agents = [SimpleNamespace(output=Goods.food, is_corporation=False,
            employer=None, alive=True, is_government=False) for _ in range(10)] + [
            SimpleNamespace(output=Goods.food, is_corporation=True,
            employer=None, alive=True) for _ in range(20)]
        trace = MemoryTrace()
        region._run_trace = trace
        region._collective_trace_clock = {'turn': 1, 'phase': 'ecology', 'next': 1}
        region.soil_fertility = 1
        step_tile_externalities(region, 1)
        self.assertAlmostEqual(region.soil_fertility, .978)
        row = next(r for r in trace.rows if r['kind'] == 'soil_fertility_update')
        event = {**row, 'value_before': row['before']}
        self.assertAlmostEqual(replay(event), row['after'])
        old = {**event, 'formula_id': 'ecology.soil_balance.v1'}
        self.assertAlmostEqual(replay(old), .78)


class ProductivityExpansionTests(TestCase):
    def test_every_domestic_production_profession_has_specific_technology(self):
        region = Region('Catalog coverage', 0, 0)
        general = {'steam_engines', 'dynamo_electrification', 'microelectronics'}
        for good, recipe in region.recipes.items():
            if good in (Goods.gov, Goods.none) or recipe.get('import_only') or recipe.get('production', 0) <= 0:
                continue
            with self.subTest(profession=good.name):
                self.assertTrue(any(good.value in t.production_modifiers
                    for tid, t in TECH_CATALOG.items() if tid not in general))
        self.assertNotIn(Goods.furniture.value, TECH_CATALOG['mechanized_looms'].production_modifiers)
        self.assertIn(Goods.iron.value, TECH_CATALOG['coal_coking'].production_modifiers)

    def test_catalog_prerequisites_are_acyclic_and_all_pilots_exist(self):
        visited, active = set(), set()
        def visit(tid):
            self.assertNotIn(tid, active, tid)
            if tid in visited:
                return
            active.add(tid)
            for prerequisite in TECH_CATALOG[tid].required_techs:
                self.assertIn(prerequisite, TECH_CATALOG)
                visit(prerequisite)
            active.remove(tid)
            visited.add(tid)
        for tid in TECH_CATALOG:
            visit(tid)
            self.assertIn(tid + '_prototype', BUILDING_RECIPES)

    def test_steam_only_improves_compatible_owner_machinery(self):
        region = Region('Steam applications', 0, 0)
        system, nation = InnovationSystem(), engineering_nation()
        grant(system, nation)
        recipe = quote_recipe(nation, BUILDING_RECIPES['steam_engines_prototype'], system)
        installation = Building(recipe.name, recipe, 0, region.name)
        firm = Agent(0)
        seed_traits(firm)
        firm.is_corporation = True
        firm.wage = 2
        firm.employees = [Agent(0) for _ in range(6)]
        region.agents.append(firm)
        region._last_turn = 1
        installation.private_owner_id = firm.id
        for good in PRODUCTION_GOODS:
            if region.recipes[good].get('import_only'):
                continue
            with self.subTest(good=good.name):
                firm.output = good
                region.buildings = [installation]
                if good != Goods.furniture:
                    self.assertEqual(terrain_bonus(region, good, producer=firm),
                                     terrain_bonus(region, good, producer=firm.employees[0]))
                    continue
                production = {**region.recipes[good], 'production': 4,
                    'numInput': 0, 'maxinv': 1000, 'maxtotalprod': 1000000}
                firm.inv_set(good, 0)
                region.buildings = []
                with patch('region_production.rand.random_n', return_value=[0] * 6):
                    produce_corporation(region, firm, production, good, {good: 1}, {}, turn=1)
                ordinary = firm.inv_get(good, 0)
                firm.inv_set(good, 0)
                region.buildings = [installation]
                with patch('region_production.rand.random_n', return_value=[0] * 6):
                    produce_corporation(region, firm, production, good, {good: 1}, {}, turn=1)
                self.assertGreater(firm.inv_get(good, 0), ordinary)
                self.assertGreater(terrain_bonus(region, good, producer=firm),
                                   terrain_bonus(region, good, producer=firm.employees[0]))

    def test_legacy_steam_installation_is_limited_to_compatible_application(self):
        nation, system = engineering_nation(), InnovationSystem()
        grant(system, nation)
        from copy import copy
        recipe = copy(quote_recipe(nation, BUILDING_RECIPES['steam_engines_prototype'], system))
        recipe.production_bonuses = {Goods.furniture: 1.5}
        old = Building(recipe.name, recipe, 0, nation.tiles[0].name)
        self.assertNotIn(Goods.food, old.production_bonuses)
        self.assertNotIn(Goods.coal, old.production_bonuses)

    def test_specialized_production_generates_research_experience(self):
        nation = engineering_nation()
        nation.provinces = []
        tile = nation.tiles[0]
        tile.export_vol, tile.military_units = {}, []
        tile.gov = SimpleNamespace()
        for good, domain in ((Goods.cotton, TechDomain.AGRONOMY),
                             (Goods.wool, TechDomain.AGRONOMY),
                             (Goods.porcelain, TechDomain.MANUFACTURING),
                             (Goods.rum, TechDomain.MANUFACTURING),
                             (Goods.iron_ore, TechDomain.MANUFACTURING),
                             (Goods.transport, TechDomain.CIVIL_ENGINEERING)):
            with self.subTest(good=good.name):
                system = InnovationSystem()
                tile.production_log = {good: [100]}
                system.accumulate_learning_by_doing([tile], [nation], 1)
                self.assertGreater(system.get_domain_xp(nation.name, domain), 0)

"""Funded project lifecycle, conserved wages, and map-state checks."""

import unittest

import pygame

from scenario_projects import (advance, cancel_project, damage_project,
                               draw_map_overlay, effectiveness, get_project,
                               record_food_results, repair_project, start_project)
from scenario_egypt_1877 import apply_action
from worldview_engine import build_world_view


class StrategicProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.egypt = next(nation for nation in self.world['nations'] if nation.name == 'Egypt')

    def _egypt_cash(self):
        return (float(self.egypt.government.agent.cash)
                + sum(float(agent.cash) for tile in self.egypt.tiles for agent in tile.agents))

    def test_local_wages_progress_upkeep_damage_and_repair(self):
        before = self._egypt_cash()
        ok, _ = start_project(self.world, 'nile_repair', 'Nile Delta')
        self.assertTrue(ok)
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        project = get_project(self.world, 'nile_repair', 'Nile Delta')
        self.assertEqual(project['progress'], 0)
        self.assertEqual(len(project['worker_ids']), 3)
        self.assertFalse(start_project(self.world, 'nile_repair', 'Nile Delta')[0])
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        self.assertEqual(project['status'], 'operating')
        self.assertGreater(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        self.assertEqual(project['progress'], 2)
        advance(self.world)
        self.assertEqual(project['progress'], 2)
        self.assertTrue(damage_project(self.world, 'nile_repair', 'Nile Delta', .7))
        self.assertEqual(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)
        self.assertTrue(repair_project(self.world, 'nile_repair', 'Nile Delta')[0])
        self.world['turn'] = 4
        advance(self.world)
        self.assertEqual(project['status'], 'operating')
        self.assertAlmostEqual(self._egypt_cash(), before, places=4)
        self.assertTrue(cancel_project(self.world, 'nile_repair', 'Nile Delta')[0])
        self.assertEqual(effectiveness(self.world, 'nile_repair', 'Nile Delta'), 0)

    def test_occupation_stops_work_and_overlay_supports_both_modes(self):
        ok, _ = start_project(self.world, 'revenue_office', 'Alexandria')
        self.assertTrue(ok)
        project = get_project(self.world, 'revenue_office', 'Alexandria')
        self.world['scenario_state']['campaign']['territorial_control']['Alexandria'] = 'Britain'
        self.world['turn'] = 2
        advance(self.world)
        self.assertEqual(project['status'], 'occupied')
        self.assertEqual(project['progress'], 0)
        surface = pygame.Surface((1400, 900))
        for mode in ('guided', 'advanced'):
            self.world['ui_mode'] = mode
            draw_map_overlay(surface, self.world)
        self.world['scenario_state']['campaign']['territorial_control'].clear()
        self.world['turn'] = 3
        advance(self.world)
        self.assertEqual(project['progress'], 1)

    def test_nile_action_changes_real_food_yield_and_preserves_action_budget(self):
        from goods import Goods
        from region_production import terrain_bonus

        tile = next(tile for tile in self.egypt.tiles
                    if getattr(tile, 'scenario_location', None) == 'Nile Delta')
        baseline = terrain_bonus(tile, Goods.food, 4)
        cash_before = self.egypt.government.agent.cash
        ok, _ = apply_action(self.world, 'repair_delta_channels')
        self.assertTrue(ok)
        self.assertEqual(cash_before - self.egypt.government.agent.cash, 45.0)
        self.assertFalse(apply_action(self.world, 'release_maize')[0])
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        improved = terrain_bonus(tile, Goods.food, 4)
        self.assertAlmostEqual(improved / baseline, 1.8, places=3)
        record_food_results(self.world)
        report = self.world['scenario_state']['strategic_projects']['food_reports'][-1]
        self.assertEqual(report['site'], 'Nile Delta')
        self.assertIn('private_reserved', report)
        self.assertIn('underfed', report)

    def test_revenue_office_moves_real_receipts_after_caisse_claim(self):
        from scenario_debt import outstanding, set_collection_assignment

        tile = next(tile for tile in self.egypt.tiles
                    if getattr(tile, 'scenario_location', None) == 'Alexandria')
        ok, message = apply_action(self.world, 'build_revenue_office')
        self.assertTrue(ok, message)
        for turn in (2, 3, 4):
            self.world['turn'] = turn
            advance(self.world)
        office = get_project(self.world, 'revenue_office', 'Alexandria')
        self.assertEqual(office['status'], 'operating')
        self.world['turn'] = 5
        central_before = self.egypt.government.agent.cash
        local_before = tile.gov.agent.cash
        tile.gov.collect_tax(5, 10)
        self.assertAlmostEqual(tile.gov.agent.cash - local_before, 6)
        self.assertAlmostEqual(self.egypt.government.agent.cash - central_before, 4)
        report = self.world['scenario_state']['strategic_projects']['revenue_reports'][-1]
        self.assertEqual(report['source'], 'tax')
        self.assertEqual(report['payer'], 'Egyptian taxpayers')
        self.assertIn(tile.name, report['districts'])
        self.assertAlmostEqual(report['central_transfer'] + report['local_retained'], 10)
        advance(self.world)
        self.assertEqual(self.world['scenario_state']['strategic_projects']['fiscal_challenge']['status'],
                         'pending')
        ok, message = apply_action(self.world, 'publish_revenue_accounts')
        self.assertTrue(ok, message)
        self.assertEqual(self.world['scenario_state']['strategic_projects']['fiscal_challenge']['status'],
                         'published')
        self.assertGreater(outstanding(self.world), 0)

        set_collection_assignment(self.world, 10, 'caisse_consent')
        self.world['turn'] = 6
        central_before = self.egypt.government.agent.cash
        local_before = tile.gov.agent.cash
        debt_before = outstanding(self.world)
        tile.gov.collect_tax(6, 10)
        self.assertAlmostEqual(debt_before - outstanding(self.world), 2.5)
        self.assertAlmostEqual(tile.gov.agent.cash - local_before, 4.5)
        self.assertAlmostEqual(self.egypt.government.agent.cash - central_before, 3)

    def test_canal_line_uses_public_food_and_changes_a_real_battle(self):
        from scenario_campaign import _battle, _move_egypt_garrison
        from scenario_diplomacy import british_policy, mobilization_cost
        from scenario_geography import create_fleet

        food_before = self.egypt.government.food_inventory
        britain = next(nation for nation in self.world['nations'] if nation.name == 'Britain')
        britain.government.agent.cash = mobilization_cost('abstain') + 5
        self.assertEqual(british_policy(self.world, 'abstain')[0], 'intervene')
        ok, message = apply_action(self.world, 'prepare_canal_line')
        self.assertTrue(ok, message)
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        project = get_project(self.world, 'canal_line', 'Tel el Kebir')
        self.assertEqual(project['status'], 'operating')
        self.assertEqual(self.egypt.government.food_inventory, food_before - 6)
        self.assertEqual(self.world['scenario_state']['strategic_projects']['payments'][-1]['kind'],
                         'crew_food')
        self.assertEqual(effectiveness(self.world, 'canal_line', 'Tel el Kebir'), 1.0)
        self.assertEqual(british_policy(self.world, 'abstain')[0], 'withdraw')
        _move_egypt_garrison(self.world, 'Tel el Kebir')
        create_fleet(self.world, 'Britain')
        _battle(self.world, 'Tel el Kebir')
        battle = self.world['scenario_state']['campaign']['battles'][-1]
        self.assertEqual(battle['defense_project_bonus'], 55)
        self.assertAlmostEqual(project['integrity'], .65)
        self.world['scenario_state']['campaign']['territorial_control'].clear()
        ok, message = apply_action(self.world, 'repair_canal_line')
        self.assertTrue(ok, message)
        self.assertEqual(project['integrity'], 1.0)

        self.egypt.government.food_inventory = 0
        self.world['turn'] = 4
        advance(self.world)
        self.assertEqual(project['status'], 'unsupplied')
        self.assertEqual(effectiveness(self.world, 'canal_line', 'Tel el Kebir'), 0)

    def test_paid_canal_line_forces_funded_british_route(self):
        from scenario_campaign import advance_expedition, resolve_landing
        from scenario_geography import create_fleet, move_fleet

        self.assertTrue(apply_action(self.world, 'prepare_canal_line')[0])
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        britain = next(nation for nation in self.world['nations'] if nation.name == 'Britain')
        britain.government.agent.cash = 500
        create_fleet(self.world, 'Britain')
        self.assertTrue(move_fleet(self.world, 'Britain', 'Alexandria'))
        self.world['scenario_state']['naval_crisis']['stage'] = 'blockaded'
        self.world['scenario_warning_modal'] = {'kind': 'landing_warning'}
        ok, message = resolve_landing(self.world, 'defend_canal')
        self.assertTrue(ok, message)
        expedition = self.world['scenario_state']['campaign']['expedition']
        self.assertEqual(expedition['route'], 'Port Said–Ismailia–Tel el Kebir')
        for turn in (4, 5, 6, 7):
            self.world['turn'] = turn
            advance(self.world)
            advance_expedition(self.world)
        battles = self.world['scenario_state']['campaign']['battles']
        self.assertTrue(battles)
        self.assertEqual(battles[-1]['location'], 'Tel el Kebir')
        self.assertGreater(battles[-1]['defense_project_bonus'], 0)

    def test_canal_denial_makes_britain_change_approach(self):
        from scenario_campaign import resolve_landing
        from scenario_geography import close_canal, create_fleet, move_fleet

        self.assertTrue(apply_action(self.world, 'prepare_canal_line')[0])
        for turn in (2, 3):
            self.world['turn'] = turn
            advance(self.world)
        britain = next(nation for nation in self.world['nations'] if nation.name == 'Britain')
        britain.government.agent.cash = 500
        create_fleet(self.world, 'Britain')
        self.assertTrue(move_fleet(self.world, 'Britain', 'Alexandria'))
        self.assertTrue(close_canal(self.world)[0])
        self.world['scenario_state']['naval_crisis']['stage'] = 'blockaded'
        self.world['scenario_warning_modal'] = {'kind': 'landing_warning'}
        self.assertTrue(resolve_landing(self.world, 'defend_canal')[0])
        expedition = self.world['scenario_state']['campaign']['expedition']
        self.assertEqual(expedition['route'], 'Alexandria after canal denial')
        self.assertEqual(self.world['scenario_state']['campaign']['battles'][-1]['location'],
                         'Alexandria')


if __name__ == '__main__':
    unittest.main()

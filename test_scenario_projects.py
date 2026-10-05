"""Funded project lifecycle, conserved wages, and map-state checks."""

import unittest

import pygame

from scenario_projects import (advance, cancel_project, damage_project,
                               draw_map_overlay, effectiveness, get_project,
                               record_food_results, repair_project, start_project,
                               strategic_strip, project_hover_tip,
                               advance_grain_entitlement)
from scenario_egypt_1877 import apply_action, build_debrief
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

    def test_grain_entitlement_consumes_real_owner_food_and_pays_carriers(self):
        from goods import Goods

        for tile in self.egypt.tiles:
            for agent in tile.agents:
                agent.calorie_deficit_kcal = 0
        delta = next(tile for tile in self.egypt.tiles
                     if getattr(tile, 'scenario_location', '') == 'Nile Delta')
        owner = next(agent for agent in delta.agents if getattr(agent, 'is_lord', False))
        recipient = next(agent for agent in delta.agents
                         if not agent.is_government and not agent.is_corporation
                         and not agent.is_trader and not agent.is_lord)
        owner.inv_set(Goods.food, 20)
        recipient.calorie_deficit_kcal = 1000
        food_before = sum(agent.inv_get(Goods.food, 0) for tile in self.egypt.tiles
                          for agent in tile.agents)
        cash_before = self._egypt_cash()
        treasury_before = self.egypt.government.agent.cash
        self.assertTrue(apply_action(self.world, 'enact_grain_entitlement')[0])
        self.world['turn'] = 2
        advance_grain_entitlement(self.world)
        report = self.world['scenario_state']['strategic_projects']['grain_entitlement_reports'][-1]
        self.assertEqual(report['units'], 2)
        self.assertEqual(recipient.calorie_deficit_kcal, 0)
        self.assertAlmostEqual(report['transport_wages'], .1)
        self.assertAlmostEqual(self.egypt.government.agent.cash, treasury_before - .1)
        self.assertAlmostEqual(self._egypt_cash(), cash_before, places=4)
        self.assertEqual(food_before - sum(agent.inv_get(Goods.food, 0)
                                           for tile in self.egypt.tiles for agent in tile.agents), 2)
        self.assertTrue(apply_action(self.world, 'end_grain_entitlement')[0])

    def test_reserve_recall_moves_local_cash_once_and_leaves_operating_floor(self):
        from scenario_projects import reserve_recall_capacity

        local = {id(tile.gov): tile.gov for tile in self.egypt.tiles
                 if tile.gov is not self.egypt.government}
        self.assertTrue(local)
        for government in local.values():
            government.agent.cash = 70
        accounts = [self.egypt.government, *local.values()]
        cash_before = sum(government.agent.cash for government in accounts)
        capacity = reserve_recall_capacity(self.world)
        self.assertGreater(capacity, 0)
        ok, message = apply_action(self.world, 'recall_district_reserves')
        self.assertTrue(ok, message)
        report = self.world['scenario_state']['strategic_projects']['reserve_recall_reports'][-1]
        self.assertAlmostEqual(report['total'], capacity)
        self.assertAlmostEqual(sum(government.agent.cash for government in accounts), cash_before)
        self.assertTrue(all(government.agent.cash >= 20 for government in local.values()))
        self.assertEqual(reserve_recall_capacity(self.world), 0)
        self.world['turn'] = 2
        self.assertFalse(apply_action(self.world, 'recall_district_reserves')[0])

    def test_generic_revolution_cannot_silently_erase_caisse_bonds(self):
        from macro.imperialism.manager import get_imperialism_manager
        from scenario_debt import bonds, outstanding

        claim_before = outstanding(self.world)
        get_imperialism_manager().repudiate_all_imperial_obligations(
            self.egypt, 2, self.world)
        self.assertEqual(outstanding(self.world), claim_before)
        self.assertTrue(all(bond.status == 'active' for bond in bonds(self.world)))

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

    def test_guided_plan_strip_analysis_and_debrief_report_project_costs(self):
        from worldview_scenario_ui import _draw_guided_projects_analysis, MAP_RIGHT, TOP_BAR_H

        opening = strategic_strip(self.world)
        self.assertEqual([item['title'] for item in opening],
                         ['Current plan', 'Next threat', 'Recent consequence'])
        self.assertIn('No strategic project', opening[0]['text'])
        self.assertTrue(apply_action(self.world, 'repair_delta_channels')[0])
        funded = strategic_strip(self.world)
        self.assertIn('Nile Delta', funded[0]['text'])
        self.assertIn('45', ' '.join(funded[0]['details']))
        self.world['_guided_hover_tip'] = None
        surface = pygame.Surface((1400, 900))
        _draw_guided_projects_analysis(surface, self.world,
                                       mouse_pos=(MAP_RIGHT + 32, TOP_BAR_H + 96 + 109))
        self.assertEqual(self.world['_guided_hover_tip'][0], 'Food project')
        from worldview_camera import world_to_screen
        position = self.world['scenario_state']['geography']['sites']['Nile Delta']['position']
        marker = world_to_screen(self.world, *position)
        self.assertEqual(project_hover_tip(self.world, marker)[0], 'Food project')
        result = build_debrief(self.world, 'fiscal_hardship')
        self.assertIn('nile repair', result['projects'])
        self.assertTrue(any(row['label'] == 'Strategic works and labor' for row in
                            result['social_stats']))


if __name__ == '__main__':
    unittest.main()

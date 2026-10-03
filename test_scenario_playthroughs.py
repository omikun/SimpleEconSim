"""Deterministic full campaign paths for the strategic Egypt scenario."""

import unittest
import random

from scenario_campaign import resolve_landing
from scenario_egypt_1877 import SCENARIO, apply_action, finish_due_campaign
from scenario_gunboat import resolve_naval_response
from scenario_occupation import resolve_capital
from scenario_politics import resolve as resolve_politics
from scenario_situation import creditor_response_options, resolve_creditor_response
from worldview_engine import build_world_view, step_world


def play_campaign(mode):
    random.seed(1877)
    world = build_world_view(scenario_id='egypt_1877')
    state = world['scenario_state']
    if mode == 'hardship':
        # A stricter food-access objective under a prolonged, unusually low Nile.
        world['scenario']['thresholds']['protected_hunger_rate'] = .005
        egypt = next(n for n in world['nations'] if n.name == 'Egypt')
        for tile in egypt.tiles:
            tile.scenario_food_yield_modifier = .20
            tile.scenario_food_yield_modifier_until = 20
        egypt.government.food_inventory = 0
        state['public_maize_stock_units'] = 0
    seen = []
    for _ in range(70):
        if state.get('ending'):
            break
        turn = int(world['turn'])
        if mode in ('historical', 'nationalist') and state.get('last_action_turn') != turn:
            if turn == 1:
                ok, _ = apply_action(world, 'invite_representative_cabinet')
                assert ok
            elif turn == 2:
                ok, _ = apply_action(world, 'dismiss_foreign_controllers')
                assert ok
        if mode in ('peace', 'settlement', 'food_project', 'food_project_access') and turn == 1 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'repair_delta_channels' if mode.startswith('food_project')
                                       else 'prioritize_domestic_grain')
            assert ok, message
        if mode.startswith('food_project') and turn == 2 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'prioritize_domestic_grain')
            assert ok, message
        if mode == 'food_project_access' and turn == 5 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'requisition_private_grain')
            assert ok, message
        if mode == 'food_project_access' and turn == 7 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'release_maize')
            assert ok, message
        if mode == 'hardship' and turn == 1 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'reduce_fellahin_tax')
            assert ok, message
        if mode in ('extraction', 'breakdown') and state.get('last_action_turn') != turn:
            if turn == 1:
                ok, _ = apply_action(world, 'raise_local_taxes')
                assert ok
            elif mode == 'breakdown' and state.get('extraction_level', 0) > 0:
                ok, message = apply_action(world, 'intensify_requisitions')
                assert ok, (turn, message)
        if (mode in ('joint', 'french_brokered', 'opposition')
                and state.get('last_action_turn') != turn
                and state.get('naval_crisis', {}).get('stage') == 'mobilizing'
                and not state.get('diplomatic_crisis', {}).get('egyptian_proposal')):
            offer = {'joint': 'offer_joint_guarantee',
                     'french_brokered': 'request_french_mediation',
                     'opposition': 'seek_french_opposition'}[mode]
            ok, message = apply_action(world, offer)
            assert ok, (turn, message)
        if mode == 'unresolved' and turn == 18 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'revoke_oversight')
            assert ok, message
        if not world.get('scenario_warning_modal'):
            step_world(world)
        warning = world.get('scenario_warning_modal')
        if warning:
            kind = warning['kind']
            seen.append((int(world['turn']), kind))
            if kind == 'debt_due':
                if mode.startswith('food_project'):
                    egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
                    cash = float(egypt.government.agent.cash)
                    due = float(state['scheduled_remittance'])
                    answer = ('pay_remittance' if cash >= due else
                              'concede_revenue' if cash >= due * .5 else
                              'defer_remittance')
                else:
                    answer = ('concede_revenue' if mode in ('settlement', 'unresolved') and int(world['turn']) == 6 else
                              'pay_remittance' if mode in ('peace', 'extraction', 'breakdown', 'hardship')
                              else 'default_remittance')
                ok, message = apply_action(world, answer)
            elif kind == 'creditor_reaction':
                branch = warning['action_id']
                answer = ('defend_controller_dismissal' if branch == 'dismiss_foreign_controllers'
                          else ('accept_customs_control' if mode == 'control' else 'contest_customs_claim')
                          if branch == 'default_remittance'
                          else next(item['id'] for item in creditor_response_options(world, branch)
                                    if item['enabled']))
                ok, message = resolve_creditor_response(world, answer)
            elif kind in ('naval_ultimatum', 'naval_blockade'):
                answer = ('naval_disarm' if mode == 'disarm' else
                          'naval_seek_mediation' if mode == 'mediation' else
                          'naval_accept_control' if mode == 'imposed' else
                          'naval_defend') if kind == 'naval_ultimatum' else 'naval_hold'
                ok, message = resolve_naval_response(world, answer)
            elif kind in ('french_terms', 'joint_guarantee_terms'):
                from scenario_diplomacy import resolve_terms
                ok, message = resolve_terms(world, 'accept')
            elif kind == 'landing_warning':
                ok, message = resolve_landing(world,
                    'defend_canal' if mode in ('canal', 'nationalist') else 'evacuate_port')
            elif kind == 'capital_warning':
                ok, message = resolve_capital(world, 'defend_cairo' if mode == 'stalled' else 'evacuate_cairo')
            elif kind in ('dynastic_crisis', 'officer_movement'):
                ok, message = resolve_politics(world,
                    'accept_tawfiq' if kind == 'dynastic_crisis' else 'support_urabi')
            elif kind == 'breakdown':
                import pygame
                from ui_targets import clear_targets
                from worldview_scenario_ui import draw_scenario_warning_modal, scenario_warning_modal_hit
                pygame.font.init()
                clear_targets(world)
                draw_scenario_warning_modal(pygame.Surface((1400, 900)), world)
                target = next(target for target in world['_ui_targets']
                              if target.action == ('scenario_warning', 'accept_breakdown'))
                scenario_warning_modal_hit(target.rect.center, world)
                ok, message = True, 'Accepted government breakdown.'
            else:
                raise AssertionError(f'Unexpected scenario modal {warning}')
            assert ok, message
            world['scenario_warning_modal'] = None
            finish_due_campaign(world)
    return world, seen


class ScenarioPlaythroughTests(unittest.TestCase):
    def test_food_repair_reaches_harvest_and_forces_a_debt_tradeoff(self):
        world, _ = play_campaign('food_project')
        state = world['scenario_state']
        project = state['strategic_projects']['projects'][0]
        reports = state['strategic_projects']['food_reports']
        self.assertEqual(project['id'], 'nile_repair:Nile Delta')
        self.assertTrue(any(row['yield_applied'] and row['yield_factor'] > 1
                            and row['food_produced'] > 0 for row in reports))
        self.assertTrue(any(row['private_reserved'] > 0 for row in reports))
        self.assertTrue(any(entry['action'] in ('concede_revenue', 'defer_remittance')
                            for entry in state['actions_taken']))
        self.assertTrue(state['ending'])

    def test_payment_path_completes_without_war(self):
        world, seen = play_campaign('peace')
        state = world['scenario_state']
        self.assertTrue(state['ending'])
        self.assertEqual(state['payment_status'], 'paid')
        self.assertFalse(state['campaign']['battles'])
        self.assertFalse(any(kind == 'naval_ultimatum' for _, kind in seen))

    def test_historical_spine_is_reachable_from_player_decisions(self):
        world, seen = play_campaign('historical')
        state = world['scenario_state']
        kinds = [kind for _, kind in seen]
        for required in ('dynastic_crisis', 'debt_due', 'naval_ultimatum',
                         'landing_warning', 'capital_warning', 'officer_movement'):
            self.assertIn(required, kinds)
        self.assertLess(kinds.index('dynastic_crisis'), kinds.index('officer_movement'))
        self.assertLess(kinds.index('officer_movement'), kinds.index('naval_ultimatum'))
        self.assertEqual(state['politics']['ruler'], 'Tawfiq Pasha')
        self.assertEqual(state['politics']['governing_coalition'], 'nationalist')
        self.assertEqual(state['ending'], 'occupation')
        self.assertEqual(state['occupation']['institutional_control']['cabinet'], 'Britain')
        self.assertTrue(any(entry['kind'] == 'historical_parallel' for entry in state['historical_log']))

    def test_canal_defense_can_block_capital_capture(self):
        world, seen = play_campaign('canal')
        state = world['scenario_state']
        self.assertTrue(state['ending'])
        self.assertIn('landing_warning', [kind for _, kind in seen])
        self.assertTrue(any(battle['location'] == 'Tel el Kebir' for battle in state['campaign']['battles']))
        self.assertNotEqual(state['campaign']['territorial_control'].get('Cairo'), 'Britain')
        self.assertEqual(state['ending'], 'successful_repudiation')

    def test_every_other_declared_ending_has_a_player_decision_path(self):
        cases = {
            'settlement': 'creditor_settlement',
            'extraction': 'coercive_extraction',
            'imposed': 'imposed_financial_control',
            'control': 'imposed_financial_control',
            'mediation': 'sovereign_compromise',
            'nationalist': 'nationalist_victory',
            'stalled': 'stalled_intervention',
            'breakdown': 'breakdown',
            'disarm': 'coerced_disarmament',
            'joint': 'joint_financial_control',
            'french_brokered': 'french_brokered_settlement',
            'unresolved': 'unresolved_crisis',
            'hardship': 'fiscal_hardship',
        }
        reached = {'relief_and_payment', 'occupation', 'successful_repudiation'}
        for choices, expected in cases.items():
            with self.subTest(choices=choices):
                world, seen = play_campaign(choices)
                self.assertEqual(world['scenario_state']['ending'], expected)
                self.assertIsNone(world.get('scenario_warning_modal'))
                self.assertTrue(seen)
                reached.add(expected)
        declared = {entry['id'] for entry in SCENARIO['outcomes']}
        self.assertEqual(len(SCENARIO['outcomes']), len(declared))
        self.assertEqual(declared, reached)

    def test_outcome_evidence_distinguishes_food_hardship_from_breakdown(self):
        from scenario_egypt_1877 import classify_outcome
        world, _ = play_campaign('peace')
        state = world['scenario_state']
        self.assertEqual(classify_outcome(world, {
            **state['ending_metrics'], 'hunger_rate': 0.30,
        }), 'fiscal_hardship')
        self.assertEqual(classify_outcome(world, {
            **state['ending_metrics'], 'hunger_rate': 0.30, 'legitimacy': 0.05,
        }), 'breakdown')

    def test_outstanding_claim_without_enforcement_is_unresolved(self):
        from scenario_egypt_1877 import classify_outcome
        world = build_world_view(scenario_id='egypt_1877')
        world['scenario_state']['payment_status'] = 'defaulted'
        self.assertEqual(classify_outcome(world), 'unresolved_crisis')


if __name__ == '__main__':
    unittest.main()

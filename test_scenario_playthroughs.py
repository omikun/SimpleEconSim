"""Deterministic full campaign paths for the strategic Egypt scenario."""

import unittest
import random

from scenario_campaign import resolve_landing
from scenario_egypt_1877 import SCENARIO, apply_action, campaign_horizon, finish_due_campaign
from scenario_gunboat import resolve_naval_response
from scenario_occupation import resolve_capital
from scenario_politics import resolve as resolve_politics
from scenario_situation import creditor_response_options, resolve_creditor_response
from worldview_engine import build_world_view, step_world


def play_campaign(mode, observer=None):
    from agent import _agentid_counter
    from random_cache import rand
    import sovereign_bonds
    import macro.imperialism.manager as imperialism_manager
    import diplomacy
    import innovation
    import ledger
    # The sandbox exposes registries as singletons. Each replay needs fresh
    # contracts and blockades or a previous campaign can change this one.
    sovereign_bonds._GLOBAL_BOND_MARKET = None
    imperialism_manager._GLOBAL_IMPERIALISM_MANAGER = None
    diplomacy.diplomacy_instance = diplomacy.DiplomacySystem()
    innovation._INNOVATION_SYSTEM = None
    ledger._destruction.clear()
    # Imports can initialize the global random cache and reseed random.
    random.seed(1877)
    _agentid_counter[0] = 0
    rand._idx = rand._capacity
    world = build_world_view(scenario_id='egypt_1877')
    # Generation may import modules that advance the shared random stream.
    # Start the simulated campaign from a fixed stream independently of that.
    random.seed(1877)
    rand._idx = rand._capacity
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
    if observer is not None:
        observer(world, seen)
    for _ in range(70):
        if state.get('ending'):
            break
        turn = int(world['turn'])
        if mode in ('historical', 'nationalist', 'resistance', 'premature_offer') and state.get('last_action_turn') != turn:
            if turn == 1:
                ok, _ = apply_action(world, 'invite_representative_cabinet')
                assert ok
            elif turn == 2:
                ok, _ = apply_action(world, 'dismiss_foreign_controllers')
                assert ok
        if mode in ('peace', 'settlement', 'relief_payment', 'food_project', 'food_project_access', 'fiscal_project', 'hardship') and turn == 1 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world,
                'repair_delta_channels' if mode.startswith('food_project') else
                'build_revenue_office' if mode in ('fiscal_project', 'peace', 'settlement',
                                                   'relief_payment', 'hardship') else
                'prioritize_domestic_grain')
            assert ok, message
        if mode == 'sovereignty_project' and turn == 1 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'prepare_canal_line')
            assert ok, message
        if (mode in ('peace', 'relief_payment') and turn == 15
                and state.get('last_action_turn') != turn):
            from scenario_projects import reserve_recall_capacity
            if reserve_recall_capacity(world) >= 1.0:
                ok, message = apply_action(world, 'recall_district_reserves')
                assert ok, message
        if (mode in ('fiscal_project', 'peace', 'settlement', 'relief_payment', 'hardship')
                and state.get('last_action_turn') != turn
                and (state.get('strategic_projects', {}).get('fiscal_challenge') or {}).get('status') == 'pending'):
            ok, message = apply_action(world, 'publish_revenue_accounts')
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
        if mode == 'mediation' and turn == 14 and state.get('last_action_turn') != turn:
            ok, message = apply_action(world, 'reduce_fellahin_tax')
            assert ok, message
        if mode.startswith('food_project') and turn == 15 and state.get('last_action_turn') != turn:
            egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
            world['selected_region'] = next(tile for tile in egypt.tiles
                                            if getattr(tile, 'scenario_location', '') == 'Nile Delta')
            ok, message = apply_action(world, 'district_bargain_workers')
            assert ok, message
        if (mode in ('settlement', 'relief_payment')
                and turn == max(19, campaign_horizon(world) - 1)
                and not state['strategic_projects']['grain_entitlement_active']
                and state.get('last_action_turn') != turn):
            ok, message = apply_action(world, 'enact_grain_entitlement')
            assert ok, message
        if (mode == 'food_project_access' and turn == 19
                and not state['strategic_projects']['grain_entitlement_active']
                and state.get('last_action_turn') != turn):
            ok, message = apply_action(world, 'enact_grain_entitlement')
            assert ok, message
        if mode in ('extraction', 'breakdown') and state.get('last_action_turn') != turn:
            if turn == 1:
                ok, _ = apply_action(world, 'raise_local_taxes')
                assert ok
            elif mode == 'extraction' and turn == 2:
                ok, message = apply_action(world, 'build_revenue_office')
                assert ok, message
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
        if mode in ('resistance', 'premature_offer') and state.get('last_action_turn') != turn:
            held = any(owner == 'Britain' for owner in
                       state['campaign']['territorial_control'].values())
            choice = ({10: 'organize_boycott', 11: 'call_general_strike',
                       12: 'coordinate_insurgency', 13: 'negotiate_withdrawal'}.get(turn)
                      if mode == 'resistance' else
                      'negotiate_withdrawal' if turn == 10 else None)
            if held and choice:
                ok, message = apply_action(world, choice)
                assert ok, (turn, message)
        if not world.get('scenario_warning_modal'):
            step_world(world)
        if observer is not None:
            observer(world, seen)
        warning = world.get('scenario_warning_modal')
        if warning:
            kind = warning['kind']
            seen.append((int(world['turn']), kind))
            if kind == 'debt_due':
                if mode.startswith('food_project') or mode in ('fiscal_project', 'payment_first',
                                                                 'peace', 'relief_payment', 'settlement',
                                                                 'extraction', 'hardship'):
                    egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
                    cash = float(egypt.government.agent.cash)
                    due = float(state['scheduled_remittance'])
                    answer = ('concede_revenue' if mode == 'settlement' and int(world['turn']) == 6
                              and cash >= due * .5 else
                              'pay_remittance' if cash >= due else
                              'concede_revenue' if cash >= due * .5 else
                              'defer_remittance')
                elif mode == 'unresolved' and int(world['turn']) == 6:
                    answer = 'concede_revenue'
                elif (mode in ('breakdown',)
                      or mode == 'unresolved' and int(world['turn']) < 20):
                    answer = 'pay_remittance'
                else:
                    answer = 'default_remittance'
                ok, message = apply_action(world, answer)
                if not ok and answer == 'defer_remittance':
                    answer = 'default_remittance'
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
                    'defend_canal' if mode in ('canal', 'nationalist', 'sovereignty_project') else 'evacuate_port')
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
            assert ok, (mode, world['turn'], kind, answer, message,
                        float(next(n for n in world['nations'] if n.name == 'Egypt').government.agent.cash))
            world['scenario_warning_modal'] = None
            finish_due_campaign(world)
        if observer is not None:
            observer(world, seen)
    return world, seen


class ScenarioPlaythroughTests(unittest.TestCase):
    def test_funded_canal_line_changes_battle_or_deters_expedition(self):
        funded = [False]

        def fund_expedition(world, _seen):
            if not funded[0]:
                britain = next(nation for nation in world['nations'] if nation.name == 'Britain')
                britain.government.agent.cash += 140
                funded[0] = True

        world, seen = play_campaign('sovereignty_project', observer=fund_expedition)
        state = world['scenario_state']
        self.assertTrue(any(row['kind'] == 'crew_food' for row in
                            state['strategic_projects']['payments']))
        if any(kind == 'landing_warning' for _, kind in seen):
            self.assertEqual(state['campaign']['expedition']['route'],
                             'Port Said–Ismailia–Tel el Kebir')
            self.assertTrue(any(battle['location'] == 'Tel el Kebir'
                                and battle['defense_project_bonus'] > 0
                                for battle in state['campaign']['battles']))
        else:
            self.assertFalse(state['campaign']['battles'])
            self.assertIn(state['campaign']['expedition']['stage'], ('none', 'repelled'))

    def test_fiscal_project_earns_receipts_and_gets_creditor_reply(self):
        world, seen = play_campaign('fiscal_project')
        state = world['scenario_state']
        reports = state['strategic_projects']['revenue_reports']
        self.assertTrue(reports)
        self.assertTrue(all(0 < report['central_transfer'] <= report['receipt_after_interception']
                            for report in reports))
        self.assertTrue(any(row['action'] == 'publish_revenue_accounts'
                            for row in state['actions_taken']))
        self.assertEqual(state['strategic_projects']['fiscal_challenge']['status'], 'published')
        self.assertTrue(any(row['headline'] == 'Caisse reviews Alexandria office'
                            for row in state['creditor_news']))
        self.assertIn((6, 'debt_due'), seen)

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

    def test_occupation_requires_pressure_before_britain_accepts_withdrawal(self):
        premature, _ = play_campaign('premature_offer')
        weak = premature['scenario_state']['occupation']
        self.assertFalse(weak['withdrawal_replies'][0]['accepted'])
        self.assertEqual(premature['scenario_state']['ending'], 'occupation')

        resistant, _ = play_campaign('resistance')
        strong = resistant['scenario_state']['occupation']
        self.assertTrue(strong['withdrawal_replies'][0]['accepted'])
        self.assertEqual(resistant['scenario_state']['ending'], 'nationalist_victory')
        self.assertFalse(resistant['scenario_state']['campaign']['territorial_control'])
        self.assertTrue(any(entry['source'] == 'withdrawal_settlement'
                            and entry['amount'] == 30 for entry in strong['revenue_ledger']))

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
        # Holding the capital does not itself prevent a domestic breakdown.

    def test_every_declared_ending_has_a_player_decision_path(self):
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile

        # Full campaigns can share process-wide markets and innovation state.
        # The reachability claim concerns at least one viable decision path
        # per ending, so replay each path in a separate interpreter.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'matrix.json'
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).with_name('audit_egypt_strategic_integration.py')),
                 '--suite', '--output', str(output)],
                cwd=Path(__file__).parent,
                env={**os.environ, 'PYTHONHASHSEED': '0'},
                capture_output=True, text=True, timeout=900, check=False,
            )
            self.assertEqual(completed.returncode, 0,
                             completed.stdout[-3000:] + '\n' + completed.stderr[-3000:])
            rows = json.loads(output.read_text())
        self.assertTrue(all('error' not in row for row in rows))
        reached = {row['ending'] for row in rows}
        declared = {entry['id'] for entry in SCENARIO['outcomes']}
        self.assertEqual(len(SCENARIO['outcomes']), len(declared))
        self.assertEqual(declared, reached)

    def test_outcome_evidence_distinguishes_food_hardship_from_breakdown(self):
        from scenario_egypt_1877 import classify_outcome
        world, _ = play_campaign('fiscal_project')
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

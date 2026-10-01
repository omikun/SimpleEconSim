"""Deterministic full campaign paths for the strategic Egypt scenario."""

import unittest

from scenario_campaign import resolve_landing
from scenario_egypt_1877 import apply_action, finish_due_campaign
from scenario_gunboat import resolve_naval_response
from scenario_occupation import resolve_capital
from scenario_politics import resolve as resolve_politics
from scenario_situation import creditor_response_options, resolve_creditor_response
from worldview_engine import build_world_view, step_world


def play_campaign(mode):
    world = build_world_view(scenario_id='egypt_1877')
    state = world['scenario_state']
    seen = []
    for _ in range(70):
        if state.get('ending'):
            break
        turn = int(world['turn'])
        if mode == 'historical' and state.get('last_action_turn') != turn:
            if turn == 1:
                ok, _ = apply_action(world, 'invite_representative_cabinet')
                assert ok
            elif turn == 2:
                ok, _ = apply_action(world, 'dismiss_foreign_controllers')
                assert ok
        if not world.get('scenario_warning_modal'):
            step_world(world)
        warning = world.get('scenario_warning_modal')
        if warning:
            kind = warning['kind']
            seen.append((int(world['turn']), kind))
            if kind == 'debt_due':
                answer = 'pay_remittance' if mode == 'peace' else 'default_remittance'
                ok, message = apply_action(world, answer)
            elif kind == 'creditor_reaction':
                branch = warning['action_id']
                answer = ('defend_controller_dismissal' if branch == 'dismiss_foreign_controllers'
                          else 'contest_customs_claim' if branch == 'default_remittance'
                          else next(item['id'] for item in creditor_response_options(world, branch)
                                    if item['enabled']))
                ok, message = resolve_creditor_response(world, answer)
            elif kind in ('naval_ultimatum', 'naval_blockade'):
                ok, message = resolve_naval_response(world,
                    'naval_defend' if kind == 'naval_ultimatum' else 'naval_hold')
            elif kind == 'landing_warning':
                ok, message = resolve_landing(world,
                    'defend_canal' if mode == 'canal' else 'evacuate_port')
            elif kind == 'capital_warning':
                ok, message = resolve_capital(world, 'evacuate_cairo')
            elif kind in ('dynastic_crisis', 'officer_movement'):
                ok, message = resolve_politics(world,
                    'accept_tawfiq' if kind == 'dynastic_crisis' else 'support_urabi')
            else:
                raise AssertionError(f'Unexpected scenario modal {warning}')
            assert ok, message
            world['scenario_warning_modal'] = None
            finish_due_campaign(world)
    return world, seen


class ScenarioPlaythroughTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()

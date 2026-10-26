import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from army import MilitaryUnit
from scenario_occupation import apply_action


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, held=True, force=True, cash=100.0,
             pending_proposal=None):
    trace = MemoryTrace()
    government = SimpleNamespace(agent=SimpleNamespace(cash=float(cash)))
    tile = SimpleNamespace(name='Cairo', home_currency='EGP', gov=government)
    egypt = SimpleNamespace(name='Egypt', currency='EGP', government=government,
                            legitimacy=0.55, tiles=[tile])
    britain = SimpleNamespace(name='Britain', military_units=[])
    tile.owner_nation = egypt
    if force:
        britain.military_units.append(MilitaryUnit(
            'guided_british_landing_Alexandria', 'Britain', 'Alexandria',
            soldiers=8))
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 5, 'phase': 'occupation', 'next': 1}
    occupation = {
        'formal_sovereign': 'Egypt',
        'institutional_control': {'customs': 'Britain', 'cabinet': 'Egypt'},
        'resistance': 0.4, 'collaboration': 0.2, 'boycott_until': 0,
        'strike_until': 0, 'garrison_supply_paid': 0.0,
        'collected_this_turn': 0.0, 'collection_turn': 0,
        'revenue_ledger': [], 'events': [],
        'capital_warning_resolved': False,
        'withdrawal_proposal': copy.deepcopy(pending_proposal),
        'withdrawal_replies': [],
    }
    world = {
        'turn': 5, 'nations': [egypt, britain], 'tiles': [tile],
        'scenario_feedback': None,
        'scenario_state': {
            'occupation': occupation,
            'campaign': {
                'territorial_control': {'Alexandria': 'Britain'} if held else {},
                'civilian_casualties': 0,
            },
            'historical_log': [],
        },
    }
    return SimpleNamespace(world=world, egypt=egypt, britain=britain,
                           tile=tile, trace=trace)


class ScenarioOccupationActionTraceTests(unittest.TestCase):
    def _apply(self, fixture, action_id):
        with patch('scenario_occupation._event'):
            return apply_action(fixture.world, action_id)

    def _action_row(self, fixture):
        rows = [row for row in fixture.trace.rows
                if row.get('metric_id') == 'scenario.occupation_action']
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_boycott_and_strike_trace_effect_windows_and_legitimacy(self):
        boycott = _fixture()
        self.assertTrue(self._apply(boycott, 'organize_boycott')[0])
        boycott_row = self._action_row(boycott)
        self.assertEqual(boycott_row['inputs']['state_after']['boycott_until'], 7)
        self.assertAlmostEqual(
            boycott_row['inputs']['state_after']['resistance'], 0.52)
        self.assertEqual(boycott_row['inputs']['receipt_effect_window_turns'], 2)

        strike = _fixture()
        self.assertTrue(self._apply(strike, 'call_general_strike')[0])
        strike_row = self._action_row(strike)
        self.assertEqual(strike_row['inputs']['state_after']['strike_until'], 7)
        self.assertAlmostEqual(strike_row['inputs']['state_after']['egypt_legitimacy'],
                               0.58)
        self.assertEqual(strike_row['inputs']['legitimacy_rule'],
                         'min(1.0, legitimacy_before + 0.03)')

    def test_insurgency_records_actual_garrison_loss_and_civilian_counter(self):
        fixture = _fixture()
        unit = fixture.britain.military_units[0]
        unit.soldiers = 2
        fixture.world['scenario_state']['occupation']['resistance'] = 0.9
        fixture.egypt.legitimacy = 0.02

        self.assertTrue(self._apply(fixture, 'coordinate_insurgency')[0])

        row = self._action_row(fixture)
        inputs = row['inputs']
        self.assertEqual(inputs['selected_garrison_unit_id'], unit.unit_id)
        self.assertEqual((inputs['selected_unit_soldiers_before'],
                          inputs['selected_unit_soldiers_after']), (2, 0))
        self.assertEqual(inputs['civilian_casualty_counter_increment'], 1)
        self.assertEqual(inputs['state_after']['civilian_casualty_counter'], 1)
        self.assertEqual(inputs['state_after']['resistance'], 1.0)
        self.assertEqual(inputs['state_after']['egypt_legitimacy'], 0.0)

    def test_collaboration_and_withdrawal_offer_record_their_tradeoffs(self):
        collaboration = _fixture()
        self.assertTrue(self._apply(
            collaboration, 'collaborate_with_occupation')[0])
        collaboration_inputs = self._action_row(collaboration)['inputs']
        self.assertAlmostEqual(
            collaboration_inputs['state_after']['collaboration'], 0.45)
        self.assertAlmostEqual(
            collaboration_inputs['state_after']['resistance'], 0.22)
        self.assertAlmostEqual(
            collaboration_inputs['state_after']['egypt_legitimacy'], 0.5)

        withdrawal = _fixture()
        cash_before = withdrawal.egypt.government.agent.cash
        self.assertTrue(self._apply(withdrawal, 'negotiate_withdrawal')[0])
        withdrawal_inputs = self._action_row(withdrawal)['inputs']
        self.assertEqual(withdrawal_inputs['payment_status'],
                         'proposal_only_no_cash_transfer')
        self.assertEqual(withdrawal_inputs['state_after']['withdrawal_proposal'],
                         {'turn': 5, 'reply_turn': 6, 'amount': 30.0})
        self.assertEqual(withdrawal.egypt.government.agent.cash, cash_before)

    def test_rejection_gates_are_explained(self):
        cases = [
            (_fixture(held=False), 'organize_boycott',
             'no_foreign_garrison_to_confront'),
            (_fixture(force=False), 'coordinate_insurgency',
             'no_occupation_force_in_reach'),
            (_fixture(cash=10), 'negotiate_withdrawal',
             'insufficient_egyptian_treasury_cash'),
            (_fixture(pending_proposal={'turn': 4, 'reply_turn': 5,
                                        'amount': 30.0}),
             'negotiate_withdrawal', 'withdrawal_proposal_pending'),
            (_fixture(), 'invent_a_decision', 'unknown_occupation_decision'),
        ]
        for fixture, action_id, expected_reason in cases:
            with self.subTest(action_id=action_id, reason=expected_reason):
                ok, _ = self._apply(fixture, action_id)
                self.assertFalse(ok)
                row = self._action_row(fixture)
                self.assertEqual(row['record_class'], 'decision')
                self.assertEqual(row['inputs']['reason'], expected_reason)
                self.assertEqual(row['after'], 0)

    def test_trace_presence_does_not_change_action_state(self):
        for action_id in ('organize_boycott', 'call_general_strike',
                          'coordinate_insurgency', 'collaborate_with_occupation',
                          'negotiate_withdrawal'):
            with self.subTest(action_id=action_id):
                traced = _fixture(traced=True)
                plain = _fixture(traced=False)
                traced_result = self._apply(traced, action_id)
                plain_result = self._apply(plain, action_id)
                self.assertEqual(traced_result, plain_result)
                self.assertEqual(
                    traced.world['scenario_state']['occupation'],
                    plain.world['scenario_state']['occupation'])
                self.assertEqual(
                    traced.world['scenario_state']['campaign'],
                    plain.world['scenario_state']['campaign'])
                self.assertEqual(traced.egypt.legitimacy, plain.egypt.legitimacy)
                self.assertEqual(traced.egypt.government.agent.cash,
                                 plain.egypt.government.agent.cash)
                self.assertEqual(
                    [unit.soldiers for unit in traced.britain.military_units],
                    [unit.soldiers for unit in plain.britain.military_units])

    def test_repeated_same_turn_actions_get_distinct_operation_ids(self):
        fixture = _fixture()

        self.assertTrue(self._apply(fixture, 'organize_boycott')[0])
        self.assertTrue(self._apply(fixture, 'organize_boycott')[0])

        rows = [row for row in fixture.trace.rows
                if row.get('metric_id') == 'scenario.occupation_action']
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['inputs']['operation_id'],
                            rows[1]['inputs']['operation_id'])


if __name__ == '__main__':
    unittest.main()

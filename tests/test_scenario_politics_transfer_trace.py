import json
import unittest
from types import SimpleNamespace

from metric_catalog import METRICS, TRACE_INSTRUMENTED
from scenario_politics import advance as advance_politics
from scenario_politics import apply_action
from scenario_politics import resolve as resolve_political_response


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, treasury_cash=100.0, recipients=True, already_paid=False,
             traced=True):
    residents = [
        SimpleNamespace(id=11, cash=3.0, alive=True,
                        is_government=False, is_corporation=False,
                        home_currency='EGP'),
        SimpleNamespace(id=12, cash=7.0, alive=True,
                        is_government=False, is_corporation=False,
                        home_currency='EGP'),
    ] if recipients else []
    residents.extend([
        SimpleNamespace(id=13, cash=1.0, alive=True,
                        is_government=True, is_corporation=False),
        SimpleNamespace(id=14, cash=1.0, alive=True,
                        is_government=False, is_corporation=True),
    ])
    tile = SimpleNamespace(name='Alexandria', scenario_location='Alexandria',
                           home_currency='EGP', agents=residents)
    treasury = SimpleNamespace(id=900, cash=float(treasury_cash))
    unit = SimpleNamespace(unit_id='egypt_alexandria_garrison', morale=0.4)
    nation = SimpleNamespace(name='Egypt', currency='EGP', tiles=[tile],
                             government=SimpleNamespace(agent=treasury),
                             military_units=[unit])
    politics = {'officers_paid': already_paid, 'army_loyalty': 0.5,
                'garrison_id': unit.unit_id, 'events': []}
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 4, 'phase': 'scenario_action',
                                        'next': 1}
    world = {'turn': 4, 'nations': [nation], 'tiles': [tile],
             'scenario_state': {'politics': politics}, 'ticker_events': []}
    return world, nation, tile, residents, treasury, unit, politics, trace


def _state(fixture):
    world, nation, tile, residents, treasury, unit, politics, _trace = fixture
    return (treasury.cash, tuple(agent.cash for agent in residents),
            politics['officers_paid'], politics['army_loyalty'], unit.morale,
            tuple(world['ticker_events']), tuple(politics['events']))


def _dynamics_fixture(*, traced=True):
    resident = SimpleNamespace(
        id=21, alive=True, is_government=False, is_corporation=False,
        is_trader=False, calorie_need_kcal=600.0,
        calorie_deficit_kcal=300.0)
    tile = SimpleNamespace(name='Alexandria', unrest_level=0.4,
                           agents=[resident])
    unit = SimpleNamespace(unit_id='egypt_alexandria_garrison', morale=0.5)
    nation = SimpleNamespace(name='Egypt', tiles=[tile], military_units=[unit])
    politics = {
        'ruler': 'Ismail Pasha', 'governing_coalition': 'palace',
        'officer_access': 0.35, 'army_loyalty': 0.70,
        'palace_authority': 0.80, 'civilian_support': 0.20,
        'nationalist_movement': 0.20, 'cabinet_authority': 0.20,
        'officers_promoted': False, 'representative_cabinet': False,
        'controllers_dismissed': False, 'crisis_resolved': False,
        'deposition_resolved': False, 'garrison_id': unit.unit_id,
        'events': [],
    }
    scenario = {'politics': politics, 'fiscal_autonomy': 0.80,
                'extraction_level': 0.60,
                'naval_crisis': {'stage': 'blockaded'},
                'creditor_reactions': []}
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {'turn': 5, 'phase': 'scenario_politics',
                                        'next': 1}
    world = {'turn': 5, 'nations': [nation], 'tiles': [tile],
             'scenario_state': scenario, 'ticker_events': [], 'playing': True}
    return world, nation, tile, resident, unit, politics, trace


def _dynamics_state(fixture):
    world, _nation, _tile, _resident, unit, politics, _trace = fixture
    return ({key: politics[key] for key in (
        'army_loyalty', 'civilian_support', 'nationalist_movement',
        'palace_authority', 'cabinet_authority')}, unit.morale,
        world.get('scenario_warning_modal'), world.get('playing'))


def _scenario_world_with_trace(seed=22):
    from worldview_engine import build_world_view

    world = build_world_view(seed=seed, scenario_id='egypt_1877')
    nation = world['selected_nation']
    tile = nation.tiles[0]
    trace = MemoryTrace()
    tile._run_trace = trace
    tile._collective_trace_clock = {
        'turn': int(world.get('turn', 0)), 'phase': 'scenario_politics', 'next': 1}
    return world, nation, trace


class ScenarioPoliticsTransferTraceTests(unittest.TestCase):
    def test_arrears_payment_records_treasury_and_each_household_receipt(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        self.assertTrue(apply_action(plain[0], 'pay_army_arrears')[0])
        self.assertTrue(apply_action(traced[0], 'pay_army_arrears')[0])

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[4].cash, 70.0)
        self.assertEqual([person.cash for person in traced[3]], [18.0, 22.0, 1.0, 1.0])
        funding = next(row for row in traced[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        debit = next(row for row in traced[7].rows
                     if row.get('kind') == 'officer_arrears_treasury_debit')
        receipts = [row for row in traced[7].rows
                    if row.get('kind') == 'officer_arrears_household_receipt']
        outcome = next(row for row in traced[7].rows
                       if row.get('kind') == 'officer_arrears_payment_outcome')
        self.assertTrue(funding['inputs']['funded'])
        self.assertEqual(len(receipts), 2)
        self.assertEqual(debit['inputs']['transfer_contract']['amount'], 30.0)
        self.assertEqual(debit['inputs']['transfer_contract']['payer_account']['balance_before'],
                         100.0)
        self.assertEqual(debit['inputs']['transfer_contract']['payer_account']['balance_after'],
                         70.0)
        self.assertEqual([row['subject']['id'] for row in receipts], ['11', '12'])
        self.assertTrue(all(row['cause_event_ids'] == [debit['event_id']]
                            for row in receipts))
        self.assertEqual(outcome['before'], 0.5)
        self.assertEqual(outcome['after'], 0.72)
        self.assertEqual(outcome['cause_event_ids'],
                         [funding['event_id'], debit['event_id']]
                         + [row['event_id'] for row in receipts])
        morale = next(row for row in traced[7].rows
                      if row.get('kind') ==
                      'officer_arrears_garrison_morale_outcome')
        self.assertEqual(morale['before'], 0.4)
        self.assertAlmostEqual(morale['after'], 0.6)
        self.assertIn(outcome['event_id'], morale['cause_event_ids'])
        for row in traced[7].rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_underfunded_arrears_records_gate_without_changing_cash_or_loyalty(self):
        fixture = _fixture(treasury_cash=29.0)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 29.0)
        self.assertEqual([agent.cash for agent in fixture[3]], [3.0, 7.0, 1.0, 1.0])
        self.assertEqual(fixture[6]['army_loyalty'], 0.5)
        funding = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        self.assertEqual(funding['inputs']['reason'], 'treasury_cash_below_cost')
        self.assertEqual(funding['inputs']['cash_shortfall'], 1.0)
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))

    def test_missing_household_recipients_records_gate_without_payment(self):
        fixture = _fixture(recipients=False)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 100.0)
        funding = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_funding_decision')
        self.assertEqual(funding['inputs']['reason'], 'no_household_recipients')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))

    def test_already_paid_package_is_recorded_as_noop(self):
        fixture = _fixture(already_paid=True)
        self.assertFalse(apply_action(fixture[0], 'pay_army_arrears')[0])
        self.assertEqual(fixture[4].cash, 100.0)
        outcome = next(row for row in fixture[7].rows
                       if row.get('kind') == 'officer_arrears_payment_outcome')
        self.assertEqual(outcome['inputs']['reason'], 'arrears_package_already_funded')
        self.assertFalse(any(row.get('record_class') == 'transfer'
                             for row in fixture[7].rows))

    def test_turn_dynamics_trace_each_formula_input_and_changed_political_metric(self):
        plain = _dynamics_fixture(traced=False)
        traced = _dynamics_fixture(traced=True)

        advance_politics(plain[0])
        advance_politics(traced[0])

        self.assertEqual(_dynamics_state(plain), _dynamics_state(traced))
        calculation = next(row for row in traced[6].rows
                           if row.get('kind') == 'scenario_politics_dynamics_calculation')
        inputs = calculation['inputs']
        self.assertEqual(inputs['model'], 'egypt_political_support.v1')
        self.assertEqual(inputs['population_inputs']['eligible_household_count'], 1)
        self.assertAlmostEqual(inputs['population_inputs']['mean_hunger_fraction'], 0.5)
        self.assertAlmostEqual(inputs['population_inputs']['mean_unrest'], 0.4)
        self.assertAlmostEqual(inputs['military_inputs']['naval_loyalty_penalty'], 0.3)
        self.assertAlmostEqual(inputs['foreign_control_inputs']['foreign_control'], 0.2)
        self.assertAlmostEqual(inputs['intermediate_values']['loyalty_target'], 0.0825)
        self.assertAlmostEqual(inputs['intermediate_values']['nationalist_grievance'],
                               0.46076)
        outcomes = [row for row in traced[6].rows
                    if row.get('kind') == 'scenario_politics_metric_outcome']
        self.assertEqual({row['metric_id'] for row in outcomes}, {
            'politics.army_loyalty', 'politics.civilian_support',
            'politics.nationalist_movement', 'politics.palace_authority'})
        self.assertTrue(all(row['cause_event_ids'] == [calculation['event_id']]
                            for row in outcomes))
        gate_rows = [row for row in traced[6].rows
                     if row.get('kind') == 'scenario_political_crisis_gate_evaluation']
        self.assertEqual([(row['inputs']['gate'], row['after']) for row in gate_rows],
                         [('dynastic_crisis', False), ('officer_movement', False)])
        for row in traced[6].rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_dynastic_and_officer_crisis_gates_record_trigger_conditions(self):
        dynastic = _dynamics_fixture()
        dynastic[5]['palace_authority'] = 0.61
        dynastic[0]['scenario_state']['fiscal_autonomy'] = 0.20
        advance_politics(dynastic[0])
        self.assertEqual(dynastic[0]['scenario_warning_modal']['kind'],
                         'dynastic_crisis')
        dynastic_gate = next(row for row in dynastic[6].rows
                             if row.get('kind') ==
                             'scenario_political_crisis_gate_evaluation')
        self.assertTrue(dynastic_gate['after'])
        self.assertEqual(dynastic_gate['inputs']['gate'], 'dynastic_crisis')
        self.assertTrue(dynastic_gate['inputs']['conditions']['dismissal_reaction_pending']
                        is False)

        officer = _dynamics_fixture()
        officer[5]['palace_authority'] = 0.95
        officer[5]['nationalist_movement'] = 0.54
        officer[5]['army_loyalty'] = 0.58
        officer[0]['scenario_state']['fiscal_autonomy'] = 1.0
        advance_politics(officer[0])
        self.assertEqual(officer[0]['scenario_warning_modal']['kind'],
                         'officer_movement')
        gates = [row for row in officer[6].rows
                 if row.get('kind') == 'scenario_political_crisis_gate_evaluation']
        self.assertEqual([row['inputs']['gate'] for row in gates],
                         ['dynastic_crisis', 'officer_movement'])
        self.assertFalse(gates[0]['after'])
        self.assertTrue(gates[1]['after'])

    def test_constitutional_response_traces_choice_and_political_state_changes(self):
        world, egypt, trace = _scenario_world_with_trace()
        world['scenario_warning_modal'] = {'kind': 'dynastic_crisis'}
        state = world['scenario_state']['politics']
        state['palace_authority'] = 0.50
        world['scenario_state']['fiscal_autonomy'] = 0.50
        autonomy_before = world['scenario_state']['fiscal_autonomy']
        palace_before = state['palace_authority']
        civilian_before = state['civilian_support']

        success, _message = resolve_political_response(
            world, 'constitutional_compromise')

        self.assertTrue(success)
        decision = next(row for row in trace.rows
                        if row.get('kind') == 'scenario_political_response_decision')
        applied = next(row for row in trace.rows
                       if row.get('kind') == 'scenario_political_response_applied')
        self.assertEqual(decision['before'], 'dynastic_crisis')
        self.assertEqual(decision['after'], 'constitutional_compromise')
        self.assertEqual(applied['cause_event_ids'], [decision['event_id']])
        changes = [row for row in trace.rows
                   if row.get('kind') ==
                   'scenario_political_response_metric_outcome']
        changed = {row['metric_id']: (row['before'], row['after'])
                   for row in changes}
        self.assertAlmostEqual(changed['scenario.fiscal_autonomy'][1],
                               autonomy_before + 0.10)
        self.assertAlmostEqual(changed['politics.palace_authority'][1],
                               palace_before + 0.20)
        self.assertAlmostEqual(changed['politics.civilian_support'][1],
                               civilian_before + 0.10)
        categories = [row for row in trace.rows
                      if row.get('kind') ==
                      'scenario_political_response_category_outcome']
        self.assertEqual({row['metric_id'] for row in categories}, {
            'scenario.ruler_transition', 'scenario.governing_coalition'})
        for row in trace.rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_backing_palace_traces_per_tile_unrest_effect_from_army_loyalty(self):
        world, egypt, trace = _scenario_world_with_trace(seed=23)
        world['scenario_warning_modal'] = {'kind': 'officer_movement'}
        state = world['scenario_state']['politics']
        state['army_loyalty'] = 0.4
        tiles = egypt.tiles[:2]
        if len(tiles) < 2:
            self.skipTest('Egypt scenario needs at least two tiles for territorial unrest trace.')
        tiles[0].unrest_level = 0.2
        tiles[1].unrest_level = 0.95
        unrest_before = {tile.name: float(getattr(tile, 'unrest_level', 0.0))
                         for tile in egypt.tiles}

        success, _message = resolve_political_response(world, 'back_palace')

        self.assertTrue(success)
        response = next(row for row in trace.rows
                        if row.get('kind') == 'scenario_political_response_applied')
        unrest_events = [row for row in trace.rows
                         if row.get('kind') ==
                         'scenario_political_response_unrest_outcome']
        self.assertEqual({row['subject']['id'] for row in unrest_events},
                         {name for name, value in unrest_before.items() if value < 1.0})
        self.assertTrue(all(row['cause_event_ids'] == [response['event_id']]
                            for row in unrest_events))
        by_tile = {row['subject']['id']: row for row in unrest_events}
        self.assertAlmostEqual(by_tile[tiles[0].name]['after'], 0.272)
        self.assertEqual(by_tile[tiles[1].name]['after'], 1.0)
        self.assertEqual(by_tile[tiles[0].name]['inputs']['army_loyalty'], 0.4)

    def test_unavailable_political_responses_record_noop_gates(self):
        no_crisis = _fixture()
        self.assertFalse(resolve_political_response(
            no_crisis[0], 'accept_tawfiq')[0])
        no_crisis_gate = next(row for row in no_crisis[7].rows
                              if row.get('kind') ==
                              'scenario_political_response_gate_evaluation')
        self.assertEqual(no_crisis_gate['inputs']['reason'],
                         'no_political_transition_awaiting_decision')
        self.assertFalse(no_crisis_gate['after'])

        invalid = _fixture()
        invalid[0]['scenario_warning_modal'] = {'kind': 'dynastic_crisis'}
        self.assertFalse(resolve_political_response(invalid[0], 'invalid_response')[0])
        invalid_gate = next(row for row in invalid[7].rows
                            if row.get('kind') ==
                            'scenario_political_response_gate_evaluation')
        self.assertEqual(invalid_gate['inputs']['reason'],
                         'response_unavailable_for_crisis')
        self.assertIn('accept_tawfiq', invalid_gate['inputs']['available_response_ids'])


if __name__ == '__main__':
    unittest.main()

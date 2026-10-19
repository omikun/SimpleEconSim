"""Causal tracing for Guided Egypt's naval ultimatum and blockade responses."""

import json
import tempfile
import unittest
from pathlib import Path

from macro.imperialism.manager import get_imperialism_manager
from run_trace import RunTrace, verify
from scenario_geography import create_fleet, move_fleet
from scenario_gunboat import resolve_naval_response
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'naval-response-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, stage='ultimatum', turn=4):
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = turn
    state = world['scenario_state']
    state['naval_crisis']['stage'] = stage
    state['naval_crisis']['battery_strength'] = 28.0
    tile_name = state['geography']['sites']['Alexandria']['tile']
    trace = MemoryTrace()
    clock = {'turn': turn, 'phase': 'naval_crisis', 'next': 1}
    if traced:
        for tile in world['tiles']:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    manager = get_imperialism_manager()
    manager.blockaded_tiles.discard(tile_name)
    manager.blockade_enforcers.pop(tile_name, None)
    return world, trace, tile_name


class ScenarioNavalResponseTraceTests(unittest.TestCase):
    @staticmethod
    def _response_row(trace):
        rows = [row for row in trace.rows
                if row.get('metric_id') == 'scenario.naval_response']
        if not rows:
            raise AssertionError('naval response trace was not emitted')
        return rows[-1]

    def test_rejected_response_traces_stage_and_affordability_gates(self):
        idle, idle_trace, _ = _fixture(stage='none')
        self.assertFalse(resolve_naval_response(idle, 'naval_hold')[0])
        idle_row = self._response_row(idle_trace)
        self.assertEqual(idle_row['inputs']['reason'],
                         'no_naval_demand_awaiting_response')

        unaffordable, unaffordable_trace, _ = _fixture()
        egypt = next(n for n in unaffordable['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = 0.0
        self.assertFalse(resolve_naval_response(unaffordable, 'naval_settle')[0])
        row = self._response_row(unaffordable_trace)
        self.assertEqual(row['inputs']['reason'],
                         'settlement_cash_below_required_amount')
        self.assertFalse(row['inputs']['response_enabled'])

    def test_unreliable_palace_command_rejection_names_the_gate(self):
        world, trace, _ = _fixture()
        politics = world['scenario_state']['politics']
        politics['governing_coalition'] = 'palace'
        politics['army_loyalty'] = 0.2

        self.assertFalse(resolve_naval_response(world, 'naval_defend')[0])

        row = self._response_row(trace)
        self.assertEqual(row['inputs']['reason'], 'garrison_command_unreliable')
        self.assertEqual(row['inputs']['state_before'], row['inputs']['state_after'])

    def test_disarm_traces_legitimacy_autonomy_and_withdrawal(self):
        traced, trace, _ = _fixture()
        plain, _plain_trace, _ = _fixture(traced=False)
        egypt_traced = next(n for n in traced['nations'] if n.name == 'Egypt')
        egypt_plain = next(n for n in plain['nations'] if n.name == 'Egypt')

        self.assertEqual(resolve_naval_response(traced, 'naval_disarm'),
                         resolve_naval_response(plain, 'naval_disarm'))

        row = self._response_row(trace)
        self.assertTrue(row['inputs']['success'])
        self.assertEqual(row['inputs']['battery_strength_after'], 0.0)
        self.assertEqual(row['inputs']['legitimacy_rule'],
                         'max(0.0, legitimacy_before - 0.08)')
        self.assertEqual(egypt_traced.legitimacy, egypt_plain.legitimacy)
        self.assertEqual(traced['scenario_state']['fiscal_autonomy'],
                         plain['scenario_state']['fiscal_autonomy'])
        withdrawal = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_crisis_stage')
        self.assertIn(withdrawal['event_id'], row['cause_event_ids'])
        self.assertEqual(row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')

    def test_customs_settlement_links_debt_transfers_and_withdrawal(self):
        world, trace, _ = _fixture()
        egypt = next(n for n in world['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = 100000.0

        success, _ = resolve_naval_response(world, 'naval_settle')

        self.assertTrue(success)
        row = self._response_row(trace)
        self.assertAlmostEqual(row['inputs']['settlement_amount'],
                               row['inputs']['debt_before']
                               * row['inputs']['settlement_fraction'], places=2)
        self.assertEqual(row['inputs']['state_after']['payment_status'],
                         'restructured')
        causes = set(row.get('cause_event_ids', []))
        debt_rows = [event for event in trace.rows
                     if event.get('metric_id') == 'finance.obligation_balance'
                     and event.get('kind') == 'caisse_naval_settlement']
        withdrawal = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_crisis_stage')
        self.assertTrue(debt_rows)
        self.assertTrue({event['event_id'] for event in debt_rows}.issubset(causes))
        self.assertIn(withdrawal['event_id'], causes)

    def test_customs_control_records_levy_assignment_and_autonomy_cost(self):
        world, trace, _ = _fixture()
        success, _ = resolve_naval_response(world, 'naval_accept_control')

        self.assertTrue(success)
        row = self._response_row(trace)
        self.assertEqual(row['inputs']['levy_per_turn'], 5.0)
        self.assertEqual(row['inputs']['assigned_revenue_sources'],
                         world['scenario_state']['assigned_revenues'])
        self.assertAlmostEqual(
            row['inputs']['fiscal_autonomy_before']
            - row['inputs']['state_after']['fiscal_autonomy'], 0.15)
        causes = set(row.get('cause_event_ids', []))
        assignment_rows = [event for event in trace.rows
                           if event.get('kind') == 'caisse_collection_assignment']
        withdrawal = next(event for event in trace.rows
                          if event.get('metric_id') == 'scenario.naval_crisis_stage')
        self.assertTrue(assignment_rows)
        self.assertTrue({event['event_id'] for event in assignment_rows}.issubset(causes))
        self.assertIn(withdrawal['event_id'], causes)

    def test_defense_links_bombardment_and_blockade_effects(self):
        world, trace, tile_name = _fixture()
        politics = world['scenario_state']['politics']
        politics['governing_coalition'] = 'nationalist'
        politics['army_loyalty'] = 0.8
        create_fleet(world, 'Britain')
        self.assertTrue(move_fleet(world, 'Britain', 'Alexandria'))

        success, _ = resolve_naval_response(world, 'naval_defend')

        self.assertTrue(success)
        row = self._response_row(trace)
        self.assertEqual(row['inputs']['defense_result'], 'blockade_imposed')
        self.assertGreaterEqual(row['inputs']['force_ratio'],
                                row['inputs']['minimum_force_ratio'])
        self.assertTrue(row['inputs']['state_after']['alexandria_blockaded'])
        bombardment = next(event for event in trace.rows
                           if event.get('metric_id') == 'scenario.bombardment')
        self.assertIn(bombardment['event_id'], row['cause_event_ids'])
        manager = get_imperialism_manager()
        manager.lift_blockade(tile_name, world, int(world['turn']))

    def test_defense_withdraws_when_fleet_is_absent_or_deterred(self):
        absent, absent_trace, _ = _fixture()
        absent['scenario_state']['politics']['governing_coalition'] = 'nationalist'
        self.assertTrue(resolve_naval_response(absent, 'naval_defend')[0])
        absent_row = self._response_row(absent_trace)
        self.assertEqual(absent_row['inputs']['defense_result'],
                         'no_supplied_squadron')
        self.assertEqual(absent_row['inputs']['state_after']['naval_crisis_stage'],
                         'withdrawn')

        deterred, deterred_trace, _ = _fixture()
        deterred['scenario_state']['politics']['governing_coalition'] = 'nationalist'
        fleet = create_fleet(deterred, 'Britain', guns=80)
        fleet['damage'] = 0.95
        self.assertTrue(move_fleet(deterred, 'Britain', 'Alexandria'))
        deterred['scenario_state']['naval_crisis']['battery_strength'] = 500.0
        self.assertTrue(resolve_naval_response(deterred, 'naval_defend')[0])
        deterred_row = self._response_row(deterred_trace)
        self.assertEqual(deterred_row['inputs']['defense_result'],
                         'coastal_defenses_deterred_fleet')
        self.assertLess(deterred_row['inputs']['force_ratio'],
                        deterred_row['inputs']['minimum_force_ratio'])

    def test_hold_and_mediation_record_their_distinct_wait_states(self):
        hold, hold_trace, _ = _fixture(stage='blockaded', turn=7)
        self.assertTrue(resolve_naval_response(hold, 'naval_hold')[0])
        hold_row = self._response_row(hold_trace)
        self.assertEqual(hold_row['inputs']['last_offer_turn_after'], 7)
        self.assertTrue(hold_row['inputs']['blockade_continues'])

        mediation, mediation_trace, _ = _fixture(stage='ultimatum', turn=8)
        self.assertTrue(resolve_naval_response(mediation, 'naval_seek_mediation')[0])
        mediation_row = self._response_row(mediation_trace)
        self.assertEqual(mediation_row['inputs']['mediation_due_turn'], 9)
        self.assertEqual(mediation_row['inputs']['state_after']['naval_crisis_stage'],
                         'mediation')

    def test_response_record_serializes_in_compact_trace(self):
        world, _memory_trace, _ = _fixture(traced=False)
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'naval-response.ctr'
            recorder = RunTrace(trace_path, 'naval-response-test')
            clock = {'turn': int(world['turn']),
                     'phase': 'naval_crisis', 'next': 1}
            for tile in world['tiles']:
                tile._run_trace = recorder
                tile._collective_trace_clock = clock
            self.assertTrue(resolve_naval_response(world, 'naval_disarm')[0])
            result = recorder.query(metric_id='scenario.naval_response')
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['events'][0]['inputs']['response_id'],
                             'naval_disarm')
            self.assertGreater(verify(trace_path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()

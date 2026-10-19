"""Trace coverage for the Alexandria revenue inspection decision."""

import json
import tempfile
import unittest
from pathlib import Path

from run_trace import RunTrace, verify
from scenario_debt import bonds
from scenario_projects import answer_fiscal_challenge
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'fiscal-challenge-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, stage='none', turn=6):
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = turn
    state = world['scenario_state']
    state['naval_crisis']['stage'] = stage
    state['strategic_projects']['fiscal_challenge'] = {
        'status': 'pending', 'due_turn': turn}
    trace = MemoryTrace()
    clock = {'turn': turn, 'phase': 'scenario_projects', 'next': 1}
    if traced:
        for tile in world['tiles']:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return world, trace


class FiscalChallengeTraceTests(unittest.TestCase):
    @staticmethod
    def _row(trace, metric_id, kind=None):
        return next(row for row in trace.rows
                    if row.get('metric_id') == metric_id
                    and (kind is None or row.get('kind') == kind))

    def test_missing_challenge_records_rejection_without_mutation(self):
        world, trace = _fixture()
        world['scenario_state']['strategic_projects']['fiscal_challenge'] = None

        success, _ = answer_fiscal_challenge(world, publish=True)

        self.assertFalse(success)
        row = self._row(trace, 'scenario.fiscal_challenge_response')
        self.assertEqual(row['inputs']['reason'], 'no_pending_fiscal_challenge')
        self.assertEqual(row['inputs']['state_before'], row['inputs']['state_after'])

    def test_publishing_records_status_and_confidence_change(self):
        world, trace = _fixture()
        confidence_before = world['scenario_state']['creditor_confidence']

        success, _ = answer_fiscal_challenge(world, publish=True)

        self.assertTrue(success)
        row = self._row(trace, 'scenario.fiscal_challenge_response')
        self.assertEqual(row['inputs']['reason'], 'accounts_published')
        self.assertEqual(row['inputs']['state_before']['challenge_status'], 'pending')
        self.assertEqual(row['inputs']['state_after']['challenge_status'], 'published')
        self.assertAlmostEqual(row['inputs']['confidence_after'] - confidence_before,
                               0.06)
        self.assertFalse(row['inputs']['escalation_attempted'])

    def test_refusal_without_default_does_not_trigger_naval_crisis(self):
        world, trace = _fixture()
        self.assertFalse(any(bond.status == 'defaulted' for bond in bonds(world)))

        success, _ = answer_fiscal_challenge(world, publish=False)

        self.assertTrue(success)
        row = self._row(trace, 'scenario.fiscal_challenge_response')
        self.assertEqual(row['inputs']['reason'],
                         'inspection_refused_without_defaulted_obligation')
        self.assertEqual(world['scenario_state']['naval_crisis']['stage'], 'none')
        self.assertFalse(any(event.get('metric_id') == 'scenario.naval_escalation'
                             for event in trace.rows))

    def test_defaulted_refusal_links_action_decision_to_escalation(self):
        world, trace = _fixture()
        for bond in bonds(world):
            bond.status = 'defaulted'

        success, _ = answer_fiscal_challenge(world, publish=False)

        self.assertTrue(success)
        decision = self._row(trace, 'scenario.fiscal_challenge_escalation_decision')
        escalation = self._row(trace, 'scenario.naval_escalation')
        response = self._row(trace, 'scenario.fiscal_challenge_response')
        self.assertEqual(decision['inputs']['reason'],
                         'inspection_refused_with_defaulted_obligation')
        self.assertTrue(decision['inputs']['escalation_gate_open'])
        self.assertIn(decision['event_id'], escalation['cause_event_ids'])
        self.assertIn(decision['event_id'], response['cause_event_ids'])
        self.assertIn(escalation['event_id'], response['cause_event_ids'])
        self.assertEqual(response['inputs']['state_after']['naval_crisis_stage'],
                         'mobilizing')
        self.assertEqual(set(response['inputs']['defaulted_bond_ids']),
                         {bond.bond_id for bond in bonds(world)})

    def test_active_crisis_records_escalation_rejection(self):
        world, trace = _fixture(stage='ultimatum')
        for bond in bonds(world):
            bond.status = 'defaulted'

        success, _ = answer_fiscal_challenge(world, publish=False)

        self.assertTrue(success)
        escalation = self._row(trace, 'scenario.naval_escalation')
        response = self._row(trace, 'scenario.fiscal_challenge_response')
        self.assertFalse(escalation['inputs']['success'])
        self.assertEqual(escalation['inputs']['gate_reason'],
                         'naval_crisis_already_active')
        self.assertFalse(response['inputs']['escalation_gate_open'])
        self.assertEqual(response['inputs']['state_after']['naval_crisis_stage'],
                         'ultimatum')

    def test_trace_on_off_state_parity_and_compact_serialization(self):
        def run(traced):
            world, _trace = _fixture(traced=traced)
            for bond in bonds(world):
                bond.status = 'defaulted'
            answer_fiscal_challenge(world, publish=False)
            state = world['scenario_state']
            return (state['strategic_projects']['fiscal_challenge'],
                    state['creditor_confidence'], state['naval_crisis'],
                    state['chapter'], state.get('chapter_two_start_turn'),
                    world.get('scenario_bookend_modal'), state['creditor_news'])

        self.assertEqual(run(True), run(False))

        world, _trace = _fixture(traced=False)
        for bond in bonds(world):
            bond.status = 'defaulted'
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / 'fiscal-challenge.ctr'
            recorder = RunTrace(trace_path, 'fiscal-challenge-test')
            clock = {'turn': int(world['turn']),
                     'phase': 'scenario_projects', 'next': 1}
            for tile in world['tiles']:
                tile._run_trace = recorder
                tile._collective_trace_clock = clock
            answer_fiscal_challenge(world, publish=False)
            result = recorder.query(metric_id='scenario.fiscal_challenge_response')
            self.assertEqual(result['total'], 1)
            self.assertGreater(verify(trace_path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()

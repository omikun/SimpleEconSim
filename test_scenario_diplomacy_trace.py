import json
import unittest
from unittest.mock import patch

from scenario_diplomacy import advance, evaluate
from scenario_geography import foreign_decisions
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture():
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = 8
    world['scenario_state']['payment_status'] = 'defaulted'
    trace = MemoryTrace()
    tile = world['tiles'][0]
    tile._run_trace = trace
    tile._collective_trace_clock = {
        'turn': 8, 'phase': 'scenario_diplomacy', 'next': 1}
    for nation in world['nations']:
        if nation.name in ('France', 'Britain'):
            nation.government.agent.cash = 500.0
    return world, trace, tile


def _policy_state(world):
    crisis = world['scenario_state']['diplomatic_crisis']
    return (crisis['french_policy'], crisis['british_policy'],
            crisis['french_commitment'], dict(crisis['french_authorization']),
            dict(crisis['reasons']), list(crisis['history']))


class ScenarioDiplomacyTraceTests(unittest.TestCase):
    def test_foreign_policy_trace_explains_funding_protest_and_ottoman_gates(self):
        world, trace, tile = _fixture()
        state = world['scenario_state']
        crisis = state['diplomatic_crisis']
        crisis['egyptian_proposal'] = 'mediation'
        state['naval_crisis']['stage'] = 'blockaded'

        with patch('scenario_diplomacy._energy', return_value=1.0):
            traced_decisions = foreign_decisions(world)
            traced_state = _policy_state(world)

        france = next(row for row in trace.rows
                      if row.get('kind') == 'scenario_diplomacy_ai_decision'
                      and row['subject']['id'] == 'France')
        britain = next(row for row in trace.rows
                       if row.get('kind') == 'scenario_diplomacy_ai_decision'
                       and row['subject']['id'] == 'Britain')
        ottoman = next(row for row in trace.rows
                       if row.get('kind') == 'scenario_diplomacy_ai_decision'
                       and row['subject']['id'] == 'Ottoman Empire')
        self.assertEqual(france['metric_id'], 'scenario.foreign_diplomacy_ai')
        self.assertEqual(france['inputs']['policy'], 'mediate')
        french_mediation = next(row for row in france['inputs']['candidates']
                                if row['candidate'] == 'mediation_offer')
        self.assertTrue(french_mediation['selected'])
        self.assertGreaterEqual(france['inputs']['treasury_cash'], 20.0)
        self.assertLess(france['inputs']['domestic_protest'], 6.0)
        self.assertEqual(britain['inputs']['policy'], 'intervene')
        intervention = next(row for row in britain['inputs']['candidates']
                            if row['candidate'] == 'intervene_to_collect_claim')
        self.assertTrue(intervention['selected'])
        self.assertEqual(britain['cause_event_ids'], [france['event_id']])
        self.assertEqual(ottoman['inputs']['policy'], 'offer_mediation')
        self.assertEqual(ottoman['cause_event_ids'], [britain['event_id']])
        self.assertEqual(traced_decisions['Ottoman Empire'], 'offer_mediation')

        crisis['french_policy'] = 'abstain'
        crisis['british_policy'] = 'observe'
        crisis['french_commitment'] = 'none'
        crisis['french_authorization'] = {
            'demonstrate': False, 'blockade': False, 'bombard': False}
        crisis['reasons'] = {}
        crisis['history'] = []
        world['scenario_state']['creditor_news'] = []
        del tile._run_trace
        del tile._collective_trace_clock
        with patch('scenario_diplomacy._energy', return_value=1.0):
            plain_decisions = foreign_decisions(world)
            plain_state = _policy_state(world)
        self.assertEqual(traced_decisions, plain_decisions)
        self.assertEqual(traced_state, plain_state)

    def test_offer_reply_records_valuation_formula_and_policy_link(self):
        world, trace, _tile = _fixture()
        crisis = world['scenario_state']['diplomatic_crisis']
        crisis['egyptian_proposal'] = 'mediation'
        crisis['proposal_due_turn'] = world['turn']

        with patch('scenario_diplomacy._energy', return_value=1.0):
            advance(world, world['turn'], lambda *_args: None)

        british_evaluation = next(row for row in trace.rows
                                  if row.get('kind') == 'scenario_diplomacy_ai_decision'
                                  and row['subject']['id'] == 'Britain'
                                  and row['inputs']['decision'] == 'assess_creditor_crisis')
        offer_reply = next(row for row in trace.rows
                           if row.get('kind') == 'scenario_diplomacy_ai_decision'
                           and row['inputs']['decision'] == 'evaluate_diplomatic_offer')
        self.assertEqual(offer_reply['formula_id'],
                         'scenario.british_offer_value.v1')
        self.assertEqual(offer_reply['cause_event_ids'],
                         [british_evaluation['event_id']])
        self.assertIn('military_value', offer_reply['inputs'])
        self.assertIn('treaty_value', offer_reply['inputs'])
        self.assertEqual(sum(candidate['selected'] for candidate in
                             offer_reply['inputs']['candidates']), 1)
        self.assertIn((world.get('scenario_warning_modal') or {}).get('kind'),
                      ('french_terms', None))


if __name__ == '__main__':
    unittest.main()

import json
import unittest
from types import SimpleNamespace

from diplomacy import DiplomacySystem, TreatyType
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'diplomacy-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _world(names, *, traced=True, strengths=None, cash=None):
    strengths = strengths or {}
    cash = cash or {}
    recorder = MemoryTrace()
    clock = {'turn': 5, 'phase': 'strategy', 'next': 1}
    nations = []
    for name in names:
        tile = SimpleNamespace(name=f'{name}-capital', agents=[])
        if traced:
            tile._run_trace = recorder
            tile._collective_trace_clock = clock
        treasury_agent = SimpleNamespace(
            id=f'{name}-treasury', cash=float(cash.get(name, 100.0)))
        nation = SimpleNamespace(
            name=name, tiles=[tile], currency=f'{name[:2].upper()}',
            regime_type='autocracy', ruling_faction='Ruling',
            military_units=[SimpleNamespace(
                strength=float(strengths.get(name, 0.0)))] if strengths.get(name, 0.0)
            else [],
            government=SimpleNamespace(agent=treasury_agent))
        nations.append(nation)
    return {'nations': nations}, recorder


class DiplomacyActionTraceTests(unittest.TestCase):
    def setUp(self):
        self.world, self.trace = _world(['Alpha', 'Beta'])
        self.nations = {nation.name: nation for nation in self.world['nations']}
        self.diplomacy = DiplomacySystem()

    def test_tracing_does_not_change_treaty_or_war_state(self):
        outcomes = []
        for traced in (False, True):
            world, _trace = _world(['A', 'B'], traced=traced)
            diplomacy = DiplomacySystem()
            diplomacy.set_relation('A', 'B', 0.4)
            accepted, _ = diplomacy.propose_treaty(
                'A', 'B', TreatyType.TRADE_PACT.value, t=1,
                _trace_world=world)
            diplomacy.set_relation('A', 'B', -0.7)
            events = diplomacy.declare_war(
                'A', 'B', t=2, nations={n.name: n for n in world['nations']})
            outcomes.append((accepted, diplomacy.get_relation('A', 'B'),
                             tuple(sorted(diplomacy.active_wars)),
                             tuple(tr.status for tr in diplomacy.treaties),
                             [event['event'] for event in events]))
        self.assertEqual(outcomes[0], outcomes[1])

    def test_treaty_accept_reject_break_and_cancel_records_reasons_and_effects(self):
        self.diplomacy.set_relation('Alpha', 'Beta', -0.3)
        rejected, _ = self.diplomacy.propose_treaty(
            'Alpha', 'Beta', TreatyType.TRADE_PACT.value, t=1,
            _trace_world=self.world)
        self.assertFalse(rejected)
        rejected_gate = next(row for row in self.trace.rows
                             if row.get('kind') == 'diplomacy_treaty_decision')
        self.assertEqual(rejected_gate['inputs']['reason_code'],
                         'relation_below_threshold')
        self.assertAlmostEqual(rejected_gate['inputs']['relation_threshold'], -0.2)
        self.assertEqual(self.diplomacy.treaties, [])

        self.diplomacy.set_relation('Alpha', 'Beta', -0.1)
        accepted, _ = self.diplomacy.propose_treaty(
            'Alpha', 'Beta', TreatyType.TRADE_PACT.value, t=2,
            _trace_world=self.world)
        self.assertTrue(accepted)
        signed = next(row for row in self.trace.rows
                      if row.get('kind') == 'diplomacy_treaty_signed')
        self.assertEqual(signed['before'], 'absent')
        self.assertEqual(signed['after'], 'active')
        self.assertEqual(signed['inputs']['relation_before'], -0.1)
        self.assertAlmostEqual(signed['inputs']['relation_after'], 0.05)
        signed_gate = next(row for row in self.trace.rows
                           if row.get('kind') == 'diplomacy_treaty_decision'
                           and row['inputs']['reason_code'] == 'accepted')
        self.assertEqual(signed['cause_event_ids'], [signed_gate['event_id']])

        broken = self.diplomacy.break_treaty(
            'Alpha', 'Beta', TreatyType.TRADE_PACT.value, t=3,
            reason='border dispute', _trace_world=self.world)
        self.assertTrue(broken['success'])
        broken_row = next(row for row in self.trace.rows
                          if row.get('kind') == 'diplomacy_treaty_broken')
        self.assertEqual(broken_row['before'], 'active')
        self.assertEqual(broken_row['after'], 'broken')
        self.assertEqual(broken_row['inputs']['betrayal_count_after'], 1)
        self.assertAlmostEqual(self.diplomacy.get_relation('Alpha', 'Beta'), -0.3)

        self.diplomacy.set_relation('Alpha', 'Beta', 0.5)
        accepted_nap, _ = self.diplomacy.propose_treaty(
            'Alpha', 'Beta', TreatyType.NON_AGGRESSION.value, t=4,
            _trace_world=self.world)
        self.assertTrue(accepted_nap)
        relation_before_cancel = self.diplomacy.get_relation('Alpha', 'Beta')
        cancelled = self.diplomacy.cancel_treaty(
            'Alpha', 'Beta', TreatyType.NON_AGGRESSION.value, t=5,
            reason='review', _trace_world=self.world)
        self.assertTrue(cancelled['success'])
        cancelled_row = next(row for row in self.trace.rows
                             if row.get('kind') == 'diplomacy_treaty_cancelled')
        self.assertFalse(cancelled_row['inputs']['betrayal_memory_created'])
        self.assertEqual(self.diplomacy.get_relation('Alpha', 'Beta'),
                         relation_before_cancel)
        self.assertEqual(len(self.diplomacy.betrayal_memory[('Beta', 'Alpha')]), 1)
        self._assert_catalogued(self.trace.rows)

    def test_war_records_broken_treaties_and_defensive_alliance_calls(self):
        world, trace = _world(['Aggressor', 'Target', 'Ally'])
        nations = {nation.name: nation for nation in world['nations']}
        diplomacy = DiplomacySystem()
        diplomacy.set_relation('Target', 'Ally', 0.8)
        signed, _ = diplomacy.propose_treaty(
            'Target', 'Ally', TreatyType.DEFENSIVE_ALLIANCE.value, t=1,
            _trace_world=world)
        self.assertTrue(signed)
        diplomacy.set_relation('Aggressor', 'Target', -0.8)

        events = diplomacy.declare_war(
            'Aggressor', 'Target', t=2, reason='border claim',
            nations=nations)

        self.assertEqual(len(events), 2)
        self.assertTrue(diplomacy.are_at_war('Aggressor', 'Target'))
        self.assertTrue(diplomacy.are_at_war('Aggressor', 'Ally'))
        declared = next(row for row in trace.rows
                        if row.get('kind') == 'diplomacy_war_declared')
        gate = next(row for row in trace.rows
                    if row.get('kind') == 'diplomacy_war_decision')
        self.assertEqual(declared['cause_event_ids'], [gate['event_id']])
        ally_decision = next(row for row in trace.rows
                             if row.get('kind') ==
                             'diplomacy_alliance_call_decision')
        ally_result = next(row for row in trace.rows
                           if row.get('kind') == 'diplomacy_alliance_called')
        self.assertEqual(ally_decision['after'], True)
        self.assertEqual(ally_decision['inputs']['defensive_treaty_ids'],
                         [diplomacy.get_active_treaties(
                             'Target', 'Ally')[0].treaty_id])
        self.assertEqual(ally_result['cause_event_ids'],
                         [ally_decision['event_id']])
        self.assertEqual(
            [row for row in trace.rows
             if row.get('kind') == 'diplomacy_war_outcome'][0]['inputs']
            ['alliance_calls_joined'], ['Ally'])

        duplicate_events = diplomacy.declare_war(
            'Aggressor', 'Target', t=3, nations=nations)
        self.assertEqual(duplicate_events, [])
        duplicate_gate = [row for row in trace.rows
                          if row.get('kind') == 'diplomacy_war_decision'][-1]
        self.assertEqual(duplicate_gate['inputs']['reason_code'], 'already_at_war')
        self._assert_catalogued(trace.rows)

    def test_peace_timing_response_and_reparation_cash_legs_are_traced(self):
        world, trace = _world(
            ['Victor', 'Defeated'], strengths={'Victor': 70, 'Defeated': 10},
            cash={'Victor': 100, 'Defeated': 100})
        nations = {nation.name: nation for nation in world['nations']}
        diplomacy = DiplomacySystem()
        diplomacy.declare_war('Victor', 'Defeated', t=1, nations=nations)
        offered = diplomacy.propose_peace(
            'Victor', 'Defeated', t=2, _trace_world=world)
        self.assertTrue(offered['success'])
        duplicate_offer = diplomacy.propose_peace(
            'Victor', 'Defeated', t=2, _trace_world=world)
        self.assertFalse(duplicate_offer['success'])
        early_reply = diplomacy.respond_peace(
            'Defeated', 'Victor', True, t=2, _trace_world=world)
        self.assertFalse(early_reply['success'])
        early_gate = [row for row in trace.rows
                      if row.get('kind') ==
                      'diplomacy_peace_response_decision'][-1]
        self.assertEqual(early_gate['inputs']['reason_code'],
                         'reply_must_be_next_turn')

        accepted = diplomacy.respond_peace(
            'Defeated', 'Victor', True, t=3, _trace_world=world)
        self.assertTrue(accepted['success'])
        self.assertFalse(diplomacy.are_at_war('Victor', 'Defeated'))
        self.assertEqual(nations['Defeated'].government.agent.cash, 100.0)
        first_peace = [row for row in trace.rows
                       if row.get('kind') == 'diplomacy_peace_signed'][-1]
        self.assertEqual(first_peace['inputs']['reparations']['reason_code'],
                         'mechanic_world_not_supplied')

        diplomacy.declare_war('Victor', 'Defeated', t=4, nations=nations)
        direct_peace = diplomacy.sign_peace(
            'Victor', 'Defeated', t=5, world=world)
        self.assertTrue(direct_peace['success'])
        self.assertEqual(nations['Defeated'].government.agent.cash, 60.0)
        self.assertEqual(nations['Victor'].government.agent.cash, 140.0)
        paid = next(row for row in trace.rows
                    if row.get('kind') == 'war_reparations_paid')
        received = next(row for row in trace.rows
                        if row.get('kind') == 'war_reparations_received')
        self.assertEqual(paid['after'], -40.0)
        self.assertEqual(received['after'], 40.0)
        self.assertEqual(paid['inputs']['cash_balance_before'], 100.0)
        self.assertEqual(paid['inputs']['cash_balance_after'], 60.0)
        self.assertEqual(received['inputs']['cash_balance_before'], 100.0)
        self.assertEqual(received['inputs']['cash_balance_after'], 140.0)
        self.assertEqual(paid['inputs']['operation_id'],
                         received['inputs']['operation_id'])
        gate = [row for row in trace.rows
                if row.get('kind') == 'diplomacy_reparations_amount_decision'][-1]
        self.assertEqual(paid['cause_event_ids'], [gate['event_id']])
        self._assert_catalogued(trace.rows)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

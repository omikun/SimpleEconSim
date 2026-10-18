"""Causal records for capitalist planner activation and cadence gates."""

import json
import unittest
from types import SimpleNamespace

from economy.capitalist_planner import EliteCapitalistPlanner
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'elite-gate-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Actor:
    def __init__(self, agent_id, *, lord=True, inventory=None):
        self.id = agent_id
        self.is_lord = lord
        self.is_corporation = False
        self.cash = 0.0
        self._inventory = inventory or {}

    def inv_get(self, good, default=0):
        return self._inventory.get(good, default)


class ElitePlanningGateTraceTests(unittest.TestCase):
    def make_region(self, *, turn=7, goods=(), actor=None, traced=True):
        actor = actor or Actor(17)
        region = SimpleNamespace(
            name='TraceMarket', goods=list(goods), agents=[actor],
            supply_proposal_events=[], concession_events=[])
        trace = MemoryTrace()
        if traced:
            region._run_trace = trace
            region._collective_trace_clock = {
                'turn': turn, 'phase': 'local', 'next': 1}
        return region, actor, trace

    def test_new_market_good_triggers_and_links_planning_gate(self):
        planner = EliteCapitalistPlanner()
        region, actor, trace = self.make_region(
            goods=['cotton'], actor=Actor(17, inventory={'cotton': 2}))

        self.assertTrue(planner.check_new_market_items(region))
        self.assertTrue(planner.should_run_planning(actor, region, 7, True))

        scan, gate = trace.rows
        self.assertEqual(scan['kind'], 'elite_market_novelty_scan')
        self.assertEqual(scan['metric_id'], 'market.elite_market_novelty')
        self.assertEqual(scan['after'], 1)
        self.assertEqual(scan['inputs']['new_goods'], ['cotton'])
        self.assertEqual(gate['kind'], 'elite_planning_gate')
        self.assertEqual(gate['metric_id'], 'market.elite_planning_gate')
        self.assertEqual(gate['after'], 1)
        self.assertEqual(gate['inputs']['reason'], 'new_market_item')
        self.assertEqual(gate['cause_event_ids'], [scan['event_id']])

        actor._inventory['cotton'] = 0
        self.assertFalse(planner.check_new_market_items(region))
        self.assertEqual(trace.rows[-1]['inputs']['removed_goods'], ['cotton'])
        actor._inventory['cotton'] = 2
        self.assertTrue(planner.check_new_market_items(region))
        self.assertEqual(trace.rows[-1]['inputs']['new_goods'], ['cotton'])

    def test_gate_records_each_existing_trigger_and_cadence_reason(self):
        cases = (
            (7, {'turn': 7, 'buyer_id': 17, 'proposal_id': 'p-1',
                 'kind': 'advance_offtake', 'status': 'settled'},
             None, False, True, 'same_turn_supply_proposal'),
            (7, None, {'turn': 7, 'sponsor_id': 17, 'petition_id': 'c-1',
                       'status': 'enacted'},
             False, True, 'same_turn_concession'),
            (10, None, None, False, True, 'five_turn_cadence'),
            (8, None, None, False, False, 'not_due'),
        )
        for turn, supply_event, concession_event, market_new, expected, reason in cases:
            with self.subTest(reason=reason):
                planner = EliteCapitalistPlanner()
                region, actor, trace = self.make_region(turn=turn, goods=())
                if supply_event:
                    region.supply_proposal_events.append(supply_event)
                if concession_event:
                    region.concession_events.append(concession_event)
                self.assertFalse(planner.check_new_market_items(region))

                self.assertEqual(
                    planner.should_run_planning(actor, region, turn, market_new), expected)
                gate = trace.rows[-1]
                self.assertEqual(gate['inputs']['reason'], reason)
                self.assertEqual(gate['after'], int(expected))
                if supply_event or concession_event:
                    self.assertEqual(gate['inputs']['matched_trigger']['status'],
                                     (supply_event or concession_event)['status'])

    def test_trace_does_not_change_novelty_or_cadence_results(self):
        results = []
        for traced in (False, True):
            planner = EliteCapitalistPlanner()
            region, actor, _ = self.make_region(
                goods=['grain'], actor=Actor(17, inventory={'grain': 1}),
                traced=traced)
            first_scan = planner.check_new_market_items(region)
            first_gate = planner.should_run_planning(actor, region, 1, first_scan)
            second_scan = planner.check_new_market_items(region)
            second_gate = planner.should_run_planning(actor, region, 1, second_scan)
            results.append((first_scan, first_gate, second_scan, second_gate))
        self.assertEqual(results, [(True, True, False, False)] * 2)

    def test_metric_catalog_covers_planner_gates_and_existing_strategy_events(self):
        for metric_id in ('market.supply_strategy', 'market.elite_market_novelty',
                          'market.elite_planning_gate',
                          'market.elite_planner_phase_gate'):
            with self.subTest(metric_id=metric_id):
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_scenario_owner_policy_suppression_is_explicit(self):
        planner = EliteCapitalistPlanner()
        region, _, trace = self.make_region()
        region.scenario_owner_policy = True

        planner.record_planning_phase_gate(region, 7, planning_enabled=False)

        event = trace.rows[-1]
        self.assertEqual(event['metric_id'], 'market.elite_planner_phase_gate')
        self.assertEqual(event['after'], 0)
        self.assertEqual(event['inputs']['reason'], 'scenario_owner_policy')
        self.assertTrue(event['inputs']['scenario_owner_policy'])


if __name__ == '__main__':
    unittest.main()

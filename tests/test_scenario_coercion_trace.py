"""Causal tracing for the reusable scenario naval-coercion module."""

import json
import unittest
from types import SimpleNamespace

from scenarios.modules.coercion import CoercionModule


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"coercion-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, trace_enabled, cash=10.0, stage='blockaded', turn=4,
             due_turn=0):
    trace = MemoryTrace()
    tile = SimpleNamespace(name='Port', agents=[])
    if trace_enabled:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': turn, 'phase': 'scenario', 'next': 1}
    treasury = SimpleNamespace(id='aggressor-treasury', cash=cash)
    aggressor = SimpleNamespace(
        name='Aggressor', currency='GBP', tiles=[tile],
        government=SimpleNamespace(agent=treasury))
    crisis = {
        'stage': stage, 'reason': 'test', 'squadron_strength': 80.0,
        'battery_strength': 28.0, 'reinforcement_strength': 40.0,
        'upkeep_per_turn': 8.0, 'max_protest_energy': 6.5,
        'due_turn': due_turn, 'historical_parallel': True,
    }
    world = {
        'tiles': [tile], 'nations': [aggressor],
        'scenario_state': {'scenario_id': 'test_scenario',
                           'naval_crisis': crisis},
    }
    module = CoercionModule('naval_coercion', {})
    tickers = []
    module.advance_turn(
        world, turn, lambda *args: tickers.append(args),
        {'aggressor_nation': aggressor, 'player_nation': None})
    return world, trace, treasury, tickers


def _state(fixture):
    world, _trace, treasury, tickers = fixture
    return (treasury.cash, dict(world['scenario_state']['naval_crisis']),
            world.get('playing'), world.get('scenario_warning_modal'),
            [(entry[1], entry[2], entry[3], entry[4]) for entry in tickers])


class ScenarioCoercionTraceTests(unittest.TestCase):
    def test_blockade_upkeep_records_expense_and_trace_is_state_neutral(self):
        plain = _fixture(trace_enabled=False, cash=10.0)
        traced = _fixture(trace_enabled=True, cash=10.0)

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(plain[2].cash, 2.0)
        event = next(row for row in traced[1].rows
                     if row.get('metric_id') == 'military.fleet_upkeep')
        self.assertEqual(event['unit'], 'GBP')
        self.assertEqual(event['before'], 0.0)
        self.assertEqual(event['after'], 8.0)
        self.assertEqual(event['inputs']['reason'], 'upkeep_paid')
        self.assertEqual(event['inputs']['treasury_cash_before'], 10.0)
        self.assertEqual(event['inputs']['treasury_cash_after'], 2.0)
        self.assertFalse(event['inputs']['expense_counterparty_modeled'])
        self.assertEqual(event['inputs']['accounting_treatment'],
                         'military_operating_expense_sink')

    def test_insolvency_records_unpaid_upkeep_and_links_withdrawal(self):
        plain = _fixture(trace_enabled=False, cash=3.0)
        traced = _fixture(trace_enabled=True, cash=3.0)

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(plain[2].cash, 3.0)
        self.assertEqual(plain[0]['scenario_state']['naval_crisis']['stage'],
                         'withdrawn')
        event = next(row for row in traced[1].rows
                     if row.get('metric_id') == 'military.fleet_upkeep')
        self.assertEqual(event['after'], 0.0)
        self.assertEqual(event['inputs']['cash_shortfall'], 5.0)
        self.assertEqual(event['inputs']['reason'],
                         'treasury_cash_below_upkeep')
        transition = next(row for row in traced[1].rows
                          if row.get('metric_id') ==
                          'scenario.naval_crisis_stage')
        self.assertEqual(transition['before'], 'blockaded')
        self.assertEqual(transition['after'], 'withdrawn')
        self.assertEqual(transition['cause_event_ids'], [event['event_id']])
        self.assertEqual(transition['inputs']['withdrawal_cause'],
                         'insolvency')

    def test_due_mobilization_traces_force_comparison_and_stage_change(self):
        plain = _fixture(trace_enabled=False, cash=20.0,
                         stage='mobilizing', due_turn=4)
        traced = _fixture(trace_enabled=True, cash=20.0,
                          stage='mobilizing', due_turn=4)

        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(plain[2].cash, 20.0)
        transition = next(row for row in traced[1].rows
                          if row.get('metric_id') ==
                          'scenario.naval_crisis_stage')
        self.assertEqual(transition['before'], 'mobilizing')
        self.assertEqual(transition['after'], 'ultimatum')
        self.assertEqual(transition['inputs']['reason'], 'mobilization_due')
        self.assertAlmostEqual(transition['inputs']['force_ratio'],
                               80.0 / 28.0)
        self.assertEqual(traced[0]['scenario_warning_modal']['kind'],
                         'naval_ultimatum')


if __name__ == '__main__':
    unittest.main()

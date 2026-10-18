"""Causal coverage for regime coup eligibility and force-ratio decisions."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from regime import step_regime


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"coup-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _world(*, traced, legitimacy=0.2, general=True, units=(), gov_cash=10.0):
    agents = []
    if general:
        agents.append(SimpleNamespace(
            id='general-1', alive=True, is_corporation=False,
            is_government=False, ambition=0.6, charisma=0.6, loyalty=0.6,
            cash=0.0, region='Capital', age=lambda _turn: 30,
            mem_push=lambda *_args: None))
    tile = SimpleNamespace(
        name='Capital', agents=agents,
        gov=SimpleNamespace(agent=SimpleNamespace(cash=0.0)))
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 5, 'phase': 'regime', 'next': 1}
    nation = SimpleNamespace(
        name='Test Republic', legitimacy=legitimacy,
        regime_type='autocracy', ruling_faction='Incumbent',
        tiles=[tile], military_units=list(units),
        government=SimpleNamespace(agent=SimpleNamespace(cash=gov_cash)),
        regime_log=[], _last_election=0)
    return nation, trace, agents[0] if agents else None


class CoupDecisionTraceTests(unittest.TestCase):
    def test_force_decision_is_reconstructable_and_trace_neutral(self):
        loyal = SimpleNamespace(
            unit_id='palace-guard', region_name='Barracks', soldiers=10,
            morale=1.0, strength=20.0)
        defector = SimpleNamespace(
            unit_id='mutinous-unit', region_name='Barracks', soldiers=3,
            morale=0.2, strength=3.0)
        worlds = [
            _world(traced=False, units=(loyal, defector)),
            _world(traced=True, units=(
                SimpleNamespace(**vars(loyal)),
                SimpleNamespace(**vars(defector))))]
        outcomes = []
        for nation, _trace, _general in worlds:
            with patch('regime.track_legitimacy'), patch(
                    'labor_politics.evaluate_uprising_pressure',
                    return_value=[]):
                events = step_regime(nation, 5, rng=0.5)
            outcomes.append((
                events, nation.regime_type, nation.legitimacy,
                nation.ruling_faction, nation._last_election))
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[0][0], [])

        row = next(row for row in worlds[1][1].rows
                   if row.get('kind') == 'coup_check')
        self.assertEqual(row['metric_id'], 'politics.coup_decision')
        self.assertEqual(row['formula_id'], 'coup.force_balance.v1')
        self.assertFalse(row['after'])
        inputs = row['inputs']
        self.assertEqual(inputs['reason_code'], 'loyalist_force_holds')
        self.assertEqual(inputs['general_id'], 'general-1')
        self.assertEqual(inputs['candidate_scores'][0]['weighted_score'], 0.6)
        self.assertEqual(inputs['defector_units'][0]['unit_id'],
                         'mutinous-unit')
        self.assertEqual(inputs['loyalist_units'][0]['unit_id'],
                         'palace-guard')
        self.assertAlmostEqual(inputs['general_trait_force'], 15.0)
        self.assertAlmostEqual(inputs['defector_force'], 3.0)
        self.assertAlmostEqual(inputs['conspirator_force'], 18.0)
        self.assertAlmostEqual(inputs['loyalist_unit_force'], 20.0)
        self.assertAlmostEqual(inputs['treasury_guard_force'], 2.0)
        self.assertAlmostEqual(inputs['legitimacy_defense_force'], 6.0)
        self.assertAlmostEqual(inputs['loyalist_force'], 28.0)
        self.assertAlmostEqual(inputs['force_margin'], -10.0)
        self.assertEqual(inputs['rng_draw'], 0.5)
        self.assertEqual(inputs['rng_margin'], 0.0)

    def test_legitimacy_and_candidate_gates_are_named(self):
        cases = [
            (0.5, True, 'legitimacy_above_trigger'),
            (0.2, False, 'no_eligible_general'),
        ]
        for legitimacy, has_general, reason in cases:
            with self.subTest(reason=reason):
                nation, trace, _general = _world(
                    traced=True, legitimacy=legitimacy, general=has_general)
                with patch('regime.track_legitimacy'), patch(
                        'labor_politics.evaluate_uprising_pressure',
                        return_value=[]):
                    step_regime(nation, 5, rng=0.25)
                row = next(row for row in trace.rows
                           if row.get('kind') == 'coup_check')
                self.assertEqual(row['inputs']['reason_code'], reason)
                self.assertFalse(row['after'])
                self.assertEqual(row['inputs']['rng_draw'], 0.25)

    def test_successful_force_comparison_preserves_coup_execution(self):
        nation, trace, general = _world(
            traced=True, gov_cash=0.0,
            units=())
        general.ambition = 1.0
        general.charisma = 1.0
        general.loyalty = 1.0
        general.cash = 100.0

        events = step_regime(nation, 5, rng=0.5)

        row = next(row for row in trace.rows
                   if row.get('kind') == 'coup_check')
        self.assertTrue(row['after'])
        self.assertEqual(row['inputs']['reason_code'],
                         'conspirators_overmatch')
        self.assertGreater(row['inputs']['conspirator_force'],
                           row['inputs']['loyalist_force'])
        self.assertEqual(events[0]['kind'], 'coup')
        self.assertEqual(nation.regime_type, 'autocracy')
        self.assertEqual(nation.legitimacy, 0.3)
        self.assertIsNone(nation.ruling_faction)


if __name__ == '__main__':
    unittest.main()

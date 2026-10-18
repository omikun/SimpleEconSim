"""Causal coverage for popular-front takeover and garrison decisions."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from unrest import _takeover


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"takeover-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


class Resident:
    def __init__(self, agent_id='worker'):
        self.id = agent_id
        self.is_corporation = False
        self.is_government = False
        self.hungry_steps = 1
        self.memory = []

    def mem_push(self, name, value):
        self.memory.append((name, value))


def _world(*, traced, legitimacy=0.0, units=(), protest=5.0,
           regime='democracy', owner=True, faction=True):
    resident = Resident()
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='Mill Town', agents=[resident], military_units=list(units),
        protest_energy_log=[protest],
        factions=SimpleNamespace(factions={}))
    if owner:
        region.owner_nation = SimpleNamespace(
            name='Republic', legitimacy=legitimacy, regime_type=regime)
    else:
        region.owner_nation = None
    if faction:
        leader = SimpleNamespace(
            name='Popular Front', kind='political',
            total_grievance=lambda: 3.0)
        region.factions.factions['Popular Front'] = leader
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 9, 'phase': 'unrest', 'next': 1}
    return region, trace, resident


class TakeoverDecisionTraceTests(unittest.TestCase):
    def test_zero_probability_gate_records_why_no_draw_was_used(self):
        region, trace, _resident = _world(
            traced=True, legitimacy=1.0)

        with patch('unrest.rand.random') as draw:
            result = _takeover(region, 9, mob=8)

        self.assertFalse(result)
        draw.assert_not_called()
        row = next(row for row in trace.rows
                   if row.get('metric_id') == 'politics.takeover_decision')
        self.assertEqual(row['kind'], 'takeover_attempt_failed')
        self.assertFalse(row['after'])
        self.assertEqual(row['inputs']['reason_code'],
                         'attempt_chance_zero')
        self.assertEqual(row['inputs']['legitimacy_pressure'], 0.0)
        self.assertEqual(row['inputs']['attempt_chance'], 0.0)
        self.assertIsNone(row['inputs']['attempt_draw'])

    def test_garrison_repulsion_records_force_casualties_and_protest(self):
        unit = SimpleNamespace(
            unit_id='state-guard', soldiers=10, morale=1.0,
            strength=100.0)
        worlds = [
            _world(traced=False, units=(unit,)),
            _world(traced=True, units=(SimpleNamespace(**vars(unit)),))]
        states = []
        for region, _trace, resident in worlds:
            with patch('unrest.rand.random', side_effect=[0.1, 0.5]):
                result = _takeover(region, 9, mob=1)
            states.append((result, region.owner_nation.legitimacy,
                           region.protest_energy_log[-1], resident.memory))
        self.assertEqual(states[0], states[1])
        self.assertFalse(states[0][0])
        self.assertEqual(states[0][2], 2.5)

        decision = next(row for row in worlds[1][1].rows
                        if row.get('metric_id') ==
                        'politics.takeover_decision')
        self.assertEqual(decision['inputs']['reason_code'],
                         'garrison_repels_mob')
        self.assertEqual(decision['inputs']['garrison_units'][0]['unit_id'],
                         'state-guard')
        self.assertAlmostEqual(decision['inputs']['garrison_force'], 100.0)
        self.assertEqual(decision['inputs']['seeded_casualty_agent_ids'],
                         ['worker'])
        self.assertEqual(decision['inputs']['seeded_casualty_count'], 1)
        protest = next(row for row in worlds[1][1].rows
                       if row.get('kind') == 'garrison_repels_takeover')
        self.assertEqual(protest['metric_id'], 'politics.protest_energy')
        self.assertEqual(protest['before'], 5.0)
        self.assertEqual(protest['after'], 2.5)

    def test_success_records_regime_and_legitimacy_outcome(self):
        region, trace, _resident = _world(
            traced=True, legitimacy=0.0, units=(), protest=9.0)

        with patch('unrest.rand.random', return_value=0.1):
            result = _takeover(region, 9, mob=8)

        self.assertTrue(result)
        self.assertEqual(region.owner_nation.legitimacy, 0.0)
        self.assertEqual(region.owner_nation.regime_type, 'autocracy')
        decision = next(row for row in trace.rows
                        if row.get('metric_id') ==
                        'politics.takeover_decision')
        self.assertTrue(decision['after'])
        self.assertEqual(decision['inputs']['reason_code'],
                         'no_garrison_defense')
        self.assertEqual(decision['inputs']['leading_grievance_faction'],
                         'Popular Front')
        self.assertEqual(decision['inputs']['new_regime'], 'autocracy')
        legitimacy = next(row for row in trace.rows
                          if row.get('kind') == 'takeover_succeeded')
        self.assertEqual(legitimacy['metric_id'], 'politics.legitimacy')

    def test_ownerless_takeover_check_is_explained(self):
        region, trace, _resident = _world(traced=True, owner=False)

        self.assertFalse(_takeover(region, 9, mob=2))

        decision = next(row for row in trace.rows
                        if row.get('metric_id') ==
                        'politics.takeover_decision')
        self.assertEqual(decision['inputs']['reason_code'], 'no_nation_owner')
        self.assertFalse(decision['after'])


if __name__ == '__main__':
    unittest.main()

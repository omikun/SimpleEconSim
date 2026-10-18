import json
import unittest
from types import SimpleNamespace

from agent import Agent
from labor_politics import evaluate_uprising_pressure
from metric_catalog import METRICS, TRACE_INSTRUMENTED
from region import Region


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, strikers=20, unrest=0.5,
             ruling='Bourgeoisie', military_strength=50.0,
             ten_hour_act=False, factory_safety_act=False):
    tile = Region('Mill Town', t=0, number_of_agents=0)
    tile.unrest_level = float(unrest)
    tile.police_employed = 0
    workers = []
    for agent_id in range(1, 21):
        worker = Agent(agent_id)
        worker.alive = True
        worker.social_class = 'proletarian'
        worker.is_striking = agent_id <= strikers
        worker.class_consciousness = 0.3
        workers.append(worker)
    tile.agents.extend(workers)

    units = ([SimpleNamespace(name='Garrison', soldiers=50, morale=0.9,
                              strength=float(military_strength))]
             if military_strength is not None else [])
    nation = SimpleNamespace(
        name='Mill Republic', tiles=[tile], ruling_faction=ruling,
        military_units=units, ten_hour_act=bool(ten_hour_act),
        factory_safety_act=bool(factory_safety_act),
        max_workday_hours=10.0 if ten_hour_act else 16.0,
        legitimacy=0.6, regime_log=[])
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 5, 'phase': 'labor_politics', 'next': 1}
    return nation, tile, workers, trace


def _state(fixture):
    nation, tile, workers, _trace = fixture
    return (nation.ten_hour_act, nation.factory_safety_act,
            nation.max_workday_hours, nation.legitimacy,
            tile.unrest_level, tuple(worker.is_striking for worker in workers),
            bool(getattr(tile, 'truck_act_enacted', False)),
            bool(getattr(tile, 'factory_safety_act', False)))


class UprisingPressureTraceTests(unittest.TestCase):
    def test_below_threshold_records_inputs_and_no_action(self):
        fixture = _fixture(traced=True, strikers=2, unrest=0.2,
                           military_strength=None)

        events = evaluate_uprising_pressure(fixture[0], 5)

        self.assertEqual(events, [])
        gate = self._row(fixture, 'uprising_pressure_gate')
        response = self._row(fixture, 'uprising_response_decision')
        outcome = self._row(fixture, 'uprising_response_outcome')
        self.assertFalse(gate['after'])
        self.assertEqual(gate['inputs']['worker_count'], 20)
        self.assertEqual(gate['inputs']['striker_count'], 2)
        self.assertAlmostEqual(gate['inputs']['strike_rate'], 0.1)
        self.assertFalse(gate['inputs']['class_consciousness_used_in_gate'])
        self.assertEqual(response['after'], 'no_crisis')
        self.assertEqual(outcome['after'], 'no_action')
        self._assert_catalogued(fixture[3].rows)

    def test_armed_strikebreaking_records_force_decision_and_changes(self):
        traced = _fixture(traced=True, strikers=20, unrest=0.5,
                          military_strength=50.0)
        plain = _fixture(traced=False, strikers=20, unrest=0.5,
                         military_strength=50.0)

        traced_events = evaluate_uprising_pressure(traced[0], 5)
        plain_events = evaluate_uprising_pressure(plain[0], 5)

        self.assertEqual([row['kind'] for row in traced_events],
                         [row['kind'] for row in plain_events])
        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(traced[1].unrest_level, 0.35)
        self.assertFalse(any(worker.is_striking for worker in traced[2]))
        gate = self._row(traced, 'uprising_pressure_gate')
        decision = self._row(traced, 'uprising_response_decision')
        strikes = self._row(traced, 'uprising_strikebreaking_tile_effect')
        unrest = self._row(traced, 'uprising_strikebreaking_unrest_effect')
        outcome = self._row(traced, 'uprising_response_outcome')
        self.assertTrue(gate['after'])
        self.assertEqual(decision['after'], 'armed_strikebreaking')
        self.assertEqual(decision['inputs']['military_strength_eligible'], 50.0)
        self.assertEqual(decision['inputs']['strike_force'], 30.0)
        self.assertEqual(decision['cause_event_ids'], [gate['event_id']])
        self.assertEqual(strikes['before'], 20)
        self.assertEqual(strikes['after'], 0)
        self.assertEqual(strikes['cause_event_ids'], [decision['event_id']])
        self.assertEqual(unrest['before'], 0.5)
        self.assertEqual(unrest['after'], 0.35)
        self.assertEqual(outcome['after'], 'armed_strikebreaking_applied')
        self._assert_catalogued(traced[3].rows)

    def test_strikes_force_concession_and_trace_unrest_legitimacy(self):
        traced = _fixture(traced=True, strikers=20, unrest=0.5,
                          ruling='Proletariat', military_strength=None)
        plain = _fixture(traced=False, strikers=20, unrest=0.5,
                         ruling='Proletariat', military_strength=None)

        traced_events = evaluate_uprising_pressure(traced[0], 5)
        plain_events = evaluate_uprising_pressure(plain[0], 5)

        self.assertEqual([row['kind'] for row in traced_events],
                         [row['kind'] for row in plain_events])
        self.assertEqual(_state(traced), _state(plain))
        self.assertTrue(traced[0].ten_hour_act)
        self.assertAlmostEqual(traced[1].unrest_level, 0.25)
        self.assertAlmostEqual(traced[0].legitimacy, 0.75)
        decision = self._row(traced, 'uprising_response_decision')
        unrest = self._row(traced, 'uprising_concession_unrest_effect')
        legitimacy = self._row(traced, 'uprising_concession_legitimacy_effect')
        outcome = self._row(traced, 'uprising_response_outcome')
        self.assertEqual(decision['after'], 'ten_hour_act_concession')
        self.assertEqual(unrest['before'], 0.5)
        self.assertEqual(unrest['after'], 0.25)
        self.assertEqual(legitimacy['before'], 0.6)
        self.assertEqual(legitimacy['after'], 0.75)
        self.assertEqual(outcome['after'], 'ten_hour_act_concession_applied')
        self.assertIn(decision['event_id'], outcome['cause_event_ids'])
        self.assertIn(unrest['event_id'], outcome['cause_event_ids'])
        self._assert_catalogued(traced[3].rows)

    def test_second_crisis_forces_factory_safety_concession(self):
        fixture = _fixture(traced=True, strikers=20, unrest=0.5,
                           ruling='Proletariat', military_strength=None,
                           ten_hour_act=True)

        events = evaluate_uprising_pressure(fixture[0], 5)

        self.assertEqual([row['kind'] for row in events],
                         ['factory_safety_concession'])
        self.assertTrue(fixture[0].factory_safety_act)
        self.assertTrue(fixture[1].factory_safety_act)
        self.assertAlmostEqual(fixture[1].unrest_level, 0.3)
        self.assertAlmostEqual(fixture[0].legitimacy, 0.7)
        decision = self._row(fixture, 'uprising_response_decision')
        outcome = self._row(fixture, 'uprising_response_outcome')
        self.assertEqual(decision['after'], 'factory_safety_concession')
        self.assertEqual(outcome['after'], 'factory_safety_concession_applied')
        self._assert_catalogued(fixture[3].rows)

    def test_no_remaining_concession_is_logged_when_laws_already_active(self):
        fixture = _fixture(traced=True, strikers=20, unrest=0.5,
                           ruling='Proletariat', military_strength=None,
                           ten_hour_act=True, factory_safety_act=True)

        events = evaluate_uprising_pressure(fixture[0], 5)

        self.assertEqual(events, [])
        decision = self._row(fixture, 'uprising_response_decision')
        outcome = self._row(fixture, 'uprising_response_outcome')
        self.assertEqual(decision['after'], 'no_additional_concession_available')
        self.assertEqual(outcome['after'], 'no_additional_concession_available')
        self.assertFalse(outcome['inputs']['response_applied'])
        self.assertEqual(fixture[1].unrest_level, 0.5)

    def _row(self, fixture, kind):
        return next(row for row in fixture[3].rows
                    if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

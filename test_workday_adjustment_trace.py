import json
import unittest
from types import SimpleNamespace

from labor_politics import adjust_workday_hours
from metric_catalog import METRICS, TRACE_INSTRUMENTED


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _faction(support):
    return SimpleNamespace(support=float(support))


def _fixture(*, cap=12.0, traced=True, protest=2.0):
    corp = SimpleNamespace(id='mill', is_corporation=True, shift_hours=16.0)
    worker = SimpleNamespace(id='worker', is_corporation=False, shift_hours=8.0)
    factions = {'Labor': _faction(0.5), 'Peasant': _faction(0.8),
                'Bourgeoisie': _faction(0.4)}
    tile = SimpleNamespace(
        name='Mill District', max_workday_hours=float(cap),
        workday_cap=float(cap), ten_hour_act=cap <= 10.0,
        agents=[corp, worker], factions=SimpleNamespace(factions=factions),
        protest_energy_log=[float(protest)])
    nation = SimpleNamespace(name='Agraria', max_workday_hours=float(cap),
                             ten_hour_act=cap <= 10.0, tiles=[tile])
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 7, 'phase': 'policy_action', 'next': 1}
    return nation, tile, corp, worker, factions, trace


def _state(fixture):
    nation, tile, corp, worker, _factions, _trace = fixture
    factions = tile.factions.factions
    return (nation.max_workday_hours, nation.ten_hour_act,
            tile.max_workday_hours, tile.workday_cap, tile.ten_hour_act,
            corp.shift_hours, worker.shift_hours,
            tuple((name, faction.support) for name, faction in factions.items()),
            tuple(tile.protest_energy_log))


class WorkdayAdjustmentTraceTests(unittest.TestCase):
    def test_shorter_workday_traces_shift_caps_and_prolabor_support_changes(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        result_plain = adjust_workday_hours(plain[0], -2.0)
        result_traced = adjust_workday_hours(traced[0], -2.0)

        self.assertEqual(result_plain, result_traced)
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[0].max_workday_hours, 10.0)
        self.assertEqual(traced[2].shift_hours, 10.0)
        self.assertAlmostEqual(traced[4]['Labor'].support, 0.6)
        self.assertAlmostEqual(traced[4]['Peasant'].support, 0.9)
        self.assertAlmostEqual(traced[4]['Bourgeoisie'].support, 0.32)
        gate = self._row(traced, 'workday_adjustment_gate')
        tile_effect = self._row(traced, 'workday_tile_limit_outcome')
        shift = self._row(traced, 'workday_corporate_shift_outcome')
        outcome = self._row(traced, 'workday_adjustment_outcome')
        faction_rows = [row for row in traced[5].rows
                        if row.get('kind') == 'workday_faction_support_outcome']
        self.assertTrue(gate['after'])
        self.assertEqual(tile_effect['before'], 12.0)
        self.assertEqual(tile_effect['after'], 10.0)
        self.assertEqual(shift['before'], 16.0)
        self.assertEqual(shift['after'], 10.0)
        self.assertEqual(len(faction_rows), 3)
        self.assertEqual(outcome['after'], 10.0)
        self.assertEqual(outcome['cause_event_ids'][0], gate['event_id'])
        self._assert_catalogued(traced[5].rows)

    def test_longer_workday_records_protest_increase_and_corporate_limit(self):
        fixture = _fixture(cap=14.0, protest=2.0)
        fixture[2].shift_hours = 17.0

        ok, _message = adjust_workday_hours(fixture[0], 2.0)

        self.assertTrue(ok)
        self.assertEqual(fixture[0].max_workday_hours, 16.0)
        self.assertEqual(fixture[2].shift_hours, 16.0)
        self.assertEqual(fixture[1].protest_energy_log[-1], 3.5)
        protest = self._row(fixture, 'workday_protest_energy_outcome')
        self.assertEqual(protest['before'], 2.0)
        self.assertEqual(protest['after'], 3.5)
        gate = self._row(fixture, 'workday_adjustment_gate')
        self.assertFalse(gate['inputs']['clamped_by_statutory_limit'])

    def test_boundary_attempt_is_traced_as_noop(self):
        fixture = _fixture(cap=8.0)
        before = _state(fixture)

        ok, message = adjust_workday_hours(fixture[0], -2.0)

        self.assertFalse(ok)
        self.assertIn('minimum', message)
        self.assertEqual(_state(fixture), before)
        gate = self._row(fixture, 'workday_adjustment_gate')
        outcome = self._row(fixture, 'workday_adjustment_outcome')
        self.assertFalse(gate['after'])
        self.assertFalse(outcome['inputs']['applied'])

    def _row(self, fixture, kind):
        return next(row for row in fixture[5].rows if row.get('kind') == kind)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

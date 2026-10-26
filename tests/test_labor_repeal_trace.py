import json
import unittest
from types import SimpleNamespace

from labor_politics import repeal_labor_laws
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


def _fixture(*, traced=True, workday_active=True, safety_active=True):
    firm = SimpleNamespace(id='Mill Co', is_corporation=True,
                           shift_hours=10.0, wage=1.0)
    tile = SimpleNamespace(
        name='Mill District', agents=[firm],
        max_workday_hours=10.0 if workday_active else 16.0,
        workday_cap=10.0 if workday_active else 16.0,
        ten_hour_act=bool(workday_active),
        factory_safety_act=bool(safety_active))
    nation = SimpleNamespace(
        name='Industrial Republic', tiles=[tile],
        ten_hour_act=bool(workday_active),
        max_workday_hours=10.0 if workday_active else 16.0,
        factory_safety_act=bool(safety_active),
        statute_of_laborers=True, maximum_wage_cap=1.2,
        truck_act_enacted=True)
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 8, 'phase': 'regime_change', 'next': 1}
    return nation, tile, firm, trace


def _state(fixture):
    nation, tile, firm, _trace = fixture
    return (nation.ten_hour_act, nation.max_workday_hours,
            nation.factory_safety_act, tile.ten_hour_act,
            tile.max_workday_hours, tile.workday_cap,
            tile.factory_safety_act, firm.shift_hours, firm.wage,
            nation.statute_of_laborers, nation.maximum_wage_cap,
            nation.truck_act_enacted)


class LaborRepealTraceTests(unittest.TestCase):
    def test_repeal_logs_declared_laws_and_stale_enforcement_state(self):
        traced = _fixture()
        plain = _fixture(traced=False)

        result = repeal_labor_laws(traced[0])
        plain_result = repeal_labor_laws(plain[0])

        self.assertEqual(result, plain_result)
        self.assertEqual(_state(traced), _state(plain))
        self.assertEqual(len(result['repealed']), 2)
        self.assertFalse(traced[0].ten_hour_act)
        self.assertEqual(traced[0].max_workday_hours, 16.0)
        self.assertFalse(traced[0].factory_safety_act)
        # Current repeal only changes max_workday_hours; lower-level caps,
        # tile flag, and the firm's actual shift stay at their old values.
        self.assertEqual(traced[1].workday_cap, 10.0)
        self.assertTrue(traced[1].ten_hour_act)
        self.assertEqual(traced[2].shift_hours, 10.0)
        self.assertTrue(traced[0].statute_of_laborers)
        self.assertEqual(traced[0].maximum_wage_cap, 1.2)
        self.assertTrue(traced[0].truck_act_enacted)

        decision = self._row(traced, 'labor_law_repeal_decision')
        workday = self._row(traced, 'labor_law_repeal_workday_tile_outcome')
        shift = self._row(traced, 'labor_law_repeal_firm_shift_unchanged')
        safety = self._row(traced, 'labor_law_repeal_safety_tile_outcome')
        outcome = self._row(traced, 'labor_law_repeal_outcome')
        self.assertTrue(decision['after'])
        self.assertEqual(workday['before'], 10.0)
        self.assertEqual(workday['after'], 16.0)
        self.assertEqual(workday['inputs']['workday_cap_after'], 10.0)
        self.assertTrue(workday['inputs']['tile_ten_hour_act_after'])
        self.assertEqual(shift['before'], 10.0)
        self.assertEqual(shift['after'], 10.0)
        self.assertEqual(safety['before'], True)
        self.assertEqual(safety['after'], False)
        self.assertTrue(outcome['inputs']['other_laws_active_but_not_repealed']
                        ['statute_of_laborers_active'])
        self.assertTrue(outcome['inputs']['other_laws_active_but_not_repealed']
                        ['anti_truck_act_active'])
        self._assert_catalogued(traced[3].rows)

    def test_no_supported_laws_gate_records_other_active_laws(self):
        fixture = _fixture(workday_active=False, safety_active=False)

        result = repeal_labor_laws(fixture[0])

        self.assertEqual(result['repealed'], [])
        decision = self._row(fixture, 'labor_law_repeal_decision')
        outcome = self._row(fixture, 'labor_law_repeal_outcome')
        self.assertFalse(decision['after'])
        self.assertEqual(outcome['after'], 'no_supported_laws_to_repeal')
        self.assertTrue(decision['inputs']['other_laws_active_but_not_handled']
                        ['statute_of_laborers_active'])
        self._assert_catalogued(fixture[3].rows)

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

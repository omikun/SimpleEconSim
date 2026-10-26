import json
import unittest
from types import SimpleNamespace

from labor_politics import enact_trade_quarantine, repeal_trade_quarantine
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


def _fixture(*, traced=True):
    routes = [SimpleNamespace(id='route-north', is_quarantined=False),
              SimpleNamespace(id='route-south', is_quarantined=True)]
    labor = SimpleNamespace(support=0.8)
    bourgeoisie = SimpleNamespace(support=0.5)
    factions = {'Labor': labor, 'Bourgeoisie': bourgeoisie}
    tile = SimpleNamespace(
        name='Port', routes={f'route-{index}': route
                             for index, route in enumerate(routes)},
        factions=SimpleNamespace(factions=factions), quarantine_active=False)
    nation = SimpleNamespace(name='Agraria', tiles=[tile],
                             quarantine_active=False)
    trace = MemoryTrace()
    if traced:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 6, 'phase': 'policy_action', 'next': 1}
    return nation, tile, routes, factions, trace


def _state(fixture):
    nation, tile, routes, factions, _trace = fixture
    return (nation.quarantine_active, tile.quarantine_active,
            tuple(route.is_quarantined for route in routes),
            tuple((name, faction.support) for name, faction in factions.items()))


class TradeQuarantineTraceTests(unittest.TestCase):
    def test_enactment_and_repeal_trace_routes_and_faction_effects(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        self.assertEqual(enact_trade_quarantine(plain[0]),
                         enact_trade_quarantine(traced[0]))
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(_state(traced)[:3], (True, True, (True, True)))
        self.assertAlmostEqual(traced[3]['Labor'].support, 0.9)
        self.assertAlmostEqual(traced[3]['Bourgeoisie'].support, 0.35)
        route_rows = [row for row in traced[4].rows
                      if row.get('kind') == 'trade_route_quarantine_outcome']
        self.assertEqual(len(route_rows), 2)
        self.assertTrue(all(row['after'] for row in route_rows))
        enact_outcome = next(row for row in traced[4].rows
                             if row.get('kind') == 'trade_quarantine_action_outcome')
        self.assertEqual(enact_outcome['inputs']['routes_quarantined'], 2)

        self.assertEqual(repeal_trade_quarantine(plain[0]),
                         repeal_trade_quarantine(traced[0]))
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(_state(traced)[:3], (False, False, (False, False)))
        self.assertAlmostEqual(traced[3]['Labor'].support, 0.9)
        self.assertAlmostEqual(traced[3]['Bourgeoisie'].support, 0.45)
        repeal_rows = [row for row in traced[4].rows
                       if row.get('kind') == 'trade_route_quarantine_repeal_outcome']
        self.assertEqual(len(repeal_rows), 2)
        self.assertTrue(all(row['after'] is False for row in repeal_rows))
        self._assert_catalogued(traced[4].rows)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

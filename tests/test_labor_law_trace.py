import json
import unittest
from types import SimpleNamespace

from labor_politics import (enact_factory_safety_act,
                            enact_statute_of_laborers,
                            repeal_statute_of_laborers)
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


def _fixture(*, traced=True):
    firm = SimpleNamespace(id='mill', is_corporation=True, wage=2.0)
    low_wage_firm = SimpleNamespace(id='handloom', is_corporation=True, wage=1.0)
    labor = _faction(0.8)
    peasant = _faction(0.6)
    gentry = _faction(0.2)
    bourgeoisie = _faction(0.4)
    factions = {'Labor': labor, 'Peasant': peasant, 'Gentry': gentry,
                'Bourgeoisie': bourgeoisie}
    first = SimpleNamespace(
        name='North', agents=[firm, low_wage_firm],
        factions=SimpleNamespace(factions=factions),
        statute_of_laborers=False, factory_safety_act=False)
    second = SimpleNamespace(name='South', agents=[],
                             factions=SimpleNamespace(factions={}),
                             statute_of_laborers=False,
                             factory_safety_act=False)
    nation = SimpleNamespace(name='Agraria', tiles=[first, second],
                             statute_of_laborers=False,
                             factory_safety_act=False,
                             maximum_wage_cap=None)
    trace = MemoryTrace()
    if traced:
        first._run_trace = trace
        first._collective_trace_clock = {
            'turn': 8, 'phase': 'policy_action', 'next': 1}
    return nation, [first, second], [firm, low_wage_firm], factions, trace


def _state(fixture):
    nation, tiles, firms, factions, _trace = fixture
    return (nation.statute_of_laborers, nation.maximum_wage_cap,
            nation.factory_safety_act,
            tuple((tile.statute_of_laborers, tile.maximum_wage_cap
                   if hasattr(tile, 'maximum_wage_cap') else None,
                   tile.factory_safety_act) for tile in tiles),
            tuple(firm.wage for firm in firms),
            tuple((name, faction.support) for name, faction in factions.items()))


class LaborLawTraceTests(unittest.TestCase):
    def test_wage_cap_enactment_and_repeal_trace_distributional_effects(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        enact_result = enact_statute_of_laborers(plain[0], 1.2)
        traced_enact_result = enact_statute_of_laborers(traced[0], 1.2)
        self.assertEqual(enact_result, traced_enact_result)
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual(traced[2][0].wage, 1.2)
        self.assertEqual(traced[2][1].wage, 1.0)
        self.assertAlmostEqual(traced[3]['Gentry'].support, 0.35)
        self.assertAlmostEqual(traced[3]['Labor'].support, 0.6)
        wage_event = next(row for row in traced[4].rows
                          if row.get('kind') == 'statute_of_laborers_firm_wage_cap')
        enact_outcome = next(row for row in traced[4].rows
                             if row.get('kind') ==
                             'statute_of_laborers_action_outcome')
        self.assertEqual(wage_event['before'], 2.0)
        self.assertEqual(wage_event['after'], 1.2)
        self.assertEqual(enact_outcome['inputs']['firms_capped'], 1)
        self.assertAlmostEqual(enact_outcome['inputs']['total_wage_reduction'], 0.8)

        repeal_result = repeal_statute_of_laborers(plain[0])
        traced_repeal_result = repeal_statute_of_laborers(traced[0])
        self.assertEqual(repeal_result, traced_repeal_result)
        self.assertEqual(_state(plain), _state(traced))
        self.assertFalse(traced[0].statute_of_laborers)
        self.assertEqual(traced[0].maximum_wage_cap, 1.2)
        self.assertEqual(traced[2][0].wage, 1.2)
        repeal = next(row for row in traced[4].rows
                      if row.get('kind') == 'statute_of_laborers_repeal_outcome')
        self.assertFalse(repeal['inputs']['wages_restored'])
        self.assertEqual(repeal['inputs']['target_wage_cap_value_retained'], 1.2)
        self._assert_catalogued(traced[4].rows)

    def test_factory_safety_mandate_traces_all_tile_flags(self):
        fixture = _fixture()

        ok, _message = enact_factory_safety_act(fixture[0])

        self.assertTrue(ok)
        self.assertTrue(fixture[0].factory_safety_act)
        self.assertTrue(all(tile.factory_safety_act for tile in fixture[1]))
        rows = [row for row in fixture[4].rows
                if row.get('kind') == 'factory_safety_tile_state_outcome']
        self.assertEqual({row['subject']['id'] for row in rows}, {'North', 'South'})
        self.assertTrue(all(row['after'] for row in rows))
        self._assert_catalogued(fixture[4].rows)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

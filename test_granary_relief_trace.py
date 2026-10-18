import json
import unittest
from types import SimpleNamespace

from agent import Agent
from goods import Goods
from labor_politics import emergency_granary_relief
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


def _agent(agent_id, *, hungry_steps=2, alive=True, food=0):
    agent = Agent(0)
    agent.id = agent_id
    agent.alive = alive
    agent.hungry_steps = hungry_steps
    agent.inv_add(Goods.food, food)
    return agent


def _tile(name, *, stock=10.0, famine=0, agents=(), treasury_food=99.0):
    return SimpleNamespace(
        name=name, granary_stock=float(stock), famine_outbreak_turns=famine,
        agents=list(agents),
        gov=SimpleNamespace(food_inventory=float(treasury_food)))


def _fixture(*, traced=True):
    first = _tile('North', agents=[_agent('north-1')], famine=3)
    second = _tile('South', agents=[_agent('south-1'), _agent('south-2')])
    nation = SimpleNamespace(name='Agraria', tiles=[first, second])
    trace = MemoryTrace()
    if traced:
        first._run_trace = trace
        first._collective_trace_clock = {
            'turn': 12, 'phase': 'policy_action', 'next': 1}
    return nation, [first, second], trace


def _state(fixture):
    nation, tiles, _trace = fixture
    return (tuple((tile.granary_stock, tile.famine_outbreak_turns,
                   tile.gov.food_inventory,
                   tuple((agent.hungry_steps, agent.inv_get(Goods.food, 0))
                         for agent in tile.agents)) for tile in tiles),
            nation.name)


class GranaryReliefTraceTests(unittest.TestCase):
    def test_trace_records_sequential_household_relief_and_cumulative_stock_draw(self):
        plain = _fixture(traced=False)
        traced = _fixture(traced=True)

        result_plain = emergency_granary_relief(plain[0], food_amount=2.0)
        result_traced = emergency_granary_relief(traced[0], food_amount=2.0)

        self.assertEqual(result_plain, result_traced)
        self.assertEqual(_state(plain), _state(traced))
        self.assertEqual([tile.granary_stock for tile in traced[1]], [9.5, 8.5])
        self.assertEqual([tile.famine_outbreak_turns for tile in traced[1]], [0, 0])
        self.assertTrue(all(tile.gov.food_inventory == 99.0 for tile in traced[1]))
        gates = [row for row in traced[2].rows
                 if row.get('kind') == 'national_granary_relief_tile_gate']
        households = [row for row in traced[2].rows
                      if row.get('kind') ==
                      'national_granary_relief_household_outcome']
        stocks = [row for row in traced[2].rows
                  if row.get('kind') == 'national_granary_stock_outcome']
        summary = next(row for row in traced[2].rows
                       if row.get('kind') == 'national_granary_relief_outcome')
        famine_reset = next(row for row in traced[2].rows
                            if row.get('kind') ==
                            'national_granary_famine_progression_reset')
        self.assertEqual([row['inputs']['recipient_count'] for row in gates], [1, 2])
        self.assertEqual(gates[1]['inputs']['cumulative_fed_before_tile'], 1)
        self.assertEqual([row['inputs']['actual_stock_draw'] for row in stocks],
                         [0.5, 1.5])
        self.assertEqual(len(households), 3)
        self.assertTrue(all(row['before'] == 2 and row['after'] == 0
                            for row in households))
        self.assertTrue(all(row['inputs']['food_inventory_changed'] is False
                            for row in households))
        self.assertEqual(famine_reset['before'], 3)
        self.assertEqual(famine_reset['after'], 0)
        self.assertEqual(summary['inputs']['households_fed'], 3)
        self.assertEqual(summary['inputs']['cumulative_grain_stock_debited'], 2.0)
        self.assertFalse(summary['inputs']['government_food_inventory_used'])
        self._assert_catalogued(traced[2].rows)

    def test_no_eligible_households_still_resets_famine_without_stock_draw(self):
        tile = _tile('Empty', stock=4.0, famine=2, agents=[])
        nation = SimpleNamespace(name='Agraria', tiles=[tile])
        trace = MemoryTrace()
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 5, 'phase': 'policy_action', 'next': 1}

        ok, _message = emergency_granary_relief(nation)

        self.assertTrue(ok)
        self.assertEqual(tile.granary_stock, 4.0)
        self.assertEqual(tile.famine_outbreak_turns, 0)
        gate = next(row for row in trace.rows
                    if row.get('kind') == 'national_granary_relief_tile_gate')
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'national_granary_relief_outcome')
        self.assertFalse(gate['after'])
        self.assertEqual(outcome['inputs']['households_fed'], 0)
        self.assertEqual(outcome['inputs']['cumulative_grain_stock_debited'], 0.0)

    def _assert_catalogued(self, rows):
        for row in rows:
            metric_id = row.get('metric_id')
            if metric_id:
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()

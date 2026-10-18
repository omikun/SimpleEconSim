import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from demographics_consumption import consume_goods
from goods import Goods


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, wood=5, furniture=3, multiplier=2.0):
    region = SimpleNamespace(name='Parish', _last_turn=9)
    agent = Agent(0)
    initialize_agent(agent, Goods.food, 0, 0, 0.0)
    agent.consumption_multiplier = multiplier
    agent.inv_set(Goods.wood, wood)
    agent.inv_set(Goods.furniture, furniture)
    trace = MemoryTrace()
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 9, 'phase': 'demographics', 'next': 1}
    ctx = SimpleNamespace(
        goods=[Goods.wood, Goods.furniture],
        profession={Goods.wood: 'wood', Goods.furniture: 'furniture'},
        source_region=region)
    return ctx, agent, region, trace


def _run(fixture):
    ctx, agent, _region, _trace = fixture
    return consume_goods(ctx, agent, 0, 0, 0)


class HouseholdNonfoodConsumptionTraceTests(unittest.TestCase):
    def test_wealth_drawdown_and_furniture_wear_record_inventory_reasons(self):
        traced = _fixture()
        plain = _fixture(traced=False)
        with patch('demographics_consumption.rand.random', return_value=0.01):
            result = _run(traced)
        with patch('demographics_consumption.rand.random', return_value=0.01):
            plain_result = _run(plain)

        self.assertEqual(result, plain_result)
        self.assertEqual(result, (0, 2, 2))
        self.assertEqual((traced[1].inv_get(Goods.wood, 0),
                          traced[1].inv_get(Goods.furniture, 0)), (3, 1))
        self.assertEqual((traced[1].inv_get(Goods.wood, 0),
                          traced[1].inv_get(Goods.furniture, 0)),
                         (plain[1].inv_get(Goods.wood, 0),
                          plain[1].inv_get(Goods.furniture, 0)))

        events = {row['subject']['good']: row for row in traced[3].rows
                  if row.get('kind') == 'household_nonfood_consumption'}
        self.assertEqual(set(events), {'wood', 'furniture'})
        wood = events['wood']
        self.assertEqual((wood['before'], wood['after'], wood['inputs']['units_consumed']),
                         (5, 3, 2))
        self.assertEqual([row['mechanism'] for row in
                          wood['inputs']['consumption_components']],
                         ['wealth_multiplier', 'wood_stockpile_drawdown'])
        self.assertEqual(wood['inputs']['consumption_components'][1]['stock_before'], 4)
        furniture = events['furniture']
        self.assertEqual((furniture['before'], furniture['after']), (3, 1))
        wear = furniture['inputs']['consumption_components'][1]
        self.assertEqual(wear['mechanism'], 'furniture_stochastic_wear')
        self.assertEqual(wear['random_draw'], 0.01)
        self.assertEqual(wear['consumption_threshold'], 0.066)

    def test_no_inventory_change_adds_no_nonfood_consumption_rows(self):
        fixture = _fixture(wood=2, furniture=0, multiplier=1.0)

        _run(fixture)

        self.assertFalse(any(row.get('kind') == 'household_nonfood_consumption'
                             for row in fixture[3].rows))

    def test_trace_does_not_change_random_draw_or_consumption_state(self):
        traced = _fixture()
        plain = _fixture(traced=False)
        with patch('demographics_consumption.rand.random', return_value=0.03):
            traced_result = _run(traced)
        with patch('demographics_consumption.rand.random', return_value=0.03):
            plain_result = _run(plain)

        self.assertEqual(traced_result, plain_result)
        self.assertEqual((traced[1].inv_get(Goods.wood, 0),
                          traced[1].inv_get(Goods.furniture, 0)),
                         (plain[1].inv_get(Goods.wood, 0),
                          plain[1].inv_get(Goods.furniture, 0)))


if __name__ == '__main__':
    unittest.main()

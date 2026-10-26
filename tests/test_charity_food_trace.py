"""Exact trace evidence for charity food distribution to households."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from charity import Charity
from goods import Goods


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f"charity-food-test:{clock['next']}"
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _agent(agent_id, *, hungry, age):
    person = Agent(agent_id)
    initialize_agent(person, Goods.food, 0, 0, 0.0)
    person.id = agent_id
    person.hungry_steps = hungry
    person.age = lambda _turn: age
    person.inv_set(Goods.food, 0)
    return person


def _fixture(*, traced, stock=2):
    people = [_agent(1, hungry=2, age=30),
              _agent(2, hungry=1, age=30),
              _agent(3, hungry=0, age=5)]
    trace = MemoryTrace()
    region = SimpleNamespace(name='Delta', agents=people,
                             home_currency='USD')
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {
            'turn': 8, 'phase': 'welfare', 'next': 1}
    charity = Charity('Delta', {Goods.food: {'price': 1.0}})
    charity.food_inventory = stock
    return charity, region, people, trace


def _state(charity, people):
    return (charity.food_inventory,
            [person.inv_get(Goods.food, 0) for person in people],
            dict(charity.log))


class CharityFoodTraceTests(unittest.TestCase):
    def test_recipient_transfers_and_summary_are_exact_and_trace_neutral(self):
        fixtures = [_fixture(traced=False), _fixture(traced=True)]
        states = []
        for charity, region, people, _trace in fixtures:
            with patch('charity.random.shuffle', side_effect=lambda values: None):
                charity.distribute_food(8, people, regions=(region,))
            states.append(_state(charity, people))

        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0][0], 0)
        self.assertEqual(states[0][1], [1, 0, 1])
        self.assertEqual(states[0][2]['food_distributed'], 2)

        rows = fixtures[1][3].rows
        transfers = [row for row in rows
                     if row.get('metric_id') ==
                     'goods.charity_food_distribution']
        self.assertEqual(len(transfers), 2)
        self.assertEqual([row['subject']['id'] for row in transfers],
                         ['1', '3'])
        self.assertEqual(transfers[0]['inputs']['recipient_group'], 'hungry')
        self.assertEqual(transfers[1]['inputs']['recipient_group'], 'young')
        self.assertEqual(
            (transfers[0]['inputs']['charity_inventory_before'],
             transfers[0]['inputs']['charity_inventory_after']), (2, 1))
        self.assertEqual(
            (transfers[0]['inputs']['recipient_inventory_before'],
             transfers[0]['inputs']['recipient_inventory_after']), (0, 1))
        summary = next(row for row in rows
                       if row.get('metric_id') == 'goods.charity_food_aid')
        self.assertEqual((summary['before'], summary['after']), (0, 2))
        self.assertEqual(summary['cause_event_ids'],
                         [row['event_id'] for row in transfers])
        self.assertEqual(summary['inputs']['food_inventory_before'], 2)
        self.assertEqual(summary['inputs']['food_inventory_after'], 0)

    def test_empty_charity_stock_does_not_emit_routine_noise(self):
        charity, region, people, trace = _fixture(traced=True, stock=0)

        charity.distribute_food(8, people, regions=(region,))

        self.assertEqual(trace.rows, [])
        self.assertEqual(_state(charity, people)[0], 0)

    def test_fractional_stock_is_carried_forward_without_overdraw(self):
        charity, region, people, trace = _fixture(traced=True, stock=0.5)

        charity.distribute_food(8, people, regions=(region,))

        self.assertEqual(charity.food_inventory, 0.5)
        self.assertEqual([person.inv_get(Goods.food, 0) for person in people],
                         [0, 0, 0])
        self.assertEqual(charity.log['food_distributed'], 0)
        self.assertEqual(trace.rows, [])


if __name__ == '__main__':
    unittest.main()

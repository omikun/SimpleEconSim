"""Occupation episodes and temporary statuses remain separate."""

import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from labor_choice import apply_career_switch
from region_logistics import make_trader_internal, exit_trader


class LivelihoodStatusTest(unittest.TestCase):
    def test_trader_round_trip_keeps_trade_and_food(self):
        region = SimpleNamespace(name='Delta', _last_turn=10, destination_region=None,
                                 routes={}, route=None, trader_agents=[], _run_trace=None)
        worker = Agent(0)
        initialize_agent(worker, Goods.wood, 0, 2, 10)
        worker.last_career_switch = 3
        before_food = worker.inv_get(Goods.food)
        make_trader_internal(region, worker)
        self.assertTrue(worker.is_trader)
        self.assertEqual(worker.primary_livelihood, Goods.wood)
        self.assertEqual(worker.last_career_switch, 3)
        self.assertEqual(worker.inv_get(Goods.food), before_food)
        exit_trader(region, worker)
        self.assertFalse(worker.is_trader)
        self.assertEqual(worker.output, Goods.wood)
        self.assertEqual(worker.primary_livelihood, Goods.wood)
        self.assertEqual(worker.last_career_switch, 3)

    def test_same_trade_noop_preserves_tenure(self):
        worker = Agent(0)
        initialize_agent(worker, Goods.food, 0, 0, 0)
        worker.last_career_switch = 4
        self.assertFalse(apply_career_switch(None, worker, Goods.food, 10))
        self.assertEqual(worker.last_career_switch, 4)
        self.assertTrue(apply_career_switch(None, worker, Goods.wood, 10,
                                            reason='voluntary'))
        self.assertEqual(worker.primary_livelihood, Goods.wood)
        self.assertEqual(worker.livelihood_started_turn, 10)
        self.assertEqual(worker.last_career_switch, 10)

    def test_child_has_no_occupation_before_entry(self):
        child = Agent(10)
        child.is_native_child = True
        initialize_agent(child, Goods.food, 0, 0, 0)
        self.assertIsNone(child.primary_livelihood)
        self.assertTrue(apply_career_switch(None, child, Goods.food, 24,
                                            reason='adult_entry'))
        self.assertEqual(child.primary_livelihood, Goods.food)


if __name__ == '__main__':
    unittest.main()

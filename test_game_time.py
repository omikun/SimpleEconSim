"""The agent lifecycle and seasonal production deliberately use different clocks."""

import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from demographics_consumption import transfer_dependent_food
from food_security import forecast_commons_food
from game_time import agent_elapsed_years, seasonal_cycle_phase, seasonal_cycle_year
from goods import Goods
from labor_choice import apply_career_switch, career_lifecycle_age, career_switch_hurdle_and_cooldown
from nutrition import appetite_units, update_dependent_need


class GameTimeTests(unittest.TestCase):
    def test_ten_turns_age_agent_ten_years_and_advance_one_seasonal_cycle(self):
        self.assertEqual(agent_elapsed_years(0, 10), 10)
        self.assertEqual(seasonal_cycle_phase(9), 9)
        self.assertEqual(seasonal_cycle_phase(10), 0)
        self.assertEqual(seasonal_cycle_year(9), 1)
        self.assertEqual(seasonal_cycle_year(10), 2)

    def test_scenario_adult_is_not_classified_as_child_by_birth_turn(self):
        adult = Agent(5)
        initialize_agent(adult, Goods.food, 0, 0, 0)
        self.assertFalse(adult.is_native_child)
        self.assertGreaterEqual(career_lifecycle_age(adult, 5), 18)

    def test_child_needs_grow_and_hunger_cannot_unlock_underage_hiring(self):
        child = Agent(5)
        initialize_agent(child, Goods.food, 0, 0, 0)
        child.is_native_child = True
        child.hungry_steps = 10
        update_dependent_need(child, 5)
        self.assertEqual(appetite_units(child), 2)
        update_dependent_need(child, 10)
        self.assertEqual(appetite_units(child), 3)
        self.assertEqual(career_switch_hurdle_and_cooldown(child, 10, is_emergency=True)[2], 0)
        update_dependent_need(child, 19)
        self.assertEqual(appetite_units(child), 4)

    def test_parent_food_transfer_conserves_units(self):
        parent = Agent(0)
        child = Agent(1)
        initialize_agent(parent, Goods.food, 0, 4, 0)
        initialize_agent(child, Goods.food, 0, 0, 0)
        child.is_native_child = True
        child.parent = parent
        parent.region = child.region = 'Home'
        update_dependent_need(child, 2)
        before = parent.inv_get(Goods.food, 0) + child.inv_get(Goods.food, 0)
        self.assertEqual(transfer_dependent_food([parent, child], 2), (2, 1))
        self.assertEqual(parent.inv_get(Goods.food, 0) + child.inv_get(Goods.food, 0), before)

    def test_food_forecast_does_not_count_child_as_forager(self):
        child = Agent(1)
        initialize_agent(child, Goods.food, 0, 0, 0)
        child.is_native_child = True
        self.assertEqual(forecast_commons_food(child, SimpleNamespace(_last_turn=2)), 0)

    def test_same_trade_mutation_preserves_tenure(self):
        worker = Agent(0)
        initialize_agent(worker, Goods.food, 0, 0, 0)
        worker.last_career_switch = 2
        self.assertFalse(apply_career_switch(None, worker, Goods.food, 10))
        self.assertEqual(worker.last_career_switch, 2)


if __name__ == '__main__':
    unittest.main()

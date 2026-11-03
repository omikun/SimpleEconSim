"""Food reserved for public relief remains physical until the next meal."""

import unittest

from demographics_consumption import consume_daily_food
from goods import Goods
from nutrition import (deficit_fraction, effective_calorie_need, queue_emergency_meal,
                       record_intake, starvation_hazard)


from agent import Agent, initialize_agent


class Household(Agent):
    def __init__(self, food=0):
        super().__init__(0)
        initialize_agent(self, Goods.food, 0, food, 0)
        self.energy_reserve_kcal = 40000.0

    @property
    def food(self):
        return self.inv_get(Goods.food, 0)


class NutritionReliefTests(unittest.TestCase):
    def test_child_aid_requires_a_complete_ration_in_local_stock(self):
        from government import Government
        from region import Region

        for stock, expected in ((0.5, 0), (1.5, 1)):
            with self.subTest(stock=stock):
                region = Region('Relief Parish', 0)
                government = Government('Relief', 0)
                child = Household()
                child.is_native_child = True
                child.age = lambda turn: 1
                government.add_food(region, stock)

                given = government.provide_food_aid(1, [child], 2, region)

                self.assertEqual(given, expected)
                self.assertEqual(child.food, expected)
                self.assertEqual(government.food_at(region), stock - expected)

    def test_depleted_body_slows_calorie_burn_and_starvation_hazard(self):
        person = Household()
        person.energy_reserve_kcal = 0
        self.assertEqual(effective_calorie_need(person), 1300)
        record_intake(person, 0)
        self.assertEqual(person.energy_reserve_kcal, 0)
        self.assertEqual(person.calorie_deficit_kcal, 1300)
        self.assertLess(starvation_hazard(person), 0.5)

    def test_starvation_adaptation_extends_reserve_runway(self):
        person = Household()
        for _ in range(22):
            record_intake(person, 0)
        self.assertGreater(person.energy_reserve_kcal, 0)
        self.assertLess(person.energy_reserve_kcal, 40000)

    def test_reserved_meal_is_eaten_once_next_turn(self):
        person = Household()
        queue_emergency_meal(person, 4)
        self.assertEqual(person.food, 4)
        self.assertEqual(person.emergency_food_units, 0)
        self.assertEqual(consume_daily_food(person), 4)
        self.assertEqual(deficit_fraction(person), 0)
        self.assertEqual(person.emergency_food_units, 0)
        self.assertEqual(consume_daily_food(person), 0)
        self.assertEqual(deficit_fraction(person), 1)

    def test_excess_reserved_food_returns_to_inventory(self):
        person = Household(food=2)
        queue_emergency_meal(person, 6)
        self.assertEqual(consume_daily_food(person), 4)
        self.assertEqual(person.food, 4)
        self.assertEqual(person.emergency_food_units, 0)


if __name__ == '__main__':
    unittest.main()

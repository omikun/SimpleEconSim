"""Food reserved for public relief remains physical until the next meal."""

import unittest

from demographics_consumption import consume_daily_food
from goods import Goods
from nutrition import deficit_fraction, queue_emergency_meal


class Household:
    def __init__(self, food=0):
        self.food = food
        self.emergency_food_units = 0
        self.consumption_multiplier = 1.0
        self.energy_reserve_kcal = 40000.0
        self.calorie_need_kcal = 2000.0
        self.hungry_steps = 0.0
        self.is_trader = False

    def inv_get(self, good, default=0):
        assert good == Goods.food
        return self.food

    def inv_add(self, good, amount):
        assert good == Goods.food
        self.food += amount

    def mem_push(self, *_args):
        pass


class NutritionReliefTests(unittest.TestCase):
    def test_reserved_meal_is_eaten_once_next_turn(self):
        person = Household()
        queue_emergency_meal(person, 4)
        self.assertEqual(person.emergency_food_units, 4)
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

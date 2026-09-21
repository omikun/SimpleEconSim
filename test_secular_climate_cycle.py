"""Unit tests for the Secular Climate Cycle (Medieval Warm Optimum vs Little Ice Age)."""

import unittest
from secular_climate import get_secular_climate, SECULAR_CYCLE_TURNS
from region import Region
from goods import Goods
from region_production import terrain_bonus


class TestSecularClimateCycle(unittest.TestCase):

    def test_climate_cycle_epochs(self):
        """Verify that secular climate correctly transitions across 80-turn multi-decade cycle."""
        # Peak Warm Optimum: turn 20
        c_warm = get_secular_climate(20)
        self.assertEqual(c_warm['epoch'], 'warm_optimum')
        self.assertAlmostEqual(c_warm['anomaly'], 0.50, places=2)
        self.assertGreater(c_warm['yield_multiplier'], 1.20)
        self.assertLess(c_warm['col_modifier'], 1.0)

        # Transition: turn 40
        c_trans = get_secular_climate(40)
        self.assertEqual(c_trans['epoch'], 'temperate')
        self.assertAlmostEqual(c_trans['anomaly'], 0.0, places=2)

        # Peak Little Ice Age: turn 60
        c_ice = get_secular_climate(60)
        self.assertEqual(c_ice['epoch'], 'ice_age')
        self.assertAlmostEqual(c_ice['anomaly'], -0.50, places=2)
        self.assertLess(c_ice['yield_multiplier'], 0.70)
        self.assertGreater(c_ice['col_modifier'], 1.10)

        # 80-turn periodicity
        c_cycle1 = get_secular_climate(10)
        c_cycle2 = get_secular_climate(10 + SECULAR_CYCLE_TURNS)
        self.assertAlmostEqual(c_cycle1['anomaly'], c_cycle2['anomaly'], places=4)
        self.assertAlmostEqual(c_cycle1['yield_multiplier'], c_cycle2['yield_multiplier'], places=4)

    def test_terrain_bonus_food_scaling(self):
        """Verify that food crop terrain yield is scaled by secular climate epoch."""
        r = Region("TestFields", 0, 0)
        r.terrain[Goods.food] = 1.0

        # In warm optimum (turn 20)
        yield_warm = terrain_bonus(r, Goods.food, t=20)
        # In little ice age (turn 60)
        yield_ice = terrain_bonus(r, Goods.food, t=60)

        self.assertGreater(yield_warm, yield_ice)
        self.assertGreater(yield_warm / yield_ice, 1.30)

        # Non-food good (e.g. wood) is not modulated by secular food climate
        r.terrain[Goods.wood] = 1.0
        wood_warm = terrain_bonus(r, Goods.wood, t=20)
        wood_ice = terrain_bonus(r, Goods.wood, t=60)
        self.assertEqual(wood_warm, wood_ice)

    def test_cost_of_living_anomaly(self):
        """Verify that Little Ice Age raises regional cost of living due to harsh winter heating."""
        r = Region("TestHaven", 0, 0)
        r.recipes[Goods.food]['price'] = 2.0
        r.recipes[Goods.wood]['price'] = 1.0
        r.recipes[Goods.furniture]['price'] = 1.0
        r.col_multiplier = 1.0

        r.step_economy(t=20)
        col_warm = r.cost_of_living

        r.step_economy(t=60)
        col_ice = r.cost_of_living

        self.assertGreater(col_ice, col_warm)


if __name__ == '__main__':
    unittest.main()

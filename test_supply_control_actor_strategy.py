"""Named actors and route in a normal seasonal engine step."""
import unittest

from goods import Goods
from scenario_labor_frontier_rivalry import create_world, step_world


class SupplyControlActorFixtureTests(unittest.TestCase):
    def test_two_growers_two_mills_and_route_survive_normal_tick(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        works = world['by_name']['Meridian Works']
        rival_works = world['by_name']['Vesper Works']
        growers = [a for a in fields.agents if a.output == Goods.cotton
                   and not a.is_corporation and getattr(a, 'alive', True)]
        mills = [a for r in (works, rival_works) for a in r.agents
                 if a.is_corporation and a.output == Goods.cloth]
        self.assertGreaterEqual(len(growers), 2)
        self.assertEqual(len(mills), 2)
        self.assertIn('Meridian Works', fields.routes)
        self.assertIn('Vesper Fields', fields.routes)
        named = [growers[0], growers[1], mills[0], mills[1]]
        before = {a.id: (a.cash, a.inv_get(a.output, 0)) for a in named}
        violations = step_world(world)
        self.assertFalse(violations)
        self.assertEqual(world['turn'], 1)
        for a in named:
            self.assertIn(a.id, before)
            self.assertTrue(any(person.id == a.id for person in
                                (fields if a in growers else works if a is mills[0]
                                 else rival_works).agents))

    def test_poor_water_year_reduces_named_plot_allocation(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        from supply_rights import allocate_seasonal_water
        normal = sum(allocate_seasonal_water(fields, 1).values())
        fields.seasonal_rainfall = 0.4
        drought = sum(allocate_seasonal_water(fields, 2).values())
        self.assertLess(drought, normal)


if __name__ == '__main__':
    unittest.main()

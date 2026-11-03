import unittest

from scripts.food_growth import analyze_growth


def period(start, population, farm, forage=0, need=None, prepared=0, **extras):
    return [dict(turn=t, population=population, production={'food': farm, 'prepared_food': prepared},
                 foraged_food=forage, basic_meal_demand=population * 4 if need is None else need,
                 underfed=0, **extras) for t in range(start, start + 20)]


class FoodGrowthTest(unittest.TestCase):
    def test_matching_growth_preserves_food_per_person_and_requires_a_streak(self):
        rows = sum((period(1 + 20 * i, 10 * 2 ** i, 40 * 2 ** i) for i in range(4)), [])
        result = analyze_growth(rows)
        self.assertTrue(result['sustained_alignment_while_both_growing'])
        self.assertEqual(result['longest_aligned_growth_streak'], 3)
        self.assertTrue(all(b['food_per_resident_turn'] == 4 for b in result['blocks']))
        self.assertFalse(result['blocks'][2]['sustained_alignment_while_both_growing'])

    def test_contraction_and_underfeeding_are_not_healthy_growth(self):
        rows = period(1, 20, 40) + period(21, 10, 20)
        block = analyze_growth(rows)['blocks'][-1]
        self.assertTrue(block['near_alignment'])
        self.assertFalse(block['aligned_while_both_growing'])
        self.assertEqual(block['gross_ordinary_need_coverage'], .5)

    def test_prepared_food_does_not_create_calories_and_unknown_costs_stay_unknown(self):
        block = analyze_growth(period(1, 10, 30, 10, prepared=100))['blocks'][0]
        self.assertEqual(block['gross_new_food_per_turn'], 40)
        self.assertEqual(block['gross_ordinary_need_coverage'], 1)
        self.assertIsNone(block['net_of_seed_and_storage_need_coverage'])

    def test_seed_and_storage_costs_can_turn_gross_surplus_into_a_deficit(self):
        block = analyze_growth(period(1, 10, 44, food_seed_use=4, food_storage_losses=2))['blocks'][0]
        self.assertEqual(block['gross_ordinary_need_coverage'], 1.1)
        self.assertEqual(block['net_of_seed_and_storage_need_coverage'], .95)

    def test_zero_production_baseline_and_extinction_have_no_infinite_growth(self):
        result = analyze_growth(period(1, 10, 0) + period(21, 0, 2))
        self.assertIsNone(result['blocks'][1]['farm_food_growth'])
        self.assertIsNone(result['blocks'][1]['food_per_person_growth'])
        self.assertFalse(result['blocks'][1]['near_alignment'])

    def test_complete_cycles_filter_harvest_spikes_and_partial_blocks(self):
        rows = period(1, 10, 0) + period(21, 10, 0) + period(41, 10, 0)[:5]
        for row in rows:
            row['production']['food'] = 200 if row['turn'] % 10 in (6, 7) else 0
        result = analyze_growth(rows)
        self.assertEqual(len(result['blocks']), 2)
        self.assertEqual(result['blocks'][1]['farm_food_growth'], 0)
        self.assertEqual(result['omitted_partial_block_turns'], list(range(41, 46)))
        with self.assertRaises(ValueError):
            analyze_growth(rows, window=7)
        with self.assertRaises(ValueError):
            analyze_growth(rows[1:3] + rows[4:])


if __name__ == '__main__':
    unittest.main()

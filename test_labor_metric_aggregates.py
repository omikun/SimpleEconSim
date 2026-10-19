import unittest
from types import SimpleNamespace

from labor_contract import FirmLaborStats, aggregate_tile_surplus


class TestLaborMetricAggregates(unittest.TestCase):
    def test_shift_and_exploitation_inputs_replay_aggregate(self):
        firms = [
            SimpleNamespace(
                id=11, is_corporation=True, employees=[object(), object()],
                shift_hours=10.0, machinery_level=2, broken_machinery=0,
                _latest_labor_stats=FirmLaborStats(
                    firm_id=11, num_workers=2, shift_hours=10.0,
                    safety_investment=0.0, machinery_level=2,
                    broken_machinery=0, variable_capital=20.0,
                    constant_capital=10.0, gross_output_value=70.0,
                    surplus_value=40.0, rate_of_exploitation=2.0)),
            SimpleNamespace(
                id=12, is_corporation=True, employees=[object()],
                shift_hours=6.0, machinery_level=1, broken_machinery=0,
                _latest_labor_stats=FirmLaborStats(
                    firm_id=12, num_workers=1, shift_hours=6.0,
                    safety_investment=0.0, machinery_level=1,
                    broken_machinery=0, variable_capital=40.0,
                    constant_capital=5.0, gross_output_value=55.0,
                    surplus_value=10.0, rate_of_exploitation=0.25)),
        ]
        stats = aggregate_tile_surplus(SimpleNamespace(agents=firms))

        shift_inputs = stats['avg_shift_hours_inputs']
        shift_replay = (shift_inputs['weighted_shift_hours_sum']
                        / shift_inputs['worker_count'])
        self.assertAlmostEqual(shift_replay, stats['avg_shift_hours'])
        self.assertAlmostEqual(stats['avg_shift_hours'], 26.0 / 3.0)

        exploitation_inputs = stats['exploitation_inputs']
        exploitation_replay = (
            exploitation_inputs['total_surplus_value']
            / exploitation_inputs['total_variable_capital'])
        self.assertAlmostEqual(exploitation_replay,
                               stats['avg_rate_of_exploitation'])
        self.assertAlmostEqual(stats['avg_rate_of_exploitation'], 50.0 / 60.0)
        self.assertEqual(len(shift_inputs['firms']), 2)
        self.assertTrue(all(row['included_in_rate']
                            for row in exploitation_inputs['firms']))

    def test_empty_metrics_record_explicit_fallbacks(self):
        stats = aggregate_tile_surplus(SimpleNamespace(agents=[]))
        self.assertEqual(stats['avg_shift_hours_inputs']['empty_value'], 8.0)
        self.assertEqual(stats['exploitation_inputs']['empty_value'], 0.0)
        self.assertEqual(stats['avg_shift_hours_inputs']['firms'], [])
        self.assertEqual(stats['exploitation_inputs']['firms'], [])


if __name__ == '__main__':
    unittest.main()

import unittest

from economic_shock_multiseed import paired_effect


class PairedSeedAggregationTests(unittest.TestCase):
    def test_missing_turns_are_coverage_gaps_not_zero_deltas(self):
        pair = {"comparison": {"market_response": [
            {"turn": 8, "tile": "c50", "good": "wood",
             "values": {"units_sold": {"treatment_minus_control": -4}}},
            {"turn": 9, "tile": "c50", "good": "wood",
             "values": {"units_sold": {"treatment_minus_control": None}}},
        ]}}
        result = paired_effect(pair, "wood", "units_sold", "sum",
                               start=8, end=9)
        self.assertEqual(result, {
            "effect": -4, "observed_turns": 1,
            "expected_turns": 2, "statistic": "sum",
        })

    def test_price_summary_uses_mean_of_observed_paired_deltas(self):
        pair = {"comparison": {"market_response": [
            {"turn": turn, "tile": "c50", "good": "furniture",
             "values": {"transaction_vwap": {
                 "treatment_minus_control": delta}}}
            for turn, delta in ((8, 1.0), (9, -0.5), (10, None))
        ]}}
        result = paired_effect(pair, "furniture", "transaction_vwap", "mean",
                               start=8, end=10)
        self.assertAlmostEqual(result["effect"], 0.25)
        self.assertEqual(result["observed_turns"], 2)
        self.assertEqual(result["expected_turns"], 3)

    def test_effect_uses_the_pair_recorded_active_target_tile(self):
        pair = {"target_tile": "c10", "comparison": {"market_response": [
            {"turn": 8, "tile": "c10", "good": "wood",
             "values": {"units_sold": {"treatment_minus_control": -3}}},
            {"turn": 8, "tile": "c50", "good": "wood",
             "values": {"units_sold": {"treatment_minus_control": 99}}},
        ]}}
        result = paired_effect(pair, "wood", "units_sold", "sum",
                               start=8, end=8)
        self.assertEqual(result["effect"], -3)
        self.assertEqual(result["observed_turns"], 1)


if __name__ == "__main__":
    unittest.main()

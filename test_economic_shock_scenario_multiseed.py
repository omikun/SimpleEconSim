import unittest

from economic_shock_scenario_multiseed import (
    market_window_effect,
    mill_order_summary,
    recovery_assessment,
)


def _market_row(turn, *, control=10, treatment=10, key="units_sold"):
    return {
        "tile": "Cotton Fields", "good": "cotton", "turn": turn,
        "values": {key: {"control": control, "treatment": treatment,
                         "treatment_minus_control": treatment - control}},
    }


class ScenarioMultiSeedTests(unittest.TestCase):
    def test_market_effect_keeps_missing_turns_out_of_sum(self):
        pair = {"comparison": {"market_response": [
            _market_row(8, control=10, treatment=8),
            _market_row(10, control=10, treatment=7),
        ]}}
        result = market_window_effect(
            pair, "Cotton Fields", "cotton", "units_sold", "sum")
        self.assertEqual(result["effect"], -5)
        self.assertEqual(result["observed_turns"], 2)
        self.assertEqual(result["expected_turns"], 4)

    def test_recovery_requires_three_observed_consecutive_turns(self):
        rows = [_market_row(turn, control=10, treatment=8)
                for turn in range(8, 12)]
        rows.extend(_market_row(turn, control=10, treatment=10)
                    for turn in range(12, 15))
        pair = {"comparison": {"market_response": rows}}
        result = recovery_assessment(
            pair, "cotton", "units_sold", "quantity")
        self.assertEqual(result["status"], "within_tolerance")
        self.assertEqual(result["recovery_turn"], 12)
        self.assertEqual(result["post_shock_observed_turns"], 3)
        self.assertEqual(result["post_shock_missing_turns"], list(range(15, 21)))

    def test_no_detectable_shock_response_is_not_reported_as_recovery(self):
        rows = [_market_row(turn) for turn in range(8, 21)]
        result = recovery_assessment(
            {"comparison": {"market_response": rows}},
            "cotton", "units_sold", "quantity")
        self.assertEqual(result["status"], "no_detectable_shock_response")
        self.assertIsNone(result["recovery_turn"])

    def test_mill_order_summary_uses_unshocked_target_and_actor_filter(self):
        run = {"scenario_mill_order_events": [
            {"turn": 8, "buyer_id": 47, "desired_target": 5,
             "unshocked_desired_target": 3, "submitted_quantity": 4,
             "target_override_applied": True},
            {"turn": 9, "buyer_id": 47, "desired_target": 2,
             "unshocked_desired_target": None, "submitted_quantity": 2,
             "target_override_applied": False},
            {"turn": 8, "buyer_id": 48, "desired_target": 8,
             "submitted_quantity": 9, "target_override_applied": False},
        ]}
        result = mill_order_summary(run, {47})
        self.assertEqual(result["order_events"], 2)
        self.assertEqual(result["desired_target_sum"], 7)
        self.assertEqual(result["unshocked_target_sum"], 5)
        self.assertEqual(result["target_uplift_sum"], 2)
        self.assertEqual(result["submitted_bid_units"], 6)
        self.assertEqual(result["override_events"], 1)


if __name__ == "__main__":
    unittest.main()

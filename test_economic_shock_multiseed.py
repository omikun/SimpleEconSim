import unittest

from economic_shock_multiseed import paired_effect, resident_cohort_effect


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

    def test_cross_seed_price_effect_is_currency_free_percent_change(self):
        pair = {"target_tile": "c59", "comparison": {"market_response": [
            {"turn": 8, "tile": "c59", "good": "wood",
             "currency": "USD",
             "values": {"transaction_vwap": {
                 "control": 2.0, "treatment": 2.2,
                 "treatment_minus_control": 0.2}}},
            {"turn": 9, "tile": "c59", "good": "wood",
             "currency": "USD",
             "values": {"transaction_vwap": {
                 "control": 4.0, "treatment": 3.0,
                 "treatment_minus_control": -1.0}}},
        ]}}
        result = paired_effect(pair, "wood", "transaction_vwap", "mean_percent",
                               start=8, end=9)
        self.assertAlmostEqual(result["effect"], -7.5)
        self.assertEqual(result["observed_turns"], 2)

    def test_fixed_resident_cohort_reports_paired_welfare_rates_and_coverage(self):
        roster = [{"actor_id": 1}, {"actor_id": 2}]

        def cohort(need_met, eaten, wage_recipients, cash_change_percent):
            observations = []
            for turn in range(8, 12):
                observations.append({
                    "turn": turn,
                    "baseline_member_count": 2,
                    "present_member_count": 2,
                    "alive_member_count": 2,
                    "need_observed_member_count": 2,
                    "need_met_member_count": need_met,
                    "calories_eaten_total_kcal": eaten,
                    "calorie_shortfall_total_kcal": 200,
                    "employer_linked_member_count": 1,
                    "median_cash_change_percent_from_turn7": cash_change_percent,
                    "cash_change_percent_member_coverage": 2,
                    "median_debt_change_as_baseline_cash_share": 0.0,
                    "debt_change_cash_share_member_coverage": 2,
                    "cash_wage_recipient_member_count": wage_recipients,
                    "scrip_wage_recipient_member_count": 0,
                })
            return {"roster": roster, "observations": observations}

        result = resident_cohort_effect({
            "default_resident_cohort": {
                "control": cohort(1, 3000, 1, 0.0),
                "treatment": cohort(2, 3600, 2, 2.0),
            }
        })

        self.assertTrue(result["available"])
        self.assertTrue(result["roster_matched"])
        self.assertAlmostEqual(
            result["treatment_minus_control"]["need_met_share"], 0.5)
        self.assertAlmostEqual(
            result["treatment_minus_control"][
                "calories_eaten_per_need_person_turn"], 300.0)
        self.assertAlmostEqual(
            result["treatment_minus_control"][
                "cash_wage_recipient_share_of_living_person_turns"], 0.5)
        self.assertAlmostEqual(
            result["treatment_minus_control"][
                "cash_change_percent_from_turn7_at_t11"], 2.0)
        self.assertEqual(result["control"]["present_person_turns"], 8)

    def test_cohort_effects_are_withheld_when_baseline_rosters_differ(self):
        observations = [{
            "turn": turn, "baseline_member_count": 1,
            "present_member_count": 1, "alive_member_count": 1,
            "need_observed_member_count": 1, "need_met_member_count": 1,
            "calories_eaten_total_kcal": 100,
            "calorie_shortfall_total_kcal": 0,
            "employer_linked_member_count": 1,
        } for turn in range(8, 12)]
        result = resident_cohort_effect({
            "default_resident_cohort": {
                "control": {"roster": [{"actor_id": 1}],
                            "observations": observations},
                "treatment": {"roster": [{"actor_id": 2}],
                              "observations": observations},
            }
        })

        self.assertFalse(result["roster_matched"])
        self.assertIsNone(result["treatment_minus_control"]["need_met_share"])


if __name__ == "__main__":
    unittest.main()

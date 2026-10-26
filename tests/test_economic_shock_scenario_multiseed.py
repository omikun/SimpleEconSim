import unittest

from economic_shock_scenario_multiseed import (
    _deep_audit_summary,
    household_cohort_effects,
    market_window_effect,
    mill_order_summary,
    physical_stock_effects,
    recovery_assessment,
)


def _market_row(turn, *, control=10, treatment=10, key="units_sold"):
    return {
        "tile": "Cotton Fields", "good": "cotton", "turn": turn,
        "values": {key: {"control": control, "treatment": treatment,
                         "treatment_minus_control": treatment - control}},
    }


class ScenarioMultiSeedTests(unittest.TestCase):
    def test_deep_audit_summary_keeps_unrun_traces_out_of_pass_counts(self):
        quality = {
            "structural_and_supported_formula_checks_pass": True,
            "audit_issue_count": 0,
            "complete_causal_coverage": False,
            "treasury_account_closure": {"verified": 40, "nation_closes": 40},
            "treasury_reconciliation": {
                "fully_attributed_turns": 40, "turns": 40,
                "unattributed_absolute_total": 1e-12,
            },
        }
        results = {812: {"experiments": {"pair": {
            "control_result_data": {
                "trace_quality_gates": quality,
                "market_mechanical_gates": {"passed": True},
            },
            "treatment_result_data": {
                "market_mechanical_gates": {"passed": True},
            },
        }}}}
        summary = _deep_audit_summary(results)
        self.assertEqual(summary["arms_expected"], 2)
        self.assertEqual(summary["arms_deep_audited"], 1)
        self.assertEqual(summary["account_closes_verified"], 40)
        self.assertEqual(summary["treasury_turns_attributed"], 40)
        self.assertEqual(summary["complete_causal_coverage_arms"], 0)

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

    def test_household_effects_compare_a_fixed_turn7_cohort(self):
        def arm(treatment):
            observations = []
            for turn in range(7, 12):
                cash = 10 + (turn - 7) * (2 if treatment else 1)
                observations.append({
                    "turn": turn,
                    "members": [{
                        "actor_id": 41, "present": True, "alive": True,
                        "cash": cash, "food_stock": 3 + (turn - 7),
                        "total_debt": 2.0, "food_need_met_ratio":
                        0.75 if treatment else 0.5,
                        "food_shortfall": not treatment,
                        "employer_linked": treatment,
                        "calories_eaten": 1500 if treatment else 1000,
                        "wage_income_cash": 2 if treatment else 1,
                        "sales_cash": 3 if treatment else 1,
                        "purchases_cash": 4 if treatment else 5,
                    }],
                })
            return {
                "scenario_household_cohort_roster": [{"actor_id": 41}],
                "scenario_household_cohort_observations": observations,
            }

        result = household_cohort_effects({
            "control_result_data": arm(False),
            "treatment_result_data": arm(True),
        })
        metrics = result["metrics"]
        self.assertEqual(result["paired_baseline_members"], 1)
        self.assertEqual(metrics["cash"]["effect"], 4)
        self.assertEqual(metrics["food_need_met_ratio"]["effect"], 0.25)
        self.assertEqual(metrics["food_shortfall"]["effect"], -1.0)
        self.assertEqual(metrics["employer_linked"]["effect"], 1.0)
        self.assertEqual(metrics["wage_income_cash"]["effect"], 1.0)

    def test_physical_stock_effects_keep_census_gaps_missing(self):
        def arm(quantity, include_t11=True):
            observations = [{
                "turn": 7,
                "coverage": {"agents_scanned": 2},
                "stocks": [{"category": "household", "pool": "inventory",
                            "good": "cotton", "quantity": 10}],
            }]
            if include_t11:
                observations.append({
                    "turn": 11,
                    "coverage": {"agents_scanned": 2},
                    "stocks": [{"category": "household", "pool": "inventory",
                                "good": "cotton", "quantity": quantity}],
                })
            return {"scenario_goods_stock_observations": observations}

        result = physical_stock_effects({
            "control_result_data": arm(8),
            "treatment_result_data": arm(6),
        })
        stock = result["stocks"][0]
        self.assertEqual(stock["points"]["7"]["treatment_minus_control"], 0)
        self.assertEqual(stock["points"]["11"]["treatment_minus_control"], -2)
        self.assertEqual(stock["shock_window_change_effect"], -2)

        missing = physical_stock_effects({
            "control_result_data": arm(8, include_t11=False),
            "treatment_result_data": arm(6, include_t11=False),
        })
        self.assertIsNone(missing["stocks"][0]["points"]["11"][
            "treatment_minus_control"])


if __name__ == "__main__":
    unittest.main()

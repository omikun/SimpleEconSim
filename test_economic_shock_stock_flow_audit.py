import unittest

from economic_shock_stock_flow_audit import audit_run, render_markdown


class EconomicShockStockFlowAuditTests(unittest.TestCase):
    def _run(self, snapshots, completed_turns=2):
        return {
            "scenario": "supply_rivalry",
            "seed": 17,
            "experiment": "rivalry_cotton_supply_reduction",
            "arm": "cotton-control",
            "completed_turns": completed_turns,
            "scenario_goods_stock_observations": snapshots,
        }

    def test_reconciles_production_inputs_consumption_and_internal_turnover(self):
        run = self._run([
            {"turn": 1, "stocks": [
                {"good": "cotton", "quantity": 10},
                {"good": "cloth", "quantity": 2},
                {"good": "food", "quantity": 20},
                {"good": "wood", "quantity": 3},
            ]},
            {"turn": 2, "stocks": [
                {"good": "cotton", "quantity": 11},
                {"good": "cloth", "quantity": 4},
                {"good": "food", "quantity": 20},
                {"good": "wood", "quantity": 3},
            ]},
        ])
        events = [
            {"turn": 2, "kind": "independent_production",
             "subject": {"good": "cotton"}, "value_after": 4},
            {"turn": 2, "kind": "firm_production",
             "subject": {"good": "cloth"}, "value_after": 3,
             "inputs": {"input_good": "cotton", "input_quantity_used": 3}},
            {"turn": 2, "kind": "household_nonfood_consumption",
             "subject": {"good": "cloth"}, "delta": -1,
             "inputs": {"units_consumed": 1}},
            {"turn": 2, "kind": "civilian_food_consumption_total",
             "subject": {"good": "food"}, "value_after": 0,
             "inputs": {"eaten_food_units": 0}},
            {"turn": 2, "kind": "paid_market_sale",
             "subject": {"good": "cotton"}, "value_after": 99,
             "inputs": {"imported": False}},
            {"turn": 2, "kind": "route_shipment_loaded",
             "subject": {"type": "shipment"},
             "inputs": {"good": "cotton", "quantity": 2}},
            {"turn": 2, "kind": "feudal_tribute_transfer",
             "record_class": "transfer", "subject": {"good": "cotton"},
             "value_after": 1},
            {"turn": 2, "kind": "market_seller_receipt_posted",
             "record_class": "transfer", "subject": {"good": "cotton"},
             "value_after": 50},
        ]

        result = audit_run(run, events)

        self.assertTrue(result["passed"])
        self.assertEqual(result["summary_by_good"]["cotton"][
            "balanced_interval_count"], 1)
        self.assertEqual(result["summary_by_good"]["cloth"][
            "production_units"], 3.0)
        self.assertEqual(result["summary_by_good"]["cloth"][
            "household_nonfood_consumption_units"], 1.0)
        turnover = result["summary_by_good"]["cotton"]["internal_turnover"]
        self.assertEqual(turnover["paid_market_sale"]["reported_quantity"], 99)
        self.assertEqual(turnover["route_shipment_loaded"]["reported_quantity"], 2)
        self.assertEqual(turnover["feudal_tribute_transfer"]["event_count"], 1)
        self.assertEqual(turnover["market_seller_receipt_posted"][
            "reported_quantity"], 0)

    def test_missing_input_good_is_an_explicit_coverage_failure(self):
        run = self._run([
            {"turn": 1, "stocks": [{"good": "cotton", "quantity": 4}]},
            {"turn": 2, "stocks": [{"good": "cotton", "quantity": 4}]},
        ])
        events = [{
            "turn": 2, "kind": "firm_production",
            "subject": {"good": "cloth"}, "value_after": 1,
            "inputs": {"inputs_used": 1},
        }]

        result = audit_run(run, events)

        self.assertFalse(result["passed"])
        self.assertIn("missing_production_input_good",
                      [issue["kind"] for issue in result["issues"]])

    def test_missing_snapshot_interval_is_not_silently_skipped(self):
        run = self._run([
            {"turn": 1, "stocks": []},
            {"turn": 3, "stocks": []},
        ], completed_turns=3)

        result = audit_run(run, [])

        self.assertFalse(result["passed"])
        self.assertIn({"kind": "missing_consecutive_stock_snapshot", "turn": 2},
                      result["issues"])
        self.assertIn({"kind": "missing_consecutive_stock_snapshot", "turn": 3},
                      result["issues"])

    def test_report_uses_experiment_and_arm_as_distinct_columns(self):
        run = self._run([
            {"turn": 1, "stocks": []},
            {"turn": 2, "stocks": []},
        ])
        result = audit_run(run, [])

        report = render_markdown([result])

        self.assertIn("| 17 | cotton supply | cotton-control |", report)
        self.assertNotIn("| 17 | mill cotton demand |", report)

    def test_food_balance_includes_foraging_meals_and_granary_stock(self):
        run = self._run([
            {"turn": 1, "stocks": [
                {"good": "food", "pool": "inventory", "quantity": 10},
                {"good": "food", "pool": "granary_food", "quantity": 5},
            ]},
            {"turn": 2, "stocks": [
                {"good": "food", "pool": "inventory", "quantity": 11},
                {"good": "food", "pool": "granary_food", "quantity": 6},
            ]},
        ])
        events = [
            {"turn": 2, "kind": "independent_production",
             "subject": {"good": "food"}, "value_after": 1},
            {"turn": 2, "kind": "foraged_food_receipt",
             "subject": {"good": "food"}, "value_after": 2},
            {"turn": 2, "kind": "civilian_food_consumption_total",
             "subject": {"good": "food"}, "value_after": 1,
             "inputs": {"eaten_food_units": 1}},
            {"turn": 2, "kind": "granary_food_stock_transfer",
             "record_class": "transfer", "subject": {"good": "food"},
             "inputs": {"direction": "deposit", "units": 1}},
        ]

        result = audit_run(run, events)

        self.assertTrue(result["passed"])
        self.assertEqual(result["summary_by_good"]["food"][
            "foraged_food_units"], 2.0)
        self.assertEqual(result["summary_by_good"]["food"][
            "civilian_food_consumption_units"], 1.0)
        food_interval = next(row for row in result["intervals"]
                             if row["good"] == "food")
        self.assertEqual(food_interval["granary_stock_delta"], 1)
        self.assertEqual(result["summary_by_good"]["food"][
            "internal_turnover"]["granary_food_stock_transfer"][
                "reported_quantity"], 1)

    def test_granary_change_remains_inside_boundary_and_exposes_gap(self):
        run = self._run([
            {"turn": 1, "stocks": [
                {"good": "food", "pool": "inventory", "quantity": 10},
                {"good": "food", "pool": "granary_food", "quantity": 5},
            ]},
            {"turn": 2, "stocks": [
                {"good": "food", "pool": "inventory", "quantity": 12},
                {"good": "food", "pool": "granary_food", "quantity": 7},
            ]},
        ])
        events = [{
            "turn": 2, "kind": "civilian_food_consumption_total",
            "subject": {"good": "food"}, "value_after": 0,
            "inputs": {"eaten_food_units": 0},
        }]

        result = audit_run(run, events)

        self.assertFalse(result["passed"])
        food_interval = next(row for row in result["intervals"]
                             if row["good"] == "food")
        self.assertEqual(food_interval["granary_stock_delta"], 2)
        self.assertEqual(food_interval["residual"], 4)

    def test_food_aggregates_are_required_once_per_region(self):
        run = self._run([
            {"turn": 1, "coverage": {"region_count": 2},
             "stocks": [{"good": "food", "quantity": 10}]},
            {"turn": 2, "coverage": {"region_count": 2},
             "stocks": [{"good": "food", "quantity": 5}]},
        ])
        events = [
            {"turn": 2, "kind": "civilian_food_consumption_total",
             "subject": {"id": "North", "good": "food"},
             "inputs": {"eaten_food_units": 2}},
            {"turn": 2, "kind": "civilian_food_consumption_total",
             "subject": {"id": "South", "good": "food"},
             "inputs": {"eaten_food_units": 3}},
        ]

        result = audit_run(run, events)

        self.assertTrue(result["passed"])
        self.assertEqual(result["summary_by_good"]["food"][
            "civilian_food_consumption_units"], 5.0)


if __name__ == "__main__":
    unittest.main()

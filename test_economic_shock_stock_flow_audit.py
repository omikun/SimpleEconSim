import unittest

from economic_shock_stock_flow_audit import audit_run


class EconomicShockStockFlowAuditTests(unittest.TestCase):
    def _run(self, snapshots, completed_turns=2):
        return {
            "scenario": "supply_rivalry",
            "seed": 17,
            "arm": "cotton-control",
            "completed_turns": completed_turns,
            "scenario_goods_stock_observations": snapshots,
        }

    def test_reconciles_production_inputs_consumption_and_internal_turnover(self):
        run = self._run([
            {"turn": 1, "stocks": [
                {"good": "cotton", "quantity": 10},
                {"good": "cloth", "quantity": 2},
            ]},
            {"turn": 2, "stocks": [
                {"good": "cotton", "quantity": 11},
                {"good": "cloth", "quantity": 4},
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
            {"turn": 2, "kind": "paid_market_sale",
             "subject": {"good": "cotton"}, "value_after": 99,
             "inputs": {"imported": False}},
            {"turn": 2, "kind": "route_shipment_loaded",
             "subject": {"type": "shipment"},
             "inputs": {"good": "cotton", "quantity": 2}},
            {"turn": 2, "kind": "feudal_tribute_transfer",
             "record_class": "transfer", "subject": {"good": "cotton"},
             "value_after": 1},
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
        self.assertEqual(result["issues"][0]["kind"],
                         "missing_production_input_good")

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


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from economic_shock_analysis import analyze_trace
from goods import Goods
from region_market import _analysis_demand_target
from trace_codec import CompactTraceWriter


class AnalysisDemandTargetTests(unittest.TestCase):
    def test_demand_override_is_opt_in_and_agent_specific(self):
        class Region:
            pass

        region = Region()
        self.assertEqual(
            _analysis_demand_target(region, Goods.furniture, 7, 1), 1)
        region._analysis_demand_target_overrides = {
            Goods.furniture: {7: 1.5}}
        self.assertEqual(
            _analysis_demand_target(region, Goods.furniture, 7, 1), 2)
        self.assertEqual(
            _analysis_demand_target(region, Goods.furniture, 8, 1), 1)

    def test_invalid_demand_multiplier_fails_clearly(self):
        class Region:
            _analysis_demand_target_overrides = {
                Goods.furniture: {7: 0}}

        with self.assertRaisesRegex(ValueError, "finite and positive"):
            _analysis_demand_target(Region(), Goods.furniture, 7, 1)


class TracePanelCoverageTests(unittest.TestCase):
    def test_absent_clearing_is_not_reported_as_zero_trade(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.ctr"
            writer = CompactTraceWriter(path)
            writer.append(json.dumps({
                "record_class": "metadata", "run_id": "fixture",
                "seed": 1, "scenario": None, "schema_version": 1,
            }))
            for turn, event_id in ((1, "fixture:1"), (2, "fixture:2")):
                writer.append(json.dumps({
                    "kind": "market_price_update", "event_id": event_id,
                    "turn": turn,
                    "subject": {"type": "tile", "id": "c50",
                                "good": "furniture"},
                    "inputs": {"currency": "CNY", "demand_ratio": 1.0},
                    "value_before": 10.0, "value_after": 10.0,
                }))
            writer.append(json.dumps({
                "kind": "market_clearing_summary", "event_id": "fixture:3",
                "turn": 2,
                "subject": {"type": "tile", "id": "c50",
                            "good": "furniture"},
                "inputs": {"submitted_bids": 0, "offered_asks": 0,
                           "cash_collected": 0, "no_paid_sale": True},
                "value_after": 0,
            }))
            writer.close()

            result = analyze_trace(path)
            by_turn = {(row["turn"], row["tile"], row["good"]): row
                       for row in result["panel"]}
            missing = by_turn[(1, "c50", "furniture")]
            zero = by_turn[(2, "c50", "furniture")]

            self.assertFalse(missing["coverage"]["market_clearing"])
            self.assertNotIn("units_sold", missing["market"])
            self.assertTrue(zero["coverage"]["market_clearing"])
            self.assertEqual(zero["market"]["units_sold"], 0)
            self.assertEqual(result["market_reference_observation_count"], 2)
            self.assertEqual(result["market_clearing_missing_count"], 1)


if __name__ == "__main__":
    unittest.main()

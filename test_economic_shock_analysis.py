import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from economic_shock_analysis import analyze_trace
from economic_shock_experiment import (
    _market_mechanical_gates,
    _select_target_tile,
)
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


class ShockTargetSelectionTests(unittest.TestCase):
    def test_empty_preferred_tile_falls_back_to_active_market_cohort(self):
        class Agent:
            def __init__(self, agent_id, output=None):
                self.id = agent_id
                self.output = output
                self.alive = True

        class Tile:
            def __init__(self, name, agents):
                self.name = name
                self.agents = agents
                self.recipes = {
                    Goods.wood: {"production": 2.0, "price": 1.0},
                    Goods.furniture: {"production": 1.0, "price": 16.0},
                }

        class Server:
            tiles = [
                Tile("c50", []),
                Tile("c10", [Agent(1, Goods.wood), Agent(2, Goods.furniture),
                              Agent(3)]),
            ]

        supply_tile, supply_selection = _select_target_tile(
            Server(), "wood_supply_reduction")
        demand_tile, demand_selection = _select_target_tile(
            Server(), "furniture_demand_increase")

        self.assertEqual(supply_tile.name, "c10")
        self.assertEqual(supply_selection["wood_producers"], 1)
        self.assertEqual(demand_tile.name, "c10")
        self.assertEqual(demand_selection["eligible_households"], 3)

    def test_preferred_tile_is_kept_when_it_can_receive_the_shock(self):
        class Agent:
            id = 1
            alive = True
            output = Goods.wood

        class Tile:
            def __init__(self, name, agents):
                self.name = name
                self.agents = agents
                self.recipes = {
                    Goods.wood: {"production": 2.0, "price": 1.0},
                    Goods.furniture: {"production": 1.0, "price": 16.0},
                }

        class Server:
            tiles = [Tile("c10", [Agent()]), Tile("c50", [Agent()])]

        tile, _selection = _select_target_tile(Server(), "wood_supply_reduction")
        self.assertEqual(tile.name, "c50")


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

    def test_nonfood_consumption_is_aggregated_with_requested_coverage(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "consumption.ctr"
            writer = CompactTraceWriter(path)
            writer.append(json.dumps({
                "record_class": "metadata", "run_id": "fixture",
                "seed": 1, "scenario": None, "schema_version": 1,
            }))
            writer.append(json.dumps({
                "kind": "household_nonfood_consumption",
                "event_id": "fixture:1", "turn": 8,
                "subject": {"type": "tile/agent/good", "id": "7",
                            "tile": "c50", "good": "furniture"},
                "inputs": {"units_consumed": 1,
                           "consumption_components": [
                               {"quantity": 1, "requested_quantity": 2}]},
                "value_before": 1, "value_after": 0,
            }))
            writer.append(json.dumps({
                "kind": "household_nonfood_consumption",
                "event_id": "fixture:2", "turn": 8,
                "subject": {"type": "tile/agent/good", "id": "8",
                            "tile": "c50", "good": "furniture"},
                "inputs": {"units_consumed": 1,
                           "consumption_components": [
                               {"quantity": 1, "mechanism": "wear"}]},
                "value_before": 1, "value_after": 0,
            }))
            writer.close()

            result = analyze_trace(path)
            row = result["panel"][0]
            self.assertEqual(row["nonfood_consumption"], {
                "records": 2, "units_consumed": 2, "requested_units": 2,
                "requested_observed_records": 1,
            })
            self.assertTrue(row["coverage"]["nonfood_consumption"])


class MarketMechanicalGateTests(unittest.TestCase):
    def test_missing_settlement_is_not_counted_as_zero_or_failure(self):
        result = _market_mechanical_gates([{
            "turn": 1, "tile": "c50", "good": "furniture", "market": {},
            "production_units": 0, "producer_inventory_units": 0,
        }])
        self.assertTrue(result["passed"])
        self.assertEqual(result["settlements_checked"], 0)

    def test_settlement_bounds_and_no_paid_sale_consistency(self):
        good = {
            "turn": 1, "tile": "c50", "good": "furniture",
            "production_units": 1, "producer_inventory_units": 0,
            "market": {"funded_demand_units": 5, "offered_supply_units": 4,
                       "units_sold": 3, "cash_collected": 12,
                       "import_units": 0, "no_paid_sale": False},
        }
        self.assertTrue(_market_mechanical_gates([good])["passed"])

        bad = {**good, "market": {**good["market"], "units_sold": 5,
                                   "no_paid_sale": True}}
        result = _market_mechanical_gates([bad])
        self.assertFalse(result["passed"])
        self.assertEqual({item["check"] for item in result["violations"]}, {
            "sales_within_recorded_supply", "no_paid_sale_matches_zero_sales"})


if __name__ == "__main__":
    unittest.main()

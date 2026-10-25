import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from economic_shock_analysis import analyze_trace
from economic_shock_experiment import (
    _intervention_hook_observation,
    _market_mechanical_gates,
    _scenario_observation_summary,
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

    def test_supply_rivalry_selects_named_crop_and_domestic_mill_roles(self):
        class Agent:
            def __init__(self, ident, output, *, corporation=False, name=None):
                self.id = ident
                self.output = output
                self.alive = True
                self.is_corporation = corporation
                self.company_name = name

        class Tile:
            name = "Cotton Fields"
            recipes = {
                Goods.cotton: {"price": 4.0, "production": 3},
                Goods.cloth: {"price": 13.0, "input": Goods.cotton},
            }
            agents = [Agent(6, Goods.cotton), Agent(7, Goods.cotton),
                      Agent(47, Goods.cloth, corporation=True,
                            name="Meridian Mill")]

        class Server:
            tiles = [Tile()]
            scenario_state = {"grower_ids": [6, 7], "domestic_mill_id": 47}

        supply_tile, supply_selection = _select_target_tile(
            Server(), "rivalry_cotton_supply_reduction")
        demand_tile, demand_selection = _select_target_tile(
            Server(), "rivalry_mill_cotton_demand_increase")

        self.assertEqual(supply_tile.name, "Cotton Fields")
        self.assertEqual(supply_selection["grower_agent_ids"], [6, 7])
        self.assertEqual(demand_tile.name, "Cotton Fields")
        self.assertEqual(demand_selection["target_agent_ids"], [47])
        self.assertEqual(demand_selection["target_agent_name"], "Meridian Mill")
        self.assertEqual(demand_selection["base_desired_target_units"], 3)

    def test_scenario_hook_gate_checks_active_and_restored_supply(self):
        class Tile:
            recipes = {Goods.cotton: {"production": 1.5}}

        class Server:
            scenario_id = "supply_rivalry"

        treatment = {"before": 3.0, "after": 1.5}
        active = _intervention_hook_observation(
            Server(), {"kind": "physical_supply", "good": "cotton"},
            Tile(), 10, "treatment", treatment)
        Tile.recipes[Goods.cotton]["production"] = 3.0
        restored = _intervention_hook_observation(
            Server(), {"kind": "physical_supply", "good": "cotton"},
            Tile(), 12, "treatment", treatment)
        self.assertTrue(active["passed"])
        self.assertTrue(restored["passed"])

    def test_scenario_hook_gate_checks_mill_input_override_removal(self):
        class Tile:
            _analysis_demand_target_overrides = {
                Goods.cotton: {47: 1.5}}

        class Server:
            scenario_id = "supply_rivalry"

        config = {"kind": "input_demand", "good": "cotton", "factor": 1.5}
        intervention = {"affected_agent_ids": [47]}
        active = _intervention_hook_observation(
            Server(), config, Tile(), 9, "treatment", intervention)
        Tile._analysis_demand_target_overrides = {}
        restored = _intervention_hook_observation(
            Server(), config, Tile(), 12, "treatment", intervention)
        self.assertTrue(active["passed"])
        self.assertTrue(restored["passed"])


class ScenarioObservationSummaryTests(unittest.TestCase):
    def test_scenario_observation_summary_uses_window_and_named_actor_coverage(self):
        run = {
            "scenario_actor_observations": [
                {"turn": turn,
                 "actors": [{"role": "grower", "food_intake": 2}],
                 "cotton_trade_events": [{"quantity": 3}]}
                for turn in (7, 8, 11, 12)],
            "scenario_route_events": [
                {"turn": 8, "kind": "route_shipment_departure", "quantity": 4},
                {"turn": 11, "kind": "route_shipment_arrival", "quantity": 4},
                {"turn": 12, "kind": "route_shipment_departure", "quantity": 9}],
            "scenario_mill_order_events": [
                {"turn": 8, "submitted_quantity": 5, "desired_target": 5,
                 "unshocked_desired_target": 3,
                 "target_override_applied": True}],
        }
        summary = _scenario_observation_summary(run)
        self.assertEqual(summary["cotton_market_fills"], 6)
        self.assertEqual(summary["route_departures"], 4)
        self.assertEqual(summary["route_arrivals"], 4)
        self.assertEqual(summary["mill_submitted_bid_units"], 5)
        self.assertEqual(summary["mill_override_order_events"], 1)
        self.assertEqual(summary["grower_food_intake"], 4)
        self.assertEqual(summary["actor_turns_observed"], 2)


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

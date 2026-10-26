import unittest
from types import SimpleNamespace
from unittest.mock import patch

from economic_replay import replay
from goods import Goods
from region_production import produce


class MemoryTrace:
    def __init__(self):
        self.rows = []
        self._turn_production_receipts = {}

    def emit(self, clock, **row):
        event_id = f"test:{clock['next']}"
        clock["next"] += 1
        trace_row = {"event_id": event_id, "turn": clock.get("turn"),
                     "phase": clock.get("phase"), **row}
        if "before" in row:
            trace_row["value_before"] = row["before"]
        if "after" in row:
            trace_row["value_after"] = row["after"]
        self.rows.append(trace_row)
        return event_id


class InventoryAgent:
    def __init__(self, ident, *, output=Goods.food, food=0):
        self.id = ident
        self.output = output
        self.food = food
        self.employer = None
        self.is_trader = False
        self.is_corporation = False
        self.is_striking = False
        self.in_revolt = False
        self.is_native_child = False
        self.military_unit_id = None

    def inv_get(self, good, default=0):
        return self.food if good == Goods.food else default

    def inv_add(self, good, amount):
        if good == Goods.food:
            self.food += int(amount)


class GranaryStockFlowTests(unittest.TestCase):
    def _region(self, *, granary=25, public_food=0):
        farmer = InventoryAgent("farmer")
        trace = MemoryTrace()
        government = SimpleNamespace(
            name="Agraria", food_inventory=float(public_food),
            receive_food=lambda units: setattr(
                government, "food_inventory", government.food_inventory + units))
        region = SimpleNamespace(
            name="North", agents=[farmer], goods=[Goods.food, Goods.gov],
            recipes={Goods.food: {"import_only": False}}, terrain={},
            production_log={Goods.food: []}, granary_stock=float(granary),
            gov=government, owner_nation=None, tenure=None,
            _run_trace=trace,
            _collective_trace_clock={"turn": 4, "phase": "production", "next": 1},
        )
        return region, farmer, government, trace

    @staticmethod
    def _produce_ten_food(region, agent, _recipe, output, _counts,
                          production_totals, receipt_ids=None, **_kwargs):
        agent.inv_add(output, 10)
        production_totals[output] += 10
        trace = region._run_trace
        clock = region._collective_trace_clock
        event_id = trace.emit(
            clock, kind="independent_production", record_class="outcome",
            phase="production", subject={"type": "agent", "id": agent.id,
                                          "tile": region.name, "good": "food"},
            metric_id="goods.production", unit="units", before=0, after=10,
            formula_id="production.independent.v1", inputs={})
        trace._turn_production_receipts[event_id] = 10
        if receipt_ids is not None:
            receipt_ids.append(event_id)

    def test_harvest_deposit_and_lean_release_conserve_physical_food(self):
        region, farmer, government, trace = self._region()
        starting_food = farmer.food + region.granary_stock + government.food_inventory

        with patch("region_production.produce_independent",
                   side_effect=self._produce_ten_food):
            produce(region, 4)

        self.assertEqual(farmer.food, 9)
        self.assertEqual(region.granary_stock, 26.0)
        self.assertEqual(region.production_log[Goods.food][-1], 10)
        deposit = next(row for row in trace.rows
                       if row.get("kind") == "granary_food_stock_transfer")
        self.assertEqual(deposit["inputs"]["direction"], "deposit")
        self.assertEqual(deposit["inputs"]["units"], 1)
        self.assertEqual(deposit["inputs"]["source_inventory_changes"], [{
            "agent_id": "farmer", "units": 1,
            "inventory_before": 10, "inventory_after": 9,
        }])
        self.assertEqual(deposit["inputs"]["transfer_contract"][
            "counterparty_leg_status"],
            "producer_inventory_debits_and_granary_credit_captured")
        self.assertEqual(replay(deposit), deposit["value_after"])

        region._collective_trace_clock["turn"] = 9
        with patch("region_production.produce_independent"):
            produce(region, 9)

        self.assertEqual(region.granary_stock, 22.0)
        self.assertEqual(government.food_inventory, 4.0)
        self.assertEqual(region.production_log[Goods.food][-1], 0)
        release = [row for row in trace.rows
                   if row.get("kind") == "granary_food_stock_transfer"][-1]
        self.assertEqual(release["inputs"]["direction"], "release")
        self.assertEqual(release["inputs"]["units"], 4)
        self.assertEqual(release["inputs"]["transfer_contract"][
            "counterparty_leg_status"],
            "granary_debit_and_public_food_credit_captured")
        self.assertEqual(replay(release), release["value_after"])
        self.assertEqual(farmer.food + region.granary_stock
                         + government.food_inventory, starting_food + 10)

        production_total = next(
            row for row in trace.rows
            if row.get("kind") == "tile_production_total"
            and row.get("turn") == 9)
        self.assertEqual(replay(production_total), 0)

    def test_granary_does_not_release_when_no_public_food_store_exists(self):
        region, _farmer, _government, _trace = self._region(granary=10)
        region.gov = None
        region._collective_trace_clock["turn"] = 9

        with patch("region_production.produce_independent"):
            produce(region, 9)

        self.assertEqual(region.granary_stock, 10.0)


if __name__ == "__main__":
    unittest.main()

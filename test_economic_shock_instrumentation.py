import unittest
from types import SimpleNamespace

from economic_shock_experiment import (
    _scenario_goods_stock_observation,
    _scenario_household_cohort_observations,
    _scenario_household_cohort_roster,
)
from goods import Goods


def _inventory(**amounts):
    values = [0] * (max(good.value for good in Goods) + 1)
    for name, quantity in amounts.items():
        values[getattr(Goods, name).value] = quantity
    return values


def _actor(ident, *, household=False, corporation=False, trader=False,
           government=False, **stocks):
    values = _inventory(**stocks)
    return SimpleNamespace(
        id=ident, alive=True, is_corporation=corporation,
        is_trader=trader, is_government=government,
        military_unit_id=None, display_name=f"Agent {ident}",
        inventory=values, inventory_export=_inventory(),
        inventory_foreign=_inventory(), parked_foreign={},
        transport_pipeline=[], custom_inventory={}, cash=20.0,
        calorie_need_kcal=2000.0, last_calories_eaten=1500.0,
        hungry_steps=1.0, employer=None, output=Goods.food,
        debt=0.0,
        inv_get=lambda good, default=0, v=values: v[good.value] or default,
    )


def _tile(name, agents, *, government=None, routes=None, charities=None,
          granary_stock=0):
    return SimpleNamespace(
        name=name, agents=agents, gov=government, owner_nation=None,
        routes=routes or {}, route=None, actor_turn_accounts=[],
        economic_events=[], charity=None, charities=charities or [],
        granary_stock=granary_stock,
    )


class EconomicShockInstrumentationTests(unittest.TestCase):
    def test_turn7_household_roster_is_fixed_to_ordinary_residents(self):
        household = _actor(1, household=True)
        company = _actor(2, corporation=True)
        trader = _actor(3, trader=True)
        government_agent = _actor(4, government=True)
        tile = _tile("Cotton Fields", [household, company, trader,
                                        government_agent])
        server = SimpleNamespace(scenario_id="supply_rivalry", tiles=[tile])

        roster = _scenario_household_cohort_roster(server)

        self.assertEqual([row["actor_id"] for row in roster], [1])
        self.assertEqual(roster[0]["baseline_tile"], "Cotton Fields")

    def test_household_observation_retains_nutrition_cash_debt_and_wage_receipts(self):
        household = _actor(1, household=True, food=2)
        employer = SimpleNamespace(id=9)
        household.employer = employer
        tile = _tile("Cotton Fields", [household])
        tile.actor_turn_accounts = [{
            "turn": 8, "actor_id": 1, "closing_debt": 3.5,
            "closing_bank_debt": 2.0, "sales_cash": 4.0,
            "purchases_cash": 5.0, "input_consumed_cost": 1.0,
        }]
        tile.economic_events = [{
            "turn": 8, "kind": "wage", "recipient_id": 1, "amount": 6.0,
        }]
        server = SimpleNamespace(scenario_id="supply_rivalry", tiles=[tile])
        roster = _scenario_household_cohort_roster(server)

        result = _scenario_household_cohort_observations(server, 8, roster)
        member = result["members"][0]

        self.assertEqual(result["baseline_cohort_size"], 1)
        self.assertEqual(member["food_need_met_ratio"], 0.75)
        self.assertTrue(member["food_shortfall"])
        self.assertEqual(member["total_debt"], 5.5)
        self.assertEqual(member["wage_income_cash"], 6.0)
        self.assertEqual(member["sales_cash"], 4.0)
        self.assertTrue(member["employer_linked"])

    def test_stock_census_counts_distinct_pools_and_route_cargo_once(self):
        household = _actor(1, household=True, food=7)
        producer = _actor(2, corporation=True, cloth=8)
        trader = _actor(3, trader=True)
        trader.inventory_export[Goods.cotton.value] = 3
        trader.inventory_foreign[Goods.cloth.value] = 4
        trader.parked_foreign = {"Rival Port": _inventory(cotton=5)}
        government = SimpleNamespace(food_inventory=10)
        charity = SimpleNamespace(food_inventory=6)
        overdrawn_charity = SimpleNamespace(food_inventory=-0.5)
        route = SimpleNamespace(
            name="Cotton Fields->Rival Port",
            pending=[[trader, Goods.cotton, 2]],
            in_transit=[[trader, Goods.cloth, 3, 1, "Cotton Fields"]],
        )
        fields = _tile("Cotton Fields", [household, producer, trader],
                       government=government,
                       routes={"Rival Port": route}, granary_stock=24.5)
        port = _tile("Rival Port", [], government=government,
                     charities=[charity, overdrawn_charity])
        server = SimpleNamespace(scenario_id="supply_rivalry",
                                 tiles=[fields, port])

        census = _scenario_goods_stock_observation(server, 7)
        stocks = {(row["tile"], row["category"], row["pool"], row["good"]):
                  row["quantity"] for row in census["stocks"]}

        self.assertEqual(stocks[("Cotton Fields", "household", "inventory",
                                 "food")], 7)
        self.assertEqual(stocks[("Cotton Fields", "producer", "inventory",
                                 "cloth")], 8)
        self.assertEqual(stocks[("Cotton Fields", "trader", "export_inventory",
                                 "cotton")], 3)
        self.assertEqual(stocks[("Rival Port", "trader", "parked_foreign",
                                 "cotton")], 5)
        self.assertEqual(stocks[("Cotton Fields", "in_transit", "route_pending",
                                 "cotton")], 2)
        self.assertEqual(stocks[("Cotton Fields", "in_transit", "route_in_transit",
                                 "cloth")], 3)
        self.assertEqual(stocks[("Cotton Fields", "public", "government_food",
                                 "food")], 10)
        self.assertEqual(stocks[("Cotton Fields", "public", "granary_food",
                                 "food")], 24.5)
        self.assertEqual(stocks[("Rival Port", "public", "charity_food",
                                 "food")], 5.5)
        self.assertEqual(census["coverage"]["distinct_government_stores"], 1)
        self.assertEqual(census["coverage"]["distinct_charity_stores"], 2)
        self.assertEqual(census["coverage"]["granary_stores_scanned"], 2)
        self.assertEqual(census["coverage"]["routes_scanned"], 1)
        self.assertEqual(census["coverage"]["negative_stock_row_count"], 1)
        self.assertEqual(census["negative_stock_rows"][0]["quantity"], -0.5)


if __name__ == "__main__":
    unittest.main()

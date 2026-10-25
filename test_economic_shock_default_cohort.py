import unittest
from types import SimpleNamespace

from economic_shock_experiment import (
    _default_resident_cohort_observation,
    _default_resident_cohort_roster,
)


class _Resident:
    def __init__(self, ident, *, cash=0, food=0, alive=True, employer=None):
        self.id = ident
        self.alive = alive
        self.is_corporation = False
        self.is_government = False
        self.is_trader = False
        self.military_unit_id = None
        self.cash = cash
        self.inventory = {1: food}
        self.calorie_need_kcal = 100
        self.last_calories_eaten = 75
        self.employer = employer

    def inv_get(self, _good, default=0):
        return self.inventory.get(1, default)


class DefaultResidentCohortTests(unittest.TestCase):
    def test_turn7_roster_freezes_ordinary_residents_only(self):
        resident = _Resident(1, cash=10, food=2)
        corporation = SimpleNamespace(
            id=2, alive=True, is_corporation=True, is_government=False,
            is_trader=False, military_unit_id=None)
        tile = SimpleNamespace(
            name="District",
            agents=[resident, corporation],
            actor_turn_accounts=[{
                "actor_id": 1, "turn": 7,
                "closing_debt": 3.0, "closing_bank_debt": 2.0,
            }],
        )
        server = SimpleNamespace(scenario_id=None, tiles=[tile])

        roster = _default_resident_cohort_roster(server, 7)

        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["actor_id"], 1)
        self.assertEqual(roster[0]["baseline_cash"], 10.0)
        self.assertEqual(roster[0]["baseline_bank_debt"], 2.0)

    def test_compact_observation_reports_coverage_and_fixed_cohort_outcomes(self):
        resident = _Resident(1, cash=14, food=3, employer=object())
        tile = SimpleNamespace(
            name="District",
            agents=[resident],
            actor_turn_accounts=[{
                "actor_id": 1, "turn": 8,
                "closing_debt": 4.0, "closing_bank_debt": 2.0,
                "cash_change": 4.0, "wages_cash": 5.0,
                "sales_cash": 2.0, "purchases_cash": 1.0,
                "input_consumed_cost": 0.0, "produced_units": 0.0,
            }],
        )
        server = SimpleNamespace(scenario_id=None, tiles=[tile])
        roster = [
            {"actor_id": 1, "baseline_tile": "District", "baseline_cash": 10.0,
             "baseline_debt": 3.0, "baseline_bank_debt": 2.0},
            {"actor_id": 2, "baseline_tile": "District", "baseline_cash": 6.0,
             "baseline_debt": 0.0, "baseline_bank_debt": 0.0},
        ]

        observation = _default_resident_cohort_observation(server, 8, roster)

        self.assertEqual(observation["baseline_member_count"], 2)
        self.assertEqual(observation["present_member_count"], 1)
        self.assertEqual(observation["missing_member_count"], 1)
        self.assertEqual(observation["alive_member_count"], 1)
        self.assertEqual(observation["need_observed_member_count"], 1)
        self.assertEqual(observation["need_met_member_count"], 0)
        self.assertEqual(observation["cash_change_total_from_turn7"], 4.0)
        self.assertEqual(observation["debt_change_total_from_turn7"], 1.0)
        self.assertEqual(observation["account_flow_totals"]["wages_cash"], 5.0)
        self.assertEqual(observation["account_flow_coverage"]["wages_cash"], 1)


if __name__ == "__main__":
    unittest.main()

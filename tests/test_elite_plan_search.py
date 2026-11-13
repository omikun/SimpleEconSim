import unittest
from dataclasses import FrozenInstanceError, replace
from economy.elite_planning_state import PlanningState, PlanningGoal, derive_goal
from economy.elite_plan_search import plan_goal
from types import SimpleNamespace


def snapshot(**changes):
    state = PlanningState(1, 'Fixture', 'local', 0, 'opening', 'wood', 'furniture',
        20, 0, 0, 4, 0, 1, 2, 1, 1, 20, 3, 15, 20, 1, 8)
    return replace(state, **changes)


class PlanningContractTests(unittest.TestCase):
    def test_quantitative_goals_reserve_payroll_and_have_deadlines(self):
        state = snapshot()
        goal = derive_goal(state)
        self.assertEqual(goal.minimum, 2)
        self.assertFalse(goal.satisfied(state))
        self.assertTrue(goal.satisfied(replace(state, inputs=2, phase='inputs')))
        self.assertFalse(goal.satisfied(replace(state, inputs=2, cash=3)))
        self.assertFalse(goal.satisfied(replace(state, inputs=2, turn=1)))
        with self.assertRaises(FrozenInstanceError): state.cash = 100
        self.assertFalse(PlanningGoal('cash_buffer', 18, 1).satisfied(replace(state, cash=17)))

    def test_cash_goal_is_checked_at_its_future_phase_not_at_root(self):
        from economy.elite_planning_projection import purchase, finish_turn
        state = snapshot(demand=0)
        goal = PlanningGoal('cash_buffer', 18, 1)
        self.assertFalse(goal.satisfied(purchase(state, 0)))
        after_payroll = purchase(finish_turn(purchase(state, 0)), 0)
        self.assertEqual(after_payroll.cash, 16)
        self.assertFalse(goal.satisfied(after_payroll))
        self.assertTrue(goal.satisfied(replace(after_payroll, cash=18)))

    def test_bounded_search_finds_chain_and_reproduces(self):
        limits = SimpleNamespace(max_decisions=3, horizon=4, max_states=200)
        state = snapshot()
        result = plan_goal(state, derive_goal(state), limits)
        self.assertEqual(result, plan_goal(state, derive_goal(state), limits))
        self.assertTrue(result.steps)
        self.assertEqual(result.steps[0].quantity, 2)
        self.assertLessEqual(result.expanded, 200)
        self.assertFalse(plan_goal(snapshot(cash=3), derive_goal(state), limits).steps)
        self.assertFalse(plan_goal(snapshot(cash=100, supply=2), derive_goal(state), limits).steps)
        limited = plan_goal(state, derive_goal(state), SimpleNamespace(max_decisions=3, horizon=4, max_states=1))
        self.assertEqual(limited.status, 'budget_exhausted')
        self.assertEqual(limited.expanded, 1)

    def test_repeated_batches_and_phase_waits_are_bounded(self):
        state = snapshot(cash=20, demand=5)
        limits = SimpleNamespace(max_decisions=2, horizon=4, max_states=200)
        result = plan_goal(state, derive_goal(state), limits)
        self.assertLessEqual(sum(s.quantity > 0 for s in result.steps), 2)
        self.assertTrue(any(s.turn > state.turn for s in result.steps))

    def test_no_funded_demand_cannot_make_unprofitable_chain_useful(self):
        state = snapshot(demand=0)
        result = plan_goal(state, derive_goal(state), SimpleNamespace(max_decisions=3, horizon=4, max_states=200))
        self.assertFalse(result.steps)

    def test_terminal_value_includes_both_turns_payroll(self):
        state = snapshot()
        result = plan_goal(state, derive_goal(state), SimpleNamespace(max_decisions=3, horizon=2, max_states=200))
        self.assertEqual(result.candidate_value, 21)  # 20 - 6 inputs + 15 sale - 8 wages.
        self.assertEqual(result.baseline_value, 12)  # Idle still pays both turns.

"""Priority and boundary contracts for the planner's shared operator stages."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from economy.capitalist_planner import EliteCapitalistPlanner
from economy.elite_operator_runner import FRONTIER_STAGES, MACHINERY_STAGES
from economy.transformation_graph import TransformationGraph, TransformationOperator
from tests.test_elite_planning_gate_trace import Actor, MemoryTrace


def operator(policy, expected_return=100.0):
    return TransformationOperator(
        policy.operator_id, policy.operator_id, 'capital_goods',
        check_prerequisites=Mock(return_value=True),
        estimate_return_hook=Mock(return_value=expected_return),
        on_execute=Mock(return_value={'success': True}))


def plan(operators, *, cash=80.0, traced=True, supply=None):
    owner, provider = Actor(71, lord=False), Actor(72, lord=False)
    owner.cash = cash
    trace = MemoryTrace()
    region = SimpleNamespace(
        name='OperatorMarket', agents=[owner, provider], goods=[], recipes={},
        home_currency='crown', neighbors={}, economic_events=[])
    if traced:
        region._run_trace = trace
        region._collective_trace_clock = {'turn': 7, 'phase': 'local', 'next': 1}
    planner = EliteCapitalistPlanner()
    for name, value in (('get_market_luxuries', []),
                        ('evaluate_triangular_trade_voyage', None),
                        ('evaluate_spatial_trade', None),
                        ('evaluate_class_legislation', None)):
        setattr(planner, name, Mock(return_value=value))
    planner._execute_input_control = supply or Mock(return_value=None)
    with patch.object(TransformationGraph, 'get_operator', side_effect=operators.get):
        result = planner._plan_and_execute_elite(owner, region, 7)
    return result, owner, provider, trace


class EliteOperatorRunnerTests(unittest.TestCase):
    def test_return_equal_to_each_stage_threshold_does_not_execute(self):
        for policy in (*MACHINERY_STAGES[1:], *FRONTIER_STAGES):
            for value in (policy.minimum_return, policy.minimum_return + .01):
                with self.subTest(stage=policy.stage, value=value):
                    op = operator(policy, value)
                    result, _, _, trace = plan({op.id: op})
                    selected = value > policy.minimum_return
                    self.assertEqual(result['action_taken'], policy.action if selected else None)
                    self.assertEqual(op.on_execute.call_count, int(selected))
                    gate = next(row for row in trace.rows
                                if row['kind'] == 'elite_operator_evaluation')
                    self.assertEqual(gate['inputs']['strict_return_threshold'],
                                     policy.minimum_return)
                    self.assertEqual(gate['inputs']['selected_for_execution'], selected)

    def test_failed_repair_rechecks_cash_before_construction_and_supply(self):
        for traced in (True, False):
            with self.subTest(traced=traced):
                repair, construction = [operator(policy) for policy in MACHINERY_STAGES]
                repair.estimate_return_hook.side_effect = AssertionError('Repair must not need a valuation')

                def repair_failure(owner, region, turn):
                    owner.cash -= 30.0
                    region.agents[1].cash += 30.0
                    return {'success': False, 'reason': 'paid inspection; repair failed'}

                repair.on_execute.side_effect = repair_failure
                supply = Mock(return_value={'action_taken': 'SUPPLY_PROPOSAL', 'details': {}})
                result, owner, provider, trace = plan(
                    {repair.id: repair, construction.id: construction},
                    traced=traced, supply=supply)
                self.assertEqual(result['action_taken'], 'SUPPLY_PROPOSAL')
                self.assertEqual((owner.cash, provider.cash), (50.0, 30.0))
                repair.on_execute.assert_called_once()
                construction.check_prerequisites.assert_not_called()
                construction.on_execute.assert_not_called()
                supply.assert_called_once()
                if traced:
                    gates = [row for row in trace.rows
                             if row['kind'] == 'elite_operator_evaluation']
                    self.assertEqual([row['inputs']['stage'] for row in gates],
                                     ['machinery_repair', 'machinery_construction'])
                    self.assertFalse(gates[1]['inputs']['planner_cash_gate_passed'])
                    execution = next(row for row in trace.rows
                                     if row['kind'] == 'elite_operator_execution')
                    self.assertFalse(execution['inputs']['execution_result']['success'])

    def test_conquest_cash_gate_skips_evaluation_below_50(self):
        policy = FRONTIER_STAGES[-1]
        for cash in (49.99, 50.0):
            with self.subTest(cash=cash):
                op = operator(policy)
                result, _, _, trace = plan({op.id: op}, cash=cash)
                eligible = cash >= 50.0
                self.assertEqual(result['action_taken'], policy.action if eligible else None)
                self.assertEqual(op.check_prerequisites.call_count, int(eligible))
                gates = [row for row in trace.rows
                         if row['kind'] == 'elite_operator_evaluation']
                self.assertEqual(len(gates), int(eligible))

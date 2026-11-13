"""Ordered elite decisions and the stable public planner API.

Action handlers own execution; trace modules own observations. Bounded firm
planning joins the supply stage through the central off/shadow/active setting.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
from economy.transformation_graph import TransformationGraph
from economy.elite_decision import EliteDecision
from economy.elite_decision_trace import EliteDecisionTrace, record_decision_outcome
from economy.elite_luxury import purchase_luxury, evaluate_spatial_trade
from economy.elite_transformation import execute_lord_transformation
from economy.elite_investment import invest_capital
from economy.elite_liquidation import liquidate_inventory
from economy.elite_treasury_trace import (
    _trace_government_company_equity, _trace_government_inventory_liquidation,
)
from economy.elite_operator_runner import (
    MACHINERY_STAGES, FRONTIER_STAGES, run_operator_stages,
)
from economy.elite_activation import (
    get_market_luxuries, check_new_market_items, calculate_shadow_price_cash,
    is_elite, should_run_planning, record_planning_phase_gate,
)
from economy.elite_supply import (
    _input_control_options, _execute_input_control,
)
from economy.elite_voyage import (
    evaluate_triangular_trade_voyage,
)
from economy.elite_legislation import (
    evaluate_class_legislation,
)


class EliteCapitalistPlanner:
    """Decision engine for landed nobility, merchants, and capitalists."""

    def __init__(self):
        self._known_market_goods: Dict[str, set] = {}
        self._last_market_novelty_trace: Dict[int, Tuple[int, str]] = {}
        self._active_plans: Dict[int, Dict[str, Any]] = {}

    get_market_luxuries = get_market_luxuries
    check_new_market_items = check_new_market_items
    calculate_shadow_price_cash = calculate_shadow_price_cash
    is_elite = is_elite
    should_run_planning = should_run_planning
    record_planning_phase_gate = record_planning_phase_gate
    evaluate_spatial_trade = evaluate_spatial_trade
    evaluate_class_legislation = evaluate_class_legislation
    _input_control_options = _input_control_options
    _execute_input_control = _execute_input_control
    evaluate_triangular_trade_voyage = evaluate_triangular_trade_voyage

    def plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Execute one ordered decision, then publish its observed outcome."""
        cash_before = float(agent.cash)
        TransformationGraph.step_pending_capacity_decay(region, t)
        result = self._plan_and_execute_elite(agent, region, t)
        record_decision_outcome(agent, region, t, result, cash_before, float(agent.cash))
        return result

    def _plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Consider existing decision stages in order and stop after one action."""
        luxuries = self.get_market_luxuries(region)
        shadow_cash = self.calculate_shadow_price_cash(agent, region, _luxuries=luxuries)
        decision = EliteDecision(agent, region, t, shadow_cash, luxuries)
        trace = EliteDecisionTrace(decision)
        if purchase_luxury(decision, trace):
            return decision.result
        for evaluate in (self.evaluate_triangular_trade_voyage,
                         self.evaluate_spatial_trade, self.evaluate_class_legislation):
            if decision.accept(evaluate(agent, region, t)):
                return decision.result
        if execute_lord_transformation(decision, trace):
            return decision.result
        if run_operator_stages(MACHINERY_STAGES, decision, trace):
            return decision.result
        if decision.accept(self._execute_input_control(agent, region, t)):
            return decision.result
        if run_operator_stages(FRONTIER_STAGES, decision, trace):
            return decision.result
        if not invest_capital(decision):
            liquidate_inventory(decision)
        return decision.result

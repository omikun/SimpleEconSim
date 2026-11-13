"""Shared execution for the elite planner's ordered operator stages."""
from dataclasses import dataclass

from economy.transformation_graph import TransformationGraph


@dataclass(frozen=True)
class OperatorStage:
    operator_id: str
    stage: str
    action: str
    minimum_return: float | None = None
    minimum_cash: float | None = None
    report_cash_gate: bool = False


MACHINERY_STAGES = (
    OperatorStage('maintain_repair_machinery', 'machinery_repair', 'REPAIR_MACHINERY'),
    OperatorStage('construct_machinery', 'machinery_construction', 'CONSTRUCT_MACHINERY',
                  minimum_return=15.0, minimum_cash=60.0, report_cash_gate=True),
)

FRONTIER_STAGES = (
    OperatorStage('mandate_plantation_labor_gang', 'plantation_labor_gang',
                  'MANDATE_PLANTATION_LABOR_GANG', minimum_return=10.0),
    OperatorStage('procure_captive_labor', 'procure_captive_labor',
                  'PROCURE_CAPTIVE_LABOR', minimum_return=15.0),
    OperatorStage('chartered_frontier_conquest', 'frontier_conquest',
                  'WAR_CAPITALISM_FRONTIER_CONQUEST', minimum_return=20.0,
                  minimum_cash=50.0),
)


def run_operator_stage(policy, *, agent, region, turn, shadow_cash,
                       snapshot, record_gate, record_execution):
    """Try one stage, returning an action only after successful execution.

    The callbacks retain the planner's existing evidence and snapshot ownership.
    Failed execution can change state; callers must evaluate later stages live.
    """
    operator = TransformationGraph.get_operator(policy.operator_id)
    if not operator:
        return None
    cash_gate_passed = (policy.minimum_cash is None
                        or agent.cash >= policy.minimum_cash)
    if not cash_gate_passed and not policy.report_cash_gate:
        return None

    net_return = None
    if cash_gate_passed:
        can_run, reason = operator.can_agent_execute(agent, region)
        if can_run and policy.minimum_return is not None:
            net_return = operator.estimate_net_return(agent, region, shadow_cash)
    else:
        can_run = False
        reason = f'Planner cash threshold ${policy.minimum_cash:.1f} not met'
    selected = can_run and (policy.minimum_return is None
                            or net_return > policy.minimum_return)
    # Construction historically reports its return threshold only if feasible;
    # the other stages report their threshold even when prerequisites fail.
    threshold = (None if policy.report_cash_gate and not can_run
                 else policy.minimum_return)
    evaluation_id = record_gate(
        operator, stage=policy.stage, can_execute=can_run, reason=reason,
        net_return=net_return, threshold=threshold,
        selected_for_execution=selected, state_before=snapshot(operator),
        planner_cash_gate_threshold=(policy.minimum_cash if policy.report_cash_gate else None),
        planner_cash_gate_passed=(cash_gate_passed if policy.report_cash_gate else None))
    if not selected:
        return None

    state_before = snapshot(operator, execution=True)
    cash_before = float(agent.cash) if state_before is not None else None
    execution = operator.on_execute(agent, region, turn)
    record_execution(
        operator, stage=policy.stage, evaluation_event_id=evaluation_id,
        execution_result=execution, cash_before=cash_before, state_before=state_before)
    if execution.get('success'):
        return {'action_taken': policy.action, 'details': execution}
    return None


def run_operator_stages(policies, decision, trace):
    for policy in policies:
        outcome = run_operator_stage(
            policy, agent=decision.agent, region=decision.region, turn=decision.turn,
            shadow_cash=decision.shadow_cash, snapshot=trace.stage_snapshot,
            record_gate=trace.record_operator_gate, record_execution=trace.record_operator_execution)
        if decision.accept(outcome):
            return True
    return False

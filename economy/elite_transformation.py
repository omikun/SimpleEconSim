"""Select and execute the lord's best eligible transformation."""
from economy.elite_decision_trace import trace_number
from run_trace import emit
from economy.transformation_graph import TransformationGraph


def select_lord_operator(decision, trace):
    agent, region, t = decision.agent, decision.region, decision.turn
    result, trace_enabled = decision.result, decision.trace_enabled
    shadow_cash = decision.shadow_cash
    all_ops = TransformationGraph.all_operators()
    best_op = None
    best_roc = -999.0
    lord_evaluation_state = (trace.operator_state_snapshot(include_tenure=True)
                             if trace_enabled else None)

    eligible_categories = ('enclosure', 'corvee', 'artisan', 'war_capitalism')
    candidate_evaluations = [] if trace_enabled else None
    for index, op in enumerate(all_ops):
        best_roc_before = best_roc
        can_run, feasibility_reason = op.can_agent_execute(agent, region)
        category_eligible = op.category in eligible_categories
        net_return = None
        selected_as_best = False
        if can_run and category_eligible:
            net_return = op.estimate_net_return(agent, region, shadow_cash)
            selected_as_best = net_return > best_roc
            if selected_as_best:
                best_roc = net_return
                best_op = op
        if trace_enabled:
            trace_net_return = None
            if net_return is not None:
                trace_net_return = trace_number(net_return)
            candidate_evaluations.append({
                'consideration_index': index,
                'operator_id': str(op.id),
                'operator_name': str(op.name),
                'category': str(op.category),
                'category_eligible_for_lord_planning': category_eligible,
                'can_execute': bool(can_run),
                'feasibility_reason': str(feasibility_reason),
                'estimated_net_return': trace_net_return,
                'return_basis': (trace.operator_return_basis(op)
                                 if trace_net_return is not None
                                 and isinstance(trace_net_return, (int, float)) else None),
                'best_return_before': trace_number(best_roc_before),
                'selected_as_best': selected_as_best,
                'not_evaluated_reason': (
                    'ineligible' if not can_run else
                    'operator_category_not_used_by_lord_planner'
                    if not category_eligible else None)})

    execute_best_operator = best_op is not None and best_roc > 5.0
    lord_evaluation_id = None
    if trace_enabled:
        lord_evaluation_id = emit(
            region, kind='elite_lord_transformation_evaluation',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='operator_candidates',
            after=(str(best_op.id) if execute_best_operator else
                   'best_candidate_below_strict_threshold'
                   if best_op is not None else 'no_eligible_category_candidate'),
            formula_id='elite.lord_transformation_selection.v1',
            inputs={'turn': int(t),
                    'considered_categories': list(eligible_categories),
                    'candidate_evaluations': candidate_evaluations,
                    'best_operator_id': (str(best_op.id)
                                         if best_op is not None else None),
                    'best_net_return': trace_number(best_roc),
                    'strict_execution_threshold': 5.0,
                    'state_before': lord_evaluation_state,
                    'selected_for_execution': bool(execute_best_operator),
                    'selection_reason': (
                        'best_return_strictly_above_threshold'
                        if execute_best_operator else
                        'best_return_not_above_strict_threshold'
                        if best_op is not None else
                        'no_feasible_operator_in_considered_categories')})
        if lord_evaluation_id is not None:
            result['evaluation_event_ids'].append(lord_evaluation_id)

    # If an enclosure, corvée, or war capitalism operator yields positive net return, execute it!
    return (best_op if execute_best_operator else None), lord_evaluation_id


def execute_lord_transformation(decision, trace):
    agent, region, t = decision.agent, decision.region, decision.turn
    result, trace_enabled = decision.result, decision.trace_enabled
    if not getattr(agent, 'is_lord', False):
        return None
    best_op, lord_evaluation_id = select_lord_operator(decision, trace)
    if best_op is None:
        return None
    lord_state_before = (
        trace.operator_state_snapshot(
            best_op, include_tenure=True, include_recipients=True) if trace_enabled else None)
    lord_cash_before = float(agent.cash) if trace_enabled else None
    if best_op.on_execute:
        exec_res = best_op.on_execute(agent, region, t)
        trace.record_operator_execution(
            best_op, stage='lord_transformation',
            evaluation_event_id=lord_evaluation_id,
            execution_result=exec_res,
            cash_before=lord_cash_before,
            state_before=lord_state_before)
        result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
        result['details'] = {'operator': best_op.name, 'execution_result': exec_res}
        return result
    else:
        from economy.inventory_transform import execute_inventory_transform
        execution = execute_inventory_transform(best_op, agent, region, t, lord_evaluation_id)
        trace.record_operator_execution(
            best_op, stage='lord_transformation',
            evaluation_event_id=lord_evaluation_id, execution_result=execution,
            cash_before=lord_cash_before, state_before=lord_state_before)
        if execution['success']:
            result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
            result['details'] = {'operator': best_op.name, 'yield': execution['yield']}
        return result

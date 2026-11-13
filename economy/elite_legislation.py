"""Elite legislation decisions and their evidence."""
from __future__ import annotations
from typing import Any, Dict, Optional
from economy.transformation_graph import TransformationGraph


def evaluate_class_legislation(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
    """Evaluate institutional state power operators (Statute of Laborers, Vagrancy Enforcement)."""
    from run_trace import emit
    trace_enabled = (getattr(region, '_run_trace', None) is not None
                     and getattr(region, '_collective_trace_clock', None) is not None)
    operator_specs = (
        ('petition_statute_of_laborers', 'PETITION_STATUTE_OF_LABORERS'),
        ('enforce_vagrancy_decree', 'PETITION_VAGRANCY_DECREE'))
    evaluations = [] if trace_enabled else None

    def state_snapshot():
        government = getattr(getattr(region, 'gov', None), 'agent', None)
        return {
            'sponsor_cash': float(agent.cash),
            'government_cash': (float(government.cash)
                                if government is not None else None),
            'petition_count': len(getattr(region, 'labor_law_petitions', [])),
            'law_states': {
                'statute_of_laborers': bool(getattr(region, 'statute_of_laborers', False)),
                'vagrancy_law_active': bool(getattr(region, 'vagrancy_law_active', False))}}

    for index, (operator_id, action) in enumerate(operator_specs):
        operator = TransformationGraph.get_operator(operator_id)
        if operator is None:
            if trace_enabled:
                evaluations.append({'consideration_index': index,
                                    'operator_id': operator_id,
                                    'registered': False,
                                    'can_execute': False,
                                    'reason': 'operator_not_registered'})
            continue
        can_run, reason = operator.can_agent_execute(agent, region)
        row = {'consideration_index': index, 'operator_id': operator_id,
               'registered': True, 'can_execute': bool(can_run),
               'reason': str(reason)}
        if can_run:
            if trace_enabled:
                evaluations.append({**row, 'selected_for_execution': True})
                evaluation_id = emit(
                    region, kind='elite_labor_legislation_evaluation',
                    record_class='decision', phase='local',
                    subject={'type': 'agent', 'id': agent.id,
                             'tile': getattr(region, 'name', 'default')},
                    metric_id='ai.elite_economic_decision', unit='law_petition',
                    after=operator_id,
                    formula_id='elite.labor_legislation_priority.v1',
                    inputs={'turn': int(t), 'candidate_evaluations': evaluations,
                            'selected_operator_id': operator_id,
                            'selection_rule': 'first_feasible_operator_in_priority_order'})
                before = state_snapshot()
            else:
                evaluation_id = None
                before = None
            exec_res = operator.on_execute(agent, region, t)
            if trace_enabled:
                after = state_snapshot()
                execution_id = emit(
                    region, kind='elite_labor_legislation_petition',
                    record_class='outcome', phase='local',
                    subject={'type': 'agent', 'id': agent.id,
                             'tile': getattr(region, 'name', 'default')},
                    metric_id='ai.elite_economic_decision', unit='law_petition',
                    before=before['sponsor_cash'], after=after['sponsor_cash'],
                    cause_event_ids=([evaluation_id]
                                     if evaluation_id is not None else None),
                    formula_id='elite.labor_legislation_priority.v1',
                    inputs={'operator_id': operator_id, 'action': action,
                            'execution_result': exec_res,
                            'state_before': before, 'state_after': after})
                evaluation_ids = [evaluation_id] if evaluation_id is not None else []
                execution_ids = [execution_id] if execution_id is not None else []
            else:
                evaluation_ids = []
                execution_ids = []
            return {'action_taken': action, 'details': exec_res,
                    'evaluation_event_ids': evaluation_ids,
                    'execution_event_ids': execution_ids}
        if trace_enabled:
            evaluations.append(row)

    if trace_enabled:
        evaluation_id = emit(
            region, kind='elite_labor_legislation_evaluation',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='law_petition',
            after='no_feasible_petition',
            formula_id='elite.labor_legislation_priority.v1',
            inputs={'turn': int(t), 'candidate_evaluations': evaluations,
                    'selection_rule': 'first_feasible_operator_in_priority_order',
                    'selection_reason': 'all_registered_petitions_failed_feasibility'})
        return {'action_taken': None, 'details': {},
                'evaluation_event_ids': ([evaluation_id]
                                         if evaluation_id is not None else []),
                'execution_event_ids': []}
    return None

"""Elite voyage decisions and their evidence."""
from __future__ import annotations
import math
from typing import Any, Dict, Optional
from goods import Goods


def evaluate_triangular_trade_voyage(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
    """Evaluate chartering an oceanic merchant voyage on discovered trade circuits."""
    trade_mgr = getattr(region, 'trade_manager', None)
    from run_trace import emit
    trace_recorder = getattr(region, '_run_trace', None)
    trace_clock = getattr(region, '_collective_trace_clock', None)
    trace_enabled = trace_recorder is not None and trace_clock is not None
    candidates = [] if trace_enabled else None
    price_cause_ids = []

    def trace_safe(value):
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else str(value)
        if isinstance(value, dict):
            return {str(key): trace_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [trace_safe(item) for item in value]
        if hasattr(value, 'value'):
            return trace_safe(value.value)
        return str(value)

    def price_event_id(good_name):
        getter = getattr(trace_recorder, 'latest_reference_price_event_id', None)
        if not callable(getter):
            return None
        return getter(getattr(region, 'name', 'default'), str(good_name))

    if not trade_mgr:
        evaluation_id = emit(
            region, kind='elite_voyage_circuit_evaluation',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='trade.triangular_voyage_decision', unit='circuit_candidates',
            after='no_trade_manager', formula_id='trade.voyage_ai_selection.v1',
            inputs={'turn': int(t), 'candidate_evaluations': [],
                    'selection_reason': 'no_trade_manager_attached'})
        return ({'action_taken': None, 'details': {},
                 'evaluation_event_ids': [evaluation_id]}
                if evaluation_id is not None else None)

    best_circuit = None
    best_roi = -999.0
    best_is_pioneer = False

    for index, c in enumerate(trade_mgr.circuits.values()):
        best_roi_before = best_roi
        arb = trade_mgr.evaluate_dynamic_arbitrage(c, region)
        can_run = None
        charter_reason = 'not_checked_because_circuit_is_not_viable'
        pioneer = getattr(c, 'status', '') == 'DORMANT_UNEXPLORED'
        pioneer_bonus = 0.2 if pioneer else 0.0
        effective_score = None
        selected_as_best = False
        if arb.get('viable'):
            can_run, charter_reason = trade_mgr.can_charter_voyage(agent, region, c)
            if can_run:
                roi = arb.get('roi', 0.0)
                effective_score = roi + pioneer_bonus
                selected_as_best = effective_score > best_roi
                if selected_as_best:
                    best_roi = effective_score
                    best_circuit = c
                    best_is_pioneer = pioneer
        if trace_enabled:
            export_price_event_id = price_event_id(c.export_good)
            luxury_price_event_id = price_event_id(c.import_luxury)
            for event_id in (export_price_event_id, luxury_price_event_id):
                if event_id is not None and event_id not in price_cause_ids:
                    price_cause_ids.append(event_id)
            candidates.append({
                'consideration_index': index,
                'circuit_id': str(c.circuit_id),
                'circuit_name': str(c.name),
                'circuit_status': str(getattr(c, 'status', 'unknown')),
                'export_good': str(c.export_good),
                'intermediate_good': c.intermediate_good,
                'import_luxury': str(c.import_luxury),
                'arbitrage_viable': bool(arb.get('viable')),
                'arbitrage_status': str(arb.get('status', 'unknown')),
                'arbitrage_reason': arb.get('reason'),
                'arbitrage': trace_safe({key: value for key, value in arb.items()
                                         if key != 'status'}),
                'charter_feasible': can_run,
                'charter_reason': str(charter_reason),
                'pioneer_bonus': pioneer_bonus,
                'effective_score': trace_safe(effective_score),
                'best_score_before': trace_safe(best_roi_before),
                'selected_as_best': selected_as_best,
                'export_price_trace_event_id': export_price_event_id,
                'luxury_price_trace_event_id': luxury_price_event_id})

    charter_selected = best_circuit is not None and best_roi >= 0.20
    evaluation_id = None
    if trace_enabled:
        evaluation_id = emit(
            region, kind='elite_voyage_circuit_evaluation',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='trade.triangular_voyage_decision', unit='circuit_candidates',
            after=(str(best_circuit.circuit_id) if charter_selected else
                   'best_circuit_below_strict_threshold'
                   if best_circuit is not None else 'no_feasible_circuit'),
            formula_id='trade.voyage_ai_selection.v1',
            cause_event_ids=price_cause_ids or None,
            inputs={'turn': int(t), 'candidate_evaluations': candidates,
                    'selected_circuit_id': (str(best_circuit.circuit_id)
                                            if best_circuit is not None else None),
                    'best_effective_score': trace_safe(best_roi),
                    'charter_threshold': 0.20,
                    'strict_best_score_comparison': True,
                    'pioneer_bonus': 0.2,
                    'selected_for_charter': bool(charter_selected),
                    'selection_reason': (
                        'best_viable_and_affordable_circuit_meets_threshold'
                        if charter_selected else
                        'best_viable_and_affordable_circuit_below_threshold'
                        if best_circuit is not None else
                        'no_viable_affordable_circuit')})

    execution_event_ids = []
    if charter_selected:
        export_good = getattr(Goods, best_circuit.export_good, None)
        if trace_enabled:
            agent_before = {
                'cash': float(agent.cash),
                'export_inventory': (float(agent.inv_get(export_good, 0))
                                     if export_good is not None else 0.0)}
            actor_balances_before = [
                {'agent_id': str(getattr(person, 'id', 'unknown')),
                 'cash': float(getattr(person, 'cash', 0.0)),
                 'export_inventory': (float(person.inv_get(export_good, 0))
                                      if export_good is not None else 0.0)}
                for person in getattr(region, 'agents', [])]
            circuit_state_before = {
                'status': str(best_circuit.status),
                'pioneered_by': (str(best_circuit.pioneered_by)
                                 if best_circuit.pioneered_by is not None else None),
                'active_voyages': len(trade_mgr.active_voyages)}
        res = trade_mgr.charter_voyage(agent, region, best_circuit.circuit_id, is_pioneer=best_is_pioneer)
        if trace_enabled:
            agent_after = {
                'cash': float(agent.cash),
                'export_inventory': (float(agent.inv_get(export_good, 0))
                                     if export_good is not None else 0.0)}
            actor_balances_after = [
                {'agent_id': str(getattr(person, 'id', 'unknown')),
                 'cash': float(getattr(person, 'cash', 0.0)),
                 'export_inventory': (float(person.inv_get(export_good, 0))
                                      if export_good is not None else 0.0)}
                for person in getattr(region, 'agents', [])]
            changed_actor_balances = []
            for balance_index, before in enumerate(actor_balances_before):
                after = actor_balances_after[balance_index]
                if (before['cash'] != after['cash']
                        or before['export_inventory'] != after['export_inventory']):
                    changed_actor_balances.append({
                        'agent_id': before['agent_id'],
                        'cash_before': before['cash'], 'cash_after': after['cash'],
                        'export_inventory_before': before['export_inventory'],
                        'export_inventory_after': after['export_inventory']})
            circuit_state_after = {
                'status': str(best_circuit.status),
                'pioneered_by': (str(best_circuit.pioneered_by)
                                 if best_circuit.pioneered_by is not None else None),
                'active_voyages': len(trade_mgr.active_voyages)}
            execution_id = emit(
                region, kind='elite_voyage_charter_execution',
                record_class='outcome', phase='trade',
                subject={'type': 'agent', 'id': agent.id,
                         'tile': getattr(region, 'name', 'default')},
                metric_id='trade.voyage_charter_execution', unit='local_currency',
                before=agent_before['cash'], after=agent_after['cash'],
                cause_event_ids=([evaluation_id] if evaluation_id is not None else None),
                inputs={'circuit_id': str(best_circuit.circuit_id),
                        'is_pioneer': bool(best_is_pioneer),
                        'charter_result': trace_safe(res),
                        'agent_before': agent_before, 'agent_after': agent_after,
                        'changed_actor_balances': changed_actor_balances,
                        'circuit_before': circuit_state_before,
                        'circuit_after': circuit_state_after})
            if execution_id is not None:
                execution_event_ids.append(execution_id)
        if res.get('success'):
            return {
                'action_taken': 'CHARTER_MERCHANT_VOYAGE',
                'details': res,
                'evaluation_event_ids': ([evaluation_id]
                                         if evaluation_id is not None else []),
                'execution_event_ids': execution_event_ids
            }
        if evaluation_id is not None or execution_event_ids:
            return {'action_taken': None, 'details': res,
                    'evaluation_event_ids': ([evaluation_id]
                                             if evaluation_id is not None else []),
                    'execution_event_ids': execution_event_ids}
    if evaluation_id is not None:
        return {'action_taken': None, 'details': {},
                'evaluation_event_ids': [evaluation_id],
                'execution_event_ids': []}
    return None

"""Select and settle one local luxury purchase."""
from __future__ import annotations
from typing import Any, Dict, Optional
from economy.actor_accounts import record
from run_trace import emit
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish


def settle_luxury_purchase(decision, seller, good, price, good_name, evaluation_id):
    agent, region, t = decision.agent, decision.region, decision.turn
    result, trace_enabled = decision.result, decision.trace_enabled
    if trace_enabled:
        cash_before = float(agent.cash)
        buyer_inventory_before = float(agent.inv_get(good, 0))
        seller_cash_before = float(seller.cash)
        seller_inventory_before = float(seller.inv_get(good, 0))
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash -= price
    _trace_public_finish(_trace_cash_write, 'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
                         inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:d5aba2ddcd15f97f:1'})
    _trace_cash_write = _trace_public_begin(None, seller)
    seller.cash += price
    _trace_public_finish(_trace_cash_write, 'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
                         inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:3bb460e81ef75609:1'})
    seller.inv_add(good, -1)
    agent.inv_add(good, 1)
    record(region, 'spot_sale', turn=t, payer_id=agent.id,
           recipient_id=seller.id, good=good, quantity=1, amount=price,
           detail={'settlement_path': 'elite_luxury_purchase'})
    result['action_taken'] = 'PURCHASE_LUXURY'
    result['details'] = {'good': good_name,
                         'price': price, 'seller_id': seller.id}
    if evaluation_id is not None:
        result['evaluation_event_ids'].append(evaluation_id)
    execution_id = None
    if trace_enabled:
        execution_id = emit(
            region, kind='elite_luxury_purchase_execution',
            record_class='outcome', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='luxury_purchase',
            before=cash_before, after=float(agent.cash),
            cause_event_ids=([evaluation_id]
                             if evaluation_id is not None else None),
            formula_id='elite.luxury_purchase_priority.v1',
            inputs={'good': good_name, 'seller_id': str(seller.id),
                    'unit_price': float(price), 'quantity': 1,
                    'buyer_inventory_before': buyer_inventory_before,
                    'buyer_inventory_after': float(agent.inv_get(good, 0)),
                    'seller_cash_before': seller_cash_before,
                    'seller_cash_after': float(seller.cash),
                    'seller_inventory_before': seller_inventory_before,
                    'seller_inventory_after': float(seller.inv_get(good, 0))})
    if execution_id is not None:
        result['execution_event_ids'].append(execution_id)
    return result


def purchase_luxury(decision, trace):
    agent, region, t = decision.agent, decision.region, decision.turn
    result, trace_enabled = decision.result, decision.trace_enabled
    luxuries = decision.luxuries
    luxury_candidate_evaluations = [] if trace_enabled else None
    luxury_gate_open = bool(luxuries and agent.cash >= 25.0)
    if luxury_gate_open:
        luxuries.sort(key=lambda item: item[2] / max(1.0, item[1]), reverse=True)
        for index, (good, price, prestige, qty) in enumerate(luxuries):
            affordable = agent.cash >= price
            seller = (next((a for a in region.agents
                            if a.id != agent.id and a.alive
                            and a.inv_get(good, 0) > 0), None)
                      if affordable else None)
            good_name = good.name if hasattr(good, 'name') else str(good)
            price_event_id = None
            if trace_enabled:
                getter = getattr(getattr(region, '_run_trace', None),
                                 'latest_reference_price_event_id', None)
                if callable(getter):
                    price_event_id = getter(
                        getattr(region, 'name', 'default'), good_name)
            row = {
                'consideration_index': index,
                'good': good_name,
                'price': float(price),
                'prestige': float(prestige),
                'prestige_per_cash': float(prestige) / max(1.0, float(price)),
                'available_quantity': int(qty),
                'cash_before_candidate': float(agent.cash),
                'affordable': bool(affordable),
                'seller_id': (str(seller.id) if seller is not None else None),
                'seller_inventory': (float(seller.inv_get(good, 0))
                                     if seller is not None else 0.0),
                'price_trace_event_id': price_event_id,
                'selected': bool(affordable and seller is not None),
                'reason': ('selected_highest_ranked_purchasable_luxury'
                           if affordable and seller is not None else
                           'no_other_live_seller_with_stock' if affordable else
                           'cash_below_price')}
            if trace_enabled:
                luxury_candidate_evaluations.append(row)
            if seller:
                evaluation_id = trace.record_luxury_decision(
                    luxury_candidate_evaluations,
                    good_name, 'first_ranked_affordable_seller_found')
                return settle_luxury_purchase(decision, seller, good, price, good_name, evaluation_id)
    if trace_enabled:
        selection_reason = (
            'cash_below_minimum_gate' if luxuries and not luxury_gate_open else
            'no_purchasable_luxury_found' if luxuries else
            'no_available_luxury_inventory')
        evaluation_id = trace.record_luxury_decision(
            luxury_candidate_evaluations, None, selection_reason)
        if evaluation_id is not None:
            result['evaluation_event_ids'].append(evaluation_id)


def evaluate_spatial_trade(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
    """Spatial sales clear through trader routes and the destination auction.

    Kept as a no-op compatibility seam for the elite planner. Direct
    neighbor-to-neighbor inventory edits bypass freight, FX, and market
    prices; route traders now respond to profitable destinations and
    input shortages instead.
    """
    from run_trace import emit
    event_id = emit(
        region, kind='elite_spatial_trade_delegation', record_class='decision',
        phase='local', subject={'type': 'agent', 'id': agent.id,
                                'tile': getattr(region, 'name', 'default')},
        metric_id='ai.elite_economic_decision', unit='spatial_trade_stage',
        after='delegated_to_trader_routes',
        formula_id='elite.spatial_trade_delegation.v1',
        inputs={'turn': int(t), 'direct_neighbor_sale_enabled': False,
                'reason': ('route traders handle spatial goods movement through '
                           'freight, FX, and destination auctions'),
                'neighbor_names': sorted(getattr(region, 'neighbors', {}).keys()),
                'available_route_names': sorted(getattr(region, 'routes', {}).keys()),
                'active_trader_ids': [str(getattr(trader, 'id', 'unknown'))
                                      for trader in getattr(region, 'trader_agents', [])
                                      if getattr(trader, 'is_trader', False)
                                      and getattr(trader, 'alive', True)]})
    return ({'action_taken': None, 'details': {},
             'evaluation_event_ids': [event_id]}
            if event_id is not None else None)

"""Select a direct inventory buyer and settle the liquidation."""
from economy.actor_accounts import record
from goods import Goods
from run_trace import emit
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
from economy.transformation_graph import TransformationGraph
from economy.elite_treasury_trace import _trace_government_inventory_liquidation


def first_buyer(region, seller, price, candidate):
    for index, buyer in enumerate(region.agents):
        if buyer.id == seller.id:
            reason = 'seller_cannot_buy_own_inventory'
        elif not buyer.alive:
            reason = 'buyer_not_alive'
        elif buyer.cash < price:
            reason = 'buyer_cannot_afford_one_unit'
        else:
            reason = 'first_live_buyer_who_can_afford_one_unit'
        if candidate is not None:
            candidate['buyer_checks'].append({'order': index, 'agent_id': str(buyer.id),
                                               'cash': float(buyer.cash), 'reason': reason})
        if reason == 'first_live_buyer_who_can_afford_one_unit':
            return buyer
    return None


def settle_inventory_sale(decision, g, buyer, sale_qty, p, evaluation_event_id):
    agent, region, t = decision.agent, decision.region, decision.turn
    result = decision.result
    trade_cash = sale_qty * p
    seller_cash_before = float(agent.cash)
    buyer_cash_before = float(buyer.cash)
    seller_inventory_before = float(agent.inv_get(g, 0))
    buyer_inventory_before = float(buyer.inv_get(g, 0))
    _trace_cash_write = _trace_public_begin(None, buyer)
    buyer.cash -= trade_cash
    buyer_cash_write_ids = _trace_public_finish(
        _trace_cash_write,
        'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
        inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:8a474dde2fb88dbe:1'})
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash += trade_cash
    seller_cash_write_ids = _trace_public_finish(
        _trace_cash_write,
        'economy/capitalist_planner:EliteCapitalistPlanner._plan_and_execute_elite',
        inputs={"source_writer": 'economy/capitalist_planner.py:EliteCapitalistPlanner._plan_and_execute_elite:69cdbbf2dc1793ab:1'})
    agent.inv_add(g, -sale_qty)
    buyer.inv_add(g, sale_qty)
    record(region, 'spot_sale', turn=t, payer_id=buyer.id,
           recipient_id=agent.id, good=g, quantity=sale_qty, amount=trade_cash,
           detail={'settlement_path': 'elite_inventory_liquidation'})
    _trace_government_inventory_liquidation(
        region, seller=agent, buyer=buyer, good=g,
        quantity=sale_qty, amount=trade_cash, turn=t,
        seller_cash_before=seller_cash_before,
        seller_cash_after=agent.cash,
        seller_write_event_ids=seller_cash_write_ids,
        buyer_cash_before=buyer_cash_before,
        buyer_cash_after=buyer.cash,
        buyer_write_event_ids=buyer_cash_write_ids,
        decision_event_id=evaluation_event_id)
    result['action_taken'] = f'LIQUIDATE_{g.name.upper()}'
    result['details'] = {'good': g.name, 'quantity': sale_qty,
                         'cash_received': trade_cash,
                         'buyer_id': buyer.id,
                         'reference_unit_price': p,
                         'currency': getattr(region, 'home_currency', None),
                         'settlement_path': 'direct_inventory_transfer',
                         'currency_conversion_applied': False,
                         'seller_cash_before': seller_cash_before,
                         'seller_cash_after': float(agent.cash),
                         'buyer_cash_before': buyer_cash_before,
                         'buyer_cash_after': float(buyer.cash),
                         'seller_inventory_before': seller_inventory_before,
                         'seller_inventory_after': float(agent.inv_get(g, 0)),
                         'buyer_inventory_before': buyer_inventory_before,
                         'buyer_inventory_after': float(buyer.inv_get(g, 0))}
    return result


def liquidate_inventory(decision):
    agent, region, t = decision.agent, decision.region, decision.turn
    result, trace_enabled = decision.result, decision.trace_enabled
    liquidation_evaluations = [] if trace_enabled else None
    for g in getattr(region, 'goods', []):
        spec = TransformationGraph.get_commodity_spec(g)
        if spec and spec.prestige_rating == 0.0 and g != Goods.food:
            held = agent.inv_get(g, 0)
            if held <= 0:
                if trace_enabled:
                    liquidation_evaluations.append({
                        'good': getattr(g, 'name', str(g)),
                        'seller_inventory': float(held),
                        'reason': 'no_liquidatable_inventory'})
                continue

            p = float(region.recipes.get(g, {}).get('price', 1.0))
            candidate = ({'good': getattr(g, 'name', str(g)),
                          'seller_inventory': float(held), 'reference_price': p,
                          'price_basis': 'displayed_recipe_reference', 'buyer_checks': []}
                         if trace_enabled else None)
            buyer = first_buyer(region, agent, p, candidate)
            if buyer is None:
                if trace_enabled:
                    candidate['reason'] = 'no_live_buyer_can_afford_one_unit'
                    liquidation_evaluations.append(candidate)
                continue

            sale_qty = min(held, max(1, int(buyer.cash // p)))
            trade_cash = sale_qty * p
            evaluation_event_id = None
            if trace_enabled:
                candidate.update({
                    'reason': 'liquidation_selected',
                    'selected_buyer_id': str(buyer.id),
                    'buyer_affordable_quantity': int(buyer.cash // p),
                    'sale_quantity': float(sale_qty),
                    'cash_received': float(trade_cash),
                    'settlement_path': 'direct_inventory_transfer'})
                liquidation_evaluations.append(candidate)
                from run_trace import emit
                evaluation_event_id = emit(
                    region, kind='elite_inventory_liquidation_decision',
                    record_class='decision', phase='local',
                    subject={'type': 'agent', 'id': agent.id,
                             'tile': getattr(region, 'name', 'default')},
                    metric_id='ai.elite_economic_decision', unit='candidate',
                    after=f"LIQUIDATE_{getattr(g, 'name', str(g)).upper()}",
                    formula_id='elite.inventory_liquidation_gate.v1',
                    inputs={'decision_rule': (
                                'sell the first eligible non-luxury, non-food good '
                                'for which the seller has stock and the first live '
                                'non-seller buyer can afford one unit'),
                            'evaluated_goods': liquidation_evaluations,
                            'selected_good': getattr(g, 'name', str(g)),
                            'selected_buyer_id': str(buyer.id),
                            'unit_reference_price': p,
                            'sale_quantity': float(sale_qty),
                            'cash_received': float(trade_cash),
                            'settlement_path': 'direct_inventory_transfer'})
                if evaluation_event_id is not None:
                    result['evaluation_event_ids'].append(evaluation_event_id)

            return settle_inventory_sale(decision, g, buyer, sale_qty, p, evaluation_event_id)

    if trace_enabled:
        from run_trace import emit
        evaluation_event_id = emit(
            region, kind='elite_inventory_liquidation_decision',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': agent.id,
                     'tile': getattr(region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='candidate',
            after='continue', formula_id='elite.inventory_liquidation_gate.v1',
            inputs={'decision_rule': (
                        'sell the first eligible non-luxury, non-food good '
                        'for which the seller has stock and the first live '
                        'non-seller buyer can afford one unit'),
                    'evaluated_goods': liquidation_evaluations,
                    'reason': ('no eligible inventory goods'
                               if not liquidation_evaluations else
                               'no good had both seller inventory and an '
                               'affordable live buyer'),
                    'selected_good': None})
        if evaluation_event_id is not None:
            result['evaluation_event_ids'].append(evaluation_event_id)

    return result

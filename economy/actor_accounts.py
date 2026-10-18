"""Settled economic transfers and small per-actor turn statements.

This journal observes settlement; it never moves money or goods.  Its IDs remain
stable when optional causal tracing is disabled and survive pickle save/load.
"""
from __future__ import annotations

from goods import Goods


def _name(good):
    return getattr(good, 'name', str(good)) if good is not None else None


def record(region, kind, *, turn=None, payer_id=None, recipient_id=None,
           good=None, quantity=0, amount=0.0, debt_credit=0.0,
           asset_id=None, source_id=None, currency=None, detail=None):
    ident = int(getattr(region, '_next_economic_event_id', 1))
    region._next_economic_event_id = ident + 1
    event = {'id': ident, 'turn': int(turn if turn is not None else getattr(region, '_last_turn', 0)),
             'tile': region.name, 'kind': kind, 'payer_id': payer_id,
             'recipient_id': recipient_id, 'good': _name(good),
             'quantity': float(quantity), 'amount': float(amount),
             'debt_credit': float(debt_credit), 'asset_id': asset_id,
             'source_id': source_id,
             'currency': currency or getattr(region, 'home_currency', None),
             'detail': detail or {}}
    history = getattr(region, 'economic_events', [])
    history.append(event)
    region.economic_events = history[-2000:]
    return event


def begin_turn(region, turn):
    if getattr(region, 'tenure', None) is not None:
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
    region._economic_opening_turn = int(turn)
    region._economic_opening = {
        a.id: {'cash': float(getattr(a, 'cash', 0.0)),
               'scrip': float(getattr(a, 'scrip_wallet', 0.0)),
               'food': int(a.inv_get(Goods.food, 0)),
               'inventory': {g.name: int(a.inv_get(g, 0)) for g in getattr(region, 'recipes', {})},
               'debt': sum(float(c.balance) for c in getattr(region, 'cash_obligations', [])
                           if c.debtor_id == a.id and c.status == 'active'),
               'title_plots': [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                               if p.lord_id == a.id],
               'water_units': sum(float(r.units) for r in getattr(region, 'water_rights', [])
                                  if r.holder_id == a.id)}
        for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)}


def seal_turn(region, turn):
    """Seal observable results once; repeated snapshots cannot alter accounts."""
    if getattr(region, '_economic_sealed_turn', -1) == turn:
        return getattr(region, 'actor_turn_accounts', [])
    opening = getattr(region, '_economic_opening', {})
    events = [e for e in getattr(region, 'economic_events', []) if e['turn'] == turn]
    by_actor = {}
    for event in events:
        for ident in {event['payer_id'], event['recipient_id']} - {None}:
            by_actor.setdefault(ident, []).append(event)
    accounts = []
    for actor in getattr(region, 'agents', []):
        if actor.id not in opening:
            continue
        own = by_actor.get(actor.id, [])
        receipts = sum((e['detail'].get('seller_receipt', e['amount'])
                        if e['kind'] == 'spot_sale' else e['amount'])
                       for e in own if e['recipient_id'] == actor.id
                       and e['kind'] in ('spot_sale', 'contract_delivery'))
        crop_value = sum(e['amount'] + e['debt_credit'] for e in own
                         if e['recipient_id'] == actor.id
                         and e['kind'] in ('spot_sale', 'contract_delivery'))
        purchases = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                        and e['kind'] in ('spot_sale', 'contract_delivery'))
        recipe_input = getattr(region, 'recipes', {}).get(getattr(actor, 'output', None), {}).get('input')
        delivered_imports = [e for e in own if e['payer_id'] == actor.id
                             and e['kind'] == 'spot_sale'
                             and e['good'] == _name(recipe_input)
                             and e['detail'].get('imported', False)]
        delivered_input_spend = sum(e['amount'] for e in delivered_imports)
        delivered_input_units = sum(e['quantity'] for e in delivered_imports)
        wages = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                    and e['kind'] == 'wage')
        other_costs = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                          and e['kind'] in ('freight', 'petition_fee', 'rent', 'tax', 'cash_tax'))
        # Purchases are working inventory. Cost of goods sold needs the later
        # production-consumption posting; never expense purchases twice.
        input_used = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                         and e['kind'] == 'input_consumed')
        prior = opening[actor.id]
        noncash = ('production', 'input_consumed', 'scrip_wage',
                   'scrip_store_sale', 'scrip_food_credit')
        cash_in = sum((e['detail'].get('seller_receipt', e['amount'])
                       if e['kind'] == 'spot_sale' else e['amount'])
                      for e in own if e['recipient_id'] == actor.id
                      and e['kind'] not in noncash)
        cash_out = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                       and e['kind'] not in noncash)
        observed_cash_change = float(actor.cash) - prior['cash']
        financing = sum(e['amount'] for e in own if e['recipient_id'] == actor.id
                        and e['kind'] == 'owner_financing')
        fx_received = sum(e['amount'] for e in own if e['recipient_id'] == actor.id
                          and e['kind'] == 'fx_conversion')
        fx_paid = sum(e['amount'] for e in own if e['payer_id'] == actor.id
                      and e['kind'] == 'fx_conversion')
        for_lease = [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                     if getattr(p, 'controlled_by_id', None) == actor.id]
        debt = sum(float(c.balance) for c in getattr(region, 'cash_obligations', [])
                   if c.debtor_id == actor.id and c.status == 'active')
        output = getattr(actor, 'output', None)
        output_name = _name(output)
        produced = sum(e['quantity'] for e in events if e['recipient_id'] == actor.id
                       and e['kind'] == 'production' and e['good'] == output_name)
        accounts.append({
            'turn': int(turn), 'actor_id': actor.id,
            'actor_name': getattr(actor, 'company_name', None) or
                          getattr(actor, 'display_name', None) or f'Actor {actor.id}',
            'type': 'corporation' if getattr(actor, 'is_corporation', False) else
                    'grower' if output in (Goods.food, Goods.cotton, Goods.sugar, Goods.tobacco) else 'other',
            'output': output_name, 'opening_cash': round(prior['cash'], 2),
            'closing_cash': round(float(actor.cash), 2),
            'opening_scrip': round(prior['scrip'], 2),
            'closing_scrip': round(float(getattr(actor, 'scrip_wallet', 0.0)), 2),
            'scrip_change': round(float(getattr(actor, 'scrip_wallet', 0.0)) - prior['scrip'], 2),
            'cash_change': round(float(actor.cash) - prior['cash'], 2),
            'posted_cash_change': round(cash_in - cash_out, 2),
            'unposted_cash_change': round(observed_cash_change - (cash_in - cash_out), 2),
            'owner_financing_received': round(financing, 2),
            'fx_converted_in': round(fx_received, 2),
            'fx_converted_out': round(fx_paid, 2),
            'opening_food': prior['food'], 'closing_food': int(actor.inv_get(Goods.food, 0)),
            'food_intake': round(float(getattr(actor, 'last_calories_eaten', 0.0)) / 500.0, 2),
            'opening_debt': round(prior['debt'], 2), 'closing_debt': round(debt, 2),
            'sales_cash': round(receipts, 2), 'crop_value': round(crop_value, 2),
            'purchases_cash': round(purchases, 2), 'wages_cash': round(wages, 2),
            'delivered_input_purchase_cash': round(delivered_input_spend, 2),
            'delivered_input_purchase_units': round(delivered_input_units, 2),
            'delivered_input_unit_price': round(delivered_input_spend / delivered_input_units, 2)
            if delivered_input_units else None,
            'delivered_input_lots': [
                {'event_id': e['id'], 'shipment_id': e['detail'].get('shipment_id'),
                 'quantity': e['quantity'], 'paid_unit_price': e['detail'].get('unit_price'),
                 'source_unit_cost': e['detail'].get('source_unit_cost'),
                 'freight_per_unit': e['detail'].get('freight_per_unit'),
                 'source_currency': e['detail'].get('source_currency')}
                for e in delivered_imports],
            'other_costs_cash': round(other_costs, 2),
            'input_consumed_cost': round(input_used, 2),
            'operating_result_recorded': round(receipts - wages - other_costs - input_used, 2),
            'operating_result_complete': False,
            'produced_units': produced,
            'opening_output_stock': prior['inventory'].get(output_name, 0),
            'closing_output_stock': int(actor.inv_get(output, 0)) if output is not None else 0,
            'opening_title_plots': prior['title_plots'],
            'closing_title_plots': [p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                                    if p.lord_id == actor.id],
            'leased_control_plots': for_lease,
            'opening_water_units': round(prior['water_units'], 3),
            'closing_water_units': round(sum(float(r.units) for r in getattr(region, 'water_rights', [])
                                             if r.holder_id == actor.id), 3),
            'event_ids': [e['id'] for e in own[-30:]],
        })
    region.actor_turn_accounts = accounts
    region._economic_sealed_turn = int(turn)
    history = getattr(region, 'actor_account_history', [])
    history.extend(accounts)
    region.actor_account_history = history[-600:]
    return accounts

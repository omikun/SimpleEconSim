"""Comparable near-term valuations for input-supply actions.

Values are private actor estimates in local currency, not realized profit.
They use observed quotes/fills and seller outside options, never future draws.
"""
from __future__ import annotations


def value_options(agent, region, options):
    recipe = region.recipes.get(agent.output, {})
    good = recipe.get('input')
    if good is None or not options:
        return options
    input_per_batch = max(1.0, float(recipe.get('numInput', 1)))
    good_price = max(.01, float(region.recipes.get(good, {}).get('price', 1.0)))
    output_price = max(0.0, float(recipe.get('price', 0.0)))
    payroll = max(0.0, float(getattr(agent, 'wage', 0.0))) * len(getattr(agent, 'employees', []))
    history = [a for a in getattr(region, 'actor_account_history', [])[-600:]
               if a['actor_id'] == agent.id and a['turn'] < getattr(region, '_last_turn', 0)]
    recent = history[-3:]
    produced = sum(float(a['produced_units']) for a in recent)
    sold = sum(float(a['sales_cash']) for a in recent) / max(.01, output_price)
    saleability = min(1.0, max(.2, sold / produced)) if produced > 0 else .65
    unit_output_value = (float(recipe.get('production', 0.0)) * output_price
                         * saleability - payroll) / input_per_batch
    unit_margin = unit_output_value - good_price
    needed = max(1, int(input_per_batch * max(1, len(getattr(agent, 'employees', [])))))
    missing = max(0, needed - int(agent.inv_get(good, 0)))
    prior_trades = [e for e in getattr(region, 'market_trade_events', [])
                    if e['good'] == good.name and e['turn'] < getattr(region, '_last_turn', 0)
                    and e['turn'] >= getattr(region, '_last_turn', 0) - 3]
    own_fills = sum(e['quantity'] for e in prior_trades if e['buyer_id'] == agent.id)
    fill_probability = min(.85, max(.15, own_fills / max(1, needed * 3)))
    imported = sum(e['quantity'] for e in prior_trades if e['imported'])
    route_probability = min(.65, imported / max(1, needed * 3))
    ordinary_fill = max(fill_probability, route_probability)
    baseline = max(0.0, missing * ordinary_fill * unit_margin)
    cash_runway = float(agent.cash) / max(1.0, payroll)
    scored = []
    now = int(getattr(region, '_last_turn', 0))
    rejected = {(e.get('kind'), e.get('seller_id')) for e in
                getattr(region, 'supply_proposal_events', [])
                if e.get('status') == 'rejected' and now - int(e.get('turn', 0)) < 5}
    for raw in options:
        row = dict(raw)
        kind = row['candidate']
        row['baseline_expected_value'] = round(baseline, 2)
        row['unit_output_value'] = round(unit_output_value, 2)
        row['unit_margin_at_quote'] = round(unit_margin, 2)
        row['observed_fill_probability'] = round(ordinary_fill, 3)
        row['saleability_estimate'] = round(saleability, 3)
        row['cash_runway_payrolls'] = round(cash_runway, 2)
        row['horizon_turns'] = 3
        gain = float('-inf')
        if kind == 'advance_offtake' and row.get('feasible'):
            from supply_proposals import reservation
            seller = next((a for a in region.agents if a.id == row['grower_id']), None)
            if seller is not None:
                offer = {'kind': kind, 'seller_id': seller.id, 'good': row['good'],
                         'quantity': row['quantity'], 'price': row['advance']}
                minimum, basis = reservation(region, offer)
                offered_crop = row['quantity'] * row['unit_price']
                accept = .9 if offered_crop >= minimum else 0.0
                delivery = min(missing, row['quantity']) * .7 * accept
                extra_fill = delivery * (1.0 - ordinary_fill) * max(0.0, unit_output_value - row['unit_price'])
                cheaper_fill = delivery * ordinary_fill * max(0.0, good_price - row['unit_price'])
                financing_cost = .05 * row['advance']
                default_loss = .12 * row['advance']
                gain = extra_fill + cheaper_fill - financing_cost - default_loss
                row.update({'acceptance_probability': accept, 'delivery_probability': .7,
                            'seller_reservation': round(minimum, 2),
                            'seller_reservation_basis': basis,
                            'finance_cost': round(financing_cost, 2),
                            'default_loss_estimate': round(default_loss, 2)})
        elif kind == 'acquire_water_right':
            contract = any(c.get('status') == 'active' and c.get('grower_id') == row.get('grower_id')
                           and c.get('lender_id') == agent.id
                           for c in getattr(region, 'offtake_contracts', []))
            if contract and row.get('feasible'):
                extra_crop = min(missing, float(row['units']) * 2.0)
                gain = extra_crop * max(0.0, unit_margin) * .6 - float(row['price'])
                row['expected_extra_crop'] = round(extra_crop, 2)
            else:
                row['feasible'] = False
                row['reason'] = 'water on another plot does not secure crop without a contract'
        elif kind == 'lease_input_land':
            row['feasible'] = False
            row['reason'] = 'lease keeps tenant crop; no direct input delivery or cultivation right yet'
        elif kind == 'exclusive_processing_charter' and row.get('feasible'):
            rivals = sum(1 for a in region.agents if a.id != agent.id
                         and getattr(a, 'is_corporation', False)
                         and region.recipes.get(a.output, {}).get('input') == good)
            approval, enforcement = .45, float(getattr(region, 'concession_enforcement', .65))
            extra_fill = min(missing, rivals * 2) * approval * enforcement * .5
            gain = extra_fill * max(0.0, unit_margin) - float(row['fee'])
            row.update({'approval_probability': approval,
                        'enforcement_probability': enforcement,
                        'rival_input_buyers': rivals, 'expected_extra_fill': round(extra_fill, 2)})
        elif kind == 'reduce_or_pause_output':
            gain = 0.0
        row['expected_incremental_value'] = round(gain, 2) if gain != float('-inf') else None
        row['score'] = max(0.0, gain) if gain != float('-inf') else 0.0
        if cash_runway < 1.0 and kind in ('advance_offtake', 'acquire_water_right',
                                         'lease_input_land', 'exclusive_processing_charter'):
            row['feasible'] = False
            row['reason'] = 'less than one payroll of cash runway'
            row['score'] = 0.0
        proposal_kind = {'acquire_water_right': 'water_right',
                         'lease_input_land': 'land_lease'}.get(kind, kind)
        target_seller = row.get('grower_id') if kind == 'advance_offtake' else row.get('seller_id')
        if (proposal_kind, target_seller) in rejected:
            row['feasible'] = False
            row['score'] = 0.0
            row['reason'] = 'seller recently rejected this offer; five-turn cooling period'
        scored.append(row)
    scored.append({'candidate': 'spot_or_route', 'feasible': True,
                   'good': good.name, 'shortage': missing, 'score': 0.0,
                   'expected_incremental_value': 0.0,
                   'baseline_expected_value': round(baseline, 2),
                   'unit_output_value': round(unit_output_value, 2),
                   'observed_fill_probability': round(ordinary_fill, 3),
                   'reason': 'ordinary funded auction and trader route remain available'})
    return scored

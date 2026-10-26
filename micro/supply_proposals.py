"""Negotiated offers for advances, plot control, and water rights."""
from __future__ import annotations

from goods import Goods


TYPES = frozenset({'advance_offtake', 'crop_advance', 'land_lease', 'land_sale', 'water_right'})


def authorized(region, proposal_id, buyer_id, seller_id, kinds):
    return any(p['id'] == proposal_id and p['status'] == 'accepted'
               and p['buyer_id'] == buyer_id and p['seller_id'] == seller_id
               and p['kind'] in kinds for p in getattr(region, 'supply_proposals', []))


def _agents(region):
    return {a.id: a for a in getattr(region, 'agents', [])}


def _good(region, name):
    return next((g for g in getattr(region, 'recipes', {}) if g.name == name), None)


def _valid(region, proposal):
    actors = _agents(region)
    buyer, seller = actors.get(proposal['buyer_id']), actors.get(proposal['seller_id'])
    if buyer is None or seller is None or buyer is seller or not buyer.alive or not seller.alive:
        return False, 'party_unavailable'
    price = float(proposal.get('price', 0.0))
    if price < 0 or buyer.cash < price:
        return False, 'buyer_funds'
    kind = proposal['kind']
    if kind in ('advance_offtake', 'crop_advance'):
        plot = region.tenure.find_plot(proposal['plot_id']) if getattr(region, 'tenure', None) else None
        good = _good(region, proposal['good'])
        if plot is None or good is None or seller.id not in plot.tenant_ids or seller.output != good:
            return False, 'cultivator_or_plot_changed'
        if kind == 'advance_offtake':
            if int(proposal['quantity']) <= 0 or float(proposal['unit_price']) <= 0:
                return False, 'invalid_crop_terms'
            committed = sum(int(c.get('remaining', 0)) for c in getattr(region, 'offtake_contracts', [])
                            if c.get('status') == 'active' and c.get('grower_id') == seller.id
                            and c.get('good') == proposal['good'])
            expected = max(1, int(region.recipes[good].get('production', 4)))
            if good == Goods.food:
                expected = max(0, expected - 4)
            if committed + int(proposal['quantity']) > expected:
                return False, 'harvest_already_pledged'
    elif kind in ('land_lease', 'land_sale'):
        plot = region.tenure.find_plot(proposal['plot_id']) if getattr(region, 'tenure', None) else None
        if plot is None or plot.lord_id != seller.id or seller.is_government:
            return False, 'title_unavailable'
        if any(l.get('status') == 'active' and l.get('plot_id') == proposal['plot_id']
               for l in getattr(region, 'land_leases', [])):
            return False, 'plot_already_leased'
    elif kind == 'water_right':
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
        units = float(proposal.get('units', 0))
        if units <= 0:
            return False, 'invalid_water_units'
        if not any(r.holder_id == seller.id and r.plot_id == proposal['from_plot_id']
                   and r.units >= units for r in region.water_rights):
            return False, 'water_right_unavailable'
        source = next(r for r in region.water_rights if r.holder_id == seller.id
                      and r.plot_id == proposal['from_plot_id'] and r.units >= units)
        if source.units - units < .5 and any(a.output == Goods.food and
                                            getattr(a, 'assigned_plot_id', None) == source.plot_id
                                            for a in region.agents):
            return False, 'protected_food_water_minimum'
        if region.tenure.find_plot(proposal['to_plot_id']) is None:
            return False, 'target_plot_unavailable'
    return True, 'eligible'


def propose(region, kind, buyer, seller, *, turn, price, cause_event_ids=None, **terms):
    """Create an offer without moving money, goods, debt, title, or water."""
    if kind not in TYPES or buyer is None or seller is None:
        return None
    proposal = {'id': int(getattr(region, '_next_supply_proposal_id', 1)),
                'kind': kind, 'buyer_id': buyer.id, 'seller_id': seller.id,
                'buyer_name': getattr(buyer, 'company_name', None) or
                              getattr(buyer, 'display_name', None) or f'Actor {buyer.id}',
                'seller_name': getattr(seller, 'display_name', None) or f'Actor {seller.id}',
                'created_turn': int(turn), 'decision_turn': int(turn) + 1,
                'expiry_turn': int(turn) + 3, 'price': max(0.0, float(price)),
                'status': 'proposed', 'round': 0,
                'planner_decision_event_ids': list(cause_event_ids or ()), **terms}
    key = (kind, seller.id, proposal.get('plot_id', proposal.get('from_plot_id')))
    if any((p['kind'], p['seller_id'], p.get('plot_id', p.get('from_plot_id'))) == key
           and p['status'] in ('proposed', 'countered')
           for p in getattr(region, 'supply_proposals', [])):
        return None
    valid, reason = _valid(region, proposal)
    if not valid:
        return None
    region._next_supply_proposal_id = proposal['id'] + 1
    region.supply_proposals = (getattr(region, 'supply_proposals', []) + [proposal])[-300:]
    from run_trace import emit
    proposal['offer_event_id'] = emit(region, kind='supply_offer', record_class='decision',
         subject={'type': 'agent', 'id': buyer.id},
         metric_id='market.supply_offer', unit='proposal', after=proposal['id'],
         formula_id='supply.offer.v1', inputs=dict(proposal),
         cause_event_ids=cause_event_ids)
    return proposal


def reservation(region, proposal):
    """Seller's observable outside value; the estimate is not a cash posting."""
    seller = _agents(region).get(proposal['seller_id'])
    if seller is None:
        return float('inf'), {'reason': 'seller_unavailable'}
    kind = proposal['kind']
    food_price = float(region.recipes.get(Goods.food, {}).get('price', 1.0))
    if kind in ('advance_offtake', 'crop_advance'):
        good = _good(region, proposal['good'])
        spot = float(region.recipes.get(good, {}).get('price', 1.0))
        quantity = int(proposal.get('quantity', 0))
        existing = sum(float(c.balance) for c in getattr(region, 'cash_obligations', [])
                       if c.debtor_id == seller.id and c.status == 'active')
        food_shortfall = max(0.0, 4.0 - seller.inv_get(Goods.food, 0)) * food_price
        liquidity_need = max(0.0, existing + food_shortfall - max(0.0, seller.cash))
        advance = float(proposal['price'])
        liquidity_value = min(advance * .4, liquidity_need * .5)
        outside = quantity * spot if kind == 'advance_offtake' else 0.0
        return max(.01, outside - liquidity_value), {
            'spot_quote': spot, 'quantity': quantity, 'cash': float(seller.cash),
            'debt_due': existing, 'food_shortfall_value': food_shortfall,
            'early_liquidity_value': liquidity_value}
    if kind in ('land_lease', 'land_sale'):
        plot = region.tenure.find_plot(proposal['plot_id'])
        annual_rent = float(getattr(plot, 'rent_rate', 0.0)) * float(plot.fraction) * food_price * 10
        title_value = max(5.0, float(plot.fraction) * food_price * 20.0)
        minimum = annual_rent * (float(proposal.get('lease_turns', 10)) / 10.0) if kind == 'land_lease' else title_value
        return minimum, {'annual_rent_value': annual_rent, 'title_value': title_value,
                         'tenants_retained': list(plot.tenant_ids)}
    plot = region.tenure.find_plot(proposal['from_plot_id'])
    units = float(proposal['units'])
    crop = next((a.output for a in getattr(region, 'agents', [])
                 if getattr(a, 'assigned_plot_id', None) == plot.plot_id), Goods.food)
    crop_price = float(region.recipes.get(crop, {}).get('price', food_price))
    value = units * crop_price * max(1.0, float(plot.fraction) * 4.0)
    return value, {'crop': crop.name, 'crop_quote': crop_price,
                   'units_lost': units, 'plot_fraction': float(plot.fraction)}


def _settle(region, proposal, turn):
    actors = _agents(region)
    buyer, seller = actors[proposal['buyer_id']], actors[proposal['seller_id']]
    kind = proposal['kind']
    if kind == 'advance_offtake':
        from crop_credit import offer_advance
        result = offer_advance(buyer, seller, region, proposal['price'],
                               proposal['due_turn'], proposal['plot_id'],
                               interest_rate=proposal.get('interest_rate', 0.0),
                               lien_share=proposal.get('lien_share', .5),
                               offtake_quantity=proposal['quantity'],
                               offtake_price=proposal['unit_price'],
                               accepted_proposal_id=proposal['id'])
        return {'claim_id': result.id} if result is not None else None
    if kind == 'crop_advance':
        from crop_credit import offer_advance
        result = offer_advance(buyer, seller, region, proposal['price'],
                               proposal['due_turn'], proposal['plot_id'],
                               interest_rate=proposal.get('interest_rate', 0.0),
                               lien_share=proposal.get('lien_share', .5),
                               accepted_proposal_id=proposal['id'])
        return {'claim_id': result.id} if result is not None else None
    if kind in ('land_lease', 'land_sale'):
        from supply_rights import transfer_plot_title
        return transfer_plot_title(region, seller, buyer, proposal['plot_id'],
                                   proposal['price'], turn=turn,
                                   lease_turns=proposal.get('lease_turns', 0),
                                   accepted_proposal_id=proposal['id'])
    from supply_rights import acquire_water_right
    return acquire_water_right(region, seller, buyer, proposal['from_plot_id'],
                               proposal['to_plot_id'], proposal['units'],
                               proposal['price'], turn,
                               accepted_proposal_id=proposal['id'])


def decide(region, turn):
    """Resolve due offers in stable order, with at most one seller counteroffer."""
    outcomes = []
    for proposal in sorted(getattr(region, 'supply_proposals', []), key=lambda p: p['id']):
        if proposal['status'] not in ('proposed', 'countered') or turn < proposal['decision_turn']:
            continue
        valid, reason = _valid(region, proposal)
        if turn > proposal['expiry_turn']:
            proposal['status'], reason = 'expired', 'deadline'
        elif not valid:
            proposal['status'] = 'rejected'
        elif proposal['status'] == 'countered':
            if float(proposal.get('max_price', proposal['price'])) >= proposal['price']:
                proposal['status'] = 'accepted'
                result = _settle(region, proposal, turn)
                proposal['status'] = 'settled' if result is not None else 'rejected'
                proposal['result'] = result
                reason = 'buyer_accepted_counter' if result is not None else 'settlement_failed'
            else:
                proposal['status'], reason = 'rejected', 'buyer_declined_counter'
        else:
            minimum, basis = reservation(region, proposal)
            proposal['reservation_value'] = round(minimum, 3)
            proposal['reservation_basis'] = basis
            offered = (float(proposal['quantity']) * float(proposal['unit_price'])
                       if proposal['kind'] == 'advance_offtake' else proposal['price'])
            if offered + 1e-9 >= minimum:
                proposal['status'] = 'accepted'
                result = _settle(region, proposal, turn)
                proposal['status'] = 'settled' if result is not None else 'rejected'
                proposal['result'] = result
                reason = 'seller_accepted' if result is not None else 'settlement_failed'
            elif offered >= minimum * .75 and proposal['kind'] not in ('advance_offtake', 'crop_advance'):
                proposal['status'] = 'countered'
                proposal['round'] = 1
                proposal['price'] = round(minimum, 2)
                proposal['decision_turn'] = int(turn) + 1
                reason = 'seller_countered_at_reservation'
            else:
                proposal['status'], reason = 'rejected', 'below_seller_outside_option'
        event = {'turn': int(turn), 'proposal_id': proposal['id'],
                 'kind': proposal['kind'], 'buyer_id': proposal['buyer_id'],
                 'seller_id': proposal['seller_id'], 'status': proposal['status'],
                 'reason': reason, 'reservation_value': proposal.get('reservation_value'),
                 'price': proposal['price']}
        outcomes.append(event)
        from run_trace import emit
        emit(region, kind='supply_offer_decision', record_class='outcome',
             subject={'type': 'proposal', 'id': proposal['id']},
             metric_id='market.supply_offer_status', unit='status',
             after=proposal['status'], formula_id='supply.reservation_decision.v1',
             inputs={**event, 'reservation_basis': proposal.get('reservation_basis')},
             cause_event_ids=([proposal['offer_event_id']]
                              if proposal.get('offer_event_id') else [])
             + list(proposal.get('planner_decision_event_ids') or ()))
    region.supply_proposal_events = (getattr(region, 'supply_proposal_events', []) + outcomes)[-300:]
    return outcomes

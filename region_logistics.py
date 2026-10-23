"""
Inter-region transport routes, trader arbitrage repointing, migration scoring, and trader exits.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

import math

from goods import Goods
from transporter import Route
from logger import loginfo
from random_cache import rand


def migration_intent_score(region):
    """Compute a per-tile migration intent score (M1.5)."""
    return migration_intent_components(region)['score']


def migration_intent_components(region):
    """Return the score and observable inputs used by the migration pressure gate."""
    agents = region.agents
    if not agents:
        return {'score': 0.0, 'average_wage_memory': 0.0, 'wage_intent': 0.0,
                'local_food_price': None, 'average_neighbor_food_price': None,
                'food_price_differential': 0.0, 'average_risk_tolerance': 0.0}
    wage_scores = []
    for a in agents:
        avg = getattr(a, 'mem_avg', lambda k, d=0.0: d)('mem_wages', None)
        if avg is not None:
            wage_scores.append(avg)
    avg_wage = sum(wage_scores) / len(wage_scores) if wage_scores else 0.0
    wage_intent = 0.0
    if avg_wage > 0 and avg_wage < 5.0:
        wage_intent = 1.0 - (avg_wage / 5.0)
    diff = 0.0
    if region.neighbors:
        local_food = region.recipes.get(Goods.food, {}).get('price', 1.0)
        neighbor_prices = [
            other.recipes.get(Goods.food, {}).get('price', 1.0)
            for other in region.neighbors.values()
            if getattr(other, 'recipes', None)
        ]
        if neighbor_prices:
            avg_neighbor = sum(neighbor_prices) / len(neighbor_prices)
            if avg_neighbor > 0:
                diff = max(0.0, (local_food - avg_neighbor) / max(1.0, avg_neighbor))
    risk = sum(getattr(a, 'risk_tolerance', 0.5) for a in agents) / len(agents)
    score = wage_intent * 0.5 + diff * (0.5 + risk)
    return {'score': max(0.0, min(10.0, score)),
            'average_wage_memory': avg_wage, 'wage_intent': wage_intent,
            'local_food_price': float(local_food) if region.neighbors else None,
            'average_neighbor_food_price': (sum(neighbor_prices) / len(neighbor_prices)
                                            if region.neighbors and neighbor_prices else None),
            'food_price_differential': diff, 'average_risk_tolerance': risk}


def add_neighbor(region, other, t=0):
    """Register *other* as a reachable tile of *region*."""
    region.neighbors[other.name] = other
    route = Route(f"{region.name}->{other.name}", region, other,
                  base_delay=region.transport_delay)
    region.routes[other.name] = route
    if region.destination_region is None:
        region.destination_region = other
        region.route = route
        for trader in region.trader_agents:
            trader.destination_region = other
    return route


def all_routes(region):
    """Every directional Route owned by this region (multi-route aware)."""
    if region.routes:
        return list(region.routes.values())
    return [region.route] if region.route is not None else []


def transport_cost_per_unit(region):
    """Home-currency transport cost to move one unit of a good."""
    capacity = region.recipes.get(Goods.transport, {}).get('capacity', 10)
    return region.recipes[Goods.transport]['price'] / max(1, capacity)


def repoint_traders(region):
    """Route traders toward profitable neighbors, including requested inputs."""
    from world_trade import TRADE_GOODS
    from run_trace import emit

    trace_recorder = getattr(region, '_run_trace', None)
    trace_enabled = (trace_recorder is not None
                     and getattr(region, '_collective_trace_clock', None) is not None)
    if not region.neighbors and not trace_enabled:
        return

    def price_event_id(tile_id, good):
        getter = getattr(trace_recorder, 'latest_reference_price_event_id', None)
        if not callable(getter):
            return None
        return getter(str(tile_id), getattr(good, 'name', str(good)))

    def trace_safe(value):
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else str(value)
        if isinstance(value, dict):
            return {str(key): trace_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [trace_safe(item) for item in value]
        return str(value)

    base_freight = transport_cost_per_unit(region) if region.neighbors else 0.0
    for trader in region.trader_agents:
        if not getattr(trader, 'is_trader', False) or not getattr(trader, 'alive', True):
            continue
        previous_destination = getattr(
            getattr(trader, 'destination_region', None), 'name', None)
        previous_good = getattr(getattr(trader, 'trade_good', None), 'name',
                                getattr(trader, 'trade_good', None))
        best = None
        best_score = -1e18
        evaluated = [] if trace_enabled else None
        skipped_neighbors = [] if trace_enabled else None
        rejection_counts = {} if trace_enabled else None
        price_cause_ids = [] if trace_enabled else None

        def reject(reason):
            if trace_enabled:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

        def candidate_row(name, good, **details):
            if trace_enabled:
                evaluated.append({'destination': str(name),
                                  'good': getattr(good, 'name', str(good)),
                                  **details})

        if not region.neighbors and trace_enabled:
            skipped_neighbors.append({'destination': None,
                                      'reason': 'no_neighbor_regions'})
        for name, other in region.neighbors.items():
            if not other or getattr(other, 'recipes', None) is None:
                reject('destination_market_unavailable')
                if trace_enabled:
                    skipped_neighbors.append({'destination': str(name),
                                              'reason': 'destination_market_unavailable'})
                continue
            if name not in region.routes:
                reject('route_missing')
                if trace_enabled:
                    skipped_neighbors.append({'destination': str(name),
                                              'reason': 'route_missing'})
                continue
            from terrain_edges import get_edge_manager
            em = get_edge_manager()
            frict = em.get_friction(region.name, other.name) if em else 1.0
            if frict == float('inf'):
                reject('route_blocked_by_edge')
                if trace_enabled:
                    skipped_neighbors.append({'destination': str(name),
                                              'reason': 'route_blocked_by_edge'})
                continue
            desk = region.forex_desks.get(name)
            rate = desk.buy_rate() if desk is not None else 1.0
            gov = getattr(other, 'gov', None)
            fee = (gov.get_trade_fee_multiplier(include_import_tariff=False)
                   if gov is not None else 1.0)
            from economy.trade_costs import import_tariff_terms
            tariff, drawback, effective_tariff = import_tariff_terms(
                other, getattr(region, 'home_currency', None))
            for good in TRADE_GOODS:
                if good not in region.recipes or good not in other.recipes:
                    reject('good_not_quoted_in_both_markets')
                    continue
                local_price = float(region.recipes[good].get('price', 0.0))
                dest_price = float(other.recipes[good].get('price', 0.0))
                source_price_id = price_event_id(region.name, good) if trace_enabled else None
                destination_price_id = price_event_id(other.name, good) if trace_enabled else None
                if trace_enabled:
                    for event_id in (source_price_id, destination_price_id):
                        if event_id is not None and event_id not in price_cause_ids:
                            price_cause_ids.append(event_id)
                if local_price <= 0 or dest_price <= 0:
                    reject('nonpositive_market_price')
                    candidate_row(name, good, status='rejected',
                                  reason='nonpositive_market_price',
                                  source_price=local_price,
                                  destination_price=dest_price,
                                  source_price_trace_event_id=source_price_id,
                                  destination_price_trace_event_id=destination_price_id)
                    continue
                freight = base_freight * max(0.2, frict)
                net_receipt = dest_price * rate * fee * (1.0 - effective_tariff)
                unit_margin = net_receipt - local_price - freight
                required_margin = local_price * region.IMPORT_MARGIN_MIN
                if unit_margin <= required_margin:
                    reject('margin_does_not_exceed_required_threshold')
                    candidate_row(name, good, status='rejected',
                                  reason='margin_does_not_exceed_required_threshold',
                                  source_price=local_price,
                                  destination_price=dest_price,
                                  import_margin_min=region.IMPORT_MARGIN_MIN,
                                  fx_buy_rate=rate, destination_fee_multiplier=fee,
                                  nominal_tariff_rate=tariff,
                                  drawback_rate=drawback,
                                  effective_tariff_rate=effective_tariff,
                                  base_freight_per_unit=base_freight,
                                  edge_friction_multiplier=frict,
                                  freight_per_unit=freight, net_receipt=net_receipt,
                                  unit_margin=unit_margin,
                                  required_margin=required_margin,
                                  source_price_trace_event_id=source_price_id,
                                  destination_price_trace_event_id=destination_price_id)
                    continue
                requested = 0
                requesters = [] if trace_enabled else None
                demand_diagnostics = ({'eligible_corporation_count': 0,
                                       'zero_shortfall_count': 0,
                                       'cash_limited_below_one_unit_count': 0}
                                      if trace_enabled else None)
                for company in getattr(other, 'agents', ()):
                    if (not getattr(company, 'alive', True)
                            or not getattr(company, 'is_corporation', False)):
                        continue
                    recipe = other.recipes.get(company.output, {})
                    if recipe.get('input') != good:
                        continue
                    target = float(recipe.get('numInput', 0)) * 2 * (1 + len(company.employees))
                    shortfall = max(0.0, target - company.inv_get(good, 0))
                    affordable = (company.cash / max(0.05, dest_price)
                                  if dest_price > 0 else 0.0)
                    requested_units = int(min(shortfall, affordable))
                    requested += requested_units
                    if trace_enabled:
                        demand_diagnostics['eligible_corporation_count'] += 1
                        if shortfall <= 0:
                            demand_diagnostics['zero_shortfall_count'] += 1
                        elif requested_units <= 0:
                            demand_diagnostics[
                                'cash_limited_below_one_unit_count'] += 1
                        if requested_units > 0:
                            requesters.append({
                                'company_id': str(getattr(company, 'id', 'unknown')),
                                'input_target': target,
                                'inventory': float(company.inv_get(good, 0)),
                                'shortfall': shortfall,
                                'cash': float(company.cash),
                                'cash_affordable_units': affordable,
                                'requested_units': requested_units})
                # Input demand selects among otherwise profitable routes and
                # gives firms' missing materials a visible supply response.
                demand_bonus = min(local_price * 0.20,
                                   local_price * 0.05 * requested)
                score = unit_margin - required_margin + demand_bonus
                best_score_before = best_score
                selected_as_best = score > best_score
                if score > best_score:
                    best_score = score
                    best = (other, good)
                if trace_enabled:
                    row = {
                        'status': 'profitable_candidate',
                        'reason': 'margin_exceeds_required_threshold',
                        'source_price': local_price,
                        'destination_price': dest_price,
                        'import_margin_min': region.IMPORT_MARGIN_MIN,
                        'fx_buy_rate': rate,
                        'destination_fee_multiplier': fee,
                        'nominal_tariff_rate': tariff,
                        'drawback_rate': drawback,
                        'effective_tariff_rate': effective_tariff,
                        'base_freight_per_unit': base_freight,
                        'edge_friction_multiplier': frict,
                        'freight_per_unit': freight,
                        'net_receipt': net_receipt,
                        'unit_margin': unit_margin,
                        'required_margin': required_margin,
                        'requested_input_units': requested,
                        'input_demand_diagnostics': demand_diagnostics,
                        'requesting_corporations': requesters,
                        'demand_bonus': demand_bonus,
                        'score': score,
                        'best_score_before': (best_score_before
                                              if best_score_before > -1e17 else None),
                        'selected_as_best': selected_as_best,
                        'source_price_trace_event_id': source_price_id,
                        'destination_price_trace_event_id': destination_price_id}
                    evaluated.append({'destination': str(name),
                                      'good': getattr(good, 'name', str(good)),
                                      **row})
        selected = best is not None and best_score > 0
        if selected:
            trader.destination_region, trader.trade_good = best
        if trace_enabled:
            selected_destination = best[0].name if selected else previous_destination
            selected_good = (getattr(best[1], 'name', str(best[1]))
                             if selected else previous_good)
            route_changed = (selected and
                             (selected_destination != previous_destination
                              or selected_good != previous_good))
            if not evaluated and not skipped_neighbors:
                rejection_counts['no_eligible_market_goods'] = 1
            evaluation_id = emit(
                region, kind='trader_route_decision', record_class='decision',
                phase='trade',
                subject={'type': 'agent', 'id': trader.id,
                         'tile': getattr(region, 'name', 'default')},
                metric_id='trade.route_destination_decision', unit='destination_good',
                before=(previous_destination, previous_good),
                after=(selected_destination, selected_good),
                formula_id='route.trader_destination_score.v1',
                cause_event_ids=price_cause_ids or None,
                inputs=trace_safe({
                    'turn': int(getattr(region, '_collective_trace_clock', {}).get(
                        'turn', getattr(region, '_last_turn', 0))),
                    'starting_destination': previous_destination,
                    'starting_good': previous_good,
                    'candidate_evaluations': evaluated,
                    'skipped_neighbors': skipped_neighbors,
                    'rejection_counts': rejection_counts,
                    'candidate_count': len(evaluated),
                    'selected_destination': (str(selected_destination)
                                             if selected_destination is not None else None),
                    'selected_good': selected_good,
                    'best_score': best_score if selected else None,
                    'required_margin_formula': 'source_price * IMPORT_MARGIN_MIN',
                    'net_receipt_formula': ('destination_price * fx_buy_rate * '
                                             'destination_fee * (1 - effective_tariff)'),
                    'unit_margin_formula': 'net_receipt - source_price - freight_per_unit',
                    'freight_formula': ('base_freight_per_unit * '
                                        'max(0.2, edge_friction_multiplier)'),
                    'input_target_formula': ('numInput * 2 * '
                                             '(1 + corporation_employee_count)'),
                    'score_formula': ('unit_margin - required_margin + demand_bonus'),
                    'demand_bonus_formula': ('min(source_price * 0.20, '
                                             'source_price * 0.05 * requested_input_units)'),
                    'selection_rule': 'strictly_greater_score_then_positive_score',
                    'route_assignment_changed': bool(route_changed),
                    'selection_reason': (
                        'highest_positive_score_selected' if selected else
                        'no_positive_profitable_route')}))
            if route_changed:
                emit(region, kind='trader_route_assignment',
                     record_class='outcome', phase='trade',
                     subject={'type': 'agent', 'id': trader.id,
                              'tile': getattr(region, 'name', 'default')},
                     metric_id='trade.route_destination_decision', unit='destination_good',
                     before=(previous_destination, previous_good),
                     after=(str(selected_destination), selected_good),
                     formula_id='route.trader_destination_score.v1',
                     cause_event_ids=([evaluation_id]
                                      if evaluation_id is not None else None),
                     inputs={'selected_score': best_score,
                             'assignment_applied': True})


def post_exports_to_route(region):
    """Move all traders' export inventory onto their destination Route."""
    from world_trade import TRADE_GOODS
    if not all_routes(region):
        return
    for trader in region.trader_agents:
        if not trader.is_trader:
            continue
        dest = getattr(trader, 'destination_region', None)
        route = None
        if dest is not None:
            route = region.routes.get(dest.name)
        if route is None:
            route = region.route
        if route is None:
            continue
        for g in TRADE_GOODS:
            qty = trader.inventory_export[g.value]
            permitted_qty = qty
            charters = [c for c in getattr(region, 'market_charters', [])
                        if c.get('status') == 'active' and c.get('type') == 'exclusive_route'
                        and c.get('good') == getattr(g, 'value', str(g))
                        and c.get('start_turn', 0) <= getattr(region, '_last_turn', 0) < c.get('expiry_turn', 0)]
            if charters and qty > 0:
                charter = sorted(charters, key=lambda c: c['id'])[0]
                owner = getattr(trader, 'owner', None)
                authorized = trader.id == charter['sponsor_id'] or getattr(owner, 'id', None) == charter['sponsor_id']
                if not authorized:
                    enforcement = max(0.0, min(1.0, float(charter.get('enforcement', .65))))
                    permitted = int(qty * (1.0 - enforcement))
                    charter['opposition'] = float(charter.get('opposition', 0.0)) + max(1.0, (qty - permitted) / 3.0)
                    from run_trace import emit
                    emit(region, kind='route_charter_enforcement', record_class='calculation',
                         subject={'type': 'charter', 'id': charter['id']},
                         metric_id='trade.route_licensed_quantity', unit='units',
                         before=qty, after=permitted, formula_id='charter.route_leakage.v1',
                         inputs={'good': g.name, 'trader_id': trader.id,
                                 'authorized_sponsor_id': charter['sponsor_id'],
                                 'enforcement': enforcement})
                    permitted_qty = permitted
            if g == Goods.food:
                export_fraction = max(0.0, min(1.0, float(getattr(region, 'food_export_fraction', 1.0))))
                if export_fraction < 1.0 and qty > 0:
                    available_food_export = qty
                    export_qty = int(qty * export_fraction)
                    retained = qty - export_qty
                    trader.inventory_export[g.value] -= retained
                    region.granary_stock = float(getattr(region, 'granary_stock', 0.0)) + retained
                    qty = min(permitted_qty, export_qty)
                    from run_trace import emit
                    emit(region, kind='route_food_export_retained',
                         record_class='calculation',
                         subject={'type': 'tile', 'id': region.name, 'good': g.name},
                         metric_id='trade.export_quantity', unit='units',
                         before=available_food_export, after=qty,
                         formula_id='route.food_export_fraction.v1',
                         inputs={'trader_id': trader.id,
                                 'food_export_fraction': export_fraction,
                                 'charter_permitted_quantity': permitted_qty,
                                 'retained_quantity': retained,
                                 'granary_stock_after': region.granary_stock})
            else:
                qty = permitted_qty
            if qty > 0:
                carrier = getattr(getattr(region, 'gov', None), 'agent', None)
                has_transport_quote = Goods.transport in getattr(region, 'recipes', {})
                freight_unit = (max(0.0, float(transport_cost_per_unit(region)))
                                if carrier is not None and has_transport_quote else 0.0)
                if carrier is not None and freight_unit > 0:
                    submitted_qty = qty
                    spendable_cash = max(0.0, float(trader.cash))
                    qty = min(qty, int(spendable_cash / freight_unit))
                    if qty < submitted_qty:
                        from run_trace import emit
                        emit(region, kind='route_freight_affordability_limit',
                             record_class='calculation',
                             subject={'type': 'tile', 'id': region.name,
                                      'good': g.name},
                             metric_id='trade.export_quantity', unit='units',
                             before=submitted_qty, after=qty,
                             formula_id='route.freight_affordability.v1',
                             inputs={'trader_id': trader.id,
                                     'destination': route.dst.name,
                                     'route': route.name,
                                     'freight_per_unit': freight_unit,
                                     'spendable_cash': spendable_cash,
                                     'affordable_quantity': qty})
                unit_cost = float(trader.cost_get(g, 0.0))
                moved = route.post(trader, g, qty, unit_cost=unit_cost,
                                   freight_per_unit=freight_unit,
                                   source_currency=getattr(region, 'home_currency', None))
                if moved and carrier is not None and freight_unit > 0:
                    freight = moved * freight_unit
                    trader_cash_before = float(trader.cash)
                    carrier_cash_before = float(carrier.cash)
                    from treasury_trace import begin_public_change,finish_public_change
                    payer_public_change=begin_public_change(region,trader)
                    carrier_public_change=begin_public_change(region,carrier)
                    trader.cash -= freight
                    carrier.cash += freight
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(region, 'freight', payer_id=trader.id,
                                          recipient_id=carrier.id, good=g, quantity=moved,
                                          amount=freight, asset_id=route.name,
                                          detail={'destination': route.dst.name,
                                                  'unit_cost': freight_unit})
                    from run_trace import emit
                    shipment_id = route.pending[-1][4]
                    trace = getattr(region, '_run_trace', None)
                    departure_event_id = (
                        trace.shipment_event_id(shipment_id, 'departure')
                        if trace is not None and hasattr(trace, 'shipment_event_id')
                        else None)
                    freight_event_id=emit(region, kind='route_freight_settlement',
                         record_class='transfer',
                         subject={'type': 'shipment', 'id': shipment_id},
                         metric_id='trade.route_freight_settlement',
                         unit=getattr(region, 'home_currency', None),
                         after=freight,
                         formula_id='route.freight_settlement.v1',
                         cause_event_ids=([departure_event_id]
                                          if departure_event_id is not None else None),
                         inputs={'operation_id': f'freight:{shipment_id}',
                                 'route': route.name,
                                 'source': region.name,
                                 'destination': route.dst.name,
                                 'good': g.name, 'quantity': moved,
                                 'payer_id': trader.id,
                                 'recipient_id': carrier.id,
                                 'amount': freight,
                                 'freight_per_unit': freight_unit,
                                 'payer_cash_before': trader_cash_before,
                                 'payer_cash_after': trader.cash,
                                 'recipient_cash_before': carrier_cash_before,
                                 'recipient_cash_after': carrier.cash})
                    from finance_trace import emit_public_account_flow
                    for context,actor,amount in ((payer_public_change,trader,-freight),
                                                 (carrier_public_change,carrier,freight)):
                        writes=finish_public_change(context,'route_freight_settlement',
                            inputs={'semantic_operation_id':f'freight:{shipment_id}'},
                            cause_event_ids=[freight_event_id] if freight_event_id else None)
                        emit_public_account_flow(region,actor,kind='government_route_freight_settlement',
                            signed_amount=amount,inputs={'operation_id':f'freight:{shipment_id}'},
                            cause_event_ids=([freight_event_id] if freight_event_id else [])+writes)
                if moved:
                    shipment = route.pending[-1]
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(region, 'shipment_departure',
                                          payer_id=trader.id, good=g, quantity=moved,
                                          asset_id=shipment[4],
                                          currency=getattr(region, 'home_currency', None),
                                          detail={'destination': route.dst.name,
                                                  'source_unit_cost': unit_cost,
                                                  'freight_per_unit': freight_unit,
                                                  'shipment_id': shipment[4],
                                                  'source_shipment_id': shipment[8],
                                                  'source_region': shipment[9],
                                                  'source_cost_status': shipment[10],
                                                  'route_history': list(shipment[11]),
                                                  'source_acquisitions': list(shipment[12])})


def liquidation_price(good, cost_basis):
    """Discounted resale price (70% of cost basis) for trader exit lots."""
    return max(0.05, cost_basis * 0.7)


def give_goods(agent, good, qty, price):
    """Add *qty* of *good* to *agent*'s local inventory."""
    old_q = agent.inv_get(good, 0)
    old_c = agent.cost_get(good, 0)
    total_q = old_q + qty
    new_cost = ((old_q * old_c + qty * price) / total_q) if total_q > 0 else price
    agent.cost_set(good, new_cost)
    agent.inv_add(good, qty)


def exit_trader(region, agent):
    """Liquidate a trader's goods and loans, then exit the profession."""
    # 1. Reclaim any cargo still in transit back to the exporter
    for rt in all_routes(region):
        rt.reclaim(agent)

    from world_trade import TRADE_GOODS
    # 2. Gather all tradable lots (export + foreign + parked)
    lots = []
    for g in TRADE_GOODS:
        qty = (agent.inventory_export[g.value]
               + agent.inventory_foreign[g.value]
               + agent.parked_total(g))
        if qty > 0:
            lots.append((g, qty, agent.cost_get(g, 0)))

    # 3. Sell lots to another home-region trader at a discount
    buyers = [a for a in region.trader_agents
              if a is not agent and getattr(a, 'is_trader', False)]
    for good, qty, cost in lots:
        price = liquidation_price(good, cost)
        buyer = None
        for cand in buyers:
            if (cand.trade_good == good or cand.trade_good is None) \
                    and cand.cash >= price * qty:
                buyer = cand
                break
        if buyer is not None:
            total = price * qty
            _trace_cash_write = _trace_public_begin(None, buyer)
            buyer.cash -= total
            _trace_public_finish(_trace_cash_write, 'region_logistics:exit_trader',
                                 inputs={"source_writer": 'region_logistics.py:exit_trader:040390b75623bc79:1'})
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash += total
            _trace_public_finish(_trace_cash_write, 'region_logistics:exit_trader',
                                 inputs={"source_writer": 'region_logistics.py:exit_trader:17eef11acf9bae3a:1'})
            give_goods(buyer, good, qty, price)
            loginfo(0, f"liquidation: {agent.name()} sold {qty} {good} "
                    f"to {buyer.name()} at ${price:.2f}")
        else:
            region.gov.receive_food(qty) if good == Goods.food else None
            region.gov.agent.inv_add(good, qty) if good != Goods.food else None
            loginfo(0, f"liquidation: {agent.name()} {qty} {good} "
                    f"escheated to gov inventory")
        agent.inventory_export[good.value] = 0
        agent.inventory_foreign[good.value] = 0
        agent.parked_foreign = {}
    agent.trade_acquisition_lots = []

    # 4. Pay down loans with all remaining liquid cash
    while agent.cash > 0 and agent.loans:
        loan = agent.loans[0]
        payment = min(agent.cash, loan.getPaymentAmount())
        if payment <= 0:
            break
        _trace_cash_write = _trace_public_begin(None, agent)
        agent.cash -= payment
        _trace_public_finish(_trace_cash_write, 'region_logistics:exit_trader',
                             inputs={"source_writer": 'region_logistics.py:exit_trader:46411047f1496360:1'})
        loan.pay(payment)
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(region, 'bank_loan_repayment', turn=getattr(region, '_last_turn', 0),
                              payer_id=agent.id, amount=payment,
                              detail={'trader_exit_settlement': True})
        if loan.isPaid():
            agent.loans.pop(0)

    # 5. End the trade spell; the person's prior livelihood remains intact.
    from labor_choice import record_labor_status
    turn = int(getattr(region, '_last_turn', 0) or 0)
    agent.is_trader = False
    record_labor_status(region, agent, turn, before='trader', after='independent',
                        reason='unprofitable_trader_exit')
    agent.trade_good = None
    agent.employer = None


def process_trader_exits(region, t, agents):
    """Evaluate trader profitability and exit unprofitable traders every 20 turns."""
    if t % 20 != 0:
        return
    col = region.cost_of_living
    grace_period = 40
    for agent in agents:
        if not agent.is_trader or not agent.alive:
            continue
        age = t - agent.birth_round
        if age < grace_period:
            agent._trader_revenue_check = agent._trader_revenue
            continue
        period_revenue = agent._trader_revenue - agent._trader_revenue_check
        committed = 0.0
        for g in Goods:
            if g == Goods.none or g == Goods.transport:
                continue
            q = (agent.inventory_export[g.value]
                 + agent.inventory_foreign[g.value]
                 + agent.parked_total(g))
            for rt in all_routes(region):
                q += rt.holdings_of(agent).get(g, 0)
            if q > 0:
                committed += q * agent.cost_get(g, 0)
        benchmark = col + 0.02 * committed
        if period_revenue < benchmark:
            exit_trader(region, agent)
            loginfo(t, f"{agent.name()} exited trading "
                    f"(revenue ${period_revenue:.0f} < ${benchmark:.0f})")
        agent._trader_revenue_check = agent._trader_revenue


def make_trader_internal(region, agent):
    """Set an agent's fields to make them a trader."""
    from labor_choice import record_labor_status
    turn = int(getattr(region, '_last_turn', 0) or 0)
    best_good = Goods.food
    best_gap = -1.0
    dest = region.destination_region
    if dest is not None:
        from world_trade import TRADE_GOODS
        for g in TRADE_GOODS:
            if g not in dest.recipes or g not in region.recipes:
                continue
            gap = dest.recipes[g]['price'] - region.recipes[g]['price']
            if gap > best_gap:
                best_gap = gap
                best_good = g
    old_employer = agent.employer
    if old_employer is not None:
        if agent in getattr(old_employer, 'employees', []):
            old_employer.employees.remove(agent)
        agreement = getattr(agent, 'labor_agreement', None)
        if agreement is not None:
            agreement.active = False
    agent.employer = None
    agent.is_trader = True
    agent.home_region = region.name
    agent.destination_region = region.destination_region
    record_labor_status(region, agent, turn,
                        before='employed' if old_employer is not None else 'independent',
                        after='trader', reason='entered_trading',
                        employer_before=old_employer)
    agent.trade_good = best_good
    for g in Goods:
        if g == Goods.none:
            continue
        agent.inventory_export[g.value] = 0
        agent.inventory_foreign[g.value] = 0
    agent.trade_acquisition_lots = []
    agent.parked_foreign = {}
    for rt in all_routes(region):
        rt.reclaim(agent)

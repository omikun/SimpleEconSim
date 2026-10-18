"""Market clearing, order prices, reference updates, and bid/ask mechanics."""

import math
from goods import Goods
from logger import loginfo
import econsim_trade_money as _tm
import forex as _fx
from region_logistics import all_routes, transport_cost_per_unit


def borrow_food(region, agent, food_price):
    from nutrition import food_credit_pressure
    from random_cache import rand
    pressure = food_credit_pressure(agent)
    if agent.output != Goods.food and agent.cash < food_price \
       and pressure > 0 and rand.random() < pressure:
        bank_balance = region.bank.deposits.get(agent, 0)
        if bank_balance > 0:
            region.bank.Withdraw(agent, min(bank_balance, food_price - agent.cash))
        if agent.cash < food_price:
            region.bank.Borrow(0, agent, food_price, trace_region=region)


def borrow_inputs(region, agent):
    r = region.recipes.get(agent.output)
    if not r or r.get('numInput', 0) <= 0:
        return
    cost = region.recipes[r['input']]['price'] * r['numInput']
    if agent.cash >= cost:
        return
    bank_balance = region.bank.deposits.get(agent, 0)
    if bank_balance > 0:
        region.bank.Withdraw(agent, min(bank_balance, cost - agent.cash))
    if agent.cash < cost:
        region.bank.Borrow(0, agent, cost - agent.cash, trace_region=region)


def deposit_excess(region, agent, all_goods_price):
    mult = agent.consumption_multiplier
    total_liquid = agent.cash + region.bank.deposits.get(agent, 0)
    current_deposits = region.bank.deposits.get(agent, 0)
    if agent.is_trader:
        deposit_fraction = 0.10
        cash_floor = int(region.cost_of_living * 5) + int(all_goods_price * 15)
    else:
        deposit_fraction = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
        cash_floor = int(all_goods_price * (100 / max(1.0, mult)))
    max_deposits = max(0.0, total_liquid - cash_floor) * deposit_fraction
    excess = max(0, max_deposits - current_deposits)
    if agent.cash > cash_floor and excess > 0:
        region.bank.Deposit(agent, min(agent.cash - cash_floor, excess))


def decide_borrow_deposit(region, agents, all_goods_price, food_price, t):
    for a in agents:
        if getattr(a, 'military_unit_id', None):
            continue
        _tm.borrow_if_needed(t, a, bank=region.bank, trace_region=region)
        _tm.PayLoans(a, bank=region.bank, trace_region=region)
        borrow_food(region, a, food_price)
        borrow_inputs(region, a)
        deposit_excess(region, a, all_goods_price)
        if a.is_trader:
            trader_reserve = region.cost_of_living * 5
            total_liquid = a.cash + region.bank.deposits.get(a, 0)
            if total_liquid < trader_reserve:
                region.bank.Borrow(t, a, trader_reserve - total_liquid, trace_region=region)
            dest = a.destination_region
            if dest is not None:
                fee = (dest.gov.get_trade_fee_multiplier()
                       if dest.gov is not None else region._trade_fee_mult)
                for g in [Goods.wood, Goods.furniture]:
                    local = region.recipes.get(g, {}).get('price', 0)
                    if local <= 0:
                        continue
                    remote = dest.recipes.get(g, {}).get('price', 0)
                    effective = remote * fee
                    if effective > local * 1.01:
                        target = local * 15 + trader_reserve
                        total_liquid = a.cash + region.bank.deposits.get(a, 0)
                        if total_liquid < target:
                            region.bank.Borrow(t, a, target - total_liquid, trace_region=region)
                        break
        a.remainingCash = a.cash


def withdraw_if_needed(region, agent, good_price, current_desired):
    bank_balance = region.bank.deposits.get(agent, 0)
    if bank_balance > 0 and agent.remainingCash < good_price * current_desired:
        region.bank.Withdraw(agent, min(bank_balance, good_price * current_desired - agent.remainingCash))


def input_good(region, agent):
    if getattr(agent, 'output', Goods.none) not in region.recipes:
        return Goods.none
    return region.recipes[agent.output].get('input', Goods.none)


def food_reserve_units(agent):
    """Food a living grower keeps for the next meal before offering surplus."""
    from nutrition import appetite_units
    return appetite_units(agent)


def emergency_food_surplus(agent):
    """Food a public buyer may purchase without taking a person's next meal."""
    if not agent.alive or agent.is_government:
        return 0
    reserve = 0 if agent.is_corporation else food_reserve_units(agent)
    return max(0, agent.inv_get(Goods.food, 0) - reserve)


def calculate_bid(region, agent, good, good_price, current_desired, agent_recipe, is_employee, mult):
    if good == Goods.transport and not agent.is_trader:
        return 0
    if agent.is_trader:
        if good == Goods.food:
            food_on_hand = agent.inv_get(Goods.food, 0)
            need = max(0, 8 - food_on_hand)
            spendable = max(0, agent.remainingCash - region.cost_of_living * 5)
            affordable = int(spendable // good_price)
            return min(need, affordable)
        if agent.trade_good is not None and good != agent.trade_good:
            return 0
        destination = agent.destination_region
        if destination is not None:
            dest_price = destination.recipes.get(good, {}).get('price', 0)
            min_margin = region.IMPORT_MARGIN_MIN
            desk = region.forex_desks.get(destination.name) or getattr(region, 'forex', None)
            home_per_dest = desk.buy_rate() if desk is not None else 1.0
            net_foreign = dest_price * home_per_dest
            t_cost = transport_cost_per_unit(region)
            if net_foreign <= (good_price + t_cost) * (1.0 + min_margin):
                return 0
        max_trader_inventory = region.recipes.get(good, {}).get(
            'maxinv', agent_recipe.get('maxinv', 10))
        total_holding = agent.inv_get(good, 0) + agent.inventory_export[good.value] + agent.inventory_foreign[good.value]
        for rt in all_routes(region):
            total_holding += rt.holdings_of(agent).get(good, 0)
        space = max(0, max_trader_inventory - total_holding)
        spendable = max(0, agent.remainingCash - region.cost_of_living * 5)
        if space <= 0 or spendable < good_price:
            return 0
        affordable = spendable // good_price
        bid = min(space, affordable)
        return max(0, bid)
    if (good == Goods.food and agent.output == Goods.food
            and not agent.is_corporation and not agent.is_government):
        missing_meal = max(0, food_reserve_units(agent) - agent.inv_get(Goods.food, 0))
        affordable = int(agent.remainingCash // good_price) if good_price > 0 else missing_meal
        return min(missing_meal, max(0, affordable))
    if not is_employee and input_good(region, agent) == good:
        num_employees = len(agent.employees) if agent.is_corporation else 0
        desired = max(0, agent_recipe['numInput'] * 2 * (1 + num_employees) - agent.inv_get(good, 0))
        if mult > 1.0:
            desired = int(desired * mult)
        affordable = agent.remainingCash // good_price if good_price > 0 else desired
        return int(min(desired, affordable))
    elif (is_employee or agent.output != good) and agent.remainingCash > good_price:
        if good == Goods.food:
            max_inventory_limit = agent_recipe['maxinv']
            if agent.is_corporation:
                max_inventory_limit *= (1 + len(agent.employees))
            if mult > 1.0:
                max_inventory_limit = int(max_inventory_limit * min(mult, 3.0))
            num_storable = max(0, max_inventory_limit - agent.inv_get(good, 0))
            base_desire = min(current_desired, agent.remainingCash // good_price)
            bid = min(int(base_desire * mult), num_storable)
            return max(0, min(bid, num_storable))
        spendable = max(0.0, agent.remainingCash - 2.0 * getattr(region, 'food_price', 1.0))
        if spendable < good_price:
            return 0
        if good == Goods.wood:
            max_inventory_limit = 3 if mult <= 1.5 else int(3 * min(mult, 2.5))
            eff_desired = min(current_desired, 2)
        elif good == Goods.furniture:
            max_inventory_limit = max(2, int(3 * min(mult, 3.0)))
            eff_desired = min(current_desired, 2)
        else:
            if mult <= 1.05 and not getattr(agent, 'is_lord', False):
                return 0
            max_inventory_limit = max(2, int(2 * min(mult, 3.0)))
            eff_desired = min(current_desired, 2)
        if agent.is_corporation:
            max_inventory_limit *= (1 + len(agent.employees))
        num_storable = max(0, max_inventory_limit - agent.inv_get(good, 0))
        base_desire = min(eff_desired, int(spendable // good_price)) if good_price > 0 else eff_desired
        bid = min(int(max(base_desire, base_desire * mult)), num_storable)
        return max(0, min(bid, num_storable))
    return 0


def excess_non_producer_saleable(region, agent, good):
    """Return excess inventory a non-producer household/lord can sell on the market."""
    if (getattr(agent, 'is_trader', False) or getattr(agent, 'is_government', False)
            or agent.output == good or agent.output == Goods.gov
            or good in (Goods.food, Goods.transport, Goods.gov, Goods.none)):
        return 0
    if input_good(region, agent) == good:
        return 0
    stock = int(agent.inv_get(good, 0))
    if stock <= 0:
        return 0
    if good == Goods.wood:
        reserve = 3
    elif good == Goods.furniture:
        reserve = 2
    else:
        reserve = 0
    return max(0, stock - reserve)


def calculate_ask(region, agent, good, good_price, is_employee):
    if (good == Goods.food and agent.id == getattr(region, 'scenario_grain_holder_id', None)
            and getattr(region, 'scenario_grain_policy', 'open') == 'hold'):
        stock = max(0, agent.inv_get(Goods.food, 0))
        reserved = min(stock, max(0, int(getattr(region, 'scenario_grain_reserved_units', 0))))
        return min(stock, stock - reserved +
                   max(0, int(getattr(region, 'scenario_grain_offer_units', 0))))
    if agent.is_trader:
        dest = getattr(agent, 'destination_region', None) or region.destination_region
        if dest is not None:
            desk = region.forex_desks.get(dest.name) or getattr(region, 'forex', None)
            fx_rate = desk.buy_rate() if desk is not None else region.exchange_rate
            fee = dest.gov.get_trade_fee_multiplier() if dest.gov is not None else region._trade_fee_mult
            foreign_net = dest.recipes.get(good, {}).get('price', 0) * fee * fx_rate
            if good_price <= foreign_net:
                return 0
        return max(0, agent.inventory_export[good.value])
    if is_employee:
        return 0
    if agent.output != good and agent.output != Goods.gov:
        return excess_non_producer_saleable(region, agent, good)
    if agent.output == good or (agent.output == Goods.gov and agent.inv_get(good, 0) > 0):
        cost_to_make = 0.0
        agent_recipe = region.recipes.get(good, {})
        if agent.output == good and agent_recipe.get('numInput', 0) > 0 and agent_recipe.get('production', 0) > 0:
            cost_to_make = (agent_recipe['numInput'] * agent.cost_get(agent_recipe['input'], 0)) / agent_recipe['production']
        if good == Goods.food and agent.output == Goods.food:
            return max(0, agent.inv_get(good, 0) - food_reserve_units(agent))
        elif good_price >= cost_to_make:
            return max(0, agent.inv_get(good, 0))
    return 0


def calculate_transport_bid(region, agent, transport_price):
    """Traders bid transport based on goods waiting in export inventory."""
    if not agent.is_trader:
        return 0
    capacity = region.recipes[Goods.transport]['capacity']
    from world_trade import TRADE_GOODS
    total_export = sum(agent.inventory_export[g.value] for g in TRADE_GOODS)
    if total_export <= 0:
        return 0
    needed = max(1, (total_export + capacity - 1) // capacity)
    spendable = max(0, agent.remainingCash - region.cost_of_living * 5)
    affordable = int(spendable // transport_price) if transport_price > 0 else needed
    max_buy = min(needed, region.recipes[Goods.transport]['maxinv'])
    return min(max_buy, affordable)


def calculate_ask_price(region, agent, good, ref):
    """Per-agent local ask price for output *good*."""
    if agent.is_trader or agent.output != good:
        return ref
    stock = agent.inv_get(good, 0)
    maxinv = region.recipes.get(good, {}).get('maxinv', 10)
    ratio = stock / max(1, maxinv)
    scarcity = 1.10 - 0.30 * max(0.0, min(1.0, ratio))
    hungry = getattr(agent, 'hungry_steps', 0)
    urgency = max(0.0, 1.0 - 0.12 * hungry)
    mult = scarcity * urgency
    mult = max(region.ASK_URGENCY_MIN, min(region.ASK_URGENCY_MAX, mult))
    ask = ref * mult
    from run_trace import emit
    emit(region, kind='local_seller_ask', record_class='calculation',
         subject={'type': 'tile', 'id': region.name, 'good': good.name,
                  'seller_id': agent.id},
         metric_id='goods.seller_ask', unit='local_currency_per_unit',
         after=ask, formula_id='market.local_ask.v1',
         inputs={'reference': ref, 'stock': stock, 'max_inventory': maxinv,
                 'hungry_steps': hungry, 'scarcity_multiplier': scarcity,
                 'urgency_multiplier': urgency, 'bounded_multiplier': mult,
                 'urgency_min': region.ASK_URGENCY_MIN,
                 'urgency_max': region.ASK_URGENCY_MAX,
                 'currency': region.home_currency})
    return ask


def calculate_bid_limit(region, agent, good, ref, demand_ratio, quantity):
    """Maximum price this submitted order will pay per unit.

    The reference is the neutral quote. Funded excess demand raises the limit
    gradually, allowing competing buyers to bid for scarce stock.
    """
    if quantity <= 0 or ref <= 0:
        return 0.0
    pressure = max(0.0, min(2.0, float(demand_ratio) - 1.0))
    premium = min(0.50, pressure * 0.20)
    need_premium = 0.0
    if good == Goods.food and not getattr(agent, 'is_corporation', False):
        need_premium = min(0.75, max(0.0, getattr(agent, 'hungry_steps', 0) * 0.05))
    limit = ref * (1.0 + max(premium, need_premium))

    # Bound productive buyers by output value after direct payroll. This is a
    # ceiling, not a profit forecast: debts, transport, and unsold output can
    # still make the recipe unprofitable.
    if input_good(region, agent) == good:
        recipe = region.recipes.get(agent.output, {})
        input_units = max(0.0, float(recipe.get('numInput', 0)))
        output_units = max(0.0, float(recipe.get('production', 0)))
        if input_units > 0 and output_units > 0:
            output_value = output_units * float(
                region.recipes.get(agent.output, {}).get('price', 0.0))
            payroll = max(0.0, float(getattr(agent, 'wage', 0.0))
                         * len(getattr(agent, 'employees', ())))
            limit = min(limit, max(0.0, (output_value - payroll) / input_units))

    if getattr(agent, 'is_trader', False):
        dest = getattr(agent, 'destination_region', None) or region.destination_region
        if dest is not None:
            desk = region.forex_desks.get(dest.name) or getattr(region, 'forex', None)
            fx_rate = desk.buy_rate() if desk is not None else region.exchange_rate
            fee = (dest.gov.get_trade_fee_multiplier(include_import_tariff=False)
                   if dest.gov is not None else region._trade_fee_mult)
            from economy.trade_costs import import_tariff_terms
            tariff, drawback, effective_tariff = import_tariff_terms(
                dest, getattr(agent, 'home_currency', region.home_currency))
            destination_value = (dest.recipes.get(good, {}).get('price', 0.0)
                                 * fee * fx_rate * (1.0 - effective_tariff))
            limit = min(limit, max(0.0, destination_value - transport_cost_per_unit(region)))

    available_cash = max(0.0, getattr(agent, 'cash', 0.0))
    return max(0.0, min(limit, available_cash / quantity))


def import_ask_price(region, trader, good, *, source_unit_cost=None,
                     freight_per_unit=0.0, source_currency=None,
                     source_region_name=None, shipment_id=None,
                     source_cost_status=None):
    """Ask for one imported lot using its landed cost and tariff terms."""
    source_region_name = source_region_name or getattr(trader, 'home_region', None)
    src_region = (region.neighbors.get(source_region_name)
                  or getattr(region, 'destination_region', None))
    if source_unit_cost is not None:
        cost_home = float(source_unit_cost)
        quote_cost_basis = 'shipment_lot_source_cost'
    else:
        cost_home = float(trader.cost_get(good, 0.0))
        quote_cost_basis = 'trader_average_cost'
    if cost_home <= 0.05 + 1e-9 and src_region is not None:
        cost_home = max(0.05, src_region.recipes.get(good, {}).get('price', 0.0))
        quote_cost_basis = 'source_reference_price'
    cost_home = max(0.05, cost_home)
    freight_per_unit = max(0.0, float(freight_per_unit or 0.0))
    source_currency = (source_currency or getattr(src_region, 'home_currency', None)
                       or getattr(trader, 'home_currency', None))
    from economy.inventory_provenance import source_to_destination_rate
    fx_source_to_destination, fx_method = source_to_destination_rate(
        region, source_region_name, source_currency)
    if fx_source_to_destination is None:
        # Keep legacy shipments tradable when a bilateral desk is absent, but
        # make the parity assumption explicit in the quote trace.
        fx_source_to_destination = 1.0
        fx_method = 'parity_assumed_no_bilateral_rate'
    landed_cost_source = cost_home + freight_per_unit
    landed_cost_destination = landed_cost_source * fx_source_to_destination
    margin = region.IMPORT_MARGIN_MIN + (
        region.IMPORT_MARGIN_MAX - region.IMPORT_MARGIN_MIN) * (
            abs(hash((trader.id, good))) % 1000) / 1000.0
    from economy.trade_costs import import_tariff_terms
    tariff, drawback, effective_tariff = import_tariff_terms(
        region, getattr(trader, 'home_currency', source_currency))
    denom = max(0.05, 1.0 - effective_tariff)
    break_even_ask = landed_cost_destination / denom
    uncapped_ask = break_even_ask * (1.0 + margin)
    ask = uncapped_ask
    dest_price = region.recipes.get(good, {}).get('price', 0.0)
    cap = None
    cap_binding = False
    cap_below_break_even = False
    if dest_price > 0:
        cap = dest_price * (1.0 + region.IMPORT_MARGIN_MIN)
        cap_below_break_even = cap + 1e-9 < break_even_ask
        cap_binding = cap + 1e-9 < ask and not cap_below_break_even
        ask = max(break_even_ask, min(ask, cap))
    ask = max(0.05, ask)
    from run_trace import emit
    emit(region, kind='import_delivered_quote', record_class='calculation',
         subject={'type': 'tile', 'id': region.name, 'good': good.name,
                  'seller_id': trader.id, 'shipment_id': shipment_id},
         metric_id='goods.delivered_quote', unit='local_currency_per_unit',
         after=ask, formula_id='market.import_ask.landed_cost.v2',
         inputs={'source_tile': src_region.name if src_region is not None else None,
                 'shipment_id': shipment_id,
                         'source_cost_status': source_cost_status,
                 'source_unit_cost': source_unit_cost,
                 'quote_cost_basis_unit_cost': cost_home,
                 'quote_cost_basis': quote_cost_basis,
                 'freight_per_unit': freight_per_unit,
                 'landed_cost_source_currency': landed_cost_source,
                 'landed_cost_destination_currency': landed_cost_destination,
                 'source_currency': source_currency,
                 'fx_source_to_destination_rate': fx_source_to_destination,
                 'fx_valuation_method': fx_method,
                 'margin': margin,
                 'tariff': tariff, 'drawback': drawback,
                 'effective_tariff': effective_tariff,
                 'denominator': denom, 'break_even_ask': break_even_ask,
                 'uncapped_ask': uncapped_ask,
                 'destination_price_cap_binding': cap_binding,
                 'destination_price_cap_below_break_even': cap_below_break_even,
                 'destination_price_cap': cap,
                 'destination_reference': dest_price,
                 'minimum_import_margin': region.IMPORT_MARGIN_MIN,
                 'currency': region.home_currency})
    return ask


def update_price_ref(region, good, demand_ratio, *, local_asks=None,
                     imported_asks=None, bids=None):
    """Bounded move-toward-target price reference WITH demand-gated supply scarcity."""
    from run_trace import emit
    ref = region._price_ref[good]
    old_ref = ref
    old_display_price = region.recipes.get(good, {}).get('price', ref)
    inflation = 0.25 * math.tanh(demand_ratio - 1.0)
    maxinv = region.recipes.get(good, {}).get('maxinv', 10)
    producers = [a for a in region.agents
                 if a.output == good and not getattr(a, 'is_trader', False)]
    if producers:
        avg_inv = sum(a.inv_get(good, 0) for a in producers) / len(producers)
    else:
        avg_inv = 0.0
    raw_scarcity = max(-0.6, min(1.0, 1.0 - avg_inv / max(0.1, maxinv * 0.5)))
    if raw_scarcity > 0.0:
        scarcity = raw_scarcity * max(0.0, min(1.0, (demand_ratio - 1.0) / 0.50))
    else:
        scarcity = raw_scarcity * max(0.0, min(1.0, 1.15 - demand_ratio))

    influence = inflation + 0.30 * scarcity
    influence = max(-0.35, min(0.50, influence))
    target = ref * (1.0 + influence)
    blended = ref + (target - ref) * 0.25
    ref = blended
    recent = region._trade_prices.get(good, [])[-12:]
    recent_event_ids = getattr(region, '_trade_price_event_ids', {}).get(good, [])[-12:]
    sample_mean = None
    if recent:
        sample_mean = sum(recent) / len(recent)
        ref = 0.7 * ref + 0.3 * sample_mean
    after_vwap = ref
    r = region.recipes.get(good, {})
    cost_floor = 1.0
    input_good = r.get('input') if r.get('numInput', 0) > 0 else None
    input_price = (region.recipes[input_good]['price'] if input_good is not None
                   and r.get('production', 0) > 0 else None)
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        cost_floor = max(0.1, (r['numInput'] * input_price)
                         / r['production'])
    ref = max(cost_floor, ref)
    ref = max(0.1, min(50.0, ref))
    region._price_ref[good] = ref
    if good in region.recipes:
        region.recipes[good]['price'] = ref
    emit(region, kind='market_price_update', record_class='calculation',
         subject={'type': 'tile', 'id': region.name, 'good': good.name},
         metric_id='goods.price', unit='local_currency_per_unit',
         before=old_display_price, after=ref, formula_id='market.reference.v1',
         cause_event_ids=recent_event_ids,
         inputs={'demand_ratio': demand_ratio, 'local_asks': local_asks,
                 'imported_asks': imported_asks, 'bids': bids,
                 'prior_reference': old_ref,
                 'producer_count': len(producers), 'average_producer_inventory': avg_inv,
                 'max_inventory': maxinv, 'scarcity': scarcity,
                 'inflation_term': inflation, 'bounded_influence': influence,
                 'target': target, 'move_blend': blended,
                 'recent_market_price_samples': list(recent),
                 'recent_sample_mean': sample_mean, 'vwap': sample_mean,
                 'after_sample_blend': after_vwap, 'after_vwap': after_vwap,
                 'input_good': input_good.name if input_good is not None else None,
                 'input_price': input_price,
                 'input_quantity': r.get('numInput', 0),
                 'production_quantity': r.get('production', 0),
                 'input_cost_floor': cost_floor,
                 'prior_display_price': old_display_price,
                 'new_internal_reference': ref,
                 'price_basis': 'displayed_recipe_reference',
                 'currency': getattr(region, 'home_currency', None)},
         constraints={'active_floor': cost_floor if after_vwap < cost_floor else None,
                      'active_cap': 50.0 if max(cost_floor, after_vwap) > 50.0 else None})


def gather_import_pool(region, good):
    """Return (pool, total) of pending import asks for *good*."""
    pend = getattr(region, 'pending_imports', None) or {}
    entries = pend.get(good)
    if not entries:
        return [], 0
    pool = []
    total = 0
    for e in entries:
        trader, qty = e[0], e[1]
        is_parked = e[2] if len(e) > 2 else False
        if qty > 0 and getattr(trader, 'is_trader', False):
            pool.append(list(e))
            total += qty
    return pool, total


def clear_discriminatory(region, good, ref, total_asks, total_bids,
                         imp_pool, agents, t, local_orders=None):
    """Clear one good, using the exact submitted local quantities when given."""
    from run_trace import emit
    book = []
    if local_orders is not None:
        for row in local_orders.get('sellers', ()):
            seller, qty = row['agent'], int(row['quantity'])
            if qty > 0 and getattr(seller, 'alive', True):
                book.append([float(row['limit_price']), qty, seller, False])
    else:
        for a in agents:
            if getattr(a, 'is_trader', False) or not getattr(a, 'alive', True):
                continue
            if a.output == good:
                qty = a.inventory[good.value]
                if good == Goods.food:
                    qty = max(0, qty - 2)
            else:
                qty = excess_non_producer_saleable(region, a, good)
            if qty > 0:
                book.append([calculate_ask_price(region, a, good, ref), qty, a, False])
    for item in imp_pool:
        trader, qty = item[0], item[1]
        ask = import_ask_price(
            region, trader, good,
            shipment_id=item[3] if len(item) > 3 else None,
            source_unit_cost=item[4] if len(item) > 4 else None,
            freight_per_unit=item[5] if len(item) > 5 else 0.0,
            source_currency=item[6] if len(item) > 6 else None,
            source_cost_status=item[7] if len(item) > 7 else None,
            source_region_name=item[9] if len(item) > 9 else None)
        is_parked = item[2] if len(item) > 2 else False
        book.append([ask, qty, trader, True, is_parked,
                     *(item[3:] if len(item) > 3 else [])])
    book.sort(key=lambda o: o[0])

    bid_limits = {}
    if local_orders is not None:
        bid_rows = [row for row in local_orders.get('buyers', ())
                    if int(row['quantity']) > 0 and getattr(row['agent'], 'alive', True)]
        bid_rows.sort(key=lambda row: (-float(row['limit_price']), row['agent'].id))
        buyers = [row['agent'] for row in bid_rows]
        rem_bids = {row['agent'].id: int(row['quantity']) for row in bid_rows}
        bid_limits = {row['agent'].id: float(row['limit_price']) for row in bid_rows}
    else:
        if not hasattr(region, '_cached_hungry_sorted') or region._cached_hungry_turn != t:
            region._cached_hungry_sorted = sorted(
                agents, key=lambda a: a.hungry_steps, reverse=True)
            region._cached_hungry_turn = t
        buyers = [a for a in region._cached_hungry_sorted
                  if not getattr(a, 'military_unit_id', None)]
        if good != Goods.food:
            buyers.sort(key=lambda a: (
                0 if input_good(region, a) == good else (1 if getattr(a, 'is_trader', False) else 2),
                -getattr(a, 'hungry_steps', 0)
            ))
        bid_attr = f'bid_{good.name}'
        has_explicit_bids = any(hasattr(a, bid_attr) for a in buyers)
        rem_bids = {
            a.id: int(getattr(a, bid_attr, 0)) if has_explicit_bids else total_bids
            for a in buyers
        }
        if has_explicit_bids:
            buyers = [a for a in buyers if rem_bids.get(a.id, 0) > 0]

    cash_collected = 0.0
    units = 0
    prices = []
    sale_event_ids = []
    imp_units = 0
    imp_value = 0.0
    bi = 0
    for b in book:
        ask, qty, seller, is_import = b[0], b[1], b[2], b[3]
        is_parked = b[4] if len(b) > 4 else False
        shipment_id = b[5] if len(b) > 5 else None
        source_unit_cost = b[6] if len(b) > 6 else None
        freight_per_unit = b[7] if len(b) > 7 else None
        source_currency = b[8] if len(b) > 8 else None
        source_cost_status = b[9] if len(b) > 9 else None
        source_shipment_id = b[10] if len(b) > 10 else shipment_id
        source_region = b[11] if len(b) > 11 else None
        route_history = list(b[12] if len(b) > 12 and b[12] else [])
        source_acquisitions = list(b[13] if len(b) > 13 and b[13] else [])
        if qty <= 0 or units >= total_bids:
            continue
        remaining = qty
        while remaining > 0 and units < total_bids and bi < len(buyers):
            buyer = buyers[bi]
            want = rem_bids.get(buyer.id, 0)
            if want <= 0 or buyer is seller:
                bi += 1
                continue
            bid_limit = bid_limits.get(buyer.id, float('inf'))
            if bid_limit + 1e-9 < ask:
                bi = len(buyers)
                break
            unit_price = (ask + bid_limit) / 2.0 if math.isfinite(bid_limit) else ask
            afford = int(buyer.cash / unit_price) if unit_price > 0 else want
            take = min(remaining, want, max(0, afford), total_bids - units)
            if take <= 0:
                bi += 1
                continue
            cost = take * unit_price
            buyer_cash_before = buyer.cash
            seller_cash_before = seller.cash
            seller_wallet_before = _fx.fx_balance(seller, region.home_currency)
            gov_cash_before = region.gov.agent.cash if getattr(region, 'gov', None) is not None else None
            import_tariff_assessed = 0.0
            import_tariff_rebate = 0.0
            import_tariff_paid = 0.0
            buyer.cash -= cost
            sold_source_acquisitions = []
            if is_import:
                if not getattr(seller, 'alive', True):
                    if getattr(region, 'gov', None) is not None:
                        region.gov.agent.cash += cost
                        region.gov.record_income(t, 'import_escheat', cost)
                    if is_parked:
                        seller.parked_sub(region.name, good, take)
                    else:
                        seller.inventory_foreign[good.value] -= take
                elif getattr(seller, 'home_currency', None) == region.home_currency:
                    seller.cash += cost
                    if is_parked:
                        seller.parked_sub(region.name, good, take)
                    else:
                        seller.inventory_foreign[good.value] -= take
                else:
                    from economy.trade_costs import import_tariff_terms
                    tau, drawback, _effective_tariff = import_tariff_terms(
                        region, getattr(seller, 'home_currency', None))
                    trader_share = cost * (1.0 - tau)
                    tariff_share = cost * tau
                    rebate = tariff_share * drawback
                    gov_share = tariff_share - rebate
                    import_tariff_assessed = tariff_share
                    import_tariff_rebate = rebate
                    import_tariff_paid = gov_share
                    _fx.fx_add(seller, region.home_currency, trader_share + rebate)
                    if gov_share > 0:
                        region.gov.receive_tariff(t, gov_share, region=region)
                    if is_parked:
                        seller.parked_sub(region.name, good, take)
                    else:
                        seller.inventory_foreign[good.value] -= take
                imp_units += take
                imp_value += cost
                if shipment_id is not None:
                    found_lot = False
                    for lot in getattr(seller, 'import_lots', []):
                        if lot.get('shipment_id') == shipment_id:
                            lot['quantity'] = max(0, int(lot.get('quantity', 0)) - take)
                            from economy.inventory_provenance import consume_acquisition_links
                            sold_source_acquisitions = consume_acquisition_links(
                                lot.get('source_acquisitions', []), take)
                            found_lot = True
                            break
                    if not found_lot:
                        from economy.inventory_provenance import consume_acquisition_links
                        sold_source_acquisitions = consume_acquisition_links(
                            source_acquisitions, take)
                else:
                    from economy.inventory_provenance import consume_acquisition_links
                    sold_source_acquisitions = consume_acquisition_links(
                        source_acquisitions, take)
            else:
                seller.cash += cost
                seller.inventory[good.value] -= take

            exported_acquisition_qty = 0
            if getattr(buyer, 'is_trader', False):
                if good == Goods.transport:
                    buyer.inv_add(good, take)
                elif good != Goods.food:
                    old_q = buyer.inv_get(good, 0)
                    old_c = buyer.cost_get(good, 0)
                    total_q = old_q + take
                    buyer.cost_set(good, ((old_q * old_c + take * unit_price)
                                          / total_q) if total_q > 0 else unit_price)
                    buyer.inventory_export[good.value] += take
                    exported_acquisition_qty = take
                else:
                    food_needed = max(0, 8 - buyer.inv_get(good, 0))
                    keep = min(food_needed, take)
                    buyer.inv_add(good, keep)
                    if take - keep > 0:
                        export = take - keep
                        old_q = buyer.inv_get(good, 0)
                        old_c = buyer.cost_get(good, 0)
                        total_q = old_q + export
                        buyer.cost_set(good, ((old_q * old_c + export * unit_price)
                                              / total_q) if total_q > 0 else unit_price)
                        buyer.inventory_export[good.value] += export
                        exported_acquisition_qty = export
            else:
                old_q = buyer.inv_get(good, 0)
                old_c = buyer.cost_get(good, 0)
                total_q = old_q + take
                buyer.cost_set(good, ((old_q * old_c + take * unit_price)
                                      / total_q) if total_q > 0 else unit_price)
                buyer.inv_add(good, take)
                if good == Goods.food:
                    buyer.food_purchased += int(take)
            seller_receipt_amount = (
                seller.cash - seller_cash_before
                + _fx.fx_balance(seller, region.home_currency) - seller_wallet_before)
            shipment_cost_detail = {}
            if is_import:
                cost_currency = source_currency or getattr(seller, 'home_currency', None)
                from economy.inventory_provenance import source_to_destination_rate
                fx_source_to_destination, fx_valuation_method = source_to_destination_rate(
                    region, source_region, cost_currency)
                if fx_source_to_destination is None:
                    # Match the explicit parity fallback used to make legacy lots quotable.
                    fx_source_to_destination = 1.0
                    fx_valuation_method = 'parity_assumed_no_bilateral_rate'
                source_cost_destination_currency = (
                    float(source_unit_cost) * fx_source_to_destination
                    if source_unit_cost is not None else None)
                freight_destination_currency = (
                    float(freight_per_unit) * fx_source_to_destination
                    if freight_per_unit is not None else None)
                landed_cost_source_currency = (
                    float(source_unit_cost) + float(freight_per_unit)
                    if source_unit_cost is not None and freight_per_unit is not None else None)
                landed_cost_destination_currency = (
                    landed_cost_source_currency * fx_source_to_destination
                    if landed_cost_source_currency is not None else None)
                fx_basis = {
                    'source_home_buy_rate_inverse': 'source_desk_current_buy_quote',
                    'destination_home_buy_rate': 'destination_desk_current_buy_quote',
                    'same_currency': 'same_currency_no_conversion',
                    'parity_assumed_no_bilateral_rate': 'explicit_parity_fallback',
                }.get(fx_valuation_method, 'bilateral_desk_quote')
                shipment_cost_detail = {
                    'destination_currency': region.home_currency,
                    'destination_paid_unit_price': float(unit_price),
                    'source_cost_currency': cost_currency,
                    'source_cost_destination_currency': source_cost_destination_currency,
                    'freight_destination_currency': freight_destination_currency,
                    'landed_cost_source_currency': landed_cost_source_currency,
                    'landed_cost_destination_currency': landed_cost_destination_currency,
                    'fx_source_to_destination_rate': fx_source_to_destination,
                    'fx_valuation_method': fx_valuation_method,
                    'fx_valuation_basis': fx_basis,
                    'import_tariff_assessed': import_tariff_assessed,
                    'import_tariff_rebate': import_tariff_rebate,
                    'import_tariff_paid': import_tariff_paid,
                    'import_tariff_assessed_per_unit': import_tariff_assessed / take,
                    'import_tariff_rebate_per_unit': import_tariff_rebate / take,
                    'import_tariff_paid_per_unit': import_tariff_paid / take,
                    'seller_net_receipt': seller_receipt_amount,
                    'seller_net_receipt_per_unit': seller_receipt_amount / take,
                    'trader_landed_margin_per_unit': (
                        seller_receipt_amount / take - landed_cost_destination_currency
                        if landed_cost_destination_currency is not None else None),
                }
            cash_collected += cost
            sale_id = emit(region, kind='paid_market_sale', record_class='transfer',
                           subject={'type': 'tile', 'id': region.name, 'good': good.name},
                           metric_id='goods.sold', unit='units', before=0, after=take,
                           inputs={'buyer_id': buyer.id, 'seller_id': seller.id,
                                   'imported': is_import, 'parked': is_parked,
                                   'shipment_id': shipment_id,
                                   'source_shipment_id': source_shipment_id,
                                   'source_region': source_region,
                                   'source_unit_cost': source_unit_cost,
                                   'freight_per_unit': freight_per_unit,
                                   'source_currency': source_currency,
                                   'source_cost_status': source_cost_status,
                                   'route_history': route_history,
                                   'source_acquisitions': sold_source_acquisitions,
                                   'unit_price': unit_price, 'total_paid': cost,
                                   **shipment_cost_detail,
                                   'buyer_cash_before': buyer_cash_before,
                                   'buyer_cash_after': buyer.cash,
                                   'seller_cash_delta': seller.cash - seller_cash_before,
                                   'seller_local_wallet_delta':
                                   _fx.fx_balance(seller, region.home_currency) - seller_wallet_before,
                                   'government_cash_delta':
                                   region.gov.agent.cash - gov_cash_before
                                   if gov_cash_before is not None else None})
            if sale_id is not None:
                sale_event_ids.append(sale_id)
            emit(region, kind='paid_market_unit_price', record_class='observation',
                 subject={'type': 'tile', 'id': region.name, 'good': good.name},
                 metric_id='goods.transaction_price', unit='local_currency_per_unit',
                 after=unit_price, cause_event_ids=[sale_id] if sale_id else [],
                 inputs={'quantity': take, 'total_paid': cost,
                         'buyer_id': buyer.id, 'seller_id': seller.id,
                         'imported': is_import, 'currency': region.home_currency})
            units += take
            prices.extend([unit_price] * int(take))
            trade_events = getattr(region, 'market_trade_events', [])
            trade_events.append({'turn': int(t), 'good': good.name, 'buyer_id': buyer.id,
                                 'seller_id': seller.id, 'quantity': int(take),
                                 'unit_price': float(unit_price), 'total_paid': float(cost),
                                 'imported': bool(is_import),
                                 'shipment_id': shipment_id,
                                 'source_shipment_id': source_shipment_id,
                                 'source_region': source_region,
                                 'source_unit_cost': source_unit_cost,
                                 'freight_per_unit': freight_per_unit,
                                 'source_currency': source_currency,
                                 'source_cost_status': source_cost_status,
                                 **shipment_cost_detail,
                                 'route_history': route_history,
                                 'source_acquisitions': sold_source_acquisitions})
            region.market_trade_events = trade_events[-500:]
            from economy.actor_accounts import record as record_economic_event
            economic_event = record_economic_event(
                region, 'spot_sale', turn=t, payer_id=buyer.id,
                recipient_id=seller.id, good=good, quantity=take,
                amount=cost, source_id=sale_id,
                detail={'unit_price': unit_price, 'imported': bool(is_import),
                        'parked': bool(is_parked), 'shipment_id': shipment_id,
                        'source_unit_cost': source_unit_cost,
                        'freight_per_unit': freight_per_unit,
                        'source_currency': source_currency,
                        'source_cost_status': source_cost_status,
                        **shipment_cost_detail,
                        'source_shipment_id': source_shipment_id,
                        'source_region': source_region,
                        'route_history': route_history,
                        'source_acquisitions': sold_source_acquisitions,
                        'seller_receipt': seller_receipt_amount,
                        'government_receipt':
                            (region.gov.agent.cash - gov_cash_before)
                            if gov_cash_before is not None else 0.0})
            if exported_acquisition_qty > 0:
                from economy.inventory_provenance import record_trader_acquisition
                record_trader_acquisition(
                    buyer, good, exported_acquisition_qty, unit_price, economic_event,
                    source_region=region.name, source_seller_id=seller.id,
                    source_currency=region.home_currency,
                    purchase_trace_event_id=sale_id,
                    parent_shipment_id=shipment_id,
                    parent_source_shipment_id=source_shipment_id)
            remaining -= take
            rem_bids[buyer.id] = want - take
            if buyer.cash < unit_price or rem_bids[buyer.id] <= 0:
                bi += 1
    region._auction_import_sales[good] = (imp_units, imp_value)
    realized = sum(prices) / len(prices) if prices else ref
    if units > 0:
        emit(region, kind='market_transaction_vwap', record_class='calculation',
             subject={'type': 'tile', 'id': region.name, 'good': good.name},
             metric_id='goods.transaction_vwap', unit='local_currency_per_unit',
             after=cash_collected / units,
             formula_id='market.transaction_vwap.v1',
             cause_event_ids=sale_event_ids,
             inputs={'total_paid': cash_collected, 'quantity': units,
                     'currency': region.home_currency})
    summary_id = emit(region, kind='market_clearing_summary', record_class='calculation',
                      subject={'type': 'tile', 'id': region.name, 'good': good.name},
                      metric_id='goods.sold', unit='units', after=units,
                      formula_id='market.discriminatory_clear.v1',
                      inputs={'offered_asks': total_asks, 'submitted_bids': total_bids,
                              'cash_collected': cash_collected, 'import_units': imp_units,
                              'import_value': imp_value, 'realized_or_reference_price': realized,
                              'no_paid_sale': not bool(prices)},
                      cause_event_ids=sale_event_ids)
    if summary_id is not None:
        recent_ids = region.__dict__.setdefault('_trade_price_event_ids', {}).setdefault(good, [])
        recent_ids.append(summary_id)
        del recent_ids[:-12]
    return units, cash_collected, realized


def sell_imports(region, pool, good, price, remaining_qty):
    """Sell remaining auction demand to import owners."""
    sold = 0
    value = 0.0
    for item in pool:
        if remaining_qty <= 0:
            break
        trader, qty = item[0], item[1]
        is_parked = item[2] if len(item) > 2 else False
        take = min(qty, remaining_qty)
        if take <= 0:
            continue
        if is_parked:
            trader.parked_sub(region.name, good, take)
        else:
            trader.inventory_foreign[good.value] -= take
        home = take * price
        _fx.fx_add(trader, region.home_currency, home)
        item[1] -= take
        remaining_qty -= take
        sold += take
        value += home
    return sold, value


def legacy_buy(region, t, good, price, total_asks):
    """Legacy buy matching logic (used for transport)."""
    if not hasattr(region, '_cached_hungry_sorted') or region._cached_hungry_turn != t:
        region._cached_hungry_sorted = sorted(region.agents, key=lambda a: a.hungry_steps, reverse=True)
        region._cached_hungry_turn = t
    bidders = region._cached_hungry_sorted
    total_bought = 0
    total_cash_purchases = 0.0
    for a in bidders:
        if total_asks > total_bought:
            agent_bid = getattr(a, f'bid_{good.name}', a.bid)
            bought = max(0, min(agent_bid, min(total_asks - total_bought, int(a.cash / price))))
            cash = bought * price
            if bought > 0:
                a.cash = max(0.0, a.cash - cash)
            total_cash_purchases += cash
            if bought > 0:
                if a.is_trader:
                    if good == Goods.transport:
                        a.inv_add(good, bought)
                    elif good != Goods.food:
                        old_q = a.inv_get(good, 0)
                        old_c = a.cost_get(good, 0)
                        total_q = old_q + bought
                        a.cost_set(good, ((old_q * old_c + bought * price)
                                          / total_q) if total_q > 0 else price)
                        a.inventory_export[good.value] += bought
                    else:
                        food_needed = max(0, 8 - a.inv_get(good, 0))
                        keep = min(food_needed, bought)
                        export = bought - keep
                        a.inv_add(good, keep)
                        if export > 0:
                            old_q = a.inv_get(good, 0)
                            old_c = a.cost_get(good, 0)
                            total_q = old_q + export
                            a.cost_set(good, ((old_q * old_c + export * price)
                                              / total_q) if total_q > 0 else price)
                            a.inventory_export[good.value] += export
                else:
                    old_quantity = a.inv_get(good, 0)
                    old_cost = a.cost_get(good, 0)
                    a.cost_set(good, ((old_quantity * old_cost + bought * price) / (old_quantity + bought)) if (old_quantity + bought) > 0 else price)
                    a.inv_add(good, bought)
                    if good == Goods.food:
                        a.food_purchased += int(bought)
                total_bought += bought
                region.bought_log[a.output][good][-1] += bought
    return total_bought, total_cash_purchases


def legacy_sell(region, askers, good, price, t, total_bought, total_cash_purchases):
    """Legacy sell matching logic (used for transport)."""
    total_sold = 0
    total_cash_sales = 0.0
    for a in askers:
        if total_sold < total_bought and total_cash_purchases > total_cash_sales:
            agent_ask = getattr(a, f'ask_{good.name}', a.ask)
            sold = min(agent_ask, total_bought - total_sold)
            total_sold += sold
            a.cash += sold * price
            a.inv_add(good, -sold)
            total_cash_sales += sold * price
    return total_cash_sales, total_sold


def price_decay(region, good):
    from run_trace import emit
    r = region.recipes[good]
    before = r['price']
    cost_to_make = 1.0
    input_good = r.get('input') if r.get('numInput', 0) > 0 else None
    input_price = (region.recipes[input_good]['price'] if input_good is not None
                   and r.get('production', 0) > 0 else None)
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        cost_to_make = (r['numInput'] * input_price) / r['production']
    if r['price'] > cost_to_make * 1.05:
        r['price'] = max(cost_to_make, r['price'] * 0.95)
    r['price'] = max(cost_to_make, r['price'])
    emit(region, kind='market_price_decay', record_class='calculation',
         subject={'type': 'tile', 'id': region.name, 'good': good.name},
         metric_id='goods.price', unit='local_currency_per_unit',
         before=before, after=r['price'], formula_id='market.decay.v1',
         inputs={'prior_display_price': before,
                 'prior_internal_reference': region._price_ref.get(good),
                 'new_internal_reference': region._price_ref.get(good),
                 'trigger': 'no_bids_and_no_asks', 'threshold_multiplier': 1.05,
                 'decay_factor': 0.95, 'input_cost_floor': cost_to_make,
                 'input_good': input_good.name if input_good is not None else None,
                 'input_price': input_price,
                 'input_quantity': r.get('numInput', 0),
                 'production_quantity': r.get('production', 0),
                 'price_basis': 'displayed_recipe_reference',
                 'currency': getattr(region, 'home_currency', None)},
         constraints={'active_floor': cost_to_make if r['price'] == cost_to_make else None})


def set_price(region, demand_ratio, good):
    from run_trace import emit
    r = region.recipes[good]
    price = r['price']
    before = price
    fundamental_cost = 1.0
    input_good = r.get('input') if r.get('numInput', 0) > 0 else None
    input_price = (region.recipes[input_good]['price'] if input_good is not None
                   and r.get('production', 0) > 0 else None)
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        fundamental_cost = (r['numInput'] * input_price) / r['production']
    food_price = region.food_price
    living_cost_floor = (4 * food_price) / max(1, r.get('production', 1))

    def lerp(a, b, t):
        return a + (b - a) * t

    if demand_ratio >= 1:
        clamped_ratio = min(5.0, demand_ratio - 1)
        price *= lerp(1.01, 1.20, clamped_ratio / 5.0)
    elif demand_ratio < 0.2:
        price *= lerp(0.90, 0.95, demand_ratio / 0.2)
    elif demand_ratio < 0.5:
        price *= lerp(0.95, 1.0, (demand_ratio - 0.2) / 0.3)
    min_price_floor = fundamental_cost * 1.10 if r.get('numInput', 0) > 0 else max(living_cost_floor, 0.10)
    price = max(min_price_floor, price, 0.1)
    r['price'] = price
    emit(region, kind='transport_price_update', record_class='calculation',
         subject={'type': 'tile', 'id': region.name, 'good': good.name},
         metric_id='goods.price', unit='local_currency_per_unit',
         before=before, after=price, formula_id='market.transport.v1',
         inputs={'prior_display_price': before, 'demand_ratio': demand_ratio,
                 'fundamental_cost': fundamental_cost, 'food_price': food_price,
                 'living_cost_floor': living_cost_floor,
                 'input_good': input_good.name if input_good is not None else None,
                 'input_price': input_price,
                 'input_quantity': r.get('numInput', 0),
                 'production_quantity': r.get('production', 1),
                 'currency': region.home_currency},
         constraints={'min_price_floor': min_price_floor})
    return price


def trade(region, t):
    """Run market trading session for goods and transport services."""
    from run_trace import emit
    all_goods_price = region.all_goods_price
    food_price = region.food_price
    if getattr(region, 'province', None) is None:
        region.bank.PayDepositInterest(region.agents, trace_region=region)

    dest = region.destination_region
    if dest is not None and dest.gov is not None:
        region._trade_fee_mult = dest.gov.get_trade_fee_multiplier()
    else:
        region._trade_fee_mult = 0.95

    decide_borrow_deposit(region, region.agents, all_goods_price, food_price, t)

    # ---- Phase A: trade food, wood, furniture, and active local goods ----
    recipes = region.recipes
    agents = region.agents
    goods_goods = [Goods.food, Goods.wood, Goods.furniture]
    for g in getattr(region, 'goods', []):
        if (g in goods_goods or g in (Goods.gov, Goods.none, Goods.transport)
                or g not in recipes or recipes[g].get('import_only', False)):
            continue
        has_market_activity = any(
            getattr(a, 'alive', True) and (
                a.output == g
                or a.inv_get(g, 0) > 0
                or input_good(region, a) == g
            )
            for a in agents
        ) or bool((getattr(region, 'pending_imports', None) or {}).get(g))
        if has_market_activity:
            goods_goods.append(g)
            region._price_ref.setdefault(g, max(0.1, recipes[g].get('price', 1.0)))
            region.demand_ratio_log.setdefault(g, [])
            region.demand_log.setdefault(g, [])
            region.supply_log.setdefault(g, [])
            region.sold_log.setdefault(g, [])

    desired_food = 16
    desired_wood = 10
    desired_furn = max(1, int(16 / max(1, recipes[Goods.furniture]['price'])))
    desires = {Goods.food: desired_food, Goods.wood: desired_wood,
               Goods.furniture: desired_furn}
    for g in goods_goods:
        if g not in desires:
            desires[g] = max(1, int(12 / max(1.0, recipes[g]['price'])))
    prices = {g: recipes[g]['price'] for g in goods_goods}
    total_asks = {g: 0 for g in goods_goods}
    total_bids = {g: 0 for g in goods_goods}
    local_orders = {g: {'buyers': [], 'sellers': []} for g in goods_goods}
    for a in agents:
        if not getattr(a, 'alive', True):
            for g in goods_goods:
                setattr(a, f'bid_{g.name}', 0)
                setattr(a, f'ask_{g.name}', 0)
            continue
        if getattr(a, 'military_unit_id', None):
            for g in goods_goods:
                setattr(a, f'bid_{g.name}', 0)
                setattr(a, f'ask_{g.name}', 0)
            continue
        ar = recipes.get(a.output, {})
        is_emp = a.employer is not None
        mult = a.consumption_multiplier
        for g in goods_goods:
            p = prices[g]
            d = desires[g]
            withdraw_if_needed(region, a, p, d)
            bid = calculate_bid(region, a, g, p, d, ar, is_emp, mult)
            a.bid = bid
            a.remainingCash -= bid * p
            total_bids[g] += bid
            if bid > 0:
                local_orders[g]['buyers'].append({'agent': a, 'quantity': int(bid)})
            ask = calculate_ask(region, a, g, p, is_emp)
            a.ask = ask
            # Trader export inventory is committed to the route pipeline; it
            # is not a local seller offer. Foreign stock enters through the
            # separately priced import pool below.
            local_ask = 0 if getattr(a, 'is_trader', False) else ask
            total_asks[g] += local_ask
            if local_ask > 0:
                local_orders[g]['sellers'].append({
                    'agent': a, 'quantity': int(local_ask),
                    'limit_price': calculate_ask_price(region, a, g, p)
                    if a.output == g else max(0.05, p),
                })
            setattr(a, f'bid_{g.name}', bid)
            setattr(a, f'ask_{g.name}', ask)

    # Active state concessions alter which funded bids may legally execute.
    # Show the remaining eligible demand in the market totals and later fills.
    from market_concessions import filter_chartered_bids
    for good in goods_goods:
        submitted = local_orders[good]['buyers']
        filtered = filter_chartered_bids(region, good, submitted, t)
        permitted_by_id = {row['agent'].id: int(row['quantity']) for row in filtered}
        quote = max(0.0, float(prices.get(good, 0.0)))
        for row in submitted:
            buyer = row['agent']
            permitted = permitted_by_id.get(buyer.id, 0)
            if permitted < int(row['quantity']):
                buyer.remainingCash += (int(row['quantity']) - permitted) * quote
                setattr(buyer, f'bid_{good.name}', permitted)
        local_orders[good]['buyers'] = filtered
        total_bids[good] = sum(int(row['quantity']) for row in filtered)

    max_demand_ratio = 0
    most_demand_good = Goods.food
    for good in goods_goods:
        ta = total_asks[good]
        tb = total_bids[good]
        imp_pool, imp_total = gather_import_pool(region, good)
        emergency_surplus = (sum(emergency_food_surplus(a) for a in agents)
                             if good == Goods.food and getattr(region.gov, 'emergency_food_policy', False)
                             else 0)
        if ta == 0 and imp_total == 0 and tb == 0 and emergency_surplus == 0:
            price_decay(region, good)
            continue
        price_ta = ta + imp_total
        demand_ratio = 5.0 if price_ta == 0 else tb / price_ta
        region.demand_ratio_log[good].append(demand_ratio)
        region.demand_log[good].append(tb)
        region.supply_log[good].append(price_ta)
        from run_trace import emit
        market_subject = {'type': 'tile', 'id': region.name, 'good': good.name}
        emit(region, kind='market_demand_total', record_class='calculation',
             subject=market_subject, metric_id='goods.demand', unit='units_offered',
             after=tb, formula_id='market.sum_bids.v1',
             inputs={'active_agents': len(agents)})
        emit(region, kind='market_supply_total', record_class='calculation',
             subject=market_subject, metric_id='goods.supply', unit='units_offered',
             after=price_ta, formula_id='market.local_plus_imports.v1',
             inputs={'local_asks': ta, 'imported_asks': imp_total})
        if max_demand_ratio < demand_ratio and tb > 0:
            max_demand_ratio = demand_ratio
            most_demand_good = good
        # Orders are priced against the quote visible when submitted. Discover
        # and publish the next reference after clearing so the terms cannot
        # change between order submission and settlement.
        ref = prices[good]
        for row in local_orders[good]['buyers']:
            buyer = row['agent']
            qty = row['quantity']
            row['limit_price'] = calculate_bid_limit(
                region, buyer, good, ref, demand_ratio, qty)
            pressure = max(0.0, min(2.0, float(demand_ratio) - 1.0))
            premium = min(0.50, pressure * 0.20)
            need_premium = (min(0.75, max(0.0, getattr(buyer, 'hungry_steps', 0) * 0.05))
                            if good == Goods.food and not getattr(buyer, 'is_corporation', False)
                            else 0.0)
            input_value_ceiling = None
            if input_good(region, buyer) == good:
                recipe = region.recipes.get(buyer.output, {})
                input_units = max(0.0, float(recipe.get('numInput', 0)))
                output_units = max(0.0, float(recipe.get('production', 0)))
                if input_units > 0 and output_units > 0:
                    output_value = output_units * float(
                        region.recipes.get(buyer.output, {}).get('price', 0.0))
                    payroll = max(0.0, float(getattr(buyer, 'wage', 0.0))
                                 * len(getattr(buyer, 'employees', ())))
                    input_value_ceiling = max(0.0, (output_value - payroll) / input_units)
            trader_net_value = None
            trader_tariff_terms = None
            if getattr(buyer, 'is_trader', False):
                dest = getattr(buyer, 'destination_region', None) or region.destination_region
                if dest is not None:
                    desk = region.forex_desks.get(dest.name) or getattr(region, 'forex', None)
                    fx_rate = desk.buy_rate() if desk is not None else region.exchange_rate
                    fee = (dest.gov.get_trade_fee_multiplier(include_import_tariff=False)
                           if dest.gov is not None else region._trade_fee_mult)
                    from economy.trade_costs import import_tariff_terms
                    tariff_terms = import_tariff_terms(
                        dest, getattr(buyer, 'home_currency', region.home_currency))
                    tariff, drawback, effective_tariff = tariff_terms
                    trader_net_value = (dest.recipes.get(good, {}).get('price', 0.0)
                                        * fee * fx_rate * (1.0 - effective_tariff)
                                        - transport_cost_per_unit(region))
                    trader_tariff_terms = {'statutory': tariff,
                                           'drawback': drawback,
                                           'effective': effective_tariff}
            from run_trace import emit
            emit(region, kind='local_buyer_bid', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name, 'good': good.name,
                          'buyer_id': buyer.id},
                 metric_id='goods.buyer_bid', unit='local_currency_per_unit',
                 after=row['limit_price'], formula_id='market.local_bid.v1',
                 inputs={'reference': ref, 'demand_ratio': demand_ratio,
                         'demand_premium': premium, 'need_premium': need_premium,
                         'input_value_ceiling': input_value_ceiling,
                         'quantity': qty,
                         'cash_limit': buyer.cash / qty if qty else 0.0,
                         'trader_net_value': trader_net_value,
                         'trader_tariff_terms': trader_tariff_terms,
                         'currency': region.home_currency})
        price = ref
        if min(price_ta, tb) == 0:
            region._auction_import_sales[good] = (0, 0.0)
            from run_trace import emit
            emit(region, kind='market_no_trade', record_class='observation',
                 subject={'type': 'tile', 'id': region.name, 'good': good.name},
                 metric_id='goods.sold', unit='units', after=0,
                 inputs={'local_asks': ta, 'imported_asks': imp_total,
                         'bids': tb, 'reason': 'no bids or no offers'})
            if good != Goods.food or (ta == 0 and emergency_surplus == 0):
                update_price_ref(region, good, demand_ratio, local_asks=ta,
                                 imported_asks=imp_total, bids=tb)
                continue
            # A cash-poor population can make zero private bids. Public food
            # procurement must still be able to buy locally offered grain.
            total_bought, realized = 0, ref
        else:
            total_bought, _tcash, realized = clear_discriminatory(
                region, good, ref, price_ta, tb, imp_pool, agents, t,
                local_orders=local_orders[good])
        update_price_ref(region, good, demand_ratio, local_asks=ta,
                         imported_asks=imp_total, bids=tb)
        price = region._price_ref[good]
        region.sold_log[good].append(total_bought)
        region._trade_prices[good].append(realized)
        total_sold = total_bought
        charity_bought = 0
        gov_bought = 0
        askers = sorted(agents, key=lambda a: a.ask, reverse=True)

        # Charity food purchase
        if good == Goods.food:
            charity_bid = region.charity.bid_food(price, desires[good], region.bank)
            if charity_bid > 0:
                food_askers = [a for a in askers if a.output == Goods.food
                               and a.inv_get(Goods.food, 0) > food_reserve_units(a)]
                for seller in food_askers:
                    if charity_bid <= 0 or region.charity.cash < price:
                        break
                    available = seller.inv_get(Goods.food, 0) - food_reserve_units(seller)
                    if available <= 0:
                        continue
                    bought = min(charity_bid, available, int(region.charity.cash / price))
                    if bought > 0:
                        seller.inv_add(Goods.food, -bought)
                        seller.cash += bought * price
                        region.charity.pay_for_food(bought * price)
                        region.charity.receive_food(bought)
                        emit(region, kind='charity_food_purchase', record_class='transfer',
                             subject={'type': 'tile', 'id': region.name, 'good': good.name},
                             metric_id='goods.sold', unit='units', before=0, after=bought,
                             inputs={'seller_id': seller.id, 'buyer': 'charity',
                                     'unit_price': price, 'paid': bought * price})
                        from economy.actor_accounts import record as record_economic_event
                        record_economic_event(
                            region, 'spot_sale', turn=t, recipient_id=seller.id,
                            good=good, quantity=bought, amount=bought * price,
                            detail={'unit_price': price, 'public_buyer': 'charity',
                                    'seller_receipt': bought * price})
                        charity_bid -= bought
                        charity_bought += bought
                if charity_bought > 0:
                    total_sold += charity_bought
                    region.sold_log[good][-1] += charity_bought
                    loginfo(t, f"{region.charity.name} bought {charity_bought} food at ${price:.2f}")
            region.charity.deposit_remaining(region.bank)

            # Government food purchase
            if hasattr(region, 'gov'):
                if region.gov.emergency_food_policy:
                    from nutrition import appetite_units
                    region.gov.emergency_meal_target = sum(
                        max(0, appetite_units(a) - a.inv_get(Goods.food, 0))
                        for a in agents if a.alive and not a.is_corporation
                        and not a.is_government and not getattr(a, 'military_unit_id', None))
                gov_bid = region.gov.bid_food(price, desires[good], region.bank)
                if gov_bid > 0:
                    if region.gov.emergency_food_policy:
                        gov_askers = sorted(
                            (a for a in agents if emergency_food_surplus(a) > 0),
                            key=lambda a: (-emergency_food_surplus(a), a.id))
                    else:
                        gov_askers = [a for a in askers if a.output == Goods.food
                                       and a.inv_get(Goods.food, 0) > food_reserve_units(a)]
                    for seller in gov_askers:
                        if gov_bid <= 0 or region.gov.agent.cash < price:
                            break
                        available = (emergency_food_surplus(seller)
                                     if region.gov.emergency_food_policy else
                                     seller.inv_get(Goods.food, 0) - food_reserve_units(seller))
                        if available <= 0:
                            continue
                        bought = min(gov_bid, available,
                                     int(region.gov.agent.cash / price))
                        if bought > 0:
                            seller.inv_add(Goods.food, -bought)
                            seller.cash += bought * price
                            region.gov.pay_for_food(bought * price)
                            region.gov.receive_food(bought)
                            emit(region, kind='government_food_purchase', record_class='transfer',
                                 subject={'type': 'tile', 'id': region.name, 'good': good.name},
                                 metric_id='goods.sold', unit='units', before=0, after=bought,
                                     inputs={'seller_id': seller.id, 'buyer': 'government',
                                             'unit_price': price, 'paid': bought * price,
                                             'emergency_surplus': region.gov.emergency_food_policy,
                                             'seller_occupation': seller.output.name})
                            from economy.actor_accounts import record as record_economic_event
                            record_economic_event(
                                region, 'spot_sale', turn=t,
                                payer_id=region.gov.agent.id, recipient_id=seller.id,
                                good=good, quantity=bought, amount=bought * price,
                                detail={'unit_price': price,
                                        'public_buyer': 'government',
                                        'emergency_surplus': region.gov.emergency_food_policy,
                                        'seller_receipt': bought * price})
                            gov_bid -= bought
                            gov_bought += bought
                    if gov_bought > 0:
                        total_sold += gov_bought
                        region.sold_log[good][-1] += gov_bought
                        owner = getattr(region, 'owner_nation', None)
                        if owner is not None:
                            emit(region, kind='government_food_spending',
                                 record_class='transfer',
                                 subject={'type': 'nation', 'id': owner.name},
                                 metric_id='finance.treasury_flow', unit=owner.currency,
                                 after=-(gov_bought * price),
                                 inputs={'tile': region.name, 'quantity': gov_bought,
                                         'unit_price': price})
                        loginfo(t, f"Government({region.gov.name}) bought "
                                f"{gov_bought} food at ${price:.2f}")
                region.gov.deposit_remaining(region.bank)
        emit(region, kind='market_total_units_sold', record_class='calculation',
             subject={'type': 'tile', 'id': region.name, 'good': good.name},
             metric_id='goods.sold', unit='units', after=region.sold_log[good][-1],
             formula_id='market.clear_plus_public_buyers.v1',
             inputs={'private_units': total_bought, 'charity_units': charity_bought,
                     'government_units': gov_bought})

    # ---- Phase B: trade transport ----
    transport_price = recipes[Goods.transport]['price']
    tr_asks = 0
    tr_bids = 0
    for a in agents:
        tr_bid = calculate_transport_bid(region, a, transport_price)
        a.bid_transport = tr_bid
        a.remainingCash -= tr_bid * transport_price
        tr_bids += tr_bid
        tr_ask = calculate_ask(region, a, Goods.transport, transport_price, a.employer is not None)
        a.ask_transport = tr_ask
        tr_asks += tr_ask
    if tr_asks == 0 and tr_bids == 0:
        price_decay(region, Goods.transport)
    else:
        dr = 5.0 if tr_asks == 0 else tr_bids / tr_asks
        region.demand_ratio_log[Goods.transport].append(dr)
        region.demand_log[Goods.transport].append(tr_bids)
        region.supply_log[Goods.transport].append(tr_asks)
        transport_subject = {'type': 'tile', 'id': region.name, 'good': Goods.transport.name}
        emit(region, kind='transport_demand_total', record_class='calculation',
             subject=transport_subject, metric_id='goods.demand',
             unit='units_offered', after=tr_bids, formula_id='market.sum_transport_bids.v1')
        emit(region, kind='transport_supply_total', record_class='calculation',
             subject=transport_subject, metric_id='goods.supply',
             unit='units_offered', after=tr_asks, formula_id='market.sum_transport_asks.v1')
        if max_demand_ratio < dr and tr_bids > 0:
            max_demand_ratio = dr
        price = set_price(region, dr, Goods.transport)
        if dr > 0 and tr_bids > 0 and tr_asks > 0:
            total_bought, tcash = legacy_buy(region, t, Goods.transport, price, tr_asks)
            askers = sorted(agents, key=lambda a: a.ask_transport, reverse=True)
            _, total_sold = legacy_sell(region, askers, Goods.transport, price, t,
                                        total_bought, tcash)
            region.sold_log[Goods.transport].append(total_sold)
        else:
            region.sold_log[Goods.transport].append(0)
        emit(region, kind='transport_units_sold', record_class='calculation',
             subject=transport_subject, metric_id='goods.sold', unit='units',
             after=region.sold_log[Goods.transport][-1],
             formula_id='market.legacy_transport_clear.v1',
             inputs={'bids': tr_bids, 'asks': tr_asks})

    region.most_demand = most_demand_good

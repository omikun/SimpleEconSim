"""
Market clearing, pay-as-bid double auction, pricing reference updates, and bid/ask mechanics.
"""

import math
from goods import Goods
from logger import loginfo
import econsim_trade_money as _tm
import forex as _fx
from region_logistics import all_routes, transport_cost_per_unit


def borrow_food(region, agent, food_price):
    if agent.output != Goods.food and agent.cash < food_price and agent.hungry_steps > 10:
        bank_balance = region.bank.deposits.get(agent, 0)
        if bank_balance > 0:
            region.bank.Withdraw(agent, min(bank_balance, food_price - agent.cash))
        if agent.cash < food_price:
            region.bank.Borrow(0, agent, food_price)


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
        region.bank.Borrow(0, agent, cost - agent.cash)


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
        _tm.borrow_if_needed(t, a, bank=region.bank)
        _tm.PayLoans(a, bank=region.bank)
        borrow_food(region, a, food_price)
        borrow_inputs(region, a)
        deposit_excess(region, a, all_goods_price)
        if a.is_trader:
            trader_reserve = region.cost_of_living * 5
            total_liquid = a.cash + region.bank.deposits.get(a, 0)
            if total_liquid < trader_reserve:
                region.bank.Borrow(t, a, trader_reserve - total_liquid)
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
                            region.bank.Borrow(t, a, target - total_liquid)
                        break
        a.remainingCash = a.cash


def withdraw_if_needed(region, agent, good_price, current_desired):
    bank_balance = region.bank.deposits.get(agent, 0)
    if bank_balance > 0 and agent.remainingCash < good_price * current_desired:
        region.bank.Withdraw(agent, min(bank_balance, good_price * current_desired - agent.remainingCash))


def input_good(region, agent):
    return region.recipes[agent.output].get('input', Goods.none)


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
        max_trader_inventory = agent_recipe['maxinv']
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
    if not is_employee and input_good(region, agent) == good:
        num_employees = len(agent.employees) if agent.is_corporation else 0
        desired = max(0, agent_recipe['numInput'] * (1 + num_employees) - agent.inv_get(good, 0))
        if mult > 1.0:
            desired = int(desired * mult)
        affordable = agent.remainingCash // good_price if good_price > 0 else desired
        return int(min(desired, affordable))
    elif (is_employee or agent.output != good) and agent.remainingCash > good_price:
        max_inventory_limit = agent_recipe['maxinv']
        if agent.is_corporation:
            max_inventory_limit *= (1 + len(agent.employees))
        if mult > 1.0:
            max_inventory_limit = int(max_inventory_limit * min(mult, 3.0))
        num_storable = max(0, max_inventory_limit - agent.inv_get(good, 0))
        base_desire = min(current_desired, agent.remainingCash // good_price)
        bid = min(int(base_desire * mult), num_storable)
        if mult > 2.0 and good != Goods.food:
            extra = min(int(current_desired * (mult - 1.0)), agent.remainingCash // good_price) if good_price > 0 else 0
            bid += min(extra, num_storable - bid)
        return max(0, min(bid, num_storable))
    return 0


def calculate_ask(region, agent, good, good_price, is_employee):
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
        return 0 if agent.inv_get(good, 0) <= 0 else 0
    if agent.output == good or (agent.output == Goods.gov and agent.inv_get(good, 0) > 0):
        cost_to_make = 0.0
        agent_recipe = region.recipes.get(good, {})
        if agent.output == good and agent_recipe.get('numInput', 0) > 0 and agent_recipe.get('production', 0) > 0:
            cost_to_make = (agent_recipe['numInput'] * agent.cost_get(agent_recipe['input'], 0)) / agent_recipe['production']
        if good == Goods.food and agent.output == Goods.food:
            return max(0, agent.inv_get(good, 0) - 2)
        elif good_price >= cost_to_make:
            return max(0, agent.inv_get(good, 0))
    return 0


def calculate_transport_bid(region, agent, transport_price):
    """Traders bid transport based on goods waiting in export inventory."""
    if not agent.is_trader:
        return 0
    capacity = region.recipes[Goods.transport]['capacity']
    total_export = sum(agent.inventory_export[g.value] for g in [Goods.food, Goods.wood, Goods.furniture])
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
    scarcity = 1.4 - 0.4 * max(0.0, min(1.0, ratio))
    hungry = getattr(agent, 'hungry_steps', 0)
    urgency = max(0.0, 1.0 - 0.12 * hungry)
    mult = scarcity * urgency
    mult = max(region.ASK_URGENCY_MIN, min(region.ASK_URGENCY_MAX, mult))
    return ref * mult


def import_ask_price(region, trader, good):
    """Import ask price calculation."""
    cost_home = max(0.05, trader.cost_get(good, 0))
    src_region = region.neighbors.get(getattr(trader, 'home_region', None)) \
        or getattr(region, 'destination_region', None)
    if cost_home <= 0.05 + 1e-9 and src_region is not None:
        cost_home = max(0.05, src_region.recipes.get(good, {}).get('price', 0.0))
    margin = region.IMPORT_MARGIN_MIN + (
        region.IMPORT_MARGIN_MAX - region.IMPORT_MARGIN_MIN) * (
            abs(hash((trader.id, good))) % 1000) / 1000.0
    tariff = getattr(region.gov, 'import_tariff_rate', 0.0)
    drawback = (getattr(region.gov, 'import_drawback_rate', 0.0)
                if getattr(region.gov, 'import_drawback_enabled', False)
                else 0.0)
    effective_tariff = tariff * (1.0 - drawback)
    dest_desk = None
    if src_region is not None:
        dest_desk = src_region.forex_desks.get(region.name) \
            or getattr(src_region, 'forex', None)
    buy_rate = dest_desk.buy_rate() if dest_desk is not None else 1.0
    denom = max(0.05, (1.0 - effective_tariff) * buy_rate)
    ask = cost_home * (1.0 + margin) / denom
    dest_price = region.recipes.get(good, {}).get('price', 0.0)
    if dest_price > 0:
        cap = dest_price * (1.0 + region.IMPORT_MARGIN_MIN)
        ask = min(ask, cap)
    return max(0.05, ask)


def update_price_ref(region, good, demand_ratio):
    """Bounded move-toward-target price reference WITH supply scarcity."""
    ref = region._price_ref[good]
    inflation = 0.25 * math.tanh(demand_ratio - 1.0)
    maxinv = region.recipes.get(good, {}).get('maxinv', 10)
    producers = [a for a in region.agents
                 if a.output == good and not getattr(a, 'is_trader', False)]
    if producers:
        avg_inv = sum(a.inv_get(good, 0) for a in producers) / len(producers)
    else:
        avg_inv = 0.0
    scarcity = max(0.0, min(1.0, 1.0 - avg_inv / max(0.1, maxinv * 0.6)))

    influence = inflation + 0.30 * scarcity
    influence = max(-0.35, min(0.50, influence))
    target = ref * (1.0 + influence)
    ref = ref + (target - ref) * 0.25
    recent = region._trade_prices.get(good, [])[-12:]
    if recent:
        vwap = sum(recent) / len(recent)
        ref = 0.7 * ref + 0.3 * vwap
    r = region.recipes.get(good, {})
    cost_floor = 1.0
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        cost_floor = max(0.1, (r['numInput'] * region.recipes[r['input']]['price'])
                         / r['production'])
    ref = max(cost_floor, ref)
    ref = max(0.1, min(50.0, ref))
    region._price_ref[good] = ref
    if good in region.recipes:
        region.recipes[good]['price'] = ref


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
            pool.append([trader, qty, is_parked])
            total += qty
    return pool, total


def clear_discriminatory(region, good, ref, total_asks, total_bids,
                         imp_pool, agents, t):
    """Cheapest-first pay-as-bid clear for one good."""
    book = []
    for a in agents:
        if a.output != good or getattr(a, 'is_trader', False) or not getattr(a, 'alive', True):
            continue
        qty = a.inventory[good.value]
        if good == Goods.food:
            qty = max(0, qty - 2)
        if qty > 0:
            book.append([calculate_ask_price(region, a, good, ref), qty, a, False])
    for item in imp_pool:
        trader, qty = item[0], item[1]
        ask = import_ask_price(region, trader, good)
        is_parked = item[2] if len(item) > 2 else False
        book.append([ask, qty, trader, True, is_parked])
    book.sort(key=lambda o: o[0])

    if not hasattr(region, '_cached_hungry_sorted') or region._cached_hungry_turn != t:
        region._cached_hungry_sorted = sorted(
            agents, key=lambda a: a.hungry_steps, reverse=True)
        region._cached_hungry_turn = t
    buyers = region._cached_hungry_sorted

    cash_collected = 0.0
    units = 0
    prices = []
    imp_units = 0
    imp_value = 0.0
    bi = 0
    for b in book:
        ask, qty, seller, is_import = b[0], b[1], b[2], b[3]
        is_parked = b[4] if len(b) > 4 else False
        if qty <= 0 or units >= total_bids:
            continue
        remaining = qty
        while remaining > 0 and units < total_bids and bi < len(buyers):
            buyer = buyers[bi]
            afford = int(buyer.cash / ask) if ask > 0 else 0
            take = min(remaining, max(0, afford))
            if take <= 0:
                bi += 1
                continue
            cost = take * ask
            buyer.cash -= cost
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
                    tau = getattr(region.gov, 'import_tariff_rate', 0.0) \
                        if getattr(region.gov, 'import_tariff_enabled', False) \
                        else 0.0
                    drawback = getattr(region.gov, 'import_drawback_rate', 0.0) \
                        if getattr(region.gov, 'import_drawback_enabled', False) \
                        else 0.0
                    trader_share = cost * (1.0 - tau)
                    tariff_share = cost * tau
                    rebate = tariff_share * drawback
                    gov_share = tariff_share - rebate
                    _fx.fx_add(seller, region.home_currency, trader_share + rebate)
                    if gov_share > 0:
                        region.gov.receive_tariff(t, gov_share)
                    if is_parked:
                        seller.parked_sub(region.name, good, take)
                    else:
                        seller.inventory_foreign[good.value] -= take
                imp_units += take
                imp_value += cost
            else:
                seller.cash += cost
                seller.inventory[good.value] -= take

            if getattr(buyer, 'is_trader', False):
                if good == Goods.transport:
                    buyer.inv_add(good, take)
                elif good != Goods.food:
                    old_q = buyer.inv_get(good, 0)
                    old_c = buyer.cost_get(good, 0)
                    total_q = old_q + take
                    buyer.cost_set(good, ((old_q * old_c + take * ask)
                                          / total_q) if total_q > 0 else ask)
                    buyer.inventory_export[good.value] += take
                else:
                    food_needed = max(0, 8 - buyer.inv_get(good, 0))
                    keep = min(food_needed, take)
                    buyer.inv_add(good, keep)
                    if take - keep > 0:
                        export = take - keep
                        old_q = buyer.inv_get(good, 0)
                        old_c = buyer.cost_get(good, 0)
                        total_q = old_q + export
                        buyer.cost_set(good, ((old_q * old_c + export * ask)
                                              / total_q) if total_q > 0 else ask)
                        buyer.inventory_export[good.value] += export
            else:
                buyer.inv_add(good, take)
            cash_collected += cost
            units += take
            prices.extend([ask] * int(take))
            remaining -= take
            if buyer.cash < ask:
                bi += 1
    region._auction_import_sales[good] = (imp_units, imp_value)
    realized = sum(prices) / len(prices) if prices else ref
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
    r = region.recipes[good]
    cost_to_make = 1.0
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        input_cost = region.recipes[r['input']]['price']
        cost_to_make = (r['numInput'] * input_cost) / r['production']
    if r['price'] > cost_to_make * 1.05:
        r['price'] = max(cost_to_make, r['price'] * 0.95)
    r['price'] = max(cost_to_make, r['price'])


def set_price(region, demand_ratio, good):
    r = region.recipes[good]
    price = r['price']
    fundamental_cost = 1.0
    if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
        input_cost = region.recipes[r['input']]['price']
        fundamental_cost = (r['numInput'] * input_cost) / r['production']
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
    return price


def trade(region, t):
    """Run market trading session for goods and transport services."""
    all_goods_price = region.all_goods_price
    food_price = region.food_price
    if getattr(region, 'province', None) is None:
        region.bank.PayDepositInterest(region.agents)

    dest = region.destination_region
    if dest is not None and dest.gov is not None:
        region._trade_fee_mult = dest.gov.get_trade_fee_multiplier()
    else:
        region._trade_fee_mult = 0.95

    decide_borrow_deposit(region, region.agents, all_goods_price, food_price, t)

    # ---- Phase A: trade food, wood, furniture ----
    recipes = region.recipes
    agents = region.agents
    goods_goods = [Goods.food, Goods.wood, Goods.furniture]
    desired_food = 16
    desired_wood = 10
    desired_furn = max(1, int(16 / max(1, recipes[Goods.furniture]['price'])))
    desires = {Goods.food: desired_food, Goods.wood: desired_wood,
               Goods.furniture: desired_furn}
    prices = {g: recipes[g]['price'] for g in goods_goods}
    total_asks = {g: 0 for g in goods_goods}
    total_bids = {g: 0 for g in goods_goods}
    for a in agents:
        ar = recipes[a.output]
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
            ask = calculate_ask(region, a, g, p, is_emp)
            a.ask = ask
            total_asks[g] += ask
            setattr(a, f'bid_{g.name}', bid)
            setattr(a, f'ask_{g.name}', ask)

    max_demand_ratio = 0
    most_demand_good = Goods.food
    for good in goods_goods:
        ta = total_asks[good]
        tb = total_bids[good]
        imp_pool, imp_total = gather_import_pool(region, good)
        if ta == 0 and imp_total == 0 and tb == 0:
            price_decay(region, good)
            continue
        price_ta = ta + imp_total
        demand_ratio = 5.0 if price_ta == 0 else tb / price_ta
        region.demand_ratio_log[good].append(demand_ratio)
        region.demand_log[good].append(tb)
        region.supply_log[good].append(price_ta)
        if max_demand_ratio < demand_ratio and tb > 0:
            max_demand_ratio = demand_ratio
            most_demand_good = good
        update_price_ref(region, good, demand_ratio)
        ref = region._price_ref[good]
        price = ref
        if min(price_ta, tb) == 0:
            region._auction_import_sales[good] = (0, 0.0)
            continue
        total_bought, tcash, realized = clear_discriminatory(
            region, good, ref, price_ta, tb, imp_pool, agents, t)
        region.sold_log[good].append(total_bought)
        region._trade_prices[good].append(realized)
        total_sold = total_bought
        askers = sorted(agents, key=lambda a: a.ask, reverse=True)

        # Charity food purchase
        if good == Goods.food:
            charity_bid = region.charity.bid_food(price, desires[good], region.bank)
            if charity_bid > 0:
                food_askers = [a for a in askers if a.output == Goods.food
                               and a.inv_get(Goods.food, 0) > 2]
                charity_bought = 0
                for seller in food_askers:
                    if charity_bid <= 0 or region.charity.cash < price:
                        break
                    available = seller.inv_get(Goods.food, 0) - 2
                    if available <= 0:
                        continue
                    bought = min(charity_bid, available, int(region.charity.cash / price))
                    if bought > 0:
                        seller.inv_add(Goods.food, -bought)
                        seller.cash += bought * price
                        region.charity.pay_for_food(bought * price)
                        region.charity.receive_food(bought)
                        charity_bid -= bought
                        charity_bought += bought
                if charity_bought > 0:
                    total_sold += charity_bought
                    region.sold_log[good][-1] += charity_bought
                    loginfo(t, f"{region.charity.name} bought {charity_bought} food at ${price:.2f}")
            region.charity.deposit_remaining(region.bank)

            # Government food purchase
            if hasattr(region, 'gov'):
                gov_bid = region.gov.bid_food(price, desires[good], region.bank)
                if gov_bid > 0:
                    gov_askers = [a for a in askers if a.output == Goods.food
                                   and a.inv_get(Goods.food, 0) > 2]
                    gov_bought = 0
                    for seller in gov_askers:
                        if gov_bid <= 0 or region.gov.agent.cash < price:
                            break
                        available = seller.inv_get(Goods.food, 0) - 2
                        if available <= 0:
                            continue
                        bought = min(gov_bid, available,
                                     int(region.gov.agent.cash / price))
                        if bought > 0:
                            seller.inv_add(Goods.food, -bought)
                            seller.cash += bought * price
                            region.gov.pay_for_food(bought * price)
                            region.gov.receive_food(bought)
                            gov_bid -= bought
                            gov_bought += bought
                    if gov_bought > 0:
                        total_sold += gov_bought
                        region.sold_log[good][-1] += gov_bought
                        loginfo(t, f"Government({region.gov.name}) bought "
                                f"{gov_bought} food at ${price:.2f}")
                region.gov.deposit_remaining(region.bank)

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

    region.most_demand = most_demand_good

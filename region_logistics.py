"""
Inter-region transport routes, trader arbitrage repointing, migration scoring, and trader exits.
"""

from goods import Goods
from transporter import Route
from logger import loginfo
from random_cache import rand


def migration_intent_score(region):
    """Compute a per-tile migration intent score (M1.5)."""
    agents = region.agents
    if not agents:
        return 0.0
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
    return max(0.0, min(10.0, score))


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
    """Re-point each trader at the best-margin neighbour (M0.3)."""
    if not region.neighbors:
        return
    for trader in region.trader_agents:
        if not getattr(trader, 'is_trader', False):
            continue
        good = trader.trade_good or Goods.food
        local_price = region.recipes.get(good, {}).get('price', 0.0)
        transport_cost = transport_cost_per_unit(region)
        floor = (local_price + transport_cost) * (1.0 + region.IMPORT_MARGIN_MIN)
        best = None
        best_score = -1e18
        for name, other in region.neighbors.items():
            if not other or getattr(other, 'recipes', None) is None:
                continue
            desk = region.forex_desks.get(name)
            rate = desk.buy_rate() if desk is not None else 1.0
            dest_price = other.recipes.get(good, {}).get('price', 0.0)
            net_foreign = dest_price * rate
            score = net_foreign - floor
            if score > best_score:
                best_score = score
                best = other
        if best is None or best_score <= 0:
            continue
        if best is not getattr(trader, 'destination_region', None):
            trader.destination_region = best


def post_exports_to_route(region):
    """Move all traders' export inventory onto their destination Route."""
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
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            qty = trader.inventory_export[g.value]
            if qty > 0:
                route.post(trader, g, qty)


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

    # 2. Gather all tradable lots (export + foreign + parked)
    lots = []
    for g in [Goods.food, Goods.wood, Goods.furniture]:
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
            buyer.cash -= total
            agent.cash += total
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

    # 4. Pay down loans with all remaining liquid cash
    while agent.cash > 0 and agent.loans:
        loan = agent.loans[0]
        payment = min(agent.cash, loan.getPaymentAmount())
        if payment <= 0:
            break
        agent.cash -= payment
        loan.pay(payment)
        if loan.isPaid():
            agent.loans.pop(0)

    # 5. Zero remaining trade state and reset to food producer
    agent.is_trader = False
    agent.output = Goods.food
    agent.trade_good = None
    agent.hungry_steps = 0
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
    best_good = Goods.food
    best_gap = -1.0
    dest = region.destination_region
    if dest is not None:
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            gap = dest.recipes[g]['price'] - region.recipes[g]['price']
            if gap > best_gap:
                best_gap = gap
                best_good = g
    agent.is_trader = True
    agent.home_region = region.name
    agent.destination_region = region.destination_region
    agent.output = Goods.food
    agent.trade_good = best_good
    for g in Goods:
        if g == Goods.none:
            continue
        agent.inventory_export[g.value] = 0
        agent.inventory_foreign[g.value] = 0
    agent.parked_foreign = {}
    for rt in all_routes(region):
        rt.reclaim(agent)
    agent.inv_set(Goods.food, max(agent.inv_get(Goods.food, 0), 4))
    agent.employer = None

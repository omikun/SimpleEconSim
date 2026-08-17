"""
Generalized multi-region trade helpers for N-tile drivers (M0.3+).

These mirror the helpers in econsim_two_region.py but are multi-neighbour
aware: they resolve the per-pair ForexDesk from ``region.forex_desks``
(falling back to the legacy ``region.forex``) and per-pair Route from
``region.routes`` (falling back to ``region.route``).  econsim_two_region.py
itself is NOT touched so the legacy single-partner driver stays intact.
"""

from goods import Goods
import forex as fx


def desk_for(region, partner):
    """Per-pair ForexDesk between *region* and *partner* (multi-neighbor)."""
    desks = getattr(region, 'forex_desks', None)
    if desks:
        d = desks.get(partner.name)
        if d is not None:
            return d
    return getattr(region, 'forex', None)


def route_for(region, partner):
    """Per-pair Route from *region* to *partner* (multi-neighbor)."""
    routes = getattr(region, 'routes', None)
    if routes:
        r = routes.get(partner.name)
        if r is not None:
            return r
    return getattr(region, 'route', None)


GOODS_T1 = (Goods.food, Goods.wood, Goods.furniture)
T1_MARGIN_MIN = 0.05


def pending_imports(dest, src):
    """Goods that *src*'s traders have physically delivered to *dest*.

    Returns {Goods.good: [(trader, qty, is_parked), ...]}.
      - Active pool: ``inventory_foreign`` lots whose current destination is
        *dest* (same rule as the legacy two-region helper) -> is_parked=False.
      - Parked pool (T1): lots that matured at *dest* after the trader
        re-pointed elsewhere -> is_parked=True.  Settlement decrements
        parked_foreign instead of the shared inventory_foreign.
    """
    pend = {}
    for trader in src.trader_agents:
        if getattr(trader, 'destination_region', None) is dest:
            for g in GOODS_T1:
                qty = trader.inventory_foreign[g.value]
                if qty > 0:
                    pend.setdefault(g, []).append((trader, qty, False))
        for g in GOODS_T1:
            qty = trader.parked_get(dest.name, g, 0)
            if qty > 0:
                pend.setdefault(g, []).append((trader, qty, True))
    return pend


def _net_foreign_home(trader, region, all_regions, good):
    """*region*'s price for *good* expressed in the trader's home currency.

    Uses the home-side per-pair desk buy rate (converts the destination
    currency into the trader's home currency), matching _repoint_traders.
    Same-currency tiles convert at 1.0.
    """
    price = region.recipes.get(good, {}).get('price', 0.0)
    if price <= 0:
        return 0.0
    if trader.home_region == region.name:
        return price
    home = None
    for r in all_regions:
        if r.name == trader.home_region:
            home = r
            break
    if home is None:
        return 0.0
    desk = (home.forex_desks or {}).get(region.name)
    if desk is None:
        return 0.0
    return price * desk.buy_rate()


def resolve_parked(regions):
    """T1.3: resolve parked goods once per turn (re-route / hold).

    Selling at the parked tile is driven by that tile's auction: the harness's
    pending_imports(dest, src) offers parked lots with is_parked=True, and
    settlement decrements parked_foreign in place.  Unslued lots remain parked
    for the next turn automatically.

    This function only handles RE-ROUTE: a parked lot at tile X is re-shipped
    toward the trader's CURRENT destination via X's own outbound route, and
    only when the trader changed destination (dest != x) AND that tile clears
    strictly more than a sale at X and still beats cost.  Otherwise HOLD.
    """
    for x in regions:
        for src in regions:
            if src is x:
                continue
            for trader in src.trader_agents:
                if not getattr(trader, 'is_trader', False) or not getattr(trader, 'alive', True):
                    continue
                bucket = trader.parked_foreign.get(x.name)
                if not bucket:
                    continue
                dest = getattr(trader, 'destination_region', None)
                if dest is None or dest is x or dest is src:
                    continue
                if dest.name not in x.neighbors:
                    continue
                for g in GOODS_T1:
                    qty = bucket[g.value]
                    if qty <= 0:
                        continue
                    cost = trader.cost_get(g, 0)
                    if cost <= 0:
                        cost = max(0.05, src.recipes.get(g, {}).get('price', 0.0))
                    decent = cost * (1.0 + T1_MARGIN_MIN)
                    net_x = _net_foreign_home(trader, x, regions, g)
                    net_z = _net_foreign_home(trader, dest, regions, g)
                    if net_z > net_x and net_z >= decent:
                        route = x.routes.get(dest.name)
                        if route is not None:
                            route.post_parked(trader, g, qty)


def settle_trade(t, destination_region, source_region):
    """Post-auction settlement for an ordered region pair (multi-neighbor).

    Same responsibilities as econsim_two_region.settle_trade: log the priced
    auction's import sales, let away-traders buy food at the destination out
    of their wallet, and post leftover foreign earnings as ASKs on the home
    desk for this specific partner currency.  Returns (qty, value).

    v3_wilderness: a WILDERNESS destination (no bank, no currency, no market)
    is serviced exclusively by trade_settle.settle_wilderness — arriving here
    would credit homesteader sellers in a None-keyed wallet and leak past the
    per-currency audit, so skip it.
    """
    if getattr(destination_region, 'wilderness', False):
        return 0, 0.0
    sname = source_region.name
    traders = [a for a in source_region.trader_agents
               if a.home_region == sname]
    desk = desk_for(source_region, destination_region)
    use_fx = desk is not None and getattr(source_region, 'home_currency',
                                          None) is not None
    dest_currency = destination_region.home_currency
    total_sold_value = 0.0
    total_sold_quantity = 0

    # 1. Log what the destination's priced auction sold for us this turn.
    for good in [Goods.food, Goods.wood, Goods.furniture]:
        aq, av = destination_region._auction_import_sales.get(good, (0, 0.0))
        if aq > 0:
            source_region.export_vol[good].append(aq)
            source_region.export_val[good].append(av)
            destination_region.import_vol[good].append(aq)
            destination_region.import_val[good].append(av)
            total_sold_quantity += aq
            total_sold_value += av
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)

    # 2. Away traders buy food for themselves at the destination.
    for trader in traders:
        if trader.inv_get(Goods.food, 0) < 8:
            food_price = destination_region.recipes[Goods.food]['price']
            need = 8 - trader.inv_get(Goods.food, 0)
            if use_fx:
                wallet_bal = fx.fx_balance(trader, dest_currency)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0
            to_buy = min(need, afford)
            if to_buy > 0:
                sellers = [a for a in destination_region.agents
                           if a.output == Goods.food
                           and a.inv_get(Goods.food, 0) > 2
                           and not getattr(a, 'is_trader', False)]
                bought = 0
                for seller in sellers:
                    if bought >= to_buy:
                        break
                    available = seller.inv_get(Goods.food, 0) - 2
                    if available <= 0:
                        continue
                    take = min(available, to_buy - bought)
                    seller.inv_add(Goods.food, -take)
                    seller.cash += take * food_price
                    if use_fx:
                        fx.fx_sub(trader, dest_currency, take * food_price)
                    else:
                        trader.cash -= take * food_price
                    trader.inv_add(Goods.food, take)
                    bought += take

    # 3. Post leftover foreign earnings as ASKs on the home desk for this
    #    partner's currency (book persists; cycle clears/repatriates).
    if use_fx:
        for trader in traders:
            bal = fx.fx_balance(trader, dest_currency)
            if bal > 0:
                desk.post_order('ask', trader, bal, desk.buy_rate())

    if total_sold_value > 0 and t % 50 == 0:
        from logger import loginfo
        loginfo(t, f"TRADE {source_region.name}->{destination_region.name}: "
                f"sold {total_sold_quantity} units worth ${total_sold_value:.2f} "
                f"through the priced auction")

    return total_sold_quantity, total_sold_value


def trader_wealth(region):
    """Total trader wealth in home currency across all desks.

    Cash + bank deposits + every foreign wallet converted at that currency's
    per-pair desk buy rate.
    """
    total = 0.0
    desks = getattr(region, 'forex_desks', None)
    for a in region.trader_agents:
        w = a.cash + region.bank.deposits.get(a, 0)
        if desks:
            for name, d in desks.items():
                other = d.other
                if other == region.home_currency:
                    continue
                w += fx.fx_balance(a, other) * d.buy_rate()
        elif getattr(region, 'forex', None) is not None:
            d = region.forex
            w += fx.fx_balance(a, d.other) * d.buy_rate()
        total += w
    return total


def check_trader_holdings(region, other, t):
    """Sanity-check that no trader holds goods that can't clear a profit.

    Multi-neighbor equivalent of econsim_two_region.check_trader_holdings:
    uses the per-pair desk rate and per-pair route holdings.
    Returns number of violations.
    """
    violations = 0
    stranded_value = 0.0
    worst = []
    transport_cost = region._transport_cost_per_unit()
    desk = desk_for(region, other)
    home_per_dest = desk.buy_rate() if desk is not None else 1.0
    route = route_for(region, other)
    for trader in region.trader_agents:
        if not getattr(trader, 'is_trader', False):
            continue
        holdings = {}
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            qty = (trader.inventory_export[g.value]
                   + trader.inventory_foreign[g.value]
                   + trader.parked_total(g))
            if route is not None:
                qty += route.holdings_of(trader).get(g, 0)
            if g != Goods.food:
                qty += trader.inv_get(g, 0)
            if qty > 0:
                holdings[g] = qty
        for g, qty in holdings.items():
            dest_price = other.recipes.get(g, {}).get('price', 0)
            cost = trader.cost_get(g, 0)
            if cost <= 0:
                cost = region.recipes.get(g, {}).get('price', 0)
            net_foreign = dest_price * home_per_dest
            loss_per_unit = (cost + transport_cost) - net_foreign
            if loss_per_unit > 0:
                violations += 1
                stranded_value += loss_per_unit * qty
                worst.append((loss_per_unit * qty, trader.name(), qty, g,
                              loss_per_unit))
    if violations > 0:
        worst.sort(reverse=True)
        print(f"  [TRADER AUDIT] T={t} {region.name}: {violations} unprofitable "
              f"holdings, stranded value ${stranded_value:,.0f}")
        for loss, name, qty, g, unit in worst[:5]:
            print(f"      {name}: {qty} {g} @ ${unit:.2f} loss/unit")
    return violations
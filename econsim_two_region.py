#!/usr/bin/env python3
"""
Two-region economic simulation.

Initializes two independent regions, each with its own Government, bank, agent
population, and logging state.  Trade flows between regions via specialized
trader agents through a structural Route (transporter.py) that owns delivery
time and congestion.  Supports per-government policy toggles and floating
exchange rates.

Usage:
    python3 econsim_two_region.py [time_steps]
"""

import sys
import random
from collections import defaultdict

from goods import Goods, profession
from region import Region, get_total_cash
from econsim_states import starvation_limit, max_career_switches, probability_birth, birth_gap
from logger import loginfo, logInit
from transporter import Route
import wealth_lineage
import wealth_diagnostic
import forex as fx


# =============================================================================
# Trader constant
# =============================================================================
TRADER_GOOD = Goods.none
profession[Goods.none] = 'T'  # traders show as 'T'

MAX_TRADER_FRACTION = 0.2
TRANSPORT_DELAY = 1

# Floating exchange rate tuning: recent net trade flows (rolling window, not
# cumulative stock) drive the rate; a gentle reversion pulls toward parity.
FX_WINDOW = 40            # rolling window (turns) of net flows used
FX_SENSITIVITY = 0.00005  # rate change per $ of average recent flow
FX_REVERT = 0.01          # per-turn pull toward parity (1.0)


def update_exchange_rate(region):
    """Adjust the region's exchange rate.

    Phase 1: delegates to the region's ForexDesk (central-bank quote with
    reserve constraints) when wired.  Falls back to the legacy trade-flow
    heuristic when no desk exists (e.g. single-region or external scripts).
    """
    desk = getattr(region, 'forex', None)
    if desk is not None:
        # PPP anchor: basket cost in partner / basket cost at home.
        partner = region.destination_region
        ppp = 1.0
        if partner is not None:
            home_col = max(0.1, region.cost_of_living)
            partner_col = max(0.1, partner.cost_of_living)
            ppp = partner_col / home_col
        desk.update(0, bank=getattr(region, 'bank', None),
                    fx_regime=getattr(region.gov, 'fx_regime', 'managed'),
                    ppp_target=ppp)
        desk.save_rate(region)
        # Record the per-turn rate history so plots/dashboards show movement.
        region.exchange_rate_log.append(region.exchange_rate)
        return region.exchange_rate
    if not getattr(region.gov, 'floating_exchange_rate_enabled', True):
        region.exchange_rate_log.append(region.exchange_rate)
        return
    recent = region.trade_flow_log[-FX_WINDOW:]
    flow = sum(recent) / len(recent) if recent else 0.0
    region.exchange_rate *= (1 + flow * FX_SENSITIVITY)
    region.exchange_rate += (1.0 - region.exchange_rate) * FX_REVERT
    region.exchange_rate = max(0.5, min(2.0, region.exchange_rate))
    region.exchange_rate_log.append(region.exchange_rate)


# =============================================================================
# Inter-region settlement (imports are sold in the destination's auction)
# =============================================================================

def _pending_imports(dest, src):
    """Goods that *src*'s traders have physically delivered to *dest*.

    Returns {Goods.good: [(trader, qty), ...]}.  The main loop installs this
    on each destination before step so the round-1 auction can include them.
    """
    pend = {}
    for trader in src.trader_agents:
        if getattr(trader, 'destination_region', None) is not dest:
            continue
        for g in (Goods.food, Goods.wood, Goods.furniture):
            qty = trader.inventory_foreign[g.value]
            if qty > 0:
                pend.setdefault(g, []).append((trader, qty))
    return pend


def settle_trade(t, destination_region, source_region):
    """Post-auction settlement for a region pair.

    Import goods themselves are sold inside the destination's round-1 priced
    auction (Region._clear_discriminatory) during step(); this function:
      1. logs the auction's sales into export/import volume & value logs,
      2. lets away-traders buy food at the destination out of their wallet,
      3. posts leftover foreign earnings as ASKs on the home FX desk.
    """
    sname = source_region.name
    # Use cached trader list (maintained on Region) — avoid O(N) filter per call
    traders = [a for a in source_region.trader_agents
               if a.home_region == sname]
    use_fx = (getattr(source_region, 'forex', None) is not None
              and getattr(source_region, 'home_currency', None) is not None)
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

    # 2. Traders buy food for themselves at the destination out of sales
    #    proceeds (they are away from home and must eat from local markets).
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

    # 3. Post leftover foreign earnings as ASKs on the home desk's order book
    #    (book persists across turns so they can cross with next-turn
    #    working-capital bids).  Residuals are repatriated by fx.cycle_market
    #    (desk last resort) at the end of the turn.
    if use_fx:
        desk = source_region.forex
        for trader in traders:
            bal = fx.fx_balance(trader, dest_currency)
            if bal > 0:
                desk.post_order('ask', trader, bal, desk.buy_rate())

    if total_sold_value > 0 and t % 50 == 0:
        loginfo(t, f"TRADE {source_region.name}->{destination_region.name}: "
                f"sold {total_sold_quantity} units worth ${total_sold_value:.2f} "
                f"through the priced auction")

    return total_sold_quantity, total_sold_value


def trader_wealth(region):
    """Total trader wealth in home currency.

    Cash + bank deposits + foreign wallet converted at the home desk's
    current buy rate (the rate at which the trader could repatriate today).
    """
    total = 0.0
    desk = getattr(region, 'forex', None)
    for a in region.trader_agents:
        w = a.cash + region.bank.deposits.get(a, 0)
        if desk is not None:
            w += fx.fx_balance(a, desk.other) * desk.buy_rate()
        total += w
    return total


def check_trader_holdings(region, other, t):
    """Sanity-check that no trader holds goods that can't clear a profit.

    Audit-only: for every good a trader holds (export, in-transit, or
    foreign), compute the deliverable foreign net
        dest_price × home_per_dest − (cost_basis + transport_cost)
    and warn if it is negative.  Because prices move between buy and
    delivery, some price-drift losses are expected; this audit's job is to
    surface *sustained* stranding (destinations where local producers
    persistently undercut the import).  Prints a per-turn summary with the
    largest violations, capped to avoid log spam.
    """
    violations = 0
    stranded_value = 0.0
    worst = []
    transport_cost = region._transport_cost_per_unit()
    desk = getattr(region, 'forex', None)
    home_per_dest = desk.buy_rate() if desk is not None else 1.0
    for trader in region.trader_agents:
        if not getattr(trader, 'is_trader', False):
            continue
        holdings = {}
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            qty = (trader.inventory_export[g.value]
                   + trader.inventory_foreign[g.value])
            if region.route is not None:
                qty += region.route.holdings_of(trader).get(g, 0)
            if g != Goods.food:
                # Local stock for non-food goods is trade inventory.  For
                # food, local stock is the personal eating buffer (≤ 8 units)
                # which is consumed, never shipped — exclude it.
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
                worst.append((loss_per_unit * qty, trader.name(), qty, g, loss_per_unit))
    if violations > 0:
        worst.sort(reverse=True)
        print(f"  [TRADER AUDIT] T={t} {region.name}: {violations} unprofitable "
              f"holdings, stranded value ${stranded_value:,.0f}")
        for loss, name, qty, g, unit in worst[:5]:
            print(f"      {name}: {qty} {g} @ ${unit:.2f} loss/unit")
    return violations


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Two-Region Simulation: {time_steps} time steps per region\n")

    random.seed(42)

    # 3 traders per good type (food/wood/furniture) = 9 traders, 200 agents.
    region_a = Region("Region_A", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037},
                       number_of_traders=3)
    region_b = Region("Region_B", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05},
                       number_of_traders=3)

    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2

    region_a.destination_region = region_b
    region_b.destination_region = region_a
    for trader in region_a.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_b
    for trader in region_b.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_a

    # Wire the structural routes (one directional Route per region pair).
    region_a.route = Route(f"{region_a.name}->{region_b.name}",
                           region_a, region_b, base_delay=TRANSPORT_DELAY)
    region_b.route = Route(f"{region_b.name}->{region_a.name}",
                           region_b, region_a, base_delay=TRANSPORT_DELAY)

    fx.connect_regions(region_a, region_b, t=0)
    region_a._init_trader_wealth = trader_wealth(region_a)
    region_b._init_trader_wealth = trader_wealth(region_b)
    currencies = [region_a.home_currency, region_b.home_currency]

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    # Instrument diagnostics so they record from THIS simulation run
    wealth_lineage.init_collectors()
    wealth_diagnostic.init_collectors()

    for t in range(1, time_steps + 1):
        curr_before = {c: fx.audit_currency_total([region_a, region_b], c)
                       for c in currencies}
        cash_before = sum(curr_before.values())
        region_a.pending_imports = _pending_imports(region_a, region_b)
        region_b.pending_imports = _pending_imports(region_b, region_a)
        region_a._auction_import_sales = {}
        region_b._auction_import_sales = {}
        region_a.step(t)
        region_b.step(t)
        # Advance routes: deliver matured cargo, load freshly posted cargo.
        region_a.route.advance()
        region_a.route.deliver_pending()
        region_b.route.advance()
        region_b.route.deliver_pending()
        settle_trade(t, region_a, region_b)
        settle_trade(t, region_b, region_a)
        fx.cycle_market(region_a, region_b, t)
        # Sanity check: no profitable-trader invariant violations.
        check_trader_holdings(region_a, region_b, t)
        check_trader_holdings(region_b, region_a, t)
        wealth_lineage.record_turn(t, region_a, region_b)
        wealth_diagnostic.record_turn(t, region_a, region_b)
        cash_after = sum(fx.audit_currency_total([region_a, region_b], c)
                         for c in currencies)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")

        for c in currencies:
            delta = fx.audit_currency_total([region_a, region_b], c) - curr_before[c]
            if abs(delta) > 5.0:
                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")

        for region, other in [(region_a, region_b), (region_b, region_a)]:
            turn_export = sum(region.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.export_val[g])
            turn_import = sum(region.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.import_val[g])
            region.cumulative_trade_balance += (turn_export - turn_import)
            region.trade_flow_log.append(turn_export - turn_import)
            update_exchange_rate(region)
            # Per-turn foreign reserves snapshot (for balance-of-payments plot)
            region.foreign_reserves_log.append(dict(region.bank.foreign_reserves))

        for g in [Goods.food, Goods.wood, Goods.furniture]:
            price_a = region_a.recipes[g]['price']
            price_b = region_b.recipes[g]['price']
            spread = abs(price_a - price_b)
            region_a.price_spread_log[g].append(spread)
            region_b.price_spread_log[g].append(spread)

        if t % 50 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\nGenerating plots...")
    region_a.plot("region_a_output.png")
    region_b.plot("region_b_output.png")
    import trade_dashboard
    trade_dashboard.generate_dashboard(region_a, region_b)
    wealth_lineage.generate_plots(time_steps, region_a, region_b)
    wealth_diagnostic.generate_plots(time_steps, region_a, region_b)

    print("\n" + "=" * 60)
    print("FINAL SUMMARY =")
    print("=" * 60)

    for region in (region_a, region_b):
        print(f"\n--- {region.name} ---")
        labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture',
                  Goods.transport: 'Transport', Goods.gov: 'Gov'}
        for g in region.goods:
            pop = region.population_log.get(g, [0])[-1] if region.population_log.get(g) else 0
            price = (region.price_log.get(g, [1.0])[-1] if g != Goods.gov and region.price_log.get(g) else 1.0)
            inv = (region.inventory_log.get(g, [0])[-1] if g != Goods.gov and region.inventory_log.get(g) else 0)
            cash = region.cash_log.get(g, [0])[-1] if region.cash_log.get(g) else 0
            print(f"  {labels[g]}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
        total_population = region.total_population[-1] if region.total_population else 0
        dead_starved = region.dead_starved_population[-1] if region.dead_starved_population else 0
        print(f"  Total Pop: {total_population}, Dead/Starved: {dead_starved}")
        gdp_value = region.gdp_log[-1] if region.gdp_log else 0
        print(f"  Final GDP/turn: ${gdp_value:.2f}")

        total_export = sum(sum(v) for v in region.export_vol.values())
        total_import = sum(sum(v) for v in region.import_vol.values())
        total_export_val = sum(sum(v) for v in region.export_val.values())
        total_import_val = sum(sum(v) for v in region.import_val.values())
        print(f"  Total Exports: {total_export} units (${total_export_val:.2f})")
        print(f"  Total Imports: {total_import} units (${total_import_val:.2f})")
        net_trade = total_export_val - total_import_val
        sign = "+" if net_trade >= 0 else ""
        print(f"  Net Trade Balance: {sign}${net_trade:.2f}")
        avg_spread = {}
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            if region.price_spread_log.get(g) and len(region.price_spread_log[g]) > 0:
                avg_spread[g] = sum(region.price_spread_log[g]) / len(region.price_spread_log[g])
        if avg_spread:
            spread_str = ", ".join(f"{Goods(g).name}: ${s:.2f}" for g, s in avg_spread.items())
            print(f"  Avg Price Spread: {spread_str}")
        init_trader_wealth = getattr(region, '_init_trader_wealth', 0.0)
        final_traders = [a for a in region.agents if a.is_trader]
        final_cash = sum(a.cash for a in final_traders)
        final_deposits = sum(region.bank.deposits.get(a, 0) for a in final_traders)
        desk = getattr(region, 'forex', None)
        final_wallet = 0.0
        if desk is not None:
            final_wallet = sum(fx.fx_balance(a, desk.other) for a in final_traders) * desk.buy_rate()
        final_trader_wealth = final_cash + final_deposits + final_wallet
        trader_roi = 0.0
        if init_trader_wealth > 0:
            trader_roi = (final_trader_wealth - init_trader_wealth) / init_trader_wealth * 100
        # Charity summary
        c = region.charity.log
        print(f"  Charity: ${c['donations_collected']:.2f} collected, "
              f"{c['food_distributed']} food to {c['recipients']} recipients, "
              f"{c['food_purchased']} purchased")

        # Trader summary (wealth = cash + deposits + foreign wallet @ buy rate)
        print(f"  Traders: {len(final_traders)} traders, "
              f"cash ${final_cash:.0f}, deposits ${final_deposits:.0f}, "
              f"wallet ${final_wallet:.0f}, wealth ${final_trader_wealth:.0f} "
              f"(start ${init_trader_wealth:.0f}), "
              f"ROI: {trader_roi:.1f}%")

        desk = getattr(region, "forex", None)
        if desk is not None:
            bank = region.bank
            print(f"  FX Desk: mid={desk.mid:.4f} ({region.home_currency} per 1 "
                  f"{desk.other}), spread={desk.spread:.2%}, "
                  f"reserves={ {k: round(v, 2) for k, v in dict(bank.foreign_reserves).items()} }, "
                  f"fx_pool=${bank.fx_pool:.2f}")

        # Government income decomposition
        income_log = getattr(region.gov, 'income_log', None)
        if income_log:
            total_tax = sum(snap.get('tax', 0.0) for snap in income_log)
            total_tariff = sum(snap.get('tariff', 0.0) for snap in income_log)
            total_inheritance = sum(snap.get('inheritance', 0.0) for snap in income_log)
            print(f"  Gov Income: Tax ${total_tax:.2f}, Tariff ${total_tariff:.2f}, "
                  f"Inheritance ${total_inheritance:.2f}, "
                  f"Total ${total_tax + total_tariff + total_inheritance:.2f} "
                  f"(gov cash ${region.gov.agent.cash:.2f})")

    print("\nDone.")


if __name__ == "__main__":
    main()
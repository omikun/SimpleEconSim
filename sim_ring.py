#!/usr/bin/env python3
"""
3-tile ring simulation (M0.3).

Regions A, B, C form a ring A-B-C-A.  Each region has terrain advantages,
one Route per neighbor, and one ForexDesk per neighbor.  Traders re-point
each turn toward the best-margin neighbour (Region._repoint_traders).

Runs `time_steps` turns and verifies per-currency conservation across all
three home currencies.

Usage:
    python3 sim_ring.py [time_steps]
"""

import sys
import random

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
from world_trade import (pending_imports, resolve_parked, settle_trade,
                         trader_wealth, check_trader_holdings)


TRANSPORT_DELAY = 1


def update_exchange_rate_pair(region, partner):
    """Update region<->partner desk mid from PPP + reserve pressure.

    Uses the per-pair desk; the legacy region.exchange_rate field is kept
    in sync for single-primary drivers (plots show the primary pair).
    """
    desk = region.forex_desks.get(partner.name)
    if desk is None:
        return
    home_col = max(0.1, region.cost_of_living)
    partner_col = max(0.1, partner.cost_of_living)
    ppp = partner_col / home_col
    desk.update(0, bank=region.bank,
                fx_regime=getattr(region.gov, 'fx_regime', 'managed'),
                ppp_target=ppp)
    if getattr(region, 'destination_region', None) is partner:
        desk.save_rate(region)


def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Ring Simulation (A-B-C-A): {time_steps} turns\n")
    random.seed(42)

    # --- Tiles with terrain comparative advantages ---
    region_a = Region("A", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.753,
                                               Goods.wood: 0.110,
                                               Goods.furniture: 0.037},
                      number_of_traders=3,
                      terrain={Goods.food: 1.6})
    region_b = Region("B", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.50,
                                               Goods.wood: 0.35,
                                               Goods.furniture: 0.05},
                      number_of_traders=3,
                      terrain={Goods.wood: 1.6})
    region_c = Region("C", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.55,
                                               Goods.wood: 0.20,
                                               Goods.furniture: 0.12},
                      number_of_traders=3)
    # C gets a furniture processing edge via cheaper wood access from B;
    # plain terrain otherwise (exports furniture back through the ring).

    regions = [region_a, region_b, region_c]

    # --- Wire the ring: every region is a neighbor of the other two ---
    for r in regions:
        for other in regions:
            if other is r:
                continue
            r.add_neighbor(other)   # registers routes + legacy aliases
    for r in regions:
        for other in regions:
            if other is r:
                continue
            fx.connect_desks(r, other, t=0)

    for r in regions:
        r._init_trader_wealth = trader_wealth(r)

    currencies = [r.home_currency for r in regions]

    print("Regions:", ", ".join(r.name for r in regions))
    for r in regions:
        print(f"  {r.name}: {len(r.agents)} agents, "
              f"terrain={ {str(k): v for k, v in r.terrain.items()} }")

    pair_orders = [(r, o) for r in regions for o in regions if o is not r]

    for t in range(1, time_steps + 1):
        curr_before = {c: fx.audit_currency_total(regions, c) for c in currencies}
        cash_before = sum(curr_before.values())

        # Install pending imports + clear auction sales.  Traders re-point
        # inside Region.step() (single repoint per turn keeps destination
        # switches from splitting a route mid-auction).
        for r in regions:
            pending = {}
            for other in regions:
                if other is r:
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}

        for r in regions:
            r.step(t)

        # Advance/deliver all routes, then resolve parked lots (T1.3).  Parked
        # goods sell via the NEXT turn's auction; profitable re-routes ship now.
        for r in regions:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()
        resolve_parked(regions)

        # Settlement for every ordered pair
        for r, other in pair_orders:
            settle_trade(t, other, r)

        # FX: one interbank cycle across all desks
        fx.cycle_all_markets(regions, t)

        # Per-pair exchange-rate updates
        for r, other in pair_orders:
            update_exchange_rate_pair(r, other)

        # Conservation checks per currency
        for c in currencies:
            delta = fx.audit_currency_total(regions, c) - curr_before[c]
            if abs(delta) > 5.0:
                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")

        cash_after = sum(fx.audit_currency_total(regions, c) for c in currencies)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after - cash_before:.2f}")

        # Trade-flow + price-spread logging
        for r in regions:
            for other in regions:
                if other is r:
                    continue
                turn_export = sum(r.export_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.export_val[g])
                turn_import = sum(r.import_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.import_val[g])
                r.cumulative_trade_balance += (turn_export - turn_import)
                r.trade_flow_log.append(turn_export - turn_import)
            for other in regions:
                if other is r:
                    continue
                for g in [Goods.food, Goods.wood, Goods.furniture]:
                    spread = abs(r.recipes[g]['price'] - other.recipes[g]['price'])
                    r.price_spread_log[g].append(spread)

        if t % 50 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\n" + "=" * 60)
    print("RING FINAL SUMMARY (A-B-C-A)")
    print("=" * 60)
    for r in regions:
        print(f"\n--- {r.name} ---")
        food_price = r.recipes[Goods.food]['price']
        wood_price = r.recipes[Goods.wood]['price']
        furn_price = r.recipes[Goods.furniture]['price']
        pop = r.total_population[-1] if r.total_population else 0
        print(f"  Prices: food=${food_price:.2f}, wood=${wood_price:.2f}, "
              f"furniture=${furn_price:.2f}")
        print(f"  Total Pop: {pop}")
        total_export = sum(sum(v) for v in r.export_vol.values())
        total_import = sum(sum(v) for v in r.import_vol.values())
        total_export_val = sum(sum(v) for v in r.export_val.values())
        total_import_val = sum(sum(v) for v in r.import_val.values())
        print(f"  Total Exports: {total_export} units (${total_export_val:.2f})")
        print(f"  Total Imports: {total_import} units (${total_import_val:.2f})")
        net = total_export_val - total_import_val
        sign = "+" if net >= 0 else ""
        print(f"  Net Trade Balance: {sign}${net:.2f}")
        desk = r.forex_desks
        if desk:
            rates = ", ".join(f"{n}: {d.mid:.3f}" for n, d in desk.items())
            print(f"  FX mid rates: {rates}")
        init_w = getattr(r, '_init_trader_wealth', 0.0)
        final_w = trader_wealth(r)
        roi = (final_w - init_w) / init_w * 100 if init_w > 0 else 0.0
        print(f"  Trader wealth: ${final_w:.2f} (start ${init_w:.2f}), "
              f"ROI: {roi:.1f}%")

    print("\nDone.")


if __name__ == "__main__":
    main()
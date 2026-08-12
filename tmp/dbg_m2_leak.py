#!/usr/bin/env python3
"""Reproduce the seed-7 ring CURRENCY C SUPPLY SHIFT at T=243 (post-M2 leak).

Builds the exact ring used by tmp/behavior_drift.py (seed 7), steps to
T=243, and snapshots every component of audit_currency_total for C before
and after each turn to isolate which component leaks the 6.66.

Usage:
    python3 tmp/dbg_m2_leak.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade, trader_wealth


def update_exchange_rate_pair(region, partner):
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


def build_ring():
    region_a = Region("A", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.753,
                                               Goods.wood: 0.110,
                                               Goods.furniture: 0.037},
                      number_of_traders=3, terrain={Goods.food: 1.6})
    region_b = Region("B", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.50,
                                               Goods.wood: 0.35,
                                               Goods.furniture: 0.05},
                      number_of_traders=3, terrain={Goods.wood: 1.6})
    region_c = Region("C", t=0, number_of_agents=200,
                      profession_distribution={Goods.food: 0.55,
                                               Goods.wood: 0.20,
                                               Goods.furniture: 0.12},
                      number_of_traders=3)
    regions = [region_a, region_b, region_c]
    for r in regions:
        for other in regions:
            if other is r:
                continue
            r.add_neighbor(other)
    for r in regions:
        for other in regions:
            if other is r:
                continue
            fx.connect_desks(r, other, t=0)
    return regions


def currency_components(regions, cur):
    """Mimic fx.audit_currency_total internals (best-effort)."""
    total = 0.0
    parts = []
    for r in regions:
        if r.home_currency == cur:
            cash = sum(a.cash for a in r.agents)
            equity = r.bank.total_deposits - r.bank.total_liabilities
            total += cash + equity
            parts.append(("home", r.name, round(cash + equity, 2)))
            parts.append(("charity", r.name, round(r.charity.agent.cash, 2)))
            total += r.charity.agent.cash
        for a in r.agents:
            w = getattr(a, 'wallets', None)
            if w and w.get(cur, 0.0):
                total += w[cur]
                parts.append(("wallet", f"{a.name()}", round(w[cur], 2)))
        for cc, bal in r.bank.foreign_reserves.items():
            if cc == cur:
                total += bal
                parts.append(("reserves", r.name, round(bal, 2)))
        total += r.bank.fx_pool
    return total, parts


def main():
    random.seed(7)
    logInit()
    regions = build_ring()
    currencies = [r.home_currency for r in regions]
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]

    for t in range(1, 244):
        before = fx.audit_currency_total(regions, "C")
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
        for r in regions:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()
        resolve_parked(regions)
        for r, other in pair_orders:
            settle_trade(t, other, r)
        fx.cycle_all_markets(regions, t)
        for r, other in pair_orders:
            update_exchange_rate_pair(r, other)
        after = fx.audit_currency_total(regions, "C")
        if t >= 243:
            print(f"T={t}: C before={before:.2f} after={after:.2f} "
                  f"delta={after-before:+.2f}")
            _, parts = currency_components(regions, "C")
            # fetch live after-state parts
            live, _ = currency_components(regions, "C")
            print("  live components sample:", parts[:12])

    print("done")


if __name__ == "__main__":
    main()
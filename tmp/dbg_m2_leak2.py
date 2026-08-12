#!/usr/bin/env python3
"""Tight instrument: rerun the gate loop for seed 7, turns 238-244, and dump
the deltas per currency + component changes of audit_currency_total for C.

Also runs once more after to check if the $6.66 leak reproduces at the same
turn (determinism check for hash-driven margins).

Usage:
    python3 tmp/dbg_m2_leak2.py
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
    desk.update(0, bank=region.bank,
                fx_regime=getattr(region.gov, 'fx_regime', 'managed'),
                ppp_target=partner_col / home_col)
    if getattr(region, 'destination_region', None) is partner:
        desk.save_rate(region)


def build_ring():
    a = Region("A", t=0, number_of_agents=200,
               profession_distribution={Goods.food: 0.753, Goods.wood: 0.110,
                                        Goods.furniture: 0.037},
               number_of_traders=3, terrain={Goods.food: 1.6})
    b = Region("B", t=0, number_of_agents=200,
               profession_distribution={Goods.food: 0.50, Goods.wood: 0.35,
                                        Goods.furniture: 0.05},
               number_of_traders=3, terrain={Goods.wood: 1.6})
    c = Region("C", t=0, number_of_agents=200,
               profession_distribution={Goods.food: 0.55, Goods.wood: 0.20,
                                        Goods.furniture: 0.12},
               number_of_traders=3)
    regions = [a, b, c]
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


def c_breakdown(regions):
    """Return the C-currency components matching audit_currency_total exactly."""
    out = {}
    for r in regions:
        if r.home_currency == 'C':
            out['chome_cash'] = sum(a.cash for a in r.agents)
            out['chome_eq'] = r.bank.total_deposits - r.bank.total_liabilities
        out['fx_pool'] = sum(r.bank.fx_pool for r in regions)
        out['charity'] = sum(r.charity.agent.cash for r in regions)
    out['wallet_C'] = 0.0
    for r in regions:
        for a in r.agents:
            w = getattr(a, 'wallets', None)
            if w:
                out['wallet_C'] += w.get('C', 0.0)
    out['reserves_C'] = 0.0
    for r in regions:
        out['reserves_C'] += r.bank.foreign_reserves.get('C', 0.0)
    return out


def run_one(label):
    random.seed(7)
    regions = build_ring()
    currencies = [r.home_currency for r in regions]
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    hits = []
    for t in range(1, 244):
        before = {cc: fx.audit_currency_total(regions, cc) for cc in currencies}
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

        if 240 <= t <= 245:
            after = {cc: fx.audit_currency_total(regions, cc) for cc in currencies}
            dC = after['C'] - before['C']
            print(f"[{label}] T={t}: dC={dC:+.2f} "
                  f"(A {after['A']-before['A']:+.2f}, "
                  f"B {after['B']-before['B']:+.2f})")
            if abs(dC) > 5.0:
                hits.append((t, dC))
                bd = c_breakdown(regions)
                print(f"    C breakdown after: {bd}")
    return hits


def main():
    logInit()
    h1 = run_one("run1")
    print("run1 hits:", h1)
    h2 = run_one("run2")
    print("run2 hits:", h2)


if __name__ == "__main__":
    main()
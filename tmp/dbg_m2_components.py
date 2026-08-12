#!/usr/bin/env python3
"""Cross-seed C-component instrumentation: run seed 42 fully, then seed 7 in
the SAME process, and at the leak turn (T=243) dump the per-component delta
of audit_currency_total for currency C.

This isolates WHICH audit line mints the +6.66 C (agents' cash, bank equity,
fx_pool, charity, foreign wallets, or foreign reserves).

Usage:
    python3 tmp/dbg_m2_components.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade


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
    """Return the C-audit components matching audit_currency_total exactly,
    keyed by the audit source lines."""
    out = {}
    # r.home_currency == 'C' branch
    for r in regions:
        if r.home_currency == 'C':
            out.setdefault('C_home_agents_cash', 0.0)
            out['C_home_agents_cash'] += sum(a.cash for a in r.agents)
            out['C_bank_equity'] = r.bank.total_deposits - r.bank.total_liabilities
            out['C_fx_pool'] = r.bank.fx_pool
            out['C_charity_cash'] = (r.charity.agent.cash
                                     if getattr(r, 'charity', None) is not None else 0.0)
    # foreign wallets + reserves across ALL regions
    wallet = 0.0
    for r in regions:
        for a in r.agents:
            w = getattr(a, 'wallets', None)
            if w:
                wallet += w.get('C', 0.0)
    out['wallet_C_all'] = wallet
    reserves = 0.0
    for r in regions:
        reserves += r.bank.foreign_reserves.get('C', 0.0)
    out['reserves_C_all'] = reserves
    return out


def run_ring(seed, start=1, stop=301, watch=None):
    """Run one ring seed; at each *watch* turn print per-component C delta."""
    random.seed(seed)
    regions = build_ring()
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    for t in range(start, stop):
        if watch is not None and t in watch:
            before_components = c_breakdown(regions)
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
        if watch is not None and t in watch:
            after_components = c_breakdown(regions)
            dC_before = sum(before_components.values())
            dC_after = sum(after_components.values())
            print(f"[seed={seed}] T={t}: total C delta = {dC_after - dC_before:+.4f}")
            for k in sorted(before_components):
                d = after_components[k] - before_components[k]
                marker = "  <-- MINT" if abs(d) > 0.01 else ""
                print(f"    {k:22s} {before_components[k]:12.4f} -> "
                      f"{after_components[k]:12.4f}  (d={d:+.4f}){marker}")


def main():
    logInit()
    watch = {243}
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch=watch)          # seed 7 in same process


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Prove cross-seed contamination: run seed 42's full 300t ring, then seed 7's
turns 240-245 in the SAME process, printing per-turn C deltas.

If seed 7 is clean standalone but leaks when run after seed 42, M2 introduced
shared module state that persists between run_seed calls (the behavior_drift
gate runs all seeds in one process).

Usage:
    python3 tmp/dbg_m2_crossseed.py
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


def run_ring(seed, start=1, stop=301, track=None):
    """Run one ring seed; return list of (t, dC) matching *track* turns."""
    random.seed(seed)
    regions = build_ring()
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    hits = []
    for t in range(start, stop):
        before = {cc: fx.audit_currency_total(regions, cc)
                  for cc in ('A', 'B', 'C')}
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
        after = {cc: fx.audit_currency_total(regions, cc)
                 for cc in ('A', 'B', 'C')}
        dC = after['C'] - before['C']
        if track is not None and t in track:
            hits.append((t, dC))
    return hits


def main():
    logInit()
    track = set(range(240, 246))
    # Seed 42 first (as in the gate), full 300 turns.
    hits42 = run_ring(42, 1, 301, track=track)
    print("seed42 (after 42 full run) 240-245 dC:", hits42)
    # Then seed 7 in the SAME process.
    hits7 = run_ring(7, 1, 301, track=track)
    print("seed7  (after seed42)      240-245 dC:", hits7)


if __name__ == "__main__":
    main()
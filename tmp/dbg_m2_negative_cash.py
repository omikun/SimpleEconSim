#!/usr/bin/env python3
"""Detect the FIRST moment any agent's cash goes negative in the contaminated
cross-seed run (seed 42 then seed 7 in one process), with traceback.

Patches Agent.cash into a logging property: when a store makes cash < 0,
prints the store location with a traceback to the calling frame (one line).

Usage:
    python3 tmp/dbg_m2_negative_cash.py
"""

import os
import random
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from agent import Agent
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade

# ---- Patch Agent.cash into a logging property ----
_CASH_BACKING = '_cash_value'
_FIRED = [False]


def _get_cash(self):
    return getattr(self, _CASH_BACKING, 0.0)


def _set_cash(self, value):
    old = getattr(self, _CASH_BACKING, 0.0)
    if value < 0 and old >= 0 and not _FIRED[0]:
        _FIRED[0] = True
        # Find the caller frame that did the store
        stack = traceback.extract_stack(limit=8)
        print("=== NEGATIVE CASH SET ===")
        print(f"agent {self.id} cash {old:.4f} -> {value:.4f}")
        for fr in stack[-7:-1]:
            print(f"  {fr.filename.split('/')[-1]}:{fr.lineno} in {fr.name}: {fr.line}")
    setattr(self, _CASH_BACKING, value)


Agent.cash = property(_get_cash, _set_cash)


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


def run_ring(seed, start=1, stop=301):
    random.seed(seed)
    regions = build_ring()
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    for t in range(start, stop):
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
            if _FIRED[0]:
                print(f"  (negative cash set during region {r.name} step at T={t})")
                return
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


def main():
    logInit()
    run_ring(42, 1, 301)
    if _FIRED[0]:
        print("(fired during seed 42)")
        return
    print("--- seed 42 clean; running seed 7 in same process ---")
    run_ring(7, 1, 301)
    if not _FIRED[0]:
        print("NO negative cash observed in seed 7 either (unexpected)")


if __name__ == "__main__":
    main()
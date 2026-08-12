#!/usr/bin/env python3
"""Find the FIRST turn and phase where ANY agent's cash goes negative in the
contaminated cross-seed run (seed 42 then seed 7 in one process).

Checks every region at: turn start, after _produce, after _trade, after
tax (all inside the patched _audit_cash checkpoints), plus end-of-day.

Usage:
    python3 tmp/dbg_m2_first_neg.py
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

_FIRST = {'t': None, 'region': None, 'label': None, 'id': None, 'val': None}


def patched_audit_cash(self, t, label):
    neg = [a for a in self.agents if a.cash < 0]
    if neg and _FIRST['t'] is None:
        _FIRST['t'] = t
        _FIRST['region'] = self.name
        _FIRST['label'] = label
        _FIRST['id'] = neg[0].id
        _FIRST['val'] = neg[0].cash


Region._audit_cash = patched_audit_cash


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
            if _FIRST['t'] is not None:
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
    if _FIRST['t'] is not None:
        print(f"FIRST negative during seed 42 at T={_FIRST['t']} "
              f"region={_FIRST['region']} stage={_FIRST['label']} "
              f"agent={_FIRST['id']} cash={_FIRST['val']:.4f}")
        return
    print("--- seed 42 clean; running seed 7 in same process ---")
    run_ring(7, 1, 301)
    if _FIRST['t'] is None:
        print("NO negative cash observed in seed 7 either (unexpected)")
    else:
        print(f"FIRST negative in seed 7 at T={_FIRST['t']} "
              f"region={_FIRST['region']} stage={_FIRST['label']} "
              f"agent={_FIRST['id']} cash={_FIRST['val']:.4f}")


if __name__ == "__main__":
    main()
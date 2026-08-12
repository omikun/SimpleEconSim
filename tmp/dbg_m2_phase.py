#!/usr/bin/env python3
"""Narrow WHICH turn phase mints the C +6.66 in the cross-seed leak.

Runs seed 42 fully, then seed 7 in the SAME process, and at T=243..247
audits currency C after EVERY sub-phase of the turn:
    before -> after r.step -> after routes -> after resolve_parked
           -> after settle_trade -> after fx.cycle -> after desk update

The phase with the >5.0 jump (or the jump that does not reverse) is the mint.

Usage:
    python3 tmp/dbg_m2_phase.py
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


def audit_C(regions):
    return fx.audit_currency_total(regions, 'C')


def run_ring(seed, start=1, stop=301, watch=None):
    random.seed(seed)
    regions = build_ring()
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    for t in range(start, stop):
        if watch is not None and t in watch:
            marks = [('start', audit_C(regions))]
        for r in regions:
            pending = {}
            for other in regions:
                if other is r:
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}
        if watch is not None and t in watch:
            marks.append(('post_pending', audit_C(regions)))
        for r in regions:
            r.step(t)
        if watch is not None and t in watch:
            marks.append(('post_step   ', audit_C(regions)))
        for r in regions:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()
        if watch is not None and t in watch:
            marks.append(('post_routes ', audit_C(regions)))
        resolve_parked(regions)
        if watch is not None and t in watch:
            marks.append(('post_resolve', audit_C(regions)))
        for r, other in pair_orders:
            settle_trade(t, other, r)
        if watch is not None and t in watch:
            marks.append(('post_settle ', audit_C(regions)))
        fx.cycle_all_markets(regions, t)
        if watch is not None and t in watch:
            marks.append(('post_fx     ', audit_C(regions)))
        for r, other in pair_orders:
            update_exchange_rate_pair(r, other)
        if watch is not None and t in watch:
            marks.append(('post_desk   ', audit_C(regions)))
            print(f"[seed={seed}] T={t}:")
            prev = None
            for name, val in marks:
                d = 0.0 if prev is None else val - prev
                flag = "  <<< JUMP" if abs(d) > 5.0 else ""
                print(f"    {name}: C = {val:14.4f}  (d={d:+.4f}){flag}")
                prev = val
            # unrest events at this turn, if any
            for r in regions:
                if getattr(r, 'unrest_log', None):
                    last = r.unrest_log[-1] if r.unrest_log else {}
                    if last.get('stage', 'calm') != 'calm':
                        print(f"    unrest[{r.name}] last event: {last}")


def main():
    logInit()
    watch = set(range(243, 248))
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch=watch)


if __name__ == "__main__":
    main()
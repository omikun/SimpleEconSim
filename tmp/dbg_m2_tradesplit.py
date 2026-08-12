#!/usr/bin/env python3
"""Split the produce_done -> trade_done window: instrument _trade and
_post_exports_to_route separately with global C-currency audits, in the
cross-seed setup (seed 42 then seed 7 in one process).  Pinpoints whether
the +6.6553 mint is inside Region._trade or Region._post_exports_to_route.

Usage:
    python3 tmp/dbg_m2_tradesplit.py
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

_G = {'regions': None, 'rec': {}}

_ORIG_TRADE = Region._trade
_ORIG_POST = Region._post_exports_to_route


def patched_trade(self, t):
    _G['rec']['pre_trade'] = fx.audit_currency_total(_G['regions'], 'C')
    ret = _ORIG_TRADE(self, t)
    _G['rec']['post_trade'] = fx.audit_currency_total(_G['regions'], 'C')
    return ret


def patched_post(self):
    _G['rec']['pre_post'] = fx.audit_currency_total(_G['regions'], 'C')
    ret = _ORIG_POST(self)
    _G['rec']['post_post'] = fx.audit_currency_total(_G['regions'], 'C')
    return ret


Region._trade = patched_trade
Region._post_exports_to_route = patched_post


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


def run_ring(seed, start=1, stop=301, watch=None):
    random.seed(seed)
    regions = build_ring()
    _G['regions'] = regions
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
            _G['rec'] = {}
            r.step(t)
            if watch is not None and t in watch:
                rec = _G['rec']
                if 'pre_trade' in rec and 'post_trade' in rec:
                    dt = rec['post_trade'] - rec['pre_trade']
                    print(f"  [{r.name}] T={t}: _trade dC = {dt:+.4f}")
                if 'pre_post' in rec and 'post_post' in rec:
                    dp = rec['post_post'] - rec['pre_post']
                    print(f"  [{r.name}] T={t}: _post_exports_to_route dC = {dp:+.4f}")
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
    watch = {243}
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch=watch)


if __name__ == "__main__":
    main()
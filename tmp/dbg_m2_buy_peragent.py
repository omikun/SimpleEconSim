#!/usr/bin/env python3
"""Inside _buy at the leak turn (C, T=243, cross-seed): snapshot each agent's
cash + C-wallet + C-reserves before/after _buy, print any account that gained
C.  Also detect aliasing: agent objects appearing in multiple regions.

Usage:
    python3 tmp/dbg_m2_buy_peragent.py
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

_G = {'regions': None, 'active': False}


def snapshot_agents(regions):
    """Return {agent_id: (cash, wallet_C)} for every agent in every region."""
    out = {}
    for r in regions:
        for a in r.agents:
            wc = 0.0
            w = getattr(a, 'wallets', None)
            if w:
                wc = w.get('C', 0.0)
            out[id(a)] = (a.cash, wc)
    return out


_ORIG_BUY = Region._buy


def patched_buy(self, t, good, price, total_asks):
    if _G['active'] and self.name == 'C':
        before = snapshot_agents(_G['regions'])
        reserves_before = sum(r.bank.foreign_reserves.get('C', 0.0)
                              for r in _G['regions'])
        ret = _ORIG_BUY(self, t, good, price, total_asks)
        after = snapshot_agents(_G['regions'])
        reserves_after = sum(r.bank.foreign_reserves.get('C', 0.0)
                             for r in _G['regions'])
        print(f"  _buy(good={good.name!r}, price={price}, asks={total_asks}) "
              f"returns bought={ret[0]}, cash_spent={ret[1]:.4f}")
        print(f"  reserves_C delta = {reserves_after - reserves_before:+.6f}")
        for aid in after:
            cb, wb = before[aid]
            ca, wa = after[aid]
            if abs(ca - cb) > 0.0001 or abs(wa - wb) > 0.0001:
                print(f"    agent@{aid}: cash {cb:+.4f} -> {ca:+.4f} "
                      f"(d={ca-cb:+.4f})  walletC {wb:+.6f} -> {wa:+.6f}")
        return ret
    return _ORIG_BUY(self, t, good, price, total_asks)


Region._buy = patched_buy


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
        _G['active'] = watch is not None and t in watch
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


def main():
    logInit()
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch={243})


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Verify whether PayDepositInterest drives a bank's total_deposits negative
before the seed-1337 T=293 death write-down (gate seed order 42, 7, 1337).

Patches Bank.PayDepositInterest to log (turn, region, deposits before/after)
and capture the FIRST time it leaves total_deposits < 0, stopping early.

Usage:
    python3 tmp/probe_interest_dep.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
import econsim_trade_money as etm
from world_trade import pending_imports, resolve_parked, settle_trade

SEEDS = (42, 7, 1337)
TURNS = 300

_FOUND = {'hit': False}


_ORIG_INTEREST = etm.Bank.PayDepositInterest


def patched_interest(self, agents):
    before = self.total_deposits
    payout = _ORIG_INTEREST(self, agents)
    after = self.total_deposits
    if after < 0 and not _FOUND['hit']:
        _FOUND['hit'] = True
        _FOUND['t'] = getattr(self, '_cur_t', '?')
        _FOUND['region'] = getattr(self, '_cur_r', '?')
        _FOUND['before'] = before
        _FOUND['payout'] = payout
        _FOUND['after'] = after
        _FOUND['liab'] = self.total_liabilities
    return payout


etm.Bank.PayDepositInterest = patched_interest


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


def run_ring(seed, turns):
    random.seed(seed)
    regions = build_ring()
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    for t in range(1, turns + 1):
        for r in regions:
            r.bank._cur_t = t
            r.bank._cur_r = r.name
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
            if _FOUND['hit']:
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
    for seed in SEEDS:
        print(f"--- seed {seed} ---")
        run_ring(seed, TURNS)
        if _FOUND['hit']:
            break
    if _FOUND['hit']:
        f = _FOUND
        print(f"FIRST PayDepositInterest pushing deposits<0: "
              f"t={f['t']} region={f['region']} "
              f"dep_before={f['before']:.4f} payout={f['payout']:.4f} "
              f"dep_after={f['after']:.4f} liab={f['liab']:.4f}")
    else:
        print("No PayDepositInterest pushed deposits below zero in gate order")


if __name__ == "__main__":
    main()
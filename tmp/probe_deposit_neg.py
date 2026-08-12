#!/usr/bin/env python3
"""Find the FIRST turn any region bank's total_deposits goes negative, running
the exact M1-gate seed sequence (42, 7, 1337) in ONE process.

Prints, for each region, every turn in [first_neg_turn-1, first_neg_turn]:
  - bank.total_deposits / total_liabilities / fx_pool
  - count of agents with negative cash (and the most-negative value)
  - PayDepositInterest payout that turn (recomputed) vs deposits

Usage:
    python3 tmp/probe_deposit_neg.py
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

SEEDS = (42, 7, 1337)
TURNS = 300

_WATCH = {'first_neg': {}}   # region name -> first turn deposits < 0 (lazy)


def check_banks(regions, t, seed):
    for r in regions:
        if _WATCH['first_neg'].get(r.name) is not None:
            continue
        dep = r.bank.total_deposits
        if dep < 0:
            _WATCH['first_neg'][r.name] = t
            neg_agents = [a.cash for a in r.agents if a.cash < 0]
            print(f"[seed={seed}] T={t} region={r.name} "
                  f"FIRST total_deposits<0: dep={dep:.4f} "
                  f"liab={r.bank.total_liabilities:.4f} "
                  f"fx_pool={r.bank.fx_pool:.4f} "
                  f"neg_cash_agents={len(neg_agents)} "
                  f"min_cash={min(neg_agents) if neg_agents else 0.0:.4f}")


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
            check_banks(regions, t, seed)
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
    return regions


def main():
    logInit()
    for seed in SEEDS:
        print(f"--- seed {seed} ---")
        try:
            run_ring(seed, TURNS)
        except RuntimeError as exc:
            print(f"seed {seed}: RUNTIME ERROR: {exc}")
            break
    print("\nfirst-negative-deposits summary:")
    for name, t in _WATCH['first_neg'].items():
        print(f"  region {name}: first total_deposits<0 at T={t}")


if __name__ == "__main__":
    main()
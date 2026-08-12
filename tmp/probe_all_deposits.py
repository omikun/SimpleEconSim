#!/usr/bin/env python3
"""Find EVERY mutation of bank.total_deposits that pushes it below zero, across
the M1-gate seed order (42, 7, 1337) in ONE process.

Wraps the Bank methods that mutate total_deposits AND the direct assignments
inside econsim_live (death write-down / inheritance bailouts) via a patched
Bank.total_deposits property that logs the first negative crossing with a
traceback snippet (first 2 caller frames).

Usage:
    python3 tmp/probe_all_deposits.py
"""

import os
import random
import sys
import traceback

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
_DIVERGED = {'hit': False}

#: Bank.__init__ seeds total_deposits with this base (no matching deposits
#: dict entry) — sum(deposits) + base == total_deposits is the invariant.
DEPOSIT_BASE = 2000.0

_DEP_BACKING = '_total_deposits_value'
_cur = {'t': '?', 'region': '?'}


def _get_deposits(self):
    return getattr(self, _DEP_BACKING, 0.0)


def _set_deposits(self, value):
    old = getattr(self, _DEP_BACKING, 0.0)
    if value < 0 and old >= 0 and not _FOUND['hit']:
        _FOUND['hit'] = True
        _FOUND['t'] = _cur['t']
        _FOUND['region'] = _cur['region']
        _FOUND['old'] = old
        _FOUND['new'] = value
        stack = traceback.extract_stack(limit=10)
        _FOUND['frames'] = [(fr.filename.split('/')[-1], fr.lineno, fr.name, fr.line)
                            for fr in stack[-8:-2]]
        # Print immediately (flushed) so it survives an unwound exception.
        print(f"!! total_deposits <0 crossing: t={_cur['t']} region={_cur['region']} "
              f"old={old:.4f} new={value:.4f}", flush=True)
        for fn, ln, nm, line in _FOUND['frames']:
            print(f"    {fn}:{ln} in {nm}: {line}", flush=True)
    setattr(self, _DEP_BACKING, value)


etm.Bank.total_deposits = property(_get_deposits, _set_deposits)


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
            _cur['t'] = t
            _cur['region'] = r.name
            pending = {}
            for other in regions:
                if other is r:
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}
        for r in regions:
            try:
                r.step(t)
            except RuntimeError:
                # Print current bank ledgers before the unwound exception.
                print(f"!! RuntimeError at seed={seed} T={t} reg={r.name}: "
                      f"total_deposits={r.bank.total_deposits:.4f} "
                      f"sum_deposits_dict={sum(r.bank.deposits.values()):.4f} "
                      f"liab={r.bank.total_liabilities:.4f}",
                      flush=True)
                raise
            # Phantom-deposit drift: per-agent dict vs scalar total, accounting
            # for the bank's 2000 deposit base.  Track the FIRST turn the gap
            # changes (a real ledger drift).
            sum_dict = sum(r.bank.deposits.values())
            gap = abs(sum_dict + DEPOSIT_BASE - r.bank.total_deposits)
            if gap > 0.01 and not _DIVERGED['hit']:
                _DIVERGED['hit'] = True
                _DIVERGED['seed'] = seed
                _DIVERGED['t'] = t
                _DIVERGED['region'] = r.name
                _DIVERGED['sum_dict'] = sum_dict
                _DIVERGED['total_deposits'] = r.bank.total_deposits
                print(f"!! PHANTOM-DEPOSIT DRIFT: seed={seed} T={t} "
                      f"reg={r.name} sum(deposits)={sum_dict:.4f} "
                      f"total_deposits={r.bank.total_deposits:.4f} "
                      f"(gap {gap:.4f})", flush=True)
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
    if _DIVERGED['hit']:
        d = _DIVERGED
        print(f"PHANTOM-DEPOSIT DRIFT first: seed={d['seed']} T={d['t']} "
              f"region={d['region']} sum(deposits)={d['sum_dict']:.4f} "
              f"total_deposits={d['total_deposits']:.4f}")
    if _FOUND['hit']:
        f = _FOUND
        print(f"FIRST total_deposits < 0: t={f['t']} region={f['region']} "
              f"old={f['old']:.4f} new={f['new']:.4f}")
        for fn, ln, nm, line in f['frames']:
            print(f"    {fn}:{ln} in {nm}: {line}")
    if not _FOUND['hit'] and not _DIVERGED['hit']:
        print("No crossing or drift observed in gate order")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Wrap every cash-touching sub-call inside Region._trade with a global-C
snapshot, in the cross-seed setup (seed 42 then seed 7 in one process).
Pinpoints WHICH call mints the +6.6553 C at T=243.

Usage:
    python3 tmp/dbg_m2_trade_calls.py
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

_G = {'regions': None, 'watch_region': None, 'watch_t': -1, 'hits': []}


def label_C(label, before):
    if _G['watch_region'] is None:
        return
    after = fx.audit_currency_total(_G['regions'], 'C')
    d = after - before
    if abs(d) > 0.001:
        _G['hits'].append(f"    {label}: dC = {d:+.4f}")


def wrap(name, fn):
    def wrapper(*args, **kwargs):
        before = fx.audit_currency_total(_G['regions'], 'C') if _G['watch_region'] is not None else 0.0
        ret = fn(*args, **kwargs)
        if _G['watch_region'] is not None:
            label_C(name, before)
        return ret
    wrapper.__name__ = f"wrapped_{name}"
    return wrapper


# Region-side wraps
Region._clear_discriminatory = wrap('_clear_discriminatory', Region._clear_discriminatory)
Region._gather_import_pool = wrap('_gather_import_pool', Region._gather_import_pool)
Region._decide_borrow_deposit = wrap('_decide_borrow_deposit', Region._decide_borrow_deposit)
Region._repoint_traders = wrap('_repoint_traders', Region._repoint_traders)
Region._buy = wrap('_buy', Region._buy)
Region._sell = wrap('_sell', Region._sell)
Region._withdraw_if_needed = wrap('_withdraw_if_needed', Region._withdraw_if_needed)

# Bank-side wraps (class methods so all instances are covered)
etm.Bank.PayDepositInterest = wrap('PayDepositInterest', etm.Bank.PayDepositInterest)
etm.Bank.Borrow = wrap('Bank.Borrow', etm.Bank.Borrow)
etm.Bank.Deposit = wrap('Bank.Deposit', etm.Bank.Deposit)
etm.Bank.Withdraw = wrap('Bank.Withdraw', etm.Bank.Withdraw)

# Government wraps
from government import Government
Government.pay_for_food = wrap('gov.pay_for_food', Government.pay_for_food)
Government.bid_food = wrap('gov.bid_food', Government.bid_food)
Government.deposit_remaining = wrap('gov.deposit_remaining', Government.deposit_remaining)
Government.seal_income = wrap('gov.seal_income', Government.seal_income)

# Charity wraps (cash paths)
from charity import Charity
Charity.pay_for_food = wrap('charity.pay_for_food', Charity.pay_for_food)
Charity.bid_food = wrap('charity.bid_food', Charity.bid_food)
Charity.deposit_remaining = wrap('charity.deposit_remaining', Charity.deposit_remaining)


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
        _G['watch_region'] = None
        _G['watch_t'] = -1
        if watch is not None and t in watch:
            _G['watch_region'] = watch[0]
            _G['watch_t'] = t
            _G['hits'] = []
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
            if _G['hits']:
                print(f"[seed={seed}] T={t} region={r.name} _trade sub-call deltas:")
                for h in _G['hits']:
                    print(h)
                _G['hits'] = []
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
    # Watch region C at T=243 (the leak turn).
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch=('C', 243))


if __name__ == "__main__":
    main()
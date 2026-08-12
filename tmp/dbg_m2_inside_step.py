#!/usr/bin/env python3
"""Instrument Region._audit_cash so each sub-phase checkpoint inside
Region.step also records the GLOBAL currency-C total.  Pinpoints the exact
internal stage of the T=243 mint (cross-seed: seed 42 then seed 7 in one
process).

Usage:
    python3 tmp/dbg_m2_inside_step.py
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

_GLOBAL_C = {}


def patched_audit_cash(self, t, label):
    # Read-only original: skip it (it only prints on anomalies) and just
    # capture the global C-currency total AND agent-cash negatives here.
    _GLOBAL_C[label] = fx.audit_currency_total(_GLOBAL_C['regions'], 'C')
    neg = [a.cash for a in self.agents if a.cash < 0]
    _GLOBAL_C[f'{label}_neg'] = (len(neg), min(neg) if neg else 0.0)


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


def run_ring(seed, start=1, stop=301, watch=None):
    random.seed(seed)
    regions = build_ring()
    _GLOBAL_C['regions'] = regions
    pair_orders = [(r, o) for r in regions for o in regions if o is not r]
    for t in range(start, stop):
        if watch is not None and t in watch:
            _GLOBAL_C.clear()
            _GLOBAL_C['regions'] = regions
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
        if watch is not None and t in watch and _GLOBAL_C:
            labels = ['step_start', 'charity_done', 'labour_done', 'produce_done',
                      'trade_done', 'wages_done', 'profits_done', 'tax_done',
                      'live_done', 'charity_food_done']
            print(f"[seed={seed}] T={t}: global C during r.step")
            prev = None
            for lbl in labels:
                if lbl not in _GLOBAL_C:
                    continue
                val = _GLOBAL_C[lbl]
                d = 0.0 if prev is None else val - prev
                flag = "  <<< JUMP" if abs(d) > 5.0 else ""
                neg_info = ""
                nkey = f"{lbl}_neg"
                if nkey in _GLOBAL_C:
                    cnt, m = _GLOBAL_C[nkey]
                    if cnt > 0:
                        neg_info = f"  [negcash x{cnt}, min={m:.4f}]"
                print(f"    {lbl:18s} C = {val:14.4f}  (d={d:+.4f}){flag}{neg_info}")
                prev = val


def main():
    logInit()
    watch = {243}
    run_ring(42, 1, 301, watch=None)          # seed 42 first (as in gate)
    print("--- after seed 42, running seed 7 in same process ---")
    run_ring(7, 1, 301, watch=watch)


if __name__ == "__main__":
    main()
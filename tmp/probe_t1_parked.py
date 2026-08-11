# T1.4 parked-goods probe (compact)
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goods import Goods
from region import Region
from logger import logInit
import forex as fx
from world_trade import pending_imports, resolve_parked, settle_trade, trader_wealth

def build():
    p = {Goods.food: 0.6, Goods.wood: 0.25, Goods.furniture: 0.08}
    def mk(n, terr=None):
        return Region(n, t=0, number_of_agents=120,
                      profession_distribution=dict(p),
                      number_of_traders=2, terrain=terr)
    a = mk("A", {Goods.food: 1.6})
    b = mk("B", {Goods.wood: 1.6})
    c = mk("C")
    for x, y in ((a, b), (b, c), (c, a)):
        x.add_neighbor(y, t=0)
        fx.connect_desks(x, y, t=0)
        y.add_neighbor(x, t=0)
        fx.connect_desks(y, x, t=0)
    regs = [a, b, c]
    for r in regs:
        r._init_trader_wealth = trader_wealth(r)
    return regs

def main():
    logInit()
    random.seed(42)
    regs = build()
    currs = [r.home_currency for r in regs]
    pairs = [(r, o) for r in regs for o in regs if o is not r]
    switches = 0
    parked = 0
    prev = {t.id: t.destination_region for r in regs for t in r.trader_agents}
    for t in range(1, 61):
        for r in regs:
            for tr in r.trader_agents:
                pv = prev.get(tr.id)
                cur = tr.destination_region
                if pv is not None and cur is not None and pv is not cur:
                    switches += 1
                prev[tr.id] = cur
        before = {c: fx.audit_currency_total(regs, c) for c in currs}
        for r in regs:
            pend = {}
            for o in regs:
                if o is r:
                    continue
                for g, es in pending_imports(r, o).items():
                    pend.setdefault(g, []).extend(es)
            r.pending_imports = pend
            r._auction_import_sales = {}
        for r in regs:
            r.step(t)
        for r in regs:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()
        resolve_parked(regs)
        for r in regs:
            for tr in r.trader_agents:
                cur = getattr(tr, 'destination_region', None)
                for reg_name, bucket in (tr.parked_foreign or {}).items():
                    if any(bucket):
                        assert cur is None or cur.name != reg_name
                        parked += 1
        for r, o in pairs:
            settle_trade(t, o, r)
        fx.cycle_all_markets(regs, t)
        for c in currs:
            d = fx.audit_currency_total(regs, c) - before[c]
            assert abs(d) <= 5.0, "T%d %s shift %.2f" % (t, c, d)
    print("switches=%d parked_checks=%d" % (switches, parked))
    assert switches > 0 and parked > 0
    print("T1 PROBE PASS")

if __name__ == "__main__":
    main()
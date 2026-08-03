"""Phase 3: instrument _run_labour sub-methods to catch the +403 creation.

Wraps _cleanup/_borrow_or_layoff/_incorporate/_hire/_adjust_wages with
per-currency audit snapshots on turn 16 in Region_A.
"""
import random
from goods import Goods
from region import Region
import forex as fx
from econsim_two_region import foreign_sell, process_transport, update_exchange_rate
import wealth_lineage, wealth_diagnostic

CUR_A = "Region_A"
random.seed(42)
rA = Region(CUR_A, 0, 55, {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = Region("Region_B", 0, 55, {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for a in rA.agents + rB.agents:
    if getattr(a, 'is_trader', False):
        a.destination_region = rB if a in rA.agents else rA
fx.connect_regions(rA, rB, 0)
wealth_lineage.init_collectors()
wealth_diagnostic.init_collectors()

REGIONS = [rA, rB]


def taxa():
    return fx.audit_currency_total(REGIONS, CUR_A)


methods = ['_run_labour', '_cleanup', '_borrow_or_layoff', '_incorporate',
           '_hire', '_adjust_wages']


def make_wrap(name):
    orig = getattr(Region, name)

    def wrapped(self, *args, **kwargs):
        before = taxa()
        rc = orig(self, *args, **kwargs)
        after = taxa()
        d = after - before
        if abs(d) > 1e-6:
            print(f"    A-{name}: dA={d:+.4f}")
        return rc

    wrapped.__name__ = name
    return wrapped


for m in methods:
    setattr(Region, m, make_wrap(m))

for t in range(1, 16):
    rA.step(t); rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB); foreign_sell(t, rB, rA)
    wealth_lineage.record_turn(t, rA, rB); wealth_diagnostic.record_turn(t, rA, rB)
    for r, o in ((rA, rB), (rB, rA)):
        r.trade_flow_log.append(0); update_exchange_rate(r)

print("--- Turn 16 labour sub-phases (Region_A) ---")
rA.step(16)
print("Done.")
"""Phase 3: per-good _buy/_sell instrument to find Region_B's remaining -20.56.

Wraps Region._buy and Region._sell to snapshot fx.audit_currency_total before
and after each good's market clear, so we see exactly which good (and whether
buyers paid more than sellers received) destroys B's home currency.
"""
import random
from collections import defaultdict
from goods import Goods
from region import Region
import forex as fx
from econsim_two_region import foreign_sell, process_transport
import wealth_lineage, wealth_diagnostic

CUR_A, CUR_B = "Region_A", "Region_B"
random.seed(42)
rA = Region(CUR_A, 0, 55, {Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = Region(CUR_B, 0, 55, {Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
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

def total():
    return fx.audit_currency_total(REGIONS, CUR_B)

_orig_buy = Region._buy
_orig_sell = Region._sell

def _w_buy(self, t, good, price, total_asks):
    before = total()
    res = _orig_buy(self, t, good, price, total_asks)
    after = total()
    if abs(after - before) > 1e-6:
        print(f"  [{self.name}][_buy {good.name}] net={after-before:+.4f} "
              f"(asks={total_asks}, bought={res[0]}, cash={res[1]:.2f})")
    return res

def _w_sell(self, askers, good, price, t, total_bought, total_cash_purchases):
    before = total()
    res = _orig_sell(self, askers, good, price, t, total_bought, total_cash_purchases)
    after = total()
    if abs(after - before) > 1e-6:
        print(f"  [{self.name}][_sell {good.name}] net={after-before:+.4f}")
    return res

Region._buy = _w_buy
Region._sell = _w_sell

for t in range(1, 13):
    rA.step(t); rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB); foreign_sell(t, rB, rA)
    wealth_lineage.record_turn(t, rA, rB); wealth_diagnostic.record_turn(t, rA, rB)
    for r in (rA, rB):
        r.forex.update(t, bank=r.bank, fx_regime='managed')
        r.forex.save_rate(r)

print("--- Warmup done; Region_B step 13 market clears ---")
rB.step(13)
print("--- Region_A step 13 market clears ---")
rA.step(13)
print("Done.")
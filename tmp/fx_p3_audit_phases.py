"""Phase 3: intra-step per-phase attribution using _audit_cash hooks.

Patches Region._audit_cash to also snapshot fx.audit_currency_total at every
phase boundary inside step(), so we see exactly which sub-phase destroys/
creates money in turn 13 for each region.
"""
import random
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
_last = {'a': None, 'b': None}

_orig_audit = Region._audit_cash


def _phase_audit(self, t, label):
    _orig_audit(self, t, label)
    na = fx.audit_currency_total(REGIONS, CUR_A)
    nb = fx.audit_currency_total(REGIONS, CUR_B)
    dA = (na - _last['a']) if _last['a'] is not None else 0.0
    dB = (nb - _last['b']) if _last['b'] is not None else 0.0
    _last['a'], _last['b'] = na, nb
    if abs(dA) > 1e-6 or abs(dB) > 1e-6:
        print(f"      [{self.name}][{label}] dA={dA:+9.4f} dB={dB:+9.4f}")


Region._audit_cash = _phase_audit

for t in range(1, 13):
    rA.step(t); rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB); foreign_sell(t, rB, rA)
    wealth_lineage.record_turn(t, rA, rB); wealth_diagnostic.record_turn(t, rA, rB)
    for r in (rA, rB):
        r.forex.update(t, bank=r.bank, fx_regime='managed')
        r.forex.save_rate(r)

# Reset snapshots, then step 13 with phase attribution
rA._audit_cash(13, 'pre-step-A')
rB._audit_cash(13, 'pre-step-B')
print("--- Region_A step 13 phases ---")
rA.step(13)
print("--- Region_B step 13 phases ---")
rB.step(13)
print("Done.")
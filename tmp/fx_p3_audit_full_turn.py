"""Phase 3: find the +403 money-creation at T=16 in the FULL sim.

Runs the exact main-loop sequence (step/transport/foreign_sell/fx update) with
the _audit_cash phaser attached, printing per-phase per-currency deltas for
turns 15->16 and 19->20 to catch where Region_A creates +403 and Region_B +81.
"""
import random
from goods import Goods
from region import Region
import forex as fx
from econsim_two_region import foreign_sell, process_transport, update_exchange_rate
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
_last = {'A': None, 'B': None}

_orig_audit = Region._audit_cash


def _track(self, t, label):
    _orig_audit(self, t, label)
    na = fx.audit_currency_total(REGIONS, CUR_A)
    nb = fx.audit_currency_total(REGIONS, CUR_B)
    dA = (na - _last['A']) if _last['A'] is not None else 0.0
    dB = (nb - _last['B']) if _last['B'] is not None else 0.0
    _last['A'], _last['B'] = na, nb
    if abs(dA) > 1e-6 or abs(dB) > 1e-6:
        print(f"  [{self.name}][{label:>18}] dA={dA:+9.4f} dB={dB:+9.4f}")


Region._audit_cash = _track


def run_turn(t):
    print(f"--- Turn {t} ---")
    rA._audit_cash(t, 'pre-step'); rB._audit_cash(t, 'pre-step')
    rA.step(t); rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB); foreign_sell(t, rB, rA)
    wealth_lineage.record_turn(t, rA, rB); wealth_diagnostic.record_turn(t, rA, rB)
    for r, o in ((rA, rB), (rB, rA)):
        turn_export = sum(r.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if r.export_val[g])
        turn_import = sum(r.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if r.import_val[g])
        r.cumulative_trade_balance += (turn_export - turn_import)
        r.trade_flow_log.append(turn_export - turn_import)
        update_exchange_rate(r)
    rA._audit_cash(t, 'fx-updated'); rB._audit_cash(t, 'fx-updated')


for t in range(1, 15):
    run_turn(t)
# Fresh snapshot before turn 15-16 boundary
rA._audit_cash(15, 'pre-boundary'); rB._audit_cash(15, 'pre-boundary')
run_turn(15)
run_turn(16)
for t in range(17, 20):
    run_turn(t)
print("Done.")
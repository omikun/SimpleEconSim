"""Phase 3 step 1: extended conservation audit — per-phase attribution.

Recomputes fx.audit_currency_total (the exact quantity the sim's SUPPLY SHIFT
checks use) before/after each phase of a representative leaky turn so we can
attribute the -178 to a specific phase: A.step / B.step / transport /
foreign_sell / fx update.  Also instruments _handle_debt_inheritance to print
every forgiveness event (R, D, bailout, write_down) so we can tie the leak to
specific deaths.
"""
import random
from goods import Goods
from region import Region
import forex as fx
from econsim_two_region import foreign_sell, process_transport
import wealth_lineage, wealth_diagnostic
import econsim_live as live

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
STATE = {'a': fx.audit_currency_total(REGIONS, CUR_A),
         'b': fx.audit_currency_total(REGIONS, CUR_B)}


def mark(label):
    """Print combined per-currency delta since the last mark."""
    na = fx.audit_currency_total(REGIONS, CUR_A)
    nb = fx.audit_currency_total(REGIONS, CUR_B)
    dA = na - STATE['a']
    dB = nb - STATE['b']
    STATE['a'], STATE['b'] = na, nb
    print(f"  {label:>14}  dA={dA:+9.4f}  dB={dB:+9.4f}")


# ---- Instrument debt inheritance to print forgiveness events ----
_orig_debt = live._handle_debt_inheritance


def _tracked_debt(ctx, t, agent, living_descendants):
    b = ctx.bank
    R0 = sum((l.principle - l.principle_paid) + l.getInterest() for l in agent.loans)
    D0 = b.total_deposits
    rc = _orig_debt(ctx, t, agent, living_descendants)
    RD = sum(l.principle - l.principle_paid for l in agent.loans)
    D1 = b.total_deposits
    L1 = b.total_liabilities
    # R0 = full outstanding incl interest; RD = remaining principle after payment
    print(f"      [debt] agent#{agent.id} alive={agent.alive} loans_before={len(agent.loans)} "
          f"outstanding={R0:.2f} remaining_principle={RD:.2f} D:{D0:.2f}->{D1:.2f} "
          f"liab={L1:.2f} heirs={len(living_descendants)}")
    return rc


live._handle_debt_inheritance = _tracked_debt

print("Warmup turns 1-12...")
for t in range(1, 13):
    rA.step(t); rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB); foreign_sell(t, rB, rA)
    wealth_lineage.record_turn(t, rA, rB); wealth_diagnostic.record_turn(t, rA, rB)
    for r in (rA, rB):
        r.forex.update(t, bank=r.bank, fx_regime='managed')
        r.forex.save_rate(r)

print("Turn 13 per-phase attribution:")
mark("baseline")
rA.step(13)
mark("A.step")
rB.step(13)
mark("B.step")
process_transport(13, rA, rB)
mark("transport")
foreign_sell(13, rA, rB); foreign_sell(13, rB, rA)
mark("foreign_sell")
for r in (rA, rB):
    r.forex.update(13, bank=r.bank, fx_regime='managed')
    r.forex.save_rate(r)
mark("fx update")
print("\nDone.")
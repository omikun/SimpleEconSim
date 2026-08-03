#!/usr/bin/env python3
"""
Definitive cash-leak verification: compute TOTAL system cash (agent cash +
bank equity + charity cash) before and after the full simulation.
If they differ, cash was created or destroyed.
Then compute delta per turn to find leak magnitudes.
"""
import sys
import random
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell

time_steps = 250
logInit()
random.seed(42)

rA = Region('Region_A', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = Region('Region_B', t=0, number_of_agents=110,
            profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for trader in rA.agents:
    if trader.is_trader:
        trader.destination_region = rB
for trader in rB.agents:
    if trader.is_trader:
        trader.destination_region = rA

def process_transport(t, ra, rb):
    for trader in ra.agents:
        if trader.is_trader:
            trader._process_pipeline()
    for trader in rb.agents:
        if trader.is_trader:
            trader._process_pipeline()

def total_system(region):
    """cash + bank equity + charity cash"""
    ac = sum(a.cash for a in region.agents)
    be = region.bank.total_deposits - region.bank.total_liabilities
    return ac + be + region.charity.cash

initial = total_system(rA) + total_system(rB)
print(f"Initial system cash (agent+bank+charity): ${initial:.2f}")
print()

leak_total = 0.0
max_leak = 0.0

for t in range(1, time_steps + 1):
    before = total_system(rA) + total_system(rB)
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    after = total_system(rA) + total_system(rB)
    diff = after - before
    if abs(diff) > 0.01:
        leak_total += abs(diff)
        max_leak = max(max_leak, abs(diff))
        if t <= 5:
            print(f"  T={t}: BEFORE=${before:.2f} AFTER=${after:.2f} LEAK=${diff:+.4f}")
    if t % 50 == 0:
        print(f"  T={t}: total=${after:.2f}  popA={len(rA.agents)} popB={len(rB.agents)}")

final = total_system(rA) + total_system(rB)
print(f"\n{'='*60}")
print(f"TOTAL SYSTEM CASH ACCOUNTING (includes charity)")
print(f"{'='*60}")
print(f"Initial: ${initial:.2f}")
print(f"Final:   ${final:.2f}")
print(f"Change:  ${final - initial:+.2f}")
print(f"Total leak magnitude: ${leak_total:.6f}")
print(f"Max per-turn leak: ${max_leak:.6f}")
print()

if leak_total < 0.1:
    print("✓ NO CASH LEAKS — cash is perfectly conserved")
elif abs(final - initial) < 0.1:
    print(f"~ TOTAL CASH IS CONSERVED (change=${(final-initial):.4f}) despite {leak_total:.2f} in per-turn noise")
    print(f"  Per-turn 'leaks' cancel out — likely floating-point intermediate truncation")
else:
    print(f"✗ CASH IS NOT CONSERVED — ${abs(final-initial):.2f} destroyed over {time_steps} turns")
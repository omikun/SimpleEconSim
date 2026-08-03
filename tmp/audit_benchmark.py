#!/usr/bin/env python3
"""Run benchmark with cash-flow auditor enabled."""
import time
import sys
sys.path.insert(0, '.')

import region
from goods import Goods
from logger import logInit
import random
from econsim_two_region import foreign_sell

from cash_auditor import install_auditor, start_turn, end_turn, audit_report
install_auditor()

time_steps = 250
logInit()
random.seed(42)

rA = region.Region('Region_A', t=0, number_of_agents=110,
                    profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = region.Region('Region_B', t=0, number_of_agents=110,
                    profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for trader in rA.agents:
    if trader.is_trader: trader.destination_region = rB
for trader in rB.agents:
    if trader.is_trader: trader.destination_region = rA

def process_transport(t, rA, rB):
    for trader in rA.agents:
        if trader.is_trader: trader._process_pipeline()
    for trader in rB.agents:
        if trader.is_trader: trader._process_pipeline()

total_leak = 0.0
max_leak = 0.0
leaky_count = 0

t0 = time.time()
for t in range(1, time_steps + 1):
    start_turn()
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    entry = end_turn()
    leak = abs(entry['net_system_cash'])
    if leak > 0.01:
        total_leak += leak
        max_leak = max(max_leak, leak)
        leaky_count += 1
        if t <= 5 or t % 50 == 0:
            print(f"  T={t}: LEAK ${leak:.6f}  (mutations={entry['mutations']})")
    if t % 50 == 0:
        print(f'  T={t}')
t1 = time.time()

print(f'\nSim only ({time_steps} cycles): {t1-t0:.3f}s')
print(f'Leaky turns: {leaky_count}/{time_steps}')
print(f'Total leak: ${total_leak:.6f}  Max leak: ${max_leak:.6f}')

if leaky_count > 0 and total_leak > 0.01:
    print("\nDetailed leak report follows:")
    audit_report()
else:
    print("\nNO SIGNIFICANT LEAKS DETECTED — all cash-flow mutations are self-consistent!")
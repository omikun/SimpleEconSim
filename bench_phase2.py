#!/usr/bin/env python3
"""Benchmark Phase 2: cached random optimization."""
import random
import sys
import time
sys.path.insert(0, '.')
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import region as _r

logInit()
random.seed(42)

rA = _r.Region('Region_A', t=0, number_of_agents=110,
               profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
rB = _r.Region('Region_B', t=0, number_of_agents=110,
               profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})
rA.recipes[Goods.food]['production'] *= 2
rB.recipes[Goods.wood]['production'] *= 2
rA.destination_region = rB
rB.destination_region = rA
for trader in rA.agents:
    if trader.is_trader: trader.destination_region = rB
for trader in rB.agents:
    if trader.is_trader: trader.destination_region = rA

def process_transport(t, ra, rb):
    for trader in ra.agents:
        if trader.is_trader: trader._process_pipeline()
    for trader in rb.agents:
        if trader.is_trader: trader._process_pipeline()

time_steps = 50
t0 = time.time()
for t in range(1, time_steps + 1):
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
t1 = time.time()
print(f'Phase 2 cached random ({time_steps} cycles): {t1-t0:.3f}s')
print(f'Per-turn: {(t1-t0)/time_steps:.4f}s')
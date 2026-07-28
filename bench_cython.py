#!/usr/bin/env python3
"""Benchmark 150 cycles with and without Cython."""
import random
import sys
import time
import os

sys.path.insert(0, '.')
from goods import Goods
from logger import logInit

TIME_STEPS = 150
SEED = 42

def run_bench(label, time_steps=TIME_STEPS):
    import econsim_two_region as _tr
    import region as _r
    from random_cache import rand as _rand
    random.seed(SEED)
    _rand.__init__(seed=SEED)

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

    t0 = time.time()
    for t in range(1, time_steps + 1):
        rA.step(t)
        rB.step(t)
        process_transport(t, rA, rB)
        _tr.foreign_sell(t, rA, rB)
        _tr.foreign_sell(t, rB, rA)
    t1 = time.time()
    dt = t1 - t0
    print('%s (%d cycles): %.3fs  (%.1fms/turn)' % (label, time_steps, dt, (dt / time_steps) * 1000))
    return dt

# Purge cached imports
for mod in ['region', 'region_core', 'econsim_two_region']:
    sys.modules.pop(mod, None)

logInit()
t_cython = run_bench('WITH Cython')

# Hide .so file
so_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'region_core.cpython-313-darwin.so')
backup_path = so_path + '.bak'
if os.path.exists(so_path):
    os.rename(so_path, backup_path)

for mod in ['region', 'region_core', 'econsim_two_region']:
    sys.modules.pop(mod, None)

logInit()
t_pure = run_bench('WITHOUT Cython')

# Restore
if os.path.exists(backup_path):
    os.rename(backup_path, so_path)

print()
speedup = t_pure / t_cython if t_cython > 0 else 1.0
print('Speedup: %.2fx' % speedup)
if t_cython < t_pure:
    print('Cython saved %.3fs' % (t_pure - t_cython))
else:
    print('Cython overhead: %.3fs' % (t_cython - t_pure))
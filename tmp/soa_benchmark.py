#!/usr/bin/env python3
"""Benchmark tool to compare before/after SoA optimization."""
import time
import sys

def run_benchmark(description, time_steps=250):
    import importlib
    import region as _r
    from goods import Goods
    from logger import logInit
    from econsim_two_region import foreign_sell
    import random
    
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
    
    t0 = time.time()
    for t in range(1, time_steps + 1):
        rA.step(t)
        rB.step(t)
        process_transport(t, rA, rB)
        foreign_sell(t, rA, rB)
        foreign_sell(t, rB, rA)
        if t % 50 == 0:
            print(f'  T={t}')
    t1 = time.time()
    print(f'{description} ({time_steps} cycles): {t1-t0:.3f}s')
    return t1 - t0

if __name__ == '__main__':
    run_benchmark('Benchmark')
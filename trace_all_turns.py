#!/usr/bin/env python3
"""
Trace first 5 turns at substep granularity to find when cash creation happens.
"""
import sys
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random

time_steps = 5
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

def snap(region):
    ac = sum(a.cash for a in region.agents)
    be = region.bank.total_deposits - region.bank.total_liabilities
    cc = region.charity.cash
    return {'ac': ac, 'be': be, 'cc': cc, 'sys': ac + be + cc, 'n': len(region.agents),
            'td': region.bank.total_deposits, 'tl': region.bank.total_liabilities}

def process_transport(t, ra, rb):
    for trader in ra.agents:
        if trader.is_trader: trader._process_pipeline()
    for trader in rb.agents:
        if trader.is_trader: trader._process_pipeline()

for t in range(1, time_steps + 1):
    # Baseline at turn start
    sA0 = snap(rA); sB0 = snap(rB)
    total0 = sA0['sys'] + sB0['sys']
    
    for a in rA.agents: a.clear_wealth_cache()
    for a in rB.agents: a.clear_wealth_cache()
    
    rA.charity.collect_donations(t, rA.agents, rA.bank)
    rB.charity.collect_donations(t, rB.agents, rB.bank)
    
    newA = rA._run_labour(t)
    newB = rB._run_labour(t)
    if newA: rA.agents.extend(newA)
    if newB: rB.agents.extend(newB)
    
    rA._produce(t); rB._produce(t)
    
    # Before trade
    sA1 = snap(rA); sB1 = snap(rB)
    total1 = sA1['sys'] + sB1['sys']
    
    rA._trade(t); rB._trade(t)
    
    # After trade
    sA2 = snap(rA); sB2 = snap(rB)
    total2 = sA2['sys'] + sB2['sys']
    
    rA._pay_wages(t); rB._pay_wages(t)
    rA._record_start(); rB._record_start()
    rA._distribute_profits(t); rB._distribute_profits(t)
    rA._record_delta(); rB._record_delta()
    
    # After wages+profits
    sA3 = snap(rA); sB3 = snap(rB)
    total3 = sA3['sys'] + sB3['sys']
    
    rA._collect_tax(t); rB._collect_tax(t)
    sA4 = snap(rA); sB4 = snap(rB)
    total4 = sA4['sys'] + sB4['sys']
    
    rA.agents = rA._live(t)
    rB.agents = rB._live(t)
    
    sA5 = snap(rA); sB5 = snap(rB)
    total5 = sA5['sys'] + sB5['sys']
    
    rA.charity.distribute_food(t, rA.agents)
    rB.charity.distribute_food(t, rB.agents)
    
    sA6 = snap(rA); sB6 = snap(rB)
    total6 = sA6['sys'] + sB6['sys']
    
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    
    sA7 = snap(rA); sB7 = snap(rB)
    total7 = sA7['sys'] + sB7['sys']
    
    print(f"T={t}: "
          f"start={total0:.2f} "
          f"pre-trade={total1:.2f}(d={total1-total0:+.4f}) "
          f"trade={total2:.2f}(d={total2-total1:+.4f}) "
          f"wage+profit={total3:.2f}(d={total3-total2:+.4f}) "
          f"tax={total4:.2f}(d={total4-total3:+.4f}) "
          f"live={total5:.2f}(d={total5-total4:+.4f}) "
          f"charity_dist={total6:.2f}(d={total6-total5:+.4f}) "
          f"foreign={total7:.2f}(d={total7-total6:+.4f}) "
          f"total_d={total7-total0:+.4f}")
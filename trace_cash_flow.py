#!/usr/bin/env python3
"""
Trace all cash-flow mutations by comparing per-turn snapshots of:
  - Agent cash (per-output sums)
  - Bank total_deposits & total_liabilities
  - Charity cash
  - Government agent cash

Prints which category is leaking each turn.
"""
import sys
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random
import math

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

def process_transport(t, ra, rb):
    for trader in ra.agents:
        if trader.is_trader:
            trader._process_pipeline()
    for trader in rb.agents:
        if trader.is_trader:
            trader._process_pipeline()

def snap(region):
    """Capture detailed cash snapshot."""
    agent_cash = sum(a.cash for a in region.agents)
    non_corp_agents = [a for a in region.agents if not a.is_corporation]
    corp_agents = [a for a in region.agents if a.is_corporation]
    traders = [a for a in region.agents if getattr(a, 'is_trader', False)]
    gov_cash = region.gov.agent.cash
    return {
        'agent_cash': agent_cash,
        'non_corp_cash': sum(a.cash for a in non_corp_agents),
        'corp_cash': sum(a.cash for a in corp_agents),
        'trader_cash': sum(a.cash for a in traders),
        'gov_cash': gov_cash,
        'td': region.bank.total_deposits,
        'tl': region.bank.total_liabilities,
        'charity_cash': region.charity.cash,
        'bank_equity': region.bank.total_deposits - region.bank.total_liabilities,
        'num_agents': len(region.agents),
        'deposits_sum': sum(region.bank.deposits.values()),
        'deposits_count': len(region.bank.deposits),
        'loans_count': len(region.bank.loans),
    }

def system_cash(s):
    """agent_cash + bank_equity + charity_cash."""
    return s['agent_cash'] + s['bank_equity'] + s['charity_cash']

# Initial snapshot at t=0
sA0 = snap(rA)
sB0 = snap(rB)
print(f"INITIAL at t=0")
print(f"  Region A: agents_cash=${sA0['agent_cash']:>8.2f} (non-corp=${sA0['non_corp_cash']:>8.2f} "
      f"corp=${sA0['corp_cash']:>8.2f} trader=${sA0['trader_cash']:>8.2f} gov=${sA0['gov_cash']:>8.2f}) "
      f"bank_equity=${sA0['bank_equity']:>8.2f} charity=${sA0['charity_cash']:>8.2f} "
      f"deposits_sum=${sA0['deposits_sum']:>8.2f}")
print(f"  Region B: agents_cash=${sB0['agent_cash']:>8.2f} (non-corp=${sB0['non_corp_cash']:>8.2f} "
      f"corp=${sB0['corp_cash']:>8.2f} trader=${sB0['trader_cash']:>8.2f} gov=${sB0['gov_cash']:>8.2f}) "
      f"bank_equity=${sB0['bank_equity']:>8.2f} charity=${sB0['charity_cash']:>8.2f} "
      f"deposits_sum=${sB0['deposits_sum']:>8.2f}")
print()

for t in range(1, time_steps + 1):
    sA_before = snap(rA)
    sB_before = snap(rB)
    sys_before = system_cash(sA_before) + system_cash(sB_before)
    
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    
    sA_after = snap(rA)
    sB_after = snap(rB)
    sys_after = system_cash(sA_after) + system_cash(sB_after)
    
    leak = sys_after - sys_before
    
    print(f"T={t}: LEAK={leak:+.6f}")
    
    # Delta decomposition
    for label, s_bef, s_aft in [('A', sA_before, sA_after), ('B', sB_before, sB_after)]:
        d_agent = s_aft['agent_cash'] - s_bef['agent_cash']
        d_corp = s_aft['corp_cash'] - s_bef['corp_cash']
        d_noncorp = s_aft['non_corp_cash'] - s_bef['non_corp_cash']
        d_trader = s_aft['trader_cash'] - s_bef['trader_cash']
        d_gov = s_aft['gov_cash'] - s_bef['gov_cash']
        d_td = s_aft['td'] - s_bef['td']
        d_tl = s_aft['tl'] - s_bef['tl']
        d_equity = s_aft['bank_equity'] - s_bef['bank_equity']
        d_charity = s_aft['charity_cash'] - s_bef['charity_cash']
        d_dep_sum = s_aft['deposits_sum'] - s_bef['deposits_sum']
        
        # Check: does total_deposits = deposits_sum + non-deposit additions?
        td_minus_dep_sum_diff = d_td - d_dep_sum
        
        contrib = d_agent + d_equity + d_charity  # should equal REGIONAL portion of leak
        
        print(f"  Region {label}: agents={d_agent:+.2f} "
              f"(noncorp={d_noncorp:+.2f} corp={d_corp:+.2f} trader={d_trader:+.2f} gov={d_gov:+.2f}) "
              f"equity={d_equity:+.2f} (td={d_td:+.2f} tl={d_tl:+.2f}) "
              f"charity={d_charity:+.2f}  "
              f"deps_sum_delta={d_dep_sum:+.2f}  td-deps_diff={td_minus_dep_sum_diff:+.2f}  "
              f"contrib={contrib:+.2f}")
        
        # Check for gov cash change vs agent cash change consistency
        total_agents_after = sum(a.cash for a in rA.agents if label == 'A') if label == 'A' else sum(a.cash for a in rB.agents)
    
    # Investigate the deposit tracking mismatch
    print(f"    Bank A: deposits_dict_sum=${sA_after['deposits_sum']:.2f} "
          f"({sA_after['deposits_count']} entries) "
          f"total_deposits=${sA_after['td']:.2f}")
    print(f"    Bank B: deposits_dict_sum=${sB_after['deposits_sum']:.2f} "
          f"({sB_after['deposits_count']} entries) "
          f"total_deposits=${sB_after['td']:.2f}")
    
    if abs(leak) > 1:
        print(f"    >>> LARGE LEAK (${leak:.2f})")
        # Check: is the gap in total_deposits - deposits_sum growing?
        gap_a_before = sA_before['td'] - sA_before['deposits_sum']
        gap_a_after = sA_after['td'] - sA_after['deposits_sum']
        gap_b_before = sB_before['td'] - sB_before['deposits_sum']
        gap_b_after = sB_after['td'] - sB_after['deposits_sum']
        print(f"      Bank A gap (td - deposits_sum): ${gap_a_before:.2f} -> ${gap_a_after:.2f} "
              f"(delta=${gap_a_after - gap_a_before:+.2f})")
        print(f"      Bank B gap (td - deposits_sum): ${gap_b_before:.2f} -> ${gap_b_after:.2f} "
              f"(delta=${gap_b_after - gap_b_before:+.2f})")
        total_gap_delta = (gap_a_after - gap_a_before) + (gap_b_after - gap_b_before)
        print(f"      Total gap change = ${total_gap_delta:+.2f}")
        print(f"      Leak - total_gap = ${leak - total_gap_delta:+.4f}")
    
    print()
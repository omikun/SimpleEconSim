#!/usr/bin/env python3
"""
Trace every substep of the first turn to identify which operation causes cash leakage.
"""
import sys
sys.path.insert(0, '.')

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random

time_steps = 1
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
    """Capture all cash."""
    ac = sum(a.cash for a in region.agents)
    td = region.bank.total_deposits
    tl = region.bank.total_liabilities
    cc = region.charity.cash
    gc = region.gov.agent.cash
    n = len(region.agents)
    return {'ac': ac, 'td': td, 'tl': tl, 'cc': cc, 'gc': gc, 'n': n,
            'sys': ac + (td - tl) + cc}

def show(region, label, s):
    print(f"  {region.name:>10} {label:>25}: ac=${s['ac']:>8.2f} td=${s['td']:>8.2f} "
          f"tl=${-s['tl']:>8.2f} cc=${s['cc']:>8.2f} gc=${s['gc']:>8.2f} sys=${s['sys']:>8.2f} n={s['n']}")

# Initial
sA_init = snap(rA)
sB_init = snap(rB)
print(f"=== INITIAL ===")
show(rA, "initial", sA_init)
show(rB, "initial", sB_init)
init_total = sA_init['sys'] + sB_init['sys']
print(f"  TOTAL: ${init_total:.2f}")
print()

t = 1

# Start step(t) — manual trace
for a in rA.agents:
    a.clear_wealth_cache()
for a in rB.agents:
    a.clear_wealth_cache()

sA = snap(rA); sB = snap(rB)
print(f"After clear_wealth_cache: total={sA['sys'] + sB['sys']:.2f} (delta={sA['sys'] + sB['sys'] - init_total:+.4f})")

# Charity collect donations
rA.charity.collect_donations(t, rA.agents, rA.bank)
rB.charity.collect_donations(t, rB.agents, rB.bank)
sA = snap(rA); sB = snap(rB)
after_charity_total = sA['sys'] + sB['sys']
print(f"After charity collect:    total={after_charity_total:.2f} (delta={after_charity_total - init_total:+.4f})")
show(rA, "charity collected", sA)
show(rB, "charity collected", sB)

# _run_labour (includes _cleanup, _borrow_or_layoff, _incorporate, _hire, _adjust_wages)
newA = rA._run_labour(t)
newB = rB._run_labour(t)
if newA:
    rA.agents.extend(newA)
if newB:
    rB.agents.extend(newB)
sA = snap(rA); sB = snap(rB)
after_labour_total = sA['sys'] + sB['sys']
print(f"After _run_labour:        total={after_labour_total:.2f} (delta={after_labour_total - init_total:+.4f})")
if newA:
    show(rA, "after labour", sA)
if newB:
    show(rB, "after labour", sB)

# _produce
rA._produce(t)
rB._produce(t)
sA = snap(rA); sB = snap(rB)
after_produce_total = sA['sys'] + sB['sys']
print(f"After _produce:           total={after_produce_total:.2f} (delta={after_produce_total - init_total:+.4f})")

# _trade (includes borrow/deposit decisions)
rA._trade(t)
rB._trade(t)
sA = snap(rA); sB = snap(rB)
after_trade_total = sA['sys'] + sB['sys']
print(f"After _trade:             total={after_trade_total:.2f} (delta={after_trade_total - init_total:+.4f})")

# _pay_wages
rA._pay_wages(t)
rB._pay_wages(t)
sA = snap(rA); sB = snap(rB)
after_wages_total = sA['sys'] + sB['sys']
print(f"After _pay_wages:         total={after_wages_total:.2f} (delta={after_wages_total - init_total:+.4f})")

# _distribute_profits
rA._record_start()
rB._record_start()
rA._distribute_profits(t)
rB._distribute_profits(t)
rA._record_delta()
rB._record_delta()
sA = snap(rA); sB = snap(rB)
after_profits_total = sA['sys'] + sB['sys']
print(f"After _distribute_profits: total={after_profits_total:.2f} (delta={after_profits_total - init_total:+.4f})")

# _collect_tax
rA._collect_tax(t)
rB._collect_tax(t)
sA = snap(rA); sB = snap(rB)
after_tax_total = sA['sys'] + sB['sys']
print(f"After _collect_tax:       total={after_tax_total:.2f} (delta={after_tax_total - init_total:+.4f})")

# _log_gdp (no cash changes)

# _recalculate_multipliers (no cash changes)

# _live (life-cycle: births, deaths, etc.)
rA.agents = rA._live(t)
rB.agents = rB._live(t)
sA = snap(rA); sB = snap(rB)
after_live_total = sA['sys'] + sB['sys']
print(f"After _live:              total={after_live_total:.2f} (delta={after_live_total - init_total:+.4f})")
show(rA, "after live", sA)
show(rB, "after live", sB)

# Charity distribute food
rA.charity.distribute_food(t, rA.agents)
rB.charity.distribute_food(t, rB.agents)
sA = snap(rA); sB = snap(rB)
after_dist_total = sA['sys'] + sB['sys']
print(f"After charity distribute: total={after_dist_total:.2f} (delta={after_dist_total - init_total:+.4f})")

# Now do transport and foreign_sell
for trader in rA.agents:
    if trader.is_trader: trader._process_pipeline()
for trader in rB.agents:
    if trader.is_trader: trader._process_pipeline()
foreign_sell(t, rA, rB)
foreign_sell(t, rB, rA)
sA = snap(rA); sB = snap(rB)
after_trade_total = sA['sys'] + sB['sys']
print(f"After transport+foreign_sell: total={after_trade_total:.2f} (delta={after_trade_total - init_total:+.4f})")

print(f"\n{'='*60}")
print(f"INITIAL TOTAL:  ${init_total:.2f}")
print(f"FINAL TOTAL:    ${after_trade_total:.2f}")
print(f"NET LEAK:       ${after_trade_total - init_total:+.4f}")
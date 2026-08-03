#!/usr/bin/env python3
"""
Pinpoint cash-leak sources by comparing:
  actual_leak = (agent_cash + bank_equity + charity_cash) delta per turn
  audited_net = net of all tracked Bank operations (Borrow/Deposit/Withdraw/etc.)

If actual_leak != audited_net, the leak is from agent-to-agent cash transfers
(or charity transfers) that bypass the bank. If actual_leak matches audited_net,
the leak is inside the Bank wrapper itself.

Also logs top-5 mutations by amount from the auditor.
"""
import sys
sys.path.insert(0, '.')

from cash_auditor import install_auditor, start_turn, end_turn, audit_report
install_auditor()

from region import Region, get_total_cash
from goods import Goods
from logger import logInit
from econsim_two_region import foreign_sell
import random
import math

time_steps = 10
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

def total_with_charity(region):
    return get_total_cash(region.agents, region.bank) + region.charity.cash

print(f"{'='*80}")
print(f"CASH LEAK PINPOINT — {time_steps} turns")
print(f"Comparing ACTUAL cash delta (agent+bank+charity) vs AUDITED bank ops")
print(f"{'='*80}")
print()
print(f"{'T':>4}  {'ActualLeak':>12} {'AuditedNet':>12} {'Match?':>8} "
      f"{'AgentsA':>8} {'AgentsB':>8}")
print("-" * 80)

total_actual = 0.0
total_mismatch = 0.0

for t in range(1, time_steps + 1):
    cash_before = total_with_charity(rA) + total_with_charity(rB)

    start_turn()
    rA.step(t)
    rB.step(t)
    process_transport(t, rA, rB)
    foreign_sell(t, rA, rB)
    foreign_sell(t, rB, rA)
    entry = end_turn()

    cash_after = total_with_charity(rA) + total_with_charity(rB)
    actual_leak = cash_after - cash_before

    # Audited net: total_deposits - total_liabilities + agent_cash + bank_deposit changes
    audited_net = entry['net_system_cash']

    match = "✔" if abs(actual_leak - audited_net) < 0.01 else "✗ LEAK"
    if abs(actual_leak) > 0.01:
        total_actual += abs(actual_leak)
    if match != "✔":
        total_mismatch += abs(actual_leak - audited_net)

    print(f"{t:>4}  {actual_leak:>+12.4f} {audited_net:>+12.4f} {match:>8} "
          f"{len(rA.agents):>8} {len(rB.agents):>8}")

    if abs(actual_leak) > 5.0:
        print(f"  >>> Large actual leak — top mutations:")
        for m in entry['largest_mutations'][:5]:
            print(f"      {m.method:>25} agent={m.agent} amt={m.amount:>10.2f} "
                  f"td={m.total_deposits_delta:>8.4f} tl={m.total_liabilities_delta:>8.4f} "
                  f"ac={m.agent_cash_delta:>8.4f} [{m.caller}]")
        # Break down what's happening to agent cash directly
        a_agent_cash_before = sum(a.cash for a in rA.agents)
        b_agent_cash_before = sum(a.cash for a in rB.agents)
        a_agent_cash_after = sum(a.cash for a in rA.agents)
        b_agent_cash_after = sum(a.cash for a in rB.agents)
        print(f"      Region A agents cash: ${a_agent_cash_before:.2f} -> ${a_agent_cash_after:.2f} "
              f"(delta=${a_agent_cash_after - a_agent_cash_before:+.2f})")
        print(f"      Region B agents cash: ${b_agent_cash_before:.2f} -> ${b_agent_cash_after:.2f} "
              f"(delta=${b_agent_cash_after - b_agent_cash_before:+.2f})")

print("-" * 80)
print(f"\nTotal actual leak magnitude: ${total_actual:.4f}")
print(f"Total mismatch (actual ≠ audited): ${total_mismatch:.4f}")

if total_mismatch < 0.1:
    print(f"\n✓ All actual leaks are EXPLAINED by tracked bank operations.")
    print(f"  The leak sources are inside Bank methods — likely a wrapper bug or")
    print(f"  a mutation in Bank code that the auditor doesn't track.")
else:
    print(f"\n✗ REMAINING UNTRACKED LEAKS: ${total_mismatch:.4f}")
    print(f"  These are agent-to-agent cash transfers (wages, trade, foreign_sell)")
    print(f"  that bypass the Bank entirely.")
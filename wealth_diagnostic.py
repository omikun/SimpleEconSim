#!/usr/bin/env python3
"""
Wealth diagnostic: traces cash distribution and generates a wealth histogram
with detailed intra-profession inequality metrics.

Usage:
    python3 wealth_diagnostic.py [time_steps]
"""

import sys
import math
import random
from collections import defaultdict

from goods import Goods, profession
from region import Region, get_total_cash
from logger import logInit
import econsim_two_region as sim


def stats(vals):
    """Return (min, max, mean, median, std, count) for a list of numbers."""
    n = len(vals)
    if n == 0:
        return (0, 0, 0, 0, 0, 0)
    s = sorted(vals)
    mn = s[0]
    mx = s[-1]
    avg = sum(vals) / n
    med = s[n // 2]
    var = sum((v - avg) ** 2 for v in vals) / n
    std = math.sqrt(var)
    return (mn, mx, avg, med, std, n)


def print_wealth_diagnostic(region, label):
    agents = region.agents
    bank = region.bank

    print(f"\n{'='*70}")
    print(f"{label} — Wealth Diagnostics (Turn {current_t})")
    print(f"{'='*70}")

    total_cash = get_total_cash(agents, bank)
    agent_cash_sum = sum(a.cash for a in agents)
    bank_equity = bank.total_deposits - bank.total_liabilities

    print(f"Total system cash: ${total_cash:>10.2f}")
    print(f"  Agent cash:      ${agent_cash_sum:>10.2f}")
    print(f"  Bank equity:     ${bank_equity:>10.2f}")
    print(f"    deposits:      ${bank.total_deposits:>10.2f}")
    print(f"    liabilities:   ${-bank.total_liabilities:>10.2f}")

    # ---- Categorise agents ----
    corps = [a for a in agents if a.is_corporation]
    traders = [a for a in agents if getattr(a, 'is_trader', False)]
    gov_list = [a for a in agents if getattr(a, 'is_government', False)]
    regular = [a for a in agents if not a.is_corporation and not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False)]

    print(f"\nAgent count: {len(agents)} total ({len(regular)} regular, {len(corps)} corps, {len(traders)} traders, {len(gov_list)} gov)")
    print(f"\nCash by type:")
    print(f"  Regular agents:  ${sum(a.cash for a in regular):>10.2f}")
    print(f"  Corps:           ${sum(a.cash for a in corps):>10.2f}")
    print(f"  Traders:         ${sum(a.cash for a in traders):>10.2f}")
    print(f"  Government:      ${sum(a.cash for a in gov_list):>10.2f}")

    print(f"\nBank deposits by type:")
    print(f"  Regular agents:  ${sum(bank.deposits.get(a,0) for a in regular):>10.2f}")
    print(f"  Corps:           ${sum(bank.deposits.get(a,0) for a in corps):>10.2f}")
    print(f"  Traders:         ${sum(bank.deposits.get(a,0) for a in traders):>10.2f}")
    if gov_list:
        print(f"  Government:      ${bank.deposits.get(gov_list[0],0):>10.2f}")

    # ---- Corporate retained earnings ----
    if corps:
        total_retained = sum(a.retained_earnings for a in corps)
        print(f"\nCorporate retained earnings (total): ${total_retained:>8.2f}")
        print(f"  Corp cash on hand:                 ${sum(a.cash for a in corps):>8.2f}")
        for c in sorted(corps, key=lambda a: a.retained_earnings, reverse=True)[:5]:
            print(f"  {c.name():>20} output={str(c.output).split('.')[-1]:>9} cash=${c.cash:>7.2f} retained=${c.retained_earnings:>7.2f} employees={len(c.employees)}")

    # ==================================================================
    # INTRA-PROFESSION STATS (all non-corp non-trader non-gov agents)
    # ==================================================================
    trade_goods = [Goods.food, Goods.wood, Goods.furniture]
    print(f"\n{'='*70}")
    print(f"INTRA-PROFESSION INEQUALITY (cash + deposits)")
    print(f"{'='*70}")

    for prof in trade_goods:
        # All non-corp agents in this profession
        prof_agents = [a for a in regular if a.output == prof]
        if not prof_agents:
            print(f"\n  {str(prof).split('.')[-1]:>12}: NO AGENTS")
            continue

        wealth_vals = [a.cash + bank.deposits.get(a, 0) for a in prof_agents]
        mn, mx, avg, med, std, n = stats(wealth_vals)
        pct_below_20 = sum(1 for v in wealth_vals if v < 20) / n * 100
        
        # Separate corp-owned (employees) vs independent
        employees = [a for a in prof_agents if a.employer is not None]
        independents = [a for a in prof_agents if a.employer is None]
        emp_wealth = [a.cash + bank.deposits.get(a, 0) for a in employees]
        ind_wealth = [a.cash + bank.deposits.get(a, 0) for a in independents]

        print(f"\n  {str(prof).split('.')[-1]:>12}:")
        print(f"    count={n:>3}  min=${mn:>7.2f}  max=${mx:>9.2f}  avg=${avg:>7.2f}  median=${med:>7.2f}  std=${std:>7.2f}")
        print(f"    % below $20: {pct_below_20:.1f}%  (reproduction-critical threshold)")
        if std > 0:
            print(f"    gini-estimate (simplified): {std / (avg * 2) * 100:.1f}%")
        
        if employees and independents:
            e_mn, e_mx, e_avg, e_med, e_std, e_n = stats(emp_wealth)
            i_mn, i_mx, i_avg, i_med, i_std, i_n = stats(ind_wealth)
            print(f"    ├─ Employees ({e_n}): avg=${e_avg:>7.2f} median=${e_med:>7.2f} min=${e_mn:>7.2f} max=${e_mx:>7.2f}")
            print(f"    └─ Independent ({i_n}): avg=${i_avg:>7.2f} median=${i_med:>7.2f} min=${i_mn:>7.2f} max=${i_mx:>7.2f}")
        elif employees:
            print(f"    all {n} agents are employees")
        else:
            print(f"    all {n} agents are independent")

    # ---- Top 10 richest ----
    print(f"\n{'='*70}")
    print(f"TOP 10 RICHEST AGENTS (wealth = cash + deposits + inventory - debt)")
    print(f"{'='*70}")
    sorted_agents = sorted(agents, key=lambda a: a.wealth(), reverse=True)
    for i, a in enumerate(sorted_agents[:10]):
        wealth = a.wealth()
        tags = []
        if getattr(a, 'is_corporation', False): tags.append('CORP')
        if getattr(a, 'is_trader', False): tags.append('TRADER')
        if getattr(a, 'is_government', False): tags.append('GOV')
        tag_str = ','.join(tags)
        output = str(a.output).split('.')[-1]
        dep = bank.deposits.get(a, 0)
        inv_val = sum(a.inv_get(g, 0) * region.recipes[g]['price'] for g in [Goods.food, Goods.wood, Goods.furniture] if g in region.recipes)
        debt = sum(l.principle - l.principle_paid for l in a.loans)
        print(f"  {i+1:>2}. {a.name():>20} [{output:>9}] {tag_str:>8} cash=${a.cash:>7.2f} dep=${dep:>7.2f} inv=${inv_val:>7.2f} debt=${debt:>7.2f} wealth=${wealth:>8.2f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    global current_t

    logInit()
    print(f"Wealth Diagnostic: {time_steps} turns\n")

    random.seed(42)

    region_a = Region("Region_A", t=0, number_of_agents=110,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
    region_b = Region("Region_B", t=0, number_of_agents=110,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})

    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2

    region_a.destination_region = region_b
    region_b.destination_region = region_a
    for trader in region_a.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_b
    for trader in region_b.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_a

    # Track births and deaths
    cumulative_births = 0
    cumulative_deaths = 0

    # Collect wealth percentiles per profession (sample every 5 turns)
    wealth_history = {'Region_A': {}, 'Region_B': {}}

    for t in range(1, time_steps + 1):
        n_before = len(region_a.agents) + len(region_b.agents)

        region_a.step(t)
        region_b.step(t)
        sim.process_transport(t, region_a, region_b)
        sim.foreign_sell(t, region_a, region_b)
        sim.foreign_sell(t, region_b, region_a)

        n_after = len(region_a.agents) + len(region_b.agents)
        diff = n_after - n_before
        if diff > 0:
            cumulative_births += diff
        elif diff < 0:
            cumulative_deaths -= diff

        # Sample wealth distribution every 5 turns
        if t % 5 == 0 or t == 1:
            for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
                bank = region.bank
                regular = [a for a in region.agents if not a.is_corporation
                           and not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False)]
                frame = {}
                for prof in [Goods.food, Goods.wood, Goods.furniture]:
                    vals = [a.cash + bank.deposits.get(a, 0) for a in regular if a.output == prof]
                    frame[prof] = vals
                wealth_history[rname][t] = frame

    current_t = time_steps

    print(f"\n{'='*70}")
    print(f"POPULATION DYNAMICS (over {time_steps} turns)")
    print(f"{'='*70}")
    print(f"Region A final pop: {len(region_a.agents)} (initial: 110)")
    print(f"Region B final pop: {len(region_b.agents)} (initial: 110)")
    print(f"Cumulative births: {cumulative_births}")
    print(f"Cumulative deaths: {cumulative_deaths}")
    print(f"Net change: {cumulative_births - cumulative_deaths}")

    print_wealth_diagnostic(region_a, "REGION A")
    print_wealth_diagnostic(region_b, "REGION B")

    # ---- Wealth evolution plot (percentiles over time) ----
    try:
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker

        colors_map = {
            Goods.food: 'green',
            Goods.wood: 'red',
            Goods.furniture: 'blue',
            Goods.gov: 'yellow',
        }
        prof_labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture'}
        region_names = ['Region_A', 'Region_B']
        region_labels = {'Region_A': 'Region A', 'Region_B': 'Region B'}

        fig, axes = plt.subplots(2, 3, figsize=(16, 9))
        fig.suptitle("Wealth Distribution Evolution (cash + deposits, non-corp, non-trader)", fontsize=14)

        for row, rname in enumerate(region_names):
            for col, prof in enumerate([Goods.food, Goods.wood, Goods.furniture]):
                ax = axes[row, col]
                turns = sorted(wealth_history[rname].keys())
                if not turns:
                    ax.set_title(f"{region_labels[rname]} — {prof_labels[prof]} (no data)")
                    continue

                # Build arrays per turn
                percentiles = {'p10': [], 'p25': [], 'p50': [], 'p75': [], 'p90': []}
                for t in turns:
                    vals = sorted(wealth_history[rname][t][prof])
                    n = len(vals)
                    if n == 0:
                        for k in percentiles:
                            percentiles[k].append(0)
                        continue
                    percentiles['p10'].append(vals[n * 10 // 100])
                    percentiles['p25'].append(vals[n * 25 // 100])
                    percentiles['p50'].append(vals[n // 2])
                    percentiles['p75'].append(vals[n * 75 // 100])
                    percentiles['p90'].append(vals[n * 90 // 100])

                ax.fill_between(turns, percentiles['p10'], percentiles['p90'],
                                alpha=0.15, color=colors_map[prof])
                ax.fill_between(turns, percentiles['p25'], percentiles['p75'],
                                alpha=0.30, color=colors_map[prof])
                ax.plot(turns, percentiles['p50'], color=colors_map[prof],
                        linewidth=2, label='Median')
                ax.plot(turns, percentiles['p25'], color=colors_map[prof],
                        linewidth=1, linestyle='--', alpha=0.7, label='p25/p75')
                ax.plot(turns, percentiles['p75'], color=colors_map[prof],
                        linewidth=1, linestyle='--', alpha=0.7)
                ax.axhline(y=20, color='gray', linestyle=':', linewidth=0.5, label='Repro ($20)')
                ax.set_yscale('symlog')
                ax.set_title(f"{region_labels[rname]} — {prof_labels[prof]}")
                ax.set_ylabel("Cash + deposits ($)")
                ax.set_xlabel("Turn")
                ax.legend(fontsize='x-small')

        plt.tight_layout()
        plt.savefig("wealth_diagnostic.png")
        plt.close(fig)
        print(f"\nWealth evolution plot saved to wealth_diagnostic.png")
    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
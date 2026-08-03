#!/usr/bin/env python3
"""
Diagnose why government wealth drops to zero after ~220 turns.

Instruments tax, tariff, welfare, and bailout flows per turn and plots
the cumulative picture alongside starving agent count.

Usage:
    python3 diagnose_gov_cash.py [time_steps]
"""

import sys
import random
from collections import defaultdict

from goods import Goods
from region import Region
from logger import logInit
import econsim_two_region as sim


# =============================================================================
# Instrumented wrappers (monkey-patch to track flows without changing source)
# =============================================================================

flows = {}  # (turn, region_name) -> dict with in/out counters


def _wrap_collect_tax(original):
    def wrapper(self, t, amount):
        ret = original(self, t, amount)
        if ret > 0:
            key = (t, self.name)
            if key not in flows:
                flows[key] = defaultdict(float)
            flows[key]['tax_in'] += ret
        return ret
    return wrapper


def _wrap_distribute_welfare(original):
    def wrapper(self, t, agents, min_reserve=0):
        ret = original(self, t, agents, min_reserve)
        if ret > 0:
            key = (t, self.name)
            if key not in flows:
                flows[key] = defaultdict(float)
            flows[key]['welfare_out'] += ret
        return ret
    return wrapper


def _wrap_provide_food_aid(original):
    def wrapper(self, t, agents, food_price):
        ret = original(self, t, agents, food_price)
        if ret > 0:
            key = (t, self.name)
            if key not in flows:
                flows[key] = defaultdict(float)
            flows[key]['food_aid_cost'] += ret
        return ret
    return wrapper


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    # Apply instrumentation BEFORE creating any regions
    import government as govmod
    govmod.Government.collect_tax = _wrap_collect_tax(govmod.Government.collect_tax)
    govmod.Government.distribute_welfare = _wrap_distribute_welfare(govmod.Government.distribute_welfare)
    govmod.Government.provide_food_aid = _wrap_provide_food_aid(govmod.Government.provide_food_aid)

    logInit()
    print(f"Gov Cash Diagnostic: {time_steps} turns\n")

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

    # Per-turn data collection for gov cash + flows + starving count
    gov_log = {'Region_A': [], 'Region_B': []}
    previously_starving = {'Region_A': 0, 'Region_B': 0}
    zero_cash_turns = {'Region_A': [], 'Region_B': []}

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        sim.process_transport(t, region_a, region_b)
        sim.foreign_sell(t, region_a, region_b)
        sim.foreign_sell(t, region_b, region_a)

        for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
            gov = region.gov
            ga = gov.agent
            cash = ga.cash + region.bank.deposits.get(ga, 0)
            debt = sum(l.principle - l.principle_paid for l in ga.loans) if ga.loans else 0
            num_starving = sum(1 for a in region.agents if a.alive and a.hungry_steps > 0 and not a.is_corporation)

            key = (t, gov.name)
            f = flows.get(key, {})
            tax_in = f.get('tax_in', 0)
            welfare_out = f.get('welfare_out', 0)
            food_aid = f.get('food_aid_cost', 0)

            # Track tariff separately by watching gov.cash before/after foreign_sell
            # (we can compute it from delta minus known flows)

            gov_log[rname].append({
                'turn': t,
                'cash': ga.cash,
                'deposit': region.bank.deposits.get(ga, 0),
                'debt': debt,
                'tax_in': tax_in,
                'welfare_out': welfare_out,
                'food_aid': food_aid,
                'num_starving': num_starving,
            })

            if ga.cash == 0 and region.bank.deposits.get(ga, 0) == 0:
                if not zero_cash_turns[rname] or zero_cash_turns[rname][-1] != t - 1:
                    zero_cash_turns[rname].append(t)
            elif ga.cash > 0 and previously_starving[rname] > 0:
                # Detect first turn cash goes to zero with starving present
                pass
            previously_starving[rname] = num_starving

    # ---- Print analysis ----
    for rname in ['Region_A', 'Region_B']:
        log = gov_log[rname]
        print(f"\n{'='*70}")
        print(f"{rname} — Gov Cash Analysis")
        print(f"{'='*70}")

        first_zero = None
        for entry in log:
            if entry['cash'] < 0.01 and entry['deposit'] < 0.01:
                first_zero = entry['turn']
                break

        if first_zero:
            print(f"  Gov wealth hit $0 at turn {first_zero}")
            # Show the last 5 turns before zero and the first 5 at zero
            zero_idx = next(i for i, e in enumerate(log) if e['turn'] == first_zero)
            window = log[max(0, zero_idx-5):zero_idx+5]
            print(f"\n  Last turns before/after zero:")
            print(f"  {'Turn':>5} {'Cash':>8} {'Dep':>8} {'Debt':>8} {'Tax':>8} {'Welfare':>10} {'FoodAid':>8} {'Starving':>8}")
            for e in window:
                print(f"  {e['turn']:>5} ${e['cash']:>7.2f} ${e['deposit']:>7.2f} ${e['debt']:>7.2f} "
                      f"${e['tax_in']:>7.2f} ${e['welfare_out']:>9.2f} ${e['food_aid']:>7.2f} {e['num_starving']:>8}")

        else:
            print(f"  Gov wealth NEVER hit $0 (final cash=${log[-1]['cash']:.2f})")

        total_tax = sum(e['tax_in'] for e in log)
        total_welfare = sum(e['welfare_out'] for e in log)
        total_food_aid = sum(e['food_aid'] for e in log)
        print(f"\n  Totals over {time_steps} turns:")
        print(f"    Tax collected:     ${total_tax:>10.2f}")
        print(f"    Welfare paid:      ${total_welfare:>10.2f}")
        print(f"    Food aid cost:     ${total_food_aid:>10.2f}")
        print(f"    Tax - Welfare - FoodAid: ${total_tax - total_welfare - total_food_aid:>10.2f}")

    # ---- Plot ----
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle("Government Cash Flow Analysis", fontsize=14)

        for row, rname in enumerate(['Region_A', 'Region_B']):
            log = gov_log[rname]
            turns = [e['turn'] for e in log]
            cash = [e['cash'] + e['deposit'] for e in log]
            tax_in = [e['tax_in'] for e in log]
            welfare_out = [-e['welfare_out'] for e in log]
            starving = [e['num_starving'] for e in log]

            # Plot 1: Cash + flows (positive: income, negative: expenses)
            ax = axes[row, 0]
            ax.plot(turns, cash, color='black', linewidth=2, label='Gov wealth')
            ax.fill_between(turns, 0, tax_in, alpha=0.3, color='green', label='Tax in', step='mid')
            ax.fill_between(turns, 0, welfare_out, alpha=0.3, color='red', label='Welfare out', step='mid')
            ax.set_title(f"{rname} — Gov cash + flows")
            ax.set_ylabel("$")
            ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
            ax.legend(fontsize='small')

            # Plot 2: Starving agents
            ax2 = axes[row, 1]
            ax2.plot(turns, starving, color='darkred', linewidth=1.5)
            ax2.fill_between(turns, 0, starving, alpha=0.2, color='red')
            ax2.set_title(f"{rname} — Starving agents")
            ax2.set_ylabel("Count")
            ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

            # Mark where gov wealth went to zero
            zero_turns = [e['turn'] for e in log if e['cash'] < 0.01 and e['deposit'] < 0.01]
            if zero_turns:
                ylim = ax2.get_ylim()
                ax2.vlines(zero_turns[0], 0, ylim[1], color='red', linestyle=':', linewidth=1,
                           label=f'$0 at t={zero_turns[0]}')
                ax2.legend(fontsize='small')

        plt.tight_layout()
        plt.savefig("gov_cash_diagnostic.png")
        plt.close(fig)
        print(f"\nPlot saved to gov_cash_diagnostic.png")

    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
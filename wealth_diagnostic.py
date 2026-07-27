#!/usr/bin/env python3
"""
Wealth diagnostic: traces cash distribution and generates a wealth histogram.

Usage:
    python3 wealth_diagnostic.py [time_steps]
"""

import sys
import random
from collections import defaultdict

from goods import Goods, profession
from region import Region, get_total_cash
from logger import logInit
import econsim_two_region as sim


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
    
    # ---- Wealth by profession ----
    print(f"\nWealth by profession (cash + deposits):")
    by_prof = defaultdict(list)
    for a in regular:
        by_prof[a.output].append(a.cash + bank.deposits.get(a, 0))
    for prof, vals in sorted(by_prof.items(), key=lambda kv: str(kv[0])):
        label = str(prof).split('.')[-1]
        non_zero = [v for v in vals if v > 0]
        print(f"  {label:>12}: count={len(vals):>3} total=${sum(vals):>9.2f} avg=${sum(vals)/len(vals):>7.2f} median=${sorted(vals)[len(vals)//2]:>7.2f} non-zero={len(non_zero)}")
    
    # ---- Top 10 richest ----
    print(f"\nTop 10 by wealth (cash + deposits + inventory - debt):")
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
        inv_val = sum(qty * region.recipes[good]['price'] for good, qty in a.inventory.items() if good in region.recipes)
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
    
    # ---- Wealth histogram ----
    try:
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f"Wealth Distribution (cash + deposits) — Turn {time_steps}")
        
        colors_map = {
            Goods.food: 'green',
            Goods.wood: 'red',
            Goods.furniture: 'blue',
            Goods.gov: 'yellow',
        }
        
        for idx, (region, ax) in enumerate(zip([region_a, region_b], axes)):
            bank = region.bank
            agents = [a for a in region.agents if not a.is_corporation and not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False)]
            
            wealth_vals = [a.cash + bank.deposits.get(a, 0) for a in agents]
            prof_labels = [a.output for a in agents]
            
            # Sort by wealth descending
            paired = sorted(zip(wealth_vals, prof_labels), key=lambda x: -x[0])
            
            wealth_vals = [p[0] for p in paired]
            prof_labels = [p[1] for p in paired]
            
            bars = ax.bar(range(len(wealth_vals)), wealth_vals, 
                         color=[colors_map.get(p, 'grey') for p in prof_labels])
            ax.set_title(f"{region.name} — {len(agents)} non-corp agents")
            ax.set_xlabel("Agent index (sorted by wealth)")
            ax.set_ylabel("Cash + deposits ($)")
            ax.axhline(y=20, color='gray', linestyle='--', linewidth=0.5, label='Reproduction threshold ($20)')
            ax.axhline(y=4, color='purple', linestyle=':', linewidth=0.5, label='Food cost floor ($4)')
            ax.legend(fontsize='small')
            
            # Profession legend
            from matplotlib.patches import Patch
            legend_patches = [Patch(color=c, label=lbl) for g, c, lbl in 
                            [(Goods.food, 'green', 'Food'), (Goods.wood, 'red', 'Wood'), 
                             (Goods.furniture, 'blue', 'Furniture'), (Goods.gov, 'yellow', 'Gov')]
                            if any(p == g for p in prof_labels)]
            if legend_patches:
                ax.legend(handles=legend_patches, loc='upper right', fontsize='small')
        
        plt.tight_layout()
        plt.savefig("wealth_diagnostic.png")
        plt.close(fig)
        print(f"\nWealth histogram saved to wealth_diagnostic.png")
    except Exception as e:
        print(f"\nCould not generate histogram: {e}")


if __name__ == "__main__":
    main()
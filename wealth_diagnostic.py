#!/usr/bin/env python3
"""
Wealth diagnostic: traces cash distribution and generates a wealth histogram
with detailed intra-profession inequality metrics.

Can run standalone:
    python3 wealth_diagnostic.py [time_steps]

Or as an importable module driven by econsim_two_region.py:
    import wealth_diagnostic
    wealth_diagnostic.init_collectors()
    # ... in the simulation loop ...
    wealth_diagnostic.record_turn(t, region_a, region_b)
    # ... after the loop ...
    wealth_diagnostic.generate_plots(time_steps, region_a, region_b)
"""

import sys
import math
import random
from collections import defaultdict

from goods import Goods, profession
from region import Region, get_total_cash
from logger import logInit
import econsim_two_region as sim


# =============================================================================
# Collector lifecycle (used by both standalone main() and econsim_two_region)
# =============================================================================

snapshots = {}          # region_name -> {turn: {category: [(wealth, debt, id)]}}
cumulative_births = 0
cumulative_deaths = 0
current_t = 0
_prev_agent_ids = set()   # agent IDs present as of the previous record_turn
_seeded = False           # first call seeds baseline; migrations are not births

OUTPUT_TO_CAT = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture'}
CAT_LABELS = ['Food', 'Wood', 'Furniture', 'Trader', 'Institutions']


def init_collectors():
    """Reset all collectors before a run."""
    global snapshots, cumulative_births, cumulative_deaths, current_t, \
        _prev_agent_ids, _seeded
    snapshots = {'Region_A': {}, 'Region_B': {}}
    cumulative_births = 0
    cumulative_deaths = 0
    current_t = 0
    _prev_agent_ids = set()
    _seeded = False


def record_turn(t, region_a, region_b):
    """Record birth/death deltas and wealth snapshots for simulation turn t.

    The caller (econsim_two_region or standalone main) has already run
    step/transport/foreign_sell for this turn before calling us.
    Births are agents whose ID was not present last turn; deaths are agents
    whose ID disappeared from both regions' living-agent lists.
    """
    global cumulative_births, cumulative_deaths, current_t, _prev_agent_ids, _seeded
    current_t = t
    current_ids = {a.id for a in region_a.agents} | {a.id for a in region_b.agents}
    if not _seeded:
        # Baseline: initial population is treated as pre-existing, not births
        _prev_agent_ids = current_ids
        _seeded = True
    else:
        cumulative_births += len(current_ids - _prev_agent_ids)
        cumulative_deaths += len(_prev_agent_ids - current_ids)
        _prev_agent_ids = current_ids

    if t % 10 == 0:
        for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
            bank = region.bank
            cat_agents = {c: [] for c in CAT_LABELS}
            for a in region.agents:
                wealth = a.cash + bank.deposits.get(a, 0)
                debt = sum(l.principle - l.principle_paid for l in a.loans) if a.loans else 0
                if a.is_trader:
                    cat_agents['Trader'].append((wealth, debt, a.id))
                elif a.is_government:
                    cat_agents['Institutions'].append((wealth, debt, -10))
                else:
                    cat = OUTPUT_TO_CAT.get(a.output, 'Food')
                    cat_agents[cat].append((wealth, debt, a.id))
            bank_wealth = bank.total_deposits - bank.total_liabilities
            bank_liab = bank.total_liabilities
            cat_agents['Institutions'].append((bank_wealth, bank_liab, -20))
            charity = region.charity
            food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
            charity_wealth = charity.agent.cash + bank.deposits.get(charity.agent, 0) \
                             + charity.food_inventory * food_price
            cat_agents['Institutions'].append((charity_wealth, 0, -30))
            snapshots[rname][t] = cat_agents


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


def print_wealth_diagnostic(region, label, turn=None):
    """Print cash distribution and intra-profession inequality for a region."""
    if turn is None:
        turn = current_t
    agents = region.agents
    bank = region.bank

    print(f"\n{'='*70}")
    print(f"{label} — Wealth Diagnostics (Turn {turn})")
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
# ANALYSIS & VISUALIZATION
# =============================================================================

def generate_plots(time_steps, region_a, region_b):
    """Produce the wealth stacked bar chart and diagnostic output."""
    print(f"\n{'='*70}")
    print(f"POPULATION DYNAMICS (over {time_steps} turns)")
    print(f"{'='*70}")
    print(f"Region A final pop: {len(region_a.agents)}")
    print(f"Region B final pop: {len(region_b.agents)}")
    print(f"Cumulative births: {cumulative_births}")
    print(f"Cumulative deaths: {cumulative_deaths}")
    print(f"Net change: {cumulative_births - cumulative_deaths}")

    print_wealth_diagnostic(region_a, "REGION A", time_steps)
    print_wealth_diagnostic(region_b, "REGION B", time_steps)

    # ---- Stacked bar chart: one bar per snapshot turn, segments = agents ----
    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgba, to_hex
        import numpy as np

        region_names = ['Region_A', 'Region_B']
        region_labels = {'Region_A': 'Region A', 'Region_B': 'Region B'}
        cat_labels = ['Food', 'Wood', 'Furniture', 'Trader', 'Institutions']

        fig, axes = plt.subplots(2, 5, figsize=(24, 12))
        fig.suptitle("Wealth by Category (cash + deposits) — Region A top, Region B bottom", fontsize=16)

        # Each non-Institutions category gets its own colormap
        cmap_names = ['viridis', 'plasma', 'inferno', 'magma', 'Set1']
        # Fixed institution colors: Gov=gold, Bank=purple, Charity=teal
        inst_colors = {-10: '#FFD700', -20: '#8B008B', -30: '#008080'}
        inst_labels = {-10: 'Gov', -20: 'Bank', -30: 'Charity'}

        for idx, cat in enumerate(cat_labels):
            is_institutions = (cat == 'Institutions')
            for row, rname in enumerate(region_names):
                region = region_a if rname == 'Region_A' else region_b
                turns = sorted(snapshots[rname].keys())
                ax = axes[row, idx]

                if not turns:
                    ax.set_title(f"{region_labels[rname]} {cat} (no data)")
                    continue

                # Collect per-turn: sorted agent wealths for this category
                all_ids = set()
                per_turn_data = []
                for t in turns:
                    entries = snapshots[rname][t][cat]
                    entries_sorted = sorted(entries, key=lambda x: -x[0])
                    vals = [e[0] for e in entries_sorted]
                    debts = [e[1] for e in entries_sorted]
                    ids = [e[2] for e in entries_sorted]
                    all_ids.update(ids)
                    per_turn_data.append((t, vals, debts, ids))

                if not all_ids:
                    ax.set_title(f"{region_labels[rname]} {cat} (no agents)")
                    continue

                # Assign colors
                if is_institutions:
                    # Fixed distinct colors per institution
                    id_color = inst_colors
                else:
                    sorted_ids = sorted(all_ids)
                    n_ids = len(sorted_ids)
                    cmap = plt.get_cmap(cmap_names[idx])
                    id_color = {}
                    for i, aid in enumerate(sorted_ids):
                        rgba = cmap(0.2 + 0.8 * i / max(n_ids - 1, 1))
                        id_color[aid] = rgba

                # Build stacked bars
                x_pos = np.arange(len(per_turn_data))
                bar_width = 0.8
                for turn_idx, (t, vals, debts, ids) in enumerate(per_turn_data):
                    bottom = 0
                    for v, d, aid in zip(vals, debts, ids):
                        if v > 0:
                            color = id_color.get(aid, 'gray')
                            ax.bar(turn_idx, v, bottom=bottom, width=bar_width,
                                   color=color, edgecolor='none')
                            bottom += v
                    bottom = 0
                    for v, d, aid in zip(vals, debts, ids):
                        if d > 0:
                            color = id_color.get(aid, 'gray')
                            ax.bar(turn_idx, -d, bottom=bottom, width=bar_width,
                                   color=color, edgecolor='none')
                            bottom -= d
                ax.axhline(y=0, color='black', linewidth=0.5)

                step = max(1, len(turns) // 6)
                tick_indices = list(range(0, len(turns), step))
                ax.set_xticks(tick_indices)
                ax.set_xticklabels([str(turns[i]) for i in tick_indices], fontsize=7)
                ax.set_yscale('symlog')
                title = f"{region_labels[rname]} {cat}"
                if row == 0 and idx >= 3:
                    title = f"{region_labels[rname]}\n{cat}"
                ax.set_title(title, fontsize=10)
                if idx == 0:
                    ax.set_ylabel("Wealth ($)")

                if is_institutions:
                    # Fixed-color legend (Gov, Bank, Charity) + Debt
                    patches = []
                    for fid in [-10, -20, -30]:
                        patches.append(plt.Rectangle((0, 0), 1, 1,
                                       color=inst_colors[fid], label=inst_labels[fid]))
                    debt_patch = plt.Rectangle((0, 0), 1, 1, color='gray',
                                               label='Bank Debt')
                    patches.append(debt_patch)
                    ax.legend(handles=patches, fontsize=7, loc='upper left')
                else:
                    # Colorbar for per-agent categories
                    sorted_ids = sorted(all_ids)
                    n_ids = len(sorted_ids)
                    cmap = plt.get_cmap(cmap_names[idx])
                    sm = plt.cm.ScalarMappable(cmap=cmap,
                                               norm=plt.Normalize(vmin=sorted_ids[0],
                                                                  vmax=sorted_ids[-1]))
                    sm.set_array([])
                    cbar = plt.colorbar(sm, ax=ax, orientation='vertical',
                                        shrink=0.5, pad=0.02)
                    cbar.set_label('Agent ID', fontsize=6)
                    cbar.ax.tick_params(labelsize=5)
                    # Debt legend
                    debt_patch = plt.Rectangle((0, 0), 1, 1, color='gray',
                                               label='Debt')
                    ax.legend(handles=[debt_patch], fontsize=6, loc='upper left')

        plt.tight_layout()
        plt.savefig("wealth_stacked.png")
        plt.close(fig)
        print(f"  Wealth stacked bar saved to wealth_stacked.png")

    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# MAIN (standalone)
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 200

    logInit()
    print(f"Wealth Diagnostic: {time_steps} turns\n")

    init_collectors()

    random.seed(42)

    from transporter import Route

    region_a = Region("Region_A", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037},
                       number_of_traders=3)
    region_b = Region("Region_B", t=0, number_of_agents=200,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05},
                       number_of_traders=3)

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

    region_a.route = Route(f"{region_a.name}->{region_b.name}",
                           region_a, region_b, base_delay=sim.TRANSPORT_DELAY)
    region_b.route = Route(f"{region_b.name}->{region_a.name}",
                           region_b, region_a, base_delay=sim.TRANSPORT_DELAY)

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        region_a.route.advance()
        region_a.route.deliver_pending()
        region_b.route.advance()
        region_b.route.deliver_pending()
        sim.settle_trade(t, region_a, region_b)
        sim.settle_trade(t, region_b, region_a)
        record_turn(t, region_a, region_b)

    generate_plots(time_steps, region_a, region_b)


if __name__ == "__main__":
    main()
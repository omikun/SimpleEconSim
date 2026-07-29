#!/usr/bin/env python3
"""
Wealth Lineage Diagnostic: trace debt, inheritance, and wealth accumulation
across generations.  Monitors every death/inheritance event, every birth,
and every borrow, then produces a visual flow diagram.

Usage:
    python3 wealth_lineage.py [time_steps]
"""

import sys
import math
import random
from collections import defaultdict
from typing import Any

from goods import Goods, profession
from region import Region, get_total_cash
from logger import logInit
import econsim_two_region as sim


# =============================================================================
# Global event logs
# =============================================================================

# Inheritance events: (turn, deceased_id, deceased_profession, total_wealth,
#                       cash_transferred_inheritance, debt_inherited,
#                       heir_ids (list), went_to_gov (bool))
inheritance_events = []

# Debt events: (turn, agent_id, amount, reason)
borrow_events = []

# Birth/parent mapping: agent_id -> parent_id
parent_map = {}

# Pre-mortem state storage (Agent uses __slots__, so we store externally)
pre_mortem_state = {}

# Per-turn snapshots: {turn: {agent_id: (wealth, debt, profession, alive)}}
wealth_snapshots = {}

# Profession map for Output enum to string
PROF_NAMES = {
    Goods.food: 'Food',
    Goods.wood: 'Wood',
    Goods.furniture: 'Furniture',
    Goods.gov: 'Gov',
}


# =============================================================================
# Instrumentation (monkey-patches)
# =============================================================================

def _patch_bank():
    """Patch Borrow to log every loan."""
    import econsim_trade_money as _tm
    orig_borrow = _tm.Bank.Borrow
    def patched_borrow(self, t, agent, amount):
        result = orig_borrow(self, t, agent, amount)
        if amount > 0:
            borrow_events.append((t, agent.id, amount, 'borrow'))
        return result
    _tm.Bank.Borrow = patched_borrow


def _patch_lifecycle():
    """Patch death and inheritance in econsim_live."""
    import econsim_live as _lm

    # ---- Patch death to record pre-mortem state ----
    orig_death = _lm._handle_death
    def patched_death(ctx, t, agent, agents):
        wealth = agent.cash + ctx.bank.deposits.get(agent, 0)
        debt = sum(l.principle - l.principle_paid for l in agent.loans) if agent.loans else 0
        total_val = wealth + sum(
            agent.inventory[g.value] * ctx.recipes.get(g, {}).get('price', 0)
            for g in [Goods.food, Goods.wood, Goods.furniture]
        ) - debt
        # Store externally since Agent uses __slots__
        pre_mortem_state[agent.id] = {
            'total': total_val,
            'wealth': wealth,
            'debt': debt,
        }
        return orig_death(ctx, t, agent, agents)
    _lm._handle_death = patched_death

    # ---- Patch wealth inheritance ----
    orig_wealth = _lm._handle_wealth_inheritance
    def patched_wealth(ctx, t, agent, living_descendants):
        state = pre_mortem_state.pop(agent.id, {})
        wealth_val = state.get('wealth', 0)
        debt_val = state.get('debt', 0)
        total_val = state.get('total', 0)
        heir_ids = [d.id for d in living_descendants]
        went_to_gov = (len(living_descendants) == 0 and ctx.default_gov is not None)
        output = agent.output
        if hasattr(agent, 'is_trader') and agent.is_trader:
            prof_name = 'Trader'
        elif hasattr(agent, 'is_corporation') and agent.is_corporation:
            prof_name = 'Corp'
        elif hasattr(agent, 'is_government') and agent.is_government:
            prof_name = 'Gov'
        else:
            prof_name = PROF_NAMES.get(output, str(output))
        inheritance_events.append((
            t, agent.id, prof_name, total_val,
            wealth_val, debt_val, heir_ids, went_to_gov,
        ))
        return orig_wealth(ctx, t, agent, living_descendants)
    _lm._handle_wealth_inheritance = patched_wealth


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Wealth Lineage Diagnostic: {time_steps} turns\n")

    # Apply instrumentation
    _patch_bank()
    _patch_lifecycle()

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

    # Track agent names for readability
    agent_names = {}
    for a in region_a.agents + region_b.agents:
        agent_names[a.id] = a.name()
        if hasattr(a, 'parent') and a.parent is not None:
            parent_map[a.id] = a.parent.id

    birth_counter = 0

    for t in range(1, time_steps + 1):
        # Record snapshot for all agents before step
        if t % 10 == 0:
            snap = {}
            for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
                for a in region.agents:
                    w = a.cash + region.bank.deposits.get(a, 0)
                    d = sum(l.principle - l.principle_paid for l in a.loans) if a.loans else 0
                    prof = 'Trader' if getattr(a, 'is_trader', False) else PROF_NAMES.get(a.output, '?')
                    if getattr(a, 'is_government', False):
                        prof = 'Gov'
                    elif getattr(a, 'is_corporation', False):
                        prof = 'Corp'
                    snap[a.id] = (w, d, prof, a.alive)
            wealth_snapshots[t] = snap

        region_a.step(t)
        region_b.step(t)
        sim.process_transport(t, region_a, region_b)
        sim.foreign_sell(t, region_a, region_b)
        sim.foreign_sell(t, region_b, region_a)

        # Track births from new agents
        for a in region_a.agents + region_b.agents:
            if a.id not in agent_names:
                agent_names[a.id] = a.name()
                birth_counter += 1
                if hasattr(a, 'parent') and a.parent is not None:
                    parent_map[a.id] = a.parent.id

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"INTERGENERATIONAL WEALTH TRANSFER SUMMARY")
    print(f"{'='*70}")
    print(f"Total births: {birth_counter}")
    print(f"Total deaths tracked: {len(inheritance_events)}")
    print(f"Total borrow events: {len(borrow_events)}")

    # Compute aggregate flows by profession
    print(f"\n--- Wealth Transfer by Deceased Profession ---")
    prof_totals = defaultdict(lambda: {'count': 0, 'total_wealth': 0, 'to_gov': 0,
                                         'to_heirs': 0, 'debt': 0})
    for evt in inheritance_events:
        t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
        prof_totals[prof]['count'] += 1
        prof_totals[prof]['total_wealth'] += total_val
        prof_totals[prof]['debt'] += debt
        if to_gov:
            prof_totals[prof]['to_gov'] += total_val
        else:
            prof_totals[prof]['to_heirs'] += total_val

    for prof, data in sorted(prof_totals.items(), key=lambda x: -x[1]['total_wealth']):
        print(f"  {prof:>12}: {data['count']:>3} deaths, "
              f"total_wealth=${data['total_wealth']:>8.0f}, "
              f"debt=${data['debt']:>8.0f}, "
              f"to_gov=${data['to_gov']:>8.0f}, "
              f"to_heirs=${data['to_heirs']:>8.0f}")

    # Top wealth accumulators (final snapshot)
    if time_steps in wealth_snapshots:
        final_snap = wealth_snapshots[time_steps]
        print(f"\n--- Top 10 Net Worth Holders (Turn {time_steps}) ---")
        sorted_ids = sorted(final_snap.keys(),
                            key=lambda aid: final_snap[aid][0] - final_snap[aid][1],
                            reverse=True)
        for i, aid in enumerate(sorted_ids[:10]):
            w, d, prof, alive = final_snap[aid]
            net = w - d
            name = agent_names.get(aid, f"agent{aid}")
            tags = []
            if prof == 'Trader': tags.append('TRADER')
            if prof == 'Corp': tags.append('CORP')
            if prof == 'Gov': tags.append('GOV')
            print(f"  {i+1:>2}. {name:>20} [{prof:>8}] {' '.join(tags):>10} "
                  f"wealth=${w:>8.0f} debt=${d:>8.0f} net=${net:>8.0f} {'ALIVE' if alive else 'DEAD'}")

    # Wealth concentration
    if time_steps in wealth_snapshots:
        snap = wealth_snapshots[time_steps]
        vals = sorted([snap[aid][0] - snap[aid][1] for aid in snap], reverse=True)
        total = sum(vals)
        if total > 0:
            n = len(vals)
            top1 = int(n * 0.01) or 1
            top10 = int(n * 0.1) or 1
            print(f"\n--- Wealth Concentration (Turn {time_steps}) ---")
            print(f"  Top 1%:  {sum(vals[:top1]):>10.0f} / {total:>10.0f} = {sum(vals[:top1])/total*100:.1f}%")
            print(f"  Top 10%: {sum(vals[:top10]):>10.0f} / {total:>10.0f} = {sum(vals[:top10])/total*100:.1f}%")

    # Borrowing summary
    print(f"\n--- Borrowing Summary ---")
    total_borrowed = sum(e[2] for e in borrow_events)
    print(f"Total borrowed: ${total_borrowed:.0f} across {len(borrow_events)} loans")
    borrower_totals = defaultdict(float)
    for e in borrow_events:
        borrower_totals[e[1]] += e[2]
    top_borrowers = sorted(borrower_totals.items(), key=lambda x: -x[1])[:5]
    print(f"Top 5 borrowers (by total borrowed):")
    for aid, amt in top_borrowers:
        name = agent_names.get(aid, f"agent{aid}")
        print(f"  {name:>20}: ${amt:>8.0f}")

    # =========================================================================
    # VISUALIZATION
    # =========================================================================

    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgba
        import numpy as np

        fig = plt.figure(figsize=(28, 16))
        fig.suptitle(f"Wealth Lineage Analysis — {time_steps} Turns", fontsize=16)

        # ---- Panel 1: Wealth Flow by Profession (horizontal stacked bar) ----
        ax1 = fig.add_axes([0.03, 0.55, 0.30, 0.40])
        ax1.set_title("Total Wealth Transferred at Death\nby Deceased Profession", fontsize=11)

        prof_names_list = [p for p, _ in sorted(prof_totals.items(), key=lambda x: -x[1]['total_wealth'])]
        y_pos = np.arange(len(prof_names_list))
        bar_data = []
        for p in prof_names_list:
            d = prof_totals[p]
            bar_data.append((d['to_heirs'], d['to_gov'], d['debt']))

        heirs_vals = [x[0] for x in bar_data]
        gov_vals = [x[1] for x in bar_data]
        debt_vals = [x[2] for x in bar_data]

        ax1.barh(y_pos, heirs_vals, height=0.6, label='To Heirs', color='steelblue')
        ax1.barh(y_pos, gov_vals, left=heirs_vals, height=0.6, label='To Gov', color='gold')
        ax1.barh(y_pos, [-x for x in debt_vals],
                 height=0.6, label='Debt (inherited)', color='crimson', alpha=0.5)
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(prof_names_list, fontsize=9)
        ax1.set_xlabel("Total Wealth ($)")
        ax1.legend(fontsize=8)
        ax1.axvline(x=0, color='black', linewidth=0.5)

        # ---- Panel 2: Borrowing Over Time ----
        ax2 = fig.add_axes([0.03, 0.05, 0.30, 0.40])
        ax2.set_title("Borrowing Activity Over Time", fontsize=11)

        borrow_by_turn = defaultdict(float)
        borrow_count_by_turn = defaultdict(int)
        for evt in borrow_events:
            t, aid, amt, reason = evt
            borrow_by_turn[t] += amt
            borrow_count_by_turn[t] += 1

        turns = sorted(borrow_by_turn.keys())
        amounts = [borrow_by_turn[t] for t in turns]
        counts = [borrow_count_by_turn[t] for t in turns]

        if turns:
            ax2_2 = ax2.twinx()
            ax2.bar(turns, amounts, width=0.8, color='crimson', alpha=0.6, label='Total borrowed')
            ax2_2.plot(turns, counts, color='darkred', marker='.', markersize=2,
                       linewidth=0.5, label='Loan count')
            ax2.set_xlabel("Turn")
            ax2.set_ylabel("Total $ Borrowed", color='crimson')
            ax2_2.set_ylabel("Number of Loans", color='darkred')
            ax2.legend(fontsize=8, loc='upper left')
            ax2_2.legend(fontsize=8, loc='upper right')

        # ---- Panel 3: Top Lineages Wealth Over Time ----
        ax3 = fig.add_axes([0.38, 0.55, 0.58, 0.40])
        ax3.set_title("Wealth of Top Founding Lineages\n"
                       "(founder + all descendants, cumulative net worth)",
                       fontsize=11)

        # Identify founding agents (no parent recorded)
        founding_ids = set()
        for a in region_a.agents + region_b.agents:
            if getattr(a, 'is_trader', False) or getattr(a, 'is_government', False):
                continue
            if a.id not in parent_map:
                founding_ids.add(a.id)

        # Compute lineage wealth at end
        snap_turns = sorted(wealth_snapshots.keys())
        founder_wealth_at_end = {}
        for fid in list(founding_ids)[:50]:  # limit scan
            lineage_ids = set([fid])
            stack = [fid]
            while stack:
                cur = stack.pop()
                kids = [c for c, p in parent_map.items() if p == cur and c not in lineage_ids]
                for k in kids:
                    lineage_ids.add(k)
                    stack.append(k)
            total_desc_wealth = 0
            if time_steps in wealth_snapshots:
                snap = wealth_snapshots[time_steps]
                for aid in lineage_ids:
                    if aid in snap:
                        w, d, prof, alive = snap[aid]
                        if alive:
                            total_desc_wealth += (w - d)
            if total_desc_wealth > 0:
                founder_wealth_at_end[fid] = total_desc_wealth

        top_founders = sorted(founder_wealth_at_end.keys(),
                              key=lambda x: -founder_wealth_at_end[x])[:8]

        lineage_colors = plt.cm.tab10(np.linspace(0, 1, len(top_founders)))
        linestyle_cycle = ['-', '--', ':', '-.']

        for idx, fid in enumerate(top_founders):
            lineage_ids = set([fid])
            stack = [fid]
            while stack:
                cur = stack.pop()
                kids = [c for c, p in parent_map.items() if p == cur and c not in lineage_ids]
                for k in kids:
                    lineage_ids.add(k)
                    stack.append(k)

            series = []
            for turn in snap_turns:
                if turn in wealth_snapshots:
                    snap = wealth_snapshots[turn]
                    total_lineage = sum(max(0, snap.get(aid, (0,0,'',False))[0] - snap.get(aid, (0,0,'',False))[1])
                                        for aid in lineage_ids if snap.get(aid, (0,0,'',False))[3])
                    series.append(total_lineage)
                else:
                    series.append(0)

            if max(series) > 10:
                color = lineage_colors[idx % len(lineage_colors)]
                ls = linestyle_cycle[idx // len(lineage_colors) % len(linestyle_cycle)]
                name = agent_names.get(fid, f"agent{fid}")
                ax3.plot(snap_turns, series, color=color, linestyle=ls,
                         linewidth=1.2 + 0.3 * (8 - idx),
                         label=f"#{idx+1} {name} (${founder_wealth_at_end[fid]:.0f})",
                         alpha=0.8)

        ax3.set_xlabel("Turn")
        ax3.set_ylabel("Cumulative Lineage Net Worth ($)")
        ax3.set_yscale('symlog')
        ax3.axhline(y=0, color='gray', linewidth=0.5)
        ax3.legend(fontsize=7, loc='upper left', ncol=1)

        # ---- Panel 4: Death Event Scatter (wealth at death over time) ----
        ax4 = fig.add_axes([0.38, 0.05, 0.30, 0.40])
        ax4.set_title("Death Events\n(● = to heirs, ★ = to gov, size = total wealth)",
                       fontsize=11)

        prof_marker_colors = {
            'Food': 'green', 'Wood': 'red', 'Furniture': 'blue',
            'Gov': 'gold', 'Trader': 'orange', 'Corp': 'purple',
            '?': 'gray',
        }

        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            size = max(10, min(300, total_val / 5))
            marker = '*' if to_gov else 'o'
            color = 'gold' if to_gov else prof_marker_colors.get(prof, 'gray')
            ax4.scatter(t, total_val, s=size, c=color, marker=marker,
                       alpha=0.6, edgecolors='black', linewidth=0.3)

        ax4.set_xlabel("Turn")
        ax4.set_ylabel("Total Value at Death ($)")
        ax4.set_yscale('symlog')
        ax4.axhline(y=0, color='gray', linewidth=0.5)

        patches = []
        for pname, c in prof_marker_colors.items():
            patches.append(plt.Line2D([0], [0], marker='o', color='w',
                                      markerfacecolor=c, markersize=6, label=pname))
        patches.append(plt.Line2D([0], [0], marker='*', color='w',
                                   markerfacecolor='gold', markersize=8, label='→ Gov'))
        ax4.legend(handles=patches, fontsize=7, loc='upper left')

        # ---- Panel 5: Gov Inheritance by Profession ----
        ax5 = fig.add_axes([0.72, 0.05, 0.25, 0.40])
        ax5.set_title("Wealth Inherited by Government\n(from childless agents by profession)",
                       fontsize=11)

        gov_inheritance_by_prof = defaultdict(float)
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if to_gov:
                gov_inheritance_by_prof[prof] += total_val

        if gov_inheritance_by_prof:
            profs = list(gov_inheritance_by_prof.keys())
            vals = [gov_inheritance_by_prof[p] for p in profs]
            colors = [prof_marker_colors.get(p, 'gray') for p in profs]
            ax5.barh(range(len(profs)), vals, color=colors, height=0.6)
            ax5.set_yticks(range(len(profs)))
            ax5.set_yticklabels(profs, fontsize=9)
            ax5.set_xlabel("Total $ Inherited by Gov")

        plt.tight_layout()
        plt.savefig("wealth_lineage.png", dpi=150)
        plt.close(fig)
        print(f"\nPlot saved to wealth_lineage.png")

    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
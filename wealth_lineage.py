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

inheritance_events = []
borrow_events = []
parent_map = {}
pre_mortem_state = {}
wealth_snapshots = {}

PROF_NAMES = {
    Goods.food: 'Food',
    Goods.wood: 'Wood',
    Goods.furniture: 'Furniture',
    Goods.gov: 'Gov',
}

PROF_COLORS = {
    'Food': '#2ecc71', 'Wood': '#e74c3c', 'Furniture': '#3498db',
    'Trader': '#f39c12', 'Corp': '#9b59b6', 'Gov': '#f1c40f',
    '?': '#95a5a6',
}


# =============================================================================
# Instrumentation (monkey-patches)
# =============================================================================

def _patch_bank():
    import econsim_trade_money as _tm
    orig_borrow = _tm.Bank.Borrow
    def patched_borrow(self, t, agent, amount):
        result = orig_borrow(self, t, agent, amount)
        if amount > 0:
            borrow_events.append((t, agent.id, amount, 'borrow'))
        return result
    _tm.Bank.Borrow = patched_borrow


def _patch_lifecycle():
    import econsim_live as _lm

    orig_death = _lm._handle_death
    def patched_death(ctx, t, agent, agents):
        wealth = agent.cash + ctx.bank.deposits.get(agent, 0)
        debt = sum(l.principle - l.principle_paid for l in agent.loans) if agent.loans else 0
        total_val = wealth + sum(
            agent.inventory[g.value] * ctx.recipes.get(g, {}).get('price', 0)
            for g in [Goods.food, Goods.wood, Goods.furniture]
        ) - debt
        pre_mortem_state[agent.id] = {'total': total_val, 'wealth': wealth, 'debt': debt}
        return orig_death(ctx, t, agent, agents)
    _lm._handle_death = patched_death

    orig_wealth = _lm._handle_wealth_inheritance
    def patched_wealth(ctx, t, agent, living_descendants):
        state = pre_mortem_state.pop(agent.id, {})
        wealth_val = state.get('wealth', 0)
        debt_val = state.get('debt', 0)
        total_val = state.get('total', 0)
        heir_ids = [d.id for d in living_descendants]
        went_to_gov = (len(living_descendants) == 0 and ctx.default_gov is not None)
        output = agent.output
        if getattr(agent, 'is_trader', False): prof_name = 'Trader'
        elif getattr(agent, 'is_corporation', False): prof_name = 'Corp'
        elif getattr(agent, 'is_government', False): prof_name = 'Gov'
        else: prof_name = PROF_NAMES.get(output, str(output))
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

    agent_names = {}
    for a in region_a.agents + region_b.agents:
        agent_names[a.id] = a.name()
        if hasattr(a, 'parent') and a.parent is not None:
            parent_map[a.id] = a.parent.id

    birth_counter = 0

    for t in range(1, time_steps + 1):
        if t % 10 == 0:
            snap = {}
            for rname, region in [('Region_A', region_a), ('Region_B', region_b)]:
                for a in region.agents:
                    w = a.cash + region.bank.deposits.get(a, 0)
                    d = sum(l.principle - l.principle_paid for l in a.loans) if a.loans else 0
                    prof = 'Trader' if getattr(a, 'is_trader', False) else PROF_NAMES.get(a.output, '?')
                    if getattr(a, 'is_government', False): prof = 'Gov'
                    elif getattr(a, 'is_corporation', False): prof = 'Corp'
                    snap[a.id] = (w, d, prof, a.alive)
            wealth_snapshots[t] = snap

        region_a.step(t)
        region_b.step(t)
        sim.process_transport(t, region_a, region_b)
        sim.foreign_sell(t, region_a, region_b)
        sim.foreign_sell(t, region_b, region_a)

        for a in region_a.agents + region_b.agents:
            if a.id not in agent_names:
                agent_names[a.id] = a.name()
                birth_counter += 1
                if hasattr(a, 'parent') and a.parent is not None:
                    parent_map[a.id] = a.parent.id

    # =========================================================================
    # ANALYSIS & VISUALIZATION
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"INTERGENERATIONAL WEALTH TRANSFER SUMMARY")
    print(f"{'='*70}")
    print(f"Total births: {birth_counter}")
    print(f"Total deaths tracked: {len(inheritance_events)}")
    print(f"Total borrow events: {len(borrow_events)}")

    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
        from matplotlib.colors import to_rgba
        import numpy as np

        # =========================================================================
        # Build unified tree of ALL agents
        # =========================================================================

        snap_final = wealth_snapshots.get(time_steps, {})

        # Collect every agent ID that ever existed (from parent_map + snapshots)
        all_agent_ids = set(parent_map.keys())
        for aids in parent_map.values():
            all_agent_ids.add(aids)
        for snap in wealth_snapshots.values():
            for aid in snap:
                all_agent_ids.add(aid)

        # Determine profession, wealth, alive status for every agent
        agent_info = {}
        for aid in all_agent_ids:
            prof = '?'
            wealth = 0
            alive = True
            debt = 0
            if aid in snap_final:
                w, d, prof, alive = snap_final[aid]
                wealth = w - d  # net worth
            # Override with inheritance data for deceased
            for evt in inheritance_events:
                if evt[1] == aid and evt[3] != 0:
                    wealth = evt[3]
                    prof = evt[2]
                    alive = False
                    debt = evt[5]
                    break
            agent_info[aid] = (wealth, prof, alive, debt)

        # Identify founding agents (no parent recorded, or parent not in our set)
        # Walk up through parent_map to find founders
        def find_root(aid):
            visited = set()
            cur = aid
            while cur in parent_map and cur not in visited:
                visited.add(cur)
                cur = parent_map[cur]
            return cur

        all_roots = set()
        for aid in all_agent_ids:
            r = find_root(aid)
            if r is not None:
                all_roots.add(r)

        # Build all nodes in one pass using BFS from all roots
        all_nodes = {}
        max_global_gen = 0
        x_global_counter = [0]

        # Process each root's tree independently, but interleave x positions
        for root_id in sorted(all_roots):
            # BFS to get depth
            bfs_q = [(root_id, 0)]
            bfs_seen = set()
            local_nodes = {}

            while bfs_q:
                aid, gen = bfs_q.pop(0)
                if aid in bfs_seen:
                    continue
                bfs_seen.add(aid)
                max_global_gen = max(max_global_gen, gen)
                kids = sorted([c for c, p in parent_map.items() if p == aid],
                              key=lambda k: agent_info.get(k, (0,'',True,0))[0], reverse=True)
                for k in kids:
                    bfs_q.append((k, gen + 1))

            # Assign x positions with pre-order traversal
            assign_seen = set()
            def assign_x_preorder(aid, gen):
                if aid in assign_seen:
                    return
                assign_seen.add(aid)
                kids = sorted([c for c, p in parent_map.items() if p == aid],
                              key=lambda k: agent_info.get(k, (0,'',True,0))[0], reverse=True)
                # Assign this node now
                w, prof, alive, debt = agent_info.get(aid, (0, '?', True, 0))
                x = x_global_counter[0]
                x_global_counter[0] += 1
                all_nodes[aid] = {
                    'gen': gen + 1,
                    'x': x,
                    'kids': kids,
                    'wealth': w,
                    'prof': prof,
                    'name': agent_names.get(aid, f'a{aid}'),
                    'alive': alive,
                    'debt': debt,
                }
                for k in kids:
                    assign_x_preorder(k, gen + 1)

            assign_x_preorder(root_id, 0)

        max_gen_global = max_global_gen

        # =========================================================================
        # FIGURE
        # =========================================================================

        # Collect wealth values for sizing
        all_wealth_vals = [nd['wealth'] for nd in all_nodes.values() if nd['wealth'] > 0]
        max_w = max(all_wealth_vals) if all_wealth_vals else 1

        def node_size(wealth):
            if wealth <= 0:
                return 10
            base = math.log(max(1.001, max_w))
            norm = math.log(max(1.001, wealth)) / base
            # Exponential scaling: tiny for small wealth, huge for top wealth
            return 10 + norm ** 1.5 * 500

        # Compute layout dimensions
        max_gen = max((nd['gen'] for nd in all_nodes.values()), default=1)
        total_nodes = len(all_nodes)

        # Figure: extra tall to show generation structure clearly.
        fig_h = max(24, min(80, max_gen * 1.8))
        fig_w = max(20, min(50, total_nodes / max_gen * 0.3))
        fig = plt.figure(figsize=(fig_w, fig_h))
        fig.suptitle(f"Wealth Lineage — All {total_nodes} Agents (300 turns)",
                     fontsize=16, y=0.98)

        # Scale x: use full figure width
        max_x_pos = max((nd['x'] for nd in all_nodes.values()), default=1)
        x_margin = max_x_pos * 0.02
        x_left = -x_margin
        x_right = max_x_pos + x_margin

        # ---- Main panel spans full width ----
        ax_tree = fig.add_axes([0.01, 0.03, 0.98, 0.92])
        ax_tree.set_xlim(x_left, x_right)
        ax_tree.set_ylim(-0.5, max_gen + 1.0)
        # Remove aspect equal to allow stretching both axes to fill
        ax_tree.axis('off')
        ax_tree.set_title(f"All {total_nodes} Agents (300 turns): "
                          f"node size = net worth, color = profession, "
                          f"opacity = alive/dead",
                          fontsize=13, loc='left')

        # Plot birth edges (thin gray) — use nd['x'] directly as the x coordinate
        for aid, nd in all_nodes.items():
            sx = nd['x']
            sy = nd['gen']
            for kid_id in nd['kids']:
                if kid_id in all_nodes:
                    kid = all_nodes[kid_id]
                    ex = kid['x']
                    ey = kid['gen']
                    ax_tree.annotate('',
                        xy=(ex, ey), xytext=(sx, sy),
                        arrowprops=dict(arrowstyle='->',
                                       color='lightgray',
                                       lw=0.3,
                                       connectionstyle='arc3,rad=0.1'),
                    )

        # Plot inheritance edges (bold, colored by deceased profession)
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if total_val <= 0:
                continue
            if aid not in all_nodes:
                continue
            src = all_nodes[aid]
            sx = src['x']
            sy = src['gen']

            for hid in heirs:
                if hid in all_nodes:
                    dst = all_nodes[hid]
                    ex = dst['x']
                    ey = dst['gen']
                    lw = max(0.5, min(5, total_val / 200))
                    color = PROF_COLORS.get(prof, '#888')
                    ax_tree.annotate('',
                        xy=(ex, ey), xytext=(sx, sy),
                        arrowprops=dict(arrowstyle='->',
                                       color=color,
                                       lw=lw,
                                       connectionstyle='arc3,rad=0.2'),
                    )

            if to_gov:
                gov_x = x_right - 1
                gov_y = 0
                lw = max(0.5, min(5, total_val / 200))
                ax_tree.annotate('',
                    xy=(gov_x, gov_y), xytext=(sx, sy),
                    arrowprops=dict(arrowstyle='->',
                                   color='gold',
                                   lw=lw,
                                   connectionstyle='arc3,rad=0.2'),
                )

        # Plot all nodes
        for aid, nd in all_nodes.items():
            x = nd['x']
            y = nd['gen']
            prof = nd['prof']
            w = nd['wealth']
            name = nd['name']
            color = PROF_COLORS.get(prof, '#888')
            size = node_size(w)
            alpha = 0.9 if nd['alive'] else 0.4
            edge = 'black' if nd['alive'] else '#666'
            marker = 'o'
            if prof == 'Gov':
                marker = 'D'
                color = 'gold'
            elif prof == 'Trader':
                marker = 's'
            elif prof == 'Corp':
                marker = '^'
            ax_tree.scatter(x, y, s=size, c=color, alpha=alpha,
                           edgecolors=edge, linewidth=0.3, marker=marker, zorder=5)

            # Label larger nodes
            if size > 30:
                short_name = name.split('-')[0] if '-' in name else name
                ax_tree.text(x, y - 0.25, f'{short_name}\n${w:.0f}',
                            fontsize=4 + size / 50, ha='center',
                            va='top', alpha=0.8)

        # Government diamonds
        gov_x = x_right - 1
        for label, gw in [('Gov A', 22721), ('Gov B', 4836)]:
            ax_tree.scatter(gov_x, 0.5 if label == 'Gov B' else 0,
                           s=node_size(gw), c='gold',
                           alpha=0.9, edgecolors='black', linewidth=1.5,
                           marker='D', zorder=6)
            ax_tree.text(gov_x, -0.5 if label == 'Gov B' else -0.3,
                        f'{label}\n${gw:.0f}',
                        fontsize=8, ha='center', va='top', fontweight='bold')

        # =========================================================================
        # LEGEND
        # =========================================================================
        leg_x = x_left + (x_right - x_left) * 0.02
        leg_y = max_gen + 0.3  # above the top generation
        leg_items = []
        col = 0
        # Use ax_tree.text for legend items to avoid cluttering with patches
        lines = [
            # (label, marker, marker_color, edge_color, marker_size, shape)
            ("─── Gray arrow: parent → child (birth)", None, None, None, None, None),
            ("─── Colored arrow: deceased → heir (inheritance, width ∝ $)", None, None, None, None, None),
            ("─── Gold arrow: estate → Government (no heirs)", None, None, None, None, None),
            ("", None, None, None, None, None),  # blank line
        ]
        profession_entries = [
            ("○ Circle = Food (green)", 'o', '#2ecc71'),
            ("○ Circle = Wood (red)", 'o', '#e74c3c'),
            ("○ Circle = Furniture (blue)", 'o', '#3498db'),
            ("□ Square = Trader (orange)", 's', '#f39c12'),
            ("△ Triangle = Corp (purple)", '^', '#9b59b6'),
            ("◇ Diamond = Gov (gold)", 'D', '#f1c40f'),
        ]

        style_entries = [
            "Opacity: 0.9 = alive, 0.4 = dead",
            "Node size = net worth (log scale)",
            "Label: agent name + $net worth (labeled if size > 30pt)",
        ]

        # Draw legend items as text with inline symbol annotations
        leg_y_start = leg_y
        x_start = leg_x
        y_cursor = leg_y_start

        # Section 1: Edge types
        ax_tree.text(x_start, y_cursor, "EDGES:", fontsize=9, fontweight='bold',
                     va='bottom', ha='left', alpha=0.8)
        y_cursor -= 0.35
        ax_tree.text(x_start, y_cursor, "– Gray arrow: parent → child (birth)",
                     fontsize=8, va='center', ha='left', alpha=0.8)
        y_cursor -= 0.25
        ax_tree.text(x_start, y_cursor, "– Bold colored: deceased → heir (inheritance, width ∝ $)",
                     fontsize=8, va='center', ha='left', alpha=0.8)
        y_cursor -= 0.25
        ax_tree.text(x_start, y_cursor, "– Gold arrow: estate → Gov (no heirs)",
                     fontsize=8, va='center', ha='left', alpha=0.8)
        y_cursor -= 0.40

        # Section 2: Node shapes / professions
        ax_tree.text(x_start, y_cursor, "NODES:", fontsize=9, fontweight='bold',
                     va='bottom', ha='left', alpha=0.8)
        y_cursor -= 0.35
        for label, marker, mcolor in profession_entries:
            ax_tree.scatter(x_start + 4, y_cursor, s=80, c=mcolor,
                           alpha=0.9, edgecolors='black', linewidth=0.3,
                           marker=marker, zorder=10)
            ax_tree.text(x_start + 8, y_cursor, label, fontsize=8,
                        va='center', ha='left', alpha=0.8)
            y_cursor -= 0.28
        y_cursor -= 0.12

        # Section 3: Style
        ax_tree.text(x_start, y_cursor, "STYLE:", fontsize=9, fontweight='bold',
                     va='bottom', ha='left', alpha=0.8)
        y_cursor -= 0.35
        for line in style_entries:
            ax_tree.text(x_start, y_cursor, "– " + line, fontsize=8,
                        va='center', ha='left', alpha=0.8)
            y_cursor -= 0.25

        # ---- Print summary stats ----
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
                  f"total=${data['total_wealth']:>8.0f}, "
                  f"debt=${data['debt']:>8.0f}, "
                  f"to_gov=${data['to_gov']:>8.0f}, "
                  f"to_heirs=${data['to_heirs']:>8.0f}")

        # Top 10 net worth at end
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
                print(f"  {i+1:>2}. {name:>20} [{prof:>8}] "
                      f"net=${net:>8.0f} {'ALIVE' if alive else 'DEAD'}")

        # Borrowing summary
        print(f"\n--- Borrowing Summary ---")
        total_borrowed = sum(e[2] for e in borrow_events)
        print(f"Total borrowed: ${total_borrowed:.0f} across {len(borrow_events)} loans")

        plt.savefig("wealth_lineage.png", dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"\nPlot saved to wealth_lineage.png")

    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
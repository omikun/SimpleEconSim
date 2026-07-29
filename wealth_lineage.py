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

        # ---- Identify top lineages ----
        founding_ids = set()
        for a in region_a.agents + region_b.agents:
            if getattr(a, 'is_government', False):
                continue
            if a.id not in parent_map:
                founding_ids.add(a.id)

        def get_lineage(fid):
            ids = set([fid])
            stack = [fid]
            while stack:
                cur = stack.pop()
                kids = [c for c, p in parent_map.items() if p == cur and c not in ids]
                for k in kids:
                    ids.add(k)
                    stack.append(k)
            return ids

        founder_wealth_at_end = {}
        for fid in list(founding_ids)[:200]:
            lineage_ids = get_lineage(fid)
            total = 0
            if time_steps in wealth_snapshots:
                snap = wealth_snapshots[time_steps]
                for aid in lineage_ids:
                    if aid in snap:
                        w, d, prof, alive = snap[aid]
                        if alive and not prof == 'Gov':
                            total += (w - d)
            if total > 0:
                founder_wealth_at_end[fid] = total

        # Top 5 lineages + their full member data
        top_founders = sorted(founder_wealth_at_end.keys(),
                              key=lambda x: -founder_wealth_at_end[x])[:5]

        # Collect all lineage nodes
        lineage_ids = set()
        lineage_founder_map = {}
        for fid in top_founders:
            lineage_ids.update(get_lineage(fid))
            lineage_founder_map[fid] = get_lineage(fid)

        # Also add the government nodes (immortal, always present)
        gov_a = region_a.gov.agent
        gov_b = region_b.gov.agent

        # =========================================================================
        # Build genealogical tree layout
        # =========================================================================
        # For each top lineage, compute generation depth and sibling ordering

        def compute_tree(fid):
            """Return dict of aid -> {gen, x_offset, children, wealth, prof, name, alive}"""
            nodes = {}
            max_gen = 0

            # BFS for generation depth
            queue = [(fid, 0)]
            bfs_visited = set()
            all_members = list(lineage_founder_map.get(fid, [fid]))
            member_set = set(all_members)

            snap_final = wealth_snapshots.get(time_steps, {})

            # Collect final wealth and profession for all lineage members
            final_wealth = {}
            final_prof = {}
            final_debt = {}
            final_alive = {}

            for aid in all_members:
                if aid in snap_final:
                    w, d, prof, alive = snap_final[aid]
                    final_wealth[aid] = w - d
                    final_prof[aid] = prof
                    final_alive[aid] = alive
                    final_debt[aid] = d
                # Also check inheritance events (wealth at death for deceased)
                for evt in inheritance_events:
                    if evt[1] == aid and evt[3] != 0:
                        if aid not in final_wealth or final_wealth[aid] == 0:
                            final_wealth[aid] = evt[3]
                            final_prof[aid] = evt[2]
                            final_alive[aid] = False
                            final_debt[aid] = evt[5]
                            break
                # Defaults
                if aid not in final_wealth:
                    final_wealth[aid] = 0
                    final_prof[aid] = '?'
                    final_alive[aid] = True
                    final_debt[aid] = 0

            # BFS pass: compute generation depth
            while queue:
                aid, gen = queue.pop(0)
                if aid in bfs_visited:
                    continue
                bfs_visited.add(aid)
                max_gen = max(max_gen, gen)
                kids = [c for c, p in parent_map.items() if p == aid and c in member_set]
                for k in kids:
                    queue.append((k, gen + 1))

            # Assign x positions via in-order traversal (separate visited set!)
            assign_visited = set()
            x_counter = [0]
            def assign_x(aid, gen):
                if aid in assign_visited:
                    return
                assign_visited.add(aid)
                kids = sorted([c for c, p in parent_map.items() if p == aid and c in member_set],
                              key=lambda k: final_wealth.get(k, 0), reverse=True)
                for k in kids:
                    assign_x(k, gen + 1)
                # Midpoint of children's x positions, or a new slot
                child_positions = [nodes.get(k, {}).get('x', x_counter[0]) for k in kids]
                if child_positions:
                    x = sum(child_positions) / len(child_positions)
                else:
                    x = x_counter[0]
                    x_counter[0] += 1
                nodes[aid] = {
                    'gen': gen + 1,  # +1 so root is at y=1
                    'x': x,
                    'kids': kids,
                    'wealth': final_wealth.get(aid, 0),
                    'prof': final_prof.get(aid, '?'),
                    'name': agent_names.get(aid, f'a{aid}'),
                    'alive': final_alive.get(aid, True),
                    'debt': final_debt.get(aid, 0),
                }

            assign_x(fid, 0)
            return nodes, max_gen + 1

        # Build all trees
        all_trees = {}  # fid -> nodes dict
        max_gen_global = 0
        for fid in top_founders:
            tree, mg = compute_tree(fid)
            all_trees[fid] = tree
            max_gen_global = max(max_gen_global, mg)

        # =========================================================================
        # FIGURE
        # =========================================================================

        fig = plt.figure(figsize=(36, 20))
        fig.suptitle(f"Wealth Lineage — Family Tree & Inheritance Flows "
                     f"(top {len(top_founders)} founding lineages shown)",
                     fontsize=18, y=0.97)

        # Layout: each lineage gets its own x band, but within the same gen row
        lineage_spacing = 3.0
        x_offsets = {}
        for idx, fid in enumerate(top_founders):
            x_offsets[fid] = idx * lineage_spacing

        # Collect all agent wealth ranges for sizing
        all_wealth_vals = []
        for tree in all_trees.values():
            for aid, nd in tree.items():
                v = nd['wealth']
                if v > 0:
                    all_wealth_vals.append(v)
        if not all_wealth_vals:
            all_wealth_vals = [1]

        min_w = min(all_wealth_vals)
        max_w = max(all_wealth_vals)

        def node_size(wealth):
            """Map wealth to area in points^2."""
            if wealth <= 0:
                return 20
            base = math.log(max(1.001, max_w))
            norm = math.log(max(1.001, wealth)) / base
            return 30 + norm * 400

        # ---- Main panel: Genealogical Tree ----
        ax_tree = fig.add_axes([0.02, 0.08, 0.68, 0.85])
        max_x = max(x_offsets.values()) + 5.0
        ax_tree.set_xlim(-1, max_x)
        ax_tree.set_ylim(-0.5, max_gen_global + 2)
        ax_tree.set_aspect('equal')
        ax_tree.axis('off')
        ax_tree.set_title("Wealth Flow Through Generations\n"
                          "(node size = net worth • color = profession • "
                          "→ birth • → inheritance)",
                          fontsize=13, loc='left')

        # Max nodes per generation for height scaling
        max_nodes_in_gen = defaultdict(int)
        for fid, tree in all_trees.items():
            for aid, nd in tree.items():
                max_nodes_in_gen[nd['gen']] = max(max_nodes_in_gen[nd['gen']], 1)

        # Plot birth edges (thin)
        for fid, tree in all_trees.items():
            xoff = x_offsets[fid]
            for aid, nd in tree.items():
                for kid_id in nd['kids']:
                    if kid_id in tree:
                        kid = tree[kid_id]
                        ax_tree.annotate('',
                            xy=(xoff + kid['x'] * 0.4, kid['gen']),
                            xytext=(xoff + nd['x'] * 0.4, nd['gen']),
                            arrowprops=dict(arrowstyle='->',
                                           color='lightgray',
                                           lw=0.5,
                                           connectionstyle='arc3,rad=0.15'),
                        )

        # Plot inheritance edges (bold, colored by deceased profession)
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if total_val <= 0:
                continue
            # Find which lineage this belongs to
            source_lineage = None
            source_node = None
            for fid, tree in all_trees.items():
                if aid in tree:
                    source_lineage = fid
                    source_node = tree.get(aid)
                    break
            if source_node is None:
                continue

            xoff = x_offsets[source_lineage]
            sx = xoff + source_node['x'] * 0.4
            sy = source_node['gen']

            for hid in heirs:
                # Find heir in same tree
                for fid2, tree2 in all_trees.items():
                    if hid in tree2:
                        heir_node = tree2[hid]
                        ex = x_offsets[fid2] + heir_node['x'] * 0.4
                        ey = heir_node['gen']
                        # Bold arrow: width proportional to wealth
                        lw = max(1, min(8, total_val / 100))
                        color = PROF_COLORS.get(prof, '#888')
                        ax_tree.annotate('',
                            xy=(ex, ey), xytext=(sx, sy),
                            arrowprops=dict(arrowstyle='->',
                                           color=color,
                                           lw=lw,
                                           connectionstyle='arc3,rad=0.25'),
                        )
                        # Label with dollar amount at midpoint
                        mx = (sx + ex) / 2
                        my = (sy + ey) / 2 + 0.1
                        ax_tree.text(mx, my, f'${total_val:.0f}',
                                    fontsize=6, color=color,
                                    ha='center', va='bottom',
                                    alpha=0.8)

            if to_gov:
                # Arrow to gov node
                color = PROF_COLORS.get(prof, '#888')
                gov_a_x = -1.0 + max(x_offsets.values()) + 2.0
                gov_a_y = -0.5
                lw = max(1, min(8, total_val / 100))
                ax_tree.annotate('',
                    xy=(gov_a_x, gov_a_y), xytext=(sx, sy),
                    arrowprops=dict(arrowstyle='->',
                                   color='gold',
                                   lw=lw,
                                   connectionstyle='arc3,rad=0.3'),
                )
                ax_tree.text((sx + gov_a_x) / 2, (sy + gov_a_y) / 2 + 0.1,
                            f'${total_val:.0f}', fontsize=6, color='gold',
                            ha='center', va='bottom', alpha=0.8)

        # Plot nodes
        for fid, tree in all_trees.items():
            xoff = x_offsets[fid]
            for aid, nd in tree.items():
                x = xoff + nd['x'] * 0.4
                y = nd['gen']
                w = nd['wealth']
                prof = nd['prof']
                name = nd['name']
                color = PROF_COLORS.get(prof, '#888')
                size = node_size(w)
                if nd['alive']:
                    alpha = 0.95
                    edge = 'black'
                else:
                    alpha = 0.5
                    edge = '#666'
                ax_tree.scatter(x, y, s=size, c=color, alpha=alpha,
                               edgecolors=edge, linewidth=0.5, zorder=5)

                # Label
                if size > 40:
                    label = f"{name.split('-')[0]}\n${w:.0f}"
                    ax_tree.text(x, y - 0.2, label,
                                fontsize=5 + size / 100, ha='center',
                                va='top', alpha=0.9)

        # Government node(s)
        for gov_agent, gx_off, label in [(gov_a, max(x_offsets.values()) + 2.5, 'Gov A'),
                                          (gov_b, max(x_offsets.values()) + 4.0, 'Gov B')]:
            snap_final = wealth_snapshots.get(time_steps, {})
            gw = snap_final.get(gov_agent.id, (0, 0, 'Gov', True))[0]
            ax_tree.scatter(gx_off, -0.5, s=node_size(gw), c='gold',
                           alpha=0.9, edgecolors='black', linewidth=1.5,
                           marker='D', zorder=6)
            ax_tree.text(gx_off, -0.9, f'{label}\n${gw:.0f}',
                        fontsize=9, ha='center', va='top', fontweight='bold')

        # ---- Right panel: Inheritance Sankey (aggregate flows) ----
        ax_sankey = fig.add_axes([0.73, 0.08, 0.25, 0.85])
        ax_sankey.set_title("Aggregate Inheritance Flows\nby Profession (300 turns)",
                           fontsize=13)
        ax_sankey.axis('off')

        # Build flow matrix: source -> dest profession
        flow_matrix = defaultdict(lambda: defaultdict(float))
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if total_val <= 0:
                continue
            if to_gov:
                flow_matrix[prof]['Gov'] += total_val
            else:
                # Determine heir professions
                for hid in heirs:
                    hprof = '?'
                    if hid in wealth_snapshots.get(time_steps, {}):
                        hprof = wealth_snapshots[time_steps][hid][2]
                    else:
                        # Check final snapshot
                        for snap_t in reversed(sorted(wealth_snapshots.keys())):
                            if hid in wealth_snapshots[snap_t]:
                                hprof = wealth_snapshots[snap_t][hid][2]
                                break
                    flow_matrix[prof][hprof] += total_val / max(1, len(heirs))

        all_profs = sorted(set(list(flow_matrix.keys()) + ['Gov']))
        # Remove self-loops for clarity
        n = len(all_profs)
        if n > 1:
            # Draw a simple Sankey-like grid
            cmap = PROF_COLORS
            for i, src in enumerate(all_profs):
                for j, dst in enumerate(all_profs):
                    if src == dst:
                        continue
                    val = flow_matrix.get(src, {}).get(dst, 0)
                    if val < 10:
                        continue
                    # Draw a curved arrow from (i) to (j)
                    y1 = 0.9 - i * 0.12
                    y2 = 0.9 - j * 0.12
                    lw = max(1, min(12, val / 50))
                    color = cmap.get(src, '#888')
                    ax_sankey.annotate('',
                        xy=(0.85, y2), xytext=(0.15, y1),
                        arrowprops=dict(arrowstyle='->',
                                       color=color,
                                       lw=lw,
                                       connectionstyle='arc3,rad=0.15'),
                    )
                    # Label for large flows
                    if val > 100:
                        mx, my = 0.5, (y1 + y2) / 2
                        ax_sankey.text(mx, my + 0.02, f'${val:.0f}',
                                      fontsize=7, color=color,
                                      ha='center', va='bottom')

            # Source labels (left)
            for i, prof in enumerate(all_profs):
                y = 0.9 - i * 0.12
                ax_sankey.text(0.05, y, prof, fontsize=10,
                              color=cmap.get(prof, '#000'),
                              ha='left', va='center', fontweight='bold')
                # Total outflow
                total_out = sum(flow_matrix.get(prof, {}).values())
                ax_sankey.text(0.12, y - 0.03, f'out: ${total_out:.0f}',
                              fontsize=6, color='#666',
                              ha='left', va='top')

            # Destination labels (right)
            for j, prof in enumerate(all_profs):
                y = 0.9 - j * 0.12
                ax_sankey.text(0.88, y, prof, fontsize=10,
                              color=cmap.get(prof, '#000'),
                              ha='right', va='center', fontweight='bold')
                total_in = sum(flow_matrix[s].get(prof, 0) for s in all_profs)
                ax_sankey.text(0.82, y - 0.03, f'in: ${total_in:.0f}',
                              fontsize=6, color='#666',
                              ha='right', va='top')

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
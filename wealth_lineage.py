#!/usr/bin/env python3
"""
Wealth Lineage Diagnostic: trace debt, inheritance, and wealth accumulation
across generations.  Monitors every death/inheritance event, every birth,
and every borrow, then produces a Gantt-style lifespan chart.

Can run standalone:
    python3 wealth_lineage.py [time_steps]

Or as an importable module driven by econsim_two_region.py:
    import wealth_lineage
    wealth_lineage.init_collectors()
    # ... in the simulation loop ...
    wealth_lineage.record_turn(t, region_a, region_b)
    # ... after the loop ...
    wealth_lineage.generate_plots(time_steps, region_a, region_b)
"""

import sys
import random
from collections import defaultdict

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
agent_birth = {}   # aid -> birth_round
death_turn = {}    # aid -> turn of death (if died)
death_causes = {}  # aid -> (turn, prof_name, cause)
agent_names = {}   # aid -> display name
birth_counter = 0

PROF_NAMES = {
    Goods.food: 'Food',
    Goods.wood: 'Wood',
    Goods.furniture: 'Furniture',
    Goods.transport: 'Transport',
    Goods.gov: 'Gov',
}

PROF_COLORS = {
    'Food': '#2ecc71', 'Wood': '#e74c3c', 'Furniture': '#3498db',
    'Transport': '#8e44ad', 'Trader': '#f39c12', 'Corp': '#9b59b6',
    'Gov': '#f1c40f', '?': '#95a5a6',
}

PROF_ORDER = ['Food', 'Wood', 'Furniture', 'Transport', 'Trader', 'Corp', 'Gov', '?']

# Idempotency guard: monkey patches install only once per interpreter
_patched = False


# =============================================================================
# Instrumentation (monkey-patches)
# =============================================================================

def _prof_name(agent):
    """Human-readable profession name for an agent."""
    if getattr(agent, 'is_trader', False):
        return 'Trader'
    if getattr(agent, 'is_corporation', False):
        return 'Corp'
    if getattr(agent, 'is_government', False):
        return 'Gov'
    return PROF_NAMES.get(agent.output, str(agent.output))


def _determine_death_cause(ctx, t, agent, agents):
    """Classify the cause of death before _handle_death mutates the agent."""
    if agent.hungry_steps >= ctx.starve_limit:
        return 'Starved'
    age = agent.age(t)
    wealth = agent.wealth()
    # 105 matches the halved wealth-mortality gate in econsim_live._handle_death
    has_wealth = age < 105 and wealth > ctx.cost_of_living
    crowded = len(agents) > ctx.carrying_capacity * 0.85
    if has_wealth and crowded:
        return 'Age+Wealth+Crowded'
    if has_wealth:
        return 'Age+Wealth'
    if crowded:
        return 'Age+Crowded'
    return 'Age'


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
        cause = _determine_death_cause(ctx, t, agent, agents)
        result = orig_death(ctx, t, agent, agents)
        if result:
            death_turn[agent.id] = t
            death_causes[agent.id] = (t, _prof_name(agent), cause)
        return result
    _lm._handle_death = patched_death

    orig_wealth = _lm._handle_wealth_inheritance
    def patched_wealth(ctx, t, agent, living_descendants):
        state = pre_mortem_state.pop(agent.id, {})
        wealth_val = state.get('wealth', 0)
        debt_val = state.get('debt', 0)
        total_val = state.get('total', 0)
        heir_ids = [d.id for d in living_descendants]
        went_to_gov = (len(living_descendants) == 0 and ctx.default_gov is not None)
        prof_name = _prof_name(agent)
        inheritance_events.append((
            t, agent.id, prof_name, total_val,
            wealth_val, debt_val, heir_ids, went_to_gov,
        ))
        return orig_wealth(ctx, t, agent, living_descendants)
    _lm._handle_wealth_inheritance = patched_wealth


# =============================================================================
# Collector lifecycle (used by both standalone main() and econsim_two_region)
# =============================================================================

def init_collectors():
    """Reset all collectors and install instrumentation (idempotent)."""
    global inheritance_events, borrow_events, parent_map, pre_mortem_state, \
        wealth_snapshots, agent_birth, death_turn, death_causes, \
        agent_names, birth_counter, _patched
    inheritance_events = []
    borrow_events = []
    parent_map = {}
    pre_mortem_state = {}
    wealth_snapshots = {}
    agent_birth = {}
    death_turn = {}
    death_causes = {}
    agent_names = {}
    birth_counter = 0
    if not _patched:
        _patch_bank()
        _patch_lifecycle()
        _patched = True


def record_turn(t, region_a, region_b):
    """Record births, parent links, and wealth snapshots for simulation turn t."""
    global birth_counter
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

    for a in region_a.agents + region_b.agents:
        if a.id not in agent_names:
            agent_names[a.id] = a.name()
            agent_birth[a.id] = a.birth_round
            birth_counter += 1
            if hasattr(a, 'parent') and a.parent is not None:
                parent_map[a.id] = a.parent.id


# =============================================================================
# ANALYSIS & VISUALIZATION
# =============================================================================

def generate_plots(time_steps, region_a, region_b):
    """Produce the Gantt chart, inheritance summary, and death-cause table."""
    print(f"\n{'='*70}")
    print(f"INTERGENERATIONAL WEALTH TRANSFER SUMMARY")
    print(f"{'='*70}")
    print(f"Total births: {birth_counter}")
    print(f"Total deaths tracked: {len(inheritance_events)}")
    print(f"Total borrow events: {len(borrow_events)}")

    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from adjustText import adjust_text

        # =========================================================================
        # Lifespan bars: each agent = bar from birth to death / end of sim
        # =========================================================================

        # Backfill death turns for agents whose death wasn't captured live
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if aid not in death_turn:
                death_turn[aid] = t

        snap_final = wealth_snapshots.get(time_steps, {})

        # Collect every agent ID that ever existed
        all_agent_ids = set(parent_map.keys())
        for aids in parent_map.values():
            all_agent_ids.add(aids)
        for snap in wealth_snapshots.values():
            for aid in snap:
                all_agent_ids.add(aid)
        for aid in death_turn:
            all_agent_ids.add(aid)

        # Agents who died with no living heirs (estate → government)
        no_heir_deaths = set()
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if to_gov and aid in all_agent_ids:
                no_heir_deaths.add(aid)

        # Per-agent data
        agent_data = {}
        for aid in all_agent_ids:
            birth = agent_birth.get(aid, 0)
            end = death_turn.get(aid, time_steps)
            prof = '?'
            wealth = 0
            alive = True
            if aid in snap_final:
                w, d, p, living = snap_final[aid]
                prof = p
                wealth = w - d
                alive = living
            # Override with inheritance data for deceased
            for evt in inheritance_events:
                if evt[1] == aid:
                    wealth = evt[3]
                    prof = evt[2]
                    alive = False
                    break
            agent_data[aid] = {
                'birth': birth, 'end': end, 'prof': prof,
                'wealth': wealth, 'alive': alive,
                'name': agent_names.get(aid, f'a{aid}'),
            }

        # Order rows: group by profession, then by birth round
        groups = defaultdict(list)
        for aid, d in agent_data.items():
            groups[d['prof']].append(aid)
        rows = []  # (aid, y_pos)
        y = 0
        for prof in PROF_ORDER:
            if prof not in groups:
                continue
            for aid in sorted(groups[prof], key=lambda a: agent_data[a]['birth']):
                rows.append((aid, y))
                y += 1
        total_agents = len(rows)
        ymap = {aid: ry for aid, ry in rows}

        # Figure
        fig_h = max(12, min(80, total_agents * 0.16))
        fig_w = 20
        fig = plt.figure(figsize=(fig_w, fig_h))
        fig.suptitle(f"Agent Lifespans — {total_agents} Agents ({time_steps} turns)",
                     fontsize=16, y=0.98)

        ax = fig.add_axes([0.01, 0.04, 0.98, 0.90])
        ax.set_xlim(0, time_steps)
        ax.set_ylim(-0.5, total_agents - 0.5)
        ax.set_yticks([])
        ax.set_xlabel("Turn")
        ax.set_title(f"Each bar = agent lifespan (birth → death / end of sim), "
                     f"colored by profession",
                     fontsize=13, loc='left')

        # Draw bars
        bar_h = 0.75
        for aid, ry in rows:
            d = agent_data[aid]
            start = d['birth']
            width = max(0.5, d['end'] - start)
            color = PROF_COLORS.get(d['prof'], '#888')
            alpha = 0.5 if not d['alive'] else 0.95
            ax.barh(ry, width, left=start, height=bar_h, color=color,
                    alpha=alpha, edgecolor='black', linewidth=0.2, zorder=3)
            # End marker: filled = alive at end, hollow = died
            ax.scatter([d['end']], [ry], s=14,
                       c='black' if d['alive'] else 'none',
                       facecolors='none' if not d['alive'] else 'black',
                       edgecolors='black', linewidths=0.4, zorder=4)
            # Unique symbol: red X = died with no heirs (estate → government)
            if aid in no_heir_deaths:
                ax.scatter([d['end']], [ry], s=30, marker='x',
                           c='red', linewidths=1.0, zorder=5)

        # Inheritance arrows: parent bar end → child bar start
        for evt in inheritance_events:
            t, aid, prof, total_val, wealth, debt, heirs, to_gov = evt
            if total_val <= 0 or aid not in ymap or not heirs:
                continue
            parent_end = death_turn.get(aid, t)
            color = PROF_COLORS.get(prof, '#888')
            lw = max(0.3, min(2.5, total_val / 400))
            for hid in heirs:
                if hid in ymap:
                    ax.annotate('',
                        xy=(agent_data[hid]['birth'], ymap[hid]),
                        xytext=(parent_end, ymap[aid]),
                        arrowprops=dict(arrowstyle='->',
                                       color=color, lw=lw, alpha=0.35,
                                       connectionstyle='arc3,rad=-0.15'),
                        zorder=2)

        # Label top 10% wealthy agents (adjustText avoids overlap)
        n_top = max(5, int(len(all_agent_ids) * 0.10))
        top_aids = sorted(all_agent_ids,
                          key=lambda a: agent_data[a]['wealth'], reverse=True)[:n_top]
        labels = []
        for aid in top_aids:
            d = agent_data[aid]
            if d['wealth'] <= 0:
                continue
            short = d['name'].split('-')[0] if '-' in d['name'] else d['name']
            txt = ax.text(d['end'] + 1, ymap[aid], f'{short} ${d["wealth"]:.0f}',
                          fontsize=7, va='center', ha='left', alpha=0.9)
            labels.append(txt)
        if labels:
            adjust_text(labels, ax=ax, expand=(1.1, 1.3),
                        arrowprops=dict(arrowstyle='-', color='gray', lw=0.3))

        # White separators between profession groups
        last_y_by_prof = {}
        for aid, ry in rows:
            last_y_by_prof[agent_data[aid]['prof']] = ry
        for prof in PROF_ORDER[:-1]:
            ryl = last_y_by_prof.get(prof)
            if ryl is not None:
                ax.axhline(ryl + 0.5, color='white', linewidth=1.5, zorder=5)

        # Legend
        legend_handles = [
            mpatches.Rectangle((0, 0), 1, 1, color=PROF_COLORS[p], alpha=0.85)
            for p in PROF_ORDER if p in groups
        ]
        legend_labels = [
            f"{p} ({len(groups[p])} agents)" for p in PROF_ORDER if p in groups
        ]
        ax.legend(legend_handles, legend_labels, loc='upper right',
                  fontsize=8, title="Profession", title_fontsize=9)

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

        # =====================================================================
        # SECOND PLOT: family-tree / genogram — parent → child lineage with
        # lifespan overlap on the same time axis
        # =====================================================================
        generate_family_plot(time_steps, plt, mpatches, adjust_text)

    except Exception as e:
        print(f"\nCould not generate plots: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # DEATH CAUSES BY PROFESSION
    # =========================================================================
    print(f"\n--- Death Causes by Profession ({time_steps} turns) ---")
    causes = ['Starved', 'Age', 'Age+Wealth', 'Age+Crowded', 'Age+Wealth+Crowded']
    profs = sorted({p for _, p, _ in death_causes.values()})
    header = (" " * 12) + "".join(f"{c:>18}" for c in causes) + f"{'Total':>8}"
    print(header)
    for prof in profs:
        row = f"{prof:>12}"
        total = 0
        for c in causes:
            n = sum(1 for _, p, cc in death_causes.values() if p == prof and cc == c)
            row += f"{n:>18}"
            total += n
        row += f"{total:>8}"
        print(row)


def generate_family_plot(time_steps, plt=None, mpatches=None, adjust_text=None):
    """Draw a family-tree / genogram: who descended from whom, with lifespan
    overlap.

    Uses the already-collected genealogy (parent_map: child -> parent, birth
    round, death turn).  Each lineage (a root with descendants) is drawn as a
    vertical tree: the root bar sits on the top row of its family block,
    children one row below, grandchildren below them, etc.  Bars span
    birth -> death (or end of sim) on the shared time (x) axis, so horizontal
    overlap = agents alive at the same time.  Parent -> child edges drop from
    the parent's bar to the child's birth at the child's row.

    Only lineages with >= 2 members are drawn (singletons have no tree), and
    the display is capped to the largest families when the population is huge
    (the first Gantt chart already shows every agent).
    """
    import matplotlib.pyplot as _plt
    import matplotlib.patches as _mpatches
    plt = plt or _plt
    mpatches = mpatches or _mpatches
    adjust_text = adjust_text  # optional; only used if provided

    # ---- Build the genealogy forest from parent_map ----
    children_of = defaultdict(list)
    parents = {}
    for child, parent in parent_map.items():
        children_of[parent].append(child)
        parents[child] = parent

    all_lineages = set()
    for child in parent_map:
        p = child
        while p in parents:
            p = parents[p]
        all_lineages.add(p)  # root of the chain containing child

    # Members of each lineage (root + descendants), with generation depth
    lineage_members = {}   # root -> {aid: generation}
    member_sets = {}
    for root in all_lineages:
        members = {root: 0}
        queue = [root]
        while queue:
            aid = queue.pop(0)
            gen = members[aid]
            for kid in children_of.get(aid, []):
                members[kid] = gen + 1
                queue.append(kid)
        lineage_members[root] = members
        member_sets[root] = set(members)

    # Sort lineages: by earliest birth in the family, then size (big first)
    def _lineage_order_key(root):
        births = [agent_birth.get(m, 0) for m in lineage_members[root]]
        return (min(births), -len(lineage_members[root]), root)
    ordered_roots = sorted(all_lineages, key=_lineage_order_key)

    # Restrict to lineages with >= 2 members, cap total displayed agents
    MAX_DISPLAY = 600
    candidates = [r for r in ordered_roots if len(lineage_members[r]) >= 2]
    picked = []
    total_shown = 0
    for r in candidates:
        if total_shown + len(lineage_members[r]) > MAX_DISPLAY:
            break
        picked.append(r)
        total_shown += len(lineage_members[r])

    # ---- Row layout: each family is a contiguous block; parents on higher
    # rows than children (generations ordered root-first) ----
    row_of = {}
    agent_row_family = {}
    y_cursor = 0
    family_blocks = []  # (root, y0, y1) for separators
    for root in picked:
        members = lineage_members[root]
        y0 = y_cursor
        max_gen = max(members.values())
        # Group members by generation depth (0 = root, 1 = children, ...)
        gen_rows = {}
        for aid, gen in members.items():
            gen_rows.setdefault(gen, []).append(aid)
        # Emit one contiguous row per agent, generation by generation
        for gen in range(max_gen + 1):
            aids = sorted(gen_rows.get(gen, []), key=lambda a: agent_birth.get(a, 0))
            for aid in aids:
                row_of[aid] = y_cursor
                agent_row_family[aid] = root
                y_cursor += 1
        y1 = y_cursor
        family_blocks.append((root, y0, y1))
        # one blank row between families
        y_cursor += 1
    total_rows = y_cursor

    # ---- Wealth at end of life / end of sim, and inheritance events ----
    inheritance_by_aid = {evt[1]: evt for evt in inheritance_events}
    end_wealth = {}
    for aid in row_of:
        evt = inheritance_by_aid.get(aid)
        if evt is not None:
            end_wealth[aid] = evt[3]  # total wealth at death (cash+inv-debt)
        elif time_steps in wealth_snapshots and aid in wealth_snapshots[time_steps]:
            w, d, p, living = wealth_snapshots[time_steps][aid]
            end_wealth[aid] = w - d   # net wealth at end of sim
        else:
            end_wealth[aid] = 0.0

    # ---- Figure ----
    fig_h = max(6.0, min(60.0, total_rows * 0.30))
    fig = plt.figure(figsize=(20, fig_h))
    fig.suptitle(f"Family Trees — {len(picked)} lineages, {total_shown} agents "
                 f"({time_steps} turns)\nparent above child = descent, "
                 f"arrows = inheritance, $ = wealth at end; x-overlap = lifespans overlap",
                 fontsize=15, y=0.98)
    ax = fig.add_axes([0.02, 0.04, 0.95, 0.88])
    ax.set_xlim(0, time_steps)
    ax.set_ylim(-0.5, total_rows - 0.5)
    ax.set_yticks([])
    ax.set_xlabel("Turn")
    ax.invert_yaxis()  # root at top, descendants below

    bar_h = 0.62
    # Bars first, then edges, then markers/labels on top
    for aid, row in sorted(row_of.items(), key=lambda kv: kv[1]):
        birth = agent_birth.get(aid, 0)
        end = death_turn.get(aid, time_steps)
        # Infer profession from death/inheritance records, else snapshot
        prof = '?'
        alive = True
        for evt in inheritance_events:
            if evt[1] == aid:
                prof = evt[2]
                alive = False
                break
        if prof == '?' and time_steps in wealth_snapshots:
            for snap_aid, (w, d, p, living) in wealth_snapshots[time_steps].items():
                if snap_aid == aid:
                    prof = p
                    alive = living
                    break
        color = PROF_COLORS.get(prof, '#888')
        width = max(0.5, end - birth)
        alpha = 0.45 if not alive else 0.95
        ax.barh(row, width, left=birth, height=bar_h, color=color,
                alpha=alpha, edgecolor='black', linewidth=0.2, zorder=3)

    # Parent -> child edge (from parent bar to child birth, child row)
    for child, parent in parent_map.items():
        if child not in row_of or parent not in row_of:
            continue
        if agent_row_family.get(child) != agent_row_family.get(parent):
            continue
        y_parent = row_of[parent]
        y_child = row_of[child]
        parent_end = death_turn.get(parent, time_steps)
        child_birth = agent_birth.get(child, 0)
        color = 'gray'
        # Vertical drop at parent end, horizontal to child birth, vertical to child
        ax.plot([parent_end, parent_end], [y_parent + bar_h/2, (y_parent + y_child)/2],
                color=color, lw=0.6, alpha=0.5, zorder=1)
        ax.plot([parent_end, child_birth], [(y_parent + y_child)/2, (y_parent + y_child)/2],
                color=color, lw=0.6, alpha=0.5, zorder=1)
        ax.plot([child_birth, child_birth], [(y_parent + y_child)/2, y_child - bar_h/2],
                color=color, lw=0.6, alpha=0.5, zorder=1)

    # Inheritance arrows: deceased parent's death point -> each heir's birth
    # (fully OPAQUE so the flow is easy to read; line weight scales with the
    # estate value, color = decedent's profession)
    for evt in inheritance_events:
        t, aid, prof, total_val, wealth_val, debt_val, heirs, to_gov = evt
        if aid not in row_of or total_val <= 0 or not heirs:
            continue
        parent_end = death_turn.get(aid, t)
        pcolor = PROF_COLORS.get(prof, '#888')
        lw = max(0.6, min(3.5, total_val / 250))
        y_parent_row = row_of[aid]
        for hid in heirs:
            if hid not in row_of:
                continue
            if agent_row_family.get(hid) != agent_row_family.get(aid):
                continue
            y_heir_row = row_of[hid]
            heir_birth = agent_birth.get(hid, 0)
            ax.annotate('',
                xy=(heir_birth, y_heir_row),
                xytext=(parent_end, y_parent_row),
                arrowprops=dict(arrowstyle='->', color=pcolor, lw=lw, alpha=1.0,
                                connectionstyle='arc3,rad=0.15'),
                zorder=6)

    # End markers + labels
    label_texts = []
    for aid, row in sorted(row_of.items(), key=lambda kv: kv[1]):
        birth = agent_birth.get(aid, 0)
        end = death_turn.get(aid, time_steps)
        prof = '?'
        for evt in inheritance_events:
            if evt[1] == aid:
                prof = evt[2]
                break
        if prof == '?' and time_steps in wealth_snapshots:
            for snap_aid, (w, d, p, living) in wealth_snapshots[time_steps].items():
                if snap_aid == aid:
                    prof = p
                    break
        alive = aid not in death_turn
        age_end = end - birth  # age at death, or age at end of sim
        ax.scatter([end], [row], s=12,
                   c='none' if not alive else 'black',
                   facecolors='none' if not alive else 'black',
                   edgecolors='black', linewidths=0.4, zorder=4)
        # Wealth + age at end of life (deceased) or end of sim (alive)
        w_end = end_wealth.get(aid, 0.0)
        if w_end > 0:
            ax.text(end + 0.6, row, f"${w_end:.0f} · {age_end}y", fontsize=5,
                    va='center', ha='left', alpha=0.9, zorder=5)
        elif age_end >= 0:
            ax.text(end + 0.6, row, f"{age_end}y", fontsize=5, va='center',
                    ha='left', alpha=0.9, zorder=5)
        # Label when the bar is wide enough
        if end - birth >= 3:
            short = agent_names.get(aid, f'a{aid}')
            short = short.split('-')[0] if '-' in short else short
            txt = ax.text(birth + 0.4, row, f"{short}·{prof[:1]}"[:20],
                          fontsize=5, va='center', ha='left', alpha=0.85, zorder=5)
            label_texts.append(txt)
    if label_texts and adjust_text is not None:
        try:
            adjust_text(label_texts, ax=ax, expand=(1.05, 1.2),
                        arrowprops=dict(arrowstyle='-', color='gray', lw=0.2))
        except Exception:
            pass  # label overlap avoidance is best-effort

    # White separator lines between families
    for root, y0, y1 in family_blocks:
        ax.axhline(y1 - 0.5, color='white', linewidth=1.5, zorder=5)

    # Legend: profession colors + markers
    prof_counts = defaultdict(int)
    for aid in row_of:
        prof = '?'
        for evt in inheritance_events:
            if evt[1] == aid:
                prof = evt[2]
                break
        if prof == '?' and time_steps in wealth_snapshots:
            for snap_aid, (w, d, p, living) in wealth_snapshots[time_steps].items():
                if snap_aid == aid:
                    prof = p
                    break
        prof_counts[prof] += 1
    handles = [ _mpatches.Rectangle((0, 0), 1, 1, color=PROF_COLORS[p], alpha=0.85)
                for p in PROF_ORDER if p in prof_counts ]
    labels = [ f"{p} ({prof_counts[p]})" for p in PROF_ORDER if p in prof_counts ]
    handles.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='black',
                              markersize=5, label='Alive at end'))
    handles.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='none',
                              markeredgecolor='black', markersize=5, label='Died'))
    labels += ['Alive at end', 'Died']
    ax.legend(handles, labels, loc='upper right', fontsize=8, title="Profession",
              title_fontsize=9)

    plt.savefig("wealth_lineage_family.png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Plot saved to wealth_lineage_family.png")


# =============================================================================
# MAIN (standalone)
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Wealth Lineage Diagnostic: {time_steps} turns\n")

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

    import trade_dashboard
    trade_dashboard.generate_dashboard(region_a, region_b)
    generate_plots(time_steps, region_a, region_b)


if __name__ == "__main__":
    main()

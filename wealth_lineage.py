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
    has_wealth = age < 210 and wealth > ctx.cost_of_living
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

    generate_plots(time_steps, region_a, region_b)


if __name__ == "__main__":
    main()
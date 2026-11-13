"""Deterministic bounded search over local purchases and normal phase advances."""
from heapq import heappop, heappush
from itertools import count
from math import ceil
from economy.elite_planning_state import CandidateStep, SearchResult
from economy.elite_planning_projection import purchase, finish_turn, baseline, idle_baseline, score_terminal


def plan_goal(snapshot, goal, limits):
    queue, serial, seen = [], count(), set()
    heappush(queue, (0, next(serial), snapshot, (), False))
    best, expanded = None, 0
    ordinary = baseline(snapshot, limits.horizon)
    comparison = ordinary or idle_baseline(snapshot, limits.horizon)
    baseline_value = score_terminal(comparison)
    reason = ('higher_terminal_value' if ordinary else
              'ordinary_requires_financing_compared_with_idle')
    while queue and expanded < limits.max_states:
        _, _, state, steps, met = heappop(queue)
        met = met or goal.satisfied(state)
        key = (state, met, sum(s.quantity > 0 for s in steps))
        if key in seen:
            continue
        seen.add(key)
        expanded += 1
        elapsed = state.turn - snapshot.turn
        if elapsed == limits.horizon:
            value = score_terminal(state)
            if met and any(s.quantity for s in steps) and value > baseline_value + 1e-9:
                rank = (-value, sum(s.quantity * s.limit_price for s in steps),
                        tuple(s.quantity for s in steps))
                if best is None or rank < best[0]:
                    last_purchase = max(i for i, step in enumerate(steps) if step.quantity)
                    commitments = steps[:last_purchase + 2]  # Keep the later sale observation.
                    best = rank, commitments, baseline_value, value, reason
            continue
        missing = max(0, state.slots * state.input_per_slot - state.inputs)
        quantities = sorted({0, ceil(missing), ceil(missing + state.input_per_slot),
                             max(0, state.baseline_quantity),
                             *(ceil(missing + n * state.slots * state.input_per_slot)
                               for n in range(1, limits.horizon - elapsed))})
        for quantity in quantities:
            depth = sum(s.quantity > 0 for s in steps) + (quantity > 0)
            if depth > limits.max_decisions:
                continue
            after = purchase(state, quantity)
            if after is None:
                continue
            path = steps + (CandidateStep(quantity, state.input_price, state.turn),)
            satisfied = met or goal.satisfied(after)
            if elapsed < limits.horizon:
                successor = finish_turn(after)
                if successor is not None:
                    heappush(queue, (-score_terminal(successor), next(serial), successor, path, satisfied))
    exhausted = bool(queue)
    if best:
        _, steps, base, value, reason = best
        return SearchResult('budget_exhausted' if exhausted else 'found', steps, base, value, expanded, reason)
    return SearchResult('budget_exhausted' if exhausted else 'no_improvement', (),
                        score_terminal(snapshot), score_terminal(snapshot), expanded,
                        'state_limit' if exhausted else 'no_feasible_improvement')

"""
Demographics career: M1 learned career switching, job seeking, apprenticeship subsidies, and employer matching.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

import math

from goods import Goods
from agent import get_input_commodity
from logger import logdebug, loginfo
from random_cache import rand


def learned_switch_choice(ctx, agent, choices_list, bottleneck_weights):
    """Personalized career-switch target using M1 memory."""
    weights = []
    dr_log = getattr(getattr(ctx, 'source_region', None), 'demand_ratio_log', {}) or {}
    for i, g in enumerate(choices_list):
        w = 1.0 * bottleneck_weights[i]
        hist = dr_log.get(g, [])[-8:]
        if hist:
            avg_ratio = sum(hist) / len(hist)
            if avg_ratio > 1.2:
                w *= min(2.0, 0.5 + avg_ratio)
        weights.append(w)
    hunger_avg = getattr(agent, 'mem_avg', lambda k, d=0.0: d)('mem_hunger', 0.0)
    if hunger_avg > 0:
        for i, g in enumerate(choices_list):
            if g == Goods.food:
                weights[i] *= (1.0 + min(2.0, hunger_avg))
    # Systemic harvest shock from nitrate exhaustion (Turnip Winter famine pressure)
    s_reg = getattr(ctx, 'source_region', None)
    if s_reg and getattr(s_reg, 'is_nitrate_depleted', False):
        for i, g in enumerate(choices_list):
            if g == Goods.food:
                weights[i] *= 1.5
    ambition = getattr(agent, 'ambition', 0.5)
    if ctx.most_demand != Goods.gov:
        for i, g in enumerate(choices_list):
            if g == ctx.most_demand:
                weights[i] *= (1.0 + 0.8 * ambition)
    total = sum(weights)
    if total <= 0:
        return rand.choice(choices_list)
    roll = rand.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if roll < acc:
            return choices_list[i]
    return choices_list[-1]


def count_producers(output, agents):
    """Count non-trader producers for a given good."""
    return sum(1 for a in agents if a.alive and a.output == output and not a.is_trader)


def endangered_professions(ctx, agents, choices_list):
    """Return list of professions with fewer than 3 non-trader producers."""
    endangered = []
    for g in choices_list:
        if count_producers(g, agents) < 3:
            endangered.append(g)
    return endangered


def grant_apprenticeship_subsidy(agent, output, t, ctx):
    """Government-subsidized apprenticeship for endangered professions."""
    multiplier = 2.0 if output != Goods.food else 1.0
    col = ctx.cost_of_living
    subsidy = multiplier * col
    gov = ctx.default_gov
    if gov is not None and gov.agent.cash > 0:
        actual = min(subsidy, gov.agent.cash)
        _trace_cash_write = _trace_public_begin(None, gov.agent)
        gov.agent.cash -= actual
        _trace_public_finish(_trace_cash_write, 'demographics_career:grant_apprenticeship_subsidy',
                             inputs={"source_writer": 'demographics_career.py:grant_apprenticeship_subsidy:0a04fab8f1701fcd:1'})
    else:
        actual = 0.0
    _trace_cash_write = _trace_public_begin(None, agent)
    agent.cash += actual
    _trace_public_finish(_trace_cash_write, 'demographics_career:grant_apprenticeship_subsidy',
                         inputs={"source_writer": 'demographics_career.py:grant_apprenticeship_subsidy:ba7439727d72013b:1'})
    if actual > 0:
        loginfo(t, f"{agent.name()} apprenticeship to {ctx.profession[output]}, "
                f"subsidy ${actual:.0f}")


def build_employer_cache(agents):
    """Pre-compute eligible employers by output (avoids O(n²) scan)."""
    cache = {}
    for a in agents:
        if a.is_corporation and len(a.employees) < a.max_employees:
            cash_ok = a.cash > (len(a.employees) * a.wage + a.wage) * 2
            if cash_ok:
                cache.setdefault(a.output, []).append(a)
    return cache


def handle_job_seeking(t, agent, employer_cache, region=None):
    """Legacy entry point; no second individual hiring pass."""
    if region is not None:
        from career_transitions import step_careers
        from world_config import gameplay_flags_for
        step_careers(region, t, independent=gameplay_flags_for(region).career_mobility)


def handle_career_switching(ctx, t, agent, agents,
                            choices_list, bottleneck_weights, number_of_switches):
    """Demographics shares the earlier career decision; it never rolls another move."""
    region = getattr(ctx, 'source_region', None)
    # Coming of age commits the existing household trade; this is an initial
    # livelihood record, not a second opportunity to depart a profession.
    from labor_choice import career_lifecycle_age, apply_career_switch
    if (career_lifecycle_age(agent, t) >= 14
            and getattr(agent, 'primary_livelihood', None) is None
            and agent.output not in (Goods.none, Goods.gov)
            and not getattr(agent, 'military_unit_id', None)):
        apply_career_switch(region, agent, agent.output, t,
                            kind='youth_livelihood_entry', reason='adult_entry',
                            record_class='outcome')
    if region is not None:
        from career_transitions import step_careers
        from world_config import gameplay_flags_for
        result = step_careers(region, t,
                              independent=gameplay_flags_for(region).career_mobility)
        number_of_switches += result.get('switched', 0)
    return 0, number_of_switches

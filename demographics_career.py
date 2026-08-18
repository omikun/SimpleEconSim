"""
Demographics career: M1 learned career switching, job seeking, apprenticeship subsidies, and employer matching.
"""

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
        gov.agent.cash -= actual
    else:
        actual = 0.0
    agent.cash += actual
    agent.hungry_steps = 0
    agent.inv_set(Goods.food, max(agent.inv_get(Goods.food, 0), 4))
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


def handle_job_seeking(t, agent, employer_cache):
    """Independent struggling agents actively seek employment."""
    is_employee = getattr(agent, 'employer', None) is not None
    if is_employee or getattr(agent, 'is_corporation', False):
        return
    if agent.company_owned is not None:
        return
    if agent.cash >= 5 and agent.hungry_steps <= 0:
        return
    employers = employer_cache.get(agent.output, [])
    if employers:
        employer = rand.choice(employers)
        agent.employer = employer
        agent.hired_at = t
        employer.employees.append(agent)
        loginfo(t, agent.name(), 'sought employment at', employer.name(),
                'wage', employer.wage)


def handle_career_switching(ctx, t, agent, agents,
                            choices_list, bottleneck_weights, number_of_switches):
    """Emergency / mobility career changes for independent agents."""
    is_employee = getattr(agent, 'employer', None) is not None
    if is_employee or number_of_switches >= ctx.max_career_switches:
        return 0, number_of_switches
    if agent.hungry_steps > 2:
        if agent.output != Goods.food:
            logdebug(t, agent.name(), 'EMERGENCY! switching to farmer')
            agent.output = Goods.food
            agent.last_career_switch = t
            number_of_switches += 1
            return 0, number_of_switches
    if agent.hungry_steps > 1 and (t - getattr(agent, 'last_career_switch', 0) > 10):
        if ctx.most_demand != Goods.gov and agent.output != ctx.most_demand:
            logdebug(t, agent.name(), 'hungry, switching to in-demand career:',
                     ctx.profession[ctx.most_demand])
            agent.output = ctx.most_demand
            agent.last_career_switch = t
            number_of_switches += 1
            return 0, number_of_switches
    elif agent.cash < 20 and (t - getattr(agent, 'last_career_switch', 0) > 10):
        if rand.random() < 0.1:
            if choices_list:
                endangered = endangered_professions(ctx, agents, choices_list)
                if endangered and rand.random() < 0.5:
                    output = rand.choice(endangered)
                    grant_apprenticeship_subsidy(agent, output, t, ctx)
                else:
                    output = learned_switch_choice(
                        ctx, agent, choices_list, bottleneck_weights)
                agent.output = output
                logdebug(t, agent.name(), 'poor, exploring learned career:',
                         ctx.profession[agent.output])
                agent.last_career_switch = t
                number_of_switches += 1
                return 0, number_of_switches
        elif ctx.most_demand != Goods.gov and agent.output != ctx.most_demand:
            target = ctx.most_demand
            target_recipe = ctx.recipes.get(target)
            if target_recipe and target_recipe.get('numInput', 0) > 0:
                input_good = target_recipe['input']
                number_consumers = sum(
                    1 for a in agents
                    if get_input_commodity(a) == input_good and not a.is_corporation
                    and a.employer is None)
                number_producers = sum(
                    1 for a in agents
                    if a.output == input_good and not a.is_corporation
                    and a.employer is None)
                pressure = ((number_consumers * target_recipe['numInput'])
                            / max(1, number_producers))
                if pressure > 2.0:
                    target = input_good
                    logdebug(t, agent.name(), 'redirected to bottleneck input:',
                             ctx.profession[target])
            agent.output = target
            agent.last_career_switch = t
            number_of_switches += 1
    return 0, number_of_switches

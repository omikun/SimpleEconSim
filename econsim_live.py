"""
econsim_live.py — Agent demographics and lifecycle orchestrator.

Delegates specific demographic mechanisms to dedicated sub-modules:
  - demographics_consumption.py: food/luxury consumption, bottleneck analysis
  - demographics_career.py: learned career switching, job seeking, subsidies
  - demographics_reproduction.py: agent reproduction, fertility scaling, trusts
  - demographics_estate.py: mortality, debt resolution, inheritance, escheat
"""

import random
from dataclasses import dataclass
from typing import Any

from goods import Goods
from logger import logdebug
from random_cache import rand

from demographics_consumption import (
    compute_bottleneck_weights, consume_goods, consume_daily_food
)
from demographics_career import (
    learned_switch_choice, count_producers, endangered_professions,
    grant_apprenticeship_subsidy, build_employer_cache,
    handle_job_seeking, handle_career_switching
)
from demographics_reproduction import (
    handle_reproduction
)
from demographics_estate import (
    is_last_of_profession, living_descendants_recursive,
    cleanup_dead_agent_links, handle_company_inheritance,
    deposit_pool, forgive_bad_debt, recapitalize,
    loan_bank_currency, reclaim_dead_route_cargo,
    escheat_dead_parked_goods, handle_debt_inheritance,
    handle_wealth_inheritance, zero_out_dead_agent, handle_death
)

# Backward-compatibility aliases
_compute_bottleneck_weights = compute_bottleneck_weights
_consume_goods = consume_goods
_consume_daily_food = consume_daily_food
_learned_switch_choice = learned_switch_choice
_count_producers = count_producers
_endangered_professions = endangered_professions
_grant_apprenticeship_subsidy = grant_apprenticeship_subsidy
_build_employer_cache = build_employer_cache
_handle_job_seeking = handle_job_seeking
_handle_career_switching = handle_career_switching
_handle_reproduction = handle_reproduction
_is_last_of_profession = is_last_of_profession
_living_descendants_recursive = living_descendants_recursive
_cleanup_dead_agent_links = cleanup_dead_agent_links
_handle_company_inheritance = handle_company_inheritance
_deposit_pool = deposit_pool
_forgive_bad_debt = forgive_bad_debt
_recapitalize = recapitalize
_loan_bank_currency = loan_bank_currency
_reclaim_dead_route_cargo = reclaim_dead_route_cargo
_escheat_dead_parked_goods = escheat_dead_parked_goods
_handle_debt_inheritance = handle_debt_inheritance
_handle_wealth_inheritance = handle_wealth_inheritance
_zero_out_dead_agent = zero_out_dead_agent
_handle_death = handle_death


@dataclass
class LiveContext:
    """Context object replacing global state reads/writes in Live()."""
    recipes: dict
    goods: list
    governments: list
    default_gov: Any
    hungry_log: dict
    dead_pop: list
    deadstarve_pop: list
    production_log: dict
    starve_limit: int
    profession: dict
    max_career_switches: int
    p_birth: float
    birth_gap: int
    bank: Any
    most_demand: Any
    charity: Any = None
    max_agents: int = 400
    carrying_capacity: int = 400
    cost_of_living: float = 11.25
    food_price: float = 1.0
    source_region: Any = None


def Live(t, agents, context: LiveContext):
    """Process one turn of the life-cycle for all agents (in place)."""
    ctx = context

    # 1. Pre-life-cycle government transfers
    for government in ctx.governments:
        government.distribute_ubi(t, agents)
    for government in ctx.governments:
        immigrants = government.spawn_immigrants(t, agents)
        if immigrants:
            agents.extend(immigrants)
    for government in ctx.governments:
        government.process_parental_leave(t, agents)

    # 2. Career bottleneck analysis
    choices_list = [g for g in ctx.goods if g != Goods.gov]
    bottleneck_weights = compute_bottleneck_weights(ctx, agents, choices_list)

    # 3. Per-agent life-cycle
    new_agents = []
    number_of_switches = 0
    number_food_consumed = number_wood_consumed = number_furniture_consumed = 0
    number_dead = 0
    number_dead_starved = ctx.deadstarve_pop[-1]

    random.shuffle(agents)
    employer_cache = build_employer_cache(agents)
    rand.reset()
    for agent in agents:
        if agent.is_corporation or agent.is_government:
            new_agents.append(agent)
            continue
        number_food_consumed, number_wood_consumed, number_furniture_consumed = consume_goods(
            ctx, agent, number_food_consumed, number_wood_consumed, number_furniture_consumed
        )
        consume_daily_food(agent)
        number_food_consumed, number_of_switches = handle_career_switching(
            ctx, t, agent, agents, choices_list, bottleneck_weights, number_of_switches
        )
        handle_job_seeking(t, agent, employer_cache)
        number_food_consumed = handle_reproduction(ctx, t, agent, agents, new_agents)
        died = handle_death(ctx, t, agent, agents)
        if died:
            number_dead += 1
            number_dead_starved += 1 if agent.hungry_steps >= ctx.starve_limit else 0
        else:
            new_agents.append(agent)

    # 4. Post-life-cycle government food aid & welfare
    food_price = ctx.food_price
    for government in ctx.governments:
        government.provide_food_aid(t, new_agents, food_price)

    if ctx.default_gov is not None:
        reserve = ctx.default_gov.target_food_reserve * food_price * 2
        ctx.default_gov.distribute_welfare(t, new_agents, min_reserve=reserve)

    # 5. Logging
    for good in ctx.goods:
        ctx.hungry_log[good].append(
            sum(1 for a in agents if a.output == good and a.hungry_steps > 0))
    ctx.dead_pop.append(number_dead)
    ctx.deadstarve_pop.append(number_dead_starved)
    logdebug(t, 'num dead', number_dead)
    logdebug("consumed ", number_food_consumed, "food", number_wood_consumed, "wood", number_furniture_consumed, "furniture")
    return new_agents
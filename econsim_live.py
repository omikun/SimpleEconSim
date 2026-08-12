import bisect
import random
import math
from dataclasses import dataclass
from typing import Any

import econsim_trade_money as trade
from agent import Agent, initialize_agent, get_input_commodity, get_output_commodity, seed_traits
from goods import Goods, profession
from logger import logdebug, loginfo, logwarning
from random_cache import rand
import forex as fx


# =============================================================================
# LiveContext: bundles all stateful globals into a parameter object
# =============================================================================

@dataclass
class LiveContext:
    """Context object replacing global state reads/writes in Live().
    
    The single-region callers (econsim.py) pass no context and Live() auto-builds
    from module-level globals for backward compatibility.
    The two-region caller (econsim_two_region.py) builds a LiveContext from
    per-region state and passes it explicitly, avoiding global patching.
    """
    recipes: dict
    goods: list
    governments: list
    default_gov: Any                # Government | None
    hungry_log: dict
    dead_pop: list
    deadstarve_pop: list
    production_log: dict
    starve_limit: int
    profession: dict
    max_career_switches: int
    p_birth: float
    birth_gap: int
    bank: Any                       # Bank singleton (trade.bank or region.bank)
    most_demand: Any                # Goods enum (computed value)
    charity: Any = None             # Regional Charity (for heirless bequests)
    max_agents: int = 400         # Hard population cap (0 = unlimited)
    carrying_capacity: int = 400  # Density-dependent mortality soft ceiling
    cost_of_living: float = 11.25  # Cached 4 food + 1 wood + 0.25 furniture
    food_price: float = 1.0        # Cached food price from Region.step()
    source_region: Any = None      # Owning Region (for route cleanup on death)


# =============================================================================
# TOP-LEVEL ENTRY POINT
# =============================================================================

def Live(t, agents, context: LiveContext):
    """Process one turn of the life-cycle for all agents (in place).
    
    All reads/writes go through *context* — no global state patching needed.
    """
    ctx = context

    # ---- Pre-life-cycle government transfers ----
    for government in ctx.governments:
        government.distribute_ubi(t, agents)
    for government in ctx.governments:
        immigrants = government.spawn_immigrants(t)
        if immigrants:
            agents.extend(immigrants)
    for government in ctx.governments:
        government.process_parental_leave(t, agents)

    # ---- Career-switching bottleneck analysis (hoisted) ----
    choices_list = [g for g in ctx.goods if g != Goods.gov]
    bottleneck_weights = _compute_bottleneck_weights(ctx, agents, choices_list)

    # ---- Per-agent life-cycle ----
    new_agents = []
    number_of_switches = 0
    number_food_consumed = number_wood_consumed = number_furniture_consumed = 0
    number_dead = 0
    number_dead_starved = ctx.deadstarve_pop[-1]

    random.shuffle(agents)
    employer_cache = _build_employer_cache(agents)
    rand.reset()
    for agent in agents:
        # Corporations and governments are immortal entities — skip lifecycle
        if agent.is_corporation or agent.is_government:
            new_agents.append(agent)
            continue
        number_food_consumed, number_wood_consumed, number_furniture_consumed = _consume_goods(ctx, agent, number_food_consumed, number_wood_consumed, number_furniture_consumed)
        _consume_daily_food(agent)
        number_food_consumed, number_of_switches = _handle_career_switching(ctx, t, agent, agents,
                                                          choices_list,
                                                          bottleneck_weights,
                                                          number_of_switches)
        _handle_job_seeking(t, agent, employer_cache)
        number_food_consumed = _handle_reproduction(ctx, t, agent, agents, new_agents)
        died = _handle_death(ctx, t, agent, agents)
        if died:
            number_dead += 1
            number_dead_starved += 1 if agent.hungry_steps >= ctx.starve_limit else 0
        else:
            new_agents.append(agent)

    # ---- Post-life-cycle government programs ----
    food_price = ctx.food_price

    # Government food aid: 1 food per starving agent, scaled by available funds
    for government in ctx.governments:
        government.provide_food_aid(t, new_agents, food_price)

    # Welfare: distribute cash to starving, but only excess above a real reserve
    if ctx.default_gov is not None:
        reserve = ctx.default_gov.target_food_reserve * food_price * 2  # double reserve for welfare
        ctx.default_gov.distribute_welfare(t, new_agents, min_reserve=reserve)

    # ---- Logging ----
    for good in ctx.goods:
        ctx.hungry_log[good].append(
            sum(1 for a in agents if a.output == good and a.hungry_steps > 0))
    ctx.dead_pop.append(number_dead)
    ctx.deadstarve_pop.append(number_dead_starved)
    logdebug(t, 'num dead', number_dead)
    logdebug("consumed ", number_food_consumed, "food", number_wood_consumed, "wood", number_furniture_consumed, "furniture")
    return new_agents


# =============================================================================
# BOTTLENECK DETECTION
# =============================================================================

def _compute_bottleneck_weights(ctx: LiveContext, agents, choices_list):
    """Hoisted computation: which sector is most input-constrained?"""
    bottleneck_sector = Goods.none
    bottleneck_ratio = 0
    weights = [1] * len(choices_list)
    for candidate_good in ctx.goods:
        if candidate_good == Goods.gov:
            continue
        recipe = ctx.recipes.get(candidate_good)
        if recipe and recipe.get('numInput', 0) > 0:
            input_good = recipe['input']
            number_consumers = sum(
                1 for a in agents
                if get_input_commodity(a) == input_good and not a.is_corporation
                and a.employer is None
            )
            number_producers = sum(
                1 for a in agents
                if a.output == input_good and not a.is_corporation
                and a.employer is None
            )
            pressure = (number_consumers * recipe['numInput']) / max(1, number_producers)
            if pressure > bottleneck_ratio and pressure > 2.0:
                bottleneck_ratio = pressure
                bottleneck_sector = input_good
    if bottleneck_sector != Goods.none:
        weights = [3 if g == bottleneck_sector else 1 for g in choices_list]
    return weights


# =============================================================================
# CONSUMPTION
# =============================================================================

def _consume_goods(ctx: LiveContext, agent, number_food_consumed, number_wood_consumed, number_furniture_consumed):
    """Wealthy consumption (luxury goods & extra food) based on consumption_multiplier."""
    mult = getattr(agent, 'consumption_multiplier', 1.0)
    if mult > 1.0:
        extra_food = 0
        if mult >= 5.0:
            extra_food = 2
        elif mult >= 2.0:
            extra_food = 1
        if extra_food > 0 and agent.inv_get(Goods.food, 0) >= extra_food + 4:
            agent.inv_add(Goods.food, -extra_food)
            number_food_consumed += extra_food
            loginfo('', agent.name(),
                    'wealth consumption (mult=' + str(round(mult, 2))
                    + '), consumed extra food +' + str(extra_food))
        for luxury_good in ctx.goods:
            if luxury_good in (Goods.food, Goods.gov):
                continue
            # Transport is a service (not a consumable luxury good)
            if luxury_good == Goods.transport:
                continue
            if agent.inv_get(luxury_good, 0) > 0 and get_output_commodity(agent) != luxury_good:
                consume_qty = min(max(1, int(mult * 0.5)),
                                  agent.inv_get(luxury_good, 0), 5)
                if consume_qty > 0:
                    agent.inv_add(luxury_good, -consume_qty)
                    if luxury_good == Goods.furniture:
                        number_furniture_consumed += consume_qty
                    elif luxury_good == Goods.wood:
                        number_wood_consumed += consume_qty
                    loginfo('', agent.name(),
                            'wealth consumption (mult=' + str(round(mult, 2))
                            + '), consumed', consume_qty,
                            ctx.profession[luxury_good])
    # Basic wood/furniture consumption
    if agent.inv_get(Goods.wood, 0) > 2 and get_input_commodity(agent) != Goods.wood \
       and get_output_commodity(agent) != Goods.wood:
        agent.inv_add(Goods.wood, -1)
        number_wood_consumed += 1
    if agent.inv_get(Goods.furniture, 0) > 0 and get_output_commodity(agent) != Goods.furniture \
       and rand.random() < .066:
        agent.inv_add(Goods.furniture, -1)
        number_furniture_consumed += 1
    return number_food_consumed, number_wood_consumed, number_furniture_consumed


def _consume_daily_food(agent):
    """Consume 4 food from inventory (or go hungry)."""
    food_count = agent.inv_get(Goods.food, 0)
    if food_count >= 4:
        agent.inv_add(Goods.food, -4)
        agent.hungry_steps = 0
    elif food_count > 0:
        agent.inv_set(Goods.food, 0)
        agent.hungry_steps = 0
    else:
        agent.inv_set(Goods.food, 0)
        # Traders tap into foreign/export food inventory (they travel and
        # carry wares across regions — food is eaten en route).
        if agent.is_trader:
            foreign_food = agent.inventory_foreign[Goods.food.value]
            if foreign_food >= 4:
                agent.inventory_foreign[Goods.food.value] -= 4
                agent.hungry_steps = 0
                agent.mem_push('mem_hunger', agent.hungry_steps)
                return
            export_food = agent.inventory_export[Goods.food.value]
            if export_food >= 4:
                agent.inventory_export[Goods.food.value] -= 4
                agent.hungry_steps = 0
                agent.mem_push('mem_hunger', agent.hungry_steps)
                return
        agent.hungry_steps += 1
    # M1.3: bounded hunger memory (drives grievance + career learning)
    agent.mem_push('mem_hunger', agent.hungry_steps)


# =============================================================================
# CAREER SWITCHING
# =============================================================================

def _learned_switch_choice(ctx: LiveContext, agent, choices_list, bottleneck_weights):
    """Personalized career-switch target using M1.3 memory (M1.4).

    Replaces the uniform random pick with a weighted choice that blends:
      1. base weight 1.0 per sector,
      2. the hoisted bottleneck weights (3x for the input-constrained sector),
      3. learned demand_ratio history — sectors whose recent demand/supply
         ratio averaged > 1.2 get up to a 2x boost (agents who *watched* a
         sector do well drift toward it),
      4. hunger memory — an agent that has repeatedly gone hungry (mean
         mem_hunger over the last 8 turns > 0) strongly prefers food,
      5. the ambition trait — high ambition amplifies the pull toward the
         single most-in-demand sector (career-climbing), low ambition
         dampens it (risk-averse stay-put bias).

    The choice is still stochastic and bounded: it only picks among the
    existing choices_list and can never exceed the per-turn switch cap, so
    behavior drifts without destabilizing conservation.
    """
    weights = []
    # Recent demand-ratio history per sector (last 8 entries).  The log is
    # owned by the Region (LiveContext.source_region); legacy single-region
    # callers may not wire it, so degrade to an empty history.
    dr_log = getattr(getattr(ctx, 'source_region', None), 'demand_ratio_log', {}) \
        or {}
    for i, g in enumerate(choices_list):
        w = 1.0 * bottleneck_weights[i]
        hist = dr_log.get(g, [])[-8:]
        if hist:
            avg_ratio = sum(hist) / len(hist)
            if avg_ratio > 1.2:
                w *= min(2.0, 0.5 + avg_ratio)
        weights.append(w)
    # Hunger memory: repeatedly-hungry agents learn to value food security.
    hunger_avg = getattr(agent, 'mem_avg', lambda k, d=0.0: d)('mem_hunger', 0.0)
    if hunger_avg > 0:
        for i, g in enumerate(choices_list):
            if g == Goods.food:
                weights[i] *= (1.0 + min(2.0, hunger_avg))
    # Ambition: stronger pull toward the most-in-demand sector.
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


def _handle_career_switching(ctx: LiveContext, t, agent, agents,
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
                # Government-subsidized apprenticeships: bias toward
                # endangered professions (pop < 3) to prevent extinction.
                endangered = _endangered_professions(ctx, agents, choices_list)
                if endangered and rand.random() < 0.5:
                    output = rand.choice(endangered)
                    _grant_apprenticeship_subsidy(agent, output, t, ctx)
                else:
                    # M1.4: learn from demand history + hunger memory
                    # instead of a uniform random draw, so agents demonstrably
                    # differ in behavior by trait and memory.
                    output = _learned_switch_choice(
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


# =============================================================================
# JOB SEEKING
# =============================================================================

def _count_producers(output, agents):
    """Count non-trader producers for a given good."""
    return sum(1 for a in agents if a.alive and a.output == output and not a.is_trader)


def _endangered_professions(ctx, agents, choices_list):
    """Return list of professions with fewer than 3 non-trader producers."""
    endangered = []
    for g in choices_list:
        if _count_producers(g, agents) < 3:
            endangered.append(g)
    return endangered


def _grant_apprenticeship_subsidy(agent, output, t, ctx):
    """Government-subsidized apprenticeship for endangered professions.
    
    The government pays a cash bonus (1x-2x cost of living) to agents
    who switch into an endangered profession.  The agent also receives
    4 free food and has hunger reset so they can survive the career change.
    """
    # Parametric bonus formula: all non-food professions get 2x COL
    # because they require tools/materials; food gets 1x
    multiplier = 2.0 if output != Goods.food else 1.0
    col = ctx.cost_of_living
    subsidy = multiplier * col
    # Pay from government cash if available
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


def _build_employer_cache(agents):
    """Pre-compute eligible employers by output (avoids O(n²) scan)."""
    cache = {}
    for a in agents:
        if a.is_corporation and len(a.employees) < a.max_employees:
            cash_ok = a.cash > (len(a.employees) * a.wage + a.wage) * 2
            if cash_ok:
                cache.setdefault(a.output, []).append(a)
    return cache


def _handle_job_seeking(t, agent, employer_cache):
    """Independent struggling agents actively seek employment.
    
    Uses pre-computed employer_cache to avoid O(n) scan per agent.
    """
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


# =============================================================================
# REPRODUCTION
# =============================================================================

def _handle_reproduction(ctx: LiveContext, t, agent, agents, new_agents):
    """Handle birth of new agents.

    Wealthier agents reproduce LESS (inverse of the old wealth bonus): the
    wealthy face opportunity costs — they invest in careers, trade, and
    business rather than large families.  Wealthy traders additionally cap
    their number of living children.
    """
    number_food_consumed = 0
    if agent.hungry_steps > 0:
        return 0
    import government as govmod
    government = govmod.find_government_for_agent(agent)
    birth_prob = ctx.p_birth
    if government is not None:
        birth_prob *= government.get_fertility_multiplier()

    # Wealth-based fertility reduction: richer agents reproduce less.
    # At 1x cost of living: ~0.77x base rate; at 10x: ~0.25x base rate.
    cost_of_living = ctx.cost_of_living
    wealth = agent.wealth()
    if wealth > cost_of_living:
        wealth_factor = 1.0 / (1.0 + (wealth / cost_of_living) * 0.3)
        wealth_factor = max(0.25, wealth_factor)
        birth_prob *= wealth_factor
        # Wealthy traders cap family size: they invest in their business
        # rather than children.  Richer trader → fewer allowed children.
        if agent.is_trader:
            if wealth > cost_of_living * 6:
                max_children = 2
            elif wealth > cost_of_living * 3:
                max_children = 4
            else:
                max_children = 8
            living_children = sum(1 for d in agent.descendants if d.alive)
            if living_children >= max_children:
                return 0

    if agent.last_reproduction + ctx.birth_gap < t and rand.random() < birth_prob \
       and agent.inv_get(Goods.food, 0) >= 2:
        # Check population cap
        if ctx.max_agents > 0 and len(agents) + len(new_agents) >= ctx.max_agents:
            return 0
        agent.last_reproduction = t
        new_agent = Agent(t)
        new_agent.parent = agent
        seed_traits(new_agent, parent=agent)
        agent.descendants.append(new_agent)
        if government is not None:
            government._add_citizen(new_agent)
        food_to_give = min(1, agent.inv_get(Goods.food))
        agent.inv_add(Goods.food, -food_to_give)
        empty_professions = [
            g for g in ctx.goods if g != Goods.gov
            and sum(1 for a in agents if a.output == g) == 0
        ]
        if empty_professions:
            output = empty_professions[0]
            logdebug(t, "seeding extinct profession:", ctx.profession[output])
        else:
            output = ctx.most_demand
            if output == Goods.food or rand.random() < .5:
                output = agent.output
        if output != Goods.gov and ctx.recipes[output]['maxtotalprod'] + 5 \
           <= ctx.production_log[output][-1]:
            output = Goods.gov
        logdebug(t, "new agent of ", output)
        number_input = 0
        wealth_val = abs(agent.wealth())
        liquid = agent.cash + ctx.bank.deposits.get(agent, 0)
        if wealth_val > cost_of_living * 4:
            # Rich families: a bounded FAMILY TRUST seeded at birth, funded
            # ONLY from surplus above a liquidity floor, so the family
            # business / trading capital stays intact (a 10%-of-wealth
            # bequest drained trader working capital and the exit benchmark
            # evicted every trader).  The trust is sized to keep the child
            # "somewhat wealthy" — a few multiples of the cost of living —
            # which is enough to hold the wealth-mortality discount, and the
            # inherited bridge below keeps the line protected through its
            # prime years.  Conserved: cash moves parent -> child, deposits
            # fall by the same amount.
            if agent.is_trader:
                floor = int(cost_of_living * 10) + int(ctx.food_price * 45)
            else:
                floor = int(cost_of_living * 2)
            surplus = max(0, liquid - floor)
            # Trust target: 3-5x cost of living, gently scaled by wealth
            trust_target = min(int(cost_of_living * 5),
                               int(cost_of_living * 3 + wealth_val * 0.02))
            cash = min(trust_target, surplus)
        else:
            # Standard birth endowment (original behavior).
            cash = min(agent.cash, max(int(wealth_val ** 0.72), 1))
        if cash > agent.cash:
            need = cash - agent.cash
            ctx.bank.Withdraw(agent, min(need, ctx.bank.deposits.get(agent, 0)))
        agent.cash -= cash
        initialize_agent(new_agent, output, number_input, food_to_give, cash)
        # Inherited mortality protection: the richer the parent, the longer
        # the family-support bridge (25-100 turns, halved with the halved
        # lifespans).  After it fades, the child's OWN trust-funded wealth
        # (>= cost of living) keeps the mortality discount active.
        if wealth_val > cost_of_living * 4:
            new_agent._birth_parent_wealth = wealth_val
            new_agent._birth_protection_until = t + max(25, min(100, int(cash)))
        new_agents.append(new_agent)
        if government is not None:
            government.provide_baby_bonus(t, agent, new_agent)
        if government is not None:
            government.grant_parental_leave(t, agent)
    return number_food_consumed


# =============================================================================
# DEATH
# =============================================================================

def _is_last_of_profession(agent, agents, ctx):
    """Return True if agent is the sole producer of their profession.
    
    Does not apply to traders, corporations, government agents, or gov output.
    """
    if agent.is_trader or agent.is_corporation or agent.is_government:
        return False
    output = agent.output
    if output == Goods.gov:
        return False
    count = sum(1 for a in agents if a.alive and a.output == output and not a.is_trader)
    return count <= 1


def _handle_death(ctx: LiveContext, t, agent, agents):
    """Determine if agent dies (starvation or old age). Clean up assets."""
    if agent.hungry_steps < ctx.starve_limit:
        base_death_prob = [0.0002, 0.0003, 0.0007, 0.0013, 0.0025,
                            0.006, 0.013, 0.027, 0.06, 0.13]
        import government as govmod
        government = govmod.find_government_for_agent(agent)
        if government is not None:
            # 15-turn age buckets: the mortality schedule advances TWICE as
            # fast, halving typical lifespans (~300 turns -> ~150).
            adjusted_prob = government.get_death_probability(
                agent, base_death_prob[min(agent.age(t) // 15, 9)])
        else:
            adjusted_prob = base_death_prob[min(agent.age(t) // 15, 9)]
        # Wealth-based mortality reduction: wealth protects from early death
        # by providing better nutrition, healthcare access, and living conditions.
        # Effect diminishes with age: full effect when young, negligible when old.
        agent_age = agent.age(t)
        # Lifespans halved: the wealth-mortality discount now covers the first
        # half of the halved schedule (105 turns vs 210).
        if agent_age < 105 and adjusted_prob > 0:
            col = ctx.cost_of_living
            wealth = agent.wealth()
            if wealth > col:
                # At 10x cost of living: 1% of base death prob (100x less)
                # Age factor: stays ~flat for most of life, then drops sharply near death
                age_weight = max(0.0, 1.0 - (agent_age / 105.0) ** 6)
                wealth_factor = (col / max(0.01, wealth)) ** 2
                wealth_factor = max(0.01, min(1.0, wealth_factor))
                # Inherited mortality protection: child of rich parent borrows parent's
                # wealth_factor while the family-support bridge is active, fading
                # linearly over the LAST 25 turns before expiry.  The bridge lasts
                # 25-100 turns (scaled by the bequest, halved with the lifespans),
                # keeping wealthy lines alive through their prime years.
                if hasattr(agent, '_birth_parent_wealth') and t < getattr(agent, '_birth_protection_until', 0):
                    parent_wealth_factor = (col / max(0.01, agent._birth_parent_wealth)) ** 2
                    parent_wealth_factor = max(0.01, min(1.0, parent_wealth_factor))
                    # Clamp fade to [0,1]: with bridges >25 turns the unclamped
                    # formula amplified wealth_factor past 1.0 and INVERTED the
                    # protection into extra mortality for rich children.
                    fade = max(0.0, min(1.0, (agent._birth_protection_until - t) / 25.0))
                    wealth_factor = wealth_factor * (1 - fade) + parent_wealth_factor * fade
                # Blend: only reduce prob when young, full reduction when very young
                mortality_discount = 1.0 - (1.0 - wealth_factor) * age_weight
                adjusted_prob *= mortality_discount
        # Density-dependent mortality: death probability ramps up as population
        # approaches carrying_capacity (logistic-style soft ceiling).
        current_pop = len(agents)
        threshold = ctx.carrying_capacity * 0.85  # ~340
        if current_pop > threshold:
            overage = current_pop - threshold
            crowding_factor = 1.0 + (overage / (ctx.carrying_capacity * 0.15)) * 4.0
            adjusted_prob *= crowding_factor
        # Last-of-profession safety net: the final producer of any good
        # (excluding gov) cannot die — prevents profession extinction.
        if _is_last_of_profession(agent, agents, ctx):
            return False
        if rand.random() > adjusted_prob:
            return False  # survived
        agent.alive = False
        loginfo(t, agent.name(), 'has died due to age')
    else:
        logdebug(t, agent.name(), 'has starved to death')
        agent.alive = False
    # ---- Cleanup on death ----
    _cleanup_dead_agent_links(agent)
    _handle_company_inheritance(t, agent)
    living_descendants = _living_descendants_recursive(agent)
    logdebug(t, agent.name(), 'died, has', agent.cash,
             ' #descendants:', len(living_descendants),
             [a.name() for a in living_descendants])
    # Reclaim any in-transit route cargo BEFORE the wallet is inherited/
    # cleared: a dead trader's goods must never mature on a route and later
    # be sold into its corpse wallet (which no audit can see), which would
    # leak the destination-side payment.  Reclaim returns the goods to the
    # dead agent's inventory_export where the inheritance/distribution path
    # can escheat them, and guarantees no future route delivery credits land
    # on the invisible account.
    _reclaim_dead_route_cargo(ctx, agent)
    _escheat_dead_parked_goods(ctx, agent)
    _handle_debt_inheritance(ctx, t, agent, living_descendants)
    _handle_wealth_inheritance(ctx, t, agent, living_descendants)
    _zero_out_dead_agent(ctx, agent)
    return True


def _reclaim_dead_route_cargo(ctx: LiveContext, agent):
    """Return a dying trader's in-transit cargo to its export inventory.

    Guards the per-currency audit: if a trader dies while goods are en
    route, those goods would later mature into ``inventory_foreign`` and be
    sold at the destination, crediting the dead agent's (cleared) wallet —
    invisible to ``audit_currency_total`` because the corpse is no longer in
    any region's living agents list.  Reclaiming keeps goods with the estate
    so every future credit targets a countable account.
    """
    src = getattr(ctx, 'source_region', None)
    if src is None:
        # Legacy single-region compatibility (no region wiring): nothing to
        # reclaim because no structural routes exist.
        return
    for rt in src._all_routes():
        rt.reclaim(agent)


def _escheat_dead_parked_goods(ctx: LiveContext, agent):
    """T1: a dead trader's parked goods escheat to the tile that holds them.

    Parked goods are physical lots sitting at an OLD destination tile.  If the
    trader dies, those goods would otherwise vanish (no account holds them).
    Escheat them to that tile's government inventory so goods are conserved.
    """
    if not getattr(agent, 'parked_foreign', None):
        return
    src = getattr(ctx, 'source_region', None)
    if src is None:
        agent.parked_foreign = {}
        return
    from goods import Goods as _G
    for reg_name, bucket in list(agent.parked_foreign.items()):
        tile = src.neighbors.get(reg_name)
        if tile is None:
            continue
        for g in (_G.food, _G.wood, _G.furniture):
            qty = bucket[g.value]
            if qty <= 0:
                continue
            if g == _G.food:
                tile.gov.receive_food(qty)
            else:
                tile.gov.agent.inv_add(g, qty)
        bucket[:] = [0] * len(bucket)
    agent.parked_foreign = {}


def _living_descendants_recursive(agent):
    """All living descendants (children + grandchildren per branch, BFS).

    Real inheritance law passes estates to grandchildren *per stirpes* when a
    child predeceases the decedent.  This recursive lookup makes 'heirless'
    mean truly no living descendant anywhere down the line, instead of only
    checking direct children.
    """
    seen = set()
    out = []
    queue = list(getattr(agent, 'descendants', []))
    while queue:
        d = queue.pop(0)
        if d.id in seen:
            continue
        seen.add(d.id)
        if getattr(d, 'alive', False):
            out.append(d)
        queue.extend(getattr(d, 'descendants', []))
    return out


def _cleanup_dead_agent_links(agent):
    """Clean up corporation/employee links for a dying agent."""
    if getattr(agent, 'employer', None) is not None:
        employer = agent.employer
        if hasattr(employer, 'employees') and agent in employer.employees:
            employer.employees.remove(agent)
        agent.employer = None
    if getattr(agent, 'is_corporation', False) and hasattr(agent, 'employees'):
        for emp in agent.employees:
            emp.employer = None
        agent.employees = []
        agent.is_corporation = False
        if agent.owner is not None:
            agent.owner.company_owned = None
            agent.owner = None


def _handle_company_inheritance(t, agent):
    """Pass company to heir when founder dies."""
    if getattr(agent, 'company_owned', None) is None:
        return
    company = agent.company_owned
    living_descendants = _living_descendants_recursive(agent)
    if len(living_descendants) > 0:
        heir = max(living_descendants, key=lambda d: d.cash)
        company.owner = heir
        heir.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by', heir.name())
    elif company.alive and company.is_corporation and len(company.employees) > 0:
        oldest_emp = min(company.employees, key=lambda e: e.hired_at)
        company.owner = oldest_emp
        oldest_emp.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by oldest employee', oldest_emp.name())
    elif company.alive and company.is_corporation:
        logdebug(t, agent.name(), 'company', company.name(),
                 'dissolved (no heirs, no employees)')
        for emp in company.employees:
            emp.employer = None
        company.employees = []
        company.is_corporation = False
        company.owner = None
    agent.company_owned = None


def _deposit_pool(bank):
    """True deposit pool = the per-agent ledger (sum of deposits dict).

    bank.total_deposits is a parallel scalar that history has shown can
    diverge (forgiveness write-downs and retained interest move the scalar
    but not the dict).  The dict is the money depositors can actually
    withdraw, so write-downs and insolvency checks must use it.
    """
    return sum(bank.deposits.values())


def _forgive_bad_debt(bank, amount, t):
    """Conservation-safe heirless bad-debt forgiveness.

    The loan liability was already removed (total_liabilities -= R).  To
    keep the audited total (agent cash + deposits - liabilities) unchanged,
    the DEPOSIT LEDGER must be written down by R — BOTH the per-agent dict
    (depositors genuinely absorb the loss, pro-rata, floored at 0) and the
    scalar.  A government bailout cushions the pool first when R exceeds it.
    Returns True if fully absorbed.
    """
    if amount <= 0:
        return True
    pool = _deposit_pool(bank)
    # Government bailout moves real gov cash into deposits first (conserved).
    if amount > pool:
        injected = 0.0
        for i in range(2):  # bailout can be partially funded; retry once
            bank.RequestBailout(t, amount)
            new_pool = _deposit_pool(bank)
            if new_pool <= pool:
                break
            injected += new_pool - pool
            pool = new_pool
            if pool >= amount:
                break
        if injected > 0:
            logwarning(t, f"GOV BAILOUT injected ${injected:.2f} to cover "
                          f"${amount:.2f} forgiven bad debt; depositors "
                          f"protected by gov capital")
    pool = _deposit_pool(bank)
    if amount > pool:
        # Genuine insolvency: refuse to silently destroy money.
        _raise_insolvency(t, bank, None, amount)
    # Pro-rata write-down of the per-agent dict (floored at 0 per depositor).
    total_absorb = min(amount, pool)
    if total_absorb > 0:
        for owner, bal in list(bank.deposits.items()):
            if bal <= 0:
                continue
            share = bal * (total_absorb / pool)
            bank.deposits[owner] = max(0.0, bal - share)
        bank.total_deposits -= total_absorb
    return total_absorb >= amount


def _handle_debt_inheritance(ctx: LiveContext, t, agent, living_descendants):
    """Repay debt from agent's cash/deposits; remainder passed to heirs or bank."""
    total_wealth = agent.cash + ctx.bank.deposits.get(agent, 0)
    remaining_wealth = total_wealth
    total_paid = 0
    for loan in agent.loans:
        amount_to_clear = (loan.principle - loan.principle_paid) + loan.getInterest()
        payment = min(remaining_wealth, amount_to_clear)
        if payment > 0:
            loan.pay(payment)
            total_paid += payment
            remaining_wealth -= payment
    if total_paid > 0:
        if total_paid > agent.cash:
            needed_from_bank = total_paid - agent.cash
            ctx.bank.Withdraw(agent, needed_from_bank)
        agent.cash -= total_paid
    agent.loans = [l for l in agent.loans if not l.isPaid()]
    remaining_principle = sum(l.principle - l.principle_paid for l in agent.loans)
    if remaining_principle > 0:
        ctx.bank.total_liabilities -= remaining_principle
        ctx.bank.loans = [l for l in ctx.bank.loans if l not in agent.loans]
        if len(living_descendants) > 0:
            principle_share = remaining_principle / len(living_descendants)
            for descendent in living_descendants:
                new_loan = trade.Loan(ctx.bank, descendent, principle_share,
                                      ctx.bank.interest_rate)
                descendent.loans.append(new_loan)
                ctx.bank.loans.append(new_loan)
                ctx.bank.total_liabilities += principle_share
        else:
            _forgive_bad_debt(ctx.bank, remaining_principle, t)


def _handle_wealth_inheritance(ctx: LiveContext, t, agent, living_descendants):
    """Distribute remaining cash, deposits, and inventory to heirs or government."""
    inheritance_cash = agent.cash
    inheritance_deposits = ctx.bank.deposits.get(agent, 0)
    government = ctx.default_gov
    if len(living_descendants) > 0:
        if inheritance_deposits > 0:
            ctx.bank.Withdraw(agent, inheritance_deposits)
            inheritance_cash += inheritance_deposits
        num_heirs = len(living_descendants)
        cash_share = int(inheritance_cash // num_heirs)
        cash_remainder = inheritance_cash - (cash_share * num_heirs)
        for i, descendent in enumerate(living_descendants):
            extra_cash = cash_remainder if i == 0 else 0
            descendent.cash += cash_share + extra_cash
        # Distribute foreign-currency wallets evenly to heirs (None-safe:
        # non-traders never have a wallet, so this loop is a no-op).
        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                wallet_share = bal / num_heirs
                for descendent in living_descendants:
                    fx.fx_add(descendent, currency, wallet_share)
                dead_w[currency] = 0.0
        # Distribute inventory — iterate over Goods enum (list-based inventory)
        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount == 0:
                continue
            target_heirs = [d for d in living_descendants if d.output == g_enum]
            if not target_heirs:
                target_heirs = living_descendants
            inv_share = int(amount // len(target_heirs))
            inv_remainder = amount - (inv_share * len(target_heirs))
            for i, descendent in enumerate(target_heirs):
                extra_inv = inv_remainder if i == 0 else 0
                descendent.inventory[g_enum.value] += inv_share + extra_inv
    else:
        # Heirless estate: charitable bequest default (real-world: no family
        # -> bequest to charity; state escheat is a last resort).  The
        # government keeps only a probate fee; the rest goes to the regional
        # charity.  All transfers are conserved (cash/deposits/fx wallets
        # move owner; food units move inventory).
        probate = getattr(government, 'probate_fee_rate', 0.0) if government else 0.0
        gov_share = inheritance_cash * probate
        charity_share = inheritance_cash - gov_share
        if government is not None:
            government.agent.cash += gov_share
            if gov_share > 0:
                government.record_income(t, 'inheritance', gov_share)
        charity = getattr(ctx, 'charity', None)
        if charity is not None and charity_share > 0:
            charity.agent.cash += charity_share
        elif charity is None:
            # No charity wired (single-region compat): keep the leftover
            # with the government (legacy behavior).
            if government is not None and charity_share > 0:
                government.agent.cash += charity_share
                government.record_income(t, 'inheritance', charity_share)
        # Transfer foreign-currency wallets to government (None-safe)
        dead_w = getattr(agent, 'wallets', None)
        if dead_w:
            for currency, bal in list(dead_w.items()):
                if bal <= 0:
                    continue
                fx.fx_add(government.agent, currency, bal)
                dead_w[currency] = 0.0
        if inheritance_deposits > 0:
            # Transfer deposit: probate fee to government, rest to charity
            # (total_deposits unchanged — it's a transfer).
            deposit_gov = inheritance_deposits * probate
            deposit_charity = inheritance_deposits - deposit_gov
            if government is not None and deposit_gov > 0:
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_gov
                government.record_income(t, 'inheritance', deposit_gov)
            if charity is not None and deposit_charity > 0:
                ctx.bank.deposits[charity.agent] = \
                    ctx.bank.deposits.get(charity.agent, 0) + deposit_charity
            elif charity is None and government is not None and deposit_charity > 0:
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + deposit_charity
                government.record_income(t, 'inheritance', deposit_charity)
            ctx.bank.deposits[agent] = 0  # zero out so _zero_out_dead_agent's deletion is harmless
        # Transfer all inventory: food to charity, non-food to government
        # (as before; gov food reserve / liquidation path is unchanged).
        for g_enum in Goods:
            if g_enum == Goods.none:
                continue
            amount = agent.inventory[g_enum.value]
            if amount <= 0:
                continue
            if g_enum == Goods.food and charity is not None:
                charity.receive_food(amount)
            elif government is not None:
                government.agent.inventory[g_enum.value] += amount


def _raise_insolvency(t, bank, agent, shortfall):
    """Raise when a write-down would push deposits below zero.

    Indicates the bank cannot absorb a forgiven loan even after government
    bailout — a genuine insolvency.  Refuse to silently destroy money; dump
    enough state to debug what caused it.  *agent* may be None (bad-debt
    forgiveness without a specific dying debtor).
    """
    import sys
    import traceback
    outstanding = sum((l.principle - l.principle_paid) for l in bank.loans)
    agent_owed = sum((l.principle - l.principle_paid) for l in agent.loans) \
        if agent is not None else 0.0
    gov_cash = getattr(getattr(bank, 'gov', None), 'agent', None)
    gov_cash = gov_cash.cash if gov_cash is not None else None
    print(f"\n=== BANK INSOLVENCY DETECTED (write-down would make deposits negative) ===",
          file=sys.stderr)
    print(f"  turn={t}  shortfall=${shortfall:.2f}", file=sys.stderr)
    print(f"  bank: total_deposits={bank.total_deposits:.2f} "
          f"total_liabilities={bank.total_liabilities:.2f} "
          f"equity={bank.total_deposits - bank.total_liabilities:.2f} "
          f"deposit_dict_pool={sum(bank.deposits.values()):.2f}",
          file=sys.stderr)
    print(f"  bank loans outstanding=${outstanding:.2f} ({len(bank.loans)} loans)",
          file=sys.stderr)
    if agent is not None:
        print(f"  dying agent id={agent.id} cash={agent.cash:.2f} "
              f"deposits={bank.deposits.get(agent, 0):.2f} "
              f"loans owed=${agent_owed:.2f} ({len(agent.loans)} loans) "
              f"age={t - agent.birth_round}", file=sys.stderr)
    print(f"  gov cash={gov_cash}", file=sys.stderr)
    print(f"  fx_pool={bank.fx_pool:.2f} "
          f"foreign_reserves={dict(bank.foreign_reserves)}", file=sys.stderr)
    traceback.print_stack()
    raise RuntimeError(
        "BANK INSOLVENCY: write-down would make deposits negative; "
        "see stderr for full attribution trace")


def _zero_out_dead_agent(ctx: LiveContext, agent):
    """Clear dead agent's assets so they don't leak from the cash sum."""
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]
    dead_w = getattr(agent, 'wallets', None)
    if dead_w is not None:
        dead_w.clear()
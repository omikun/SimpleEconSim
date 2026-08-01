import bisect
import random
import math
from dataclasses import dataclass
from typing import Any

import econsim_trade_money as trade
from agent import Agent, initialize_agent, get_input_commodity, get_output_commodity
from goods import Goods, profession
from logger import logdebug, loginfo, logwarning
from random_cache import rand


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
    max_agents: int = 400         # Hard population cap (0 = unlimited)
    carrying_capacity: int = 400  # Density-dependent mortality soft ceiling
    cost_of_living: float = 11.25  # Cached 4 food + 1 wood + 0.25 furniture
    food_price: float = 1.0        # Cached food price from Region.step()


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
                return
            export_food = agent.inventory_export[Goods.food.value]
            if export_food >= 4:
                agent.inventory_export[Goods.food.value] -= 4
                agent.hungry_steps = 0
                return
        agent.hungry_steps += 1


# =============================================================================
# CAREER SWITCHING
# =============================================================================

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
                agent.output = rand.choice(choices_list)
                logdebug(t, agent.name(), 'poor, exploring random career:',
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
                max_children = 0
            elif wealth > cost_of_living * 3:
                max_children = 1
            else:
                max_children = 2
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
        # Trust fund: rich parents guarantee child enough to survive (2x cost of living)
        cash = min(agent.cash, max(
            int(wealth_val ** 0.72),                   # existing gradient
            int(cost_of_living * 2) if wealth_val > cost_of_living * 4 else 1
        ))
        agent.cash -= cash
        initialize_agent(new_agent, output, number_input, food_to_give, cash)
        # Inherited mortality protection: child of rich parent gets parent's mortality
        # discount for first 50 turns (representing family support network).
        if wealth_val > cost_of_living * 4:
            new_agent._birth_parent_wealth = wealth_val
            new_agent._birth_protection_until = t + 50
        new_agents.append(new_agent)
        if government is not None:
            government.provide_baby_bonus(t, agent, new_agent)
        if government is not None:
            government.grant_parental_leave(t, agent)
    return number_food_consumed


# =============================================================================
# DEATH
# =============================================================================

def _handle_death(ctx: LiveContext, t, agent, agents):
    """Determine if agent dies (starvation or old age). Clean up assets."""
    if agent.hungry_steps < ctx.starve_limit:
        base_death_prob = [0.0002, 0.0003, 0.0007, 0.0013, 0.0025,
                            0.006, 0.013, 0.027, 0.06, 0.13]
        import government as govmod
        government = govmod.find_government_for_agent(agent)
        if government is not None:
            adjusted_prob = government.get_death_probability(
                agent, base_death_prob[min(agent.age(t) // 30, 9)])
        else:
            adjusted_prob = base_death_prob[min(agent.age(t) // 30, 9)]
        # Wealth-based mortality reduction: wealth protects from early death
        # by providing better nutrition, healthcare access, and living conditions.
        # Effect diminishes with age: full effect when young, negligible when old.
        agent_age = agent.age(t)
        if agent_age < 210 and adjusted_prob > 0:
            col = ctx.cost_of_living
            wealth = agent.wealth()
            if wealth > col:
                # At 10x cost of living: 1% of base death prob (100x less)
                # Age factor: stays ~flat for most of life, then drops sharply near death
                age_weight = max(0.0, 1.0 - (agent_age / 210.0) ** 6)
                wealth_factor = (col / max(0.01, wealth)) ** 2
                wealth_factor = max(0.01, min(1.0, wealth_factor))
                # Inherited mortality protection: child of rich parent borrows parent's
                # wealth_factor for first 50 turns (family support), fading linearly.
                if hasattr(agent, '_birth_parent_wealth') and t < getattr(agent, '_birth_protection_until', 0):
                    parent_wealth_factor = (col / max(0.01, agent._birth_parent_wealth)) ** 2
                    parent_wealth_factor = max(0.01, min(1.0, parent_wealth_factor))
                    # Fade from full inherited bonus to own wealth_factor over 50 turns
                    fade = max(0.0, (agent._birth_protection_until - t) / 50.0)
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
    living_descendants = [a for a in agent.descendants if a.alive]
    logdebug(t, agent.name(), 'died, has', agent.cash,
             ' #descendants:', len(living_descendants),
             [a.name() for a in living_descendants])
    _handle_debt_inheritance(ctx, t, agent, living_descendants)
    _handle_wealth_inheritance(ctx, t, agent, living_descendants)
    _zero_out_dead_agent(ctx, agent)
    return True


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
    living_descendants = [d for d in agent.descendants if d.alive]
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
            # Write down only what deposits can absorb. If bailout fails,
            # the excess bad debt is absorbed as a liability write-down
            # (equity stays zero rather than going negative).
            write_down = min(remaining_principle, ctx.bank.total_deposits)
            if remaining_principle > ctx.bank.total_deposits:
                bailout_ok = ctx.bank.RequestBailout(t, remaining_principle)
                if bailout_ok:
                    write_down = min(remaining_principle, ctx.bank.total_deposits)
                else:
                    # Bailout failed — write down excess as lost liabilities
                    excess = remaining_principle - ctx.bank.total_deposits
                    ctx.bank.total_liabilities -= excess
                    loginfo(t, f"Bailout failed: write down ${excess:.2f} "
                            f"in liabilities (no government funds)")
            ctx.bank.total_deposits -= write_down


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
        if government is not None:
            government.agent.cash += inheritance_cash
            if inheritance_deposits > 0:
                # Transfer deposit to government (total_deposits unchanged — it's a transfer)
                ctx.bank.deposits[government.agent] = \
                    ctx.bank.deposits.get(government.agent, 0) + inheritance_deposits
                ctx.bank.deposits[agent] = 0  # zero out so _zero_out_dead_agent's deletion is harmless
            # Transfer all inventory to government
            for g_enum in Goods:
                if g_enum == Goods.none:
                    continue
                amount = agent.inventory[g_enum.value]
                if amount > 0:
                    government.agent.inventory[g_enum.value] += amount


def _zero_out_dead_agent(ctx: LiveContext, agent):
    """Clear dead agent's assets so they don't leak from the cash sum."""
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]
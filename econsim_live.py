import bisect
import random
import math
from dataclasses import dataclass
from typing import Optional, Any

import econsim_states
from econsim_states import *
import econsim_trade_money as trade
from agent import Agent, InitAgent, GetInputCom, GetOutputCom
from goods import Goods
from logger import logdebug, loginfo, logwarning


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
    most_demand: Any                # Goods enum (trade.mostDemand or computed value)


def _build_context_from_globals() -> LiveContext:
    """Build a LiveContext from the current module/global state."""
    return LiveContext(
        recipes=recipes,
        goods=goods,
        governments=econsim_states.governments,
        default_gov=econsim_states.default_gov,
        hungry_log=hungry_log,
        dead_pop=dead_pop,
        deadstarve_pop=deadstarve_pop,
        production_log=production_log,
        starve_limit=starve_limit,
        profession=profession,
        max_career_switches=max_career_switches,
        p_birth=p_birth,
        birth_gap=birthGap,
        bank=trade.bank,
        most_demand=trade.mostDemand,
    )


# =============================================================================
# TOP-LEVEL ENTRY POINT
# =============================================================================

def Live(t, agents, context: Optional[LiveContext] = None):
    """Process one turn of the life-cycle for all agents (in place).
    
    When *context* is None (single-region callers), read/write global state
    directly via _build_context_from_globals() for backward compatibility.
    When *context* is provided (two-region callers), all reads/writes go
    through the context object — no global patching needed.
    """
    if context is None:
        ctx = _build_context_from_globals()
    else:
        ctx = context

    # ---- Pre-life-cycle government transfers ----
    for gov in ctx.governments:
        gov.distribute_ubi(t, agents)
    for gov in ctx.governments:
        immigrants = gov.spawn_immigrants(t)
        if immigrants:
            agents.extend(immigrants)
    for gov in ctx.governments:
        gov.process_parental_leave(t, agents)

    # ---- Government food aid ----
    food_price = ctx.recipes[Goods.food]['price']
    if ctx.default_gov is not None:
        ctx.default_gov.provide_food_aid(t, agents, food_price)
    else:
        logwarning(t, "No government exists to provide food aid!")

    # ---- Career-switching bottleneck analysis (hoisted) ----
    choices_list = [g for g in ctx.goods if g != Goods.gov]
    bottleneck_weights = _compute_bottleneck_weights(ctx, agents, choices_list)

    # ---- Per-agent life-cycle ----
    new_agents = []
    numSwitches = 0
    numfood = numwood = numFurn = 0
    numdead = 0
    numdeadstarve = ctx.deadstarve_pop[-1]

    random.shuffle(agents)
    for agent in agents:
        if agent.is_corp:
            new_agents.append(agent)
            continue
        numfood, numwood, numFurn = _consume_goods(ctx, agent, numfood, numwood, numFurn)
        _consume_daily_food(agent)
        numfood, numSwitches = _handle_career_switching(ctx, t, agent, agents,
                                                         choices_list,
                                                         bottleneck_weights,
                                                         numSwitches)
        _handle_job_seeking(t, agent, agents)
        numfood = _handle_reproduction(ctx, t, agent, agents, new_agents)
        died = _handle_death(ctx, t, agent, agents)
        if died:
            numdead += 1
            numdeadstarve += 1 if agent.hungry_steps >= ctx.starve_limit else 0
        else:
            new_agents.append(agent)

    # ---- Post-life-cycle welfare ----
    if ctx.default_gov is not None:
        food_price = ctx.recipes.get(Goods.food, {}).get('price', 1)
        reserve = food_price * 20
        ctx.default_gov.distribute_welfare(t, new_agents, min_reserve=reserve)

    # ---- Logging ----
    for good in ctx.goods:
        ctx.hungry_log[good].append(
            sum(1 for a in agents if a.output == good and a.hungry_steps > 0))
    ctx.dead_pop.append(numdead)
    ctx.deadstarve_pop.append(numdeadstarve)
    logdebug(t, 'num dead', numdead)
    logdebug("consumed ", numfood, "food", numwood, "wood", numFurn, "furn")
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
            num_consumers = sum(
                1 for a in agents
                if GetInputCom(a) == input_good and not a.is_corp
                and a.employer is None
            )
            num_producers = sum(
                1 for a in agents
                if a.output == input_good and not a.is_corp
                and a.employer is None
            )
            pressure = (num_consumers * recipe['numInput']) / max(1, num_producers)
            if pressure > bottleneck_ratio and pressure > 2.0:
                bottleneck_ratio = pressure
                bottleneck_sector = input_good
    if bottleneck_sector != Goods.none:
        weights = [3 if g == bottleneck_sector else 1 for g in choices_list]
    return weights


# =============================================================================
# CONSUMPTION
# =============================================================================

def _consume_goods(ctx: LiveContext, agent, numfood, numwood, numFurn):
    """Wealthy consumption (luxury goods & extra food) based on consumption_mult."""
    mult = getattr(agent, 'consumption_mult', 1.0)
    if mult > 1.0:
        extra_food = 0
        if mult >= 5.0:
            extra_food = 2
        elif mult >= 2.0:
            extra_food = 1
        if extra_food > 0 and agent.inv.get(Goods.food, 0) >= extra_food + 4:
            agent.inv[Goods.food] -= extra_food
            numfood += extra_food
            loginfo('', agent.name(),
                    'wealth consumption (mult=' + str(round(mult, 2))
                    + '), consumed extra food +' + str(extra_food))
        for luxury_good in ctx.goods:
            if luxury_good in (Goods.food, Goods.gov):
                continue
            if agent.inv.get(luxury_good, 0) > 0 and GetOutputCom(agent) != luxury_good:
                consume_qty = min(max(1, int(mult * 0.5)),
                                  agent.inv.get(luxury_good, 0), 5)
                if consume_qty > 0:
                    agent.inv[luxury_good] -= consume_qty
                    if luxury_good == Goods.furn:
                        numFurn += consume_qty
                    elif luxury_good == Goods.wood:
                        numwood += consume_qty
                    loginfo('', agent.name(),
                            'wealth consumption (mult=' + str(round(mult, 2))
                            + '), consumed', consume_qty,
                            ctx.profession[luxury_good])
    # Basic wood/furniture consumption
    if agent.inv.get(Goods.wood, 0) > 2 and GetInputCom(agent) != Goods.wood \
       and GetOutputCom(agent) != Goods.wood:
        agent.inv[Goods.wood] -= 1
        numwood += 1
    if agent.inv.get(Goods.furn, 0) > 0 and GetOutputCom(agent) != Goods.furn \
       and random.random() < .066:
        agent.inv[Goods.furn] -= 1
        numFurn += 1
    return numfood, numwood, numFurn


def _consume_daily_food(agent):
    """Consume 4 food from inventory (or go hungry)."""
    if agent.inv.get(Goods.food, 0) >= 4:
        agent.inv[Goods.food] -= 4
        agent.hungry_steps = 0
    elif agent.inv.get(Goods.food, 0) > 0:
        agent.inv[Goods.food] = 0
        agent.hungry_steps = 0
    else:
        agent.inv[Goods.food] = 0
        agent.hungry_steps += 1


# =============================================================================
# CAREER SWITCHING
# =============================================================================

def _handle_career_switching(ctx: LiveContext, t, agent, agents,
                              choices_list, bottleneck_weights, numSwitches):
    """Emergency / mobility career changes for independent agents."""
    is_employee = getattr(agent, 'employer', None) is not None
    if is_employee or numSwitches >= ctx.max_career_switches:
        return 0, numSwitches
    if agent.hungry_steps > 2:
        if agent.output != Goods.food:
            logdebug(t, agent.name(), 'EMERGENCY! switching to farmer')
            agent.output = Goods.food
            agent.lastCareerSwitch = t
            numSwitches += 1
            return 0, numSwitches
    if agent.hungry_steps > 1 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
        if ctx.most_demand != Goods.gov and agent.output != ctx.most_demand:
            logdebug(t, agent.name(), 'hungry, switching to in-demand career:',
                     ctx.profession[ctx.most_demand])
            agent.output = ctx.most_demand
            agent.lastCareerSwitch = t
            numSwitches += 1
            return 0, numSwitches
    elif agent.cash < 20 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
        if random.random() < 0.1:
            if choices_list:
                agent.output = random.choices(choices_list,
                                              weights=bottleneck_weights, k=1)[0]
                logdebug(t, agent.name(), 'poor, exploring random career:',
                         ctx.profession[agent.output])
                agent.lastCareerSwitch = t
                numSwitches += 1
                return 0, numSwitches
        elif ctx.most_demand != Goods.gov and agent.output != ctx.most_demand:
            target = ctx.most_demand
            target_recipe = ctx.recipes.get(target)
            if target_recipe and target_recipe.get('numInput', 0) > 0:
                input_good = target_recipe['input']
                num_consumers = sum(
                    1 for a in agents
                    if GetInputCom(a) == input_good and not a.is_corp
                    and a.employer is None)
                num_producers = sum(
                    1 for a in agents
                    if a.output == input_good and not a.is_corp
                    and a.employer is None)
                pressure = ((num_consumers * target_recipe['numInput'])
                            / max(1, num_producers))
                if pressure > 2.0:
                    target = input_good
                    logdebug(t, agent.name(), 'redirected to bottleneck input:',
                             ctx.profession[target])
            agent.output = target
            agent.lastCareerSwitch = t
            numSwitches += 1
    return 0, numSwitches


# =============================================================================
# JOB SEEKING
# =============================================================================

def _handle_job_seeking(t, agent, agents):
    """Independent struggling agents actively seek employment."""
    is_employee = getattr(agent, 'employer', None) is not None
    if is_employee or getattr(agent, 'is_corp', False):
        return
    if agent.company_owned is not None:
        return
    if agent.cash >= 5 and agent.hungry_steps <= 0:
        return
    employers = [
        a for a in agents
        if a.is_corp
        and len(a.employees) < a.max_employees
        and a.output == agent.output
        and a.cash > (len(a.employees) * a.wage + a.wage) * 2
    ]
    if employers:
        employer = random.choice(employers)
        agent.employer = employer
        agent.hiredAt = t
        employer.employees.append(agent)
        loginfo(t, agent.name(), 'sought employment at', employer.name(),
                'wage', employer.wage)


# =============================================================================
# REPRODUCTION
# =============================================================================

def _handle_reproduction(ctx: LiveContext, t, agent, agents, new_agents):
    """Handle birth of new agents."""
    numfood = 0
    if agent.hungry_steps > 0:
        return 0
    import government as govmod
    gov = govmod.find_government_for_agent(agent)
    birth_prob = ctx.p_birth
    if gov is not None:
        birth_prob *= gov.get_fertility_multiplier()
    if agent.lastRepro + ctx.birth_gap < t and random.random() < birth_prob \
       and agent.cash > 20 and agent.inv.get(Goods.food, 0) >= 2:
        agent.lastRepro = t
        new_agent = Agent(t)
        new_agent.parent = agent
        agent.descendents.append(new_agent)
        if gov is not None:
            gov._add_citizen(new_agent)
        giveFood = min(1, agent.inv[Goods.food])
        agent.inv[Goods.food] -= giveFood
        empty_professions = [
            g for g in ctx.goods if g != Goods.gov
            and sum(1 for a in agents if a.output == g) == 0
        ]
        if empty_professions:
            output = empty_professions[0]
            logdebug(t, "seeding extinct profession:", ctx.profession[output])
        else:
            output = ctx.most_demand
            if output == Goods.food or random.random() < .5:
                output = agent.output
        if output != Goods.gov and ctx.recipes[output]['maxtotalprod'] + 5 \
           <= ctx.production_log[output][-1]:
            output = Goods.gov
        logdebug(t, "new agent of ", output)
        numInput = 0
        cash = min(1, agent.cash)
        agent.cash -= cash
        InitAgent(new_agent, output, numInput, giveFood, cash)
        new_agents.append(new_agent)
        if gov is not None:
            gov.provide_baby_bonus(t, agent, new_agent)
        if gov is not None:
            gov.grant_parental_leave(t, agent)
    return numfood


# =============================================================================
# DEATH
# =============================================================================

def _handle_death(ctx: LiveContext, t, agent, agents):
    """Determine if agent dies (starvation or old age). Clean up assets."""
    if agent.hungry_steps < ctx.starve_limit:
        base_death_prob = [0.0002, 0.0003, 0.0007, 0.0013, 0.0025,
                           0.006, 0.013, 0.027, 0.06, 0.13]
        import government as govmod
        gov = govmod.find_government_for_agent(agent)
        if gov is not None:
            adjusted_prob = gov.get_death_probability(
                agent, base_death_prob[min(agent.age(t) // 30, 9)])
        else:
            adjusted_prob = base_death_prob[min(agent.age(t) // 30, 9)]
        if random.random() > adjusted_prob:
            return False  # survived
        agent.alive = False
        loginfo(t, agent.name(), 'has died due to age')
    else:
        logdebug(t, agent.name(), 'has starved to death')
        agent.alive = False
    # ---- Cleanup on death ----
    _cleanup_dead_agent_links(agent)
    _handle_company_inheritance(t, agent)
    livingDescendents = [a for a in agent.descendents if a.alive]
    logdebug(t, agent.name(), 'died, has', agent.cash,
             ' #descendents:', len(livingDescendents),
             [a.name() for a in livingDescendents])
    _handle_debt_inheritance(ctx, t, agent, livingDescendents)
    _handle_wealth_inheritance(ctx, t, agent, livingDescendents)
    _zero_out_dead_agent(ctx, agent)
    return True


def _cleanup_dead_agent_links(agent):
    """Clean up corporation/employee links for a dying agent."""
    if getattr(agent, 'employer', None) is not None:
        employer = agent.employer
        if hasattr(employer, 'employees') and agent in employer.employees:
            employer.employees.remove(agent)
        agent.employer = None
    if getattr(agent, 'is_corp', False) and hasattr(agent, 'employees'):
        for emp in agent.employees:
            emp.employer = None
        agent.employees = []
        agent.is_corp = False
        if agent.owner is not None:
            agent.owner.company_owned = None
            agent.owner = None


def _handle_company_inheritance(t, agent):
    """Pass company to heir when founder dies."""
    if getattr(agent, 'company_owned', None) is None:
        return
    company = agent.company_owned
    living_descendents = [d for d in agent.descendents if d.alive]
    if len(living_descendents) > 0:
        heir = max(living_descendents, key=lambda d: d.cash)
        company.owner = heir
        heir.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by', heir.name())
    elif company.alive and company.is_corp and len(company.employees) > 0:
        oldest_emp = min(company.employees, key=lambda e: e.hiredAt)
        company.owner = oldest_emp
        oldest_emp.company_owned = company
        logdebug(t, agent.name(), 'company', company.name(),
                 'inherited by oldest employee', oldest_emp.name())
    elif company.alive and company.is_corp:
        logdebug(t, agent.name(), 'company', company.name(),
                 'dissolved (no heirs, no employees)')
        for emp in company.employees:
            emp.employer = None
        company.employees = []
        company.is_corp = False
        company.owner = None
    agent.company_owned = None


def _handle_debt_inheritance(ctx: LiveContext, t, agent, livingDescendents):
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
        if len(livingDescendents) > 0:
            principle_share = remaining_principle / len(livingDescendents)
            for descendent in livingDescendents:
                new_loan = trade.Loan(ctx.bank, descendent, principle_share,
                                      ctx.bank.interest_rate)
                descendent.loans.append(new_loan)
                ctx.bank.loans.append(new_loan)
                ctx.bank.total_liabilities += principle_share
        else:
            if remaining_principle > ctx.bank.total_deposits:
                ctx.bank.RequestBailout(t, remaining_principle)
            ctx.bank.total_deposits -= remaining_principle


def _handle_wealth_inheritance(ctx: LiveContext, t, agent, livingDescendents):
    """Distribute remaining cash, deposits, and inventory to heirs or government."""
    inheritance_cash = agent.cash
    inheritance_deposits = ctx.bank.deposits.get(agent, 0)
    gov = ctx.default_gov
    if len(livingDescendents) > 0:
        if inheritance_deposits > 0:
            ctx.bank.Withdraw(agent, inheritance_deposits)
            inheritance_cash += inheritance_deposits
        num_heirs = len(livingDescendents)
        cash_share = int(inheritance_cash // num_heirs)
        cash_remainder = inheritance_cash - (cash_share * num_heirs)
        for i, descendent in enumerate(livingDescendents):
            extra_cash = cash_remainder if i == 0 else 0
            descendent.cash += cash_share + extra_cash
        for good, amount in agent.inv.items():
            target_heirs = [d for d in livingDescendents if d.output == good]
            if not target_heirs:
                target_heirs = livingDescendents
            inv_share = int(amount // len(target_heirs))
            inv_remainder = amount - (inv_share * len(target_heirs))
            for i, descendent in enumerate(target_heirs):
                extra_inv = inv_remainder if i == 0 else 0
                descendent.inv[good] += inv_share + extra_inv
    else:
        if gov is not None:
            gov.agent.cash += inheritance_cash
            if inheritance_deposits > 0:
                ctx.bank.deposits[gov.agent] = \
                    ctx.bank.deposits.get(gov.agent, 0) + inheritance_deposits
            ctx.bank.total_deposits -= inheritance_deposits
            for good, amount in agent.inv.items():
                gov.agent.inv[good] = gov.agent.inv.get(good, 0) + amount


def _zero_out_dead_agent(ctx: LiveContext, agent):
    """Clear dead agent's assets so they don't leak from the cash sum."""
    agent.cash = 0
    if agent in ctx.bank.deposits:
        del ctx.bank.deposits[agent]
"""
Demographics reproduction: agent births, fertility curves, heritable traits, and family trusts.
"""

from goods import Goods
from agent import Agent, initialize_agent, seed_traits
from logger import logdebug
from random_cache import rand


def handle_reproduction(ctx, t, agent, agents, new_agents):
    """Handle birth of new agents."""
    number_food_consumed = 0
    if agent.hungry_steps > 0:
        return 0
    import government as govmod
    government = govmod.find_government_for_agent(agent)
    birth_prob = ctx.p_birth
    if government is not None:
        birth_prob *= government.get_fertility_multiplier()

    cost_of_living = ctx.cost_of_living
    wealth = agent.wealth()
    if wealth > cost_of_living:
        wealth_factor = 1.0 / (1.0 + (wealth / cost_of_living) * 0.3)
        wealth_factor = max(0.25, wealth_factor)
        birth_prob *= wealth_factor
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
        if ctx.max_agents > 0 and len(agents) + len(new_agents) >= ctx.max_agents:
            return 0
        agent.last_reproduction = t
        new_agent = Agent(t)
        new_agent.parent = agent
        new_agent.origin_nation = getattr(agent, 'origin_nation', None)
        new_agent.home_currency = (getattr(ctx.source_region, 'home_currency', None)
                                   if getattr(ctx, 'source_region', None) else None) \
                                   or getattr(agent, 'home_currency', None)
        new_agent._bank_ref = getattr(agent, '_bank_ref', None) or getattr(ctx, 'bank', None)
        new_agent.region = getattr(agent, 'region', None) or (
            getattr(ctx.source_region, 'name', None) if getattr(ctx, 'source_region', None) else None)
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
            if agent.is_trader:
                floor = int(cost_of_living * 10) + int(ctx.food_price * 45)
            else:
                floor = int(cost_of_living * 2)
            surplus = max(0, liquid - floor)
            trust_target = min(int(cost_of_living * 5),
                               int(cost_of_living * 3 + wealth_val * 0.02))
            cash = min(trust_target, surplus)
        else:
            cash = min(agent.cash, max(int(wealth_val ** 0.72), 1))
        if cash > agent.cash:
            need = cash - agent.cash
            ctx.bank.Withdraw(agent, min(need, ctx.bank.deposits.get(agent, 0)))
        agent.cash -= cash
        initialize_agent(new_agent, output, number_input, food_to_give, cash)
        if wealth_val > cost_of_living * 4:
            new_agent._birth_parent_wealth = wealth_val
            new_agent._birth_protection_until = t + max(25, min(100, int(cash)))
        new_agents.append(new_agent)
        if government is not None:
            government.provide_baby_bonus(t, agent, new_agent)
        if government is not None:
            government.grant_parental_leave(t, agent)
    return number_food_consumed

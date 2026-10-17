"""
Demographics reproduction: agent births, fertility curves, heritable traits, and family trusts.
"""

import math

from goods import Goods
from agent import Agent, initialize_agent, seed_traits
from logger import logdebug
from random_cache import rand


def handle_reproduction(ctx, t, agent, agents, new_agents):
    """Handle birth of new agents."""
    if getattr(agent, 'is_native_child', False) and agent.age(t) < 18:
        return 0
    number_food_consumed = 0
    from nutrition import INITIAL_RESERVE_KCAL, deficit_fraction
    import government as govmod
    government = govmod.find_government_for_agent(agent)
    birth_prob = ctx.p_birth
    reserve_ratio = max(0.0, min(1.0,
        float(getattr(agent, 'energy_reserve_kcal', INITIAL_RESERVE_KCAL)) / INITIAL_RESERVE_KCAL))
    birth_prob *= math.exp(-2.0 * deficit_fraction(agent)) * (0.4 + 0.6 * reserve_ratio)
    if government is not None:
        birth_prob *= government.get_fertility_multiplier()

    cost_of_living = ctx.cost_of_living
    wealth = agent.wealth()
    if wealth > cost_of_living:
        wealth_factor = 1.0 / (1.0 + (wealth / cost_of_living) * 0.3)
        wealth_factor = max(0.25, wealth_factor)
        birth_prob *= wealth_factor
        if agent.is_trader:
            desired_children = 2.0 + 6.0 * math.exp(-wealth / max(1.0, cost_of_living * 3.0))
            living_children = sum(1 for d in agent.descendants if d.alive)
            birth_prob *= math.exp(-max(0.0, living_children - desired_children) / 2.0)

    eligible_to_reproduce = agent.last_reproduction + ctx.birth_gap < t
    reproduction_draw = rand.random() if eligible_to_reproduce else None
    has_birth_food = agent.inv_get(Goods.food, 0) >= 2
    if eligible_to_reproduce and reproduction_draw < birth_prob and has_birth_food:
        if ctx.max_agents > 0 and len(agents) + len(new_agents) >= ctx.max_agents:
            return 0

        # P3: Environmental Infant Mortality from Contaminated Drinking Water & Cholera
        reg = getattr(ctx, 'source_region', None)
        if reg is not None:
            has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(reg, 'buildings', []))
            if not has_sewer:
                p_water = getattr(reg, 'pollution_water', 0.0)
                if p_water > 20.0:
                    survival_prob = max(0.35, 1.0 - (p_water - 20.0) * 0.008)
                    mortality_draw = rand.random()
                    if mortality_draw > survival_prob:
                        fatalities_before = getattr(reg, 'infant_fatalities_this_turn', 0)
                        reg.infant_fatalities_this_turn = getattr(reg, 'infant_fatalities_this_turn', 0) + 1
                        try:
                            from run_trace import emit
                            emit(reg, kind='infant_mortality', record_class='outcome',
                                 phase='demographics',
                                 subject={'type': 'tile', 'id': reg.name},
                                 metric_id='health.infant_fatalities', unit='people',
                                 before=fatalities_before,
                                 after=reg.infant_fatalities_this_turn,
                                 formula_id='demographics.water_contamination_infant_mortality.v1',
                                 inputs={'parent_id': getattr(agent, 'id', None),
                                         'water_pollution': p_water,
                                         'sewer_present': has_sewer,
                                         'pollution_threshold': 20.0,
                                         'base_survival_probability': survival_prob,
                                         'mortality_draw': mortality_draw,
                                         'birth_probability': birth_prob,
                                         'reproduction_draw': reproduction_draw,
                                         'parent_food': agent.inv_get(Goods.food, 0)})
                        except (TypeError, ValueError):
                            pass
                        agent.last_reproduction = t
                        food_to_give = min(1, agent.inv_get(Goods.food))
                        agent.inv_add(Goods.food, -food_to_give)
                        return 0

        agent.last_reproduction = t
        new_agent = Agent(t)
        new_agent.is_native_child = True
        new_agent.calorie_need_kcal = 1000.0
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
        if (reg is not None and getattr(reg, 'labor_scheduler_last_turn', -1) >= 0
                and output not in (Goods.food, Goods.wood, Goods.furniture)):
            output = (agent.output
                      if agent.output in (Goods.food, Goods.wood, Goods.furniture)
                      else Goods.food)
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
        new_agent.last_career_switch = int(t)
        if reg is not None:
            from livelihood_access import inherit_customary_access
            inherit_customary_access(reg, agent, new_agent, t)
        if wealth_val > cost_of_living * 4:
            new_agent._birth_parent_wealth = wealth_val
            new_agent._birth_protection_until = t + max(25, min(100, int(cash)))
        new_agents.append(new_agent)
        if reg is not None:
            try:
                from run_trace import emit
                emit(reg, kind='birth', record_class='outcome', phase='demographics',
                     subject={'type': 'tile', 'id': reg.name},
                     metric_id='people.births', unit='people', before=0, after=1,
                     formula_id='demographics.fertility_and_food_gate.v1',
                     inputs={'parent_id': getattr(agent, 'id', None),
                             'birth_probability': birth_prob,
                             'reproduction_draw': reproduction_draw,
                             'birth_gap_elapsed': eligible_to_reproduce,
                             'parent_food_before_transfer': agent.inv_get(Goods.food, 0) + food_to_give,
                             'new_agent_id': getattr(new_agent, 'id', None),
                             'new_agent_profession': getattr(output, 'name', str(output)),
                             'new_agent_cash': cash,
                             'new_agent_food': food_to_give})
            except (TypeError, ValueError):
                pass
        if government is not None:
            government.provide_baby_bonus(t, agent, new_agent)
        if government is not None:
            government.grant_parental_leave(t, agent)
    return number_food_consumed

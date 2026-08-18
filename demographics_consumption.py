"""
Demographics consumption: daily food intake, luxury goods consumption, and bottleneck weights.
"""

from goods import Goods
from agent import get_input_commodity, get_output_commodity
from logger import loginfo
from random_cache import rand


def compute_bottleneck_weights(ctx, agents, choices_list):
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


def consume_goods(ctx, agent, number_food_consumed, number_wood_consumed, number_furniture_consumed):
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
    if agent.inv_get(Goods.wood, 0) > 2 and get_input_commodity(agent) != Goods.wood \
       and get_output_commodity(agent) != Goods.wood:
        agent.inv_add(Goods.wood, -1)
        number_wood_consumed += 1
    if agent.inv_get(Goods.furniture, 0) > 0 and get_output_commodity(agent) != Goods.furniture \
       and rand.random() < .066:
        agent.inv_add(Goods.furniture, -1)
        number_furniture_consumed += 1
    return number_food_consumed, number_wood_consumed, number_furniture_consumed


def consume_daily_food(agent):
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
    agent.mem_push('mem_hunger', agent.hungry_steps)

"""Shared, read-only meal requirements and physically protected food stocks."""
from __future__ import annotations

import math
from goods import Goods
from nutrition import appetite_units, basic_food_units


def prepared_food_units(person):
    """Read the calorie-equivalent meal stock, including older/mock wallets."""
    inventory = getattr(person, 'inventory', ())
    try:
        return max(0, inventory[Goods.prepared_food.value])
    except (IndexError, KeyError, TypeError):
        return 0


def meal_gap(person):
    available = max(0, person.inv_get(Goods.food, 0)) + max(
        0, getattr(person, 'emergency_food_units', 0)) + prepared_food_units(person)
    return max(0, math.ceil(appetite_units(person) - available))


def dependents(person, region):
    turn = getattr(region, '_last_turn', 0)
    return [child for child in getattr(region, 'agents', ())
            if child.alive and getattr(child, 'is_native_child', False)
            and getattr(child, 'parent', None) is person and child.age(turn) < 14]


def household_demand(person, region, *, reserve_turns=None):
    from households import demand
    return demand(person, region, reserve_turns=reserve_turns)


def business_food_target(firm, region):
    recipe = getattr(region, 'recipes', {}).get(firm.output, {})
    inputs = (2 * max(0, recipe.get('numInput', 0)) * (1 + len(firm.employees))
              if recipe.get('input') == Goods.food else 0)
    store = (getattr(firm, 'company_store_enabled', False)
             or getattr(firm, 'pay_mode', 'cash') == 'scrip')
    workers = [w for w in firm.employees if w.alive and w.employer is firm]
    meals = sum(appetite_units(w) for w in workers) if store else 0
    # Explicit in-kind meal contracts and trader orders use their own budgets.
    contracted = max(0, getattr(firm, 'contracted_food_units', 0)) * len(workers)
    from agriculture import seed_gap
    return math.ceil(inputs + meals + contracted + seed_gap(region, firm))


def independent_food_inputs(person, region):
    recipe = getattr(region, 'recipes', {}).get(person.output, {})
    from agriculture import seed_gap
    return seed_gap(region, person) + (2 * max(0, recipe.get('numInput', 0))
            if person.employer is None and recipe.get('input') == Goods.food else 0)


def protected_food(actor, region, *, emergency=False):
    if actor.is_corporation:
        return business_food_target(actor, region)
    demand = household_demand(actor, region, reserve_turns=0 if emergency else None)
    other_food = demand['available'] - max(0, actor.inv_get(Goods.food, 0))
    return max(0, demand['target'] + independent_food_inputs(actor, region) - other_food)


def food_surplus(actor, region, *, emergency=False):
    if not actor.alive or actor.is_government or actor.is_trader:
        return 0
    return max(0, math.floor(actor.inv_get(Goods.food, 0)
                             - protected_food(actor, region, emergency=emergency)))


def household_bid(person, region, price, cash, *, reserve_turns=None):
    demand = household_demand(person, region, reserve_turns=reserve_turns)
    if reserve_turns is None and not demand['dependent_order']:
        demand = {**demand, 'input_reserve': independent_food_inputs(person, region)}
        demand['desired'] += demand['input_reserve']
    # Establish the per-unit budget before the quantity. The maximum nutrition
    # urgency premium is 75%; unspent cash remains available at settlement.
    unit_budget = min(max(0, cash), max(0, price) * 1.75)
    quantity = min(math.ceil(demand['desired']), max(0, math.floor(cash / unit_budget))) if unit_budget else 0
    return quantity, demand, unit_budget

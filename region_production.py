"""
Production engine (firm and independent production) with Cython acceleration.
"""

from collections import defaultdict
from goods import Goods
from random_cache import rand

try:
    import region_core as _c
except ImportError:
    _c = None


def terrain_bonus(region, good):
    """Production multiplier from terrain for *good* (default 1.0)."""
    return region.terrain.get(good, 1.0)


def produce_corporation(region, agent, recipe, output, num_agents_per_good, local_total_production):
    """Run production logic for a corporate employer."""
    num_employees = len(agent.employees)
    max_inventory = recipe['maxinv'] * (1 + num_employees)
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    num_slots = num_employees
    if recipe.get('numInput', 0) > 0:
        available = agent.inv_get(recipe['input'], 0)
        active_slots = int(min(num_slots, available // recipe['numInput']))
    else:
        active_slots = int(num_slots)
    if active_slots <= 0 or recipe.get('production', 0) <= 0:
        return
    synergy = 1.0 + (0.15 if num_employees < 4 else 0.20 if num_employees < 8 else 0.25 if num_employees < 12 else 0.30) * num_employees
    base_production = recipe['production']
    production_per_slot = base_production * synergy * terrain_bonus(region, output)
    chance = 1.0
    if agent.hungry_steps > 0:
        chance *= 1 / (1 + agent.hungry_steps * 0.2)
    if output in (Goods.food, Goods.wood):
        chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / base_production)
    chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
    vals = rand.random_n(active_slots)
    if _c is not None:
        successful_slots = _c.produce_corporation_slots(active_slots, chance, vals)
    else:
        successful_slots = sum(1 for v in vals if v < chance)
    if successful_slots:
        if recipe.get('numInput', 0) > 0:
            agent.inv_add(recipe['input'], -successful_slots * recipe['numInput'])
        num_output = int(successful_slots * production_per_slot) or 1
        agent.inv_add(output, num_output)
        local_total_production[output] += num_output


def produce_independent(region, agent, recipe, output, num_agents_per_good, local_total_production):
    """Run production logic for an independent sole craftsman."""
    max_inventory = recipe['maxinv']
    if agent.inv_get(output, 0) / max_inventory >= 1:
        return
    has_inputs = True
    if recipe['numInput'] > 0 and agent.inv_get(recipe['input'], 0) < recipe['numInput']:
        has_inputs = False
    num_output = 0
    if has_inputs and recipe.get('production', 0) > 0:
        chance = 1.0
        if agent.hungry_steps > 0:
            chance *= 1 / (1 + agent.hungry_steps * 0.2)
        if output in (Goods.food, Goods.wood):
            chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / recipe['production'])
        chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
        rand_val = rand.random()
        if _c is not None:
            made = _c.produce_independent_check(chance, rand_val)
        else:
            made = 1 if rand_val < chance else 0
        if made:
            if recipe['numInput'] > 0:
                agent.inv_add(recipe['input'], -recipe['numInput'])
            num_output = int(recipe['production'] * terrain_bonus(region, output))
    agent.inv_add(output, num_output)
    local_total_production[output] += num_output


def produce(region, t):
    """Run production phase for all active producers in region."""
    num_agents_per_good = {}
    for a in region.agents:
        if not a.is_trader and a.output != Goods.gov:
            num_agents_per_good[a.output] = num_agents_per_good.get(a.output, 0) + 1
    for g in region.goods:
        if g not in num_agents_per_good:
            num_agents_per_good[g] = 0
    local_total_production = defaultdict(int)
    for a in region.agents:
        if a.employer or a.output == Goods.gov or a.is_trader:
            continue
        r = region.recipes[a.output]
        if a.is_corporation and len(a.employees) > 0:
            produce_corporation(region, a, r, a.output, num_agents_per_good, local_total_production)
        else:
            produce_independent(region, a, r, a.output, num_agents_per_good, local_total_production)
    for g in region.goods:
        if g != Goods.gov:
            region.production_log[g].append(local_total_production[g])

"""
Production engine (firm and independent production) with Cython acceleration.
"""

from collections import defaultdict
from goods import Goods
from random_cache import rand
from labor_contract import calculate_shift_multiplier, record_surplus_value

try:
    import region_core as _c
except ImportError:
    _c = None


def terrain_bonus(region, good):
    """Production multiplier from terrain and installed buildings for *good* (default 1.0)."""
    base = region.terrain.get(good, 1.0)
    mult = 1.0
    for b in getattr(region, 'buildings', []):
        bonuses = getattr(b, 'production_bonuses', {})
        if good in bonuses:
            mult *= bonuses[good]
    # P3: Metabolic Rift & Soil Fertility for agricultural food crops
    if good == Goods.food:
        soil_fert = getattr(region, 'soil_fertility', 1.0)
        mult *= soil_fert

        # Phase 1 Enclosure Vector: Pastoral conversion replaces food crops
        tenure = getattr(region, 'tenure', None)
        if tenure is not None:
            p_frac = getattr(tenure, 'pasture_fraction', 0.0)
            if p_frac > 0:
                mult *= max(0.20, 1.0 - (0.75 * p_frac))

        use_fert = getattr(region, 'use_fertilizer', False) or getattr(region, 'mandate_fertilizer', False)
        use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)

        if use_fert:
            # Physical fertilizer stock consumption
            stock = getattr(region, 'fertilizer_stock', 0.0)
            farm_corps = sum(1 for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False) and getattr(a, 'output', None) == Goods.food)
            needed = 1.0 + 0.5 * farm_corps
            if getattr(region, 'fertilizer_rationing', False):
                needed *= 0.5
            if stock >= needed:
                region.fertilizer_stock -= needed
                region.fertilizer_consumed_last_turn = needed
                region.is_nitrate_depleted = False
                mult *= 1.75
            else:
                region.fertilizer_consumed_last_turn = 0.0
                # Fertilizer shortage!
                if soil_fert < 0.65:
                    # Turnip Winter Harvest Shock on depleted soil
                    region.is_nitrate_depleted = True
                    mult *= 0.50
                else:
                    region.is_nitrate_depleted = False
        else:
            region.is_nitrate_depleted = False

        if use_pest:
            mult *= 1.40
    return base * mult


def produce_corporation(region, agent, recipe, output, num_agents_per_good, local_total_production):
    """Run production logic for a corporate employer."""
    # P2.3: Striking or revolting workers withhold living labor power
    working_employees = [e for e in agent.employees if not getattr(e, 'is_striking', False) and not getattr(e, 'in_revolt', False)]
    num_employees = len(working_employees)
    if num_employees == 0:
        return
    max_inventory = recipe['maxinv'] * (1 + len(agent.employees))
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

    # P2.1: Shift length multiplier and machinery capacity
    shift_mult = calculate_shift_multiplier(getattr(agent, 'shift_hours', 8.0))
    production_per_slot = base_production * synergy * terrain_bonus(region, output) * shift_mult

    machinery = getattr(agent, 'machinery_level', 1)
    broken = getattr(agent, 'broken_machinery', 0)
    working_machinery = max(0, machinery - broken)
    if working_machinery < 1:
        # If all machinery broken by sabotage, manual labor has 50% productivity penalty
        production_per_slot *= 0.5

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
        inputs_cost = 0.0
        if recipe.get('numInput', 0) > 0:
            inputs_used = successful_slots * recipe['numInput']
            agent.inv_add(recipe['input'], -inputs_used)
            input_price = region.recipes.get(recipe['input'], {}).get('price', 1.0)
            inputs_cost = inputs_used * input_price
        num_output = int(successful_slots * production_per_slot) or 1
        agent.inv_add(output, num_output)
        local_total_production[output] += num_output

        # P2.1: Surplus value extraction accounting (s/v)
        wages_paid = len(agent.employees) * getattr(agent, 'wage', 1.0)
        record_surplus_value(agent, region, output, num_output, inputs_cost, wages_paid)


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
        if not a.is_trader and a.output != Goods.gov and a.output != Goods.none and a.output in region.recipes:
            num_agents_per_good[a.output] = num_agents_per_good.get(a.output, 0) + 1
    for g in region.goods:
        if g not in num_agents_per_good:
            num_agents_per_good[g] = 0
    local_total_production = defaultdict(int)
    for a in region.agents:
        if a.employer or a.output == Goods.gov or a.is_trader or a.output == Goods.none or a.output not in region.recipes:
            continue
        if getattr(a, 'is_striking', False) or getattr(a, 'in_revolt', False):
            continue
        r = region.recipes[a.output]
        if a.is_corporation and len(a.employees) > 0:
            produce_corporation(region, a, r, a.output, num_agents_per_good, local_total_production)
        else:
            produce_independent(region, a, r, a.output, num_agents_per_good, local_total_production)

    # Phase 1: Pastoral wool / fiber yield for landlords on pasture plots
    tenure = getattr(region, 'tenure', None)
    if tenure is not None:
        for plot in getattr(tenure, 'plots', []):
            if getattr(plot, 'production_type', 'arable') == 'pasture':
                lord = None
                for a in region.agents:
                    if a.id == plot.lord_id:
                        lord = a
                        break
                if lord and lord.alive:
                    wool_yield = max(1, int(4 * plot.fraction * terrain_bonus(region, Goods.wood)))
                    lord.inv_add(Goods.wood, wool_yield)
                    local_total_production[Goods.wood] += wool_yield

    for g in region.goods:
        if g != Goods.gov:
            region.production_log[g].append(local_total_production[g])

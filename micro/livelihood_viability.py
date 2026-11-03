"""Stay/pressure/search gate. Better pay alone does not create a job seeker."""
from __future__ import annotations
from goods import Goods


def secured_meals(region, person, good, expected_return, employer=None, market=None):
    """Comparable nutrition access; high wages cannot buy absent grain."""
    from households import demand, human
    from foraging import potential
    from food_access import food_surplus
    family = demand(person, region, reserve_turns=0)
    required = family['ordinary']
    price = max(.01, region.recipes[Goods.food]['price'])
    retained = 0.0
    if employer is None and good == Goods.food:
        retained = max(0, expected_return) / price
    elif employer is not None:
        contracted = max(0, getattr(employer, 'contracted_food_units', 0))
        retained = min(contracted, employer.inv_get(Goods.food, 0) / max(1, len(employer.employees)))
    offered = market['offered'] if market else sum(food_surplus(a, region) for a in region.agents)
    buyers = (market['buyers'] if market else
              max(1, len(getattr(region, 'households', {})) or sum(human(a) for a in region.agents)))
    purchase = min(offered / buyers, max(0, expected_return - retained * price) / price)
    return min(required, family['available'] / 10 + potential(person, region) + retained + purchase)


def assess(region, person, turn, expected_return):
    from households import demand
    from career_transitions import profession
    family = demand(person, region, reserve_turns=0)
    price = max(.01, region.recipes[Goods.food]['price'])
    bank = getattr(region, 'bank', None)
    deposits = (bank.deposits.get(person, 0) if bank and not getattr(bank, 'is_frozen', False) else 0)
    liquid = max(0, person.cash) + max(0, deposits)
    wood = max(0, region.recipes.get(Goods.wood, {}).get('price', 1)) * .5
    necessities = family['ordinary'] * price + wood
    from foraging import potential
    from agriculture import turns_until_harvest
    horizon = turns_until_harvest(region) if profession(person) == Goods.food else 1
    commons_value = potential(person, region) * price
    buffer_value = min(family['ordinary'], family['available'] / max(1, horizon)) * price
    wood_buffer = min(.5, person.inv_get(Goods.wood, 0) / max(1, horizon)) * region.recipes.get(Goods.wood, {}).get('price', 1)
    gap = max(0, necessities - expected_return - commons_value - buffer_value - wood_buffer)
    runway = liquid / gap if gap > .001 else None
    prior = dict(getattr(person, 'livelihood_viability', {}))
    if prior.get('turn') == turn:
        return prior
    employer = getattr(person, 'employer', None)
    lost_job = prior.get('employer_id') is not None and employer is None
    lost_right = prior.get('field_access', 0) > 0
    from livelihood_access import effective_access
    field = effective_access(person, region, 'field')
    lost_right = lost_right and field <= 0 and profession(person) == Goods.food
    immediate = bool(getattr(person, 'calorie_deficit_kcal', 0) > 0 or lost_job or lost_right)
    old = profession(person)
    new_entrant = old is None or getattr(person, 'primary_livelihood', None) is None
    threshold = max(0, float(getattr(region, 'livelihood_cash_runway', 2)))
    pressure = gap > .001 and runway is not None and runway < threshold
    previous_count = prior.get('pressure_turns', 0) if prior.get('turn') == turn - 1 else 0
    count = previous_count + 1 if pressure else 0
    seeking = immediate or new_entrant or count >= max(1, int(getattr(region, 'livelihood_pressure_observations', 2)))
    reason = ('meal_failure' if getattr(person, 'calorie_deficit_kcal', 0) > 0 else
              'livelihood_lost' if lost_job or lost_right else 'first_entry' if new_entrant else
              'persistent_short_runway' if seeking else 'under_pressure' if pressure else
              'household_needs_covered')
    row = {'turn': turn, 'state': 'seeking' if seeking else 'pressure' if pressure else 'stable',
           'seeking': seeking, 'reason': reason, 'pressure_turns': count,
           'necessities_cost': necessities, 'expected_return': expected_return,
           'commons_food_value': commons_value, 'food_buffer_value': buffer_value,
           'wood_buffer_value': wood_buffer, 'uncovered_resource_cost': gap,
           'cash_runway': runway, 'liquid_funds': liquid,
           'employer_id': employer.id if employer else None, 'field_access': field}
    person.livelihood_viability = row
    return row

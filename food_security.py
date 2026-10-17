"""Conserved public response to food shortages and unequal food access."""

from __future__ import annotations

from goods import Goods
from nutrition import basic_food_units


def forecast_commons_food(person, tile) -> int:
    """Read the same customary access and yield rule used by foraging."""
    from foraging import BASE_FORAGE_YIELD, can_forage
    from livelihood_access import effective_access

    if not can_forage(person, tile):
        return 0
    access = effective_access(person, tile, 'commons_food')
    fertility = tile.terrain.get(Goods.food, 1.0)
    return min(4, max(1, int(BASE_FORAGE_YIELD * access * fertility)))


def diagnose_tile(tile) -> dict:
    """Read the current household food position before the next turn begins."""
    residents = [a for a in getattr(tile, 'agents', [])
                 if a.alive and not a.is_corporation and not a.is_government
                 and not getattr(a, 'military_unit_id', None)]
    population = len(residents)
    food_in_hands = sum(max(0, a.inv_get(Goods.food, 0)) for a in residents)
    forage = {a.id: forecast_commons_food(a, tile) for a in residents}
    forecast_forage = sum(forage.values())
    minimum_meal = sum(basic_food_units(a) for a in residents)
    missing_meals = sum(max(0, basic_food_units(a) - a.inv_get(Goods.food, 0) - forage[a.id])
                        for a in residents)
    underfed = sum(a.calorie_deficit_kcal > 0 for a in residents)
    producers = sum(a.output == Goods.food and a.employer is None
                    and not (getattr(a, 'is_native_child', False)
                             and a.age(getattr(tile, '_last_turn', 0)) < 14)
                    for a in residents)
    production_log = getattr(tile, 'production_log', {}).get(Goods.food, [])
    estimated_harvest = (production_log[-1] if production_log else
                         producers * tile.recipes[Goods.food]['production'] * 0.65)
    # A one-turn windfall cannot make permanent enclosure safe. Demand three
    # consecutive harvests that could feed residents without customary access.
    food_buffer_proven = (len(production_log) >= 3
                          and min(production_log[-3:]) >= minimum_meal * 1.1
                          and underfed / max(1, population) < 0.03)
    enclosure_risk = bool(population and not food_buffer_proven
                          and getattr(getattr(tile, 'tenure', None), 'feudal_fraction', 0) > 0)
    government_food = max(0, getattr(tile.gov, 'food_inventory', 0))
    expected_gap = max(0, minimum_meal - food_in_hands - forecast_forage
                       - estimated_harvest
                       - government_food)
    underfed_share = underfed / max(1, population)
    shortage = (estimated_harvest < minimum_meal * 0.8
                and (expected_gap > 0 or underfed_share >= 0.15))
    access = underfed_share >= 0.15 or missing_meals > minimum_meal * 0.2
    if shortage and access:
        diagnosis = 'shortage_and_access'
    elif shortage:
        diagnosis = 'shortage'
    elif access:
        diagnosis = 'access'
    else:
        diagnosis = 'stable'
    emergency = bool(population and (
        expected_gap >= minimum_meal * 0.1
        or missing_meals > minimum_meal * 0.2
        or underfed_share >= 0.15
        or getattr(tile, 'deaths_this_turn', 0) > 0))
    return {
        'tile': tile.name,
        'residents': population,
        'food_producers': producers,
        'minimum_meal_units': minimum_meal,
        'household_food_units': food_in_hands,
        'forecast_commons_food_units': forecast_forage,
        'government_food_units': government_food,
        'missing_meal_units': missing_meals,
        'recent_food_production': round(float(estimated_harvest), 2),
        'food_buffer_proven': food_buffer_proven,
        'enclosure_risk': enclosure_risk,
        'projected_supply_gap': round(float(expected_gap), 2),
        'underfed_residents': underfed,
        'underfed_share': round(underfed_share, 4),
        'diagnosis': diagnosis,
        'emergency': emergency,
    }


def enact_nation_food_response(nation, turn: int) -> list[dict]:
    """Set local relief and transfer only spendable sovereign cash to local buyers."""
    from run_trace import emit

    assessments = [(tile, diagnose_tile(tile)) for tile in nation.tiles]
    responses = []
    sovereign = nation.government.agent
    # A province can share one municipal government across several tiles.
    # A stable neighbor must not switch off relief for the hungry tile.
    government_emergency = {}
    for tile, assessment in assessments:
        government_emergency[tile.gov] = (government_emergency.get(tile.gov, False)
                                          or assessment['emergency'])
    for gov, emergency in government_emergency.items():
        gov.emergency_food_policy = emergency
        if not emergency:
            gov.emergency_meal_target = 0
    # A real competing use of the national treasury remains available for
    # defense, diplomacy and construction even during a food emergency.
    transfer_budget = max(0.0, min(sovereign.cash * 0.5,
                                    sovereign.cash - 150.0))
    for tile, assessment in sorted(assessments,
                                   key=lambda item: (-item[1]['underfed_share'],
                                                     -item[1]['projected_supply_gap'],
                                                     item[0].name)):
        gov = tile.gov
        tile.food_enclosure_moratorium = assessment['enclosure_risk']
        price = max(0.01, float(tile.recipes[Goods.food]['price']))
        local_liquid = gov.agent.cash + tile.bank.deposits.get(gov.agent, 0.0)
        purchase_need = max(assessment['missing_meal_units'],
                            assessment['projected_supply_gap'])
        funding_gap = max(0.0, purchase_need * price - local_liquid)
        amount = (min(transfer_budget, funding_gap, 150.0)
                  if assessment['emergency'] else 0.0)
        if amount > 0 and gov is not nation.government:
            before_sovereign, before_local = sovereign.cash, gov.agent.cash
            sovereign.cash -= amount
            gov.agent.cash += amount
            transfer_budget -= amount
            emit(tile, kind='public_food_budget_transfer', record_class='transfer',
                 phase='strategy',
                 subject={'type': 'nation', 'id': nation.name},
                 metric_id='finance.internal_transfer', unit=nation.currency,
                 after=amount,
                 inputs={'tile': tile.name, 'source': 'sovereign',
                         'recipient': 'municipal_government',
                         'source_cash_before': before_sovereign,
                         'source_cash_after': sovereign.cash,
                         'recipient_cash_before': before_local,
                         'recipient_cash_after': gov.agent.cash})
        response = {**assessment, 'food_policy': 'emergency_meals' if
                    gov.emergency_food_policy else 'ordinary',
                    'enclosure_moratorium': tile.food_enclosure_moratorium,
                    'funding_transferred': round(amount, 2),
                    'municipal_liquid': round(local_liquid + amount, 2)}
        responses.append(response)
        emit(tile, kind='food_security_assessment', record_class='decision',
             phase='strategy', subject={'type': 'tile', 'id': tile.name},
             metric_id='people.food_security', unit='residents',
             after=assessment['underfed_residents'],
             inputs=response)
    return responses

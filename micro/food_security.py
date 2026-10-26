"""Conserved public response to food shortages and unequal food access."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

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
    government_food = max(0, getattr(tile.gov, 'food_inventory', 0))
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
    # Require evidence across the full ten-turn crop cycle. Compare cycle
    # production with cycle demand, then include food households can actually
    # reach now (household/public stocks and customary foraging).
    cycle_turns = 10
    observed_cycle_turns = min(cycle_turns, len(production_log))
    cycle_production = sum(production_log[-cycle_turns:])
    cycle_demand = minimum_meal * cycle_turns
    accessible_buffer = food_in_hands + government_food
    projected_cycle_margin = cycle_production - cycle_demand + accessible_buffer
    projected_with_commons_margin = (projected_cycle_margin
                                     + forecast_forage * cycle_turns)
    # Commons foraging helps households survive today, but cannot prove that
    # enclosure is safe because enclosure would remove that same food route.
    food_buffer_proven = (len(production_log) >= cycle_turns
                          and projected_cycle_margin >= cycle_demand * 0.1
                          and underfed / max(1, population) < 0.03)
    enclosure_risk = bool(population and not food_buffer_proven
                          and getattr(getattr(tile, 'tenure', None), 'feudal_fraction', 0) > 0)
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
        'crop_cycle_turns': cycle_turns,
        'observed_crop_cycle_turns': observed_cycle_turns,
        'crop_cycle_production': round(float(cycle_production), 2),
        'crop_cycle_meal_demand': round(float(cycle_demand), 2),
        'accessible_food_buffer': round(float(accessible_buffer), 2),
        'projected_crop_cycle_margin': round(float(projected_cycle_margin), 2),
        'forecast_commons_cycle_food': round(float(forecast_forage * cycle_turns), 2),
        'projected_crop_cycle_margin_with_commons': round(float(projected_with_commons_margin), 2),
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
    from finance_trace import account_ref, transfer_contract

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
        funding_event_id = None
        if amount > 0 and gov is not nation.government:
            before_sovereign, before_local = sovereign.cash, gov.agent.cash
            sovereign_change = begin_public_change(tile, sovereign)
            local_change = begin_public_change(tile, gov.agent)
            sovereign.cash -= amount
            gov.agent.cash += amount
            finish_public_change(sovereign_change, 'national_food_relief_grant_debit')
            finish_public_change(local_change, 'national_food_relief_grant_receipt')
            transfer_budget -= amount
            operation_id = (f'nation-food-response:{nation.name}:'
                            f'{int(turn)}:{tile.name}')
            currency = (getattr(nation, 'currency', None)
                        or getattr(tile, 'home_currency', None)
                        or 'local_currency')
            recipient_currency = (getattr(tile, 'home_currency', None)
                                  or currency)
            common = {
                'operation_id': operation_id,
                'operation_type': 'nation_food_response',
                'amount': float(amount),
                'amount_currency': currency,
                'payer_account': account_ref(
                    'national_treasury', str(sovereign.id), currency,
                    nation_id=nation.name,
                    balance_before=float(before_sovereign),
                    balance_after=float(sovereign.cash),
                    balance_scope='government_agent.cash'),
                'payee_account': account_ref(
                    'municipal_treasury', str(gov.agent.id), recipient_currency,
                    tile=tile.name, nation_id=nation.name,
                    government_name=getattr(gov, 'name', None),
                    balance_before=float(before_local),
                    balance_after=float(gov.agent.cash),
                    balance_scope='government_agent.cash'),
                'local_cash_leg_amount': float(amount),
                'counterparty_leg_status': 'paired_internal_transfer_same_nation',
                'source': 'sovereign_food_security_transfer',
                'tile': tile.name,
                'turn': int(turn),
            }
            payer_contract = transfer_contract(
                side='payer',
                local_cash_leg_currency=currency,
                **common)
            debit_event_id = emit(
                tile, kind='public_food_budget_transfer_debit',
                record_class='transfer', phase='strategy',
                subject={'type': 'nation/treasury', 'id': nation.name},
                metric_id='finance.internal_transfer', unit=currency,
                after=-float(amount),
                inputs={'operation_id': operation_id,
                        'transfer_contract': payer_contract})
            payee_contract = transfer_contract(
                side='payee',
                local_cash_leg_currency=recipient_currency,
                **common)
            funding_event_id = emit(
                tile, kind='public_food_budget_transfer',
                record_class='transfer', phase='strategy',
                subject={'type': 'nation', 'id': nation.name},
                metric_id='finance.internal_transfer', unit=recipient_currency,
                after=float(amount),
                inputs={'operation_id': operation_id,
                        'tile': tile.name, 'source': 'sovereign',
                        'recipient': 'municipal_government',
                        'source_cash_before': float(before_sovereign),
                        'source_cash_after': float(sovereign.cash),
                        'recipient_cash_before': float(before_local),
                        'recipient_cash_after': float(gov.agent.cash),
                        'transfer_contract': payee_contract},
                cause_event_ids=[debit_event_id] if debit_event_id else None)
        response = {**assessment, 'nation': nation.name,
                    'food_policy': 'emergency_meals' if
                    gov.emergency_food_policy else 'ordinary',
                    'enclosure_moratorium': tile.food_enclosure_moratorium,
                    'funding_transferred': round(amount, 2),
                    'municipal_liquid': round(local_liquid + amount, 2)}
        responses.append(response)
        emit(tile, kind='food_security_assessment', record_class='decision',
             phase='strategy', subject={'type': 'tile', 'id': tile.name},
             metric_id='people.food_security', unit='residents',
             after=assessment['underfed_residents'], inputs=response,
             cause_event_ids=[funding_event_id] if funding_event_id else None)
    return responses

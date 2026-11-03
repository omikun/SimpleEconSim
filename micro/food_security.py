"""Conserved public response to food shortages and unequal food access."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

from goods import Goods
from nutrition import basic_food_units


def forecast_commons_food(person, tile):
    from foraging import potential
    return potential(person, tile)


def diagnose_tile(tile):
    from food_outlook import snapshot
    return snapshot(tile)


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

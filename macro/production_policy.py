"""Bounded public production programs with actual escrow, work and deliveries."""
from __future__ import annotations
import math
from goods import Goods

KINDS = ('procurement', 'working_capital', 'seasonal_hiring', 'relief')


def submit(region, kind, good, quantity, budget, duration, turn, *, payer=None):
    if kind not in KINDS:
        raise ValueError('Unknown production program')
    good = Goods[good] if isinstance(good, str) else Goods(good)
    numbers = (quantity, budget, duration)
    if any(not math.isfinite(float(v)) or float(v) <= 0 for v in numbers) or duration > 30 or float(duration) != int(duration):
        raise ValueError('Positive quantity/budget and a duration of at most 30 turns are required')
    if good not in region.recipes or good in (Goods.none, Goods.gov):
        raise ValueError('Unsupported commodity')
    if kind in ('relief', 'seasonal_hiring') and good != Goods.food:
        raise ValueError('Relief and seasonal farm hiring require food as the target')
    payer = payer or region.gov.agent
    bank = getattr(region, 'bank', None)
    deposits = bank.deposits.get(payer, 0) if bank and not getattr(bank, 'is_frozen', False) else 0
    if budget > payer.cash + deposits + 1e-9:
        raise ValueError('Treasury cannot fund this program')
    if budget > payer.cash:
        bank.Withdraw(payer, budget - payer.cash, trace_region=region, t=turn,
                      reason='production_program_funding')
    from agent import Agent
    from state_handler import transfer_cash
    account = Agent(turn)
    account.is_government = True
    account.output = Goods.gov
    account.home_currency = region.home_currency
    account.region = region.name
    account.company_name = f'{kind} public escrow'
    region.agents.append(account)
    transfer_cash(payer, account, budget, region=region, kind='production_program_funding',
                  record_event_kind='public_program_funding', turn=turn)
    programs = getattr(region, 'production_programs', [])
    row = {'id': f'{region.name}:program:{len(programs) + 1}', 'kind': kind, 'good': good.name,
           'quantity': float(quantity), 'delivered': 0.0, 'budget': float(budget),
           'escrow_id': account.id, 'payer_id': payer.id, 'submitted_turn': turn,
           'starts_turn': turn + 1, 'expires_turn': turn + int(duration),
           'status': 'active', 'last_prepared': None, 'last_settled': None,
           'unit_ceiling': float(region.recipes[good]['price']) * 1.5,
           'spent': 0.0, 'loans': []}
    if kind == 'seasonal_hiring':
        row['unit_ceiling'] = (4 * region.recipes[Goods.food]['price'] + .5 * region.recipes[Goods.wood]['price']) * 10 / 4.5
    programs.append(row)
    region.production_programs = programs
    return row


def _actors(region):
    result = {a.id: a for a in region.agents}
    nation = getattr(region, 'owner_nation', None)
    if nation is not None:
        result[nation.government.agent.id] = nation.government.agent
    return result


def prepare_programs(region, turn):
    from agriculture import requirements
    from state_handler import transfer_cash
    actors = _actors(region)
    region.seasonal_work_orders = []
    for row in getattr(region, 'production_programs', ()):
        if row['status'] != 'active' or not row['starts_turn'] <= turn <= row['expires_turn'] or row['last_prepared'] == turn:
            continue
        row['last_prepared'] = turn
        escrow = actors[row['escrow_id']]
        left = max(0, row['quantity'] - row['delivered'])
        if row['kind'] == 'seasonal_hiring':
            for key, amount in requirements(region, turn).items():
                if amount > 0 and left > 0:
                    region.seasonal_work_orders.append({'turn': turn, 'program_id': row['id'],
                        'farm_id': key, 'payer_id': escrow.id, 'pay_rate': row['unit_ceiling'],
                        'quantity': min(left, amount), 'delivered': 0.0, 'completed': False})
                    left -= min(left, amount)
        elif row['kind'] == 'working_capital':
            from career_transitions import profession
            from livelihood_access import assess_obligation
            good = Goods[row['good']]
            for actor in sorted(region.agents, key=lambda a: a.id):
                if not actor.alive or actor.is_government or actor.is_trader or getattr(actor, 'business_closed', False):
                    continue
                from agriculture import can_operate
                operator = good == Goods.food and any(f['operator_id'] == actor.id and can_operate(region, f, actor) for f in region.farms.values())
                if (profession(actor) != good and not operator) or any(loan['recipient_id'] == actor.id for loan in row['loans']):
                    continue
                recipe = region.recipes[good]
                if good == Goods.food:
                    need = sum(max(0, f['area'] * 6 - f.get('food_milli', 0) / 1000)
                               for f in region.farms.values() if f['operator_id'] == actor.id) * region.recipes[Goods.food]['price']
                else:
                    ingredient = recipe.get('input')
                    need = (max(0, recipe.get('numInput', 0) * 2 - actor.inv_get(ingredient, 0))
                            * region.recipes.get(ingredient, {}).get('price', 0)) if ingredient else 0
                amount = min(max(0, need - actor.cash), escrow.cash, left)
                if amount <= 0:
                    continue
                transfer_cash(escrow, actor, amount, region=region, kind='productive_advance',
                              record_event_kind='public_productive_loan', turn=turn)
                claim = assess_obligation(region, actor.id, escrow.id, 'productive_advance', amount, turn + 10)
                row['loans'].append({'recipient_id': actor.id, 'principal': amount, 'claim_id': claim.id})
                row['delivered'] += amount
                left -= amount
        row['spent'] = max(0, row['budget'] - escrow.cash)


def settle_programs(region, turn):
    from state_handler import transfer_cash
    from food_accounts import transfer, PublicAccount
    from food_access import food_surplus
    from region_market import calculate_ask, calculate_ask_price, record_paid_price
    actors = _actors(region)
    for row in getattr(region, 'production_programs', ()):
        if row['last_settled'] == turn:
            continue
        row['last_settled'] = turn
        escrow, payer = actors[row['escrow_id']], actors.get(row['payer_id'], region.gov.agent)
        if row['status'] != 'active':
            # Repayments on old advances still return to the original treasury.
            if escrow.cash > 0:
                transfer_cash(escrow, payer, escrow.cash, region=region,
                              kind='public_advance_repayment', record_event_kind='public_advance_repayment', turn=turn)
            continue
        if row['starts_turn'] <= turn <= row['expires_turn']:
            good = Goods[row['good']]
            left = max(0, row['quantity'] - row['delivered'])
            if row['kind'] in ('procurement', 'relief'):
                for seller in sorted(region.agents, key=lambda a: a.id):
                    if seller.is_government or not seller.alive or seller.is_trader:
                        continue
                    units = (food_surplus(seller, region) if good == Goods.food else
                             calculate_ask(region, seller, good, region.recipes[good]['price'], seller.employer is not None))
                    ask = calculate_ask_price(region, seller, good, region.recipes[good]['price'])
                    if ask <= 0 or ask > row['unit_ceiling']:
                        continue
                    bought = min(units, left, escrow.cash / ask)
                    if row['kind'] == 'procurement' and good == Goods.food:
                        from food_storage import granary_capacity
                        bought = min(bought, max(0, granary_capacity(region) - region.granary_stock))
                    bought = int(bought * 1000) / 1000
                    if bought <= 0:
                        continue
                    transfer_cash(escrow, seller, bought * ask, region=region,
                                  kind='public_procurement', record_event_kind='public_procurement', turn=turn)
                    if good in (Goods.food, Goods.prepared_food):
                        transfer(region, seller, escrow, bought, kind='public_procurement', good=good)
                        if row['kind'] == 'procurement' and good == Goods.food:
                            transfer(region, escrow, PublicAccount(region), bought, kind='public_reserve_deposit')
                    else:
                        seller.inv_add(good, -bought)
                        escrow.inv_add(good, bought)
                    row['delivered'] += bought
                    left -= bought
                    record_paid_price(region, good, turn, bought, bought * ask)
            elif row['kind'] == 'seasonal_hiring':
                row['delivered'] += sum(o['delivered'] for o in region.seasonal_work_orders if o['program_id'] == row['id'])
            if row['kind'] == 'relief':
                from households import human
                from nutrition import basic_food_units
                for person in sorted((a for a in region.agents if human(a)), key=lambda a: (a.energy_reserve_kcal, a.id)):
                    gap = max(0, basic_food_units(person) - person.inv_get(Goods.food, 0) - person.inv_get(Goods.prepared_food, 0))
                    transfer(region, escrow, person, gap, kind='targeted_relief')
        row['spent'] = max(0, row['budget'] - escrow.cash)
        if turn >= row['expires_turn'] or row['delivered'] >= row['quantity'] - .001:
            row['status'] = 'completed' if row['delivered'] >= row['quantity'] - .001 else 'expired'
            transfer_cash(escrow, payer, max(0, escrow.cash), region=region,
                          kind='production_program_refund', record_event_kind='public_program_refund', turn=turn)
            for good in (Goods.food, Goods.prepared_food):
                if escrow.inv_get(good, 0):
                    destination = PublicAccount(region, 'aid') if good == Goods.food else payer
                    transfer(region, escrow, destination, escrow.inv_get(good, 0), kind='public_program_inventory', good=good)


def decide_nation(nation, turn):
    """Small bounded response, only for nations explicitly running policy AI."""
    from production_needs import needs
    budget = max(0, nation.government.agent.cash) * .02
    for region in nation.tiles:
        if any(p['status'] == 'active' for p in getattr(region, 'production_programs', ())):
            continue
        rows = [r for r in needs(region) if r['essential'] and r['gap_per_turn'] > 0
                and r['coverage_turns'] is not None and r['coverage_turns'] < 2]
        prior = getattr(region, 'production_pressure_turns', 0)
        region.production_pressure_turns = prior + 1 if rows else 0
        if not rows or region.production_pressure_turns < 2 or budget < 1:
            continue
        target = max(rows, key=lambda r: r['gap_per_turn'] / max(.01, r['requirements_per_turn']))
        response = target['response']
        if response not in KINDS:
            continue
        amount = min(budget, 100)
        quantity = amount if response == 'working_capital' else max(1, target['gap_per_turn'] * 2)
        if response == 'seasonal_hiring':
            from agriculture import stage
            if stage(region, turn) == 'fallow':
                continue
        submit(region, response, target['good'], quantity, amount, 2, turn,
               payer=nation.government.agent)
        budget -= amount

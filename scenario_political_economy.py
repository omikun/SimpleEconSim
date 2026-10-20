"""Private grain, cultivator tenure, collective action, and fiscal choices in Egypt."""

from __future__ import annotations

from math import exp
from random import Random

from finance_trace import (account_ref, cash_transfer_contract,
                           emit_cash_transfer, emit_treasury_leg,
                           transfer_contract)
from goods import Goods
from nutrition import deficit_fraction


NATIONAL_ACTIONS = frozenset({'buy_private_grain', 'requisition_private_grain',
                              'open_private_grain_market', 'extend_collection_term'})
DISTRICT_ACTIONS = frozenset({'district_arrears_relief', 'district_bargain_workers',
                              'district_support_mutual_aid', 'district_break_strike'})
WAREHOUSE_CAPACITY_PER_DISTRICT = 60
CADASTRAL_ASSESSMENT_MULTIPLIER = 1.0
NATIONAL_CADASTRAL_SHARE = 0.25


def _households(tile):
    return [a for a in tile.agents if getattr(a, 'alive', True)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_trader', False)
            and not getattr(a, 'is_lord', False)]


def _name(tile):
    return getattr(tile, 'scenario_location', None) or getattr(tile, 'display_name', tile.name)


def _price(tile):
    return max(0.25, float(tile.recipes.get(Goods.food, {}).get('price', 1.0)))


def _economy(world):
    return world['scenario_state']['political_economy']


def initialize(world, nation):
    state = world['scenario_state']
    state['political_economy'] = {
        'warehouse_by_tile': {}, 'private_reserve_by_tile': {},
        'grain_policy': 'hold', 'arrears': {},
        'reservation_price_by_tile': {},
        'tenure_transfers': [], 'migrations': [], 'collective_by_tile': {},
        'scenario_strikers_by_tile': {},
        'grain_transactions': [], 'tax_assessments': [], 'fiscal_reports': [],
        'control_extension_turns': 0,
    }
    for tile in nation.tiles:
        holders = [a for a in tile.agents if getattr(a, 'alive', True)
                   and getattr(a, 'is_lord', False)]
        if not holders:
            holders = [a for a in tile.agents if getattr(a, 'alive', True)
                       and getattr(a, 'is_trader', False)]
        if holders:
            owner = max(holders, key=lambda a: float(a.cash))
            _economy(world)['warehouse_by_tile'][tile.name] = owner.id
            _economy(world)['reservation_price_by_tile'][tile.name] = round(_price(tile) * 1.5, 2)
            _economy(world)['private_reserve_by_tile'][tile.name] = min(4, owner.inv_get(Goods.food, 0))
            tile.scenario_grain_holder_id = owner.id
            tile.scenario_grain_policy = 'hold'
            tile.scenario_grain_reserved_units = _economy(world)['private_reserve_by_tile'][tile.name]
            tile.scenario_grain_offer_units = 0
        _economy(world)['collective_by_tile'][tile.name] = {
            'petitioners': 0, 'strikers': 0, 'mutual_aid_meals': 0,
            'injuries': 0, 'support': 0.0, 'settlement_until_turn': 0,
        }
        _economy(world)['scenario_strikers_by_tile'][tile.name] = []


def _holder(world, tile):
    owner_id = _economy(world)['warehouse_by_tile'].get(tile.name)
    return next((a for a in tile.agents if a.id == owner_id and a.alive), None)


def _reserved(world, tile):
    owner = _holder(world, tile)
    units = min(max(0, int(_economy(world)['private_reserve_by_tile'].get(tile.name, 0))),
                max(0, owner.inv_get(Goods.food, 0)) if owner else 0)
    _economy(world)['private_reserve_by_tile'][tile.name] = units
    tile.scenario_grain_reserved_units = units
    return units


def _set_reserved(world, tile, units):
    _economy(world)['private_reserve_by_tile'][tile.name] = max(0, int(units))
    _reserved(world, tile)


def stock(world, nation):
    return sum(_reserved(world, tile) for tile in nation.tiles)


def district_snapshot(world, tile):
    econ = _economy(world)
    owner = _holder(world, tile)
    ids = {a.id for a in _households(tile)}
    arrears = sum(float(row['balance']) for key, row in econ['arrears'].items()
                  if key in ids)
    collective = econ['collective_by_tile'].get(tile.name, {})
    return {'private_stock': _reserved(world, tile) if owner else 0,
            'owner_id': owner.id if owner else None,
            'arrears': arrears,
            'at_risk': sum(row['balance'] > 0 and row['missed'] >= 2
                           for key, row in econ['arrears'].items() if key in ids),
            'petitioners': int(collective.get('petitioners', 0)),
            'strikers': int(collective.get('strikers', 0)),
            'mutual_aid_meals': int(collective.get('mutual_aid_meals', 0))}


def _record_grain(world, tile, kind, units, cash, owner_id, turn=None,
                  operation_ids=None):
    row = {
        'turn': int(world['turn'] if turn is None else turn), 'tile': tile.name, 'kind': kind,
        'units': int(units), 'cash': round(float(cash), 2), 'owner_id': owner_id}
    if operation_ids:
        row['operation_ids'] = list(operation_ids)
    _economy(world)['grain_transactions'].append(row)


def _trace_household_mutual_aid_transfer(tile, *, operation_id, turn, donor,
                                        receiver, donor_before, donor_after,
                                        receiver_before, receiver_after, mode):
    from run_trace import emit

    transfer_contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': 'household_mutual_aid',
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(donor_before - donor_after),
        'payer_account': account_ref(
            'agent_inventory', donor.id, 'food_units',
            balance_before=int(donor_before), balance_after=int(donor_after),
            balance_scope='inventory.food'),
        'payee_account': account_ref(
            'agent_inventory', receiver.id, 'food_units',
            balance_before=int(receiver_before), balance_after=int(receiver_after),
            balance_scope='inventory.food'),
        'counterparty_leg_status': 'both household food inventories captured',
    }
    return emit(
        tile, kind='household_mutual_aid_food_transfer',
        record_class='transfer', phase='scenario_economy',
        subject={'type': 'tile/operation', 'id': operation_id,
                 'tile': tile.name, 'good': Goods.food.name},
        metric_id='goods.mutual_aid_transfer', unit='food_units',
        before=0, after=int(donor_before - donor_after),
        formula_id='scenario.household_mutual_aid_transfer.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn), 'mode': mode,
                'donor_id': donor.id, 'receiver_id': receiver.id,
                'donor_food_before': int(donor_before),
                'donor_food_after': int(donor_after),
                'receiver_food_before': int(receiver_before),
                'receiver_food_after': int(receiver_after),
                'transfer_contract': transfer_contract})


def _trace_mutual_aid_total(tile, *, operation_id, turn, mode, before, after,
                            transfer_event_ids):
    if after <= before:
        return None
    from run_trace import emit
    return emit(
        tile, kind='household_mutual_aid_meals', record_class='outcome',
        phase='scenario_economy',
        subject={'type': 'tile', 'id': tile.name},
        metric_id='politics.mutual_aid_meals', unit='meals',
        before=int(before), after=int(after),
        formula_id='scenario.household_mutual_aid_total.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn), 'mode': mode,
                'transfers': int(after - before)},
        cause_event_ids=transfer_event_ids or None)


def _grain_operation_id(tile, turn, kind, goods_payer_id, goods_payee_id):
    """Return an operation ID independent of whether optional tracing is on."""
    return (f'grain:{tile.name}:{int(turn)}:{kind}:'
            f'{goods_payer_id}:{goods_payee_id}')


def _emit_grain_stock_transfer(tile, *, operation_id, operation_type, units,
                               payer_account, payee_account, turn,
                               cash_transfer_status, cash_event_id=None,
                               details=None):
    from run_trace import emit

    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': operation_type,
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(units),
        'payer_account': payer_account,
        'payee_account': payee_account,
        'cash_transfer_status': cash_transfer_status,
        'counterparty_leg_status': 'both_food_inventory_balances_captured',
    }
    inputs = {'operation_id': operation_id, 'transfer_contract': contract,
              'turn': int(turn), **(details or {})}
    return emit(
        tile, kind=f'{operation_type}_food', record_class='transfer',
        phase='scenario_economy',
        subject={'type': 'tile', 'id': tile.name, 'good': Goods.food.name},
        metric_id='goods.grain_transfer', unit='food_units', before=0,
        after=int(units), inputs=inputs,
        cause_event_ids=[cash_event_id] if cash_event_id else None)


def _emit_private_grain_trade(tile, *, operation_id, operation_type, turn,
                              units, amount, payer, payee,
                              payer_cash_before, payer_cash_after,
                              payee_cash_before, payee_cash_after,
                              goods_payer_id, goods_payee_id,
                              goods_payer_before, goods_payer_after,
                              goods_payee_before, goods_payee_after,
                              details=None, trace_event_ids=None):
    currency = getattr(tile, 'home_currency', None) or 'local_currency'
    payer_cash = account_ref(
        'agent', payer.id, currency, balance_before=payer_cash_before,
        balance_after=payer_cash_after, balance_scope='cash')
    payee_cash = account_ref(
        'agent', payee.id, currency, balance_before=payee_cash_before,
        balance_after=payee_cash_after, balance_scope='cash')
    cash_contract = cash_transfer_contract(
        operation_id, operation_type, amount=amount, currency=currency,
        payer_account=payer_cash, payee_account=payee_cash,
        counterparty_leg_status='both_cash_balances_captured',
        mutation_reference={'turn': int(turn), 'tile': tile.name,
                            'food_units': int(units)})
    cash_event_id = emit_cash_transfer(
        tile, kind=f'{operation_type}_payment', contract=cash_contract,
        phase='scenario_economy',
        inputs={'turn': int(turn), 'food_units': int(units),
                'unit_price': float(amount) / max(1, int(units)),
                **(details or {})})
    payer_goods = account_ref(
        'agent_inventory', goods_payer_id, 'food_units',
        balance_before=int(goods_payer_before),
        balance_after=int(goods_payer_after), balance_scope='inventory.food')
    payee_goods = account_ref(
        'agent_inventory', goods_payee_id, 'food_units',
        balance_before=int(goods_payee_before),
        balance_after=int(goods_payee_after), balance_scope='inventory.food')
    food_event_id = _emit_grain_stock_transfer(
        tile, operation_id=operation_id, operation_type=operation_type,
        units=units, payer_account=payer_goods, payee_account=payee_goods,
        turn=turn, cash_transfer_status='cash_transfer.v1',
        cash_event_id=cash_event_id, details=details)
    if trace_event_ids is not None:
        trace_event_ids.extend(event_id for event_id in
                               (cash_event_id, food_event_id)
                               if event_id is not None)
    return operation_id


def _buy_harvest(world, tile, owner, turn):
    """Owners buy real excess maize from producers, then withhold it from asks."""
    if _economy(world)['grain_policy'] == 'open':
        return
    hungry = sum(deficit_fraction(a) for a in _households(tile))
    desire = 0.08 + 0.22 * (1.0 - exp(-hungry / 10.0))
    if _economy(world)['grain_policy'] == 'open':
        desire *= 0.20
    price = _price(tile)
    bought = 0
    operation_ids = []
    room = max(0, WAREHOUSE_CAPACITY_PER_DISTRICT - _reserved(world, tile))
    for producer in sorted((a for a in tile.agents if a is not owner
                            and getattr(a, 'alive', True) and a.output == Goods.food),
                           key=lambda a: a.id):
        surplus = max(0, producer.inv_get(Goods.food, 0) - 4)
        units = min(int(surplus * desire), int(owner.cash / price), 8, room - bought)
        if units <= 0:
            continue
        cost = units * price
        owner_cash_before = float(owner.cash)
        producer_cash_before = float(producer.cash)
        producer_food_before = int(producer.inv_get(Goods.food, 0))
        owner_food_before = int(owner.inv_get(Goods.food, 0))
        producer.inv_add(Goods.food, -units)
        producer.cash += cost
        owner.inv_add(Goods.food, units)
        owner.cash -= cost
        operation_id = _grain_operation_id(
            tile, turn, 'private_harvest_purchase', producer.id, owner.id)
        operation_ids.append(_emit_private_grain_trade(
            tile, operation_id=operation_id,
            operation_type='private_harvest_purchase', turn=turn,
            units=units, amount=cost, payer=owner, payee=producer,
            payer_cash_before=owner_cash_before,
            payer_cash_after=float(owner.cash),
            payee_cash_before=producer_cash_before,
            payee_cash_after=float(producer.cash),
            goods_payer_id=producer.id, goods_payee_id=owner.id,
            goods_payer_before=producer_food_before,
            goods_payer_after=int(producer.inv_get(Goods.food, 0)),
            goods_payee_before=owner_food_before,
            goods_payee_after=int(owner.inv_get(Goods.food, 0)),
            details={'owner_id': owner.id, 'producer_id': producer.id,
                     'unit_price': price, 'purchase_reason': 'harvest_withholding',
                     'household_hunger_pressure': hungry,
                     'owner_buy_share': desire, 'producer_surplus_before': surplus,
                     'owner_cash_affordable_units': int(owner_cash_before / price),
                     'warehouse_room_before': max(0, room - bought),
                     'per_producer_purchase_cap': 8}))
        bought += units
    if bought:
        _set_reserved(world, tile, _reserved(world, tile) + bought)
        _record_grain(world, tile, 'private_purchase', bought, bought * price,
                      owner.id, turn=turn, operation_ids=operation_ids)


def hold_after_harvest(tile, turn):
    """Called by production before market asks are gathered."""
    world = getattr(getattr(tile, 'gov', None), 'scenario_debt_world', None)
    if not world or world.get('scenario_id') != 'egypt_1877':
        return
    owner = _holder(world, tile)
    if owner is not None:
        _buy_harvest(world, tile, owner, turn)
        if _economy(world)['grain_policy'] == 'hold':
            neighbor_offer = max((_price(other) for other in tile.neighbors.values()), default=0.0)
            target = max(_economy(world)['reservation_price_by_tile'][tile.name],
                         neighbor_offer * 1.05)
            relative_price = _price(tile) / max(.25, target)
            release_share = .8 / (1.0 + exp(-5.0 * (relative_price - 1.0)))
            tile.scenario_grain_offer_units = int(_reserved(world, tile) * release_share)
        else:
            tile.scenario_grain_offer_units = _reserved(world, tile)


def _sell_to_households(world, tile, owner, limit=None, *, trigger='open_market',
                        trace_operation_id=None, trace_event_ids=None):
    price = _price(tile)
    reserved_before = _reserved(world, tile)
    sold = 0
    operation_ids = []
    sale_event_ids = []
    buyers = sorted(_households(tile), key=lambda a: (-deficit_fraction(a), a.cash))
    buyer_decisions = []
    for buyer in buyers:
        food_before = int(buyer.inv_get(Goods.food, 0))
        cash_before = float(buyer.cash)
        need = max(0, 4 - food_before)
        affordable = int(cash_before / price)
        reason = ('no_food_need' if need <= 0 else
                  'warehouse_empty' if reserved_before <= 0 else
                  'unaffordable_at_posted_price' if affordable <= 0 else
                  'eligible_not_yet_served')
        buyer_decisions.append({
            'buyer_id': buyer.id, 'food_inventory_before': food_before,
            'cash_before': cash_before, 'food_need_units': need,
            'cash_affordable_units': affordable,
            'food_deficit_fraction_before': deficit_fraction(buyer),
            'units_purchased': 0, 'food_inventory_after': food_before,
            'cash_after': cash_before, 'decision_reason': reason})
    decisions_by_buyer = {row['buyer_id']: row for row in buyer_decisions}
    for buyer in buyers:
        if owner.inv_get(Goods.food, 0) <= 0 or (limit is not None and sold >= limit):
            break
        need = max(0, 4 - buyer.inv_get(Goods.food, 0))
        units = min(need, int(buyer.cash / price), owner.inv_get(Goods.food, 0))
        if limit is not None:
            units = min(units, limit - sold)
        if units <= 0:
            continue
        amount = units * price
        buyer_cash_before = float(buyer.cash)
        owner_cash_before = float(owner.cash)
        owner_food_before = int(owner.inv_get(Goods.food, 0))
        buyer_food_before = int(buyer.inv_get(Goods.food, 0))
        buyer.cash -= amount
        owner.cash += amount
        owner.inv_add(Goods.food, -units)
        buyer.inv_add(Goods.food, units)
        operation_id = _grain_operation_id(
            tile, int(world['turn']), 'private_household_grain_sale',
            owner.id, buyer.id)
        operation_ids.append(_emit_private_grain_trade(
            tile, operation_id=operation_id,
            operation_type='private_household_grain_sale',
            turn=int(world['turn']), units=units, amount=amount,
            payer=buyer, payee=owner,
            payer_cash_before=buyer_cash_before, payer_cash_after=float(buyer.cash),
            payee_cash_before=owner_cash_before, payee_cash_after=float(owner.cash),
            goods_payer_id=owner.id, goods_payee_id=buyer.id,
            goods_payer_before=owner_food_before,
            goods_payer_after=int(owner.inv_get(Goods.food, 0)),
            goods_payee_before=buyer_food_before,
            goods_payee_after=int(buyer.inv_get(Goods.food, 0)),
            trace_event_ids=sale_event_ids,
            details={'owner_id': owner.id, 'buyer_id': buyer.id,
                     'unit_price': price, 'sale_reason': 'private_warehouse_release',
                     'buyer_need_units': need,
                     'buyer_cash_affordable_units': int(buyer_cash_before / price),
                     'warehouse_stock_before': owner_food_before,
                     'buyer_food_deficit_fraction': deficit_fraction(buyer),
                     'remaining_release_limit': (None if limit is None
                                                 else max(0, limit - sold))}))
        decision = decisions_by_buyer[buyer.id]
        decision.update(units_purchased=units,
                        food_inventory_after=int(buyer.inv_get(Goods.food, 0)),
                        cash_after=float(buyer.cash),
                        decision_reason='purchased')
        sold += units
    if sold:
        _set_reserved(world, tile, max(0, reserved_before - sold))
        _record_grain(world, tile, 'market_sale', sold, sold * price,
                      owner.id, operation_ids=operation_ids)
    reserved_after = _reserved(world, tile)
    for decision in buyer_decisions:
        if decision['decision_reason'] == 'eligible_not_yet_served':
            decision['decision_reason'] = (
                'warehouse_or_release_limit_exhausted'
                if owner.inv_get(Goods.food, 0) <= 0
                or (limit is not None and sold >= limit)
                else 'eligible_but_no_sale_recorded')
    if reserved_before <= 0:
        reason = 'warehouse_empty'
    elif limit is not None and limit <= 0:
        reason = 'release_limit_zero'
    elif sold:
        reason = 'household_sales_completed'
    elif not buyers or all(row['food_need_units'] <= 0 for row in buyer_decisions):
        reason = 'no_household_food_need'
    elif all(row['decision_reason'] == 'unaffordable_at_posted_price'
             for row in buyer_decisions if row['food_need_units'] > 0):
        reason = 'households_cannot_afford_posted_price'
    else:
        reason = 'no_household_sale_completed'
    operation_id = trace_operation_id or (
        f'grain-release:{tile.name}:{int(world["turn"])}:{trigger}:'
        f'{owner.id}:{reserved_before}')
    from run_trace import emit
    release_event_id = emit(
        tile, kind='private_grain_release_resolved',
        record_class='outcome' if sold else 'decision',
        phase='scenario_economy',
        subject={'type': 'tile/agent', 'id': owner.id, 'tile': tile.name,
                 'good': Goods.food.name},
        metric_id='scenario.private_grain_release', unit='food_units',
        before=reserved_before, after=reserved_after,
        formula_id='scenario_political_economy.private_grain_release.v1',
        inputs={'operation_id': operation_id, 'turn': int(world['turn']),
                'trigger': trigger, 'reason': reason,
                'owner_id': owner.id, 'posted_food_price': float(price),
                'release_limit': limit, 'reserved_food_before': reserved_before,
                'reserved_food_after': reserved_after,
                'units_sold': int(sold),
                'owner_food_inventory_after': int(owner.inv_get(Goods.food, 0)),
                'owner_cash_after': float(owner.cash),
                'buyer_decisions': buyer_decisions,
                'grain_transaction_operation_ids': operation_ids,
                'purchase_transfer_event_ids': sale_event_ids},
        cause_event_ids=sale_event_ids or None)
    if release_event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(release_event_id)
    return sold


def _tax_currency(tile):
    nation = getattr(tile, 'owner_nation', None)
    return (getattr(nation, 'currency', None)
            or getattr(tile, 'home_currency', None) or 'local_currency')


def _trace_tax_arrears_balance(tile, agent, *, turn, operation_id,
                               before, after, inputs=None,
                               cause_event_ids=None):
    from run_trace import emit
    return emit(
        tile, kind='cadastral_tax_arrears_balance', record_class='outcome',
        phase='scenario_economy',
        subject={'type': 'tile/agent', 'id': str(agent.id), 'tile': tile.name},
        metric_id='finance.tax_arrears_balance', unit=_tax_currency(tile),
        before=float(before), after=float(after),
        formula_id='cadastral_tax.arrears_balance_update.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'agent_id': agent.id, **(inputs or {})},
        cause_event_ids=cause_event_ids)


def _trace_cadastral_tax_payment(tile, agent, *, amount, turn,
                                 operation_id, collection_operation_id,
                                 cash_before, cash_after,
                                 pool_before, pool_after, details=None):
    if amount <= 0:
        return None
    currency = _tax_currency(tile)
    payer = account_ref(
        'agent', agent.id, currency, balance_before=float(cash_before),
        balance_after=float(cash_after), balance_scope='cash')
    pool = account_ref(
        'cadastral_tax_collection_pool', collection_operation_id, currency,
        balance_before=float(pool_before), balance_after=float(pool_after),
        balance_scope='collected_assessment_revenue')
    contract = cash_transfer_contract(
        operation_id, 'cadastral_tax_payment', amount=amount, currency=currency,
        payer_account=payer, payee_account=pool,
        counterparty_leg_status='collected_amount_allocated_to_public_treasuries',
        mutation_reference={'tile': tile.name, 'turn': int(turn),
                            'collection_operation_id': collection_operation_id})
    return emit_cash_transfer(
        tile, kind='cadastral_tax_payment', contract=contract,
        phase='scenario_economy',
        subject={'type': 'tile/operation', 'id': operation_id,
                 'agent_id': agent.id},
        inputs={'turn': int(turn), 'assessment_operation_id': operation_id,
                'collection_operation_id': collection_operation_id,
                **(details or {})})


def _trace_tax_treasury_allocation(tile, government, *, nation, tier,
                                  amount, turn, collection_operation_id,
                                  pool_before, pool_after, treasury_before,
                                  treasury_after, payment_event_ids):
    if amount <= 0:
        return None
    currency = _tax_currency(tile)
    allocation_id = f'{collection_operation_id}:allocation:{tier}'
    pool = account_ref(
        'cadastral_tax_collection_pool', collection_operation_id, currency,
        balance_before=float(pool_before), balance_after=float(pool_after),
        balance_scope='collected_assessment_revenue')
    treasury = account_ref(
        'government_treasury', government.name, currency,
        nation_id=getattr(nation, 'name', None), tier=tier,
        subaccount='government_agent.cash',
        balance_before=float(treasury_before), balance_after=float(treasury_after),
        balance_scope='government_agent.cash')
    contract = transfer_contract(
        allocation_id, 'cadastral_tax_treasury_allocation', side='payee',
        amount=amount, amount_currency=currency,
        payer_account=pool, payee_account=treasury,
        local_cash_leg_amount=amount, local_cash_leg_currency=currency,
        counterparty_leg_status='household_cash_payments_recorded_individually',
        mutation_reference={'turn': int(turn), 'tile': tile.name,
                            'collection_operation_id': collection_operation_id,
                            'treasury_tier': tier})
    return emit_treasury_leg(
        tile, kind='cadastral_tax_treasury_receipt',
        nation_name=(getattr(nation, 'name', tile.name)
                     if tier == 'national' else government.name), currency=currency,
        signed_amount=float(amount), contract=contract,
        phase='scenario_economy',
        subject_type='nation' if tier == 'national' else 'tile',
        cause_event_ids=payment_event_ids or None,
        inputs={'turn': int(turn), 'collection_operation_id': collection_operation_id,
                'treasury_tier': tier, 'household_count': len(payment_event_ids)})


def _trace_worker_bargain(tile, nation, *, operation_id, turn, success,
                          reason, inputs, cause_event_ids=None):
    """Record the labor outcome and the scenario action that produced it."""
    from run_trace import emit

    labor_event_id = emit(
        tile, kind=('district_bargain_settled' if success
                    else 'district_bargain_gate_rejected'),
        record_class='outcome' if success else 'decision',
        phase='scenario_action',
        subject={'type': 'tile/operation', 'id': operation_id,
                 'tile': tile.name, 'nation': nation.name},
        metric_id='labor.collective_action', unit='event_kind',
        before='bargain_pending',
        after='bargain_settled' if success else 'bargain_rejected',
        formula_id='scenario.district_bargain_workers.v1',
        inputs={'operation_id': operation_id, 'action_id': 'district_bargain_workers',
                'turn': int(turn), 'reason': reason, **inputs},
        cause_event_ids=cause_event_ids)
    return emit(
        tile, kind='district_bargain_action_resolved',
        record_class='outcome', phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name, 'nation': nation.name,
                 'action_id': 'district_bargain_workers'},
        metric_id='scenario.district_action', unit='success',
        before=0, after=int(bool(success)),
        formula_id='scenario_district.action_resolution.v1',
        inputs={'operation_id': operation_id, 'action_id': 'district_bargain_workers',
                'turn': int(turn), 'success': bool(success), 'reason': reason,
                'labor_outcome_event_id': labor_event_id, **inputs},
        cause_event_ids=([labor_event_id] if labor_event_id is not None else None))


def _trace_worker_bargain_transfer(tile, *, operation_id, turn, currency,
                                   total, source_legs, recipients):
    """Record the employer pool and every worker receipt without inventing a wallet."""
    if total <= 0:
        return None
    from finance_trace import cash_transfer_contract, emit_cash_transfer

    payer = account_ref(
        'virtual_employer_pool', f'{operation_id}:employers', currency,
        balance_scope='itemized_employer_contributions', virtual_pool=True,
        balance_captured=False, source_legs=source_legs)
    if recipients:
        payee = account_ref(
            'household_agent_cash_group', f'{operation_id}:workers', currency,
            balance_scope='member_cash_balances', member_count=len(recipients),
            member_ids=[str(row['agent_id']) for row in recipients],
            members=[{'type': 'agent_cash', 'id': str(row['agent_id']),
                      'amount': float(row['amount']), 'currency': currency,
                      'balance_before': float(row['cash_before']),
                      'balance_after': float(row['cash_after'])}
                     for row in recipients])
        counterparty_status = (
            'all employer cash debits and worker cash receipts captured')
        kind = 'district_bargain_cash_transfer'
    else:
        payee = account_ref(
            'uncredited_household_payment', f'{operation_id}:no-recipient', currency,
            balance_scope='missing_payee',
            balance_status='employer_cash_debited_without_worker_receipt')
        counterparty_status = (
            'employer cash debited; no eligible household receipt was recorded')
        kind = 'district_bargain_cash_debit_without_recipient'
    contract = cash_transfer_contract(
        operation_id, 'district_collective_bargain', amount=total,
        currency=currency, payer_account=payer, payee_account=payee,
        counterparty_leg_status=counterparty_status,
        source_leg_count=len(source_legs), recipient_count=len(recipients))
    return emit_cash_transfer(
        tile, kind=kind, contract=contract,
        phase='scenario_action',
        subject={'type': 'tile/operation', 'id': operation_id,
                 'tile': tile.name},
        inputs={'turn': int(turn), 'action_id': 'district_bargain_workers',
                'distribution_rule': 'equal_split_among_selected_recipients',
                'source_legs': source_legs,
                'recipient_allocations': recipients})


def _trace_district_economy_action(tile, nation, *, action_id, operation_id,
                                  turn, success, reason, inputs,
                                  cause_event_ids=None, labor_event_kind=None):
    """Summarize a district political-economy action and its source evidence."""
    from run_trace import emit

    labor_event_id = None
    if labor_event_kind is not None:
        labor_event_id = emit(
            tile, kind=labor_event_kind,
            record_class='outcome' if success else 'decision',
            phase='scenario_action',
            subject={'type': 'tile/operation', 'id': operation_id,
                     'tile': tile.name,
                     'nation': getattr(nation, 'name', tile.name)},
            metric_id='labor.collective_action', unit='event_kind',
            before='strike_active',
            after='strike_broken' if success else 'repression_rejected',
            formula_id='scenario.district_break_strike.v1',
            inputs={'operation_id': operation_id, 'action_id': action_id,
                    'turn': int(turn), 'reason': reason, **inputs},
            cause_event_ids=cause_event_ids)
    return emit(
        tile, kind=f'{action_id}_resolved', record_class='outcome',
        phase='scenario_action',
        subject={'type': 'tile', 'id': tile.name,
                 'nation': getattr(nation, 'name', tile.name),
                 'action_id': action_id},
        metric_id='scenario.district_action', unit='success',
        before=0, after=int(bool(success)),
        formula_id='scenario_district.action_resolution.v1',
        inputs={'operation_id': operation_id, 'action_id': action_id,
                'turn': int(turn), 'success': bool(success), 'reason': reason,
                'labor_event_id': labor_event_id, **inputs},
        cause_event_ids=([labor_event_id] if labor_event_id is not None
                         else cause_event_ids))


def _assess_arrears(world, tile, assessed_ids):
    econ = _economy(world)
    rate = max(0.0, float(tile.gov.tax_rate))
    turn = int(world['turn'])
    collected = 0.0
    nation = getattr(tile, 'owner_nation', None)
    collection_operation_id = (
        f'cadastral-tax:{getattr(nation, "name", "local")}:{tile.name}:{turn}')
    payment_event_ids = []
    for agent in _households(tile):
        if agent.id in assessed_ids or not agent.assigned_plot_id:
            continue
        assessed_ids.add(agent.id)
        # Separate scenario cadastre levy; paid receipts enter the local tax log.
        assessment = round(CADASTRAL_ASSESSMENT_MULTIPLIER * rate, 2)
        if assessment <= 0:
            continue
        row = econ['arrears'].setdefault(agent.id, {'balance': 0.0, 'missed': 0,
                                                     'plot_id': agent.assigned_plot_id})
        arrears_before = float(row['balance'])
        missed_before = int(row['missed'])
        due = round(row['balance'] + assessment, 2)
        cash_before = float(agent.cash)
        paid = min(max(0.0, cash_before), due)
        agent.cash -= paid
        cash_after = float(agent.cash)
        pool_before = collected
        collected += paid
        row['balance'] = round(due - paid, 2)
        row['missed'] = row['missed'] + 1 if row['balance'] > 0 else 0
        assessment_operation_id = (
            f'{collection_operation_id}:household:{agent.id}')
        econ['tax_assessments'].append({'turn': turn, 'tile': tile.name,
                                        'agent_id': agent.id, 'assessed': assessment,
                                        'paid': round(paid, 2), 'arrears': row['balance']})
        payment_event_id = _trace_cadastral_tax_payment(
            tile, agent, amount=paid, turn=turn,
            operation_id=assessment_operation_id,
            collection_operation_id=collection_operation_id,
            cash_before=cash_before, cash_after=cash_after,
            pool_before=pool_before, pool_after=collected,
            details={'assessed_amount': float(assessment), 'amount_due': float(due),
                     'arrears_before': arrears_before,
                     'arrears_after_assessment': float(row['balance']),
                     'plot_id': agent.assigned_plot_id})
        if payment_event_id is not None:
            payment_event_ids.append(payment_event_id)
        arrears_event_id = _trace_tax_arrears_balance(
            tile, agent, turn=turn, operation_id=assessment_operation_id,
            before=arrears_before, after=float(row['balance']),
            inputs={'assessed_amount': float(assessment), 'paid': float(paid),
                    'amount_due': float(due), 'missed_before': missed_before,
                    'missed_after': int(row['missed']),
                    'plot_id': agent.assigned_plot_id},
            cause_event_ids=([payment_event_id] if payment_event_id is not None
                             else None))
        # A continuous arrears hazard avoids an automatic cliff at a fixed bill.
        exposure = max(0.0, float(row['balance'])) * max(0, row['missed'] - 1)
        foreclosure_chance = 1.0 - exp(-0.01 * exposure)
        draw = Random(agent.id * 7919 + turn * 104729).random()
        from run_trace import emit
        risk_event_id = emit(
            tile, kind='cadastral_foreclosure_risk_roll', record_class='calculation',
            phase='scenario_economy',
            subject={'type': 'tile/agent', 'id': str(agent.id), 'tile': tile.name},
            metric_id='finance.tax_foreclosure_risk', unit='probability',
            before=0.0, after=float(foreclosure_chance),
            formula_id='cadastral_tax.foreclosure_exposure_hazard.v1',
            inputs={'operation_id': assessment_operation_id,
                    'arrears_balance': float(row['balance']),
                    'missed_assessments': int(row['missed']),
                    'exposure': float(exposure), 'random_draw': float(draw),
                    'foreclosure_triggered': bool(draw < foreclosure_chance),
                    'assessment_event_id': arrears_event_id},
            cause_event_ids=([arrears_event_id]
                             if arrears_event_id is not None else None))
        if draw < foreclosure_chance:
            cause_ids = [event_id for event_id in
                         (payment_event_id, arrears_event_id, risk_event_id)
                         if event_id is not None]
            _foreclose(world, tile, agent, row, cause_event_ids=cause_ids)
    if collected:
        allocation_trace_ids = []
        national = round(collected * NATIONAL_CADASTRAL_SHARE, 6)
        local = collected - national
        if nation is not None:
            national_before = float(nation.government.agent.cash)
            nation.government.agent.cash += national
            national_after = float(nation.government.agent.cash)
            pool_after_national = collected - national
            allocation_id = _trace_tax_treasury_allocation(
                tile, nation.government, nation=nation, tier='national',
                amount=national, turn=turn,
                collection_operation_id=collection_operation_id,
                pool_before=collected, pool_after=pool_after_national,
                treasury_before=national_before, treasury_after=national_after,
                payment_event_ids=payment_event_ids)
            if allocation_id is not None:
                allocation_trace_ids.append(allocation_id)
            nation.government.record_income(turn, 'tax', national)
        else:
            local = collected
            national = 0.0
            pool_after_national = collected
        local_before = float(tile.gov.agent.cash)
        tile.gov.agent.cash += local
        local_after = float(tile.gov.agent.cash)
        allocation_id = _trace_tax_treasury_allocation(
            tile, tile.gov, nation=nation, tier='municipal', amount=local,
            turn=turn, collection_operation_id=collection_operation_id,
            pool_before=pool_after_national, pool_after=0.0,
            treasury_before=local_before, treasury_after=local_after,
            payment_event_ids=payment_event_ids)
        if allocation_id is not None:
            allocation_trace_ids.append(allocation_id)
        tile.gov.record_income(turn, 'tax', local)
        if getattr(tile, 'tax_distribution_log', None):
            distribution_before = dict(tile.tax_distribution_log[-1])
            tile.tax_distribution_log[-1]['total'] += collected
            tile.tax_distribution_log[-1]['national'] += national
            tile.tax_distribution_log[-1]['municipal'] += local
            from finance_trace import emit_tax_distribution
            emit_tax_distribution(
                tile, turn=turn, opening=distribution_before,
                closing=tile.tax_distribution_log[-1],
                receipts=[{'operation_id': collection_operation_id,
                           'amount': float(collected),
                           'allocations': {'national': float(national),
                                           'municipal': float(local)}}],
                reason='cadastral_tax_collection', phase='scenario_economy',
                cause_event_ids=allocation_trace_ids + payment_event_ids)


def _foreclose(world, tile, cultivator, row, *, cause_event_ids=None):
    plot = tile.tenure.find_plot(cultivator.assigned_plot_id) if getattr(tile, 'tenure', None) else None
    if plot is None:
        return
    turn = int(world['turn'])
    operation_id = (f'cadastral-foreclosure:{tile.name}:{turn}:{plot.plot_id}:'
                    f'{cultivator.id}')
    owner = next((a for a in tile.agents if a.id == plot.lord_id), None)
    bidders = [a for a in tile.agents if a is not cultivator and a.alive
               and not a.is_government and not a.is_corporation
               and not getattr(a, 'assigned_plot_id', None)
               and float(a.cash) >= 2.0]
    buyer = max(bidders, key=lambda a: float(a.cash), default=None)
    price = min(10.0, float(buyer.cash) * .1) if buyer else 0.0
    arrears_before = float(row['balance'])
    cash_event_ids = []
    recovery_event_id = None
    refund_event_id = None
    if buyer:
        currency = _tax_currency(tile)
        buyer_cash_before = float(buyer.cash)
        buyer_cash_after = buyer_cash_before - price
        buyer.cash -= price
        recovery = min(price, arrears_before)
        refund = price - recovery
        pool_before = 0.0
        pool_after = float(price)
        buyer_account = account_ref(
            'agent', buyer.id, currency, balance_before=buyer_cash_before,
            balance_after=float(buyer.cash), balance_scope='cash')
        pool_account = account_ref(
            'foreclosure_settlement_pool', operation_id, currency,
            balance_before=pool_before, balance_after=pool_after,
            balance_scope='auction_proceeds')
        payment_contract = cash_transfer_contract(
            operation_id, 'tax_foreclosure_auction_payment', amount=price,
            currency=currency, payer_account=buyer_account,
            payee_account=pool_account,
            counterparty_leg_status='proceeds_split_between_tax_and_cultivator',
            allocations={'tax_recovery': float(recovery),
                         'cultivator_refund': float(refund)})
        payment_event_id = emit_cash_transfer(
            tile, kind='tax_foreclosure_auction_payment',
            contract=payment_contract, phase='scenario_economy',
            subject={'type': 'tile/operation', 'id': operation_id,
                     'buyer_id': buyer.id, 'cultivator_id': cultivator.id},
            inputs={'turn': turn, 'plot_id': plot.plot_id,
                    'auction_price': float(price), 'arrears_before': arrears_before,
                    'tax_recovery': float(recovery),
                    'cultivator_refund': float(refund),
                    'eligible_bidders': [agent.id for agent in bidders],
                    'buyer_cash_before': buyer_cash_before,
                    'buyer_cash_after': float(buyer.cash)})
        if payment_event_id is not None:
            cash_event_ids.append(payment_event_id)
        government_cash_before = float(tile.gov.agent.cash)
        tile.gov.agent.cash += recovery
        government_cash_after = float(tile.gov.agent.cash)
        if recovery > 0:
            recovery_pool = account_ref(
                'foreclosure_settlement_pool', operation_id, currency,
                balance_before=float(price), balance_after=float(refund),
                balance_scope='auction_proceeds')
            treasury_account = account_ref(
                'government_treasury', tile.gov.name, currency,
                nation_id=getattr(getattr(tile, 'owner_nation', None), 'name', None),
                subaccount='government_agent.cash',
                balance_before=government_cash_before,
                balance_after=government_cash_after,
                balance_scope='government_agent.cash')
            recovery_contract = transfer_contract(
                f'{operation_id}:tax-recovery', 'tax_foreclosure_recovery',
                side='payee', amount=recovery, amount_currency=currency,
                payer_account=recovery_pool, payee_account=treasury_account,
                local_cash_leg_amount=recovery, local_cash_leg_currency=currency,
                counterparty_leg_status='buyer_auction_payment_recorded',
                mutation_reference={'turn': turn, 'plot_id': plot.plot_id,
                                    'foreclosure_operation_id': operation_id})
            recovery_event_id = emit_treasury_leg(
                tile, kind='tax_foreclosure_treasury_recovery',
                nation_name=(getattr(getattr(tile, 'owner_nation', None), 'name', None)
                             or tile.name), currency=currency,
                signed_amount=float(recovery), contract=recovery_contract,
                phase='scenario_economy',
                subject_type='tile',
                cause_event_ids=([payment_event_id]
                                 if payment_event_id is not None else None),
                inputs={'turn': turn, 'plot_id': plot.plot_id,
                        'arrears_before': arrears_before,
                        'auction_price': float(price), 'refund': float(refund)})
            if recovery_event_id is not None:
                cash_event_ids.append(recovery_event_id)
        tile.gov.record_income(int(world['turn']), 'tax', recovery)
        if getattr(tile, 'tax_distribution_log', None):
            distribution_before = dict(tile.tax_distribution_log[-1])
            tile.tax_distribution_log[-1]['total'] += recovery
            tile.tax_distribution_log[-1]['municipal'] += recovery
            from finance_trace import emit_tax_distribution
            emit_tax_distribution(
                tile, turn=turn, opening=distribution_before,
                closing=tile.tax_distribution_log[-1],
                receipts=[{'operation_id': operation_id, 'amount': float(recovery),
                           'allocations': {'municipal': float(recovery)}}],
                reason='tax_foreclosure_recovery', phase='scenario_economy',
                cause_event_ids=cash_event_ids)
        cultivator_cash_before = float(cultivator.cash)
        cultivator.cash += price - recovery
        if refund > 0:
            refund_pool = account_ref(
                'foreclosure_settlement_pool', operation_id, currency,
                balance_before=float(refund), balance_after=0.0,
                balance_scope='auction_proceeds')
            cultivator_account = account_ref(
                'agent', cultivator.id, currency,
                balance_before=cultivator_cash_before,
                balance_after=float(cultivator.cash), balance_scope='cash')
            refund_contract = cash_transfer_contract(
                f'{operation_id}:cultivator-refund', 'tax_foreclosure_refund',
                amount=refund, currency=currency,
                payer_account=refund_pool, payee_account=cultivator_account,
                counterparty_leg_status='allocated_from_buyer_auction_payment')
            refund_event_id = emit_cash_transfer(
                tile, kind='tax_foreclosure_cultivator_refund',
                contract=refund_contract, phase='scenario_economy',
                subject={'type': 'tile/operation', 'id': operation_id,
                         'cultivator_id': cultivator.id, 'buyer_id': buyer.id},
                inputs={'turn': turn, 'plot_id': plot.plot_id,
                        'auction_price': float(price), 'tax_recovery': float(recovery),
                        'refund': float(refund)},
                cause_event_ids=([payment_event_id]
                                 if payment_event_id is not None else None))
            if refund_event_id is not None:
                cash_event_ids.append(refund_event_id)
        row['balance'] = round(arrears_before - recovery, 2)
    else:
        recovery = 0.0
        refund = 0.0
        government_cash_before = float(tile.gov.agent.cash)
        government_cash_after = government_cash_before

    arrears_after = float(row['balance']) if buyer else arrears_before
    arrears_event_id = _trace_tax_arrears_balance(
        tile, cultivator, turn=turn, operation_id=operation_id,
        before=arrears_before, after=arrears_after,
        inputs={'foreclosure_recovery': float(recovery),
                'auction_price': float(price), 'buyer_id': buyer.id if buyer else None,
                'plot_id': plot.plot_id,
                'arrears_remain_after_no_bid': not bool(buyer)},
        cause_event_ids=([recovery_event_id] if recovery_event_id is not None else None))
    if arrears_event_id is not None:
        cash_event_ids.append(arrears_event_id)
    tenure_before = list(plot.tenant_ids)
    if cultivator.id in plot.tenant_ids:
        plot.tenant_ids.remove(cultivator.id)
    cultivator.assigned_plot_id = None
    cultivator.social_class = 'dispossessed'
    cultivator.mem_push('mem_eviction', 1.0)
    cultivator.mem_push('mem_debt_trap', 1.0)
    if buyer and not getattr(buyer, 'is_lord', False) and buyer.id not in plot.tenant_ids:
        plot.tenant_ids.append(buyer.id)
        buyer.assigned_plot_id = plot.plot_id
    row['missed'] = 0
    tenure_after = list(plot.tenant_ids)
    record = {'turn': turn, 'tile': tile.name,
              'cultivator_id': cultivator.id, 'title_holder_id': owner.id if owner else plot.lord_id,
              'new_use_right_holder_id': buyer.id if buyer else None,
              'plot_id': plot.plot_id, 'arrears_before': arrears_before,
              'arrears_after': row['balance'], 'auction_price': round(price, 2),
              'tax_recovery': float(recovery), 'cultivator_refund': float(refund),
              'operation_id': operation_id}
    _economy(world)['tenure_transfers'].append(record)
    from run_trace import emit
    land_event_id = emit(
        tile, kind='cadastral_foreclosure_use_right_transfer',
        record_class='outcome', phase='scenario_economy',
        subject={'type': 'tile/plot', 'id': plot.plot_id, 'tile': tile.name},
        metric_id='land.use_right_transfer', unit='tenant_ids',
        before=tenure_before, after=tenure_after,
        formula_id='cadastral_tax.foreclosure_tenant_transfer.v1',
        inputs={'operation_id': operation_id, 'cultivator_id': cultivator.id,
                'buyer_id': buyer.id if buyer else None,
                'title_holder_id': owner.id if owner else plot.lord_id,
                'plot_id': plot.plot_id, 'arrears_before': arrears_before,
                'arrears_after': float(row['balance'])},
        cause_event_ids=[event_id for event_id in cash_event_ids
                         if event_id is not None] or None)
    foreclosure_causes = list(dict.fromkeys(
        event_id for event_id in list(cause_event_ids or []) + cash_event_ids
        + [land_event_id] if event_id is not None))
    foreclosure_event_id = emit(
        tile, kind='cadastral_tax_foreclosure', record_class='outcome',
        phase='scenario_economy',
        subject={'type': 'tile/plot', 'id': plot.plot_id, 'tile': tile.name,
                 'cultivator_id': cultivator.id,
                 'buyer_id': buyer.id if buyer else None},
        metric_id='land.tax_foreclosure', unit='plots', before=0, after=1,
        formula_id='cadastral_tax.foreclosure_and_auction.v1',
        inputs={'operation_id': operation_id, 'turn': turn,
                'plot_id': plot.plot_id, 'title_holder_id': owner.id if owner else plot.lord_id,
                'cultivator_id': cultivator.id,
                'eligible_bidders': [{'agent_id': bidder.id,
                                     'cash': float(bidder.cash)}
                                    for bidder in bidders],
                'buyer_id': buyer.id if buyer else None,
                'auction_rule': 'highest_cash_eligible_bidder; min(10, buyer_cash*0.1)',
                'auction_price': float(price), 'tax_recovery': float(recovery),
                'cultivator_refund': float(refund),
                'government_cash_before_recovery': government_cash_before,
                'government_cash_after_recovery': government_cash_after,
                'arrears_before': arrears_before,
                'arrears_after': float(row['balance']),
                'no_bid': buyer is None},
        cause_event_ids=foreclosure_causes or None)
    unrest_before = float(tile.unrest_level)
    tile.unrest_level = min(1.0, unrest_before + .03)
    unrest_after = float(tile.unrest_level)
    emit(tile, kind='cadastral_foreclosure_unrest', record_class='outcome',
         phase='scenario_economy',
         subject={'type': 'tile', 'id': tile.name, 'agent_id': cultivator.id},
         metric_id='politics.unrest_level', unit='ratio',
         before=unrest_before,
         after=unrest_after,
         formula_id='cadastral_tax.foreclosure_unrest_increase.v1',
         inputs={'operation_id': operation_id, 'foreclosure_event_id': foreclosure_event_id,
                 'increase': .03},
         cause_event_ids=([foreclosure_event_id]
                          if foreclosure_event_id is not None else None))
    nation = tile.owner_nation
    if nation is not None:
        legitimacy_before = float(nation.legitimacy)
        nation.legitimacy = max(0.0, float(nation.legitimacy) - .005)
        emit(tile, kind='cadastral_foreclosure_legitimacy_loss',
             record_class='outcome', phase='scenario_economy',
             subject={'type': 'nation', 'id': nation.name,
                      'agent_id': cultivator.id},
             metric_id='politics.legitimacy', unit='ratio',
             before=legitimacy_before, after=float(nation.legitimacy),
             formula_id='cadastral_tax.foreclosure_legitimacy_loss.v1',
             inputs={'operation_id': operation_id,
                     'foreclosure_event_id': foreclosure_event_id,
                     'change': float(nation.legitimacy) - legitimacy_before},
             cause_event_ids=([foreclosure_event_id]
                              if foreclosure_event_id is not None else None))
        destinations = [other for other in nation.tiles if other is not tile]
        def open_jobs(other):
            return [a for a in other.agents if getattr(a, 'is_corporation', False)
                    and a.alive and a.output == cultivator.output
                    and len(a.employees) < a.max_employees
                    and a.cash >= 2 * a.wage]
        if destinations:
            target = min(destinations, key=lambda other: (
                -len(open_jobs(other)),
                sum(deficit_fraction(a) for a in _households(other)) / max(1, len(_households(other))),
                len(other.agents)))
            if cultivator.employer is None and not getattr(tile.bank, 'is_frozen', False):
                scenario_strikers = _economy(world)['scenario_strikers_by_tile'][tile.name]
                if cultivator.id in scenario_strikers:
                    scenario_strikers.remove(cultivator.id)
                    cultivator.is_striking = False
                deposit = float(tile.bank.deposits.get(cultivator, 0.0))
                if deposit > 0:
                    tile.bank.Withdraw(
                        cultivator, deposit, trace_region=tile, t=turn,
                        reason='scenario_migration_deposit_withdrawal')
                    target.bank.Deposit(
                        cultivator, deposit, trace_region=target, t=turn,
                        reason='scenario_migration_deposit_redeposit')
                tile.agents.remove(cultivator)
                target.agents.append(cultivator)
                cultivator.region = target.name
                cultivator._bank_ref = target.bank
                from run_trace import emit
                emit(tile, kind='scenario_person_departure', record_class='outcome',
                     phase='scenario', subject={'type': 'tile/agent', 'id': str(cultivator.id)},
                     metric_id='people.migration', unit='people', before=1, after=0,
                     formula_id='scenario.cultivator_migration.v1',
                     inputs={'agent_id': cultivator.id, 'origin': tile.name,
                             'destination': target.name,
                             'foreclosure_operation_id': operation_id},
                     cause_event_ids=([foreclosure_event_id]
                                      if foreclosure_event_id is not None else None))
                emit(target, kind='scenario_person_arrival', record_class='outcome',
                     phase='scenario', subject={'type': 'tile/agent', 'id': str(cultivator.id)},
                     metric_id='people.migration_in', unit='people', before=0, after=1,
                     formula_id='scenario.cultivator_migration.v1',
                     inputs={'agent_id': cultivator.id, 'origin': tile.name,
                             'destination': target.name,
                             'foreclosure_operation_id': operation_id},
                     cause_event_ids=([foreclosure_event_id]
                                      if foreclosure_event_id is not None else None))
                record['migrated_to'] = target.name
                jobs = open_jobs(target)
                if jobs:
                    employer = max(jobs, key=lambda a: float(a.wage))
                    cultivator.employer = employer
                    cultivator.hired_at = int(world['turn'])
                    employer.employees.append(cultivator)
                    record['wage_employer_id'] = employer.id
                _economy(world)['migrations'].append(record.copy())


def _organize(world, tile):
    econ = _economy(world)
    row = econ['collective_by_tile'][tile.name]
    people = _households(tile)
    arrears = econ['arrears']
    petitioners = [a for a in people if deficit_fraction(a) > .05
                   or arrears.get(a.id, {}).get('balance', 0.0) > 0]
    row['petitioners'] = len(petitioners)
    pressure = (sum(deficit_fraction(a) for a in people) / max(1, len(people))
                + sum(arrears.get(a.id, {}).get('balance', 0.0) for a in people)
                / max(1, 10 * len(people)))
    share = .12 * (1.0 - exp(-3.0 * pressure))
    if int(world['turn']) <= int(row.get('settlement_until_turn', 0)):
        share *= .1
    recruits = int(len(petitioners) * share)
    recruits_by_id = {agent.id for agent in sorted(
        petitioners, key=lambda a: (-deficit_fraction(a), float(a.cash), a.id))[:recruits]}
    previous = set(econ['scenario_strikers_by_tile'].get(tile.name, []))
    for agent in people:
        if agent.id in previous and agent.id not in recruits_by_id:
            agent.is_striking = False
    for agent in petitioners:
        if agent.id not in recruits_by_id:
            continue
        agent.is_striking = True
    econ['scenario_strikers_by_tile'][tile.name] = sorted(recruits_by_id)
    row['strikers'] = sum(bool(getattr(a, 'is_striking', False)) for a in people)
    row['support'] = 1.0 - exp(-row['petitioners'] / max(1, len(people)))
    # Households redistribute only their own food; public stocks are untouched.
    donors = [a for a in people if a.inv_get(Goods.food, 0) >= 8
              and deficit_fraction(a) == 0]
    receivers = [a for a in people if a.inv_get(Goods.food, 0) == 0
                 and deficit_fraction(a) > 0]
    mutual_aid_before = int(row['mutual_aid_meals'])
    mutual_aid_operation = (
        f'mutual-aid:{tile.name}:{int(world["turn"])}:automatic:'
        f'{mutual_aid_before}')
    mutual_aid_event_ids = []
    meals = 0
    for index, (donor, receiver) in enumerate(zip(donors, receivers)):
        donor_before = int(donor.inv_get(Goods.food, 0))
        receiver_before = int(receiver.inv_get(Goods.food, 0))
        donor.inv_add(Goods.food, -1)
        receiver.inv_add(Goods.food, 1)
        event_id = _trace_household_mutual_aid_transfer(
            tile,
            operation_id=f'{mutual_aid_operation}:{index + 1}',
            turn=int(world['turn']), donor=donor, receiver=receiver,
            donor_before=donor_before,
            donor_after=int(donor.inv_get(Goods.food, 0)),
            receiver_before=receiver_before,
            receiver_after=int(receiver.inv_get(Goods.food, 0)),
            mode='automatic')
        if event_id is not None:
            mutual_aid_event_ids.append(event_id)
        meals += 1
    row['mutual_aid_meals'] += meals
    _trace_mutual_aid_total(
        tile, operation_id=mutual_aid_operation, turn=int(world['turn']),
        mode='automatic', before=mutual_aid_before,
        after=int(row['mutual_aid_meals']),
        transfer_event_ids=mutual_aid_event_ids)


def advance(world, nation, turn):
    econ = _economy(world)
    assessed_ids = set()
    for tile in nation.tiles:
        owner = _holder(world, tile)
        if owner is not None:
            _reserved(world, tile)
            if econ['grain_policy'] == 'open':
                _sell_to_households(
                    world, tile, owner, limit=_reserved(world, tile),
                    trigger='automatic_open_market',
                    trace_operation_id=(
                        f'grain-release:{nation.name}:{int(turn)}:{tile.name}:'
                        'automatic_open_market'))
        _assess_arrears(world, tile, assessed_ids)
        _organize(world, tile)
    _resolve_collection_proposal(world, turn)
    _fiscal_report(world, nation, turn)


def _private_grain_policy_operation_id(world, nation, action_id):
    region = (getattr(nation, 'tiles', [None])[0]
              if getattr(nation, 'tiles', None) else None)
    clock = getattr(region, '_collective_trace_clock', None) if region else None
    ordinal = int(clock.get('next', 1)) if clock is not None else int(world['turn'])
    return (f'grain-policy:{nation.name}:{int(world["turn"])}:'
            f'{action_id}:{ordinal}')


def _trace_private_grain_policy(world, nation, *, operation_id, success,
                                reason, before, after, details=None,
                                cause_event_ids=None):
    region = (getattr(nation, 'tiles', [None])[0]
              if getattr(nation, 'tiles', None) else
              next(iter(world.get('tiles', ())), None))
    if region is None:
        return None
    from run_trace import emit
    return emit(
        region, kind='private_grain_policy_resolved',
        record_class='outcome' if success else 'decision',
        phase='scenario_action',
        subject={'type': 'nation', 'id': nation.name},
        metric_id='scenario.private_grain_policy', unit='policy',
        before=before, after=after,
        formula_id='scenario_political_economy.private_grain_policy.v1',
        inputs={'operation_id': operation_id,
                'action_id': 'open_private_grain_market',
                'turn': int(world['turn']), 'success': bool(success),
                'reason': reason, 'policy_before': before,
                'policy_after': after, **(details or {})},
        cause_event_ids=cause_event_ids)


def _resolve_collection_proposal(world, turn):
    state = world['scenario_state']
    assignment = state.get('collection_assignment') or {}
    proposal = assignment.get('extension_proposal')
    if not proposal or turn < proposal['reply_turn']:
        return
    confidence = float(state.get('creditor_confidence', 0.0))
    accepted = assignment.get('status') == 'active' and confidence >= .4
    if accepted:
        old = float(assignment['per_turn_cap'])
        new = round(old * .5, 2)
        assignment['per_turn_cap'] = new
        assignment['extended'] = True
        assignment['control_until_turn'] = int(world['scenario']['horizon_turns']) + 8
        state['creditor_levy_per_turn'] = new
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - .10)
        _economy(world)['control_extension_turns'] += 8
        from scenario_oversight import sign as sign_oversight
        sign_oversight(world, 0.0)
        state['oversight_agreement']['expires_turn'] = assignment['control_until_turn']
        message = (f'The Caisse accepted a {old:.1f}→{new:.1f} collection cap in exchange '
                   'for eight additional turns of inspection after the campaign horizon.')
    else:
        state['creditor_confidence'] = max(0.0, confidence - .03)
        message = 'Britain and France rejected the lower levy because creditor confidence is too weak.'
    assignment['extension_proposal'] = None
    state.setdefault('creditor_news', []).append({'turn': turn, 'headline': 'Caisse collection terms', 'body': message})
    world['scenario_feedback'] = message


def _fiscal_report(world, nation, turn):
    state = world['scenario_state']
    ledger = [entry for entry in state.get('debt_ledger', [])
              if entry.get('turn') == turn and entry.get('kind') == 'assigned_revenue']
    by_creditor = {}
    by_source = {}
    for entry in ledger:
        creditor = entry.get('creditor', 'Unknown')
        source = entry.get('source', 'unknown')
        by_creditor[creditor] = by_creditor.get(creditor, 0.0) + float(entry['amount'])
        by_source[source] = by_source.get(source, 0.0) + float(entry['amount'])
    hungry = sum(deficit_fraction(a) > 0 for tile in nation.tiles for a in _households(tile))
    public_meals = min(int(nation.government.food_inventory) // 4,
                       int(state.get('relief_units_per_turn', 30)))
    unfunded = max(0, hungry - public_meals)
    avg_price = sum(_price(tile) for tile in nation.tiles) / max(1, len(nation.tiles))
    buy_budget = unfunded * 4 * avg_price
    available = max(0.0, float(nation.government.agent.cash))
    missing_cash = max(0.0, buy_budget - available)
    diverted = sum(by_creditor.values())
    report = {'turn': turn, 'creditors': by_creditor, 'sources': by_source,
              'diverted': round(diverted, 2), 'unfunded_meals': unfunded,
              'relief_purchase_cost': round(buy_budget, 2),
              'cash_shortfall': round(missing_cash, 2),
              'attributable_to_assignment': round(min(diverted, missing_cash), 2)}
    _economy(world)['fiscal_reports'].append(report)


def _emit_public_grain_acquisition(nation, tile, owner, *, action_id, turn,
                                  units, cash_amount, treasury_before,
                                  treasury_after, owner_cash_before,
                                  owner_cash_after, owner_food_before,
                                  owner_food_after, public_food_before,
                                  public_food_after, details=None):
    currency = (getattr(nation, 'currency', None)
                or getattr(tile, 'home_currency', None) or 'local_currency')
    operation_type = ('public_grain_purchase' if cash_amount > 0
                      else 'private_grain_requisition')
    operation_id = _grain_operation_id(
        tile, turn, operation_type, owner.id, nation.name)
    cash_event_id = None
    if cash_amount > 0:
        payer = account_ref(
            'government_treasury', nation.name, currency,
            subaccount='government_agent.cash',
            balance_before=treasury_before, balance_after=treasury_after,
            balance_scope='government_agent.cash')
        payee = account_ref(
            'agent', owner.id, currency,
            balance_before=owner_cash_before, balance_after=owner_cash_after,
            balance_scope='cash')
        contract = transfer_contract(
            operation_id, operation_type, side='payer', amount=cash_amount,
            amount_currency=currency, payer_account=payer, payee_account=payee,
            local_cash_leg_amount=cash_amount, local_cash_leg_currency=currency,
            counterparty_leg_status='warehouse_owner_cash_balance_captured',
            mutation_reference={'turn': int(turn), 'tile': tile.name,
                                'action_id': action_id, 'owner_id': owner.id})
        cash_event_id = emit_treasury_leg(
            tile, kind='scenario_public_grain_purchase',
            nation_name=nation.name, currency=currency,
            signed_amount=-float(cash_amount), contract=contract,
            phase='scenario_economy',
            inputs={'action_id': action_id, 'owner_id': owner.id,
                    'food_units': int(units), 'paid': float(cash_amount),
                    **(details or {})})
    payer_goods = account_ref(
        'private_warehouse', owner.id, 'food_units',
        balance_before=int(owner_food_before),
        balance_after=int(owner_food_after), balance_scope='warehouse_food')
    payee_goods = account_ref(
        'government_food_inventory', nation.name, 'food_units',
        balance_before=int(public_food_before),
        balance_after=int(public_food_after), balance_scope='food_inventory')
    goods_event_id = _emit_grain_stock_transfer(
        tile, operation_id=operation_id, operation_type=operation_type,
        units=units, payer_account=payer_goods, payee_account=payee_goods,
        turn=turn,
        cash_transfer_status=('treasury_transfer.v1' if cash_amount > 0
                              else 'not_paid_requisition'),
        cash_event_id=cash_event_id,
        details={'action_id': action_id, 'owner_id': owner.id,
                 'cash_amount': float(cash_amount),
                 'warehouse_owner_cash_before': float(owner_cash_before),
                 'warehouse_owner_cash_after': float(owner_cash_after),
                 **(details or {})})
    return operation_id, goods_event_id


def apply_action(world, nation, action_id, tile=None):
    econ = _economy(world)
    treasury = nation.government.agent
    if action_id in NATIONAL_ACTIONS:
        if action_id == 'extend_collection_term':
            assignment = world['scenario_state'].get('collection_assignment') or {}
            if assignment.get('status') != 'active':
                return False, 'There is no active collection assignment to renegotiate.'
            if assignment.get('extended') or assignment.get('extension_proposal'):
                return False, 'The collection term has already been extended.'
            old = float(assignment['per_turn_cap'])
            assignment['extension_proposal'] = {'reply_turn': int(world['turn']) + 1}
            return True, f'Proposed a {old:.1f}→{old * .5:.1f} collection cap for eight more inspection turns; the Caisse replies next turn.'
        total = stock(world, nation)
        if action_id == 'open_private_grain_market':
            operation_id = _private_grain_policy_operation_id(
                world, nation, action_id)
            policy_before = econ['grain_policy']
            if econ['grain_policy'] == 'open':
                _trace_private_grain_policy(
                    world, nation, operation_id=operation_id, success=False,
                    reason='grain_market_already_open', before=policy_before,
                    after=policy_before,
                    details={'private_stock_before': float(total),
                             'sold_units': 0,
                             'release_event_ids': []})
                return False, 'Private grain sales are already open.'
            econ['grain_policy'] = 'open'
            sold = 0
            release_event_ids = []
            tile_results = []
            for tile in nation.tiles:
                tile.scenario_grain_policy = 'open'
                reserved_before = _reserved(world, tile)
                tile.scenario_grain_offer_units = reserved_before
                owner = _holder(world, tile)
                if owner is None:
                    continue
                tile_sold = _sell_to_households(
                    world, tile, owner, limit=reserved_before,
                    trigger='open_private_grain_market',
                    trace_operation_id=f'{operation_id}:{tile.name}',
                    trace_event_ids=release_event_ids)
                sold += tile_sold
                tile_results.append({
                    'tile': tile.name, 'owner_id': owner.id,
                    'reserved_before': reserved_before,
                    'reserved_after': _reserved(world, tile),
                    'sold_units': int(tile_sold)})
            stock_after = float(stock(world, nation))
            _trace_private_grain_policy(
                world, nation, operation_id=operation_id, success=True,
                reason=('private_sales_opened' if total else
                        'private_sales_opened_without_reserved_stock'),
                before=policy_before, after=econ['grain_policy'],
                details={'private_stock_before': float(total),
                         'private_stock_after': stock_after,
                         'sold_units': int(sold),
                         'tile_release_results': tile_results,
                         'release_event_ids': release_event_ids},
                cause_event_ids=release_event_ids or None)
            return True, f'Allowed private grain sales: {sold} units reached households that could pay; holders continue to set the price.'
        if total <= 0:
            return False, 'No private warehouse maize is available.'
        available = min(total, 80)
        bought = 0
        paid = 0.0
        operation_ids = []
        grain_event_ids = []
        for region in nation.tiles:
            owner = _holder(world, region)
            if owner is None:
                continue
            price = _price(region) * (1.20 if action_id == 'buy_private_grain' else 0.0)
            reserved_before = _reserved(world, region)
            units = min(reserved_before, available - bought,
                        int(treasury.cash / price) if price else available)
            if units <= 0:
                continue
            owner_food_before = int(owner.inv_get(Goods.food, 0))
            owner_cash_before = float(owner.cash)
            treasury_before = float(treasury.cash)
            public_food_before = int(nation.government.food_inventory)
            unrest_before = float(getattr(region, 'unrest_level', 0.0))
            owner.inv_add(Goods.food, -units)
            _set_reserved(world, region, reserved_before - units)
            nation.government.food_inventory += units
            if price:
                treasury.cash -= units * price
                owner.cash += units * price
                paid += units * price
            if not price:
                region.unrest_level = min(1.0, unrest_before + .04)
            operation_id, grain_event_id = _emit_public_grain_acquisition(
                nation, region, owner, action_id=action_id,
                turn=int(world['turn']), units=units, cash_amount=units * price,
                treasury_before=treasury_before, treasury_after=float(treasury.cash),
                owner_cash_before=owner_cash_before,
                owner_cash_after=float(owner.cash),
                owner_food_before=owner_food_before,
                owner_food_after=int(owner.inv_get(Goods.food, 0)),
                public_food_before=public_food_before,
                public_food_after=int(nation.government.food_inventory),
                details={'unit_price': price, 'warehouse_reserve_before': reserved_before,
                         'warehouse_reserve_after': _reserved(world, region),
                         'treasury_cash_before': treasury_before,
                         'treasury_affordable_units': (
                             int(treasury_before / price) if price > 0 else None),
                         'price_premium_over_local_food': (
                             price / _price(region) if price > 0 else None),
                         'unrest_before': unrest_before,
                         'unrest_after': float(region.unrest_level)})
            operation_ids.append(operation_id)
            if grain_event_id is not None:
                grain_event_ids.append(grain_event_id)
            if not price:
                from run_trace import emit
                emit(region, kind='grain_requisition_unrest',
                     record_class='outcome', phase='scenario_economy',
                     subject={'type': 'tile', 'id': region.name},
                     metric_id='politics.unrest_level', unit='ratio',
                     before=unrest_before, after=float(region.unrest_level),
                     formula_id='scenario.private_grain_requisition.unrest.v1',
                     inputs={'operation_id': operation_id,
                             'requisitioned_units': units,
                             'unrest_added': float(region.unrest_level) - unrest_before},
                     cause_event_ids=[grain_event_id] if grain_event_id else None)
            bought += units
            _record_grain(world, region, 'public_buy' if price else 'requisition', units,
                          units * price, owner.id, operation_ids=[operation_id])
        if not bought:
            return False, 'The treasury cannot afford the available grain.'
        world['scenario_state']['public_maize_stock_units'] = nation.government.food_inventory
        from run_trace import emit
        if action_id == 'requisition_private_grain':
            legitimacy_before = float(nation.legitimacy)
            nation.legitimacy = max(0.0, float(nation.legitimacy) - .04)
            emit(nation.tiles[0], kind='grain_requisition_legitimacy',
                 record_class='outcome', phase='scenario_economy',
                 subject={'type': 'nation', 'id': nation.name},
                 metric_id='politics.legitimacy', unit='ratio',
                 before=legitimacy_before, after=float(nation.legitimacy),
                 formula_id='scenario.private_grain_requisition.legitimacy.v1',
                 inputs={'operation_ids': operation_ids, 'requisitioned_units': bought,
                         'legitimacy_loss': legitimacy_before - float(nation.legitimacy)},
                 cause_event_ids=grain_event_ids or None)
            return True, f'Requisitioned {bought} private maize units for public relief; owners protest and legitimacy fell.'
        legitimacy_before = float(nation.legitimacy)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .01)
        emit(nation.tiles[0], kind='grain_purchase_legitimacy',
             record_class='outcome', phase='scenario_economy',
             subject={'type': 'nation', 'id': nation.name},
             metric_id='politics.legitimacy', unit='ratio',
             before=legitimacy_before, after=float(nation.legitimacy),
             formula_id='scenario.private_grain_purchase.legitimacy.v1',
             inputs={'operation_ids': operation_ids, 'purchased_units': bought,
                     'legitimacy_gain': float(nation.legitimacy) - legitimacy_before},
             cause_event_ids=grain_event_ids or None)
        return True, f'Bought {bought} private maize units for {paid:.1f} treasury units; owners received the cash.'
    if tile is None:
        return False, 'Select an Egyptian district first.'
    people = _households(tile)
    collective = econ['collective_by_tile'][tile.name]
    if action_id == 'district_arrears_relief':
        turn = int(world['turn'])
        operation_id = f'district-arrears-relief:{tile.name}:{turn}'
        debtors = [a for a in people if econ['arrears'].get(a.id, {}).get('balance', 0) > 0]
        if not debtors:
            _trace_district_economy_action(
                tile, nation, action_id=action_id, operation_id=operation_id,
                turn=turn, success=False, reason='no_recorded_cultivator_arrears',
                inputs={'eligible_household_count': len(people),
                        'debtor_count': 0})
            return False, 'No cultivator arrears are recorded here.'
        tax_rate_before = float(tile.gov.tax_rate)
        legitimacy_before = float(nation.legitimacy)
        forgiven = 0.0
        writeoff_event_ids = []
        debtor_rows = []
        municipal_total = 0.0
        national_total = 0.0
        for agent in debtors:
            row = econ['arrears'][agent.id]
            balance_before = float(row['balance'])
            missed_before = int(row.get('missed', 0))
            forgiven += balance_before
            national_share = (round(balance_before * NATIONAL_CADASTRAL_SHARE, 6)
                              if getattr(tile, 'owner_nation', None) is not None else 0.0)
            local_share = balance_before - national_share
            municipal_total += local_share
            national_total += national_share
            allocations = (
                ('municipal', getattr(getattr(tile, 'gov', None), 'agent', None), local_share),
                ('national', getattr(getattr(nation, 'government', None), 'agent', None), national_share),
            )
            event_ids = []
            from economy.actor_accounts import record as record_economic_event
            for tier, creditor, amount in allocations:
                if creditor is None or amount <= 0.0:
                    continue
                event = record_economic_event(
                    tile, 'tax_arrears_writeoff', turn=int(world['turn']),
                    payer_id=agent.id, recipient_id=creditor.id,
                    amount=amount,
                    asset_id=f'scenario-tax-arrears:{agent.id}:{tier}',
                    currency=getattr(tile, 'home_currency', None) or nation.currency,
                    detail={'origin': 'cadastral_tax', 'creditor_tier': tier,
                            'action': 'district_arrears_relief',
                            'balance_before': balance_before,
                            'balance_after': 0.0})
                event_ids.append(event['id'])
            row['balance'] = 0.0
            row['missed'] = 0
            from run_trace import emit
            writeoff_event_id = emit(
                tile, kind='tax_arrears_forgiven', record_class='outcome',
                phase='scenario_policy',
                subject={'type': 'tile', 'id': tile.name,
                         'agent_id': agent.id},
                metric_id='finance.tax_arrears_writeoff',
                unit=getattr(tile, 'home_currency', None) or nation.currency,
                before=balance_before, after=0.0,
                inputs={'operation_id': operation_id, 'debtor_id': agent.id,
                        'creditor_tiers': [tier for tier, creditor, amount in allocations
                                           if creditor is not None and amount > 0.0],
                        'municipal_writeoff': local_share,
                        'national_writeoff': national_share,
                        'missed_assessments': missed_before,
                        'economic_event_ids': event_ids,
                        'action': 'district_arrears_relief'})
            if writeoff_event_id is not None:
                writeoff_event_ids.append(writeoff_event_id)
            debtor_rows.append({'debtor_id': str(agent.id),
                                'balance_before': balance_before,
                                'balance_after': float(row['balance']),
                                'missed_before': missed_before,
                                'municipal_writeoff': local_share,
                                'national_writeoff': national_share,
                                'economic_event_ids': event_ids,
                                'writeoff_event_id': writeoff_event_id})
        tile.gov.tax_rate = max(0.0, float(tile.gov.tax_rate) - .03)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .015)
        _trace_district_economy_action(
            tile, nation, action_id=action_id, operation_id=operation_id,
            turn=turn, success=True, reason='arrears_forgiven_and_tax_reduced',
            inputs={'debtor_count': len(debtors), 'debtor_rows': debtor_rows,
                    'forgiven_total': forgiven,
                    'municipal_writeoff_total': municipal_total,
                    'national_writeoff_total': national_total,
                    'writeoff_event_ids': writeoff_event_ids,
                    'tax_rate_before': tax_rate_before,
                    'tax_rate_after': float(tile.gov.tax_rate),
                    'tax_rate_reduction': tax_rate_before - float(tile.gov.tax_rate),
                    'tax_rate_reduction_rule': 'max(0.0, tax_rate_before - 0.03)',
                    'legitimacy_before': legitimacy_before,
                    'legitimacy_after': float(nation.legitimacy),
                    'legitimacy_increase': float(nation.legitimacy) - legitimacy_before,
                    'legitimacy_increase_rule': 'min(1.0, legitimacy_before + 0.015)'},
            cause_event_ids=writeoff_event_ids or None)
        return True, f'Forgave {forgiven:.1f} unpaid cadastral taxes for {len(debtors)} cultivators in {_name(tile)}; the next assessments fall.'
    if action_id == 'district_support_mutual_aid':
        donors = [a for a in people if a.inv_get(Goods.food, 0) >= 5
                  and deficit_fraction(a) == 0]
        receivers = [a for a in people if deficit_fraction(a) > 0]
        if not donors or not receivers:
            return False, 'Mutual aid needs both a willing food donor and an underfed household.'
        moved = 0
        mutual_aid_before = int(collective['mutual_aid_meals'])
        operation_id = (f'mutual-aid:{tile.name}:{int(world["turn"])}:supported:'
                        f'{mutual_aid_before}')
        transfer_event_ids = []
        for receiver in receivers:
            if not donors:
                break
            donor = donors[0]
            donor_before = int(donor.inv_get(Goods.food, 0))
            receiver_before = int(receiver.inv_get(Goods.food, 0))
            donor.inv_add(Goods.food, -1)
            receiver.inv_add(Goods.food, 1)
            event_id = _trace_household_mutual_aid_transfer(
                tile, operation_id=f'{operation_id}:{moved + 1}',
                turn=int(world['turn']), donor=donor, receiver=receiver,
                donor_before=donor_before,
                donor_after=int(donor.inv_get(Goods.food, 0)),
                receiver_before=receiver_before,
                receiver_after=int(receiver.inv_get(Goods.food, 0)),
                mode='supported')
            if event_id is not None:
                transfer_event_ids.append(event_id)
            moved += 1
            if donor.inv_get(Goods.food, 0) < 5:
                donors.pop(0)
        collective['mutual_aid_meals'] += moved
        total_event_id = _trace_mutual_aid_total(
            tile, operation_id=operation_id, turn=int(world['turn']),
            mode='supported', before=mutual_aid_before,
            after=int(collective['mutual_aid_meals']),
            transfer_event_ids=transfer_event_ids)
        legitimacy_before = float(nation.legitimacy)
        nation.legitimacy = min(1.0, legitimacy_before
                                + .005 * (1 - exp(-moved / 5)))
        from run_trace import emit
        emit(tile, kind='mutual_aid_legitimacy_gain', record_class='outcome',
             phase='scenario_economy',
             subject={'type': 'nation', 'id': nation.name},
             metric_id='politics.legitimacy', unit='ratio',
             before=legitimacy_before, after=float(nation.legitimacy),
             formula_id='scenario.mutual_aid_legitimacy.v1',
             inputs={'operation_id': operation_id,
                     'meals_moved': int(moved),
                     'increase': float(nation.legitimacy) - legitimacy_before},
             cause_event_ids=([total_event_id]
                              if total_event_id is not None else None))
        return True, f'Local mutual-aid networks moved {moved} food units from surplus households in {_name(tile)}.'
    if action_id == 'district_bargain_workers':
        turn = int(world['turn'])
        operation_id = f'district-bargain:{tile.name}:{turn}'
        strikers = [a for a in people if getattr(a, 'is_striking', False)]
        if not strikers and not collective['petitioners']:
            _trace_worker_bargain(
                tile, nation, operation_id=operation_id, turn=turn,
                success=False, reason='no_active_petition_or_strike',
                inputs={'active_striker_ids': [],
                        'petitioners_before': int(collective['petitioners']),
                        'employer_ids_considered': []})
            return False, 'No local petition or strike is active.'
        employers = [a for a in tile.agents if getattr(a, 'is_corporation', False) and a.alive]
        employers += [a for a in tile.agents if getattr(a, 'is_lord', False) and a.alive]
        if not employers:
            _trace_worker_bargain(
                tile, nation, operation_id=operation_id, turn=turn,
                success=False, reason='no_living_local_employer',
                inputs={'active_striker_ids': [str(a.id) for a in strikers],
                        'petitioners_before': int(collective['petitioners']),
                        'employer_ids_considered': []})
            return False, 'No local owner or employer is available to bargain.'

        petitioners_before = int(collective['petitioners'])
        recorded_strikers_before = int(collective['strikers'])
        settlement_until_before = int(collective['settlement_until_turn'])
        recorded_scenario_strikers_before = [
            str(agent_id) for agent_id in econ['scenario_strikers_by_tile'][tile.name]]
        unrest_before = float(tile.unrest_level)
        legitimacy_before = float(nation.legitimacy)
        wage_event_ids = []
        source_legs = []
        payments = 0.0
        for employer in employers:
            wage_before = float(employer.wage)
            cash_before = float(employer.cash)
            wage_after = min(20.0, wage_before + .5)
            grant = min(5.0, max(0.0, cash_before) * .02)
            employer.wage = wage_after
            employer.cash -= grant
            payments += grant
            cash_after = float(employer.cash)
            employer_currency = (getattr(tile, 'home_currency', None)
                                 or getattr(nation, 'currency', None)
                                 or 'local_currency')
            source_legs.append({
                'employer_id': str(employer.id), 'currency': employer_currency,
                'account': account_ref(
                    'agent_cash', str(employer.id), employer_currency,
                    balance_before=cash_before, balance_after=cash_after,
                    balance_scope='cash'),
                'amount': float(grant), 'cash_before': cash_before,
                'cash_after': cash_after, 'wage_before': wage_before,
                'wage_after': wage_after,
                'grant_rule': 'min(5.0, max(0.0, cash_before) * 0.02)'})
            from run_trace import emit
            wage_event_id = emit(
                tile, kind='district_bargain_wage_offer',
                record_class='outcome', phase='scenario_action',
                subject={'type': 'tile/firm', 'id': str(employer.id),
                         'tile': tile.name,
                         'firm_name': (getattr(employer, 'company_name', None)
                                       or str(employer.id))},
                metric_id='labor.firm_wage',
                unit=(getattr(tile, 'home_currency', None)
                      or getattr(nation, 'currency', None) or 'local_currency'),
                before=wage_before, after=wage_after,
                formula_id='scenario.district_bargain_wage_offer.v1',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'action_id': 'district_bargain_workers',
                        'employer_cash_before': cash_before,
                        'employer_cash_after': cash_after,
                        'grant': float(grant),
                        'grant_rule': 'min(5.0, max(0.0, cash_before) * 0.02)',
                        'wage_increment': .5, 'wage_cap': 20.0})
            if wage_event_id is not None:
                wage_event_ids.append(wage_event_id)
        recipients = strikers or people[:max(1, min(len(people), collective['petitioners']))]
        currency = (getattr(tile, 'home_currency', None)
                    or getattr(nation, 'currency', None) or 'local_currency')
        recipient_allocations = []
        for agent in recipients:
            cash_before = float(agent.cash)
            amount = payments / len(recipients)
            agent.cash += amount
            agent.is_striking = False
            recipient_allocations.append({
                'agent_id': str(agent.id), 'amount': float(amount),
                'cash_before': cash_before, 'cash_after': float(agent.cash),
                'was_striking': bool(getattr(agent, 'is_striking', False)
                                     or agent in strikers)})
        transfer_event_id = _trace_worker_bargain_transfer(
            tile, operation_id=operation_id, turn=turn, currency=currency,
            total=float(payments), source_legs=source_legs,
            recipients=recipient_allocations)
        collective['strikers'] = 0
        collective['petitioners'] = max(0, collective['petitioners'] // 2)
        collective['settlement_until_turn'] = turn + 3
        econ['scenario_strikers_by_tile'][tile.name] = []
        tile.unrest_level *= exp(-.12)
        nation.legitimacy = min(1.0, float(nation.legitimacy) + .02)
        outcome_inputs = {
            'active_striker_ids': [str(a.id) for a in strikers],
            'strikers_reported_before': recorded_strikers_before,
            'strikers_after': int(collective['strikers']),
            'petitioners_before': petitioners_before,
            'petitioners_after': int(collective['petitioners']),
            'employer_ids_considered': [str(a.id) for a in employers],
            'employer_contributions': source_legs,
            'wage_event_ids': wage_event_ids,
            'wage_rule': 'min(20.0, wage_before + 0.5)',
            'grant_rule': 'min(5.0, max(0.0, cash_before) * 0.02)',
            'recipient_basis': ('active_strikers' if strikers
                                else 'petitioners_household_fallback'),
            'recipient_allocations': recipient_allocations,
            'cash_pool_total': float(payments),
            'cash_transfer_event_id': transfer_event_id,
            'cash_transfer_status': (
                'zero_employer_contribution' if transfer_event_id is None else
                'transferred_to_selected_households' if recipient_allocations else
                'employer_debit_without_household_receipt'),
            'settlement_until_turn_before': settlement_until_before,
            'settlement_until_turn_after': turn + 3,
            'scenario_striker_ids_before': recorded_scenario_strikers_before,
            'scenario_striker_ids_after': [],
            'unrest_before': unrest_before,
            'unrest_after': float(tile.unrest_level),
            'unrest_multiplier': exp(-.12),
            'legitimacy_before': legitimacy_before,
            'legitimacy_after': float(nation.legitimacy),
            'legitimacy_increase': float(nation.legitimacy) - legitimacy_before}
        causes = wage_event_ids + ([transfer_event_id]
                                   if transfer_event_id is not None else [])
        _trace_worker_bargain(
            tile, nation, operation_id=operation_id, turn=turn, success=True,
            reason='strike_or_petition_settled', inputs=outcome_inputs,
            cause_event_ids=causes or None)
        return True, f'Owners in {_name(tile)} raised offered wages by 0.5 and paid {payments:.1f} to petitioners; the local strike ended.'
    if action_id == 'district_break_strike':
        from unrest import apply_repression
        turn = int(world['turn'])
        operation_id = f'district-break-strike:{tile.name}:{turn}'
        police_count = int(getattr(tile, 'police_employed', 0))
        garrison_units = [unit for unit in getattr(tile, 'military_units', [])
                          if getattr(unit, 'soldiers', 0) > 0]
        force_inputs = {
            'police_employed': police_count,
            'garrison_units': [
                {'id': str(getattr(unit, 'unit_id',
                                   getattr(unit, 'name', index))),
                 'soldiers': int(getattr(unit, 'soldiers', 0)),
                 'strength': float(getattr(unit, 'strength', 0.0))}
                for index, unit in enumerate(garrison_units)]}
        if not (police_count or garrison_units):
            _trace_district_economy_action(
                tile, nation, action_id=action_id, operation_id=operation_id,
                turn=turn, success=False, reason='no_police_or_garrison',
                inputs={'active_striker_ids': [str(agent.id) for agent in people
                                               if agent.is_striking],
                        'strikers_before': int(collective['strikers']),
                        **force_inputs},
                labor_event_kind='district_strike_repression_gate_rejected')
            return False, 'No police or garrison is present to break the strike.'
        active_striker_ids = [str(agent.id) for agent in people
                              if agent.is_striking]
        strikers_before = int(collective['strikers'])
        injuries_before = int(collective['injuries'])
        scenario_strikers_before = [str(agent_id)
                                    for agent_id in econ['scenario_strikers_by_tile'][tile.name]]
        protest_log = getattr(tile, 'protest_energy_log', None)
        protest_before = float(protest_log[-1]) if protest_log else None
        legitimacy_before = float(nation.legitimacy)
        repression_event_ids = []
        injured = apply_repression(
            tile, turn, operation_id=operation_id,
            trace_event_ids=repression_event_ids)
        for agent in people:
            if agent.is_striking:
                agent.is_striking = False
        collective['injuries'] += injured
        collective['strikers'] = 0
        econ['scenario_strikers_by_tile'][tile.name] = []
        protest_after = float(protest_log[-1]) if protest_log else None
        _trace_district_economy_action(
            tile, nation, action_id=action_id, operation_id=operation_id,
            turn=turn, success=True, reason='force_used_to_break_strike',
            inputs={'active_striker_ids_before': active_striker_ids,
                    'strikers_before': strikers_before,
                    'strikers_after': int(collective['strikers']),
                    'striker_flags_cleared': active_striker_ids,
                    'injury_memory_count_before': injuries_before,
                    'injury_memory_count_added': int(injured),
                    'injury_memory_count_after': int(collective['injuries']),
                    'scenario_striker_ids_before': scenario_strikers_before,
                    'scenario_striker_ids_after': [],
                    'repression_event_ids': repression_event_ids,
                    'protest_energy_before': protest_before,
                    'protest_energy_after': protest_after,
                    'legitimacy_before': legitimacy_before,
                    'legitimacy_after': float(nation.legitimacy),
                    **force_inputs},
            cause_event_ids=repression_event_ids or None,
            labor_event_kind='district_strike_broken')
        return True, f'Police broke the {_name(tile)} strike; {injured} people received casualty memories and government support fell.'
    return False, 'Unknown political-economy decision.'

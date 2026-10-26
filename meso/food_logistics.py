"""Paid, delayed movement of emergency grain between districts in a province."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

from collections import deque

from food_levy import levy_capacity, record_levy
from goods import Goods
from nutrition import appetite_units
from run_trace import emit


def _residents(tile):
    return [a for a in tile.agents if a.alive and not a.is_corporation
            and not a.is_government and not getattr(a, 'military_unit_id', None)]


def _distance(source, destination, tile_names):
    queue = deque([(source, 0)])
    seen = {source.name}
    while queue:
        tile, hops = queue.popleft()
        if tile is destination:
            return max(1, hops)
        for neighbor in tile.neighbors.values():
            if neighbor.name in tile_names and neighbor.name not in seen:
                seen.add(neighbor.name)
                queue.append((neighbor, hops + 1))
    return None


def _trace_goods_transfer(region, *, kind, operation_id, shipment_id,
                          operation_type, units, payer_type, payer_id,
                          payer_before, payer_after, payee_type, payee_id,
                          payee_before, payee_after, turn, inputs=None,
                          cause_event_ids=None):
    """Record both exact food inventories for one relief shipment leg."""
    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'parent_operation_id': shipment_id,
        'operation_type': operation_type,
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(units),
        'payer_account': {
            'type': payer_type, 'id': str(payer_id),
            'good': Goods.food.name,
            'balance_before': int(payer_before),
            'balance_after': int(payer_after),
            'balance_scope': 'food_inventory',
        },
        'payee_account': {
            'type': payee_type, 'id': str(payee_id),
            'good': Goods.food.name,
            'balance_before': int(payee_before),
            'balance_after': int(payee_after),
            'balance_scope': 'food_inventory',
        },
        'counterparty_leg_status': 'both_food_inventory_balances_captured',
    }
    return emit(
        region, kind=kind, record_class='transfer', phase='local',
        subject={'type': 'tile', 'id': region.name, 'good': Goods.food.name,
                 'shipment_id': shipment_id},
        metric_id='goods.provincial_relief', unit='food_units',
        before=0, after=int(units),
        inputs={'turn': int(turn), 'operation_id': operation_id,
                'shipment_id': shipment_id, 'transfer_contract': contract,
                **(inputs or {})},
        cause_event_ids=cause_event_ids)


def _trace_haulage_payment(region, *, shipment_id, turn, government,
                           payments, amount, government_before,
                           government_after, currency, cause_event_ids=None):
    from finance_trace import cash_transfer_contract, emit_cash_transfer

    operation_id = f'{shipment_id}:haulage'
    hauler_accounts = [
        {'id': str(hauler.id),
         'currency': getattr(hauler, 'home_currency', None) or currency,
         'balance_before': float(before), 'balance_after': float(after),
         'amount': float(payment)}
        for hauler, payment, before, after in payments
    ]
    contract = cash_transfer_contract(
        operation_id, 'provincial_food_haulage', amount=amount,
        currency=currency,
        payer_account={
            'type': 'government_agent_cash', 'id': str(government.id),
            'currency': currency, 'balance_before': float(government_before),
            'balance_after': float(government_after),
            'balance_scope': 'cash',
        },
        payee_account={
            'type': 'agent_cash_group', 'id': f'{shipment_id}:haulers',
            'currency': currency, 'member_count': len(hauler_accounts),
            'member_ids': [row['id'] for row in hauler_accounts],
            'members': hauler_accounts, 'balance_scope': 'member_cash_balances',
        },
        shipment_id=shipment_id,
        haulage_currency=currency,
        counterparty_leg_status='government debit and each hauler cash balance captured',
    )
    return emit_cash_transfer(
        region, kind='provincial_food_haulage_payment', contract=contract,
        phase='local',
        subject={'type': 'tile', 'id': region.name,
                 'shipment_id': shipment_id},
        inputs={'turn': int(turn), 'shipment_id': shipment_id},
        cause_event_ids=cause_event_ids)


def _shipment_id(province, shipment, index):
    return str(shipment.get('shipment_id') or
               f'{province.name}:{shipment["dispatched_turn"]}:'
               f'{shipment.get("source", "unknown")}:'
               f'{shipment.get("destination", "unknown")}:{index + 1}')


def deliver_province_food(province, turn):
    """Unload only shipments whose physical travel time has elapsed."""
    pending = []
    for shipment_index, shipment in enumerate(getattr(province, 'food_shipments', [])):
        if shipment['arrival_turn'] > turn:
            pending.append(shipment)
            continue
        destination = next((r for r in province.tiles
                            if r.name == shipment['destination']), None)
        if destination is None:
            pending.append(shipment)
            continue
        shipment_id = _shipment_id(province, shipment, shipment_index)
        remaining = shipment['units']
        recipients = []
        transfer_event_ids = []
        cargo_balance = int(shipment['units'])
        for person in sorted(_residents(destination),
                             key=lambda a: (-a.hungry_steps, a.energy_reserve_kcal,
                                            a.inv_get(Goods.food, 0), a.id)):
            if remaining <= 0:
                break
            meal_gap = max(0, appetite_units(person) - person.inv_get(Goods.food, 0))
            given = min(remaining, meal_gap)
            if given:
                recipient_before = int(person.inv_get(Goods.food, 0))
                cargo_before = cargo_balance
                person.inv_add(Goods.food, given)
                remaining -= given
                cargo_balance -= given
                recipient_after = int(person.inv_get(Goods.food, 0))
                transfer = {
                    'agent_id': person.id, 'units': given,
                    'food_before': recipient_before,
                    'food_after': recipient_after,
                }
                transfer_id = _trace_goods_transfer(
                    destination, kind='provincial_relief_recipient_transfer',
                    operation_id=f'{shipment_id}:arrival:recipient:{person.id}',
                    shipment_id=shipment_id,
                    operation_type='provincial_food_relief_to_resident',
                    units=given, payer_type='shipment_cargo_inventory',
                    payer_id=shipment_id, payer_before=cargo_before,
                    payer_after=cargo_balance, payee_type='agent_inventory',
                    payee_id=person.id, payee_before=recipient_before,
                    payee_after=recipient_after, turn=turn,
                    inputs={'destination': destination.name,
                            'dispatch_operation_id': shipment_id})
                if transfer_id:
                    transfer_event_ids.append(transfer_id)
                    transfer['trace_event_id'] = transfer_id
                recipients.append(transfer)
        if remaining:
            government_before = int(destination.gov.food_inventory)
            cargo_before = cargo_balance
            destination.gov.food_inventory += remaining
            cargo_balance -= remaining
            transfer_id = _trace_goods_transfer(
                destination, kind='provincial_relief_government_stock_transfer',
                operation_id=f'{shipment_id}:arrival:government-stock',
                shipment_id=shipment_id,
                operation_type='provincial_food_relief_to_public_stock',
                units=remaining, payer_type='shipment_cargo_inventory',
                payer_id=shipment_id, payer_before=cargo_before,
                payer_after=cargo_balance,
                payee_type='government_food_inventory',
                payee_id=destination.gov.name,
                payee_before=government_before,
                payee_after=int(destination.gov.food_inventory), turn=turn,
                inputs={'destination': destination.name,
                        'dispatch_operation_id': shipment_id})
            if transfer_id:
                transfer_event_ids.append(transfer_id)
        destination.relief_food_delivered_this_turn = (
            getattr(destination, 'relief_food_delivered_this_turn', 0)
            + shipment['units'] - remaining)
        emit(destination, kind='provincial_food_arrival',
             record_class='transfer',
             phase='local',
             subject={'type': 'tile', 'id': destination.name,
                      'good': Goods.food.name},
             metric_id='goods.provincial_relief', unit='units',
             after=shipment['units'],
             inputs={**shipment, 'shipment_id': shipment_id,
                     'dispatch_operation_id': shipment_id,
                     'cause_operation_ids': [shipment_id],
                     'recipients': recipients,
                     'unallocated_to_government': remaining,
                     'cargo_balance_after': cargo_balance},
             cause_event_ids=transfer_event_ids)
    province.food_shipments = pending


def dispatch_province_food(province, turn):
    """Levy local surplus, pay haulers, and send grain to a hungry district."""
    if not hasattr(province, 'food_shipments'):
        province.food_shipments = []
    if not getattr(province.gov, 'emergency_food_policy', False):
        return []
    tile_names = {tile.name for tile in province.tiles}
    destinations = []
    sources = []
    for tile in province.tiles:
        residents = _residents(tile)
        if not residents:
            continue
        hungry_share = sum(a.calorie_deficit_kcal > 0 for a in residents) / len(residents)
        meal_gap = sum(max(0, appetite_units(a) - a.inv_get(Goods.food, 0))
                       for a in residents)
        if hungry_share >= 0.1 and meal_gap:
            destinations.append((tile, hungry_share, meal_gap))
        donors = []
        for person in tile.agents:
            if (not person.alive or person.is_government
                    or getattr(person, 'military_unit_id', None)):
                continue
            reserve = 0 if person.is_corporation else 2 * appetite_units(person)
            surplus = max(0, person.inv_get(Goods.food, 0) - reserve)
            if surplus:
                donors.append((person, surplus))
        available = sum(levy_capacity(person,
                                     0 if person.is_corporation else 2 * appetite_units(person))
                        for person, _surplus in donors)
        if available > 4 * len(residents) and hungry_share < 0.1:
            sources.append((tile, available, donors))
    if not destinations or not sources:
        return []

    destinations.sort(key=lambda item: (-item[1], -item[2], item[0].name))
    sources.sort(key=lambda item: (-item[1], item[0].name))
    gov = province.gov
    if getattr(gov, '_food_aid_turn', -1) != turn:
        gov.food_aid_last_turn = 0
        gov.food_levy_last_turn = 0
        gov._food_aid_turn = turn
    dispatched = []
    for destination, _hunger, meal_gap in destinations:
        outstanding = meal_gap
        for source, _available, donors in sources:
            if outstanding <= 0 or source is destination:
                continue
            distance = _distance(source, destination, tile_names)
            if distance is None:
                emit(source, kind='provincial_food_dispatch_skipped',
                     record_class='outcome', phase='local',
                     subject={'type': 'tile', 'id': source.name,
                              'good': Goods.food.name},
                     metric_id='goods.provincial_relief',
                     inputs={'reason': 'no_provincial_route',
                             'source': source.name,
                             'destination': destination.name,
                             'turn': int(turn)})
                continue
            # Larger districts can mobilize more carts; the wage is paid to
            # named local residents and each hop adds travel time and cost.
            capacity = max(32, 4 * len(_residents(source)))
            unit_cost = 0.05 * distance
            deposit = province.bank.deposits.get(gov.agent, 0)
            if getattr(province.bank, 'is_frozen', False):
                deposit = min(deposit,
                              getattr(province.bank, 'subsistence_withdrawal_cap', 5.0))
            liquid = gov.agent.cash + deposit
            affordable = int(max(0, liquid) / unit_cost)
            request = min(outstanding, capacity, affordable)
            if request <= 0:
                emit(source, kind='provincial_food_dispatch_skipped',
                     record_class='outcome', phase='local',
                     subject={'type': 'tile', 'id': source.name,
                              'good': Goods.food.name},
                     metric_id='goods.provincial_relief',
                     inputs={'reason': 'haulage_unaffordable',
                             'source': source.name,
                             'destination': destination.name,
                             'turn': int(turn),
                             'unmet_food_units': int(outstanding),
                             'haulage_capacity_units': int(capacity),
                             'haulage_unit_cost': float(unit_cost),
                             'government_cash': float(gov.agent.cash),
                             'available_bank_deposit': float(deposit),
                             'liquid_funds': float(liquid),
                             'affordable_food_units': int(affordable),
                             'bank_withdrawals_frozen': bool(
                                 getattr(province.bank, 'is_frozen', False))})
                continue
            taken = 0
            contributor_rows = []
            shipment_id = f'{province.name}:{turn}:{len(dispatched) + 1}'
            cargo_balance = 0
            goods_transfer_event_ids = []
            for donor, surplus in sorted(donors,
                                         key=lambda row: (-int(row[0].is_corporation),
                                                          -row[1], row[0].id)):
                if taken >= request:
                    break
                current_reserve = 0 if donor.is_corporation else 2 * appetite_units(donor)
                levy = min(request - taken,
                           levy_capacity(donor, current_reserve))
                if levy:
                    donor_before = int(donor.inv_get(Goods.food, 0))
                    cargo_before = cargo_balance
                    donor.inv_add(Goods.food, -levy)
                    record_levy(donor, levy)
                    taken += levy
                    cargo_balance += levy
                    donor_after = int(donor.inv_get(Goods.food, 0))
                    contribution = {'agent_id': donor.id, 'units': levy,
                                    'food_before': donor_before,
                                    'food_after': donor_after}
                    transfer_id = _trace_goods_transfer(
                        source, kind='provincial_relief_donor_transfer',
                        operation_id=f'{shipment_id}:dispatch:donor:{donor.id}',
                        shipment_id=shipment_id,
                        operation_type='provincial_food_levy_to_transit',
                        units=levy, payer_type='agent_inventory',
                        payer_id=donor.id, payer_before=donor_before,
                        payer_after=donor_after,
                        payee_type='shipment_cargo_inventory',
                        payee_id=shipment_id, payee_before=cargo_before,
                        payee_after=cargo_balance, turn=turn,
                        inputs={'source': source.name,
                                'destination': destination.name,
                                'protected_reserve_units': current_reserve,
                                'surplus_units_at_assessment': int(surplus)})
                    if transfer_id:
                        goods_transfer_event_ids.append(transfer_id)
                        contribution['trace_event_id'] = transfer_id
                    contributor_rows.append(contribution)
            if taken == 0:
                continue
            cost = taken * unit_cost
            gov_region = next((region for region in province.tiles
                               if gov.agent in getattr(region, 'agents', ())), source)
            if gov.agent.cash < cost:
                province.bank.Withdraw(
                    gov.agent, cost - gov.agent.cash, trace_region=gov_region,
                    t=turn, reason='provincial_food_haulage')
            government_cash_before = float(gov.agent.cash)
            _trace_cash_write = _trace_public_begin(None, gov.agent)
            gov.agent.cash -= cost
            government_cash_write_ids = _trace_public_finish(
                _trace_cash_write, 'food_logistics:dispatch_province_food',
                inputs={"source_writer": 'food_logistics.py:dispatch_province_food:e195b7a3fe8bb464:1'})
            government_cash_after = float(gov.agent.cash)
            haulers = [a for a in _residents(source) if a.output == Goods.transport]
            if not haulers:
                haulers = _residents(source)
            haulers = sorted(haulers, key=lambda a: a.id)[:5]
            haulage_event_ids = []
            if haulers:
                payments = []
                payment_balances = []
                for hauler in haulers:
                    payment = cost / len(haulers)
                    hauler_cash_before = float(hauler.cash)
                    _trace_cash_write = _trace_public_begin(None, hauler)
                    hauler.cash += payment
                    _trace_public_finish(_trace_cash_write, 'food_logistics:dispatch_province_food',
                                         inputs={"source_writer": 'food_logistics.py:dispatch_province_food:575af869467b1ab6:1'})
                    hauler_cash_after = float(hauler.cash)
                    payments.append((hauler, payment))
                    payment_balances.append((hauler, payment,
                                             hauler_cash_before,
                                             hauler_cash_after))
                payment_event_id = _trace_haulage_payment(
                    gov_region, shipment_id=shipment_id, turn=turn,
                    government=gov.agent, payments=payment_balances,
                    amount=cost,
                    government_before=government_cash_before,
                    government_after=government_cash_after,
                    currency=getattr(gov_region, 'home_currency', None) or 'unknown',
                    cause_event_ids=goods_transfer_event_ids)
                if payment_event_id:
                    haulage_event_ids.append(payment_event_id)
                from finance_trace import emit_public_account_flow
                treasury_flow_event_id = emit_public_account_flow(
                    gov_region, gov.agent,
                    kind='government_provincial_food_haulage_payment',
                    signed_amount=-cost,
                    inputs={'operation_id': f'{shipment_id}:haulage',
                            'shipment_id': shipment_id,
                            'source': source.name,
                            'destination': destination.name,
                            'food_units': taken},
                    cause_event_ids=(government_cash_write_ids
                                     + ([payment_event_id]
                                        if payment_event_id else [])) or None)
                if treasury_flow_event_id:
                    haulage_event_ids.append(treasury_flow_event_id)
                from economy.actor_accounts import record as record_economic_event
                shipment_detail = {'shipment_id': shipment_id,
                                   'shipment_source': source.name,
                                   'shipment_destination': destination.name,
                                   'shipment_units': taken,
                                   'hauler_count': len(haulers),
                                   'total_haulage_payment': cost}
                if gov_region is source:
                    for hauler, payment in payments:
                        record_economic_event(
                            source, 'provincial_food_haulage', turn=turn,
                            payer_id=gov.agent.id, recipient_id=hauler.id,
                            good=Goods.food, quantity=taken, amount=payment,
                            source_id=shipment_id, detail=shipment_detail)
                else:
                    record_economic_event(
                        gov_region, 'provincial_food_haulage', turn=turn,
                        payer_id=gov.agent.id, amount=cost, source_id=shipment_id,
                        detail={**shipment_detail,
                                'recipient_ids': [hauler.id for hauler, _ in payments]})
                    for hauler, payment in payments:
                        record_economic_event(
                            source, 'provincial_food_haulage', turn=turn,
                            recipient_id=hauler.id, good=Goods.food,
                            quantity=taken, amount=payment, source_id=shipment_id,
                            detail={**shipment_detail, 'payer_id': gov.agent.id})
            else:
                _trace_cash_write = _trace_public_begin(None, gov.agent)
                gov.agent.cash += cost
                _trace_public_finish(_trace_cash_write, 'food_logistics:dispatch_province_food',
                                     inputs={"source_writer": 'food_logistics.py:dispatch_province_food:1217626170ed61aa:1'})
            shipment = {'source': source.name,
                        'destination': destination.name,
                        'dispatched_turn': turn,
                        'arrival_turn': turn + distance,
                        'distance': distance,
                        'units': taken,
                        'haulage_wages': round(cost, 4),
                        'shipment_id': shipment_id}
            province.food_shipments.append(shipment)
            source.emergency_grain_levy_units = (
                getattr(source, 'emergency_grain_levy_units', 0) + taken)
            gov.food_levy_last_turn += taken
            emit(source, kind='provincial_food_dispatch', record_class='transfer',
                 phase='local',
                 subject={'type': 'tile', 'id': source.name,
                          'good': Goods.food.name},
             metric_id='goods.provincial_relief', unit='units',
             after=taken,
             inputs={**shipment, 'contributors': contributor_rows,
                     'operation_id': shipment_id,
                     'hauler_ids': [a.id for a in haulers],
                     'haulage_payment_status': ('paid' if haulers
                                                else 'refunded_no_haulers'),
                     'cargo_balance_after': cargo_balance,
                     'haulage_payment_actual': cost if haulers else 0.0},
             cause_event_ids=goods_transfer_event_ids + haulage_event_ids)
            dispatched.append(shipment)
            outstanding -= taken
    return dispatched

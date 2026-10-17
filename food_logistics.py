"""Paid, delayed movement of emergency grain between districts in a province."""

from __future__ import annotations

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


def deliver_province_food(province, turn):
    """Unload only shipments whose physical travel time has elapsed."""
    pending = []
    for shipment in getattr(province, 'food_shipments', []):
        if shipment['arrival_turn'] > turn:
            pending.append(shipment)
            continue
        destination = next((r for r in province.tiles
                            if r.name == shipment['destination']), None)
        if destination is None:
            pending.append(shipment)
            continue
        remaining = shipment['units']
        recipients = []
        for person in sorted(_residents(destination),
                             key=lambda a: (-a.hungry_steps, a.energy_reserve_kcal,
                                            a.inv_get(Goods.food, 0), a.id)):
            if remaining <= 0:
                break
            meal_gap = max(0, appetite_units(person) - person.inv_get(Goods.food, 0))
            given = min(remaining, meal_gap)
            if given:
                person.inv_add(Goods.food, given)
                remaining -= given
                recipients.append({'agent_id': person.id, 'units': given})
        if remaining:
            destination.gov.food_inventory += remaining
        destination.relief_food_delivered_this_turn = (
            getattr(destination, 'relief_food_delivered_this_turn', 0)
            + shipment['units'] - remaining)
        emit(destination, kind='provincial_food_arrival', record_class='transfer',
             phase='local',
             subject={'type': 'tile', 'id': destination.name,
                      'good': Goods.food.name},
             metric_id='goods.provincial_relief', unit='units',
             after=shipment['units'],
             inputs={**shipment, 'recipients': recipients,
                     'unallocated_to_government': remaining})
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
                continue
            taken = 0
            contributor_rows = []
            for donor, surplus in sorted(donors,
                                         key=lambda row: (-int(row[0].is_corporation),
                                                          -row[1], row[0].id)):
                if taken >= request:
                    break
                current_reserve = 0 if donor.is_corporation else 2 * appetite_units(donor)
                levy = min(request - taken,
                           levy_capacity(donor, current_reserve))
                if levy:
                    donor.inv_add(Goods.food, -levy)
                    record_levy(donor, levy)
                    taken += levy
                    contributor_rows.append({'agent_id': donor.id, 'units': levy})
            if taken == 0:
                continue
            cost = taken * unit_cost
            if gov.agent.cash < cost:
                province.bank.Withdraw(gov.agent, cost - gov.agent.cash)
            gov.agent.cash -= cost
            haulers = [a for a in _residents(source) if a.output == Goods.transport]
            if not haulers:
                haulers = _residents(source)
            haulers = sorted(haulers, key=lambda a: a.id)[:5]
            if haulers:
                for hauler in haulers:
                    hauler.cash += cost / len(haulers)
            else:
                gov.agent.cash += cost
            shipment = {'source': source.name,
                        'destination': destination.name,
                        'dispatched_turn': turn,
                        'arrival_turn': turn + distance,
                        'distance': distance,
                        'units': taken,
                        'haulage_wages': round(cost, 4)}
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
                         'hauler_ids': [a.id for a in haulers]})
            dispatched.append(shipment)
            outstanding -= taken
    return dispatched

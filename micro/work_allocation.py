"""One bounded work budget for main work, crops, gathering, and engineering."""
from __future__ import annotations


def available_work(region, person, turn):
    from households import human
    from labor_choice import career_lifecycle_age
    if (not human(person) or career_lifecycle_age(person, turn) < 14
            or getattr(person, 'military_unit_id', None) or getattr(person, 'in_workhouse', False)):
        return 0.0
    result = min(1, max(0, getattr(region, 'workday_cap', 8) / 8))
    result *= max(0, 1 - min(1, getattr(person, 'health_attrition', 0) * .25))
    result *= max(.5, 1 / (1 + .2 * max(0, person.hungry_steps)))
    if getattr(person, 'subsistence_arrival_turn', None) == turn:
        result = max(0, result - getattr(person, 'subsistence_travel_work', .5))
    return result


def begin(region, turn):
    if getattr(region, 'work_allocations', {}).get('turn') == turn:
        return region.work_allocations
    from labor_choice import career_lifecycle_age
    from households import human
    rows = {}
    for person in region.agents:
        if (not human(person) or career_lifecycle_age(person, turn) < 14
                or getattr(person, 'military_unit_id', None) or getattr(person, 'in_workhouse', False)):
            continue
        available = available_work(region, person, turn)
        rows[person.id] = {'available': available, 'activities': {}, 'used': 0.0}
    region.work_allocations = {'turn': turn, 'people': rows}
    return region.work_allocations


def assign(region, person, activity, requested):
    row = region.work_allocations['people'].get(person.id)
    if row is None:
        return 0.0
    supplied = min(max(0, requested), max(0, row['available'] - row['used']))
    row['activities'][activity] = row['activities'].get(activity, 0) + supplied
    row['used'] += supplied
    return supplied


def remaining(region, person):
    row = getattr(region, 'work_allocations', {}).get('people', {}).get(person.id)
    return max(0, row['available'] - row['used']) if row else 0


def main_work(region, person, turn):
    state = getattr(region, 'work_allocations', {})
    if state.get('turn') != turn:
        return None
    return state['people'].get(person.id, {}).get('activities', {}).get('main', 0.0)


def finish(region, turn, *, production_enabled=True):
    from career_transitions import profession
    from goods import Goods
    from agriculture import requirements
    from engineering import production_work_share
    needs = requirements(region, turn) if production_enabled else {}
    people = {a.id: a for a in region.agents if a.alive}
    for person in sorted(people.values(), key=lambda a: a.id):
        if 'engineering' not in region.work_allocations['people'].get(person.id, {}).get('activities', {}):
            assign(region, person, 'engineering', production_work_share(person, turn))
        withholding = (person.is_striking or person.in_revolt
                       or person.id in getattr(region, 'pollution_revolt_ids', ()))
        if not withholding:
            employer = getattr(person, 'employer', None)
            operations = [f for f in region.farms.values() if
                         (employer is not None and f.get('employer_id') == employer.id)
                         or f['operator_id'] == person.id]
            for farm in operations:
                prior = sum(r['activities'].get(farm['id'], 0) for r in region.work_allocations['people'].values())
                assign(region, person, farm['id'], max(0, needs.get(farm['id'], 0) - prior))
    from collections import Counter
    counts = Counter(profession(p) for p in people.values())
    # Temporary farm jobs are real funded orders, not compulsory career changes.
    orders = getattr(region, 'seasonal_work_orders', []) if production_enabled else ()
    for order in orders:
        if order.get('turn') != turn or order.get('completed'):
            continue
        farm = region.farms.get(order['farm_id'])
        payer = next((a for a in region.agents if a.id == order['payer_id']), None)
        if farm is None or payer is None:
            continue
        short = min(order['quantity'], max(0, needs.get(farm['id'], 0) - sum(
            r['activities'].get(farm['id'], 0) for r in region.work_allocations['people'].values()))
                    )
        for person in sorted(people.values(), key=lambda a: (a.employer is not None, a.id)):
            if (short <= 0 or person.employer is not None or person.is_striking or person.in_revolt
                    or person.id in getattr(region, 'pollution_revolt_ids', ())):
                continue
            rate = max(.01, order['pay_rate'])
            good = profession(person)
            if good is not None and good != Goods.food:
                from economy.labor_mobility import independent_return
                alternative, _ = independent_return(region, person, good, counts[good], turn)
                if alternative > rate:
                    continue
            share = assign(region, person, farm['id'], min(short, payer.cash / rate))
            if share:
                from state_handler import transfer_cash
                transfer_cash(payer, person, share * rate, region=region,
                              kind='seasonal_farm_work', record_event_kind='wage', turn=turn)
                short -= share
                order['delivered'] += share
        order['completed'] = True
    for person in people.values():
        if (profession(person) != Goods.food and not person.is_striking and not person.in_revolt
                and person.id not in getattr(region, 'pollution_revolt_ids', ())):
            assign(region, person, 'main', remaining(region, person))
    for row in region.work_allocations['people'].values():
        if row['used'] > row['available'] + 1e-9:
            raise AssertionError('Work exceeds available turn')

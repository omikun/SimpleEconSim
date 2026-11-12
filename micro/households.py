"""Stable guardian/dependent households; food sharing does not pool money."""
from __future__ import annotations
from goods import Goods
from nutrition import appetite_units, basic_food_units


def human(person):
    return (getattr(person, 'alive', True) and not getattr(person, 'is_corporation', False)
            and not getattr(person, 'is_government', False))


def rebuild(region, turn):
    people = {a.id: a for a in region.agents if human(a)}
    old = getattr(region, 'households', {})
    previous = {pid: row for row in old.values() for pid in row['members']}
    groups = {}
    for person in sorted(people.values(), key=lambda a: a.id):
        child = getattr(person, 'is_native_child', False) and person.age(turn) < 14
        parent = getattr(person, 'parent', None)
        guardian = parent if child and parent is not None and parent.id in people else None
        if child and guardian is None:
            prior = previous.get(person.id, {})
            guardian = next((people[pid] for pid in prior.get('members', ()) if pid in people
                             and not (people[pid].is_native_child and people[pid].age(turn) < 14)), None)
            if guardian is None and parent is not None:
                kin = [p for p in people.values() if p is not person
                       and (getattr(p, 'parent', None) is parent or p is getattr(parent, 'parent', None))
                       and not (p.is_native_child and p.age(turn) < 14)]
                guardian = min(kin, key=lambda p: p.id) if kin else None
        leader = guardian or person
        key = str(leader.id)
        row = groups.setdefault(key, {'id': key, 'buyer_id': leader.id, 'members': [],
                                     'created_turn': old.get(key, {}).get('created_turn', turn)})
        row['members'].append(person.id)
        person.household_id = key
    region.households = groups
    region.household_people = people
    return groups


def members(person, region):
    groups = getattr(region, 'households', {})
    row = groups.get(str(getattr(person, 'household_id', person.id)))
    if row is None:
        turn = int(getattr(region, '_last_turn', 0))
        parent = getattr(person, 'parent', None)
        leader = parent if (person.is_native_child and person.age(turn) < 14
                            and parent is not None and parent.alive and parent in region.agents) else person
        children = [a for a in getattr(region, 'agents', ()) if human(a) and getattr(a, 'parent', None) is leader
                    and a.is_native_child and a.age(turn) < 14]
        return [leader, *children]
    index = getattr(region, 'household_people', None)
    if index is not None:
        return [index[pid] for pid in row['members'] if pid in index and human(index[pid])]
    ids = set(row['members'])
    return [a for a in region.agents if a.id in ids and human(a)]


def buyer(person, region):
    row = getattr(region, 'households', {}).get(str(getattr(person, 'household_id', person.id)))
    if row is not None:
        return row['buyer_id'] == person.id
    return members(person, region)[0] is person


def food(person):
    return max(0, person.inv_get(Goods.food, 0)) + max(0, person.inv_get(Goods.prepared_food, 0))


def demand(person, region, *, reserve_turns=None):
    family = members(person, region)
    ordinary = sum(basic_food_units(p) for p in family)
    meal = sum(appetite_units(p) for p in family)
    available = sum(food(p) + max(0, getattr(p, 'emergency_food_units', 0)) for p in family)
    if reserve_turns is None:
        from agriculture import turns_until_harvest, can_operate
        owns_crop = any(f['operator_id'] == person.id and f['area'] > 0
                       and f.get('employer_id') is None
                       and ((f.get('crop') and not f['crop']['closed']) or can_operate(region, f, person))
                       for f in getattr(region, 'farms', {}).values())
        reserve_turns = getattr(region, 'household_food_reserve_turns',
                                turns_until_harvest(region) if owns_crop else 1)
    reserve_turns = max(0, float(reserve_turns))
    target = meal + ordinary * reserve_turns
    is_buyer = buyer(person, region)
    return {'meal_gap': max(0, meal - available), 'target': target,
            'reserve_turns': reserve_turns, 'desired': max(0, target - available) if is_buyer else 0,
            'dependent_order': not is_buyer, 'ordinary': ordinary,
            'available': available, 'member_ids': [p.id for p in family]}


def allocate(region, turn):
    """Reserve proportional basic meals before anyone eats, independent of shuffle."""
    from food_accounts import transfer
    rebuild(region, turn)
    transferred, causes = 0.0, []
    for row in region.households.values():
        family = [a for a in region.agents if a.id in row['members'] and human(a)]
        for good in (Goods.prepared_food, Goods.food):
            held = {person.id: person.inv_get(good, 0) for person in family}
            total = sum(held.values())
            if total <= 0:
                continue
            # First cover ordinary needs proportionally; recovery uses remainder.
            targets = {p.id: max(0, basic_food_units(p) -
                       (p.inv_get(Goods.prepared_food, 0) if good == Goods.food else 0)
                       - getattr(p, 'emergency_food_units', 0)) for p in family}
            need = sum(targets.values())
            share = min(1, total / need) if need else 0
            recipients = [(p, max(0, targets[p.id] * share - held[p.id])) for p in family]
            donors = [(p, max(0, held[p.id] - targets[p.id] * share)) for p in family]
            for recipient, gap in recipients:
                for i, (donor, surplus) in enumerate(donors):
                    moved = transfer(region, donor, recipient, min(gap, surplus),
                                     kind='household_allocation', good=good)
                    if moved:
                        transferred += moved
                        event = region.food_accounts['events'][-1].get('trace_event_id')
                        if event:
                            causes.append(event)
                    gap -= moved
                    donors[i] = donor, surplus - moved
                    if gap <= .001:
                        break

    if transferred:
        from run_trace import emit
        emit(region, kind='household_food_transfer', record_class='outcome', phase='demographics',
             subject={'type': 'tile', 'id': region.name}, metric_id='food.household_transfer',
             unit='food_units', after=transferred, cause_event_ids=causes or None,
             inputs={'turn': turn, 'allocation_rule': 'proportional_basic_meals'})

"""Physical storage capacity. A full store changes losses/sales, not crop growth."""
from goods import Goods


def granary_capacity(region):
    return 120 + sum(1200 * max(0, b.operational_efficiency) for b in getattr(region, 'buildings', ())
                     if b.name == 'granary' and getattr(b, 'private_owner_id', None) is None)


def capacity(region, person, good=Goods.food):
    from nutrition import basic_food_units
    from households import members, human
    if person.is_trader:
        return max(80, getattr(person, 'max_inventory', 80))
    if person.is_government:
        return granary_capacity(region)
    if person.is_corporation:
        basic = max(20, len(person.employees) * 16)
        operator = getattr(person, 'owner', None)
        operator_id = getattr(operator, 'id', None)
    else:
        basic = sum(basic_food_units(p) for p in members(person, region)) * 3 if human(person) else 0
        operator_id = person.id
    if good == Goods.prepared_food:
        return max(8, basic)
    farms = [f for f in getattr(region, 'farms', {}).values() if
             f['operator_id'] == operator_id and
             (person.is_corporation or f.get('employer_id') is None)]
    owned = sum(max(0, f['storage_capacity'] - f['food_milli'] / 1000) for f in farms)
    added = sum(1200 * max(0, b.operational_efficiency) for b in getattr(region, 'buildings', ())
                if b.name == 'granary' and getattr(b, 'private_owner_id', None) == person.id)
    return max(0, basic + owned + added)


def enforce(region):
    from food_accounts import consume, LocatedAccount, PublicAccount
    for person in region.agents:
        for good in (Goods.food, Goods.prepared_food):
            excess = max(0, person.inv_get(good, 0) - capacity(region, person, good))
            if excess:
                consume(region, person, excess, kind='storage_loss', good=good,
                        reason='uncovered_storage_overflow', capacity=capacity(region, person, good))
    institutions = {id(i): i for i in (getattr(region, 'gov', None), getattr(region, 'charity', None),
                    getattr(getattr(region, 'owner_nation', None), 'government', None)) if i is not None}
    limit = granary_capacity(region)
    for institution in institutions.values():
        excess = max(0, institution.food_at(region) - limit)
        if excess:
            consume(region, LocatedAccount(institution, region), excess, kind='storage_loss',
                    reason='institutional_storage_overflow', capacity=limit)
    excess = max(0, getattr(region, 'granary_stock', 0) - limit)
    if excess:
        consume(region, PublicAccount(region), excess, kind='storage_loss',
                reason='granary_storage_overflow', capacity=limit)

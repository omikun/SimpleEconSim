"""Physical food transactions. Reservations are claims, never extra stock."""
from __future__ import annotations
from goods import Goods
from food_inventory import SCALE, milli


def state(region):
    if not hasattr(region, 'food_accounts'):
        region.food_accounts = {'version': 2, 'reservations': {}, 'events': [], 'sequence': 0}
    return region.food_accounts


def balance(owner, good=Goods.food):
    if hasattr(owner, 'food_balance'):
        return owner.food_balance
    if hasattr(owner, 'inv_get'):
        return owner.inv_get(good, 0)
    return owner.get('food_milli' if good == Goods.food else 'prepared_milli', 0) / SCALE


def write(owner, amount, good=Goods.food):
    if milli(amount) < 0:
        raise ValueError('Negative physical food balance')
    if hasattr(owner, 'food_balance'):
        owner.food_balance = milli(amount) / SCALE
    elif hasattr(owner, 'inv_set'):
        owner.inv_set(good, milli(amount) / SCALE)
    else:
        owner['food_milli' if good == Goods.food else 'prepared_milli'] = milli(amount)


def identity(owner):
    return str(owner.id if hasattr(owner, 'id') else owner['id'])


def reserved(region, owner, good=Goods.food):
    accounts = getattr(region, 'food_accounts', {})
    key = f'{identity(owner)}:{good.name}'
    return sum(accounts.get('reservations', {}).get(key, {}).values()) / SCALE


def available(region, owner, good=Goods.food):
    return max(0, balance(owner, good) - reserved(region, owner, good))


def reserve(region, owner, purpose, quantity, good=Goods.food):
    key = f'{identity(owner)}:{good.name}'
    rows = state(region)['reservations'].setdefault(key, {})
    other = sum(value for label, value in rows.items() if label != purpose)
    rows[purpose] = min(max(0, milli(quantity)), max(0, milli(balance(owner, good)) - other))
    return rows[purpose] / SCALE


def release(region, owner, purpose, good=Goods.food):
    key = f'{identity(owner)}:{good.name}'
    return state(region)['reservations'].get(key, {}).pop(purpose, 0) / SCALE


def record(region, kind, quantity, *, source=None, destination=None, good=Goods.food, **detail):
    book = state(region)
    book['sequence'] += 1
    row = {'id': f'{region.name}:food:{book["sequence"]}',
           'turn': int(getattr(region, '_last_turn', 0)), 'kind': kind,
           'good': good.name, 'units': milli(quantity) / SCALE,
           'source': identity(source) if source is not None else None,
           'destination': identity(destination) if destination is not None else None, **detail}
    book['events'].append(row)
    if len(book['events']) > 5000:
        del book['events'][:-5000]
    from run_trace import emit
    event_id = emit(region, kind='food_account_transaction', record_class='outcome', phase='local',
         subject={'type': 'tile', 'id': region.name, 'good': good.name},
         metric_id='food.account_transaction', unit='food_units', after=row['units'], inputs=row)
    row['trace_event_id'] = event_id
    return row


def transfer(region, source, destination, quantity, *, kind='transfer', good=Goods.food,
             use_reserved=False, **detail):
    permitted = balance(source, good) if use_reserved else available(region, source, good)
    quantity = min(max(0, milli(quantity)), milli(permitted)) / SCALE
    if quantity <= 0 or source is destination:
        return 0.0
    source_before, destination_before = balance(source, good), balance(destination, good)
    write(source, source_before - quantity, good)
    write(destination, destination_before + quantity, good)
    record(region, kind, quantity, source=source, destination=destination, good=good,
           source_before=source_before, source_after=balance(source, good),
           destination_before=destination_before, destination_after=balance(destination, good), **detail)
    return quantity


class PublicAccount:
    """Primitive view of an existing located public balance, not another store."""
    def __init__(self, region, purpose='reserve'):
        self.region, self.purpose = region, purpose
        self.id = f'{region.name}:public:{purpose}'

    @property
    def food_balance(self):
        return self.region.granary_stock if self.purpose == 'reserve' else self.region.gov.food_at(self.region)

    @food_balance.setter
    def food_balance(self, value):
        if self.purpose == 'reserve':
            self.region.granary_stock = value
        else:
            self.region.gov.add_food(self.region, value - self.region.gov.food_at(self.region))


class LocatedAccount:
    def __init__(self, institution, region):
        self.institution, self.region = institution, region
        self.id = f'{region.name}:institution:{institution.agent.id}'

    @property
    def food_balance(self):
        return self.institution.food_at(self.region)

    @food_balance.setter
    def food_balance(self, value):
        self.institution.add_food(self.region, value - self.food_balance)


def create(region, destination, quantity, *, kind, good=Goods.food, **detail):
    quantity = max(0, milli(quantity)) / SCALE
    write(destination, balance(destination, good) + quantity, good)
    record(region, kind, quantity, destination=destination, good=good, **detail)
    return quantity


def consume(region, source, quantity, *, kind, good=Goods.food, **detail):
    quantity = min(max(0, milli(quantity)), milli(balance(source, good))) / SCALE
    write(source, balance(source, good) - quantity, good)
    record(region, kind, quantity, source=source, good=good, **detail)
    return quantity


def stocks(region):
    """Disjoint local accounts, including cargo and operating stores."""
    people = list(getattr(region, 'agents', ()))
    people.extend(a for a in getattr(region, 'unclaimed_estates', ()) if a not in people)
    public = getattr(getattr(region, 'gov', None), 'agent', None)
    charity = getattr(getattr(region, 'charity', None), 'agent', None)
    sovereign = getattr(getattr(region, 'owner_nation', None), 'government', None)
    for institution, person in ((getattr(region, 'gov', None), public),
                                (getattr(region, 'charity', None), charity),
                                (sovereign, getattr(sovereign, 'agent', None))):
        if (person is not None and person not in people
                and getattr(institution, 'food_default_site', None) == region.name):
            people.append(person)
    inventory = sum(sum(max(0, balance(a, good)) for good in (Goods.food, Goods.prepared_food))
                    for a in people)
    operating = sum(balance(f) for f in getattr(region, 'farms', {}).values())
    granary = max(0, getattr(region, 'granary_stock', 0))
    aid = max(0, region.gov.food_at(region)) if getattr(region, 'gov', None) is not None else 0
    charity_food = region.charity.food_at(region) if getattr(region, 'charity', None) is not None else 0
    national = sovereign.food_at(region) if sovereign is not None and sovereign is not getattr(region, 'gov', None) else 0
    queued = sum(max(0, getattr(a, 'emergency_food_units', 0)) for a in people)
    cargo = sum(max(0, a.inventory_export[Goods.food]) + max(0, a.inventory_foreign[Goods.food])
                for a in people if getattr(a, 'is_trader', False))
    return {'inventory': inventory, 'operating': operating, 'granary': granary,
            'aid': aid, 'national_reserve': national, 'charity': charity_food, 'queued': queued, 'cargo': cargo,
            'total': inventory + operating + granary + aid + national + charity_food + queued + cargo}

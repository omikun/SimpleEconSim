"""One claimable production balance shared by crop taxes and contracts.

Debits retire claimable units at the inventory boundary. Reserves, purchases,
gifts, and inheritances never register as a new harvest.
"""


def register(region, turn):
    if getattr(region, '_harvest_registered_turn', None) == turn:
        return
    region._harvest_registered_turn = turn
    actors = {a.id: a for a in region.agents}
    for receipt in getattr(region, 'production_receipts', ()):
        if receipt.get('turn') != turn:
            continue
        actor = actors.get(receipt['person_id'])
        if actor is None:
            continue
        good = receipt['good']
        book = dict(getattr(actor, 'unclaimed_production', {}))
        book[good.name] = book.get(good.name, 0) + max(0, receipt['quantity'])
        actor.unclaimed_production = book


def available(region, actor, good, turn):
    register(region, turn)
    if good is None:
        return 0.0
    return min(max(0, actor.inv_get(good, 0)),
               max(0, getattr(actor, 'unclaimed_production', {}).get(good.name, 0)))

"""World food conservation, including every located institution and cargo leg."""
from goods import Goods
from food_inventory import milli


def physical_stock(tiles, nations=()):
    actors, institutions, routes, provinces = {}, {}, {}, {}
    stored = 0.0
    for tile in tiles:
        for actor in [*tile.agents, *getattr(tile, 'unclaimed_estates', ())]:
            actors[actor.id] = actor
        for institution in (getattr(tile, 'gov', None), getattr(tile, 'charity', None)):
            if institution is not None:
                institutions[id(institution)] = institution
                actors[institution.agent.id] = institution.agent
        stored += max(0, getattr(tile, 'granary_stock', 0))
        stored += sum(f.get('food_milli', 0) / 1000 for f in getattr(tile, 'farms', {}).values())
        for route in tile._all_routes():
            routes[id(route)] = route
        province = getattr(tile, 'province', None)
        if province is not None:
            provinces[id(province)] = province
    for nation in nations:
        institution = getattr(nation, 'government', None)
        if institution:
            institutions[id(institution)] = institution
            actors[institution.agent.id] = institution.agent
    for actor in actors.values():
        for wallet in ('inventory', 'inventory_export', 'inventory_foreign'):
            values = getattr(actor, wallet, ())
            stored += sum(max(0, values[g]) for g in (Goods.food, Goods.prepared_food) if len(values) > g)
        stored += max(0, getattr(actor, 'emergency_food_units', 0))
        for values in getattr(actor, 'parked_foreign', {}).values():
            stored += sum(max(0, values[g]) for g in (Goods.food, Goods.prepared_food) if len(values) > g)
    stored += sum(i.food_inventory for i in institutions.values())
    for route in routes.values():
        stored += sum(e[2] for e in [*route.pending, *route.in_transit]
                      if e[1] in (Goods.food, Goods.prepared_food))
    stored += sum(s['units'] for p in provinces.values() for s in p.food_shipments)
    return milli(stored)


SOURCES = {'harvest', 'commons_gathering', 'external_food_receipt'}
SINKS = {'seed_use', 'storage_loss', 'meal', 'birth_food_cost',
         'engineering_food_input', 'food_processing_loss', 'external_food_export',
         'military_food_use', 'food_destroyed'}


def open_turn(tiles, nations, turn):
    return {'turn': turn, 'opening_milli': physical_stock(tiles, nations),
            'sequences': {tile.name: getattr(tile, 'food_accounts', {}).get('sequence', 0) for tile in tiles}}


def close_turn(tiles, nations, opening):
    events = [e for tile in tiles for e in getattr(tile, 'food_accounts', {}).get('events', ())
              if e['turn'] == opening['turn'] and
              int(e['id'].rsplit(':', 1)[-1]) > opening['sequences'].get(tile.name, 0)]
    incoming = sum(milli(e['units']) for e in events if e['kind'] in SOURCES)
    outgoing = sum(milli(e['units']) for e in events if e['kind'] in SINKS)
    closing = physical_stock(tiles, nations)
    row = {'turn': opening['turn'], 'opening': opening['opening_milli'] / 1000,
           'production_and_receipts': incoming / 1000, 'uses_and_losses': outgoing / 1000,
           'closing': closing / 1000,
           'unexplained': (closing - opening['opening_milli'] - incoming + outgoing) / 1000}
    for tile in tiles:
        tile.food_conservation_audit = row
    return row

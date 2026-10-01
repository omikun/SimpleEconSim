"""Strategic Egyptian sites, canal access, and supplied naval squadrons.

Sites are anchored to generated tiles. The route graph is deliberately small:
Guided play issues strategic orders while the shared terrain remains procedural.
"""

from __future__ import annotations


ROUTES = {
    'Mediterranean': ('Alexandria', 'Port Said'),
    'Alexandria': ('Mediterranean', 'Nile Delta'),
    'Port Said': ('Mediterranean', 'Ismailia'),
    'Ismailia': ('Port Said', 'Cairo'),
    'Nile Delta': ('Alexandria', 'Cairo'),
    'Cairo': ('Nile Delta', 'Ismailia', 'Upper Egypt'),
    'Upper Egypt': ('Cairo',),
}


def initialize(world):
    egypt = next(n for n in world['nations'] if n.name == 'Egypt')
    locations = {getattr(tile, 'scenario_location', ''): tile for tile in egypt.tiles}
    required = ('Alexandria', 'Nile Delta', 'Cairo', 'Upper Egypt')
    if any(name not in locations for name in required):
        raise ValueError('The Egypt campaign needs its coastal and Nile corridor tiles.')
    delta = locations['Nile Delta']
    cairo = locations['Cairo']
    # The named canal sites are strategic points on the existing Delta/Cairo
    # corridor; they do not claim additional generated land tiles.
    sites = {name: {'tile': tile.name, 'position': tuple(tile.centroid)}
             for name, tile in locations.items() if name in ROUTES}
    dx, dy = delta.centroid
    cx, cy = cairo.centroid
    sites['Port Said'] = {'tile': delta.name,
                         'position': (dx + 0.35 * abs(dx - cx), dy - 0.10 * abs(dy - cy))}
    sites['Ismailia'] = {'tile': delta.name,
                         'position': (dx + 0.25 * abs(dx - cx), (dy + cy) / 2)}
    sites['Mediterranean'] = {'tile': None, 'position': None}
    world['scenario_state']['geography'] = {
        'sites': sites, 'routes': {name: list(edges) for name, edges in ROUTES.items()},
        'canal_open': True, 'canal_controller': 'Egypt', 'transit_rights': ['Egypt', 'Britain', 'France'],
        'canal_tolls_collected': 0.0, 'fleets': {}, 'diplomacy': {},
    }


def site(world, name):
    return world['scenario_state']['geography']['sites'][name]


def canal_access(world, nation_name):
    geography = world['scenario_state']['geography']
    return geography['canal_open'] and nation_name in geography['transit_rights']


def create_fleet(world, nation_name, *, ships=4, guns=80, coal=5, transports=40):
    fleet = {'nation': nation_name, 'location': 'Mediterranean', 'ships': int(ships),
             'guns': float(guns), 'coal': int(coal), 'transports': int(transports),
             'supplied': True, 'damage': 0.0, 'movement': 1}
    world['scenario_state']['geography']['fleets'][nation_name] = fleet
    return fleet


def fleet_at(world, nation_name, location):
    fleet = world['scenario_state']['geography']['fleets'].get(nation_name)
    return bool(fleet and fleet['location'] == location and fleet['ships'] > 0
                and fleet['coal'] > 0 and fleet['supplied'])


def move_fleet(world, nation_name, destination):
    geography = world['scenario_state']['geography']
    fleet = geography['fleets'].get(nation_name)
    if not fleet or not fleet['supplied'] or fleet['coal'] <= 0:
        return False
    location = fleet['location']
    if destination not in geography['routes'].get(location, ()):
        return False
    if destination == 'Ismailia' and not canal_access(world, nation_name):
        return False
    if destination == 'Ismailia' and nation_name != 'Egypt':
        payer = next((n for n in world['nations'] if n.name == nation_name), None)
        egypt = next((n for n in world['nations'] if n.name == 'Egypt'), None)
        toll = 2.0
        if payer is None or egypt is None or payer.government.agent.cash < toll:
            return False
        payer.government.agent.cash -= toll
        egypt.government.agent.cash += toll
        geography['canal_tolls_collected'] += toll
    fleet['coal'] -= 1
    fleet['location'] = destination
    return True


def resupply(world, nation_name, amount=2):
    fleet = world['scenario_state']['geography']['fleets'].get(nation_name)
    if fleet and fleet['ships'] > 0:
        fleet['coal'] += int(amount)
        fleet['supplied'] = True


def foreign_decisions(world):
    """Britain and France evaluate the same crisis independently each turn."""
    from scenario_debt import outstanding
    from scenario_gunboat import _nation, _protest
    from scenario_situation import situation_template

    state = world['scenario_state']
    geography = state['geography']
    rules = situation_template()['naval_crisis']
    debt = outstanding(world)
    britain = _nation(world, 'Britain')
    france = _nation(world, 'France')
    britain_can_pay = bool(britain and britain.government.agent.cash >= float(rules['mobilization_cost']))
    british_support = (debt > 0 and britain_can_pay
                       and _protest(world, 'Britain') < float(rules['max_british_protest_energy']))
    # France may endorse collection without joining an armed expedition. High
    # protest or a costly expedition can also make it oppose unilateral force.
    french_protest = _protest(world, 'France')
    if not france or debt <= 0:
        french_policy = 'abstain'
    elif french_protest >= float(rules['max_french_protest_energy']) * 1.5:
        french_policy = 'oppose'
    elif (french_protest < float(rules['max_french_protest_energy'])
          and france.government.agent.cash >= 20):
        french_policy = 'support_demand'
    else:
        french_policy = 'abstain'
    geography['diplomacy'] = {
        'Britain': 'intervene' if british_support else 'withdraw',
        'France': french_policy,
        'Ottoman Empire': ('offer_mediation' if state.get('naval_crisis', {}).get('stage')
                           in ('mobilizing', 'ultimatum', 'blockaded') else 'observe'),
    }
    return geography['diplomacy']


def close_canal(world):
    state = world['scenario_state']
    geography = state['geography']
    if not geography['canal_open']:
        return False, 'The canal is already closed to foreign transit.'
    geography['canal_open'] = False
    geography['transit_rights'] = ['Egypt']
    state['creditor_confidence'] = max(0.0, state['creditor_confidence'] - 0.10)
    return True, 'Cairo closes foreign canal transit. British access is denied, while creditor confidence falls.'

"""Versioned observations and opt-in coordination for the Egypt experiment.

Observe mode remains read-only. Governing mode plans autonomous participation;
the existing labor and scenario handlers own its actual material effects.
"""

from __future__ import annotations

from copy import deepcopy
from math import exp, fsum, isfinite

from goods import Goods
from nutrition import deficit_fraction


VERSION = 1
GOVERNING_VERSION = 2
MODES = ('off', 'observe', 'governing')
KEY = 'governing_network'
COMMUNITIES = {
    'households': 'Cultivators and workers',
    'holders': 'Grainholders and landowners',
    'merchants': 'Merchants and exporters',
}
CHANNELS = ('food', 'arrears', 'property', 'trade')
# Scenario-authored contacts, not inferred historical associations or trust
# automatically assigned to every economic neighbor/river connection.
CONTACTS = (
    ('Upper Egypt', 'Cairo'), ('Cairo', 'Nile Delta'),
    ('Nile Delta', 'Alexandria'), ('Alexandria', 'Port Said'),
    ('Port Said', 'Ismailia'), ('Ismailia', 'Tel el Kebir'),
)
HISTORY_LIMIT = 24


def validate_creation_mode(selected_mode, scenario_id):
    if selected_mode not in MODES:
        raise ValueError('Choose off, observe or governing for the network experiment.')
    if selected_mode != 'off' and scenario_id != 'egypt_1877':
        raise ValueError('The governing-network experiment currently supports Egypt 1877.')


def mode(world):
    state = world.get('scenario_state', {}).get(KEY)
    if state is None:
        return 'off'  # An old save keeps its original behavior.
    expected = {'observe': VERSION, 'governing': GOVERNING_VERSION}.get(state.get('mode'))
    if expected is None or state.get('version') != expected:
        raise ValueError('Unsupported governing-network state; no conversion was applied.')
    if state.get('scenario_id') != world.get('scenario_id'):
        raise ValueError('Governing-network state belongs to another scenario.')
    validate_state(state)
    return state['mode']


def is_governing(world):
    state = world.get('scenario_state', {}).get(KEY)
    return bool(state and state.get('mode') == 'governing' and mode(world) == 'governing')


def validate_state(state):
    """Validate frozen references, including after a native checkpoint restore."""
    try:
        obs, nodes, edges = state['observation'], state['nodes'], state['edges']
        if (state['last_turn'] != obs['turn'] or not state['history']
                or state['history'][-1]['turn'] != state['last_turn']
                or state['topology_basis'] != 'authored_scenario_contacts_v1'):
            raise ValueError('Invalid governing-network observation boundary.')
        memberships = {key: set() for key in COMMUNITIES}
        for district in obs['districts'].values():
            for community in COMMUNITIES:
                ids = district['members'][community]
                if len(set(ids)) != len(ids) or memberships[community].intersection(ids):
                    raise ValueError('A community counts the same person twice.')
                memberships[community].update(ids)
                for pid in ids:
                    if obs['people'][str(pid)]['tile'] != district['id']:
                        raise ValueError('Community member belongs to another district.')
        for key, node in nodes.items():
            if (key != f'{node["tile"]}:{node["community"]}' or node['member_ids']
                    != obs['districts'][node['tile']]['members'][node['community']]):
                raise ValueError('Network membership differs from the frozen population.')
            if any(not isfinite(node['pressure'][channel])
                   or not 0 <= node['pressure'][channel] <= 1 for channel in CHANNELS):
                raise ValueError('Invalid network pressure.')
        allowed_bases = {'authored_association_contact'}
        if state['mode'] == 'governing':
            allowed_bases.add('competing_grain_claim')
        for edge in edges.values():
            if (edge['source'] not in nodes or edge['target'] not in nodes
                    or not isfinite(edge['weight']) or not 0 <= edge['weight'] <= 1
                    or edge['basis'] not in allowed_bases):
                raise ValueError('Invalid authored organization contact.')
        if state['mode'] == 'governing':
            if state['last_applied_turn'] not in (state['last_turn'], state['last_turn'] + 1):
                raise ValueError('Invalid network participation boundary.')
            if set(state['pending']) != set(obs['districts']):
                raise ValueError('Missing network district intent.')
            for tile_id, intent in state['pending'].items():
                members = set(obs['districts'][tile_id]['members']['households'])
                petitions, strikes = intent['petition_ids'], intent['strike_ids']
                if (len(set(petitions)) != len(petitions) or len(set(strikes)) != len(strikes)
                        or not set(strikes) <= set(petitions) <= members
                        or intent['effective_turn'] != state['last_turn'] + 1
                        or intent['observation_id'] != state['history'][-1]['id']
                        or set(intent['individual']) != {str(pid) for pid in members}):
                    raise ValueError('Invalid network participation references.')
            for organization in state['organizations'].values():
                if any(not isfinite(organization[key]) or not 0 <= organization[key] <= 1
                       for key in ('cohesion', 'delivery_trust')):
                    raise ValueError('Invalid organization memory.')
    except (KeyError, TypeError) as error:
        raise ValueError('Incomplete governing-network observation state.') from error


def initialize(world, selected_mode='off'):
    """Called only at scenario creation. Never convert an existing campaign."""
    validate_creation_mode(selected_mode, world.get('scenario_id'))
    if KEY in world.get('scenario_state', {}):
        if mode(world) != selected_mode:
            raise ValueError('Start a new campaign to change the network experiment mode.')
        return
    if selected_mode == 'off':
        return
    if int(world.get('turn', 0)) != 1 or world['scenario_state'].get('actions_taken'):
        raise ValueError('Start a new campaign to enable society observations.')
    observation = observe(world)
    nodes, edges = initial_graph(observation)
    world['scenario_state'][KEY] = {
        'version': GOVERNING_VERSION if selected_mode == 'governing' else VERSION,
        'mode': selected_mode, 'scenario_id': 'egypt_1877',
        'topology_basis': 'authored_scenario_contacts_v1',
        'last_turn': 1, 'observation': observation,
        'nodes': nodes, 'edges': edges, 'history': [],
        'diagnostics': diagnostics(nodes, edges),
    }
    _record(world, opening=True)
    if selected_mode == 'governing':
        from governing_collectives import initialize as initialize_collectives
        initialize_collectives(world)


def _nation(world):
    # Following a selected foreign district must not turn Egypt's community
    # observation into a projection of the foreign government.
    return next((n for n in world.get('nations', ()) if n.name == 'Egypt'), None)


def observe(world):
    """Copy material facts. Avoid stock()/district_snapshot(), which clamp stores."""
    nation = _nation(world)
    if nation is None:
        raise ValueError('The Egypt observation needs the Egyptian population.')
    state = world['scenario_state']
    econ = state['political_economy']
    result = {
        'turn': int(world['turn']), 'people': {}, 'districts': {},
        'treasury': float(nation.government.agent.cash),
        'public_maize': int(nation.government.food_inventory),
        'grain_policy': econ['grain_policy'],
    }
    seen = set()
    for tile in sorted(nation.tiles, key=lambda t: t.name):
        collective = econ['collective_by_tile'].get(tile.name, {})
        owner_id = econ['warehouse_by_tile'].get(tile.name)
        district = {
            'id': tile.name,
            'name': getattr(tile, 'scenario_location', None) or tile.name,
            'members': {key: [] for key in COMMUNITIES},
            'owner_id': None, 'private_maize': 0,
            'petitioners': int(collective.get('petitioners', 0)),
            'strikers': int(collective.get('strikers', 0)),
            'mutual_aid_meals': int(collective.get('mutual_aid_meals', 0)),
            'tax_rate': float(getattr(getattr(tile, 'gov', None), 'tax_rate', 0.0)),
        }
        for actor in sorted(tile.agents, key=lambda a: a.id):
            if (not getattr(actor, 'alive', True) or getattr(actor, 'is_government', False)
                    or getattr(actor, 'is_corporation', False) or actor.id in seen):
                continue
            seen.add(actor.id)
            is_merchant = bool(getattr(actor, 'is_trader', False))
            is_holder = bool(getattr(actor, 'is_lord', False) or actor.id == owner_id)
            memberships = []
            if not is_merchant and not is_holder:
                memberships.append('households')
            if is_holder:
                memberships.append('holders')
            if is_merchant:
                memberships.append('merchants')
            for key in memberships:
                district['members'][key].append(actor.id)
            result['people'][str(actor.id)] = {
                'id': actor.id, 'tile': tile.name, 'memberships': memberships,
                'deficit': float(deficit_fraction(actor)), 'cash': float(actor.cash),
                'arrears': float(econ['arrears'].get(actor.id, {}).get('balance', 0.0)),
                'food': int(actor.inv_get(Goods.food, 0)),
                'is_striking': bool(getattr(actor, 'is_striking', False)),
            }
            if actor.id == owner_id:
                district['owner_id'] = actor.id
                district['private_maize'] = max(0, min(
                    int(econ['private_reserve_by_tile'].get(tile.name, 0)),
                    int(actor.inv_get(Goods.food, 0))))
        result['districts'][tile.name] = district
    # Preserve actual transaction receipts. A purchase is not a meal, and a
    # failed command never becomes a successful transaction in this view.
    result['grain_transactions'] = deepcopy(econ.get('grain_transactions', []))
    result['actions'] = deepcopy(state.get('actions_taken', []))
    return result


def _members(observation, district, community):
    return [observation['people'][str(pid)]
            for pid in district['members'][community]]


def material_inputs(observation, district, community):
    people = _members(observation, district, community)
    n = len(people)
    arrears = fsum(p['arrears'] for p in people)
    deficits = fsum(p['deficit'] for p in people)
    seized = sum(row['units'] for row in observation['grain_transactions']
                 if row['tile'] == district['id'] and row['kind'] == 'requisition')
    sold = sum(row['units'] for row in observation['grain_transactions']
               if row['tile'] == district['id'] and row['kind'] in ('public_buy', 'market_sale'))
    # These are explicit experimental pressure sources, not a loyalty score.
    # Seizure history persists. No support expiry or missed-rally penalty exists.
    sources = dict.fromkeys(CHANNELS, 0.0)
    if n and community == 'households':
        sources['food'] = deficits / n
        sources['arrears'] = 1.0 - exp(-arrears / (10.0 * n))
    elif n and community == 'holders':
        sources['property'] = 1.0 - exp(-seized / 20.0)
    elif n and community == 'merchants':
        # Only a merchant who also owns an actual warehouse is exposed to
        # held stock here. Do not invent exporter losses from unrelated sales.
        merchant_ids = {p['id'] for p in people}
        if (district['owner_id'] in merchant_ids
                and observation['grain_policy'] == 'hold'):
            sources['trade'] = 1.0 - exp(-district['private_maize'] / 20.0)
    return {
        'member_ids': [p['id'] for p in people], 'count': n,
        'underfed': sum(p['deficit'] > .05 for p in people),
        'deficit_total': deficits, 'arrears': arrears,
        'private_maize': district['private_maize'],
        'requisitioned': seized, 'sold': sold, 'sources': sources,
    }


def initial_graph(observation):
    nodes = {}
    for tile_id, district in observation['districts'].items():
        for community in COMMUNITIES:
            inputs = material_inputs(observation, district, community)
            node_id = f'{tile_id}:{community}'
            nodes[node_id] = {
                'id': node_id, 'tile': tile_id, 'community': community,
                'member_ids': inputs['member_ids'],
                'pressure': inputs['sources'].copy(),
            }
    edges = {}
    by_location = {}
    for district in observation['districts'].values():
        by_location.setdefault(district['name'], []).append(district['id'])
    for left, right in CONTACTS:
        for a in by_location.get(left, []):
            for b in by_location.get(right, []):
                for community in COMMUNITIES:
                    source, target = f'{a}:{community}', f'{b}:{community}'
                    for s, t in ((source, target), (target, source)):
                        key = f'{s}>{t}'
                        edges[key] = dict(source=s, target=t, weight=.6,
                                          basis='authored_association_contact')
    return nodes, edges


def propagate(nodes, edges, sources):
    """One synchronous bounded diffusion step, with reconstructible terms.

    A convex update keeps pressure in [0,1] at any node degree. Connections
    carry last turn's pressure; they do not instantaneously broadcast a shock
    across every district. Empty organizations cannot transmit pressure.
    """
    incoming = {node_id: [] for node_id in nodes}
    for edge_id, edge in sorted(edges.items()):
        source, target = edge['source'], edge['target']
        if source not in nodes or target not in nodes:
            raise ValueError('Network contact references an unknown organization.')
        weight = float(edge['weight'])
        if not isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError('Network contact weight must be between zero and one.')
        if nodes[source]['member_ids'] and nodes[target]['member_ids']:
            incoming[target].append((edge_id, source, weight))
    values, terms = {}, {}
    for node_id, node in sorted(nodes.items()):
        values[node_id], terms[node_id] = {}, {}
        budget = max(1.0, fsum(w for _, _, w in incoming[node_id]))
        for channel in CHANNELS:
            old = float(node['pressure'][channel])
            source = float(sources[node_id][channel])
            contact_terms = {
                edge_id: .25 * weight / budget * (nodes[peer]['pressure'][channel] - old)
                for edge_id, peer, weight in incoming[node_id]
            }
            material = .35 * (source - old)
            after = old + material + fsum(contact_terms.values())
            values[node_id][channel] = after if node['member_ids'] else 0.0
            terms[node_id][channel] = dict(
                before=old, material=material, contacts=contact_terms,
                empty_membership_adjustment=-after if not node['member_ids'] else 0.0,
                after=values[node_id][channel])
    return values, terms


def diagnostics(nodes, edges):
    adjacency = {key: set() for key, node in nodes.items() if node['member_ids']}
    for edge in edges.values():
        s, t = edge['source'], edge['target']
        if edge['weight'] > 0 and s in adjacency and t in adjacency:
            adjacency[s].add(t)
    unseen, components, reach = set(adjacency), [], {}
    while unseen:
        start = min(unseen)
        seen, todo = {start}, [start]
        while todo:
            current = todo.pop()
            neighbors = adjacency[current] | {n for n in adjacency if current in adjacency[n]}
            for peer in sorted(neighbors - seen):
                seen.add(peer)
                todo.append(peer)
        unseen -= seen
        components.append(sorted(seen))
    for start in sorted(adjacency):
        seen, todo = {start}, [start]
        while todo:
            current = todo.pop()
            for peer in sorted(adjacency[current] - seen):
                seen.add(peer)
                todo.append(peer)
        reach[start] = sorted(seen)
    return dict(components=components, reachable=reach,
                active_nodes=len(adjacency), contacts=sum(len(v) for v in adjacency.values()))


def advance(world):
    """Observe once after resolved scenario food/arrears, before politics."""
    if mode(world) == 'off':
        return
    state = world['scenario_state'][KEY]
    turn = int(world['turn'])
    if turn == state['last_turn']:
        return
    if turn != state['last_turn'] + 1:
        raise ValueError('Society observation needs one update per completed turn.')
    observation = observe(world)
    previous = state['observation']
    old_nodes = state['nodes']
    nodes, _ = initial_graph(observation)
    for node_id, node in nodes.items():
        if node_id in old_nodes:
            node['pressure'] = old_nodes[node_id]['pressure'].copy()
    # Migration may remove a district/node. Preserve the authored contact list
    # only where both organizations still exist; no fabricated replacement tie.
    edges = {key: edge for key, edge in state['edges'].items()
             if edge['source'] in nodes and edge['target'] in nodes}
    sources = {
        key: material_inputs(observation, observation['districts'][node['tile']],
                             node['community'])['sources']
        for key, node in nodes.items()
    }
    governing = state['mode'] == 'governing'
    if governing:
        from governing_collectives import augment, diffuse
        augment(world, observation)
        values, terms, sources = diffuse(nodes, edges, sources, observation)
    else:
        values, terms = propagate(nodes, edges, sources)
    for key in nodes:
        nodes[key]['pressure'] = values[key]
    state.update(last_turn=turn, observation=observation, nodes=nodes, edges=edges,
                 diagnostics=diagnostics(nodes, edges))
    _record(world, terms=terms)
    if governing:
        for key in state['history'][-1]['inputs']:
            state['history'][-1]['inputs'][key]['sources'] = sources[key]
        from governing_collectives import plan
        plan(world, previous=previous)


def prepare_turn(world, turn):
    """Consume yesterday's coordination before today's economic work."""
    if is_governing(world):
        from governing_collectives import begin_turn
        begin_turn(world, turn)


def _record(world, opening=False, terms=None):
    state = world['scenario_state'][KEY]
    obs = state['observation']
    row = {
        'id': f'governing-observation:{obs["turn"]}', 'turn': obs['turn'],
        'opening': opening, 'inputs': {
            key: material_inputs(obs, obs['districts'][node['tile']], node['community'])
            for key, node in state['nodes'].items()},
        'pressure_terms': terms or {},
    }
    # A separate observation journal avoids advancing the authoritative trace
    # clock: legacy transaction operation IDs sometimes depend on that clock.
    state['history'].append(row)
    del state['history'][:-HISTORY_LIMIT]


def project(world):
    """Plain-English summaries, using only the frozen observation."""
    if mode(world) == 'off':
        return None
    state = world['scenario_state'][KEY]
    obs = state['observation']
    summaries = []
    for community, title in COMMUNITIES.items():
        ids = sorted({pid for d in obs['districts'].values() for pid in d['members'][community]})
        people = [obs['people'][str(pid)] for pid in ids]
        rows = [material_inputs(obs, d, community) for d in obs['districts'].values()]
        underfed = sum(row['underfed'] for row in rows)
        arrears = fsum(row['arrears'] for row in rows)
        maize = sum(row['private_maize'] for row in rows)
        seized = sum(row['requisitioned'] for row in rows)
        if not people:
            concern, explanation = 'No current members', 'No agents currently match this community.'
        elif community == 'households':
            concern = f'{underfed}/{len(ids)} underfed; {arrears:.1f} unpaid taxes'
            explanation = ('Food and tax pressure can unite households. ' if underfed or arrears else
                           'No current food or arrears demand. ')
            explanation += 'Relief helps only when food reaches people.'
        elif community == 'holders':
            concern = f'{maize} maize held; {seized} seized so far'
            explanation = ('Seizure threatens owners\' control of their stocks.' if seized else
                           'Buying pays owners; seizure takes stocks without payment.')
        else:
            concern = ('Private grain sales are open' if obs['grain_policy'] == 'open' else
                       'Private warehouse sales are held')
            explanation = 'Opening sales allows trade; households still need money to buy.'
        summaries.append(dict(id=community, title=title, count=len(ids), member_ids=ids,
                              concern=concern, explanation=explanation,
                              underfed=underfed, arrears=arrears,
                              private_maize=maize, requisitioned=seized))
    result = dict(turn=obs['turn'], mode=state['mode'], communities=summaries,
                journal_id=state['history'][-1]['id'],
                diagnostic='Experimental contacts; pressure does not change petitions or strikes.',
                public_maize=obs['public_maize'], treasury=obs['treasury'])
    if state['mode'] == 'governing':
        from governing_collectives import presentation
        result.update(presentation(world))
    return result

"""Autonomous, material-based collective action for the governing experiment.

The graph plans participation; the existing production flag executes it next
turn. No inventories, accounts, legitimacy or production multipliers live here.
"""

from hashlib import sha256
from math import exp, fsum

from goods import Goods
from nutrition import basic_food_units, deficit_fraction
from strike_status import enable, has_source, set_striking, source


def _state(world):
    return world['scenario_state']['governing_network']


def _nation(world):
    return next(n for n in world['nations'] if n.name == 'Egypt')


def _fraction(pid, purpose):
    # Stable personal differences without consuming either gameplay RNG.
    return int.from_bytes(sha256(f'{pid}:{purpose}'.encode()).digest()[:4], 'big') / (2**32 - 1)


def augment(world, observation):
    for tile in _nation(world).tiles:
        tile._governing_strike_sources = True
        price = max(.25, float(tile.recipes.get(Goods.food, {}).get('price', 1.)))
        for person in tile.agents:
            row = observation['people'].get(str(person.id))
            if row is None:
                continue
            enable(person)
            child = bool(getattr(person, 'is_native_child', False)
                         and person.age(int(world['turn'])) < 14)
            employer = getattr(person, 'employer', None)
            row.update(
                adult=not child, employer_id=getattr(employer, 'id', None),
                food_price=price, food_need=basic_food_units(person),
                risk=float(getattr(person, 'risk_tolerance', .5)),
                fear=min(1., max(getattr(person, 'memory', {}).get('mem_casualties', [])[-3:] or [0.])),
                reserve=float(getattr(person, 'energy_reserve_kcal', 0.)),
                can_withhold=bool(not child and not getattr(person, 'military_unit_id', None) and (employer is not None or
                    getattr(person, 'output', Goods.none) not in (Goods.none, Goods.gov))),
                in_revolt=bool(getattr(person, 'in_revolt', False)))


def initialize(world):
    state = _state(world)
    augment(world, state['observation'])
    # A real fifth Egyptian district is present in the campaign. Give it an
    # explicit contact rather than silently treating its residents as isolated.
    by_name = {d['name']: key for key, d in state['observation']['districts'].items()}
    if 'Nile Valley' in by_name and 'Cairo' in by_name:
        for community in ('households', 'holders', 'merchants'):
            a, b = (f'{by_name[name]}:{community}' for name in ('Nile Valley', 'Cairo'))
            for s, t in ((a, b), (b, a)):
                state['edges'][f'{s}>{t}'] = dict(source=s, target=t, weight=.6,
                                                    basis='authored_association_contact')
    for tile in _nation(world).tiles:
        tile._governing_strike_sources = True
        for person in tile.agents:
            if not getattr(person, 'is_corporation', False) and not getattr(person, 'is_government', False):
                enable(person)
        a, b = f'{tile.name}:households', f'{tile.name}:holders'
        for s, t in ((a, b), (b, a)):
            state['edges'][f'claims:{s}>{t}'] = dict(
                source=s, target=t, weight=.6, basis='competing_grain_claim')
    state.update(organizations={}, pending={}, active={}, settlements={}, receipts=[],
                 events=[], last_applied_turn=int(world['turn']))
    from governing_network import diagnostics
    state['diagnostics'] = diagnostics(state['nodes'], state['edges'])
    plan(world, previous=state['observation'])


def diffuse(nodes, edges, sources, observation):
    from governing_network import propagate
    sources = {key: row.copy() for key, row in sources.items()}
    for key, node in nodes.items():
        if node['community'] == 'holders':
            seized = fsum(row['units'] * .9 ** max(0, observation['turn'] - row['turn'])
                         for row in observation['grain_transactions']
                         if row['tile'] == node['tile'] and row['kind'] == 'requisition')
            sources[key]['property'] = 1. - exp(-seized / 20.)
    friendly = {key: edge for key, edge in edges.items()
                if edge['basis'] == 'authored_association_contact'}
    values, terms = propagate(nodes, friendly, sources)
    opposing = {}
    for edge_id, edge in sorted(edges.items()):
        if edge['basis'] != 'competing_grain_claim':
            continue
        sender, receiver = nodes[edge['source']], nodes[edge['target']]
        if not sender['member_ids'] or not receiver['member_ids']:
            continue
        opposing.setdefault(edge['target'], []).append((edge_id, edge, sender))
    for node_id, incoming in opposing.items():
        budget = max(1., fsum(e['weight'] for _, e, _ in incoming))
        channels = ('food', 'arrears') if nodes[node_id]['community'] == 'households' else ('property',)
        for channel in channels:
            contributions = {}
            for edge_id, edge, sender in incoming:
                counter = (sender['pressure']['property'] if sender['community'] == 'holders'
                           else max(sender['pressure']['food'], sender['pressure']['arrears']))
                contributions[edge_id] = -.10 * edge['weight'] / budget * counter * nodes[node_id]['pressure'][channel]
            change = fsum(contributions.values())
            values[node_id][channel] += change
            terms[node_id][channel].update(opposition=contributions, after=values[node_id][channel])
    return values, terms, sources


def _grievance(person):
    return min(1., .7 * person['deficit'] + .3 * (1. - exp(-person['arrears'] / 5.)))


def _endure(person):
    return (person['food'] >= 2 or person['cash'] >= person['food_price'] * 2
            or person['reserve'] >= 10000 and person['deficit'] < .5)


def _settled(state, tile_id, person, turn):
    settlement = state['settlements'].get(tile_id, {})
    if settlement.get('kind') == 'repression' and turn <= settlement['until']:
        return True
    accepted = settlement.get('accepted', {}).get(str(person['id']))
    return bool(accepted and turn <= settlement['until']
                and person['deficit'] <= accepted['deficit'] + .25
                and person['arrears'] <= accepted['arrears'] + 1.)


def plan(world, previous):
    state = _state(world)
    obs, pending = state['observation'], {}
    turn = int(world['turn'])
    decisions = {}
    old_pending = state['pending']
    by_tile = {tile.name: tile for tile in _nation(world).tiles}
    for tile_id, district in obs['districts'].items():
        node_id = f'{tile_id}:households'
        node = state['nodes'][node_id]
        people = [obs['people'][str(pid)] for pid in node['member_ids']]
        previous_org = state['organizations'].get(node_id)
        contact_weight = fsum(e['weight'] for e in state['edges'].values()
                              if e['target'] == node_id and e['basis'] == 'authored_association_contact'
                              and state['nodes'][e['source']]['member_ids'])
        capacity = .18 + .65 * (1. - exp(-contact_weight))
        mean_grievance = fsum(_grievance(p) for p in people) / max(1, len(people))
        old = previous_org or dict(cohesion=capacity, delivery_trust=.5)
        cohesion = .85 * old['cohesion'] + .15 * capacity
        trust = .9 * old['delivery_trust'] + .1 * (1. - mean_grievance)
        state['organizations'][node_id] = dict(cohesion=cohesion, delivery_trust=trust)
        field = max(node['pressure']['food'], node['pressure']['arrears'])
        petitions, strikes, individual = [], [], {}
        for person in people:
            grievance = _grievance(person)
            demand = 'food' if .7 * person['deficit'] >= grievance - .7 * person['deficit'] else 'arrears'
            petition_score = .55 * grievance + .35 * field + .20 * cohesion
            petition_threshold = .18 + .55 * _fraction(person['id'], 'petition')
            petition = bool(person['adult'] and grievance > .035 and petition_score >= petition_threshold)
            strike_score = .45 * grievance + .40 * field + .30 * cohesion - .15 * trust - .15 * person['fear']
            strike_threshold = .42 + .30 * _fraction(person['id'], 'strike') - .1 * person['risk']
            settled = _settled(state, tile_id, person, turn + 1)
            strike = bool(petition and person['can_withhold'] and not person['in_revolt']
                          and _endure(person) and not settled and strike_score >= strike_threshold
                          and not (demand == 'food' and person['food'] >= person['food_need']))
            if petition:
                petitions.append(person['id'])
            if strike:
                strikes.append(person['id'])
            individual[str(person['id'])] = dict(
                grievance=grievance, demand=demand, petition_score=petition_score,
                petition_threshold=petition_threshold, strike_score=strike_score,
                strike_threshold=strike_threshold, can_endure=_endure(person), settled=settled,
                repression_memory=person['fear'],
                petition=petition, strike=strike)
        row = dict(effective_turn=turn + 1, petition_ids=petitions, strike_ids=strikes,
                   individual=individual, observation_id=state['history'][-1]['id'],
                   field=field, cohesion=cohesion, delivery_trust=trust)
        old_ids = old_pending.get(tile_id, {})
        changed = (old_ids.get('petition_ids') != petitions or old_ids.get('strike_ids') != strikes)
        if changed or petitions or strikes:
            tile = by_tile[tile_id]
            recorder = getattr(tile, '_run_trace', None)
            intake_events = getattr(recorder, '_latest_food_intake_events', {})
            causes = sorted({intake_events[str(pid)] for pid in petitions if str(pid) in intake_events})
            row['trace_event_id'] = _trace(
                tile, turn, 'network_collective_planned',
                before=len(old_ids.get('strike_ids', [])), after=len(strikes),
                inputs=dict(observation_id=row['observation_id'], effective_turn=turn + 1,
                            petition_ids=petitions, strike_ids=strikes, individual=individual,
                            pressure_terms=state['history'][-1]['pressure_terms'].get(node_id, {}),
                            cohesion=cohesion, delivery_trust=trust,
                            local_material_sources=state['history'][-1]['inputs'][node_id]['sources']),
                causes=causes)
        else:
            row['trace_event_id'] = old_ids.get('trace_event_id')
        pending[tile_id] = row
        decisions[tile_id] = {key: value for key, value in row.items() if key != 'individual'}
        # A petition is a demand now. Only the withholding intent waits for the
        # next economic turn, so no already-completed work is removed.
        active = state['active'].setdefault(tile_id, dict(strike_ids=[], turn=turn))
        active['petition_ids'] = petitions
    state['pending'] = pending
    state['history'][-1]['collective_decisions'] = decisions
    state['history'][-1]['policy_actions'] = obs['actions'][len(previous.get('actions', [])):]
    for tile in _nation(world).tiles:
        sync_counts(world, tile)
        obs['districts'][tile.name]['petitioners'] = world['scenario_state']['political_economy']['collective_by_tile'][tile.name]['petitioners']


def _trace(tile, turn, kind, *, before, after, inputs, causes=None):
    from collective_trace_clock import attach_clock
    clock = getattr(tile, '_collective_trace_clock', None)
    if clock is None:
        clock = attach_clock([tile])
    clock['turn'], clock['phase'] = turn, 'network_coordination'
    from run_trace import emit
    return emit(tile, kind=kind, record_class='decision', phase='network_coordination',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='politics.network_participation', unit='people',
                before=before, after=after, inputs=inputs, cause_event_ids=causes or None)


def _strike_gate(world, tile, person, intent, turn):
    state = _state(world)
    info = dict(state['observation']['people'][str(person.id)])
    info.update(cash=float(person.cash), food=int(person.inv_get(Goods.food, 0)),
                deficit=deficit_fraction(person), reserve=float(getattr(person, 'energy_reserve_kcal', 0.)))
    arrears = world['scenario_state']['political_economy']['arrears'].get(person.id, {}).get('balance', 0.)
    info['arrears'] = arrears
    if info['deficit'] <= .05 and arrears <= 0:
        return 'material_demand_resolved'
    if _settled(state, tile.name, info, turn):
        return 'funded_settlement_or_repression'
    demand = intent['individual'][str(person.id)]['demand']
    if demand == 'arrears' and arrears <= 0:
        return 'tax_arrears_written_off'
    if demand == 'food' and getattr(person, 'emergency_food_units', 0) >= basic_food_units(person):
        return 'funded_next_meal_ration'
    if demand == 'food' and info['food'] >= info['food_need']:
        return 'actual_food_stock_for_next_meal'
    if getattr(person, 'in_revolt', False):
        return 'already_in_another_collective_action'
    if getattr(person, 'military_unit_id', None):
        return 'no_longer_available_for_civilian_work'
    if (getattr(person, 'employer', None) is None
            and getattr(person, 'output', Goods.none) in (Goods.none, Goods.gov)):
        return 'no_longer_has_work_to_withhold'
    if not _endure(info):
        return 'cannot_afford_to_withhold_work'
    return None


def begin_turn(world, turn):
    state = _state(world)
    if turn <= state['last_applied_turn']:
        return
    if turn != state['last_applied_turn'] + 1 or turn != state['last_turn'] + 1:
        raise ValueError('Network participation must consume the preceding turn observation once.')
    from scenario_political_economy import _households
    nation = _nation(world)
    previous_active = state['active']
    # Clear only this layer's previous sources, including people who migrated
    # out of the country. Other workplace/movement sources remain authoritative.
    for tile in world['tiles']:
        for person in tile.agents:
            for origin in list(getattr(person, '_strike_sources', {})):
                if origin.startswith('network:'):
                    set_striking(person, origin, False, region=tile)
    active = {}
    for tile in nation.tiles:
        tile._governing_strike_sources = True
        intent = state['pending'].get(tile.name, {})
        people = {a.id: a for a in _households(tile)}
        petitions, strikes, reasons = [], [], {}
        for pid in intent.get('petition_ids', []):
            person = people.get(pid)
            if person is None:
                reasons[str(pid)] = 'no_longer_a_local_member'
                continue
            enable(person)
            arrears = world['scenario_state']['political_economy']['arrears'].get(pid, {}).get('balance', 0.)
            if deficit_fraction(person) <= .05 and arrears <= 0:
                reasons[str(pid)] = 'material_demand_resolved'
                continue
            petitions.append(pid)
            if pid not in intent.get('strike_ids', []):
                continue
            reason = _strike_gate(world, tile, person, intent, turn)
            if reason:
                reasons[str(pid)] = reason
                continue
            set_striking(person, source('network', tile), True, region=tile)
            strikes.append(pid)
        active[tile.name] = dict(petition_ids=petitions, strike_ids=strikes, turn=turn)
        before_ids = previous_active.get(tile.name, {}).get('strike_ids', [])
        event_id = None
        if strikes or before_ids or reasons:
            event_id = _trace(tile, turn, 'network_participation_consumed', before=len(before_ids), after=len(strikes),
                          inputs=dict(observation_id=intent.get('observation_id'),
                                      effective_turn=turn, petition_ids=petitions, strike_ids=strikes,
                                      declined=reasons, recruitment_basis='frozen_network_and_material_conditions'),
                          causes=[intent['trace_event_id']] if intent.get('trace_event_id') else None)
        # Production already links to this existing collective-log interface.
        if strikes:
            if not hasattr(tile, 'collective_log'):
                tile.collective_log = []
            row = dict(id=f'{tile.name}:network:{turn}', turn=turn,
                       kind='network_participation', region=tile.name,
                       firm_id=0, firm_name='Household associations',
                       strike_id=source('network', tile), scope='community',
                       message=f'{len(strikes)} residents joined the network walkout.',
                       trace_event_id=event_id, facts={'participant_ids': strikes})
            from collective_trace_clock import stamp
            stamp(tile, row)
            tile.collective_log.append(row)
        if before_ids != strikes or reasons:
            state['events'].append(dict(turn=turn, tile=tile.name, kind='participation',
                                    previous_strike_ids=list(before_ids),
                                    petition_ids=petitions, strike_ids=strikes, reasons=reasons,
                                    observation_id=intent.get('observation_id'), trace_event_id=event_id))
    state['active'] = active
    state['last_applied_turn'] = turn
    del state['events'][:-120]
    for tile in nation.tiles:
        sync_counts(world, tile)


def active_petitioners(world, tile):
    ids = set(_state(world)['active'].get(tile.name, {}).get('petition_ids', []))
    return [a for a in tile.agents if a.id in ids and getattr(a, 'alive', True)]


def sync_counts(world, tile):
    from scenario_political_economy import _households
    row = world['scenario_state']['political_economy']['collective_by_tile'][tile.name]
    people = _households(tile)
    row['petitioners'] = len(active_petitioners(world, tile))
    row['strikers'] = sum(bool(getattr(a, 'is_striking', False)) for a in people)
    row['support'] = 1. - exp(-row['petitioners'] / max(1, len(people)))


def settlement_acceptors(world, tile, recipients, grant, wage_changes):
    state = _state(world)
    org = state['organizations'].get(f'{tile.name}:households', {})
    accepted = {}
    price = max(.25, float(tile.recipes.get(Goods.food, {}).get('price', 1.)))
    for person in recipients:
        deficit = deficit_fraction(person)
        arrears = world['scenario_state']['political_economy']['arrears'].get(person.id, {}).get('balance', 0.)
        employer = getattr(person, 'employer', None)
        wage_gain = wage_changes.get(getattr(employer, 'id', None), 0.)
        benefit = grant / price + wage_gain / price
        burden = max(.25, min(2., deficit * 4. + arrears / price * .1))
        score = .7 * min(1., benefit / burden) + .3 * org.get('delivery_trust', .5)
        if grant > 0 and score >= .30 + .30 * _fraction(person.id, 'settlement'):
            accepted[str(person.id)] = dict(deficit=deficit, arrears=arrears, paid=grant,
                                            score=score, wage_offer_gain=wage_gain)
    return accepted


def record_settlement(world, tile, accepted, paid, recipients):
    state = _state(world)
    state['settlements'][tile.name] = dict(kind='paid_bargain', until=int(world['turn']) + 3,
                                           accepted=accepted, paid=float(paid))
    state['receipts'].append(dict(turn=int(world['turn']), tile=tile.name, kind='worker_bargain',
                                  paid=float(paid), recipient_ids=[a.id for a in recipients],
                                  accepted_ids=[int(pid) for pid in accepted]))
    del state['receipts'][:-48]
    active = state['active'].get(tile.name, {})
    active['strike_ids'] = [pid for pid in active.get('strike_ids', []) if str(pid) not in accepted]


def record_repression(world, tile, injured):
    _state(world)['settlements'][tile.name] = dict(kind='repression', until=int(world['turn']) + 2,
                                                  injured=int(injured), accepted={})
    _state(world)['active'].get(tile.name, {})['strike_ids'] = []


def presentation(world):
    state = _state(world)
    obs = state['observation']
    groups = {'food': set(), 'arrears': set()}
    strikers = set()
    locations = []
    live = {tile.name: {person.id for person in tile.agents
                       if getattr(person, 'alive', True) and has_source(person, source('network', tile))}
            for tile in _nation(world).tiles}
    tiles = {tile.name: tile for tile in _nation(world).tiles}
    for tile_id, intent in state['pending'].items():
        for pid in intent['petition_ids']:
            person = obs['people'][str(pid)]
            if person['deficit'] > .05:
                groups['food'].add(pid)
            if person['arrears'] > 0:
                groups['arrears'].add(pid)
        current = state['active'].get(tile_id, {})
        current_strikers = sorted(live.get(tile_id, set()))
        strikers.update(current_strikers)
        people = {a.id: a for a in tiles[tile_id].agents if getattr(a, 'alive', True)}
        planned = sum(pid in people and _strike_gate(world, tiles[tile_id], people[pid], intent,
                                                     int(world['turn']) + 1) is None
                      for pid in intent['strike_ids'])
        locations.append(dict(tile=tile_id, name=obs['districts'][tile_id]['name'],
                              petitioners=len(intent['petition_ids']),
                              striking=len(current_strikers), planned_strikers=planned))
    disputes = []
    for kind in ('food', 'arrears'):
        if not groups[kind]:
            continue
        by_tile = {}
        for pid in groups[kind]:
            key = obs['people'][str(pid)]['tile']
            by_tile[key] = by_tile.get(key, 0) + 1
        focus = max(sorted(by_tile), key=lambda key: by_tile[key])
        disputes.append(dict(id=kind, title='Food access petition' if kind == 'food' else 'Unpaid tax petition',
                             count=len(groups[kind]), tile=focus, name=obs['districts'][focus]['name'],
                             striking=len(groups[kind] & strikers), member_ids=sorted(groups[kind])))
    recent = 'Contacts help residents act together. Petitions do not stop work.'
    event = state['events'][-1] if state['events'] else None
    receipt = state['receipts'][-1] if state['receipts'] else None
    if receipt and (event is None or receipt['turn'] >= event['turn']):
        place = obs['districts'].get(receipt['tile'], {}).get('name', receipt['tile'])
        recent = (f'{receipt["paid"]:.1f} paid in {place}; '
                  f'{len(receipt["accepted_ids"])} people accepted a temporary ceasefire.')
    elif event:
        from collections import Counter
        place = obs['districts'].get(event['tile'], {}).get('name', event['tile'])
        reasons = Counter(event['reasons'].values())
        meals = reasons['funded_next_meal_ration'] + reasons['actual_food_stock_for_next_meal']
        if meals:
            recent = f'{meals} people in {place} have a next meal and skipped the planned walkout.'
        elif reasons['tax_arrears_written_off'] or reasons['material_demand_resolved']:
            count = reasons['tax_arrears_written_off'] + reasons['material_demand_resolved']
            recent = f'{count} people in {place} no longer have the demand that prompted their action.'
        elif event['strike_ids']:
            recent = (f'{len(event["strike_ids"])} people in {place} joined a walkout: '
                      'unmet needs, shared contacts and enough resources to hold out.')
        elif reasons['cannot_afford_to_withhold_work']:
            recent = f'People in {place} still have demands but cannot afford to stop work.'
        else:
            recent = f'The network walkout in {place} stopped; other disputes can continue.'
    return dict(disputes=disputes, locations=locations, recent_explanation=recent,
                organized_people=len(groups['food'] | groups['arrears']),
                network_strikers=len(strikers),
                diagnostic='Petitions and next-turn strikes follow real conditions and organization.')

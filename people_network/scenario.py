"""Authored fixture loading and validation without economic world construction."""
from copy import deepcopy
from pathlib import Path
import json
import math
import random
from .model import CHANNELS, VERSION, Session, digest

SCENARIO = Path(__file__).resolve().parents[1] / 'scenarios/people_network/broken_crossing.json'


def validate(state):
    if state['mode'] != 'network_lab' or state['version'] != VERSION:
        raise ValueError('Unsupported laboratory mode or rules version')
    people, rules = state['people'], state['rules']
    if len(people) != 32 or not set(('player', 'rival')).issubset(people):
        raise ValueError('This scenario requires 32 unique people including both leaders')
    if set(state['ap']) != {'player', 'rival'} or any(v not in (0, 1, 2) for v in state['ap'].values()):
        raise ValueError('Invalid action budget')
    if state['round'] < 0 or state['phase'] != 'decision':
        raise ValueError('Saves require a decision boundary')
    if state['government']['officeholder'] not in ('player', 'rival'):
        raise ValueError('Invalid officeholder')
    council = state['government']['council']
    if len(council) != 9 or len(set(council)) != 9 or not set(council).issubset(people):
        raise ValueError('Council must contain nine distinct people')
    for pid, p in people.items():
        if p['location'] not in state['locations'] or p['allegiance'] not in ('player', 'rival', None):
            raise ValueError(f'Invalid person {pid}')
        for key in ('pressure', 'alignment'):
            if set(p[key]) != set(CHANNELS) or any(not math.isfinite(v) or not 0 <= v <= 1 for v in p[key].values()):
                raise ValueError(f'Invalid {key}: {pid}')
        if set(p['base_alignment'])!=set(CHANNELS) or any(not math.isfinite(v) or not 0<=v<=1 for v in p['base_alignment'].values()):
            raise ValueError('Invalid underlying interests')
        if not isinstance(p['active'], bool):
            raise ValueError('Person availability must be boolean')
        if p['task'] not in ('upstream', 'market', None):
            raise ValueError('Invalid task commitment')
    for eid, e in state['edges'].items():
        if eid != f"{e['source']}>{e['target']}" or set(e['trust']) != {'governing','organizing'}:
            raise ValueError('Edges need unique canonical endpoints and both trust contexts')
        if e['source'] not in people or e['target'] not in people or e['source'] == e['target']:
            raise ValueError('Invalid edge endpoints')
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in [*e['trust'].values(), e['capacity'], e['available']]):
            raise ValueError('Invalid conductance')
    for key in ('step','receiving_budget','anchor','decay','competition','source_budget','output_budget',
                'appeal','self_source','entry','margin_entry','margin_exit','margin_switch',
                'task_entry','task_exit','contested_floor','contested_band'):
        if not math.isfinite(rules[key]) or rules[key] < 0:
            raise ValueError('Dynamics coefficients must be finite and nonnegative')
    if rules['step'] <= 0 or rules['receiving_budget'] <= 0 or rules['anchor'] < 0 or rules['decay'] < 0:
        raise ValueError('Invalid dynamics coefficients')
    if rules['step'] * (rules['receiving_budget'] + rules['anchor'] + rules['decay'] + rules.get('competition',0.)) > 1:
        raise ValueError('Unstable dynamics configuration')
    allocations=state['government']['allocations']
    if set(allocations)!=set(state['organizations']) or any(type(v) is not int or v<0 for v in allocations.values()) or sum(allocations.values())!=4 or state['government']['budget_total']!=4:
        raise ValueError('Public allocations must conserve four integer service shares')
    if any(type(p['fatigue']) is not int or not 0<=p['fatigue']<=rules['rally_limit'] or type(p['rest_until']) is not int for p in people.values()):
        raise ValueError('Invalid organizing strain/rest state')
    if any(type(rules[k]) is not int or rules[k]<1 for k in ('rally_limit','rally_rest','agreement_grace')):
        raise ValueError('Invalid coalition timing rules')
    if not 0<rules['group_response']<=1 or not 0<=rules['group_influence']<=1 or not 0<=rules['agreement_influence']<=1:
        raise ValueError('Invalid group response')
    seen=set()
    for a in state['agreements']:
        key=(a['leader'],a['group'])
        if key in seen or a['leader'] not in ('player','rival') or a['group'] not in state['organizations']:
            raise ValueError('Invalid or duplicate group agreement')
        seen.add(key)
        if a['status'] not in ('provisional','suspended','honored','breached','repairing') or min(a['office_rounds'],a['met_streak'],a['breaches'])<0:
            raise ValueError('Invalid agreement status/timer')
    for org in state['organizations'].values():
        if type(org['funding_need']) is not int or not 1<=org['funding_need']<=4 or org['location'] not in state['locations']:
            raise ValueError('Invalid group demand')
        if set(org['standing'])!={'player','rival'} or set(org['band'])!={'player','rival'} or any(v not in ('watching','angry','warming','satisfied') for v in org['band'].values()):
            raise ValueError('Invalid group delivery state')
        if any(not math.isfinite(v) or not -1<=v<=1 for v in org['standing'].values()):
            raise ValueError('Invalid delivery record')
        if len(org['members']) != len(set(org['members'])) or not set(org['members']).issubset(people):
            raise ValueError('Invalid membership')
        if org['coordinator'] is not None and org['coordinator'] not in org['members']:
            raise ValueError('Invalid coordinator')
    for invite in state['invitations']:
        if invite['sender'] not in people or invite['target'] not in people or invite['channel'] not in CHANNELS:
            raise ValueError('Invalid invitation')
    for pid, source in state['organizers'].items():
        if pid != source['person'] or source['issuer'] not in ('player','rival'):
            raise ValueError('Invalid organizer owner')
        if source['person'] not in people or source['channel'] not in CHANNELS:
            raise ValueError('Invalid organizer')
    for promise in state['promises']:
        if promise['term'] not in ('liaison','upstream','market') or promise['status'] not in ('pending','fulfilled','broken'):
            raise ValueError('Invalid promise state')
        if promise['beneficiary'] not in people or promise['issuer'] not in ('player', 'rival'):
            raise ValueError('Invalid promise')


def new_session(start='governing', seed=4243):
    if start not in ('governing', 'displaced'):
        raise ValueError('Choose governing or displaced')
    data = json.loads(SCENARIO.read_text())
    state = deepcopy(data['state'])
    from .terrain import load_terrain
    state.update(scenario_id=data['id'], terrain_digest=digest(load_terrain()), seed=seed, start=start, content_digest=digest(data), version=VERSION,
                 mode='network_lab', phase='decision', round=0, event_sequence=0,
                 graph_revision=0, ap={'player': 2, 'rival': 2}, invitations=[], organizers={},
                 promises=[], actions=[], pending_actions=[], last_change={},
                 project=dict(package=None, streak=0, deadline=None, complete=False,
                              maintenance_misses=0, completed_round=None),
                 government=dict(officeholder='player' if start == 'governing' else 'rival',
                                 council=data['council'], challenge=None, cooldown_until=-1,
                                 support_streak={'player': 0, 'rival': 0}, liaisons={}))
    rng = random.Random(seed)
    for pid, p in sorted(state['people'].items()):
        p.update(active=True, task=None, allegiance=p.pop('initial_allegiance'), last_review=-2,
                 task_since=-2, contested=False)
        # Seed changes only a bounded declared initial disposition perturbation.
        for k in CHANNELS:
            p['pressure'][k] = max(0, min(1, p['pressure'][k] + rng.uniform(-.012, .012)))
    if start == 'displaced':
        for p in state['people'].values():
            p['pressure']['player'], p['pressure']['rival'] = p['pressure']['rival'], p['pressure']['player']
            p['alignment']['player'], p['alignment']['rival'] = p['alignment']['rival'], p['alignment']['player']
            if p['allegiance']:
                p['allegiance'] = 'rival' if p['allegiance'] == 'player' else 'player'
    for leader in ('player', 'rival'):
        p = state['people'][leader]
        p['allegiance'] = leader
        p['alignment'][leader], p['alignment']['rival' if leader == 'player' else 'player'] = 1., 0.
        p['pressure'][leader], p['pressure']['rival' if leader == 'player' else 'player'] = .92, .08
    from .coalitions import initialize
    initialize(state)
    validate(state)
    return Session(state, deepcopy(state))

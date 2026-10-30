"""Authoritative laboratory commands and deterministic round resolution."""
from copy import deepcopy
import math
from .graph import Graph
from .model import CANDIDATES, CHANNELS, state_digest
from .dynamics import advance as pressure_step, summary, contested
from .coalitions import (advance_demands, rest_and_strain, failed_conditions, agreement_offer, pledge_text)
from . import patronage


class CommandError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise CommandError(message)


def command(session, issuer, kind, _preview=False, **params):
    """Validate completely before spending attention or mutating the session."""
    s, people = session.state, session.state['people']
    _require(issuer in CANDIDATES, 'Unknown political leader')
    _require(s['ap'][issuer] > 0, 'No political actions left this round')
    target = params.get('target', issuer)
    channel = params.get('channel', issuer)
    _require(target in people, 'Unknown person')
    _require(people[target].get('active',True), 'This person is currently unavailable')
    graph = Graph(s)
    if kind in patronage.KINDS:
        patronage.check(s,issuer,kind,params,_require)
    elif kind in ('approach', 'organize'):
        _require(channel in CHANNELS, 'Unknown candidate or task')
        if kind == 'approach':
            _require(target in graph.contacts(issuer), 'An appeal needs an available direct contact')
            _require(not any(i['sender'] == issuer and i['target'] == target and i['channel'] == channel
                             for i in s['invitations']), 'An equivalent appeal is already in transit')
        else:
            _require(people[target]['fatigue']<=1 and s['round']>=people[target]['rest_until'],
                     'This volunteer needs a break from politics before rallying again')
            _require(not failed_conditions(s,target,issuer), 'Honor your group agreement before asking this member to rally')
            _require(target == issuer or people[target]['allegiance'] == issuer,
                     'This organizer has not joined your coalition')
            _require(not any(o['person'] == target for o in s['organizers'].values()),
                     'Already organizing; release them first')
    elif kind == 'fund':
        group,donor=params.get('group'),params.get('donor')
        _require(s['government']['officeholder']==issuer,'Only the government can move public budget shares')
        _require(group in s['organizations'] and donor in s['organizations'] and group!=donor,'Choose two different groups')
        _require(s['government']['allocations'][donor]>0,'The donor group has no share to move')
    elif kind == 'agreement':
        oid=params.get('group')
        _require(oid in s['organizations'],'Unknown organization')
        coordinator=s['organizations'][oid]['coordinator']
        _require(coordinator in graph.contacts(issuer),'You need an available contact with the group coordinator')
        _require(not any(a['group']==oid and a['leader']==issuer for a in s['agreements']),
                 'This agreement already exists; deliver its terms to restore trust')
    elif kind == 'release':
        _require(target in s['organizers'] and s['organizers'][target]['issuer'] == issuer,
                 'No organizer to release')
    elif kind == 'introduce':
        other = params.get('other')
        _require(other in people and other != target and other != issuer and target != issuer,
                 'Choose two other people')
        _require(target in graph.contacts(issuer) and other in graph.contacts(issuer),
                 'Both people must know the introducer')
        _require(people[target]['allegiance'] == issuer and people[other]['allegiance'] == issuer,
                 'Both people must agree through your coalition')
        _require(f'{target}>{other}' not in s['edges'], 'These people already have a channel')
    elif kind in ('adopt', 'appoint'):
        _require(s['government']['officeholder'] == issuer, 'Only the incumbent has this power')
        if kind == 'adopt':
            _require(not patronage.enabled(s) or not s['patronage']['contract'] or s['patronage']['contract']['status']=='cancelled',
                     'An active contract fixes the work plan; cancel before changing it')
            _require(channel in ('upstream', 'market'), 'Choose a repair package')
            _require(not s['project']['complete'], 'The crossing is complete; maintain it')
            _require(s['project']['package'] != channel, 'This package is already active')
        else:
            _require(target not in s['government']['liaisons'], 'Already appointed')
            _require(len(s['government']['liaisons']) < 2, 'Both liaison posts are filled')
            _require(people[target]['allegiance'] == issuer, 'A liaison must agree to join your coalition')
    elif kind == 'promise':
        term = params.get('term')
        _require(term in ('liaison', 'upstream', 'market'), 'Unknown promise term')
        _require(target in graph.contacts(issuer), 'Negotiate with an existing contact')
        live = [p for p in s['promises'] if p['issuer'] == issuer and p['status'] == 'pending']
        _require(not any(p['beneficiary'] == target and p['term'] == term for p in live),
                 'Equivalent promise already exists')
        if term == 'liaison':
            reserved = {p['beneficiary'] for p in live if p['term'] == 'liaison'} | set(s['government']['liaisons'])
            _require(target not in reserved and len(reserved) < 2, 'No unpromised liaison post remains')
        else:
            _require(not any(p['term'] in ('upstream', 'market') and p['term'] != term for p in live),
                     'An incompatible package has already been promised; renounce it first')
    elif kind == 'renounce':
        _require(any(p['id'] == params.get('promise') and p['issuer'] == issuer and p['status'] == 'pending'
                     for p in s['promises']), 'No pending promise to renounce')
    elif kind == 'challenge':
        gov = s['government']
        _require(gov['officeholder'] != issuer, 'The incumbent cannot challenge itself')
        _require(gov['challenge'] is None and s['round'] >= gov['cooldown_until'], 'Vote pending or cooling down')
        _require(gov['support_streak'][issuer] >= 2, 'Hold five council commitments for two rounds first')
    elif kind == 'work':
        _require(issuer not in s['organizers'], 'Release your organizing effort before working')
        _require(s['project']['package'] is not None, 'No public project has been adopted')
        _require(not any(a['issuer'] == issuer and a['kind'] == 'work' for a in s['actions']), 'Already working')
    else:
        raise CommandError('Unknown action')
    if _preview:
        return None
    record = dict(issuer=issuer, kind=kind, params=deepcopy(params))
    visibility={}
    if patronage.enabled(s):
        private=kind in ('exempt','grant_access','completion_bonus','disclose')
        visibility['audience']=sorted({issuer,target}) if private else sorted(people)
    eid = session.emit('action', issuer, after=record, action_points=s['ap'][issuer]-1,**visibility)
    record['event'] = eid
    s['ap'][issuer] -= 1
    s['actions'].append(record)
    # Command declarations are immediately visible; resolution effects wait for the round.
    s['pending_actions'].append(record)
    _resolve_declarations(session)
    return eid


def _change(session, subject, before, after, parent=None, **details):
    eid = session.emit('structural_change', subject, before, after, [parent], **details)
    session.state['last_change'][subject] = eid
    return eid


def _trust(session, promise, honored, cause):
    s, target, issuer = session.state, promise['beneficiary'], promise['issuer']
    eid = f'{issuer}>{target}'
    if eid not in s['edges']:
        return
    edge = s['edges'][eid]
    before = deepcopy(edge['trust'])
    edge['trust'] = {k: max(.02, min(1., v + (.12 if honored else -.26))) for k, v in before.items()}
    s['graph_revision'] += 1
    _change(session, eid, before, edge['trust'], cause, reason='promise honored' if honored else 'promise broken')


def _promise_result(session, promise, status, cause):
    promise['status'] = status
    eid = session.emit('promise_result', promise['id'], 'pending', status, [cause, promise['event']])
    _trust(session, promise, status == 'fulfilled', eid)


def _resolve_declarations(session):
    s = session.state
    # Caller input order is explicit journal order, never hash iteration order.
    for a in s['pending_actions']:
        kind, issuer, p, parent = a['kind'], a['issuer'], a['params'], a['event']
        target, channel = p.get('target', issuer), p.get('channel', issuer)
        if kind in patronage.KINDS:
            patronage.declare(session,issuer,kind,p,parent)
        elif kind == 'approach':
            s['invitations'].append(dict(sender=issuer, target=target, channel=channel,
                                         due=s['round']+1, event=parent))
        elif kind == 'organize':
            value = dict(person=target, issuer=issuer, channel=channel, event=parent, active_from=s['round']+1)
            s['organizers'][target] = value
            _change(session, f'source:{target}', None, value, parent)
        elif kind == 'fund':
            before=deepcopy(s['government']['allocations'])
            s['government']['allocations'][p['donor']]-=1
            s['government']['allocations'][p['group']]+=1
            _change(session,'budget',before,s['government']['allocations'],parent,reason='one service share transferred')
        elif kind == 'agreement':
            agreement_offer(session,issuer,p['group'],parent)
        elif kind == 'release':
            old = s['organizers'].pop(target)
            _change(session, f'source:{target}', old, None, parent)
        elif kind == 'introduce':
            other = p['other']
            eid = f'{target}>{other}'
            edge = dict(source=target, target=other, trust=dict(governing=.30, organizing=.35), capacity=.5, available=1.)
            s['edges'][eid] = edge
            s['graph_revision'] += 1
            _change(session, eid, None, edge, parent, reason='agreed introduction')
        elif kind == 'adopt':
            before = deepcopy(s['project'])
            s['project'].update(package=channel, streak=0, deadline=s['round']+s['rules']['deadline_rounds'], failed=False)
            s['invitations'] = [i for i in s['invitations'] if i['channel'] not in ('upstream','market') or i['channel'] == channel]
            _change(session, 'project', before, s['project'], parent, reason='package adopted; consecutive work reset')
        elif kind == 'appoint':
            s['government']['liaisons'][target] = issuer
            changed=_change(session, f'liaison:{target}', None, issuer, parent)
            s['last_change']['liaisons']=changed
        elif kind == 'promise':
            value = dict(id=parent, issuer=issuer, beneficiary=target, term=p['term'], event=parent,
                         due=s['round']+2 if s['government']['officeholder'] == issuer else None, status='pending')
            s['promises'].append(value)
            _change(session, f'promise:{parent}', None, value, parent)
        elif kind == 'renounce':
            promise = next(v for v in s['promises'] if v['id'] == p['promise'])
            _promise_result(session, promise, 'broken', parent)
        elif kind == 'challenge':
            s['government']['challenge'] = dict(candidate=issuer, due=s['round']+1, event=parent)
            _change(session, 'challenge', None, s['government']['challenge'], parent)
    s['pending_actions'] = []


def _sources(session):
    s, rules, graph = session.state, session.state['rules'], Graph(session.state)
    requests = []
    remaining = []
    for invite in s['invitations']:
        if invite['due'] <= s['round']:
            eid = f"{invite['sender']}>{invite['target']}"
            edge = s['edges'].get(eid)
            if edge and edge['available'] and s['people'][invite['sender']].get('active',True) and s['people'][invite['target']].get('active',True):
                context = 'governing' if invite['channel'] in CANDIDATES else 'organizing'
                requests.append(dict(person=invite['target'], channel=invite['channel'],
                                     amount=rules['appeal']*edge['trust'][context]*edge['capacity'],
                                     sender=invite['sender'], event=invite['event']))
        else:
            remaining.append(invite)
    s['invitations'] = remaining
    for pid, org in sorted(s['organizers'].items()):
        if org['active_from'] > s['round']:
            continue
        person = s['people'][pid]
        if pid != org['issuer'] and person['allegiance'] != org['issuer']:
            continue
        requests.append(dict(person=pid, channel=org['channel'], amount=rules['self_source']*(1-.15*person['fatigue']), sender=pid, event=org['event']))
    for agreement in s['agreements']:
        if agreement['status'] in ('provisional','suspended'):
            oid=agreement['group'];leader=agreement['leader'];pid=s['organizations'][oid]['coordinator']
            edge=s['edges'].get(f'{leader}>{pid}')
            if edge and pid and s['people'][pid]['active']:
                requests.append(dict(person=pid,channel=leader,amount=.06*edge['trust']['governing'],sender=leader,event=agreement['last_event']))
    # Promises introduce a small local attraction, discounted by trust, while they remain pending.
    for promise in s['promises']:
        if promise['status'] == 'pending':
            edge = s['edges'].get(f"{promise['issuer']}>{promise['beneficiary']}")
            if edge:
                requests.append(dict(person=promise['beneficiary'], channel=promise['issuer'],
                                     amount=.08*edge['trust']['governing'], sender=promise['issuer'], event=promise['event']))
    # Deduplicate equivalent messages and cap targeted channel evaluations before scaling.
    unique = {}
    for request in requests:
        key = (request['sender'], request['person'], request['channel'])
        if key not in unique or unique[key]['amount'] < request['amount']:
            unique[key] = request
    requests = list(unique.values())
    for pid in s['people']:
        totals = {}
        for request in requests:
            if request['person'] == pid:
                totals[request['channel']] = totals.get(request['channel'], 0.) + request['amount']
        channels = sorted(totals, key=lambda k: (-totals[k], k))[:2]
        requests = [r for r in requests if r['person'] != pid or r['channel'] in channels]
    # Bound total sender output, then recipient attention across every active channel.
    for field, budget in [('sender', rules['output_budget']), ('person', rules['source_budget'])]:
        totals = {}
        for r in requests:
            totals[r[field]] = totals.get(r[field], 0.) + r['amount']
        for r in requests:
            r['amount'] /= max(1., totals[r[field]]/budget)
    result = {pid: {k: 0. for k in CHANNELS} for pid in s['people']}
    parents = {pid: [] for pid in s['people']}
    for r in sorted(requests, key=lambda r: (r['sender'], r['person'], r['channel'], r['event'])):
        result[r['person']][r['channel']] += r['amount']
        parents[r['person']].append(r['event'])
    return result, parents


def _decisions(session, fields, parts, parents, checkpoint):
    s, rules = session.state, session.state['rules']
    for pid, person in sorted(s['people'].items()):
        person['pressure'] = fields[pid]
        old = person['allegiance']
        margin = fields[pid]['player']-fields[pid]['rival']
        choice = 'player' if margin > 0 else 'rival'
        new = old
        if pid not in CANDIDATES and s['round']-person['last_review'] >= 2:
            if old and ((margin if old == 'player' else -margin) < -rules['margin_exit']):
                new = None
            threshold = rules['margin_switch'] if old and old != choice else rules['margin_entry']
            if fields[pid][choice] >= rules['entry'] and abs(margin) >= threshold:
                new = choice
        blocked=failed_conditions(s,pid,new) if new else []
        if pid not in CANDIDATES and blocked:
            new=None
            parents[pid].extend(a['last_event'] for a in blocked)
        if new != old:
            eid = session.emit('allegiance', pid, old, new,
                               parents[pid]+[s['last_change'].get(pid)],
                               checkpoint=checkpoint, margin=margin, decomposition=summary(parts[pid]),
                               withheld_for=[a['group'] for a in blocked])
            person['allegiance'], person['last_review'] = new, s['round']
            s['last_change'][pid] = eid
        now = contested(person, rules)
        # Entry/exit hysteresis prevents repeated events at the contested-band edge.
        if person['contested'] and min(fields[pid]['player'],fields[pid]['rival']) >= rules['contested_floor']-.04 and abs(margin) <= rules['contested_band']+.04:
            now = True
        if now != person['contested']:
            session.emit('boundary', pid, person['contested'], now, parents[pid],
                         checkpoint=checkpoint, margin=margin, decomposition=summary(parts[pid]))
            person['contested'] = now
        old_task = person['task']
        best = max(('upstream','market'), key=lambda k: (fields[pid][k], k))
        task = old_task
        if not old_task or s['round']-person['task_since'] >= 2:
            if old_task and fields[pid][old_task] < rules['task_exit']:
                task = None
            if fields[pid][best] >= rules['task_entry'] and (not task or fields[pid][best] > fields[pid][task]+.10):
                task = best
        if task != old_task:
            eid = session.emit('commitment', pid, old_task, task, parents[pid],
                               checkpoint=checkpoint, decomposition=summary(parts[pid]))
            person['task'], person['task_since'] = task, s['round']
            s['last_change'][f'task:{pid}'] = eid


def _project(session):
    s, proj, rules = session.state, session.state['project'], session.state['rules']
    if not proj['package']:
        return
    workers = [pid for pid,p in sorted(s['people'].items())
               if p.get('active',True) and p['task'] == proj['package'] and p['task_since'] < s['round']
               and pid not in s['organizers']]
    for a in s['actions']:
        if a['kind'] == 'work' and a['issuer'] not in workers:
            workers.append(a['issuer'])
    if patronage.enabled(s):
        from .contracts import crew, maintenance
        workers=list(dict.fromkeys(workers+(maintenance(session) if proj['complete'] else crew(session))))
    counts = {skill: sum(s['people'][p]['skill'] == skill for p in workers) for skill in ('work','haul')}
    before = deepcopy(proj)
    if not proj['complete']:
        enough = (counts['work'] >= rules['work_required'] and counts['haul'] >= rules['haul_required']
                  and len({s['people'][p]['location'] for p in workers}) >= 2)
        proj['streak'] = proj['streak']+1 if enough else 0
        if proj['streak'] >= rules['repair_rounds']:
            proj['complete'], proj['completed_round'] = True, s['round']
        elif s['round'] >= proj['deadline'] and not proj.get('failed'):
            proj['failed'] = True
    elif s['round'] >= proj['completed_round']+2:
        proj['maintenance_misses'] = proj['maintenance_misses']+1 if len(workers)<2 else 0
    if before != proj:
        kind = ('project_completed' if not before['complete'] and proj['complete'] else
                'project_failed' if not before.get('failed') and proj.get('failed') else
                'maintenance_failed' if before['maintenance_misses']<2<=proj['maintenance_misses'] else 'project_progress')
        causes=[s['last_change'].get('project')]+[s['last_change'].get(f'task:{p}') for p in workers]
        if patronage.enabled(s):
            causes.extend([s['last_change'].get('right:hiring'),s['patronage']['last_policy_event']])
            causes.extend(s['last_change'].get('benefit:'+pid) for pid in workers)
        eid = session.emit(kind, 'project', before, proj, causes,
                           contributors=workers, counts=counts)
        s['last_change']['project'] = eid
        if kind in ('project_completed','project_failed','maintenance_failed'):
            holder = s['government']['officeholder']
            for edge_id, edge in sorted(s['edges'].items()) if not patronage.enabled(s) else []:
                if edge['source'] == holder:
                    old = deepcopy(edge['trust'])
                    delta = .08 if kind == 'project_completed' else -.12
                    edge['trust'] = {k: max(.02,min(1.,v+delta)) for k,v in old.items()}
                    s['graph_revision'] += 1
                    _change(session, edge_id, old, edge['trust'], eid, reason=kind)


def _promises(session):
    s = session.state
    for promise in s['promises']:
        if promise['status'] != 'pending' or promise['due'] is None:
            continue
        issuer, target, term = promise['issuer'], promise['beneficiary'], promise['term']
        if term == 'liaison':
            honored = s['government']['liaisons'].get(target) == issuer
            cause = s['last_change'].get(f'liaison:{target}')
        else:
            honored = s['government']['officeholder'] == issuer and s['project']['package'] == term
            cause = s['last_change'].get('project')
        if honored:
            _promise_result(session,promise,'fulfilled',cause)
        elif s['round'] >= promise['due']:
            _promise_result(session,promise,'broken',promise['event'])


def _government(session):
    s, gov = session.state, session.state['government']
    votes = {c: [pid for pid in gov['council'] if s['people'][pid].get('active',True) and s['people'][pid]['allegiance'] == c] for c in CANDIDATES}
    for c in CANDIDATES:
        previous = gov['support_streak'][c]
        gov['support_streak'][c] = previous+1 if len(votes[c]) >= 5 else 0
        if (previous == 0) != (gov['support_streak'][c] == 0):
            session.emit('majority', c, previous>0, gov['support_streak'][c]>0,
                         [s['last_change'].get(pid) for pid in gov['council']], ballots=votes[c])
    challenge = gov['challenge']
    if challenge and challenge['due'] <= s['round']:
        candidate, old = challenge['candidate'], gov['officeholder']
        eid = session.emit('council_vote', candidate, old, candidate if len(votes[candidate])>=5 else old,
                           [challenge['event']]+[s['last_change'].get(pid) for pid in gov['council']],
                           ballots={pid:s['people'][pid]['allegiance'] for pid in gov['council']})
        if len(votes[candidate]) >= 5:
            gov['officeholder'], gov['liaisons'] = candidate, {}
            office_event=session.emit('office_transfer', 'government', old, candidate, [eid])
            s['last_change']['office']=office_event
            for promise in s['promises']:
                if promise['issuer'] == candidate and promise['status'] == 'pending' and promise['due'] is None:
                    promise['due'] = s['round']+2
                    _change(session, f"promise:{promise['id']}", None, promise['due'], eid, reason='office-contingent deadline activated')
        gov['challenge'], gov['cooldown_until'] = None, s['round']+3


def _forward(session):
    s, graph = session.state, Graph(session.state)
    for pid, org in sorted(s['organizers'].items()):
        if org['active_from'] > s['round'] or (pid != org['issuer'] and s['people'][pid]['allegiance'] != org['issuer']):
            continue
        channel = org['channel']
        contacts = sorted(graph.contacts(pid), key=lambda p: (s['people'][p]['pressure'][channel],p))
        limit = 3 if pid in s['government']['liaisons'] else 2
        for target in contacts[:limit]:
            s['invitations'].append(dict(sender=pid,target=target,channel=channel,due=s['round']+1,event=org['event']))


def step(session, rival=True):
    """One decision round. No calls into the economic world or global RNG."""
    s = session.state
    if rival:
        from .rival import act
        act(session)
    commands = [{k:deepcopy(a[k]) for k in ('issuer','kind','params')} for a in s['actions']]
    _resolve_declarations(session)
    advance_demands(session)
    if patronage.enabled(s):
        patronage.interests(session)
    sources, parents = _sources(session)
    before = deepcopy(s)
    fields, parts = pressure_step(before, sources)
    checkpoint = len(session.journal)
    graph = Graph(before)
    for pid in parents:
        if patronage.enabled(s):
            parents[pid].extend([s['last_change'].get('benefit:'+pid),s['last_change'].get('knowledge:'+pid)])
        for oid,group in s['organizations'].items():
            if pid in group['members']:
                parents[pid].extend([s['last_change'].get('budget'),s['last_change'].get('liaisons'),s['last_change'].get('office')])
                parents[pid].extend(s['last_change'].get(f'group:{oid}:{c}') for c in CANDIDATES)
                parents[pid].extend(a['last_event'] for a in s['agreements'] if a['group']==oid)
        for edge_id in graph.incoming[pid]:
            source = graph.edges[edge_id]['source']
            parents[pid].extend([s['last_change'].get(edge_id), s['last_change'].get(source),
                                 s['last_change'].get(f'source:{source}')])
    _decisions(session, fields, parts, parents, checkpoint)
    completed_before=s['project']['complete']
    _project(session)
    if patronage.enabled(s):
        from .contracts import after_project
        after_project(session,completed_before)
        patronage.after_round(session)
    _promises(session)
    _government(session)
    rest_and_strain(session)
    _forward(session)
    # A coalition cannot retain command of an organizer who has withdrawn.
    for pid, organizer in list(s['organizers'].items()):
        if pid != organizer['issuer'] and s['people'][pid]['allegiance'] != organizer['issuer']:
            del s['organizers'][pid]
            _change(session, f'source:{pid}', organizer, None, s['last_change'].get(pid), reason='organizer withdrew')
    s['round'] += 1
    if patronage.enabled(s):
        outcome=patronage.result(s)
        if outcome['won'] and s['patronage']['vote_win_round'] is None:
            s['patronage']['vote_win_round']=s['round']
            s['patronage']['debrief_event']=session.emit('mandate_secured','government',None,outcome,
                [s['last_change'].get('office'),s['last_change'].get('project')],audience=sorted(s['people']))
    s['ap'] = {'player':2,'rival':2}
    s['actions'] = []
    session.decision_start = deepcopy(s)
    session.journal.append(dict(commands=commands, rival=rival, digest=state_digest(s)))
    if session.tracing:
        session.history.append(dict(round=before['round'], before=before, sources=sources,
                                    after=deepcopy(s), digest=state_digest(s)))
    return s


def set_availability(session, person, available):
    """Journaled scenario/debug input, not a normal player coercion action."""
    s = session.state
    if person not in s['people'] or not isinstance(available,bool):
        raise ValueError('Availability input requires a known person and boolean')
    old = s['people'][person]['active']
    if old == available:
        return
    record = dict(issuer='scenario',kind='availability',params=dict(person=person,available=available))
    eid = session.emit('external_input',person,old,available)
    record['event'] = eid
    s['actions'].append(record)
    s['people'][person]['active'] = available
    s['graph_revision'] += 1
    _change(session,person,old,available,eid,reason='person availability changed')
    if not available and person in s['organizers']:
        source = s['organizers'].pop(person)
        _change(session,f'source:{person}',source,None,eid,reason='organizer unavailable')
    for oid,org in sorted(s['organizations'].items()):
        if org['coordinator'] == person and not available:
            eligible = [p for p in org['members'] if s['people'][p]['active']]
            org['coordinator'] = min(eligible) if eligible else None
            _change(session,f'coordinator:{oid}',person,org['coordinator'],eid,reason='organization selected a successor')

"""Finite repair offers, voluntary jobs and one contribution set per round."""
from collections import deque
from copy import deepcopy
from .accounts import account, balance, transfer
from .graph import Graph
from .institutions import right, expire
from .knowledge import record


def award(session, issuer, route, package, parent):
    s = session.state
    p = s['patronage']
    merchant = route == 'merchant'
    budget, margin, holder = (36, 6, 'p24') if merchant else (min(30,balance(s,'bridge_fund')), 0, 'public_board')
    value = dict(id=parent, route=route, issuer=issuer, holder=holder, budget=budget,
                 margin=margin, bonus=0, paid=0, status='active', event=parent,
                 completion_event=None, awarded_round=s['round'])
    p['contract'] = value
    transfer(session, 'bridge_fund', 'escrow:bridge', budget, 'repair escrow reserved', [parent])
    fid = record(session, 'contract_awarded', 'contract', dict(route=route, holder=holder,
                 budget=budget, labor=30, margin=margin, issuer=issuer), s['people'], [parent])
    value['event'] = fid
    right(session, 'contract', holder, issuer, fid)
    right(session, 'hiring', holder, issuer, fid)
    p['mobilize_until'] = s['round'] + (1 if route == 'public' else 0)
    s['project'].update(package=package, streak=0, deadline=s['round']+6, failed=False)
    s['last_change']['project'] = fid
    if merchant:
        p['opinions']['p24'][issuer] = min(.7, p['opinions']['p24'][issuer]+.28)


def reachable(state, source, hops=2):
    """A patron can recruit through peers; rulers are not free relay services."""
    graph = Graph(state)
    seen, todo = {source}, deque([(source, 0)])
    while todo:
        node, depth = todo.popleft()
        if depth >= hops:
            continue
        for peer in graph.contacts(node):
            if peer not in seen and peer not in ('player', 'rival'):
                seen.add(peer)
                todo.append((peer, depth+1))
    return seen


def willingness(state, pid, holder):
    p = state['patronage']
    person = state['people'][pid]
    if not person['active']:
        return False, -1., 'unavailable'
    if pid in state['organizers']:
        return False, -1., 'already rallying; one effort slot'
    if any(a['kind']=='work' and a['issuer']==pid for a in state['actions']):
        return False, -1., 'already contributing independently'
    edge = state['edges'].get(f'{holder}>{pid}')
    trust = edge['trust']['organizing'] if edge else .2
    dependence = p['dependencies'].get(f'{holder}>{pid}', {}).get('strength', 0.)
    outside = .7 + (.25 if person['task'] and person['task'] != state['project']['package'] else 0.)
    if pid=='p17' and holder=='p16':
        outside+=.65  # Rafi values an independent, broad roster over Quinn's queue.
    score = 1. + .35*trust + .35*dependence - outside
    return score > 0, score, f'wage 1 + trusted employer {trust*.35:.2f} + dependence {dependence*.35:.2f} versus outside option {outside:.2f}'


def hiring_policy(state):
    """Quinn values continuing office; a funded completion reward can outweigh it."""
    p = state['patronage']
    c = p['contract']
    holder = p['rights']['hiring']['holder']
    motive = p['brokers'].get(holder, {})
    followers = sum(d['strength'] for d in p['dependencies'].values() if d['patron']==holder)
    continuation = motive.get('control', 0)*min(1.4,followers*.5)
    completion = motive.get('delivery', 1)*.8 + c['bonus']*motive.get('income', 0)
    withheld = holder == 'p16' and state['project']['streak'] > 0 and continuation > completion
    return withheld, dict(holder=holder, continuation=continuation, completion=completion,
                          reason='continuing job control outweighs finishing' if withheld else 'completion is preferable to delaying')


def crew(session):
    """Validate, pay and return real workers; this function never advances progress."""
    s = session.state
    p = s['patronage']
    c = p['contract']
    p['last_jobs'] = []
    p['delivered_workers'] = []
    p['withheld'] = False
    if not c or c['status'] != 'active' or s['round'] < p['mobilize_until']:
        return []
    from .patronage import benefit
    holder = p['rights']['hiring']['holder']
    withheld, evaluation = hiring_policy(s)
    if evaluation != p['hiring_evaluation']:
        eid = record(session, 'hiring_decision', 'hiring_policy', evaluation, s['people'],
                     [p['rights']['hiring']['event'], c['event']]+[d['event'] for d in p['dependencies'].values() if d['patron']==holder])
        p['hiring_evaluation'] = evaluation
        p['last_policy_event'] = eid
    if withheld:
        p['withheld'] = True
        return []
    eligible = set(s['people']) - {'player', 'rival'}
    if holder not in ('public_board', 'p24'):
        eligible &= reachable(s, holder)
    graph = Graph(s)
    # Public hiring spreads jobs across communities. Private holders prioritize
    # reachable trusted contacts, without gaining command over their ballots.
    def priority(pid):
        person = s['people'][pid]
        if holder == 'public_board':
            return (pid in s['government']['council'], person['location'], pid)
        edge = s['edges'].get(f'{holder}>{pid}')
        return (not (pid in graph.contacts(holder)), -(edge['trust']['organizing'] if edge else 0.), pid)
    workers = []
    for skill, required in [('work', s['rules']['work_required']), ('haul', s['rules']['haul_required'])]:
        count = 0
        for pid in sorted((q for q in eligible if s['people'][q]['skill']==skill), key=priority):
            if count >= required or balance(s, 'escrow:bridge') <= c['margin']:
                break
            accepted, score, reason = willingness(s, pid, holder)
            job = dict(worker=pid, holder=holder, skill=skill, wage=1, round=s['round'],
                       issuer=c['issuer'],status='delivered' if accepted else 'refused', evaluation=score, reason=reason)
            parent = record(session, 'job_response', pid, job, [pid, c['issuer']]+([holder] if holder in s['people'] else []),
                            [c['event'], p['rights']['hiring']['event']])
            job['event'] = parent
            p['last_jobs'].append(job)
            if not accepted:
                continue
            pay = transfer(session, 'escrow:bridge', account(pid), 1, 'earned repair wage', [parent],
                           audience=[pid, c['issuer']]+([holder] if holder in s['people'] else []))
            c['paid'] += 1
            workers.append(pid)
            count += 1
            benefit(session, pid, holder, c['issuer'], pay)
    if balance(s, 'escrow:bridge') == c['margin'] and len(workers) < 10:
        record(session, 'contract_unfunded', 'contract', dict(paid=c['paid'], reason='labor funds exhausted; no hidden refill'), s['people'], [c['event']])
    p['delivered_workers'] = workers
    return workers


def after_project(session, completed_before):
    s = session.state
    p = s['patronage']
    c = p['contract']
    if not c or completed_before or not s['project']['complete']:
        return
    c['status'] = 'complete'
    p['withheld'] = False
    c['completion_event'] = s['last_change']['project']
    if c['margin']:
        if c['bonus']:
            eid = transfer(session, 'escrow:bridge', account('p16'), c['bonus'], 'earned completion bonus',
                           [c['completion_event'], p['bonus_event']], audience=[c['issuer'], 'p16', 'p24'])
            p['opinions']['p16'][c['issuer']] = min(.7, p['opinions']['p16'][c['issuer']]+.18)
            s['last_change']['benefit:p16'] = eid
        transfer(session, 'escrow:bridge', account(c['holder']), c['margin']-c['bonus'],
                 'earned contractor margin', [c['completion_event'], c['event']], audience=[c['issuer'], c['holder']])
        p['opinions'][c['holder']][c['issuer']] = min(.7, p['opinions'][c['holder']][c['issuer']]+.22)
    remaining = balance(s, 'escrow:bridge')
    if remaining:
        transfer(session, 'escrow:bridge', 'bridge_fund', remaining, 'unspent escrow returned', [c['completion_event']])
    expire(session, 'hiring', c['completion_event'])
    expire(session, 'contract', c['completion_event'])
    access = p['rights'].get('access')
    if access and access['active'] and access['ends_round'] is None:
        access['ends_round'] = s['round'] + p['concession_rounds']


def maintenance(session):
    s = session.state
    p = s['patronage']
    workers = []
    # Recent users can freely refuse unpaid maintenance when tolls already take
    # the benefit. Maintenance is voluntary effort, never a duplicated job.
    receipts = [f['terms'] for f in p['facts'].values() if f['kind']=='access_receipt' and f['round'] >= s['round']-2]
    willing_users = {r['person'] for r in receipts if r['asked_fee']==0}
    for pid in sorted(willing_users):
        if s['people'][pid]['active'] and pid not in s['organizers']:
            workers.append(pid)
            if len(workers) == 2:
                break
    for pid in sorted(s['people']):
        if len(workers) >= 2:
            break
        if pid in workers or pid in ('player','rival') or pid in s['organizers'] or not s['people'][pid]['active']:
            continue
        payer='bridge_fund'
        access=p['rights'].get('access')
        if balance(s,payer)<1 and access and access['active'] and access['ends_round']>s['round']:
            # A concession holder pays to preserve their remaining toll stream.
            # The credits come from their own wallet, including earned rents.
            payer=account(access['holder'])
        if balance(s,payer)>=1:
            transfer(session, payer, account(pid), 1, 'earned maintenance wage', [s['last_change'].get('project')])
            workers.append(pid)
    if workers:
        record(session, 'maintenance_effort', 'maintenance', dict(contributors=workers), s['people'],
               [s['last_change'].get('project')])
    return workers

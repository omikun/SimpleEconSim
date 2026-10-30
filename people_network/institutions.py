"""Exclusive rights, explicit permissions, and the project dependency graph."""
from copy import deepcopy


def right(session, name, holder, issuer, parent, **terms):
    s = session.state
    before = deepcopy(s['patronage']['rights'].get(name))
    value = dict(holder=holder, issuer=issuer, active=True, event=parent, **terms)
    eid = session.emit('right_changed', name, before, value, [parent], audience=sorted(s['people']))
    value['event'] = eid
    s['patronage']['rights'][name] = value
    s['last_change']['right:' + name] = eid
    return value


def expire(session, name, cause):
    value = session.state['patronage']['rights'].get(name)
    if value and value['active']:
        before = deepcopy(value)
        value['active'] = False
        eid = session.emit('right_expired', name, before, value, [value['event'], cause],
                           audience=sorted(session.state['people']))
        value['event'] = eid
        session.state['last_change']['right:' + name] = eid


def control_graph(state):
    """Typed directed graph, distinct from trust: actor -> right -> actual gate."""
    gates = {'contract': 'repair management', 'hiring': 'contracted job queue', 'access': 'toll access'}
    result = []
    for name, value in sorted(state['patronage']['rights'].items()):
        if value['active']:
            result.extend([(value['holder'], name), (name, gates[name])])
    return result


def blockers(state):
    p = state['patronage']
    contract = p['contract']
    if not contract:
        return ['Choose public management or award Yara the repair contract.']
    if state['project']['complete']:
        return ['Maintenance is falling behind; two actual contributors are needed.'] if state['project']['maintenance_misses'] else ['Repair is complete. Keep the coalition together and check any remaining access rights.']
    result = []
    if p['mobilize_until'] > state['round']:
        result.append('Public hiring is gathering applicants; work starts next round.')
    if p['withheld']:
        result.append('Quinn is withholding the contracted queue to preserve the hiring office. Offer a completion bonus or replace the office.')
    affordable=(p['accounts']['escrow:bridge']-contract['margin'])//10
    needed=max(0,3-state['project']['streak'])
    if affordable<needed and not state['project']['complete']:
        result.append(f'Escrow funds {affordable} full crew rounds; {needed} consecutive rounds remain. Recruit voluntary help; a bonus cannot recover wages already spent.')
    jobs = p['last_jobs']
    if jobs and any(j['status'] == 'refused' for j in jobs):
        result.append('Some applicants refused: compare their outside option and campaign commitments in Jobs.')
    return result or ['No institutional blockage. Keep six workers and four haulers available for three consecutive rounds.']

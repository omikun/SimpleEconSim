"""Facts have audiences. Disclosures travel one directed social hop per round."""
from copy import deepcopy
from .graph import Graph


def record(session, kind, subject, terms, audience, parents=()):
    s = session.state
    known = sorted(set(audience))
    eid = session.emit(kind, subject, None, terms, parents, audience=known)
    s['patronage']['facts'][eid] = dict(id=eid, kind=kind, subject=subject,
                                      terms=deepcopy(terms), audience=known, round=s['round'])
    for pid in known:
        learn(s, pid, eid)
    s['last_change'][subject] = eid
    return eid


def learn(state, person, fact):
    known = state['patronage']['known'][person]
    if fact not in known:
        known.append(fact)


def visible(state, viewer, fact):
    return fact in state['patronage']['known'][viewer]


def publish(session, actor, fact, parent=None):
    s = session.state
    if not visible(s, actor, fact):
        raise ValueError('A witness cannot disclose a record they have not seen')
    p = s['patronage']
    if any(d['fact'] == fact and d['actor'] == actor for d in p['disclosures']):
        return
    event = session.emit('disclosure', actor, None, fact, [parent, fact], audience=[actor])
    p['disclosures'].append(dict(fact=fact, actor=actor, frontier=[actor], seen=[actor], event=event))


def advance(session):
    s = session.state
    p = s['patronage']
    graph = Graph(s)
    auditor = p['auditor']
    if auditor and auditor['from_round'] <= s['round']:
        # Record access is an actual power. The official publishes independently.
        actor = auditor['person']
        if s['people'][actor]['active']:
            for fid, fact in list(sorted(p['facts'].items())):
                if fact['kind'] in ('concession', 'exemption', 'access_receipt', 'contract_awarded'):
                    learn(s, actor, fid)
                    if fact['kind'] == 'exemption' or (fact['kind'] == 'access_receipt' and fact['terms']['fee'] > 0):
                        publish(session, actor, fid, auditor['event'])
    for disclosure in p['disclosures']:
        recipients = sorted({q for pid in disclosure['frontier'] for q in graph.contacts(pid)} - set(disclosure['seen']))
        if recipients:
            eid = session.emit('evidence_reached', disclosure['fact'], None, recipients,
                               [disclosure['event'], disclosure['fact']], audience=recipients)
            for pid in recipients:
                learn(s, pid, disclosure['fact'])
                s['last_change']['knowledge:' + pid] = eid
        disclosure['frontier'] = recipients
        disclosure['seen'] = sorted(set(disclosure['seen']) | set(recipients))


def public_view(state, viewer='player'):
    """No inference from unseen terms; normal UI and advice share this boundary."""
    return [deepcopy(f) for fid, f in sorted(state['patronage']['facts'].items()) if visible(state, viewer, fid)]

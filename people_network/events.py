"""Reconstruct exact edge contributions and accumulated causes from checkpoints."""
import math
from .dynamics import advance


def explain(session, person, start=None, end=None):
    if not session.history:
        return {'person':person,'rounds':[],'channels':{}}
    end = len(session.history)-1 if end is None else end
    if start is None:
        transitions = [e for e in session.events if e['kind'] in ('allegiance','commitment')
                       and e['subject'] == person and e.get('checkpoint',0) < end]
        start = transitions[-1]['checkpoint']+1 if transitions else 0
    if not 0 <= start <= end < len(session.history):
        raise ValueError('History interval is outside this run')
    totals, edge_values = {}, {}
    for entry in session.history[start:end+1]:
        _, parts = advance(entry['before'],entry['sources'])
        for channel,p in parts[person].items():
            if channel not in totals:
                totals[channel] = dict(interest_components=dict(base=0.,group=0.,agreement=0.,clamp=0.),before=p['before'],after=p['after'],incoming=0.,source=0.,anchor=0.,decay=0.,opposition=0.,clamp=0.)
                edge_values[channel] = {}
            t = totals[channel]
            t['after'] = p['after']
            for key in ('incoming','source','anchor','decay','opposition','clamp'):
                t[key] += p[key]
            for key,value in p['interest_components'].items():t['interest_components'][key]+=value
            for eid,value in p['edges'].items():
                edge_values[channel][eid] = edge_values[channel].get(eid,0.) + value
    for channel,t in totals.items():
        t['edges'] = dict(sorted(edge_values[channel].items(),key=lambda item:(-abs(item[1]),item[0])))
        t['residual'] = t['after']-t['before']-math.fsum(t[k] for k in ('incoming','source','anchor','decay','opposition','clamp'))
    return dict(person=person, rounds=[start,end],channels=totals,
                note='Contributions explain the executed path; necessity requires a counterfactual replay.')


def causal_chain(session, event_id, limit=30):
    records = {e['id']:e for e in session.events}
    result, seen, todo = [], set(), [event_id]
    while todo and len(result) < limit:
        eid = todo.pop(0)
        if eid not in seen and eid in records:
            seen.add(eid)
            event = records[eid]
            result.append(event)
            todo.extend(event['parents'])
    return result

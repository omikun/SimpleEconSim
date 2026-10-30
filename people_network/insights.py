"""Read-only map advice: explain reach, political leverage and useful next actions."""
from .graph import Graph
from .coalitions import terms, pledge_text
from .advice import recommendations as forecast_recommendations


def overview(state, channel='player', decision_start=None, advise=True):
    graph=Graph(state);people=state['people'];gov=state['government']
    context='governing' if channel in ('player','rival') else 'organizing'
    metrics={}
    for pid,p in sorted(people.items()):
        trusted=[];weight=0.
        for eid in graph.outgoing[pid]:
            e=graph.edges[eid]
            if not e['available'] or not p['active'] or not people[e['target']]['active']:continue
            trust=e['trust'][context]
            if trust>=.45:
                trusted.append(e['target']);weight+=trust*e['capacity']
        regions={people[q]['location'] for q in trusted}-{p['location']}
        new_contacts=[q for q in trusted if people[q]['allegiance']!='player'] if channel in ('player','rival') else [q for q in trusted if people[q]['task']!=channel]
        margin=p['pressure']['player']-p['pressure']['rival']
        metrics[pid]=dict(contacts=len(set(trusted)),reach=weight,other_regions=len(regions),
                          can_reach=new_contacts,margin=margin,councillor=pid in gov['council'],
                          organizer=pid in state['organizers'],available=p['active'])
    council=gov['council'];supporters=[pid for pid in council if people[pid]['active'] and people[pid]['allegiance']=='player']
    swing=[pid for pid in council if people[pid]['active'] and people[pid]['allegiance']!='player' and pid in graph.contacts('player')]
    swing.sort(key=lambda pid:(-metrics[pid]['margin'],pid))
    recommendations=forecast_recommendations(state,channel,decision_start) if advise and state.get('ruleset')!='patronage' else []
    local={}
    for loc in state['locations']:
        members=[pid for pid,p in people.items() if p['location']==loc and p['active']]
        local[loc]=dict(priority='Fields first' if sum(people[p]['alignment']['upstream']-people[p]['alignment']['market'] for p in members)>0 else 'Market first',people=len(members),you=sum(people[p]['allegiance']=='player' for p in members),
                        rival=sum(people[p]['allegiance']=='rival' for p in members),
                        unsure=sum(people[p]['allegiance'] is None for p in members),
                        rallying=sum(p in state['organizers'] for p in members))
    package=state['project']['package']
    workers=[pid for pid,p in people.items() if p['active'] and package and p['task']==package and p['task_since']<state['round'] and pid not in state['organizers']]
    return dict(metrics=metrics,recommendations=recommendations,supporters=supporters,swing=swing,local=local,
                work=sum(people[p]['skill']=='work' for p in workers),haul=sum(people[p]['skill']=='haul' for p in workers),
                task_locations=len({people[p]['location'] for p in workers}),
                groups={oid:dict(allocation=gov['allocations'][oid],need=o['funding_need'],
                                 asks=pledge_text(state,oid),standing=o['band']['player'],
                                 unmet=terms(state,oid,'player'),
                                 agreement=next((a for a in state['agreements'] if a['group']==oid and a['leader']=='player'),None))
                        for oid,o in state['organizations'].items()},
                tired=[pid for pid in state['organizers'] if people[pid]['fatigue']>=state['rules']['rally_limit']-1],
                resting=[pid for pid,p in people.items() if state['round']<p['rest_until']])

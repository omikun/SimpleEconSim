"""Read-only map advice: explain reach, political leverage and useful next actions."""
from .graph import Graph


def overview(state, channel='player'):
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
    organizers=[pid for pid,p in people.items() if p['active'] and p['allegiance']=='player' and pid not in state['organizers']]
    organizers.sort(key=lambda pid:(pid=='player',-(metrics[pid]['other_regions']*2+len(metrics[pid]['can_reach'])+metrics[pid]['reach']),pid))
    recommendations=[]
    if swing:
        pid=swing[0];m=metrics[pid]
        recommendations.append(dict(person=pid,kind='approach',params=dict(target=pid,channel='player'),
                                    title='Win a council vote',action='Ask for support',
                                    reason=f"{people[pid]['name']} does not back you. Of the councillors you can ask directly, this person has the smallest opposing lead.",
                                    detail='An appeal can help; it does not guarantee a vote.'))
    at_risk=sorted([pid for pid in supporters if metrics[pid]['margin']<.20],key=lambda pid:(metrics[pid]['margin'],pid))
    if at_risk:
        pid=at_risk[0]
        recommendations.append(dict(person=pid,kind='approach',params=dict(target=pid,channel='player'),
                                    title='Keep a wavering ally',action='Reassure this ally',
                                    reason=f"{people[pid]['name']} backs you, but Sen's attraction is close. Losing this vote could weaken your majority.",detail='Existing support needs attention too.'))
    if organizers:
        pid=organizers[0];m=metrics[pid]
        recommendations.append(dict(person=pid,kind='organize',params=dict(target=pid,channel=channel),
                                    title='Ask an ally to rally others',action='Ask to rally contacts',
                                    reason=f"{people[pid]['name']} can reach {m['contacts']} trusted contacts, including {len(m['can_reach'])} not yet committed to your goal.",
                                    detail=f"Contacts in {m['other_regions']} other communities. Rallying uses this person's work time."))
    unique=[];seen=set()
    for recommendation in recommendations:
        if recommendation['person'] not in seen:
            unique.append(recommendation);seen.add(recommendation['person'])
    rally=next((r for r in unique if r['kind']=='organize'),None)
    recommendations=([unique[0],rally] if len(unique)>2 and rally and rally!=unique[0] else unique[:2])
    for n,r in enumerate(recommendations,1):r['number']=n
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
                task_locations=len({people[p]['location'] for p in workers}))

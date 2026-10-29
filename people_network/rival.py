"""Public-state rival balancing coalition delivery, votes and volunteer effort."""
from copy import deepcopy
from .graph import Graph
from .coalitions import terms
from .engine import command, CommandError


def group_weight(state,oid,issuer):
    return sum((3. if p in state['government']['council'] else .25)*
               (1. if state['people'][p]['allegiance']==issuer else .65)
               for p in state['organizations'][oid]['members'] if state['people'][p]['active'])


def choose(state,issuer):
    gov,people=state['government'],state['people'];candidates=[]
    def offer(score,kind,**params):candidates.append((score,kind,params))
    if gov['officeholder']!=issuer and gov['support_streak'][issuer]>=2 and not gov['challenge'] and state['round']>=gov['cooldown_until']:
        offer(110,'challenge')
    graph=Graph(state)
    if gov['officeholder']==issuer:
        for promise in state['promises']:
            if promise['issuer']==issuer and promise['status']=='pending':
                if promise['term']=='liaison':offer(100,'appoint',target=promise['beneficiary'])
                else:offer(95,'adopt',channel=promise['term'])
        for agreement in state['agreements']:
            if agreement['leader']!=issuer:continue
            oid=agreement['group'];org=state['organizations'][oid]
            if gov['allocations'][oid]<org['funding_need']:
                for donor,shares in gov['allocations'].items():
                    if donor==oid or shares<=0:continue
                    protects=any(a['leader']==issuer and a['group']==donor for a in state['agreements'])
                    extra=shares>state['organizations'][donor]['funding_need']
                    offer(105+(4 if extra else 0)-(10 if protects and not extra else 0),'fund',group=oid,donor=donor)
        for oid,org in state['organizations'].items():
            value=group_weight(state,oid,issuer)
            if org.get('representation') and not any(p in org['members'] and c==issuer for p,c in gov['liaisons'].items()):
                eligible=[p for p in org['members'] if people[p]['active'] and people[p]['allegiance']==issuer]
                if eligible:offer((108 if any(a['leader']==issuer and a['group']==oid for a in state['agreements']) else 75)+value,'appoint',target=sorted(eligible)[0])
            if gov['allocations'][oid]<org['funding_need']:
                for donor in state['organizations']:
                    if donor==oid or gov['allocations'][donor]<=0:continue
                    donor_org=state['organizations'][donor]
                    loss=group_weight(state,donor,issuer) if gov['allocations'][donor]<=donor_org['funding_need'] else 0.
                    pledged=any(a['leader']==issuer and a['group']==donor for a in state['agreements'])
                    benefit=value-loss-(8 if pledged else 0)
                    if pledged and gov['allocations'][donor]<=state['organizations'][donor]['funding_need']:continue
                    if benefit>0:offer(75+benefit,'fund',group=oid,donor=donor)
        if state['project']['package'] is None:
            desired=max(state['organizations'],key=lambda oid:group_weight(state,oid,issuer))
            package=state['organizations'][desired].get('preferred_package','market' if issuer=='rival' else 'upstream')
            offer(78,'adopt',channel=package)
    promised={a['group'] for a in state['agreements'] if a['leader']==issuer}
    committed=sum(state['organizations'][oid]['funding_need'] for oid in promised)
    for oid,org in state['organizations'].items():
        if oid not in promised and committed+org['funding_need']<=gov['budget_total'] and org['coordinator'] in graph.contacts(issuer):
            offer(70+group_weight(state,oid,issuer)+(8 if terms(state,oid,gov['officeholder']) else 0),'agreement',group=oid)
    owned=sum(o['issuer']==issuer for o in state['organizers'].values())
    if issuer not in state['organizers'] and people[issuer]['fatigue']<=1 and state['round']>=people[issuer]['rest_until']:
        offer(61,'organize',target=issuer,channel=issuer)
    for pid in graph.contacts(issuer):
        p=people[pid];council=pid in gov['council']
        margin=abs(p['pressure']['player']-p['pressure']['rival'])
        priority=(45 if council else 20)+(1-margin)*20
        if p['allegiance']==issuer and pid not in state['organizers'] and owned<3:
            overloaded=any(pid in o['members'] and sum(q in o['members'] and v['issuer']==issuer for q,v in state['organizers'].items())>=o.get('workload_limit',99) for o in state['organizations'].values())
            if not overloaded and p['fatigue']<=1 and state['round']>=p['rest_until']:
                offer(priority+13,'organize',target=pid,channel=issuer)
        elif p['allegiance']!=issuer:
            offer(priority,'approach',target=pid,channel=issuer)
    return sorted(candidates,key=lambda c:(-c[0],c[1],str(sorted(c[2].items()))))


def act(session,issuer='rival'):
    # Select from the same public start-of-round snapshot as before. Incorporate
    # only this leader's own declarations, not the opponent's unobserved choices.
    view=deepcopy(session.decision_start)
    for _ in range(session.state['ap'][issuer]):
        for _,kind,params in choose(view,issuer):
            try:command(session,issuer,kind,**params)
            except CommandError:continue
            if kind=='organize':view['organizers'][params['target']]={'issuer':issuer}
            elif kind=='adopt':view['project']['package']=params['channel']
            elif kind=='challenge':view['government']['challenge']={'candidate':issuer}
            elif kind=='appoint':view['government']['liaisons'][params['target']]=issuer
            elif kind=='fund':
                view['government']['allocations'][params['donor']]-=1
                view['government']['allocations'][params['group']]+=1
            elif kind=='agreement':view['agreements'].append(dict(leader=issuer,group=params['group']))
            break

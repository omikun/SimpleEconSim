"""Public-state rival balancing coalition delivery, votes and volunteer effort."""
from copy import deepcopy
from .graph import Graph
from .coalitions import terms
from .engine import command, CommandError


def own_changes(view,before,after):
    """Merge this declaration's delta without importing unseen same-round deals."""
    if isinstance(before,dict) and isinstance(after,dict):
        result=deepcopy(view)
        for key,value in after.items():
            if key not in before:result[key]=deepcopy(value)
            elif value!=before[key]:result[key]=own_changes(result.get(key),before[key],value)
        for key in before.keys()-after.keys():result.pop(key,None)
        return result
    if isinstance(before,list) and isinstance(after,list) and after[:len(before)]==before:
        return deepcopy(view)+deepcopy(after[len(before):])
    return deepcopy(after)


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
    if view.get('ruleset')=='patronage':
        # Public declared backing is observable; another actor's private
        # preference numbers and undisclosed bargain terms are not.
        for pid,person in view['people'].items():
            if pid!=issuer:
                for leader in ('player','rival'):
                    person['pressure'][leader]=.65 if person['allegiance']==leader else .35
    for _ in range(session.state['ap'][issuer]):
        candidates=choose(view,issuer)
        if view.get('ruleset')=='patronage':
            candidates=patronage_choices(view,issuer)+candidates
            candidates.sort(key=lambda c:(-c[0],c[1],str(sorted(c[2].items()))))
        for _,kind,params in candidates:
            private_before=deepcopy(session.state['patronage']) if view.get('ruleset')=='patronage' else None
            project_before=deepcopy(session.state['project'])
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
            elif kind in ('award_contract','hiring_office','completion_bonus','grant_access','exempt','free_access','audit','disclose','buyout_access','cancel_contract'):
                # Update only this actor's own accepted declarations. Other
                # same-round choices remain hidden until the next boundary.
                view['patronage']=own_changes(view['patronage'],private_before,session.state['patronage'])
                view['project']=own_changes(view['project'],project_before,session.state['project'])
            break


def patronage_choices(state,issuer):
    from .knowledge import public_view
    p=state['patronage'];c=p['contract'];candidates=[]
    incumbent=state['government']['officeholder']==issuer
    votes=sum(state['people'][pid]['allegiance']==issuer for pid in state['government']['council'])
    if incumbent and (not c or c['status']=='cancelled') and not state['project']['complete']:
        route='merchant' if p['accounts']['bridge_fund']>=36 and state['people']['p24']['allegiance']==issuer else 'public'
        candidates.append((104,'award_contract',dict(route=route,channel='market')))
    if incumbent and c and c['status']=='active' and c['route']=='merchant' and p['rights']['hiring']['holder']=='p24' and votes<=5:
        candidates.append((103,'hiring_office',dict(holder='p16')))
    if incumbent and c and c['status']=='active' and p['rights']['hiring']['holder']=='p16' and c['route']=='merchant' and not c['bonus']:
        candidates.append((109,'completion_bonus',{}))
    if incumbent and c and votes<5:
        access=p['rights'].get('access',{})
        if not access.get('active') and state['people']['p24']['allegiance']!=issuer:
            candidates.append((102,'grant_access',dict(target='p24',fee=1)))
        elif access.get('active') and state['people']['p08']['allegiance']!=issuer:
            own_exemptions=[f['terms']['person'] for f in public_view(state,issuer) if f['kind']=='exemption']
            if 'p08' not in own_exemptions:candidates.append((102,'exempt',dict(target='p08')))
    if incumbent and not p['auditor'] and p['rights'].get('access',{}).get('issuer') not in (None,issuer):
        candidates.append((85,'audit',{}))
    for fact in public_view(state,issuer):
        if fact['kind'] in ('exemption','access_receipt') and fact['terms'].get('issuer')!=issuer and not any(d['fact']==fact['id'] and d['actor']==issuer for d in p['disclosures']):
            candidates.append((88,'disclose',dict(fact=fact['id'])))
            break
    return candidates

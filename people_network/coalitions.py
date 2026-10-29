"""Competing public demands, conditional agreements and the cost of organizing.

Service-budget shares are a fixed laboratory allocation, not cash in the wider
economy. Group opinions influence individuals; no positive rule assigns votes.
"""
from copy import deepcopy


def initialize(state):
    state['government']['allocations']={oid:1 for oid in state['organizations']}
    state['government']['budget_total']=4
    state['agreements']=[]
    for org in state['organizations'].values():
        org.update(standing={'player':0.,'rival':0.},band={'player':'watching','rival':'watching'})
    for person in state['people'].values():
        person.update(fatigue=0,rest_until=0,base_alignment=deepcopy(person['alignment']),alignment_parts={})


def terms(state,oid,leader):
    """The same public promises bind incumbent and opposition after taking office."""
    org=state['organizations'][oid];gov=state['government']
    missing=[]
    if gov['allocations'][oid]<org['funding_need']:
        missing.append(f"funding {gov['allocations'][oid]}/{org['funding_need']}")
    if org.get('workload_limit') is not None:
        count=sum(p in org['members'] and o['issuer']==leader for p,o in state['organizers'].items())
        if count>org['workload_limit']:missing.append(f"{count} rallying; maximum {org['workload_limit']}")
    if org.get('representation'):
        represented=any(p in org['members'] and state['people'][p]['active'] and c==leader for p,c in gov['liaisons'].items())
        if not represented:missing.append('no liaison from this group')
    return missing


def failed_conditions(state,pid,candidate):
    return [a for a in state['agreements'] if a['leader']==candidate and a['status'] in ('breached','repairing') and a['breaches']>0
            and pid in state['organizations'][a['group']]['members']]


def pledge_text(state,oid):
    org=state['organizations'][oid]
    text=f"At least {org['funding_need']} budget share"+('s' if org['funding_need']!=1 else '')
    if org.get('workload_limit') is not None:text+=f"; no more than {org['workload_limit']} members rallying"
    if org.get('representation'):text+='; a liaison from this group'
    return text


def _record(session,kind,subject,before,after,parents=(),**detail):
    eid=session.emit(kind,subject,before,after,parents,**detail)
    session.state['last_change'][subject]=eid
    return eid


def agreement_offer(session,leader,oid,parent):
    state=session.state
    value=dict(id=parent,leader=leader,group=oid,status='provisional',office_rounds=0,
               met_streak=0,breaches=0,last_event=parent,offered_round=state['round'])
    state['agreements'].append(value)
    value['last_event']=_record(session,'agreement_offered',f'agreement:{parent}',None,value,[parent],
                                terms=pledge_text(state,oid),group=oid,leader=leader)


def _delivery(state,oid,leader):
    org=state['organizations'][oid];gov=state['government']
    funding=min(1.,gov['allocations'][oid]/org['funding_need'])
    components=[(funding,2.)]
    preferred=org.get('preferred_package')
    if preferred:
        project=state['project']
        access=(1. if project['package']==preferred else .8 if project['complete'] else
                .45 if project['package'] is None else 0.)
        components.append((access,1.))
    if org.get('representation'):
        components.append((float(any(p in org['members'] and state['people'][p]['active'] and c==leader for p,c in gov['liaisons'].items())),1.))
    if org.get('workload_limit') is not None:
        active=sum(p in org['members'] and o['issuer']==leader for p,o in state['organizers'].items())
        components.append((max(0.,1.-max(0,active-org['workload_limit'])/2),2.))
    return sum(value*weight for value,weight in components)/sum(w for _,w in components)



def credibility(state,leader):
    own=[a for a in state['agreements'] if a['leader']==leader]
    breaches=sum(a['breaches'] for a in own)
    over=max(0,sum(state['organizations'][a['group']]['funding_need'] for a in own)-state['government']['budget_total'])
    personal=sum(p['issuer']==leader and p['status']=='broken' for p in state['promises'])
    return max(.15,min(1.,.75-.20*breaches-.15*over-.10*personal))


def advance_demands(session):
    """Resolve material delivery before this round's pressure update and ballots."""
    state=session.state;holder=state['government']['officeholder']
    for agreement in state['agreements']:
        oid,leader=agreement['group'],agreement['leader'];old=agreement['status']
        if holder!=leader:
            agreement['met_streak']=0
            # An old breach is a reputation cost, but opposition cannot allocate
            # the incumbent's budget. Its conditional deadlines resume in office.
            if old!='suspended':
                agreement['status']='suspended'
                agreement['last_event']=_record(session,'agreement_suspended',f"agreement:{agreement['id']}",old,'suspended',
                                                [agreement['last_event'],state['last_change'].get('office')],group=oid,leader=leader)
            continue
        agreement['office_rounds']+=1
        unmet=terms(state,oid,leader)
        agreement['met_streak']=0 if unmet else agreement['met_streak']+1
        if agreement['met_streak']>=2:new='honored'
        elif agreement['breaches'] or agreement['office_rounds']>state['rules']['agreement_grace']:new='breached' if unmet else 'repairing'
        else:new='provisional'
        agreement['status']=new
        if new!=old:
            if new=='breached':agreement['breaches']+=1
            eid=_record(session,'agreement_'+new,f"agreement:{agreement['id']}",old,new,
                        [agreement['last_event'],state['last_change'].get('budget'),state['last_change'].get('liaisons'),
                         state['last_change'].get('office')],group=oid,leader=leader,unmet=unmet)
            agreement['last_event']=eid
            if new in ('breached','honored'):
                coordinator=state['organizations'][oid]['coordinator']
                edge=state['edges'].get(f'{leader}>{coordinator}')
                if edge:
                    before=deepcopy(edge['trust']);delta=-.12 if new=='breached' else .04
                    edge['trust']={k:max(.02,min(1.,v+delta)) for k,v in before.items()}
                    state['graph_revision']+=1
                    _record(session,'structural_change',f'{leader}>{coordinator}',before,edge['trust'],[eid],
                            reason='group agreement '+new)
    for oid,org in sorted(state['organizations'].items()):
        for leader in ('player','rival'):
            old=org['standing'][leader]
            if leader==holder:
                target=2*_delivery(state,oid,leader)-1
                new=old+(target-old)*state['rules']['group_response']
            else:
                load=sum(p in org['members'] and o['issuer']==leader for p,o in state['organizers'].items())
                excess=max(0,load-org.get('workload_limit',len(org['members'])))
                new=old*.97-.05*excess
            new=max(-1.,min(1.,new));org['standing'][leader]=new
            band=('satisfied' if leader!=holder or not terms(state,oid,leader) else 'warming') if new>=.25 else 'angry' if new<=-.25 else 'watching'
            # Small drift remains in checkpoints; only consequential bands emit.
            if band!=org['band'][leader]:
                oldband=org['band'][leader];org['band'][leader]=band
                parents=[state['last_change'].get('budget'),state['last_change'].get('project'),
                         state['last_change'].get('liaisons')]
                parents.extend(a['last_event'] for a in state['agreements'] if a['group']==oid and a['leader']==leader)
                parents.extend(o['event'] for p,o in state['organizers'].items() if p in org['members'] and o['issuer']==leader)
                _record(session,'group_mood',f'group:{oid}:{leader}',oldband,band,parents,
                        group=oid,leader=leader,standing_before=old,standing_after=new,
                        funding=state['government']['allocations'][oid],unmet=terms(state,oid,leader) if leader==holder else [])
    for pid,person in state['people'].items():
        if pid in ('player','rival'):continue
        groups=[org for org in state['organizations'].values() if pid in org['members']]
        for leader in ('player','rival'):
            opinion=sum(o['standing'][leader] for o in groups)/len(groups) if groups else 0.
            program=0.
            for agreement in state['agreements']:
                if agreement['leader']!=leader or pid not in state['organizations'][agreement['group']]['members']:continue
                factor=1. if agreement['status'] in ('provisional','suspended') else .75 if agreement['status']=='honored' else 0.
                # Matching services already delivered is less compelling than
                # addressing a demand the incumbent is currently failing.
                contrast=1. if leader==holder or terms(state,agreement['group'],holder) else .35
                program+=factor*contrast*credibility(state,leader)/max(1,len(groups))
            base=person['base_alignment'][leader]
            group_part=state['rules']['group_influence']*opinion
            agreement_part=state['rules']['agreement_influence']*program
            raw=base+group_part+agreement_part
            person['alignment'][leader]=max(0.,min(1.,raw))
            person['alignment_parts'][leader]=dict(base=base,group=group_part,agreement=agreement_part,
                                                   clamp=person['alignment'][leader]-raw)


def rest_and_strain(session):
    state=session.state;limit=state['rules']['rally_limit']
    for pid,p in sorted(state['people'].items()):
        organizer=state['organizers'].get(pid)
        working=organizer and organizer['active_from']<=state['round']
        if working:
            p['fatigue']=min(limit,p['fatigue']+1)
            if p['fatigue']>=limit:
                del state['organizers'][pid]
                p['rest_until']=state['round']+1+state['rules']['rally_rest']
                _record(session,'organizer_exhausted',f'source:{pid}',organizer,None,
                        [organizer['event']],person=pid,fatigue=p['fatigue'],rest_until=p['rest_until'])
        else:p['fatigue']=max(0,p['fatigue']-1)

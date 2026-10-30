"""Opt-in bridge patronage: benefits, institutional bargaining and local evidence.

The classic ruleset does not initialize or call this module. All tuning values
are authored laboratory mechanics, not estimates of real political behavior.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
from .accounts import account, balance, transfer
from .institutions import right, expire, blockers, control_graph
from .knowledge import record, learn, publish, visible, advance as advance_knowledge

FIXTURE = Path(__file__).resolve().parents[1] / 'scenarios/people_network/patronage.json'
KINDS = frozenset(('award_contract', 'hiring_office', 'completion_bonus', 'grant_access',
                   'exempt', 'free_access', 'audit', 'disclose', 'buyout_access', 'cancel_contract'))


def enabled(state):
    return state.get('ruleset') == 'patronage'


def initialize(state):
    fixture = json.loads(FIXTURE.read_text())
    people = state['people']
    accounts = {account(pid): fixture['wallet'] for pid in people}
    accounts.update(bridge_fund=fixture['fund'], **{'escrow:bridge': 0})
    for edge in fixture['contacts']:
        state['edges'][edge['source']+'>'+edge['target']]=deepcopy(edge)
    state['patronage'] = dict(accounts=accounts, initial_total=sum(accounts.values()),
        brokers=fixture['brokers'], travelers=fixture['travelers'], concession_rounds=fixture['concession_rounds'],
        debrief_round=fixture['debrief_round'], contract=None, rights={}, last_jobs=[],
        delivered_workers=[], dependencies={}, opinions={pid:dict(player=0.,rival=0.) for pid in people},
        facts={}, known={pid:[] for pid in people}, disclosures=[], auditor=None,
        free_claims=[], reactions=[], mobilize_until=0, withheld=False, hiring_evaluation=None,
        last_policy_event=None, bonus_event=None, total_crossings=0, total_denied=0,
        total_tolls=0, total_waiting=0, last_access=[], vote_win_round=None, debrief_event=None)


def check(state, issuer, kind, params, require):
    """Validate every precondition before spending AP or reserving funds."""
    require(enabled(state), 'Choose the Patronage ruleset for contracts and private deals')
    p = state['patronage']
    incumbent = state['government']['officeholder'] == issuer
    c = p['contract']
    target = params.get('target', issuer)
    if kind not in ('free_access', 'disclose'):
        require(incumbent, 'Only the government may grant or revoke institutional rights')
    if kind == 'award_contract':
        route = params.get('route')
        require(route in ('public','merchant'), 'Choose public or merchant management')
        require(params.get('channel', 'upstream') in ('upstream','market'), 'Choose field or market access')
        require(not c or c['status']=='cancelled', 'A repair contract already exists; honor or cancel it first')
        require(not state['project']['complete'], 'Repair is complete; maintain the bridge')
        require(balance(state,'bridge_fund') >= (36 if route=='merchant' else 10), 'The fund cannot afford this offer')
        require(route=='public' or state['people']['p24']['active'], 'Yara is unavailable')
    elif kind == 'hiring_office':
        holder = params.get('holder')
        require(c and c['status']=='active', 'An active repair contract is required')
        require(holder in ('public_board','p16','p17'), 'Choose public hiring, Quinn or Rafi')
        require(holder=='public_board' or state['people'][holder]['active'], 'The proposed officer is unavailable')
        old = p['rights']['hiring']['holder']
        require(holder != old, 'This officer already controls hiring')
        require(old in ('public_board','p24') or balance(state,account(issuer))>=2, 'Replacing a patron costs two of your personal credits in compensation')
    elif kind == 'completion_bonus':
        require(c and c['status']=='active' and c['route']=='merchant', 'Only the merchant margin can fund this bonus')
        require(p['rights']['hiring']['holder']=='p16', 'Quinn must hold the hiring office')
        require(c['bonus']==0 and c['margin']>=2, 'The completion bonus is already reserved')
    elif kind == 'grant_access':
        require(c is not None, 'Choose a repair contract before granting access rights')
        require(target in ('p24','p16'), 'This concession is offered to Yara or Quinn')
        require(type(params.get('fee',2)) is int and params.get('fee',2) in (1,2), 'The fee cap is one or two credits')
        require(not p['rights'].get('access',{}).get('active'), 'An exclusive access concession already exists')
    elif kind == 'exempt':
        access=p['rights'].get('access')
        require(access and access['active'], 'A live toll concession is required')
        require(target not in access['exemptions'], 'This person is already exempt')
        motives=p['brokers'].get(target,dict(income=.6,constituents=.5))
        require(motives['income']-.6*motives['constituents']>0,
                state['people'][target]['name']+' refuses a private exemption; public access and constituency interests matter more')
    elif kind == 'free_access':
        require(not any(claim['issuer']==issuer for claim in p['free_claims']), 'Your public free-access promise is already recorded')
    elif kind == 'audit':
        require(state['people']['p00']['active'], 'Amal is unavailable to inspect records')
        require(not p['auditor'], 'The independent auditor is already appointed and retains access across government changes')
    elif kind == 'disclose':
        fid=params.get('fact')
        require(fid in p['facts'] and visible(state,issuer,fid), 'You must possess the evidence you disclose')
        require(not any(d['fact']==fid and d['actor']==issuer for d in p['disclosures']), 'This evidence is already being shared')
    elif kind == 'buyout_access':
        require(p['rights'].get('access',{}).get('active'), 'No active concession to buy out')
        require(balance(state,account(issuer))>=2, 'Buying out the concession costs two of your personal credits')
    elif kind == 'cancel_contract':
        require(c and c['status']=='active', 'No active contract to cancel')
        require(c['route']=='public' or balance(state,account(issuer))>=2, 'Cancellation requires two personal credits of compensation')


def declare(session, issuer, kind, params, parent):
    s = session.state
    p = s['patronage']
    c = p['contract']
    target = params.get('target', issuer)
    if kind == 'award_contract':
        from .contracts import award
        award(session, issuer, params['route'], params.get('channel','upstream'), parent)
    elif kind == 'hiring_office':
        old = p['rights']['hiring']['holder']
        holder = params['holder']
        if old not in ('public_board','p24'):
            transfer(session, account(issuer), account(old), 2, 'lawful hiring-office replacement compensation', [parent])
            p['opinions'][old][issuer] = max(-.7,p['opinions'][old][issuer]-.25)
        right(session,'hiring',holder,issuer,parent)
        p['mobilize_until'] = s['round'] + (1 if holder=='public_board' else 0)
        p['withheld'] = False
        if holder in s['people']:
            p['opinions'][holder][issuer] = min(.7,p['opinions'][holder][issuer]+.22)
    elif kind == 'completion_bonus':
        c['bonus'] = 2
        p['bonus_event'] = record(session,'bonus_reserved','completion_bonus',
            dict(person='p16',amount=2,source='six-credit margin',due='completion',issuer=issuer,
                 consenting=['p16','p24'],reason='Quinn values completion income; Yara accepts four credits over an obstructed six-credit claim'), [issuer,'p16','p24'],[parent,c['event']])
    elif kind == 'grant_access':
        fee = params.get('fee',2)
        fid = record(session,'concession','access_terms',dict(holder=target,fee=fee,duration=6,issuer=issuer), [issuer,target],[parent])
        right(session,'access',target,issuer,fid,fee=fee,exemptions=[],
              ends_round=s['round']+p['concession_rounds'] if s['project']['complete'] else None,
              terms_event=fid)
        p['opinions'][target][issuer] = min(.7,p['opinions'][target][issuer]+.18)
    elif kind == 'exempt':
        access = p['rights']['access']
        access['exemptions'].append(target)
        fid = record(session,'exemption','exemption:'+target,dict(person=target,holder=access['holder'],issuer=issuer,concession=access['terms_event']),
                     [issuer,target,access['holder']],[parent,access['terms_event']])
        p['opinions'][target][issuer] = min(.7,p['opinions'][target][issuer]+.38)
        s['last_change']['benefit:'+target] = fid
    elif kind == 'free_access':
        fid = record(session,'public_promise','free_access:'+issuer,
                     dict(issuer=issuer,term='free access while governing after completion'), s['people'],[parent])
        p['free_claims'].append(dict(issuer=issuer,fact=fid))
    elif kind == 'audit':
        fid = record(session,'audit_appointed','auditor',dict(person='p00',issuer=issuer,access='all project records'),s['people'],[parent])
        p['auditor'] = dict(person='p00',from_round=s['round']+1,event=fid)
        p['opinions']['p00'][issuer] = min(.7,p['opinions']['p00'][issuer]+.12)
    elif kind == 'disclose':
        publish(session,issuer,params['fact'],parent)
    elif kind == 'buyout_access':
        access = p['rights']['access']
        transfer(session,account(issuer),account(access['holder']),2,'access-concession buyout',[parent,access['event']])
        expire(session,'access',parent)
    elif kind == 'cancel_contract':
        if c['route']=='merchant':
            transfer(session,account(issuer),account(c['holder']),2,'contract cancellation compensation',[parent,c['event']])
        remaining=balance(s,'escrow:bridge')
        if remaining:
            transfer(session,'escrow:bridge','bridge_fund',remaining,'cancelled contract escrow returned',[parent,c['event']])
        c['status']='cancelled'
        expire(session,'contract',parent)
        expire(session,'hiring',parent)
        record(session,'contract_cancelled','contract',dict(holder=c['holder'],issuer=issuer),s['people'],[parent,c['event']])


def benefit(session, worker, holder, issuer, parent):
    """A delivered wage creates a bounded, expiring relationship to its allocator."""
    s = session.state
    p = s['patronage']
    credit = issuer if holder=='public_board' else holder
    key = f'{credit}>{worker}'
    if credit != worker:
        previous=p['dependencies'].get(key)
        old=previous['strength'] if previous else 0.
        strength=min(.85,old+.24*(1.-old))
        event=session.emit('dependence',key,old,strength,[parent],patron=credit,worker=worker,
                           audience=sorted({issuer,worker,credit}))
        p['dependencies'][key]=dict(patron=credit,worker=worker,strength=strength,
                                    last_round=s['round'],event=event)
        # The paid relationship opens a modest communication route, not a vote.
        if key not in s['edges']:
            s['edges'][key]=dict(source=credit,target=worker,trust=dict(governing=.3,organizing=.4),capacity=.3,available=1.)
            s['graph_revision']+=1
            s['last_change'][key]=event
    p['opinions'][worker][issuer]=min(.7,p['opinions'][worker][issuer]+(.09 if holder=='public_board' else .035))
    s['last_change']['benefit:'+worker]=parent


def interests(session):
    """Run after classic group-interest calculation, before synchronous pressure."""
    s=session.state
    p=s['patronage']
    for dependency in p['dependencies'].values():
        dependency['strength']*=.9 if s['round']>dependency['last_round'] else 1.
    for pid, person in sorted(s['people'].items()):
        if pid in ('player','rival'):
            continue
        for leader in ('player','rival'):
            p['opinions'][pid][leader]*=.97
            dependent=sum(d['strength']*.12 for d in p['dependencies'].values()
                          if d['worker']==pid and s['people'][d['patron']]['allegiance']==leader)
            value=max(-.7,min(.7,p['opinions'][pid][leader]+dependent))
            components=person['alignment_parts'][leader]
            raw=components['base']+components['group']+components['agreement']+value
            components['patronage']=value
            person['alignment'][leader]=max(0.,min(1.,raw))
            components['clamp']=person['alignment'][leader]-raw


def access_round(session):
    s=session.state
    p=s['patronage']
    p['last_access']=[]
    access=p['rights'].get('access')
    if access and access['active'] and access['ends_round'] is not None and s['round']>=access['ends_round']:
        expire(session,'access',s['last_change'].get('project'))
    if not s['project']['complete']:
        start=(s['round']%2)*4
        delayed=[pid for pid in p['travelers'][start:start+4] if s['people'][pid]['active']]
        p['total_waiting']+=len(delayed)
        if delayed:
            record(session,'access_delayed','unfinished_bridge',dict(people=delayed,reason='bridge not repaired'),s['people'],
                   [s['last_change'].get('project')])
        return
    usable=s['project']['maintenance_misses']<2
    # Four concrete journeys each round, alternating halves of the authored list.
    start=(s['round']%2)*4
    for pid in p['travelers'][start:start+4]:
        if not s['people'][pid]['active']:
            continue
        fee=access['fee'] if access and access['active'] and pid not in access['exemptions'] and pid!=access['holder'] else 0
        enough=balance(s,account(pid))>=fee
        crossed=usable and enough
        if crossed and fee:
            transfer(session,account(pid),account(access['holder']),fee,'actual bridge toll',
                     [access['terms_event'],s['last_change'].get('project')],audience=[pid,access['holder']])
            p['total_tolls']+=fee
        receipt=dict(person=pid,fee=fee if crossed else 0,asked_fee=fee,crossed=crossed,
                     reason='crossed' if crossed else 'unaffordable toll' if usable else 'maintenance neglected',
                     government=s['government']['officeholder'],
                     issuer=access['issuer'] if access and access['active'] else s['government']['officeholder'])
        fid=record(session,'access_receipt','journey:'+pid,receipt,[pid]+([access['holder']] if access and access['active'] else []),
                   [s['last_change'].get('project')]+([access['terms_event']] if access and access['active'] else []))
        receipt['event']=fid
        p['last_access'].append(receipt)
        p['total_crossings']+=int(crossed)
        p['total_denied']+=int(not crossed)
        holder=s['government']['officeholder']
        delta=.035 if crossed and fee==0 else -.07*fee if crossed else -.18
        p['opinions'][pid][holder]=max(-.7,min(.7,p['opinions'][pid][holder]+delta))
        if fee and access:
            # A private concession affects those who encounter its actual toll;
            # the terms do not need to be globally known for a payer to object.
            learn(s,pid,access['terms_event'])


def react(session):
    s=session.state
    p=s['patronage']
    for pid in sorted(s['people']):
        if pid in ('player','rival'):
            continue
        for fid in list(p['known'][pid]):
            fact=p['facts'][fid]
            key=pid+':'+fid
            if key in p['reactions']:
                continue
            t=fact['terms']
            delta=0.
            cause=[]
            issuer=t.get('issuer')
            if fact['kind']=='access_receipt' and t['asked_fee']>0:
                promises=[claim for claim in p['free_claims'] if claim['issuer']==issuer
                          and t.get('government')==issuer and p['facts'][claim['fact']]['round']<=fact['round']
                          and visible(s,pid,claim['fact'])]
                if promises:
                    delta=-.14 if s['people'][pid]['location']=='village' else -.07
                    cause=[claim['fact'] for claim in promises]
            elif fact['kind']=='exemption' and pid!=t['person']:
                if s['people'][pid]['location']==s['people'][t['person']]['location']:
                    delta=-.12
                    edge=s['edges'].get(f"{t['person']}>{pid}")
                    if edge:
                        before=deepcopy(edge['trust'])
                        edge['trust']={k:max(.02,v-.12) for k,v in edge['trust'].items()}
                        s['graph_revision']+=1
                        eid=session.emit('structural_change',f"{t['person']}>{pid}",before,edge['trust'],[fid],
                                         reason='known personal exemption while members pay',audience=[pid,t['person']])
                        s['last_change'][f"{t['person']}>{pid}"]=eid
            if delta and issuer in ('player','rival'):
                old=p['opinions'][pid][issuer]
                p['opinions'][pid][issuer]=max(-.7,min(.7,old+delta))
                event=session.emit('evidence_reaction',pid,old,p['opinions'][pid][issuer],[fid]+cause,
                                   fact=fid,leader=issuer,audience=[pid])
                s['last_change']['benefit:'+pid]=event
            p['reactions'].append(key)


def after_round(session):
    access_round(session)
    advance_knowledge(session)
    react(session)


def result(state):
    p=state['patronage']
    votes=sum(state['people'][pid]['active'] and state['people'][pid]['allegiance']=='player' for pid in state['government']['council'])
    power=state['government']['officeholder']=='player' and votes>=5
    delivery=state['project']['complete'] and state['project']['maintenance_misses']<2
    reached=state['round']>=p['debrief_round']
    return dict(votes=votes,power=power,delivery=delivery,won=reached and power and delivery,
                ready=reached,round=state['round'],crossings=p['total_crossings'],denied=p['total_denied'],
                tolls=p['total_tolls'],waiting=p['total_waiting'],fund=balance(state,'bridge_fund'),
                label='Mandate secured' if reached and power and delivery else
                      'Power retained; public task failed' if reached and power else
                      'Bridge delivered; fewer than five votes' if reached and delivery and state['government']['officeholder']=='player' else
                      'Bridge delivered; coalition lost' if reached and delivery else
                      'Build a working bridge and a five-vote governing coalition')


def visible_summary(state,viewer='player'):
    """Facts a player can act on, without inspecting opponents' private deals."""
    from .knowledge import public_view
    p=state['patronage']
    facts=public_view(state,viewer)
    # Reconstruct known dependence from observed delivered jobs. Reading the
    # canonical current strength would reveal later undiscovered renewals.
    dependencies={}
    for fact in facts:
        if fact['kind']!='job_response' or fact['terms']['status']!='delivered':continue
        job=fact['terms'];worker=job['worker'];patron=job['holder']
        if patron=='public_board':patron=job['issuer']
        if patron not in state['people'] or patron==worker:continue
        key=patron+'>'+worker;old=dependencies.get(key)
        previous=old['strength']*.9**max(0,fact['round']-old['last_round']) if old else 0.
        dependencies[key]=dict(patron=patron,worker=worker,strength=min(.85,previous+.24*(1.-previous)),last_round=fact['round'],event=fact['id'])
    for d in dependencies.values():d['strength']*=.9**max(0,state['round']-1-d['last_round'])
    return dict(outcome=result(state),facts=facts,blockers=blockers(state),control=control_graph(state),
                jobs=[deepcopy(j) for j in p['last_jobs'] if visible(state,viewer,j['event'])],
                dependencies=list(dependencies.values()))


def validate(state):
    from .accounts import validate as validate_accounts
    p=state['patronage']
    validate_accounts(state)
    people=set(state['people'])
    for name,value in p['rights'].items():
        if name not in ('contract','hiring','access') or value['holder'] not in people|{'public_board'} or value['issuer'] not in ('player','rival') or type(value['active']) is not bool:
            raise ValueError('Invalid institutional right')
        if name=='access' and (value['fee'] not in (1,2) or not set(value['exemptions']).issubset(people) or len(set(value['exemptions']))!=len(value['exemptions'])):
            raise ValueError('Invalid access terms')
    c=p['contract']
    if c and (c['route'] not in ('public','merchant') or c['status'] not in ('active','cancelled','complete') or
              any(type(c[k]) is not int or c[k]<0 for k in ('budget','margin','bonus','paid')) or c['bonus']>c['margin']):
        raise ValueError('Invalid contract')
    if c and c['status']=='active' and balance(state,'escrow:bridge')<c['margin']:
        raise ValueError('Reserved margin cannot be spent twice')
    if c and c['status']=='active' and balance(state,'escrow:bridge')+c['paid']!=c['budget']:
        raise ValueError('Contract escrow must reconcile with earned labor payments')
    if set(p['known'])!=people or set(p['opinions'])!=people:
        raise ValueError('Invalid audience or opinion state')
    for pid,known in p['known'].items():
        if len(known)!=len(set(known)) or not set(known).issubset(p['facts']):
            raise ValueError('Unknown or duplicated evidence reference')
    for fid,fact in p['facts'].items():
        if fid!=fact['id'] or not set(fact['audience']).issubset(people):
            raise ValueError('Invalid fact identity or audience')
        if fact['kind']=='job_response' and (fact['terms'].get('issuer') not in ('player','rival') or fact['terms'].get('worker') not in people):
            raise ValueError('Invalid funded job record')
        if fact['kind']=='exemption' and fact['terms'].get('concession') not in p['facts']:
            raise ValueError('Exemption needs its specific concession record')
    for key,d in p['dependencies'].items():
        if key!=d['patron']+'>'+d['worker'] or d['patron'] not in people or d['worker'] not in people or d['patron']==d['worker'] or not math.isfinite(d['strength']) or not 0<=d['strength']<=1:
            raise ValueError('Invalid dependence edge')
    if c and c['event'] not in p['facts']:
        raise ValueError('Unknown contract record')
    for claim in p['free_claims']:
        if claim['issuer'] not in ('player','rival') or claim['fact'] not in p['facts']:
            raise ValueError('Unknown public promise record')
    for d in p['disclosures']:
        if d['fact'] not in p['facts'] or d['actor'] not in people or not set(d['frontier']).issubset(people) or not set(d['seen']).issubset(people):
            raise ValueError('Unknown disclosure actor or evidence')
    for opinion in p['opinions'].values():
        if set(opinion)!={'player','rival'} or any(not math.isfinite(v) or not -.7<=v<=.7 for v in opinion.values()):
            raise ValueError('Invalid personal benefit record')

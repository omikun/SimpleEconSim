"""Bounded, conditional action forecasts using the real laboratory rules.

Compare one legal move with waiting for five rounds. Both branches keep already
accepted commands and let the existing rival respond. This is a short-horizon
comparison, not an optimal strategy or an unconditional prediction.
"""
from copy import deepcopy
from functools import lru_cache
import json

from .engine import command, step, CommandError
from .model import Session

HORIZON = 5


def _clip(value):
    return max(0.,min(1.,value))


def _measure(state,channel):
    people,gov,rules=state['people'],state['government'],state['rules']
    council=[p for p in gov['council'] if people[p]['active']]
    votes=sum(people[p]['allegiance']=='player' for p in council)
    readiness=0.
    for pid in council:
        p=people[pid];margin=p['pressure']['player']-p['pressure']['rival']
        if p['allegiance']=='player':
            readiness+=_clip(margin/(2*rules['margin_switch']))
        else:
            readiness+=_clip((margin+rules['margin_switch'])/(rules['margin_switch']+rules['margin_entry']))*_clip(p['pressure']['player']/rules['entry'])
    goal=channel if channel in ('upstream','market') else state['project']['package']
    workers=[p for pid,p in people.items() if goal and p['active'] and p['task']==goal
             and p['task_since']<state['round'] and pid not in state['organizers']]
    work=sum(p['skill']=='work' for p in workers);haul=sum(p['skill']=='haul' for p in workers)
    sites=len({p['location'] for p in workers})
    supply=min(work/rules['work_required'],haul/rules['haul_required'],sites/2,1.) if goal else 0.
    task_readiness=0.
    if goal:
        for skill,required in [('work',rules['work_required']),('haul',rules['haul_required'])]:
            value=sum(_clip(p['pressure'][goal]/rules['task_entry']) for pid,p in people.items()
                      if p['active'] and p['skill']==skill and pid not in state['organizers'])
            task_readiness+=min(1.,value/required)
    project=state['project']
    return dict(supporters=[p for p in council if people[p]['allegiance']=='player'],votes=votes,majority=int(votes>=5),office=int(gov['officeholder']=='player'),
                council_readiness=readiness,work=work,haul=haul,supply=supply,
                task_readiness=task_readiness,complete=int(project['complete']),
                failures=int(project.get('failed',False))+int(project['maintenance_misses']>=2),
                streak=project['streak'],breaches=sum(p['status']=='broken' for p in state['promises'])+sum(a['status']=='breached' and a['leader']=='player' for a in state['agreements']),
                margins={p:people[p]['pressure']['player']-people[p]['pressure']['rival'] for p in council})


def _simulate(state,decision_start,channel,action=None):
    session=Session(deepcopy(state),deepcopy(state),tracing=False,decision_start=deepcopy(decision_start))
    if action:
        command(session,'player',action['kind'],**action['params'])
    result=[]
    for _ in range(HORIZON):
        step(session)
        result.append(_measure(session.state,channel))
    return result


def _effects(baseline,branch):
    keys=('votes','majority','office','council_readiness','supply','task_readiness','complete','failures','breaches','streak')
    # The whole path matters: a vote gained then lost is not a durable result.
    gains={k:sum((.85**n)*(b[k]-a[k]) for n,(a,b) in enumerate(zip(baseline,branch))) for k in keys}
    final={k:branch[-1][k]-baseline[-1][k] for k in ('votes','work','haul','complete','failures','breaches')}
    final['stable_votes']=min(p['votes'] for p in branch[-2:])-min(p['votes'] for p in baseline[-2:])
    baseline_stable=set.intersection(*(set(p['supporters']) for p in baseline[-2:]))
    branch_stable=set.intersection(*(set(p['supporters']) for p in branch[-2:]))
    final['extra_stable_supporters']=sorted(branch_stable-baseline_stable)
    final['affected_councillors']=[p for p in branch[-1]['margins'] if branch[-1]['margins'][p]-baseline[-1]['margins'][p]>.025]
    return gains,final


def _candidate_actions(state,channel):
    # All legal direct contacts/allied organizers are considered; no shortlist by
    # opposition margin or degree. Legality includes budgets and pending appeals.
    preview=Session(state,state,tracing=False,decision_start=state)
    for pid,p in sorted(state['people'].items()):
        if not p['active']:continue
        for kind in ('approach','organize','release'):
            params=dict(target=pid) if kind=='release' else dict(target=pid,channel=channel)
            try:
                command(preview,'player',kind,_preview=True,**params)
            except CommandError:
                continue
            yield dict(person=pid,kind=kind,params=params)

    for oid,org in sorted(state['organizations'].items()):
        options=[('agreement',dict(group=oid))]
        if state['government']['officeholder']=='player':
            options.extend(('fund',dict(group=oid,donor=d)) for d in sorted(state['organizations']) if d!=oid)
        for kind,params in options:
            try:command(preview,'player',kind,_preview=True,**params)
            except CommandError:continue
            if org['coordinator']:
                yield dict(person=org['coordinator'],kind=kind,params=params)


def _explanation(state,channel,action,gains,effect):
    pid=action['person'];p=state['people'][pid];name=p['name'].split(' — ')[-1]
    task=channel in ('upstream','market')
    protected=[q for q in effect['extra_stable_supporters'] if state['people'][q]['allegiance']=='player']
    if action['kind']=='fund':title='Choose who gets funded';label='Move one budget share'
    elif action['kind']=='agreement':title='Bargain for conditional support';label='Offer group agreement'
    elif action['kind']=='release':title='Free someone to repair';label='Let them work again'
    elif task:title='Recruit repair help';label='Ask to rally contacts' if action['kind']=='organize' else 'Ask for repair help'
    elif action['kind']=='organize':title='Protect your coalition' if protected else 'Build lasting support';label='Ask to rally contacts'
    elif p['allegiance']=='player':title='Protect existing support';label='Reassure this ally'
    else:title='Build your coalition';label='Ask for support'
    if task:
        result=f"Compared with waiting: {effect['work']:+d} workers and {effect['haul']:+d} haulers ready after {HORIZON} rounds."
        if gains['complete']>0:result='The repair finishes sooner than if you wait.'
        elif gains['supply']>0:result+=' The missing-skill bottleneck improves.'
    elif effect['stable_votes']>0 and protected:
        names=[state['people'][q]['name'].split(' — ')[-1] for q in protected]
        result='Keeps '+', '.join(names[:3])+' backing you when waiting would lose that support. The extra support lasts through both final forecast rounds.'
    elif effect['stable_votes']>0:
        result=f"Compared with waiting: {effect['stable_votes']} more council supporter"+('s' if effect['stable_votes']!=1 else '')+' held across the final two forecast rounds.'
    elif gains['majority']>0:
        result='The forecast holds a five-vote majority for longer than waiting.'
    elif effect['affected_councillors']:
        names=[state['people'][q]['name'].split(' — ')[-1] for q in effect['affected_councillors']]
        result='Support grows at '+', '.join(names[:3])+', but the forecast does not yet secure another lasting vote.'
    else:
        result='This strengthens existing support, but does not yet secure another lasting vote.'
    tradeoffs=[]
    if action['kind']=='fund':
        donor=state['organizations'][action['params']['donor']]['name']
        tradeoffs.append('One share comes from '+donor+'.')
    elif action['kind']=='agreement':
        from .coalitions import pledge_text
        tradeoffs.append('You must deliver: '+pledge_text(state,action['params']['group'])+'.')
    elif action['kind']=='organize':
        tradeoffs.append(f"At most {state['rules']['rally_limit']-p['fatigue']} rallying rounds before a break.")
        if p['task']==state['project']['package'] and p['task'] is not None and p['task_since']<state['round']:
            tradeoffs.append(f"Pulls {name}, a {p['skill']} contributor, off the repair team.")
        else:
            tradeoffs.append(f"Reserves {name}'s time; no repair work until released.")
    elif action['kind']=='release':
        tradeoffs.append(f"{name} stops recruiting contacts.")
    else:tradeoffs.append('One request, not a permanent organizer.')
    if gains['supply']<-.02:tradeoffs.append('Repair staffing becomes less reliable.')
    if gains['failures']>0:tradeoffs.append('The repair misses a deadline or maintenance requirement in this forecast.')
    if gains['breaches']>0:tradeoffs.append('An existing promise breaks in this branch.')
    if gains['office']<0:tradeoffs.append('This branch leaves you out of office for longer.')
    return dict(title=title,action=label,reason=result,detail=' '.join(tradeoffs),
                forecast=dict(horizon=HORIZON,effects=effect,contributions=gains,
                              assumption='You make this one move, then no more moves; Sen follows the current public policy.'))


@lru_cache(maxsize=24)
def _ranked(state_json,start_json,channel):
    state=json.loads(state_json);start=json.loads(start_json)
    if state['ap']['player']==0:return []
    baseline=_simulate(state,start,channel)
    ranked=[]
    for action in _candidate_actions(state,channel):
        branch=_simulate(state,start,channel,action)
        gains,effect=_effects(baseline,branch)
        # Deliberately explicit objective weights, not a claim of optimal play.
        # Quorums, survival, actual work and costly missed deadlines dominate
        # small continuous gains; raw degree and initial opposition are absent.
        political=(80*gains['office']+18*gains['majority']+8*gains['votes']
                   +2*gains['council_readiness']+10*effect['stable_votes'])
        repair=(25*gains['complete']+12*gains['supply']+2*gains['task_readiness']+2*gains['streak'])
        costs=30*gains['failures']+15*gains['breaches']
        score=(repair+.15*political if channel in ('upstream','market') else political+.35*repair)-costs
        if score<=.015:continue
        action.update(score=score,**_explanation(state,channel,action,gains,effect))
        ranked.append(action)
    ranked.sort(key=lambda r:(-r['score'],r['person'],r['kind']))
    # Present distinct alternatives instead of two moves through the same hub.
    selected=[]
    for action in ranked:
        if any(a['person']==action['person'] for a in selected):continue
        selected.append(action)
        if len(selected)==2:break
    return selected


def recommendations(state,channel='player',decision_start=None):
    if channel not in ('player','rival','upstream','market'):raise ValueError('Unknown advice goal')
    # Cache by the complete state and the actual rival information boundary.
    # Cache hits do no simulation; returned advice cannot mutate cached records.
    key=json.dumps(state,sort_keys=True,separators=(',',':'))
    start=json.dumps(decision_start if decision_start is not None else state,sort_keys=True,separators=(',',':'))
    result=deepcopy(_ranked(key,start,channel))
    for n,r in enumerate(result,1):r['number']=n
    return result

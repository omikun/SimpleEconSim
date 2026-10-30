"""Replay two winning routes and a restoration, optionally through the Pygame UI.

Usage: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m
scripts.playtest_people_network_patronage --ui --output-dir outputs/patronage
No world construction, state edits, forced ballots or disabled rival.
"""
import argparse
import json
from pathlib import Path
import time
from people_network.scenario import new_session,validate
from people_network.engine import command,step
from people_network.persistence import save,load,replay
from people_network.model import state_digest
from people_network.patronage import result
from people_network.accounts import account

ROOT=Path(__file__).resolve().parents[1]


def click_label(app,label,index=0):
    app.draw()
    matches=[(rect,enabled,reason) for rect,_,enabled,reason in app.buttons
             if app.button_labels.get(tuple(rect))==label]
    if len(matches)<=index:
        raise AssertionError('UI button not found: '+label)
    rect,enabled,reason=matches[index]
    if not enabled:raise AssertionError(label+': '+reason)
    app.click(rect.center)


def ui_command(app,action):
    kind,params=action['kind'],action['params']
    before=len(app.session.state['actions'])
    if kind in ('organize','appoint','approach','release'):
        click_label(app,'Network')
        app.draw()
        pid=params['target']
        point=next(point for point,q in app.markers if q==pid)
        app.click(point)
        assert app.selected==pid and app.sidebar_mode=='Person'
        label=dict(organize='Rally your contacts for my coalition',appoint='Appoint public-service liaison',
                   approach='Ask for your political support',release='Release from rallying')[kind]
        click_label(app,label)
    elif kind in ('fund','agreement'):
        click_label(app,'Start')
        click_label(app,'Groups: demands and service shares')
        if kind=='fund':
            while app.budget_donor!=params['donor']:
                donor=app.state['organizations'][app.budget_donor]['name']
                click_label(app,'Take a share from: '+donor)
        groups=list(app.state['organizations'])
        click_label(app,'Give one share' if kind=='fund' else 'Agree to conditions',groups.index(params['group']))
    elif kind=='challenge':
        click_label(app,'Council');click_label(app,'Call a confidence vote')
    else:
        click_label(app,'Deals')
        page='Access' if kind in ('grant_access','exempt','buyout_access') else 'Records' if kind in ('audit','free_access') else 'Repair'
        click_label(app,page)
        labels={
            'award_contract':'Use public management' if params.get('route')=='public' else 'Award Yara the contract',
            'hiring_office':{'p16':'Quinn’s job queue','p17':'Rafi’s broad roster','public_board':'Public hiring · 2 personal compensation' if app.state['patronage']['rights'].get('hiring',{}).get('holder','public_board') not in ('public_board','p24') else 'Public hiring · no compensation'}.get(params.get('holder')),
            'completion_bonus':'Reserve 2-credit completion bonus',
            'grant_access':'Yara: two-credit toll concession' if params.get('target')=='p24' else 'Quinn: one-credit toll concession',
            'exempt':'Give Inez a personal exemption',
            'free_access':'Publicly promise free bridge access',
            'audit':'Appoint Amal: independent record access',
            'buyout_access':'Buy out concession · 2 personal credits',
            'cancel_contract':'Cancel · refund unused; 2 personal compensation' if app.state['patronage']['contract'] and app.state['patronage']['contract']['route']=='merchant' else 'Cancel · return unspent public escrow'}
        click_label(app,labels[kind])
    assert len(app.session.state['actions'])==before+1,app.message
    actual=app.session.state['actions'][-1]
    assert actual['kind']==kind,(actual,action)
    for key,value in params.items():assert actual['params'][key]==value,(actual,action)


def run_route(name,output,ui=False,seed=4243):
    rows=json.loads((ROOT/'scenarios/people_network/playthroughs'/f'patronage_{name}.json').read_text())
    app=None
    if ui:
        import pygame
        from client.desktop.network_patronage import PatronageLaboratory
        app=PatronageLaboratory(seed=seed,save_path=output/f'{name}.save.json')
        app.draw();click_label(app,'Play Patronage')
        session=app.session
    else:session=new_session(seed=seed,ruleset='patronage')
    timeline=[];screens=[];started=time.perf_counter()
    for n,row in enumerate(rows):
        for action in row:
            if ui:ui_command(app,action)
            else:command(session,action['issuer'],action['kind'],**action['params'])
        if ui:click_label(app,'End round')
        else:step(session)
        validate(session.state)
        p=session.state['patronage']
        timeline.append(dict(round=n+1,commands=row,outcome=result(session.state),
            officeholder=session.state['government']['officeholder'],streak=session.state['project']['streak'],
            labor_paid=p['contract']['paid'],withheld=p['withheld'],
            escrow=p['accounts']['escrow:bridge'],
            wallets={pid:p['accounts'][account(pid)] for pid in ('player','p24','p16','p08')}))
        if ui and n in (0,2,11):
            app.sidebar_mode='Offers' if n<11 else 'Overview'
            app.deal_page='Repair' if n==0 else 'Access'
            app.draw()
            target=output/f'{name}-round-{n+1}.png';pygame.image.save(app.screen,target);screens.append(target.name)
    assert result(session.state)['won'],result(session.state)
    replay(session)
    save(session,output/f'{name}.save.json')
    assert state_digest(load(output/f'{name}.save.json').state)==state_digest(session.state)
    # The click route must reproduce the same journal as the headless route.
    if ui:
        other=new_session(seed=seed,ruleset='patronage')
        for row in rows:
            for action in row:command(other,action['issuer'],action['kind'],**action['params'])
            step(other)
        assert state_digest(other.state)==state_digest(session.state)
        pygame.quit()
    report=dict(route=name,seed=seed,played_through='Pygame mouse hit testing' if ui else 'headless legal commands',
        rival='active',replay='passed',rounds=len(rows),elapsed_seconds=round(time.perf_counter()-started,3),
        outcome=result(session.state),digest=state_digest(session.state),
        completed_round=session.state['project']['completed_round']+1,
        credit_total=sum(session.state['patronage']['accounts'].values()),
        events=len(session.events),screenshots=screens,timeline=timeline)
    (output/f'{name}.report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/people_network/patronage_playtests'))
    parser.add_argument('--seed',type=int,default=4243)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    for route in ('public','brokers','restore'):
        report=run_route(route,args.output_dir,args.ui,args.seed)
        print(json.dumps({k:report[k] for k in ('route','played_through','outcome','replay','completed_round','credit_total','elapsed_seconds')},indent=2))


if __name__=='__main__':main()

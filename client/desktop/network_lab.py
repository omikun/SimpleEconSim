"""Standalone terrain social-network laboratory. No economic world is constructed."""
import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
import pygame
from people_network.scenario import new_session
from people_network.engine import command, step, CommandError
from people_network.graph import Graph
from people_network.events import explain, causal_chain
from people_network.persistence import save, load, replay
from people_network.terrain import load_terrain
from people_network.insights import overview
from people_network.coalitions import pledge_text, failed_conditions
from client.desktop.network_map import draw as draw_network_map, positions as network_positions, short_name, relationship_width

BG=(15,24,32); PANEL=(22,34,44); TEXT=(230,235,226); MUTED=(153,174,181)
GOLD=(240,197,101); BLUE=(89,185,239); RED=(236,126,116); GREEN=(117,204,165)


class Laboratory:
    def __init__(self,start='governing',seed=4243,save_path=None,ruleset='classic'):
        pygame.init()
        self.screen=pygame.display.set_mode((1440,960),pygame.RESIZABLE)
        pygame.display.set_caption('The Broken Crossing · Network Laboratory')
        self.fonts={n:pygame.font.SysFont('Arial',n) for n in (13,15,17,20,25,32)}
        self.session=new_session(start,seed,ruleset)
        self.terrain=load_terrain()
        self.save_path=Path(save_path or ('outputs/people_network/patronage.json' if ruleset=='patronage' else 'outputs/people_network/laboratory.json'))
        self.selected='p00';self.channel='player';self.overlay=False;self.budget_donor='trade'
        self.zoom=1.;self.pan=[0.,0.];self.drag=None;self.history_index=None
        self.buttons=[];self.markers=[];self.message='Keep five council votes and get the bridge repaired. The numbered people are useful places to start.'
        self.introducing=None;self.briefing=True;self.show_trace=False;self.scroll=0;self.sidebar_mode="Overview";self.map_mode="Terrain";self.insights=overview(self.session.state)

    @property
    def state(self):
        return self.session.state if self.history_index is None else self.session.history[self.history_index]['after']

    def text(self,words,x,y,size=17,color=TEXT):
        self.screen.blit(self.fonts[size].render(str(words),True,color),(x,y))

    def wrap(self,words,x,y,width,size=15,color=MUTED,max_lines=5):
        lines=[];line=''
        for word in str(words).split():
            trial=(line+' '+word).strip()
            if self.fonts[size].size(trial)[0]>width and line:
                lines.append(line);line=word
            else:line=trial
        lines.append(line)
        for n,line in enumerate(lines[:max_lines]):self.text(line,x,y+n*(size+5),size,color)
        return y+min(len(lines),max_lines)*(size+5)

    def button(self,label,rect,action,enabled=True,reason=''):
        rect=pygame.Rect(rect)
        hover=rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen,(48,72,86) if enabled and hover else (34,51,63) if enabled else (27,36,43),rect,border_radius=5)
        font=15 if self.fonts[15].size(label)[0]<=rect.width-18 else 13
        self.text(label,rect.x+9,rect.y+7,font,TEXT if enabled else (105,120,125))
        self.buttons.append((rect,action,enabled,reason))

    def preview(self,kind,params):
        if self.history_index is not None:return False,'Return to Live before taking actions'
        try:
            command(self.session,'player',kind,_preview=True,**params)
            return True,''
        except CommandError as e:return False,str(e)

    def action_button(self,label,kind,params,x,y,width):
        valid,reason=self.preview(kind,params)
        self.button(label,(x,y,width,32),lambda:self.perform(kind,params),valid,reason)

    def perform(self,kind,params):
        try:
            command(self.session,'player',kind,**params)
            name=short_name(self.session.state['people'][params.get('target','player')])
            descriptions=dict(organize=f'{name} will spend time rallying contacts instead of repairing the bridge.',approach=f'Your request to {name} arrives next round; support is not guaranteed.',release=f'{name} is free to help with repair again.',adopt='Repair plan chosen. Now gather workers and haulers.')
            self.message=descriptions.get(kind,f'{kind.capitalize()} accepted.')+f' {self.session.state["ap"]["player"]} actions left.'
        except CommandError as e:self.message=str(e)

    def end_round(self):
        if self.history_index is not None:
            self.message='Return to Live before advancing';return
        old=self.session.state['government']['officeholder']
        step(self.session)
        new=self.session.state['government']['officeholder']
        if new != old:
            self.message=('You lost office. Your relationships remain. Organize five councillors and challenge.' if new=='rival' else
                          'You regained office. Your promises and coalition obligations still apply.')
        elif self.session.state['round']==24:
            self.message='24-round debrief available below. You may keep playing or restart.'
        else:
            info=overview(self.session.state,advise=False)
            self.message=f"Round finished. You now have {len(info['supporters'])} council votes. Ready for repair: {info['work']} workers and {info['haul']} haulers."

    def persist(self,loading=False):
        try:
            if loading:
                replacement=load(self.save_path)
                if replacement.state.get('ruleset','classic')!=self.session.state.get('ruleset','classic'):
                    raise ValueError('This save uses a different ruleset; open its matching laboratory launcher')
                replay(replacement)
                self.session=replacement;self.history_index=None
            else:save(self.session,self.save_path)
            self.message=f'{"Loaded" if loading else "Saved"}: {self.save_path}'
        except (OSError,ValueError) as e:self.message=str(e)

    def export(self):
        try:
            path=self.save_path.with_suffix('.trace.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(self.session.payload(),indent=2)+'\n')
            self.message=f'Exported pressure history and causal events: {path}'
        except OSError as e:self.message=str(e)

    def restart(self,start=None):
        self.session=new_session(start or self.session.state['start'],self.session.state['seed'],self.session.state.get('ruleset','classic'))
        self.history_index=None;self.introducing=None;self.briefing=True;self.sidebar_mode='Overview'
        self.selected='p00';self.channel='player';self.zoom=1.;self.pan=[0.,0.]
        self.message='New laboratory run. Same seed, fresh relationships.'

    def positions(self,map_rect):
        project,points,_=network_positions(self,map_rect)
        return project,points

    def draw_map(self,rect):
        draw_network_map(self,rect)

    def draw_overview(self,x,y,width,height):
        s=self.state;info=self.insights
        self.text('Who can help you?',x,y,25);y+=36
        count=len(info['supporters'])
        self.text(f'You have {count} of 9 council votes.',x,y,20,BLUE);y+=29
        sentence=('Keep at least five to hold office.' if s['government']['officeholder']=='player' else
                  'You have enough votes. Hold five for two rounds, then challenge Sen.' if count>=5 else
                  f'Win {5-count} more vote'+('s' if 5-count!=1 else '')+'; hold five for two rounds to challenge Sen.')
        y=self.wrap(sentence,x,y,width,15,TEXT,2)+9
        if s['government']['officeholder']!='player' and s['government']['support_streak']['player']>=2:
            self.action_button('Call a vote to return to office','challenge',{},x,y,width);y+=42
        pledged=sum(s['organizations'][a['group']]['funding_need'] for a in s['agreements'] if a['leader']=='player')
        broken=sum(a['leader']=='player' and a['status'] in ('breached','repairing') for a in s['agreements'])
        warning=(f'Your agreements need {pledged} shares; only 4 exist. You cannot deliver them all.' if pledged>4 else
                 f'{broken} group agreements need repair; members may withhold support.' if broken else
                 f"Groups request 6 shares; only 4 exist. {len(info['tired'])} organizers need a break soon.")
        y=self.wrap(warning,x,y,width,13,GOLD,2)+4
        self.button('Group demands and public budget',(x,y,width,29),lambda:setattr(self,'sidebar_mode','Groups'));y+=37
        project=s['project']
        if not project['package']:
            y=self.wrap('The bridge is broken. Farmers want access to their fields; traders want access to the market. Choose whom to help first.',x,y,width,15,max_lines=4)+8
            if s['government']['officeholder']=='player':
                half=(width-8)//2
                self.action_button('Help farmers first','adopt',dict(channel='upstream'),x,y,half)
                self.action_button('Help traders first','adopt',dict(channel='market'),x+half+8,y,half);y+=42
            else:y=self.wrap('You can rally support, but only the current government can adopt a repair plan.',x,y,width,13,max_lines=3)+6
        elif not project['complete']:
            self.text(f"Ready: {info['work']}/6 workers, {info['haul']}/4 haulers",x,y,17,GREEN);y+=26
            y=self.wrap('Ask allies to rally repair help. People rallying contacts cannot also work on the bridge.',x,y,width,15,max_lines=3)+8
        else:
            y=self.wrap('The bridge is repaired. Keep two people helping each round to maintain it.',x,y,width,15,GREEN,3)+8
        self.button('Goal: '+dict(player='Keep / win council votes',rival='Help Sen',upstream='Repair for farmers',market='Repair for traders')[self.channel],(x,y,width,30),self.cycle_channel);y+=40
        self.text('5-round comparisons, not guaranteed outcomes',x,y,13,MUTED);y+=25
        for recommendation in info['recommendations']:
            if y+150>height-12:break
            pid=recommendation['person'];name=short_name(s['people'][pid])
            self.text(f"{recommendation['number']}. {name} · {recommendation['title']}",x,y,17,GOLD);y+=25
            y=self.wrap(recommendation['reason'],x,y,width,15,TEXT,3)
            y=self.wrap(recommendation['detail'],x,y,width,13,MUTED,2)+7
            valid,reason=self.preview(recommendation['kind'],recommendation['params'])
            self.button(recommendation['action'],(x,y,width,30),
                        lambda r=recommendation:self.perform(r['kind'],r['params']),valid,reason);y+=43
        if y+48<height:
            self.wrap('Forecast: this move, then five rounds without more moves. Sen keeps responding.',x,y,width,13,MUTED,2)

    def draw_person(self,x,y,width):
        p=self.state['people'][self.selected]
        self.text(p['name'],x,y,25);y+=34
        self.text(f"{p['role']} · "+dict(work='repair worker',haul='hauler')[p['skill']]+' · '+('backs you' if p['allegiance']=='player' else 'backs Sen' if p['allegiance']=='rival' else 'undecided'),x,y,15);y+=25
        for k,label,color in [('player','Support for you',BLUE),('rival','Support for Sen',RED),('upstream',"Farmers' repair",GREEN),('market',"Traders' repair",GOLD)]:
            self.text(label,x,y,13,color)
            pygame.draw.rect(self.screen,(43,58,69),(x+123,y+3,width-175,10),border_radius=4)
            pygame.draw.rect(self.screen,color,(x+123,y+3,int((width-175)*p['pressure'][k]),10),border_radius=4)
            self.text(f"{p['pressure'][k]:.2f}",x+width-43,y-2,13);y+=22
        groups=[o['name'] for o in self.state['organizations'].values() if self.selected in o['members']]
        y=self.wrap('Member: '+', '.join(groups),x,y+4,width,13,max_lines=2)+6
        y=self.wrap('Repair: '+str(p['task'] or 'none')+f" · rallying strain {p['fatigue']}/{self.state['rules']['rally_limit']}"+(' · needs a politics break' if self.state['round']<p['rest_until'] else ''),x,y,width,13,max_lines=2)+5
        self.text('People they can reach',x,y,17);y+=28
        contacts=Graph(self.state).contacts(self.selected)
        # Stable contact layout, independent of terrain coordinates.
        center=(x+width//2,y+43)
        pygame.draw.circle(self.screen,BLUE,center,9)
        for i,pid in enumerate(contacts[:8]):
            angle=2*math.pi*i/min(8,len(contacts))
            point=(int(center[0]+math.cos(angle)*(width/2-45)),int(center[1]+math.sin(angle)*37))
            edge=self.state['edges'][f'{self.selected}>{pid}']
            pygame.draw.line(self.screen,MUTED,center,point,relationship_width(edge,self.channel))
            pygame.draw.circle(self.screen,RED if self.state['people'][pid]['allegiance']=='rival' else GREEN,point,6)
            self.text(self.state['people'][pid]['name'].split(' — ')[-1],point[0]-16,point[1]-19,13)
            self.markers.append((point,pid))
        y+=103
        self.text(f'{len(contacts)} outgoing contacts · Tab cycles all people',x,y,13,MUTED);y+=23
        self.button('Goal: '+dict(player='Your candidacy',rival="Sen's candidacy",upstream='Upstream repair',market='Market repair')[self.channel],(x,y,width,30),self.cycle_channel);y+=38
        y=self.wrap('Ask for support speaks to this person. Ask to rally asks them to spend work time recruiting their contacts.',x,y,width,13,MUTED,3)+7
        half=(width-8)//2
        for row in [
            [('Ask for support','approach',dict(target=self.selected,channel=self.channel)),('Ask to rally','organize',dict(target=self.selected,channel=self.channel))],
            [('Stop rallying','release',dict(target=self.selected)),('Appoint liaison','appoint',dict(target=self.selected))],
            [('Promise liaison','promise',dict(target=self.selected,term='liaison')),('Promise package','promise',dict(target=self.selected,term=self.channel if self.channel in ('upstream','market') else 'upstream'))],
            [('Help farmers first','adopt',dict(channel='upstream')),('Help traders first','adopt',dict(channel='market'))],
            [('Call council vote','challenge',{}),('Work personally','work',{})]]:
            for col,(label,kind,params) in enumerate(row):self.action_button(label,kind,params,x+col*(half+8),y,half)
            y+=38
        self.button('Introduce selected to…',(x,y,width,30),self.begin_introduction,self.history_index is None);y+=37
        pending=[v for v in self.state['promises'] if v['issuer']=='player' and v['status']=='pending']
        if pending:
            promise=pending[0]
            self.action_button('Renounce oldest promise','renounce',dict(promise=promise['id']),x,y,width);y+=36
        return y

    def cycle_donor(self):
        groups=list(self.state['organizations']);self.budget_donor=groups[(groups.index(self.budget_donor)+1)%len(groups)]

    def draw_groups(self,x,y,width,height):
        s=self.state;gov=s['government']
        self.text('Who wants what?',x,y,25);y+=36
        y=self.wrap('4 budget shares; groups ask for 6. Honor agreements for two rounds, then keep delivering. Breaches can cost votes.',x,y,width,15,TEXT,3)+8
        donor=s['organizations'][self.budget_donor]['name']
        self.button('Take a share from: '+donor,(x,y,width,31),self.cycle_donor);y+=40
        for oid,org in s['organizations'].items():
            info=self.insights['groups'][oid]
            self.text(f"{org['name']} · {info['allocation']}/{info['need']} shares",x,y,15,GOLD);y+=23
            y=self.wrap(org['demand_label'],x,y,width,13,MUTED,1)
            y=self.wrap(info['asks'],x,y,width,13,TEXT,2)
            a=info['agreement'];status=(a['status']+f" {a['met_streak']}/2" if a and a['status'] in ('provisional','repairing') else a['status'] if a else 'no agreement')
            self.text(f"You: {info['standing']} / Sen: {org['band']['rival']} · {status}",x,y,13,MUTED);y+=24
            half=(width-8)//2
            self.action_button('Give one share','fund',dict(group=oid,donor=self.budget_donor),x,y,half)
            self.action_button('Agree to conditions','agreement',dict(group=oid),x+half+8,y,half);y+=44
        pledged=sum(s['organizations'][a['group']]['funding_need'] for a in s['agreements'] if a['leader']=='player')
        if y+40<height:self.wrap(f'Your agreements require {pledged} of 4 shares. '+('You cannot honor them all at once.' if pledged>4 else 'Members still choose their votes individually.'),x,y,width,13,GOLD,2)

    def draw_council(self,x,y,width):
        gov=self.state['government']
        self.text('The nine-person council',x,y,25);y+=38
        y=self.wrap('A challenge needs five commitments for two rounds. The incumbent gets one response round.',x,y,width,15,max_lines=3)+12
        for pid in gov['council']:
            p=self.state['people'][pid]
            self.button(p['name']+' · '+('backs you' if p['allegiance']=='player' else 'backs Sen' if p['allegiance']=='rival' else 'undecided'),(x,y,width,32),lambda pid=pid:self.inspect_person(pid))
            y+=34
            withheld=failed_conditions(self.state,pid,'player')
            self.text('Withholding: group agreement broken' if withheld else 'Both sides are close' if abs(p['pressure']['player']-p['pressure']['rival'])<.2 else 'Clear preference for now',x+8,y,13,GOLD if withheld else MUTED);y+=27
        self.text('Office: '+gov['officeholder'],x,y,17,GOLD);y+=29
        self.action_button('Request a confidence vote','challenge',{},x,y,width);y+=42
        if gov['challenge']:
            y=self.wrap(f"Pending challenge by {gov['challenge']['candidate']}; resolves after round {gov['challenge']['due']+1}.",x,y,width,15,GOLD,3)
        transfers=[e for e in self.session.events if e['kind']=='office_transfer' and e['round']<self.state['round']]
        for e in transfers[-4:]:
            y=self.wrap(self.event_label(e),x,y+8,width,13,max_lines=2)

    def inspect_person(self,pid):
        self.selected=pid;self.sidebar_mode='Person'

    def draw_promises(self,x,y,width):
        self.text('Obligations survive office.',x,y,25);y+=42
        y=self.wrap('A promise changes local attraction. Honor or breach changes trust in the promisor. Losing office does not erase it.',x,y,width,15,max_lines=4)+18
        for p in self.state['promises'][-8:]:
            name=self.state['people'][p['beneficiary']]['name']
            y=self.wrap(f"{p['issuer']} to {name}: {p['term']} · {p['status']}",x,y,width,17,TEXT,2)
            self.text('Due: '+(f"round {p['due']+1}" if p['due'] is not None else 'two rounds after taking office'),x,y,13,MUTED);y+=25
            if p['issuer']=='player' and p['status']=='pending':
                self.action_button('Renounce this promise','renounce',dict(promise=p['id']),x,y,width);y+=40
            else:y+=12
        if not self.state['promises']:self.wrap('Select a contact in Person view to negotiate a package or liaison appointment.',x,y,width,17,max_lines=4)

    def draw_why(self,x,y,width,height):
        y=self.draw_history(x,y,width)+20
        y=self.wrap('People hear from contacts they trust, weigh the plan against their own needs, and hear from Sen too. These numbers explain the change in this run; they do not guarantee a vote.',x,y,width,15,max_lines=5)+16
        self.text('What changed and why',x,y,20);y+=32
        events=[e for e in self.session.events if e['round']<self.state['round'] and e['kind'] not in ('action','structural_change','project_progress')]
        relevant=[e for e in events if e['subject']==self.selected] or events
        if relevant:
            for e in causal_chain(self.session,relevant[-1]['id']):
                if y+50>height:break
                y=self.wrap(self.event_label(e),x,y,width,13,TEXT,2)+8
        self.button('Export full causal history',(x,min(y+16,height-60),width,32),self.export)

    def cycle_channel(self):
        channels=['player','upstream','market'];self.channel=channels[(channels.index(self.channel)+1)%len(channels)]

    def begin_introduction(self):
        self.introducing=self.selected;self.message='Choose the other person to introduce. Both must support you.'

    def select(self,pid):
        if self.introducing:
            first=self.introducing;self.introducing=None
            self.perform('introduce',dict(target=first,other=pid))
        self.selected=pid;self.sidebar_mode='Person'

    def draw_history(self,x,y,width):
        self.text('Why did this change?',x,y,20);y+=29
        if self.session.history:
            end=self.history_index if self.history_index is not None else len(self.session.history)-1
            info=explain(self.session,self.selected,end=end)
            channel=self.channel
            p=info['channels'][channel]
            y=self.wrap(f"Rounds {info['rounds'][0]+1}–{end+1}: {channel} {p['before']:.2f} → {p['after']:.2f}",x,y,width,15,TEXT,2)
            self.text(f"Contacts {p['incoming']:+.3f} · appeals {p['source']:+.3f}",x,y,13);y+=21
            self.text(f"Interests {p['anchor']:+.3f} · decay {p['decay']:+.3f}",x,y,13);y+=21
            interests=p['interest_components']
            if interests['group'] or interests['agreement']:
                self.text(f"Group delivery {interests['group']:+.3f} · agreements {interests['agreement']:+.3f}",x,y,13);y+=21
            self.text(f"Opposition {p['opposition']:+.3f} · cap {p['clamp']:+.3f}",x,y,13);y+=21
            edges=list(p['edges'].items())[:2]
            for eid,value in edges:
                source=self.session.history[end]['before']['edges'][eid]['source']
                self.text(f"{self.state['people'][source]['name']}: {value:+.3f}",x,y,13,MUTED);y+=19
        else:y=self.wrap('End a round to inspect accumulated pressure and its causes.',x,y,width,15,max_lines=2)
        return y

    def event_label(self,e):
        people=self.session.state['people']
        def name(pid):return people.get(pid,{}).get('name',str(pid)).replace('You — ','').replace('Rival — ','')
        subject=e['subject'];kind=e['kind'];value=e['after']
        if kind=='action':
            a=value;params=a['params'];target=params.get('target',a['issuer'])
            verb=dict(approach='appealed to',organize='organized with',promise='made a promise to',
                      appoint='appointed',release='released',introduce='introduced').get(a['kind'],a['kind'])
            if a['kind']=='fund':
                text=f"{name(a['issuer'])} moved a service share to "+self.state['organizations'][params['group']]['name']
            elif a['kind']=='agreement':
                text=f"{name(a['issuer'])} offered terms to "+self.state['organizations'][params['group']]['name']
            else:text=f"{name(a['issuer'])} {verb} {name(target)}"
        elif kind=='allegiance' and e.get('withheld_for'):
            groups=', '.join(self.state['organizations'][g]['name'] for g in e['withheld_for'])
            text=f"{name(subject)} withheld support: agreement with {groups} was broken"
        elif kind=='allegiance':text=f"{name(subject)} "+('withdrew from a coalition' if value is None else f"joined {name(value)}'s coalition")
        elif kind=='boundary':text=f"{name(subject)} "+('became contested' if value else 'left the contested zone')
        elif kind=='commitment':text=f"{name(subject)} "+(f"committed to {value} repair" if value else 'withdrew from repair')
        elif kind=='office_transfer':text=f"{name(value)} took office from {name(e['before'])}"
        elif kind=='council_vote':text=f"Council vote: {name(value)} holds office"
        elif kind=='majority':text=f"{name(subject)} "+('secured a council majority' if value else 'lost the council majority')
        elif kind=='group_mood':text=self.state['organizations'][e['group']]['name']+' is '+str(value)+' with '+name(e['leader'])
        elif kind.startswith('agreement_'):
            text=kind.replace('_',' ')+' · '+self.state['organizations'].get(e.get('group'),{}).get('name','group')
        elif kind=='organizer_exhausted':text=name(e['person'])+' needs a break from rallying'
        elif kind=='promise_result':
            promise=next((p for p in self.session.state['promises'] if p['id']==subject),None)
            text=f"Promise {value}"+(f" to {name(promise['beneficiary'])}" if promise else '')
        elif kind=='structural_change':
            if subject.startswith('source:'):
                text=f"{name(subject.split(':',1)[1])} "+('began organizing' if value else 'stopped organizing')
            elif '>' in subject:
                sender,target=subject.split('>',1)
                direction='fell' if isinstance(e['before'],dict) and isinstance(value,dict) and value.get('governing',1)<e['before'].get('governing',0) else 'changed'
                text=f"{name(target)}'s trust in {name(sender)} {direction}"
            elif subject=='budget':
                receivers=[g for g,v in value.items() if v>e['before'][g]]
                donors=[g for g,v in value.items() if v<e['before'][g]]
                text='One share: '+self.state['organizations'][donors[0]]['name']+' → '+self.state['organizations'][receivers[0]]['name']
            elif subject=='project':text=f"{value['package'].capitalize()} repair adopted"
            else:text=e.get('reason','A relationship or obligation changed')
        else:text=kind.replace('_',' ').capitalize()+' · '+(name(subject) if subject in people else 'crossing' if subject=='project' else 'community')
        return f"{e['round']+1} · {text}"

    def draw(self):
        w,h=self.screen.get_size();self.buttons=[];self.markers=[];self.screen.fill(BG)
        self.insights=overview(self.state,self.channel,self.session.decision_start if self.history_index is None else self.state,advise=self.history_index is None)
        sidebar=410 if w>=1300 else 370;map_width=w-sidebar-28
        self.text('THE BROKEN CROSSING',20,14,25)
        holder=self.state['government']['officeholder']
        council=self.state['government']['council'];support=sum(self.state['people'][p]['allegiance']=='player' for p in council)
        self.text(f"Round {self.state['round']} · {'Governing' if holder=='player' else 'Opposition'} · Your council {support}/9 · Actions {self.session.state['ap']['player']}/2",20,49,17,BLUE if holder=='player' else GOLD)
        labels=[('End round',self.end_round),('Save',self.persist),('Load',lambda:self.persist(True)),('Export',self.export),('Restart',self.restart),('Other start',lambda:self.restart('displaced' if self.session.state['start']=='governing' else 'governing'))]
        header_width=min(100,(map_width-178)//6)
        for i,(label,action) in enumerate(labels):self.button(label,(20+i*(header_width+8),79,header_width,32),action)
        self.button('Help',(map_width-92,79,92,32),lambda:setattr(self,'briefing',True))
        x=map_width+24;pygame.draw.rect(self.screen,PANEL,(x-12,0,sidebar+16,h))
        tabs=(('Start','Overview'),('Deals','Offers'),('Brokers','Power'),('Council','Council'),('Jobs','Jobs'),('Why?','Why?')) if self.state.get('ruleset')=='patronage' else (('Start','Overview'),('People','Person'),('Groups','Groups'),('Council','Council'),('Pledges','Promises'),('Why?','Why?'))
        for i,(label,mode) in enumerate(tabs):
            self.button(label,(x+i*((sidebar-22)//6),12,(sidebar-28)//6,30),lambda mode=mode:setattr(self,'sidebar_mode',mode))
        if self.sidebar_mode=='Overview':self.draw_overview(x,60,sidebar-22,h)
        elif self.sidebar_mode=='Person':
            y=self.draw_person(x,54,sidebar-22)
            if y+165<h:self.draw_history(x,y+8,sidebar-22)
        elif self.sidebar_mode=='Groups':self.draw_groups(x,60,sidebar-22,h)
        elif self.sidebar_mode=='Council':self.draw_council(x,60,sidebar-22)
        elif self.sidebar_mode=='Promises':self.draw_promises(x,60,sidebar-22)
        elif self.sidebar_mode=='Offers':self.draw_offers(x,60,sidebar-22,h)
        elif self.sidebar_mode=='Jobs':self.draw_jobs(x,60,sidebar-22,h)
        elif self.sidebar_mode=='Power':self.draw_power(x,60,sidebar-22,h)
        else:self.draw_why(x,60,sidebar-22,h)
        objective=('Keep five council votes to stay in office.' if holder=='player' else 'Build a five-vote coalition to return to office.')
        self.text(objective,22,126,20,GOLD)
        self.text('Win after round 12: a working bridge, office, and five council votes.' if self.state.get('ruleset')=='patronage' else 'The bridge needs help. Farmers and traders disagree about whom repairs should serve first.',22,155,15,TEXT)
        map_rect=pygame.Rect(18,187,map_width-18,h-377)
        self.boundaries=set(Graph(self.state).boundary_edges())
        self.draw_map(map_rect)
        y=map_rect.bottom+12
        proj=self.state['project']
        status=('Completed'+(' late' if proj.get('failed') else '') if proj['complete'] else 'Deadline missed; work continues' if proj.get('failed') else 'Awaiting adoption' if not proj['package'] else f"Work streak {proj['streak']}/3 · deadline round {proj['deadline']+1}")
        self.text('Crossing · '+str(proj['package'] or 'choose a package')+' · '+status,20,y,17,GREEN);y+=27
        self.wrap(self.message,20,y,map_width-40,15,TEXT,2);y+=44
        self.button('‹ History',(20,y,100,29),lambda:self.scrub(-1),bool(self.session.history))
        self.button('History ›',(128,y,100,29),lambda:self.scrub(1),bool(self.session.history))
        self.button('Live',(236,y,68,29),lambda:setattr(self,'history_index',None))
        self.button('Causes',(312,y,86,29),lambda:setattr(self,'show_trace',not self.show_trace))
        self.text('LIVE' if self.history_index is None else f'Viewing round {self.history_index+1}',410,y+6,13,GOLD);y+=38
        significant=[e for e in self.session.events if e['kind'] not in ('action','project_progress','structural_change') and e['round']<self.state['round'] and self.event_visible(e)]
        if self.show_trace and significant:
            relevant=[e for e in significant if e['subject']==self.selected] or significant
            events=causal_chain(self.session,relevant[-1]['id'])
        else:events=list(reversed(significant))
        for event in [e for e in events if self.event_visible(e)][:max(1,(h-y-14)//21)]:
            self.text(self.event_label(event)[:max(30,(map_width-40)//8)],20,y,13,MUTED);y+=21
        challenge=self.state['government']['challenge']
        if challenge:self.text(f"COUNCIL VOTE scheduled for round {challenge['due']+1}",20,112,13,GOLD)
        for rect,_,enabled,reason in self.buttons:
            if not enabled and rect.collidepoint(pygame.mouse.get_pos()) and reason:
                pygame.draw.rect(self.screen,BG,(18,h-34,map_width-18,30));self.text(reason,25,h-28,13,GOLD)
        if self.briefing:
            self.buttons=[]
            self.draw_briefing(w,h)
        pygame.display.flip()

    def draw_briefing(self,w,h):
        shade=pygame.Surface((w,h),pygame.SRCALPHA);shade.fill((4,12,18,210));self.screen.blit(shade,(0,0))
        box=pygame.Rect(w//2-370,h//2-230,740,460);pygame.draw.rect(self.screen,PANEL,box,border_radius=12)
        self.text('Keep support. Repair the bridge.',box.x+28,box.y+25,32)
        paragraphs=[
            'A flood broke the bridge. Farmers want field access first; traders want market access first.',
            'Keep five of nine council votes. The seats span all four communities.',
            'GROUPS: You have 4 service-budget shares. Their requests total 6. Moving a share helps one group and costs another.',
            'AGREEMENTS: Deliver the terms for two rounds, then keep doing so. Broken agreements can cost votes and survive changes of government.',
            'RALLYING: An ally recruits contacts instead of doing repairs. After three active rounds they need two rounds away from campaigning.',
            'ASK FOR SUPPORT talks to one person. The Overview suggests moves; Network shows everyone.',
            'Two actions per round. Space advances. If overthrown, rebuild a coalition and return.'
        ]
        y=box.y+78
        for paragraph in paragraphs:y=self.wrap(paragraph,box.x+28,y,680,17,TEXT,2)+5
        self.button('Enter the laboratory',(box.x+230,box.bottom-54,280,34),lambda:setattr(self,'briefing',False))

    def event_visible(self,event):
        return True

    def scrub(self,delta):
        if not self.session.history:return
        current=len(self.session.history) if self.history_index is None else self.history_index
        self.history_index=max(0,min(len(self.session.history)-1,current+delta))

    def click(self,position):
        """The same hit testing serves native mouse events and UI playtests."""
        for rect,action,enabled,reason in reversed(self.buttons):
            if rect.collidepoint(position):
                if enabled:action()
                elif reason:self.message=reason
                return
        if not self.briefing:
            nearby=sorted((math.dist(point,position),pid) for point,pid in self.markers)
            if nearby and nearby[0][0]<18:self.select(nearby[0][1])

    def run(self,screenshot=None):
        if screenshot:
            self.briefing=False;self.draw();pygame.image.save(self.screen,screenshot);pygame.quit();return
        clock=pygame.time.Clock();running=True
        while running:
            self.draw()
            for event in pygame.event.get():
                if event.type==pygame.QUIT:running=False
                elif event.type==pygame.VIDEORESIZE:
                    self.screen=pygame.display.set_mode((max(1100,event.w),max(800,event.h)),pygame.RESIZABLE)
                elif event.type==pygame.KEYDOWN:
                    if event.key==pygame.K_ESCAPE:
                        if self.briefing:self.briefing=False
                        elif self.introducing:self.introducing=None
                        elif self.history_index is not None:self.history_index=None
                    elif event.key==pygame.K_F1:self.briefing=not self.briefing
                    elif not self.briefing:
                        if event.key in (pygame.K_SPACE,pygame.K_n):self.end_round()
                        elif event.key==pygame.K_TAB:
                            ids=sorted(self.state['people']);self.select(ids[(ids.index(self.selected)+1)%len(ids)])
                        elif event.key==pygame.K_LEFT:self.scrub(-1)
                        elif event.key==pygame.K_RIGHT:self.scrub(1)
                elif event.type==pygame.MOUSEBUTTONDOWN:
                    if event.button==1:
                        self.click(event.pos)
                    elif event.button==3:self.drag=event.pos
                elif event.type==pygame.MOUSEBUTTONUP and event.button==3:self.drag=None
                elif event.type==pygame.MOUSEMOTION and self.drag and not self.briefing:
                    self.pan[0]+=event.rel[0];self.pan[1]+=event.rel[1]
                elif event.type==pygame.MOUSEWHEEL and not self.briefing:
                    self.zoom=max(.55,min(2.8,self.zoom*(1.1**event.y)))
            clock.tick(30)
        pygame.quit()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',choices=['governing','displaced'],default='governing')
    parser.add_argument('--seed',type=int,default=4243)
    parser.add_argument('--ruleset',choices=['classic','patronage'],default='classic')
    parser.add_argument('--save-path',type=Path)
    parser.add_argument('--screenshot',type=Path,help='Render one frame for visual verification')
    args=parser.parse_args()
    if args.ruleset=='patronage':
        from .network_patronage import PatronageLaboratory
        app=PatronageLaboratory(args.start,args.seed,args.save_path)
    else:app=Laboratory(args.start,args.seed,args.save_path)
    app.run(args.screenshot)


if __name__=='__main__':main()

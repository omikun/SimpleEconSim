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

BG=(15,24,32); PANEL=(22,34,44); TEXT=(230,235,226); MUTED=(153,174,181)
GOLD=(240,197,101); BLUE=(89,185,239); RED=(236,126,116); GREEN=(117,204,165)


class Laboratory:
    def __init__(self,start='governing',seed=4243,save_path=None):
        pygame.init()
        self.screen=pygame.display.set_mode((1440,960),pygame.RESIZABLE)
        pygame.display.set_caption('The Broken Crossing · Network Laboratory')
        self.fonts={n:pygame.font.SysFont('Arial',n) for n in (13,15,17,20,25,32)}
        self.session=new_session(start,seed)
        self.terrain=load_terrain()
        self.save_path=Path(save_path or 'outputs/people_network/laboratory.json')
        self.selected='p00';self.channel='player';self.overlay=False
        self.zoom=1.;self.pan=[0.,0.];self.drag=None;self.history_index=None
        self.buttons=[];self.markers=[];self.message='Start with an organizer or a councillor. Space ends a round.'
        self.introducing=None;self.briefing=True;self.show_trace=False;self.scroll=0;self.sidebar_mode="Person"

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
        self.text(label,rect.x+9,rect.y+7,15,TEXT if enabled else (105,120,125))
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
            self.message=f'{kind.capitalize()} accepted. {self.session.state["ap"]["player"]} actions remain.'
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
        else:self.message='Pressure propagated. Inspect a person to see the contributions.'

    def persist(self,loading=False):
        try:
            if loading:
                replacement=load(self.save_path)
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
        self.session=new_session(start or self.session.state['start'],self.session.state['seed'])
        self.history_index=None;self.introducing=None;self.briefing=True
        self.message='New laboratory run. Same seed, fresh relationships.'

    def positions(self,map_rect):
        scale=min(map_rect.width/1000,map_rect.height/800)*self.zoom
        center=map_rect.center
        def project(point):return (int(center[0]+(point[0]-500)*scale+self.pan[0]),int(center[1]+(point[1]-400)*scale+self.pan[1]))
        points={}
        for loc in self.state['locations']:
            members=[pid for pid,p in sorted(self.state['people'].items()) if p['location']==loc]
            anchor=self.terrain['anchors'][loc]
            for i,pid in enumerate(members):
                angle=2*math.pi*i/len(members)
                radius=36+(i%2)*15
                points[pid]=project((anchor[0]+math.cos(angle)*radius,anchor[1]+math.sin(angle)*radius))
        return project,points

    def draw_map(self,rect):
        self.screen.set_clip(rect)
        pygame.draw.rect(self.screen,(32,64,80),rect)
        project,points=self.positions(rect)
        for cell in self.terrain['cells']:
            poly=[project(p) for p in cell['polygon']]
            if len(poly)>=3:
                pygame.draw.polygon(self.screen,cell['color'],poly)
                pygame.draw.polygon(self.screen,(55,77,69),poly,1)
        for river in self.terrain['rivers']:
            pygame.draw.line(self.screen,(87,157,187),project(river[0]),project(river[1]),2)
        town=project(self.terrain['anchors']['town']);up=project(self.terrain['anchors']['village'])
        pygame.draw.line(self.screen,GOLD,up,town,3)
        self.text('Shared crossing',(up[0]+town[0])//2-55,(up[1]+town[1])//2,13,GOLD)
        graph=Graph(self.state)
        for eid,e in sorted(graph.edges.items()):
            if not e['available']:continue
            focus=self.selected in (e['source'],e['target'])
            a,b=points[e['source']],points[e['target']]
            if focus or self.overlay:
                boundary=eid in self.boundaries
                color=GOLD if boundary else (158,198,193) if focus else (78,107,103)
                pygame.draw.line(self.screen,color,a,b,2 if focus else 1)
                if focus:
                    dx,dy=b[0]-a[0],b[1]-a[1];length=max(1,math.hypot(dx,dy))
                    tip=(int(b[0]-dx/length*12),int(b[1]-dy/length*12))
                    pygame.draw.polygon(self.screen,color,[tip,(tip[0]-int(dx/length*7-dy/length*4),tip[1]-int(dy/length*7+dx/length*4)),(tip[0]-int(dx/length*7+dy/length*4),tip[1]-int(dy/length*7-dx/length*4))])
        for loc,data in self.state['locations'].items():
            anchor=project(self.terrain['anchors'][loc]);self.text(data['name'],anchor[0]-72,anchor[1]-86,17,TEXT)
        for pid,p in sorted(self.state['people'].items()):
            point=points[pid];a,b=p['pressure']['player'],p['pressure']['rival']
            color=BLUE if a-b>.10 else RED if b-a>.10 else GOLD if min(a,b)>.3 else MUTED
            radius=11 if pid==self.selected else 8
            if pid in self.state['government']['council']:
                pygame.draw.circle(self.screen,TEXT,point,radius+3,1)
            if p['contested']:pygame.draw.circle(self.screen,GOLD,point,radius+5,2)
            pygame.draw.circle(self.screen,color,point,radius)
            if pid==self.selected or pid in ('player','rival'):
                self.text(p['name'].split(' — ')[-1],point[0]+12,point[1]-8,13)
            if rect.collidepoint(point):self.markers.append((point,pid))
        self.screen.set_clip(None)
        self.text('BLUE  your pressure    CORAL  rival    GOLD  contested / boundary',rect.x+12,rect.bottom-48,13)
        self.text('White ring: councillor · click a person · wheel zoom · right-drag pan',rect.x+12,rect.bottom-27,13)

    def draw_person(self,x,y,width):
        p=self.state['people'][self.selected]
        self.text(p['name'],x,y,25);y+=34
        self.text(f"{p['role']} · {p['skill']} · {p['allegiance'] or 'undecided'}",x,y,15);y+=25
        for k,label,color in [('player','Your pressure',BLUE),('rival','Rival pressure',RED),('upstream','Upstream repair',GREEN),('market','Market repair',GOLD)]:
            self.text(label,x,y,13,color)
            pygame.draw.rect(self.screen,(43,58,69),(x+123,y+3,width-175,10),border_radius=4)
            pygame.draw.rect(self.screen,color,(x+123,y+3,int((width-175)*p['pressure'][k]),10),border_radius=4)
            self.text(f"{p['pressure'][k]:.2f}",x+width-43,y-2,13);y+=22
        groups=[o['name'] for o in self.state['organizations'].values() if self.selected in o['members']]
        y=self.wrap('Member: '+', '.join(groups),x,y+4,width,13,max_lines=2)+6
        y=self.wrap('Work commitment: '+str(p['task'] or 'none')+(' · effort reserved for organizing' if self.selected in self.state['organizers'] else ''),x,y,width,13,max_lines=2)+5
        self.text('Immediate contacts',x,y,17);y+=28
        contacts=Graph(self.state).contacts(self.selected)
        # Stable contact layout, independent of terrain coordinates.
        center=(x+width//2,y+43)
        pygame.draw.circle(self.screen,BLUE,center,9)
        for i,pid in enumerate(contacts[:8]):
            angle=2*math.pi*i/min(8,len(contacts))
            point=(int(center[0]+math.cos(angle)*(width/2-45)),int(center[1]+math.sin(angle)*37))
            pygame.draw.line(self.screen,MUTED,center,point,1)
            pygame.draw.circle(self.screen,RED if self.state['people'][pid]['allegiance']=='rival' else GREEN,point,6)
            self.text(self.state['people'][pid]['name'].split(' — ')[-1],point[0]-16,point[1]-19,13)
            self.markers.append((point,pid))
        y+=103
        self.text(f'{len(contacts)} outgoing contacts · Tab cycles all people',x,y,13,MUTED);y+=23
        self.button('Goal: '+dict(player='Your candidacy',rival="Sen's candidacy",upstream='Upstream repair',market='Market repair')[self.channel],(x,y,width,30),self.cycle_channel);y+=38
        half=(width-8)//2
        for row in [
            [('Appeal','approach',dict(target=self.selected,channel=self.channel)),('Organize','organize',dict(target=self.selected,channel=self.channel))],
            [('Release effort','release',dict(target=self.selected)),('Appoint liaison','appoint',dict(target=self.selected))],
            [('Promise liaison','promise',dict(target=self.selected,term='liaison')),('Promise package','promise',dict(target=self.selected,term=self.channel if self.channel in ('upstream','market') else 'upstream'))],
            [('Adopt upstream','adopt',dict(channel='upstream')),('Adopt market','adopt',dict(channel='market'))],
            [('Call council vote','challenge',{}),('Work personally','work',{})]]:
            for col,(label,kind,params) in enumerate(row):self.action_button(label,kind,params,x+col*(half+8),y,half)
            y+=38
        self.button('Introduce selected to…',(x,y,width,30),self.begin_introduction,self.history_index is None);y+=37
        pending=[v for v in self.state['promises'] if v['issuer']=='player' and v['status']=='pending']
        if pending:
            promise=pending[0]
            self.action_button('Renounce oldest promise','renounce',dict(promise=promise['id']),x,y,width);y+=36
        return y

    def draw_council(self,x,y,width):
        gov=self.state['government']
        self.text('The nine-person council',x,y,25);y+=38
        y=self.wrap('A challenge needs five commitments for two rounds. The incumbent gets one response round.',x,y,width,15,max_lines=3)+12
        for pid in gov['council']:
            p=self.state['people'][pid]
            self.button(p['name']+' · '+str(p['allegiance'] or 'undecided'),(x,y,width,32),lambda pid=pid:self.inspect_person(pid))
            y+=34
            self.text(f"Your pressure {p['pressure']['player']:.2f} / rival {p['pressure']['rival']:.2f}",x+8,y,13,MUTED);y+=27
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
        y=self.wrap('Pressure propagates along trusted channels. Interests anchor it; decay and opposing pressure resist it. Contributions describe this run, not a counterfactual proof.',x,y,width,15,max_lines=5)+16
        self.text('Recent inflection points',x,y,20);y+=32
        events=[e for e in self.session.events if e['round']<self.state['round'] and e['kind'] not in ('action','structural_change','project_progress')]
        relevant=[e for e in events if e['subject']==self.selected] or events
        if relevant:
            for e in causal_chain(self.session,relevant[-1]['id']):
                if y+50>height:break
                y=self.wrap(self.event_label(e),x,y,width,13,TEXT,2)+8
        self.button('Export full causal history',(x,min(y+16,height-60),width,32),self.export)

    def cycle_channel(self):
        channels=['player','rival','upstream','market'];self.channel=channels[(channels.index(self.channel)+1)%4]

    def begin_introduction(self):
        self.introducing=self.selected;self.message='Choose the other person to introduce. Both must support you.'

    def select(self,pid):
        if self.introducing:
            first=self.introducing;self.introducing=None
            self.perform('introduce',dict(target=first,other=pid))
        self.selected=pid

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
            text=f"{name(a['issuer'])} {verb} {name(target)}"
        elif kind=='allegiance':text=f"{name(subject)} "+('withdrew from a coalition' if value is None else f"joined {name(value)}'s coalition")
        elif kind=='boundary':text=f"{name(subject)} "+('became contested' if value else 'left the contested zone')
        elif kind=='commitment':text=f"{name(subject)} "+(f"committed to {value} repair" if value else 'withdrew from repair')
        elif kind=='office_transfer':text=f"{name(value)} took office from {name(e['before'])}"
        elif kind=='council_vote':text=f"Council vote: {name(value)} holds office"
        elif kind=='majority':text=f"{name(subject)} "+('secured a council majority' if value else 'lost the council majority')
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
            elif subject=='project':text=f"{value['package'].capitalize()} repair adopted"
            else:text=e.get('reason','A relationship or obligation changed')
        else:text=kind.replace('_',' ').capitalize()+' · '+(name(subject) if subject in people else 'crossing' if subject=='project' else 'community')
        return f"{e['round']+1} · {text}"

    def draw(self):
        w,h=self.screen.get_size();self.buttons=[];self.markers=[];self.screen.fill(BG)
        sidebar=410 if w>=1300 else 370;map_width=w-sidebar-28
        self.text('THE BROKEN CROSSING',20,14,25)
        holder=self.state['government']['officeholder']
        council=self.state['government']['council'];support=sum(self.state['people'][p]['allegiance']=='player' for p in council)
        self.text(f"Round {self.state['round']} · {'Governing' if holder=='player' else 'Opposition'} · Your council {support}/9 · Actions {self.session.state['ap']['player']}/2",20,49,17,BLUE if holder=='player' else GOLD)
        labels=[('End round',self.end_round),('Save',self.persist),('Load',lambda:self.persist(True)),('Export',self.export),('Restart',self.restart),('Other start',lambda:self.restart('displaced' if self.session.state['start']=='governing' else 'governing'))]
        header_width=min(100,(map_width-178)//6)
        for i,(label,action) in enumerate(labels):self.button(label,(20+i*(header_width+8),79,header_width,32),action)
        self.button('Links' if self.overlay else 'Focus only',(map_width-102,79,102,32),lambda:setattr(self,'overlay',not self.overlay))
        x=map_width+24;pygame.draw.rect(self.screen,PANEL,(x-12,0,sidebar+16,h))
        for i,label in enumerate(('Person','Council','Promises','Why?')):
            self.button(label,(x+i*((sidebar-22)//4),12,(sidebar-26)//4,30),lambda label=label:setattr(self,'sidebar_mode',label))
        if self.sidebar_mode=='Person':
            y=self.draw_person(x,54,sidebar-22)
            if y+165<h:self.draw_history(x,y+8,sidebar-22)
        elif self.sidebar_mode=='Council':self.draw_council(x,60,sidebar-22)
        elif self.sidebar_mode=='Promises':self.draw_promises(x,60,sidebar-22)
        else:self.draw_why(x,60,sidebar-22,h)
        map_rect=pygame.Rect(18,124,map_width-18,h-360)
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
        significant=[e for e in self.session.events if e['kind'] not in ('action','project_progress','structural_change') and e['round']<self.state['round']]
        if self.show_trace and significant:
            relevant=[e for e in significant if e['subject']==self.selected] or significant
            events=causal_chain(self.session,relevant[-1]['id'])
        else:events=list(reversed(significant))
        for event in events[:max(1,(h-y-14)//21)]:
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
        self.text('A nation depends on its people.',box.x+28,box.y+25,32)
        text=('The flood broke the shared crossing. Four communities need to cooperate, but disagree about who benefits. '
              'You and Sen compete for nine councillors. Holding five supporters for two rounds permits a challenge; '
              'the following round gives the incumbent a chance to respond. Losing office leaves you in the game. '
              'Build a movement and return with the obligations you promised. '
              'Select people to inspect their pressures and contacts. Appeals arrive next round; organizing uses effort '
              'to sustain pressure and reach others. Recruit for repair separately from political allegiance. '
              'Two actions per round. Space advances. Tab cycles people. F1 shows this briefing. '
              'This isolated laboratory uses abstract effort, a fixed terrain map, and no economy, aging or warfare.')
        self.wrap(text,box.x+28,box.y+85,680,20,TEXT,12)
        self.button('Enter the laboratory',(box.x+230,box.bottom-54,280,34),lambda:setattr(self,'briefing',False))

    def scrub(self,delta):
        if not self.session.history:return
        current=len(self.session.history) if self.history_index is None else self.history_index
        self.history_index=max(0,min(len(self.session.history)-1,current+delta))

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
                        for rect,action,enabled,reason in reversed(self.buttons):
                            if rect.collidepoint(event.pos):
                                if enabled:action()
                                elif reason:self.message=reason
                                break
                        else:
                            if not self.briefing:
                                nearby=sorted((math.dist(point,event.pos),pid) for point,pid in self.markers)
                                if nearby and nearby[0][0]<18:self.select(nearby[0][1])
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
    parser.add_argument('--save-path',type=Path)
    parser.add_argument('--screenshot',type=Path,help='Render one frame for visual verification')
    args=parser.parse_args()
    Laboratory(args.start,args.seed,args.save_path).run(args.screenshot)


if __name__=='__main__':main()

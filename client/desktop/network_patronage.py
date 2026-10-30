"""Plain-language offers, constituencies, jobs and known evidence for Patronage."""
from copy import deepcopy
import pygame
from .network_lab import Laboratory, PANEL, TEXT, MUTED, GOLD, BLUE, RED, GREEN
from .network_map import short_name
from people_network.accounts import account
from people_network.patronage import result, visible_summary
from people_network.knowledge import visible, public_view
from people_network.institutions import blockers


class PatronageLaboratory(Laboratory):
    def __init__(self,start='governing',seed=4243,save_path=None):
        super().__init__(start,seed,save_path,ruleset='patronage')
        pygame.display.set_caption('The Broken Crossing · Patronage')
        self.deal_page='Repair'
        self.repair_package='upstream'
        self.power_overlay=True
        self.jobs_page=0
        self.records_page=0
        self.message='Your bridge fund has 36 credits. Compare public management with Yara’s contract in Deals.'

    @property
    def state(self):
        raw=super().state
        key=(id(raw),raw['round'],raw['event_sequence'])
        if getattr(self,'_map_view_key',None)!=key:
            edges=deepcopy(self.session.initial['edges'])
            known=raw['patronage']['known']['player']
            for event in self.session.events:
                if int(event['id'][1:])>raw['event_sequence']:break
                if event['kind']!='structural_change' or '>' not in event['subject']:continue
                audience=event.get('audience')
                if audience is not None and 'player' not in audience and event['id'] not in known:continue
                after=event['after'];eid=event['subject']
                if isinstance(after,dict) and 'source' in after:edges[eid]=deepcopy(after)
                elif eid in edges and isinstance(after,dict) and 'governing' in after:edges[eid]['trust']=deepcopy(after)
            for fid in known:
                fact=raw['patronage']['facts'][fid]
                if fact['kind']!='job_response' or fact['terms']['status']!='delivered':continue
                job=fact['terms'];source=job['issuer'] if job['holder']=='public_board' else job['holder']
                target=job['worker'];eid=source+'>'+target
                if source!=target and eid not in edges:
                    edges[eid]=dict(source=source,target=target,trust=dict(governing=.3,organizing=.4),capacity=.3,available=1.)
            self._map_view_key=key
            self._map_view=dict(raw,edges=edges)
        return self._map_view

    def draw(self):
        self._map_view_key=None
        self.button_labels={}
        super().draw()

    def button(self,label,rect,action,enabled=True,reason=''):
        super().button(label,rect,action,enabled,reason)
        self.button_labels[tuple(pygame.Rect(rect))]=label

    def perform(self,kind,params):
        super().perform(kind,params)
        if 'accepted.' in self.message:
            explanations={
                'award_contract':'Funds reserved. Jobs still need individual consent; a contract buys no council votes.',
                'hiring_office':'Hiring delegated. The officeholder allocates jobs and can gain their own following.',
                'completion_bonus':'Two credits of Yara’s margin now reward Quinn for finishing, rather than delaying.',
                'grant_access':'A limited toll concession was granted. Actual users pay; poor travelers can be excluded.',
                'exempt':'A personal exemption was granted. Other villagers still pay. The deal is known to its parties.',
                'free_access':'Your public promise is recorded. Charging a toll can contradict it when people see evidence.',
                'audit':'Amal can inspect project records next round and publishes findings independently.',
                'disclose':'Evidence is being shared one relationship hop per round.',
                'buyout_access':'Concession bought out with two personal credits. The former holder keeps earned income.',
                'cancel_contract':'Unused escrow returned. Earned wages and personal relationships remain.'}
            if kind in explanations:self.message=explanations[kind]+f" {self.state['ap']['player']} actions left."

    def end_round(self):
        super().end_round()
        r=result(self.state)
        p=self.state['patronage']
        if r['ready']:
            self.message=r['label']+f" · {r['votes']}/9 votes · {r['crossings']} crossings, {r['denied']} denied. Continue to test whether power lasts."
        elif p['withheld']:
            self.message='Quinn withheld the job queue. Deals → Repair explains why and offers a completion bonus or replacement.'
        else:
            jobs=p['last_jobs']
            self.message=f"Round {self.state['round']}: {r['votes']}/9 votes; "+('bridge working' if r['delivery'] else f"repair streak {self.state['project']['streak']}/3")+f". {sum(j['status']=='delivered' for j in jobs)} paid contributions in the latest repair round."

    def draw_overview(self,x,y,width,height):
        s=self.state;p=s['patronage'];r=result(s)
        self.text('Who gains from governing?',x,y,25);y+=37
        y=self.wrap(r['label'] if r['ready'] else 'Your task: repair the bridge and govern with five council votes at round 12.',x,y,width,17,GOLD,3)+10
        self.text(f"Power · {r['votes']}/9 council votes",x,y,20,BLUE);y+=30
        self.text('Delivery · '+('bridge working' if r['delivery'] else f"repair streak {s['project']['streak']}/3"),x,y,17,GREEN);y+=27
        self.text(f"Access · {r['crossings']} crossed, {r['denied']} denied",x,y,17);y+=27
        self.text(f"{r['waiting']} journeys waited for the repair",x,y,13,MUTED);y+=23
        y=self.wrap(f"Public fund {p['accounts']['bridge_fund']} · repair escrow {p['accounts']['escrow:bridge']} · your wallet {p['accounts'][account('player')]}. Credits differ from the four service shares.",x,y,width,13,MUTED,3)+12
        self.button('Compare deals and their consequences',(x,y,width,34),lambda:setattr(self,'sidebar_mode','Offers'));y+=45
        self.text('What needs a decision?',x,y,20);y+=30
        for text in blockers(s):
            y=self.wrap(text,x,y,width,15,GOLD,4)+8
        self.action_button('Rally your own contacts','organize',dict(target='player',channel='player'),x,y,width);y+=43
        if s['government']['officeholder']=='rival':
            y=self.wrap('You retain your contacts, money and old obligations. Build five commitments for two rounds, then call a vote.',x,y,width,15,TEXT,3)+8
            self.action_button('Challenge Sen for office','challenge',{},x,y,width);y+=42
        y=self.wrap('A council vote is one person’s political commitment. A job is paid work. A broker can provide jobs and still fail to deliver votes.',x,y,width,15,TEXT,3)+14
        self.button('Groups: demands and service shares',(x,y,width,31),lambda:setattr(self,'sidebar_mode','Groups'));y+=41
        if y+82<height:
            self.button('Council: protect or gain a fifth vote',(x,y,width,31),lambda:setattr(self,'sidebar_mode','Council'));y+=41
            self.button('Brokers: personal gains versus followers',(x,y,width,31),lambda:setattr(self,'sidebar_mode','Power'))

    def draw_offers(self,x,y,width,height):
        s=self.state;p=s['patronage'];c=p['contract']
        self.text('Deals have consequences',x,y,25);y+=36
        self.text(f"Fund {p['accounts']['bridge_fund']} · escrow {p['accounts']['escrow:bridge']} · personal {p['accounts'][account('player')]}",x,y,15,GOLD);y+=29
        third=(width-12)//3
        for i,label in enumerate(('Repair','Access','Records')):
            self.button(label,(x+i*(third+6),y,third,30),lambda label=label:setattr(self,'deal_page',label))
        y+=44
        if self.deal_page=='Repair':
            if not c or c['status']=='cancelled':
                self.button('Priority: '+('Fields first' if self.repair_package=='upstream' else 'Market first'),(x,y,width,30),self.toggle_package);y+=42
                self.text('Public board · up to 30 credits',x,y,20,GREEN);y+=30
                y=self.wrap('One round to invite applicants. Broad hiring pays actual work. Six credits remain for contingencies; jobs give you some credit, without buying votes.',x,y,width,15,TEXT,4)+8
                self.action_button('Use public management','award_contract',dict(route='public',channel=self.repair_package),x,y,width);y+=50
                self.text('Yara’s contract · 36 credits',x,y,20,GOLD);y+=30
                y=self.wrap('Can start immediately. Thirty credits pay labor; six are Yara’s completion margin. Delegating hiring to Quinn can build a powerful broker who may delay completion.',x,y,width,15,TEXT,4)+8
                self.action_button('Award Yara the contract','award_contract',dict(route='merchant',channel=self.repair_package),x,y,width);y+=47
                self.wrap('The contract does not include a toll concession. Access rights are a separate choice.',x,y,width,13,MUTED,3)
            else:
                self.text(('Public management' if c['route']=='public' else 'Yara’s contract')+' · '+c['status'],x,y,20);y+=30
                y=self.wrap(f"Labor paid {c['paid']} credits; reserved margin {c['margin']}. The repair needs 6 workers and 4 haulers for 3 consecutive rounds; a missed round resets the streak.",x,y,width,15,TEXT,4)+8
                for text in blockers(s):y=self.wrap(text,x,y,width,15,GOLD,4)+8
                if c['status']=='active':
                    holder=p['rights']['hiring']['holder']
                    self.text('Hiring: '+self.holder_name(holder),x,y,17,BLUE);y+=29
                    half=(width-8)//2
                    self.action_button('Quinn’s job queue','hiring_office',dict(holder='p16'),x,y,half)
                    self.action_button('Rafi’s broad roster','hiring_office',dict(holder='p17'),x+half+8,y,half);y+=42
                    self.action_button('Reserve 2-credit completion bonus','completion_bonus',{},x,y,width);y+=41
                    self.action_button('Public hiring · 2 personal compensation' if holder not in ('public_board','p24') else 'Public hiring · no compensation','hiring_office',dict(holder='public_board'),x,y,width);y+=41
                    y=self.wrap('The bonus comes from the six-credit margin, and is earned only on completion. Replacing a private hiring officer costs you two personal credits and public recruitment takes a round.',x,y,width,13,MUTED,4)+8
                    if y+38<height:self.action_button('Cancel · refund unused; 2 personal compensation' if c['route']=='merchant' else 'Cancel · return unspent public escrow','cancel_contract',{},x,y,width)
                else:
                    self.wrap('The temporary hiring office has expired. Earned wages, the contractor’s profit and relationships persist. Check Access for any surviving toll rights.',x,y,width,15,GREEN,4)
        elif self.deal_page=='Access':
            access=p['rights'].get('access')
            if not access or not access['active']:
                y=self.wrap('Free access is the default. A concession gives one broker the right to collect actual tolls for six rounds after repair. No journeys means no income.',x,y,width,15,TEXT,4)+12
                self.action_button('Yara: two-credit toll concession','grant_access',dict(target='p24',fee=2),x,y,width);y+=43
                self.action_button('Quinn: one-credit toll concession','grant_access',dict(target='p16',fee=1),x,y,width);y+=45
            else:
                self.text('Access holder: '+self.holder_name(access['holder']),x,y,20,GOLD);y+=30
                if visible(s,'player',access['terms_event']):
                    y=self.wrap(f"Toll {access['fee']} credits per actual journey. "+('Expiry waits for completion.' if access['ends_round'] is None else f"Expires before round {access['ends_round']+1} travel."),x,y,width,15,TEXT,3)+8
                    exemptions=[f['terms']['person'] for f in public_view(s) if f['kind']=='exemption' and f['terms'].get('concession')==access['terms_event']]
                    y=self.wrap('Known personal exemptions: '+(', '.join(self.holder_name(q) for q in exemptions) or 'none'),x,y,width,13,MUTED,2)+9
                else:y=self.wrap('You know the holder, but need a receipt or audit to learn the terms.',x,y,width,15,TEXT,3)+8
                self.action_button('Give Inez a personal exemption','exempt',dict(target='p08'),x,y,width);y+=42
                y=self.wrap('This helps Inez personally. It neither exempts her village nor commits their votes. Her followers may object if they learn the terms.',x,y,width,13,GOLD,3)+12
                self.action_button('Buy out concession · 2 personal credits','buyout_access',{},x,y,width);y+=45
            self.text(f"Observed access: {p['total_crossings']} crossed",x,y,17,GREEN);y+=27
            self.text(f"{p['total_denied']} denied · {p['total_tolls']} paid in tolls",x,y,17,GOLD);y+=30
            self.text(f"{p['total_waiting']} journeys waited before repair",x,y,13,MUTED);y+=27
            self.wrap('A person with no money may be denied access. A patron keeps earned tolls after losing the concession or changing allies.',x,y,width,15,MUTED,4)
        else:
            y=self.wrap('Statements are public. Private terms are known to their parties. Evidence and audits can expose contradictions through relationships.',x,y,width,15,TEXT,4)+10
            self.action_button('Publicly promise free bridge access','free_access',{},x,y,width);y+=43
            self.action_button('Appoint Amal: independent record access','audit',{},x,y,width);y+=43
            y=self.wrap('Amal inspects next round and shares evidence herself. She can hurt the ruler who appointed her. Sharing travels one social hop per round.',x,y,width,13,GOLD,4)+12
            facts=list(reversed([f for f in public_view(s) if f['kind'] in ('exemption','access_receipt','concession')]))
            self.text('Evidence you possess',x,y,20);y+=30
            if not facts:y=self.wrap('No private record or toll receipt is known to you yet.',x,y,width,15,MUTED,3)
            self.records_page=min(self.records_page,max(0,(len(facts)-1)//3))
            half=(width-8)//2
            self.button('Newer evidence',(x,y,half,29),lambda:setattr(self,'records_page',max(0,self.records_page-1)),self.records_page>0)
            self.button('Older evidence',(x+half+8,y,half,29),lambda:setattr(self,'records_page',self.records_page+1),(self.records_page+1)*3<len(facts));y+=40
            for fact in facts[self.records_page*3:self.records_page*3+3]:
                if y+105>height:break
                y=self.wrap(self.fact_label(fact),x,y,width,13,TEXT,2)+5
                self.action_button('Share this evidence','disclose',dict(fact=fact['id']),x,y,width);y+=45

    def toggle_package(self):
        self.repair_package='market' if self.repair_package=='upstream' else 'upstream'

    def holder_name(self,pid):
        return 'Public board' if pid=='public_board' else short_name(self.state['people'][pid])

    def draw_power(self,x,y,width,height):
        self.text('A broker is not their followers',x,y,20);y+=34
        summary=visible_summary(self.state)
        y=self.wrap('A job can create dependence without buying a vote. The map’s gold rings mark rights; teal links show paid relationships you know.',x,y,width,13,TEXT,3)+10
        for pid in ('p16','p24','p08','p00'):
            p=self.state['people'][pid];m=self.state['patronage']['brokers'][pid]
            self.text(self.holder_name(pid)+' · '+('backs you' if p['allegiance']=='player' else 'backs Sen' if p['allegiance']=='rival' else 'undecided'),x,y,17,GOLD);y+=25
            y=self.wrap(m['asks'],x,y,width,13,TEXT,3)
            followers=[d for d in summary['dependencies'] if d['patron']==pid and d['strength']>.05]
            self.text(f"Known paid dependents: {len(followers)} · council seat: yes",x,y,13,BLUE);y+=22
            self.button('Talk to '+self.holder_name(pid),(x,y,width,29),lambda pid=pid:self.inspect_person(pid));y+=40
            if y+125>height:break

    def draw_person(self,x,y,width):
        pid=self.selected;p=self.state['people'][pid]
        self.text(self.holder_name(pid),x,y,25);y+=38
        y=self.wrap(p['role']+' · '+('backs you' if p['allegiance']=='player' else 'backs Sen' if p['allegiance']=='rival' else 'no declared backing'),x,y,width,15,TEXT,3)+12
        motive=self.state['patronage']['brokers'].get(pid)
        if motive:y=self.wrap(motive['asks'],x,y,width,15,GOLD,4)+15
        y=self.wrap(f"Rallying strain {p['fatigue']}/3. "+(f"Rest until round {p['rest_until']+1}." if self.state['round']<p['rest_until'] else 'Available to rally if strain is 0 or 1.'),x,y,width,13,GOLD,2)+8
        y=self.wrap('Asking for support sends one appeal. Rallying reserves this person’s effort to recruit contacts; they cannot also take a repair job.',x,y,width,15,TEXT,4)+12
        self.action_button('Ask for your political support','approach',dict(target=pid,channel='player'),x,y,width);y+=42
        self.action_button('Rally your contacts for my coalition','organize',dict(target=pid,channel='player'),x,y,width);y+=42
        self.action_button('Release from rallying','release',dict(target=pid),x,y,width);y+=42
        self.action_button('Appoint public-service liaison','appoint',dict(target=pid),x,y,width);y+=42
        self.action_button('Ask for field repair cooperation','approach',dict(target=pid,channel='upstream'),x,y,width);y+=45
        self.button('Back to brokers',(x,y,width,30),lambda:setattr(self,'sidebar_mode','Power'))
        return y+40

    def draw_jobs(self,x,y,width,height):
        self.text('Who actually worked?',x,y,25);y+=37
        summary=visible_summary(self.state)
        jobs=summary['jobs']
        y=self.wrap('One person has one effort slot. A wage pays delivered work; a broker’s advertised following is not a guaranteed crew.',x,y,width,15,TEXT,3)+12
        delivered=[j for j in jobs if j['status']=='delivered']
        self.text(f"Latest known crew: {sum(j['skill']=='work' for j in delivered)}/6 workers",x,y,17,GREEN);y+=26
        self.text(f"{sum(j['skill']=='haul' for j in delivered)}/4 haulers · {len(delivered)} credits earned",x,y,17,GREEN);y+=32
        self.jobs_page=min(self.jobs_page,max(0,(len(jobs)-1)//6))
        half=(width-8)//2
        self.button('Previous jobs',(x,y,half,29),lambda:setattr(self,'jobs_page',max(0,self.jobs_page-1)),self.jobs_page>0)
        self.button('Next jobs',(x+half+8,y,half,29),lambda:setattr(self,'jobs_page',self.jobs_page+1),(self.jobs_page+1)*6<len(jobs));y+=40
        for job in jobs[self.jobs_page*6:self.jobs_page*6+6]:
            if y+52>height:break
            name=self.holder_name(job['worker'])
            self.text(f"{name} · {job['skill']} · "+('earned 1' if job['status']=='delivered' else 'refused'),x,y,15,TEXT if job['status']=='delivered' else GOLD);y+=21
            y=self.wrap(job['reason'],x,y,width,13,MUTED,2)+8
        if not jobs:self.wrap('No repair jobs are currently known to you. Public recruitment takes a round; private job details require being a party or learning evidence.',x,y,width,15,MUTED,4)

    def draw_council(self,x,y,width):
        gov=self.state['government']
        self.text('Protect the fifth vote',x,y,25);y+=37
        y=self.wrap('Jobs and favors influence individual choices. Rallying uses effort that could repair the bridge.',x,y,width,15,TEXT,2)+12
        for pid in gov['council']:
            p=self.state['people'][pid]
            self.button(self.holder_name(pid)+' · '+('backs you' if p['allegiance']=='player' else 'backs Sen' if p['allegiance']=='rival' else 'undecided'),(x,y,width-80,32),lambda pid=pid:self.inspect_person(pid))
            self.action_button('Rally' if p['allegiance']=='player' else 'Ask','organize' if p['allegiance']=='player' else 'approach',dict(target=pid,channel='player'),x+width-74,y,74);y+=34
            working=any(j['worker']==pid and j['status']=='delivered' for j in self.state['patronage']['last_jobs']) and not self.state['project']['complete']
            status=('Repair crew: rallying removes this effort' if working else
                    f"Rallying now · strain {p['fatigue']}/3" if pid in self.state['organizers'] else
                    f"Rest until completed round {p['rest_until']}" if self.state['round']<p['rest_until'] else
                    'Ready to rally' if p['allegiance']=='player' and p['fatigue']<=1 else 'Ask for support before rallying')
            self.text(status,x+6,y,13,GOLD if working or p['fatigue']>=2 else MUTED);y+=21
        y=self.wrap('To regain office: hold five commitments for two rounds, then challenge. Sen gets one response round.',x,y,width,13,GOLD,3)+12
        self.action_button('Call a confidence vote','challenge',{},x,y,width)

    def fact_label(self,fact):
        t=fact['terms'];kind=fact['kind']
        if kind=='exemption':return self.holder_name(t['person'])+' received a private personal exemption.'
        if kind=='access_receipt':return self.holder_name(t['person'])+(' paid '+str(t['fee'])+' credits to cross.' if t['crossed'] else ' was denied: '+t['reason'])
        if kind=='concession':return self.holder_name(t['holder'])+' holds a '+str(t['fee'])+'-credit toll concession.'
        if kind=='hiring_decision':return self.holder_name(t['holder'])+': '+t['reason']
        if kind=='contract_awarded':return self.holder_name(t['holder'])+' manages repair; '+str(t['budget'])+' credits reserved.'
        return kind.replace('_',' ')

    def event_visible(self,event):
        audience=event.get('audience')
        if audience is not None and 'player' not in audience:
            return event['id'] in super().state['patronage']['known']['player']
        return True

    def event_label(self,event):
        fact=self.state['patronage']['facts'].get(event['id'])
        if fact:return f"{event['round']+1} · "+self.fact_label(fact)
        if event['kind']=='mandate_secured':return f"{event['round']} · Mandate secured: bridge working and a five-vote government."
        if event['kind']=='right_expired':return f"{event['round']+1} · {event['subject'].capitalize()} office expired; earnings and ties remain."
        return super().event_label(event)

    def draw_why(self,x,y,width,height):
        self.text('What you know and why',x,y,25);y+=38
        y=self.wrap('These are records you possess. An audit or disclosure can reveal more. Responses affect the next pressure update; support can then spread through trusted contacts.',x,y,width,15,TEXT,4)+14
        facts=public_view(self.state)
        relevant=[f for f in facts if f['kind'] not in ('job_response','access_receipt')] or facts
        for fact in reversed(relevant[-8:]):
            if y+65>height-60:break
            y=self.wrap(f"Round {fact['round']+1}: "+self.fact_label(fact),x,y,width,15,TEXT,3)+10
        self.button('Developer: export full truth and replay',(x,height-54,width,32),self.export)

    def draw_history(self,x,y,width):
        # Normal play avoids the classic full-truth pressure decomposition.
        return y

    def draw_briefing(self,w,h):
        shade=pygame.Surface((w,h),pygame.SRCALPHA);shade.fill((4,12,18,215));self.screen.blit(shade,(0,0))
        box=pygame.Rect(w//2-390,h//2-260,780,520);pygame.draw.rect(self.screen,PANEL,box,border_radius=12)
        self.text('Build the bridge. Keep the coalition.',box.x+28,box.y+24,32)
        paragraphs=[
            'WIN: from round 12, govern with at least five council votes and keep the repaired bridge working.',
            'DEALS: your public fund has 36 credits. Public management costs 30; Yara’s contract costs 36 and can start sooner.',
            'JOBS: a hired worker can still vote against you. A hiring patron builds their own following with public money.',
            'DELAY: Quinn can prefer keeping the job office open. A completion bonus or compensated replacement changes the incentives.',
            'ACCESS: tolls enrich the concession holder and can exclude poor travelers. Exempting Inez helps her, not her village.',
            'EVIDENCE: private terms stay with their parties until observed or disclosed. Amal’s audits can expose your own deals.',
            'Two actions each round; Space advances. Start explains blockers; Council shows the fifth vote; the map shows control and known dependence.'
        ]
        y=box.y+78
        for paragraph in paragraphs:y=self.wrap(paragraph,box.x+28,y,724,17,TEXT,3)+8
        self.button('Play Patronage',(box.x+250,box.bottom-52,280,34),lambda:setattr(self,'briefing',False))

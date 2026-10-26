"""Native read-only causal inspector using the shared explanation model (F11)."""
from functools import wraps
import pygame
from trace_explanation import ExplanationReader

TABS=('Treasury','Prices','Unrest','FX','Nation AI')


def _selection(world):
    tile=world.get('selected_region')
    nation=world.get('selected_nation') or getattr(tile,'owner_nation',None)
    if nation is None:nation=next(iter(world.get('nations',())),None)
    if tile is None and nation is not None:tile=next(iter(nation.tiles),None)
    return nation,tile


def load(world):
    state=world['_causal_panel'];trace=world.get('run_trace')
    state.update(row=None,explanation=None,error=None,source_offset=0)
    if trace is None:
        state['error']='No causal recorder is attached to this world.';return
    nation,tile=_selection(world)
    tab=state['tab'];subject=None;metric=None;kind=None
    if tab==0:
        subject={'type':'nation','id':nation.name} if nation else None
        metric='finance.treasury';kind='treasury_account_closure'
    elif tab==1:
        subject={'type':'tile','id':tile.name,'good':state.get('good','food')} if tile else None
        metric='goods.price'
    elif tab==2:
        subject={'type':'tile','id':tile.name} if tile else None;metric='politics.protest_energy'
    elif tab==3:
        subject={'type':'fx_desk','id':tile.name} if tile else None;metric='fx.bilateral_mid'
    else:
        subject={'type':'nation','id':nation.name} if nation else None;metric='ai.nation_decision'
    try:
        if state.get('event_id'):
            query={'event_id':state['event_id'],'limit':1,'boundary':state['boundary']}
        else:
            query={'turn':state['turn'],'subject':subject,'metric_id':metric,'kind':kind,
                   'offset':state['offset'],'limit':1,'boundary':state['boundary']}
        result=trace.query(**query);state['total']=result['total']
        if result['events']:
            state['row']=result['events'][0]
            state['explanation']=ExplanationReader(trace.path,state['boundary']).explain(state['row'])
    except Exception as error:state['error']=str(error)


def open_panel(world):
    trace=world.get('run_trace')
    world['_causal_panel']={'tab':0,'turn':world.get('turn',0),'offset':0,'event_id':None,
                            'boundary':trace._compact_writer.end_offset if trace else None,'history':[]}
    load(world)


def handle_event(event,world):
    if event.type==pygame.KEYDOWN and event.key==pygame.K_F11:
        if world.get('_causal_panel'):world['_causal_panel']=None
        else:open_panel(world)
        return True
    state=world.get('_causal_panel')
    if not state:return False
    if event.type==pygame.KEYDOWN and event.key in (pygame.K_ESCAPE,pygame.K_q):
        world['_causal_panel']=None;return True
    if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
        for rect,action,value in state.get('buttons',()):
            if not pygame.Rect(rect).collidepoint(event.pos):continue
            if action=='close':world['_causal_panel']=None;return True
            if action=='tab':state.update(tab=value,offset=0,event_id=None)
            elif action=='turn':state.update(turn=max(0,min(world.get('turn',0),state['turn']+value)),offset=0,event_id=None)
            elif action=='page':state['offset']=max(0,min(max(0,state.get('total',0)-1),state['offset']+value))
            elif action=='refresh':
                state['boundary']=world['run_trace']._compact_writer.end_offset
            elif action=='good':
                goods=('food','wood','furniture','cotton','cloth')
                state.update(good=goods[(goods.index(state.get('good','food'))+1)%len(goods)],offset=0,event_id=None)
            elif action=='sourcepage':
                count=len((state.get('explanation') or {}).get('cause_event_ids',()))
                state['source_offset']=max(0,min(max(0,count-1),state.get('source_offset',0)+value))
                return True
            elif action=='source':
                state['history'].append((state['tab'],state['turn'],state['offset'],state.get('event_id')))
                state.update(event_id=value,offset=0)
            elif action=='back' and state['history']:
                state['tab'],state['turn'],state['offset'],state['event_id']=state['history'].pop()
            load(world);return True
        return True
    return event.type in (pygame.KEYDOWN,pygame.KEYUP,pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP,pygame.MOUSEWHEEL)


def draw(surface,world):
    state=world.get('_causal_panel')
    if not state:return
    font=pygame.font.SysFont('Arial',18)
    width,height=surface.get_size();x,y=24,24;w,h=width-48,height-48
    pygame.draw.rect(surface,(12,18,28),(x,y,w,h),border_radius=8)
    pygame.draw.rect(surface,(100,130,170),(x,y,w,h),2,border_radius=8)
    state['buttons']=[]
    def text(line,px,py,color=(225,230,240)):
        surface.blit(font.render(str(line)[:max(20,int((w-32)/9))],True,color),(px,py))
    def button(label,bx,by,bw,action,value=None):
        rect=(bx,by,bw,38)
        pygame.draw.rect(surface,(42,58,80),rect,border_radius=4)
        text(label,bx+8,by+8);state['buttons'].append((rect,action,value))
    text('Causal evidence · F11 / Esc closes · records stay fixed until Refresh',x+16,y+12)
    for index,label in enumerate(TABS):button(label,x+16+index*130,y+42,122,'tab',index)
    button('Close',x+w-100,y+42,84,'close')
    button('Earlier',x+16,y+90,90,'turn',-1);text(f"Turn {state['turn']}",x+118,y+99)
    button('Later',x+220,y+90,90,'turn',1);button('Refresh',x+324,y+90,100,'refresh')
    button('Back',x+438,y+90,80,'back')
    if state['tab']==1:button(state.get('good','food'),x+532,y+90,110,'good')
    button('Previous record',x+16,y+h-54,160,'page',-1)
    button('Next record',x+190,y+h-54,140,'page',1)
    text(f"Record {state['offset']+1 if state.get('row') else 0} / {state.get('total',0)}",x+350,y+h-44)
    yy=y+148
    if state.get('error'):text('Could not load evidence: '+state['error'],x+16,yy,(255,140,120));return
    row=state.get('row');explanation=state.get('explanation')
    if row is None:text('No matching evidence for this turn. Choose an earlier turn or another category.',x+16,yy);return
    text(f"{row['kind'].replace('_',' ').capitalize()} · {explanation['label']}",x+16,yy,(250,210,120));yy+=26
    text(f"{row.get('value_before','—')} → {row.get('value_after','—')} {row.get('unit','')} · T{row['turn']}",x+16,yy);yy+=26
    for note in explanation['notes']:
        text(note,x+16,yy);yy+=24
    treasury=explanation.get('treasury')
    if treasury:
        for key,label in (('opening','Opening'),('recorded_receipts','Recorded receipts'),
                          ('recorded_spending','Recorded spending'),('confirmed_internal_cash_deposit_transfers','Confirmed internal transfers'),
                          ('membership_effect','Ownership/account membership effect'),('closing','Closing'),
                          ('unclassified_flow_residual','Unclassified flow residual')):
            value=treasury[key]
            text(f"{label}: {'unavailable' if value is None else format(0 if abs(value)<1e-8 else value,',.3f')}",x+16,yy);yy+=23
    for contribution in explanation['contributors'][:3]:
        text(f"{contribution['label']}: {contribution['value']:,.3g}",x+16,yy);yy+=23
    for issue in explanation['issues'][:3]:
        text('Evidence gap: '+issue['problem'],x+16,yy,(255,150,130));yy+=23
    causes=explanation['cause_event_ids']
    page_size=max(1,min(6,(y+h-70-yy)//42))
    source_offset=min(state.get('source_offset',0),max(0,len(causes)-1))
    for ident in causes[source_offset:source_offset+page_size]:
        label=next((source['label'] for source in explanation['sources'] if source['event_id']==ident),ident)
        button('Open '+label,x+16,yy,min(w-40,950),'source',ident);yy+=42
    if len(causes)>page_size:
        button('Earlier sources',x+w-360,y+h-54,160,'sourcepage',-page_size)
        button('More sources',x+w-190,y+h-54,170,'sourcepage',page_size)


def render_with_evidence(function):
    @wraps(function)
    def wrapped(surface,world,*args,**kwargs):
        result=function(surface,world,*args,**kwargs)
        draw(surface,world)
        return result
    return wrapped

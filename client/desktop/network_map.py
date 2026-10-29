"""Geographic and relationship overviews of the same people, with visible leverage."""
import math
import pygame
from people_network.graph import Graph

TEXT=(230,235,226);MUTED=(153,174,181);BLUE=(89,185,239);RED=(236,126,116)
GOLD=(240,197,101);GREEN=(117,204,165);DARK=(17,32,40)


def short_name(person):
    return person['name'].split(' — ')[-1]


def positions(app,rect):
    bounds=app.terrain['view_bounds']
    x0,y0,x1,y1=bounds
    scale=min(rect.width/(x1-x0),(rect.height-80)/(y1-y0))*app.zoom
    center=(rect.centerx,rect.centery+10)
    def project(point):return (int(center[0]+(point[0]-(x0+x1)/2)*scale+app.pan[0]),int(center[1]+(point[1]-(y0+y1)/2)*scale+app.pan[1]))
    result={};centers={}
    locations=list(app.state['locations'])
    for n,loc in enumerate(locations):
        members=[pid for pid,p in sorted(app.state['people'].items()) if p['location']==loc]
        if app.map_mode=='Network':
            # Schematic, deliberately stable: community groups, not fake geography.
            block_height=(rect.height-118)/2
            group_top=rect.y+48+(n//2)*block_height
            cx=rect.x+rect.width*(.26 if n%2==0 else .74)
            centers[loc]=(int(cx),int(group_top+87))
            cols=4;rows=math.ceil(len(members)/cols)
            dx=min(60,rect.width*.09);dy=min(48,(block_height-88)/max(1,rows-1))
            for i,pid in enumerate(members):
                row,col=divmod(i,cols);count=min(cols,len(members)-row*cols)
                result[pid]=(int(cx+(col-(count-1)/2)*dx),int(group_top+52+row*dy))
        else:
            anchor=app.terrain['anchors'][loc];centers[loc]=project(anchor)
            for i,pid in enumerate(members):
                angle=2*math.pi*i/len(members)
                radius=22+(i%2)*8
                result[pid]=project((anchor[0]+math.cos(angle)*radius,anchor[1]+math.sin(angle)*radius))
    return project,result,centers


def arrow(screen,color,a,b,width=1,offset=16):
    pygame.draw.line(screen,color,a,b,width)
    dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    if length<20:return
    ux,uy=dx/length,dy/length
    tip=(b[0]-ux*offset,b[1]-uy*offset)
    pygame.draw.polygon(screen,color,[tip,(tip[0]-ux*7+uy*4,tip[1]-uy*7-ux*4),(tip[0]-ux*7-uy*4,tip[1]-uy*7+ux*4)])


def draw(app,rect):
    app.screen.set_clip(rect)
    pygame.draw.rect(app.screen,(28,47,57) if app.map_mode=='Network' else (32,64,80),rect)
    project,points,centers=positions(app,rect)
    graph=Graph(app.state);metrics=app.insights['metrics']
    advice={r['person']:r for r in app.insights['recommendations']}
    if app.map_mode=='Terrain':
        for cell in app.terrain['cells']:
            poly=[project(p) for p in cell['polygon']]
            if len(poly)>=3:
                pygame.draw.polygon(app.screen,cell['color'],poly)
                pygame.draw.polygon(app.screen,(55,77,69),poly,1)
        for river in app.terrain['rivers']:
            pygame.draw.line(app.screen,(87,157,187),project(river[0]),project(river[1]),2)
        river=app.terrain['main_river']
        for a,b in zip(river,river[1:]):arrow(app.screen,(107,211,245),project(a['point']),project(b['point']),4,4)
        head=project(river[0]['point'])
        pygame.draw.polygon(app.screen,TEXT,[(head[0]-9,head[1]-14),(head[0]+9,head[1]-14),(head[0],head[1]-31)],2)
        app.text('Mountain springs',head[0]-115,head[1]+28,13,TEXT)
        mouth=project(river[-1]['point'])
        app.text('River mouth / sea',mouth[0]+10,mouth[1]-14,13,TEXT)
        # The crossing spans the actual river, not an arbitrary town-to-village line.
        banks=[project(p) for p in app.terrain['crossing']['banks']]
        pygame.draw.line(app.screen,GREEN if app.state['project']['complete'] else RED,*banks,6)
        crossing=project(app.terrain['crossing']['point'])
        app.text('Repaired bridge' if app.state['project']['complete'] else 'Broken bridge',crossing[0]-48,crossing[1]-24,13,GOLD)
    else:
        for loc,(cx,cy) in centers.items():
            pygame.draw.ellipse(app.screen,(34,57,65),(cx-rect.width*.23,cy-72,rect.width*.46,150),1)
    hover=None
    for point,pid in [(point,pid) for pid,point in points.items()]:
        if math.dist(point,pygame.mouse.get_pos())<18:hover=pid
    highlight={*advice,app.selected}
    if hover:highlight.add(hover)
    seen=set()
    for eid,e in sorted(graph.edges.items()):
        a,b=e['source'],e['target']
        if not e['available'] or not app.state['people'][a]['active'] or not app.state['people'][b]['active']:continue
        pair=tuple(sorted((a,b)))
        focused=a in highlight or b in highlight
        local=app.state['people'][a]['location']==app.state['people'][b]['location']
        if pair in seen and not (a==hover or a==app.selected):continue
        if not (focused or app.overlay or (app.map_mode=='Network' and local)):continue
        seen.add(pair)
        color=(63,90,95)
        if a in advice:color=(126,165,144)
        if a==hover or a==app.selected:color=(192,219,204)
        if eid in app.boundaries and focused:color=(166,131,85)
        weight=2 if a==hover or a==app.selected else 1
        arrow(app.screen,color,points[a],points[b],weight)
    # Community cards summarize support without opening individual inspectors.
    occupied=[]
    for loc,(cx,cy) in centers.items():
        counts=app.insights['local'][loc]
        name=app.state['locations'][loc]['name']
        if loc=='town':name='Council town'
        name+=' · '+counts['priority']
        label_y=cy-91 if app.map_mode=='Terrain' else cy-85
        label_y=max(rect.y+45,label_y)
        line=f"People: {counts['you']} back you · {counts['rival']} Sen · {counts['unsure']} unsure"
        width=max(app.fonts[15].size(name)[0],app.fonts[13].size(line)[0])+12
        label=pygame.Rect(int(cx-width/2),int(label_y),width,42)
        label.clamp_ip(rect.inflate(-8,-8))
        for prior in occupied:
            if label.colliderect(prior):label.y=prior.bottom+3
        pygame.draw.rect(app.screen,DARK,label,border_radius=5)
        app.text(name,label.x+6,label.y+3,15,TEXT)
        app.text(line,label.x+6,label.y+23,13,MUTED)
        occupied.append(label)
    max_reach=max(1,max(m['reach'] for m in metrics.values()))
    labels=[];app.visible_labels=set()
    for pid,p in sorted(app.state['people'].items(),key=lambda item:(metrics[item[0]]['reach'],item[0])):
        point=points[pid];m=metrics[pid]
        color=BLUE if p['allegiance']=='player' else RED if p['allegiance']=='rival' else GOLD
        if not p['active']:color=MUTED
        radius=6+round(7*m['reach']/max_reach)
        if pid==app.selected:pygame.draw.circle(app.screen,TEXT,point,radius+5,1)
        if m['organizer']:pygame.draw.circle(app.screen,GREEN,point,radius+3,2)
        if m['councillor']:
            x,y=point
            pygame.draw.polygon(app.screen,color,[(x,y-radius-2),(x+radius+2,y),(x,y+radius+2),(x-radius-2,y)])
        else:pygame.draw.circle(app.screen,color,point,radius)
        if pid in advice:
            badge=(point[0]-radius-4,point[1]-radius-4)
            pygame.draw.circle(app.screen,GOLD,badge,9)
            app.text(str(advice[pid]['number']),badge[0]-4,badge[1]-8,13,DARK)
        if rect.collidepoint(point):app.markers.append((point,pid))
        if app.map_mode=='Network' or pid in advice or pid in ('player','rival') or m['other_regions']>1 or pid==hover:
            labels.append((pid,point,radius))
    # Greedy labels in geographic view; a stable grid labels everybody in Network.
    for pid,point,radius in sorted(labels,key=lambda item:(item[0] not in advice,item[0])):
        p=app.state['people'][pid];label=short_name(p)
        if app.map_mode=='Terrain':label+=f" · {metrics[pid]['contacts']} contacts"
        size=app.fonts[13].size(label);candidates=[]
        for ox,oy in [(0,radius+5),(0,-radius-21),(size[0]/2+radius+5,-8),(-size[0]/2-radius-5,-8)]:
            candidates.append(pygame.Rect(int(point[0]-size[0]/2+ox-3),int(point[1]+oy-1),size[0]+6,18))
        chosen=next((r for r in candidates if rect.contains(r) and not any(r.colliderect(o) for o in occupied)),None)
        if chosen:
            pygame.draw.rect(app.screen,DARK,chosen,border_radius=3)
            app.text(label,chosen.x+3,chosen.y+1,13,TEXT);occupied.append(chosen);app.visible_labels.add(pid)
    pygame.draw.rect(app.screen,DARK,(rect.x,rect.bottom-65,rect.width,65))
    app.screen.set_clip(None)
    app.button('Terrain',(rect.x+8,rect.y+8,82,29),lambda:setattr(app,'map_mode','Terrain'))
    app.button('Network',(rect.x+96,rect.y+8,88,29),lambda:setattr(app,'map_mode','Network'))
    app.button('All links' if not app.overlay else 'Useful links',(rect.right-110,rect.y+8,100,29),lambda:setattr(app,'overlay',not app.overlay))
    caption='Terrain: river arrows run downhill to the sea.' if app.map_mode=='Terrain' else 'Network: grouped by community; positions show relationships, not geography.'
    app.text(caption,rect.x+10,rect.bottom-58,13,TEXT)
    app.text('Bigger = more trusted reach · diamond = council vote · green ring = rallying',rect.x+10,rect.bottom-38,13,MUTED)
    app.text('Blue backs you · coral backs Sen · gold undecided · numbers match advice',rect.x+10,rect.bottom-19,13,MUTED)
    if hover:
        p=app.state['people'][hover];m=metrics[hover]
        text=f"{short_name(p)} · {m['contacts']} trusted contacts"+(' · council vote' if m['councillor'] else '')
        app.text(text,rect.x+198,rect.y+15,13,TEXT)

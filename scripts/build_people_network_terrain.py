"""Export a downhill river catchment and settlements, without touching map slots."""
import json
import math
from pathlib import Path
from terrain.generator.polygon import PolygonMapGenerator


def build_fixture():
    config = dict(seed=117,width=1000,height=800,num_points=350,lloyd_iterations=2,
                  island_shape='radial',river_count=12,enable_noisy_edges=False)
    gen = PolygonMapGenerator(**config)
    cells = []
    for c in gen.centers:
        corners = sorted(c.corners,key=lambda v:math.atan2(v.y-c.y,v.x-c.x))
        cells.append(dict(id=c.index,point=[c.x,c.y],polygon=[[max(0,min(1000,v.x)),max(0,min(800,v.y))] for v in corners],
                          color=list(c.brdf_color),water=c.water,coast=c.coast,elevation=c.elevation))
    paths=[]
    for corner in gen.corners:
        if not corner.river or corner.elevation<.35 or corner.coast or corner.ocean:
            continue
        path=[];seen=set();current=corner
        while current and current.index not in seen:
            seen.add(current.index);path.append(current)
            if current.coast or current.ocean:break
            current=current.downslope
        if len(path)>5 and (path[-1].coast or path[-1].ocean):paths.append(path)
    if not paths:raise ValueError('Terrain must supply a mountain-to-coast river')
    path=max(paths,key=lambda p:sum(math.dist(a.point,b.point) for a,b in zip(p,p[1:])))
    if any(a.elevation<b.elevation for a,b in zip(path,path[1:])):
        raise ValueError('Selected river flows uphill')
    mid=len(path)//2
    a,b=path[mid-1],path[mid]
    dx,dy=b.x-a.x,b.y-a.y;length=math.hypot(dx,dy)
    normal=(-dy/length,dx/length)
    crossing=[(a.x+b.x)/2,(a.y+b.y)/2]
    desired=dict(village=[path[1].x-30,path[1].y+35],
                 town=[crossing[0]-normal[0]*55,crossing[1]-normal[1]*55],
                 workshops=[crossing[0]+normal[0]*60,crossing[1]+normal[1]*60],
                 landing=[path[-1].x,path[-1].y])
    settlements={};used=set()
    for loc in ('village','landing','town','workshops'):
        candidates=[c for c in cells if not c['water'] and c['id'] not in used]
        if loc=='village':candidates=[c for c in candidates if not c['coast'] and .25<c['elevation']<path[0].elevation]
        elif loc=='landing':candidates=[c for c in candidates if c['coast']]
        else:candidates=[c for c in candidates if not c['coast']]
        cell=min(candidates,key=lambda c:math.dist(c['point'],desired[loc]))
        used.add(cell['id'])
        settlements[loc]=dict(cell_id=cell['id'],point=cell['point'],elevation=cell['elevation'],coast=cell['coast'],
                              river_station=1 if loc=='village' else len(path)-1 if loc=='landing' else mid)
    if settlements['village']['elevation']<=settlements['landing']['elevation']:
        raise ValueError('Upstream village must be above the coastal landing')
    river=[dict(corner=c.index,point=[c.x,c.y],elevation=c.elevation,coast=c.coast) for c in path]
    anchors={k:v['point'] for k,v in settlements.items()}
    points=[*anchors.values(),*[v['point'] for v in river]]
    bounds=[min(p[0] for p in points)-125,min(p[1] for p in points)-110,
            max(p[0] for p in points)+125,max(p[1] for p in points)+110]
    rivers=[[[e.v0.x,e.v0.y],[e.v1.x,e.v1.y]] for e in gen.edges if e.river and e.v0 and e.v1]
    return dict(provenance=dict(generator='terrain.generator.polygon.PolygonMapGenerator',config=config,
                               placement='settlements anchored to one verified downhill river'),
                width=1000,height=800,cells=cells,rivers=rivers,anchors=anchors,settlements=settlements,
                main_river=river,view_bounds=bounds,
                crossing=dict(point=crossing,banks=[[crossing[0]+sign*normal[0]*18,crossing[1]+sign*normal[1]*18] for sign in (-1,1)]))


def main():
    data=build_fixture()
    dest=Path(__file__).resolve().parents[1]/'scenarios/people_network/terrain.json'
    dest.write_text(json.dumps(data,separators=(',',':'))+'\n')
    scenario=dest.with_name('broken_crossing.json')
    authored=json.loads(scenario.read_text())
    for loc,settlement in data['settlements'].items():
        authored['state']['locations'][loc].update(point=settlement['point'],elevation=settlement['elevation'],coastal=settlement['coast'])
    scenario.write_text(json.dumps(authored,indent=2)+'\n')
    print('Exported river catchment:',{k:(round(v['elevation'],2),v['coast']) for k,v in data['settlements'].items()})


if __name__=='__main__':main()

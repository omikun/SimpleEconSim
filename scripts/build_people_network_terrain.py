"""Export terrain-only geometry for the laboratory; never overwrite saved map slots."""
import json
import math
from pathlib import Path
from terrain.generator.polygon import PolygonMapGenerator


def main():
    config = dict(seed=117,width=1000,height=800,num_points=180,lloyd_iterations=2,
                  island_shape='radial',river_count=12,enable_noisy_edges=False)
    gen = PolygonMapGenerator(**config)
    cells = []
    for c in gen.centers:
        corners = sorted(c.corners,key=lambda v:math.atan2(v.y-c.y,v.x-c.x))
        cells.append(dict(id=c.index,point=[c.x,c.y],polygon=[[max(0,min(1000,v.x)),max(0,min(800,v.y))] for v in corners],
                          color=list(c.brdf_color),water=c.water,elevation=c.elevation))
    desired = dict(town=(530,460),village=(400,250),workshops=(310,570),landing=(650,620))
    anchors = {}
    used = set()
    for name,point in desired.items():
        c = min((c for c in cells if not c['water'] and c['id'] not in used),
                key=lambda c:math.dist(c['point'],point))
        anchors[name] = c['point'];used.add(c['id'])
    rivers = [[[e.v0.x,e.v0.y],[e.v1.x,e.v1.y]] for e in gen.edges if e.river and e.v0 and e.v1]
    data = dict(provenance=dict(generator='terrain.generator.polygon.PolygonMapGenerator',config=config),
                width=1000,height=800,cells=cells,rivers=rivers,anchors=anchors)
    dest = Path(__file__).resolve().parents[1]/'scenarios/people_network/terrain.json'
    dest.write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(f'Exported {len(cells)} cells and {len(rivers)} river segments to {dest}')


if __name__ == '__main__':
    main()

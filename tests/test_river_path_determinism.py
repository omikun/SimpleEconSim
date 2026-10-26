"""Equal-flux river branches must not depend on object allocation hashes."""
from types import SimpleNamespace
import unittest
from terrain.generator.polygon import PolygonMapGenerator


class Corner:
    def __init__(self,index,x,elevation,hash_value):
        self.index=index;self.x=x;self.y=0;self.elevation=elevation
        self.water=False;self.ocean=False;self.coast=False
        self.touches=[];self.protrudes=[];self.adjacent=[]
        self.downslope=None;self.river=0;self.hash_value=hash_value
    def __hash__(self):return self.hash_value


class RiverPathDeterminismTests(unittest.TestCase):
    def paths(self,hashes):
        nodes=[Corner(i,x,e,hashes[i]) for i,(x,e) in enumerate(
            ((0,.8),(500,.8),(100,.2),(400,.2),(250,.01)))]
        nodes[-1].water=True;nodes[-1].ocean=True
        edges=[]
        for u,v in ((0,2),(1,3),(2,4),(3,4)):
            a,b=nodes[u],nodes[v];a.downslope=b
            edge=SimpleNamespace(v0=a,v1=b,d0=None,d1=None,river=0)
            edges.append(edge);a.protrudes.append(edge);b.protrudes.append(edge)
            a.adjacent.append(b);b.adjacent.append(a)
        gen=PolygonMapGenerator.__new__(PolygonMapGenerator)
        gen.corners=nodes;gen.edges=edges;gen.river_count=2
        gen.canyon_depth=.5;gen.valley_width=1
        gen._generate_rivers()
        return gen.river_paths

    def test_equal_strength_confluences_retain_branch_order(self):
        first=self.paths((1,2,3,4,5))
        self.assertEqual(first,self.paths((997,53,5,601,31)))
        self.assertEqual(first,self.paths((53,31,997,5,601)))
        self.assertEqual(2,len(first))


if __name__=='__main__':unittest.main()

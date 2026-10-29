"""Geographic truth and read-only advice, not influence rankings by arbitrary degree."""
from copy import deepcopy
import unittest
from people_network.scenario import new_session
from people_network.terrain import load_terrain
from people_network.insights import overview
from people_network.engine import command


class GeographicAndOverviewTests(unittest.TestCase):
    def test_upstream_village_is_inland_above_coast_on_a_downhill_river(self):
        terrain=load_terrain();places=terrain['settlements'];river=terrain['main_river']
        self.assertFalse(places['village']['coast'])
        self.assertTrue(places['landing']['coast'])
        self.assertGreater(places['village']['elevation'],places['landing']['elevation'])
        self.assertGreaterEqual(river[0]['elevation'],places['village']['elevation'])
        self.assertLess(places['village']['river_station'],places['landing']['river_station'])
        self.assertTrue(river[-1]['coast'])
        self.assertTrue(all(a['elevation']>=b['elevation'] for a,b in zip(river,river[1:])))
        segments={frozenset(map(tuple,segment)) for segment in terrain['rivers']}
        for a,b in zip(river,river[1:]):
            self.assertIn(frozenset((tuple(a['point']),tuple(b['point']))),segments)
        cells={c['id']:c for c in terrain['cells']}
        state=new_session().state
        for loc,data in places.items():
            self.assertFalse(cells[data['cell_id']]['water'])
            self.assertEqual(state['locations'][loc]['point'],terrain['anchors'][loc])
            self.assertEqual(cells[data['cell_id']]['point'],terrain['anchors'][loc])
        # A bridge physically spans a river segment, rather than joining arbitrary towns.
        middle=terrain['crossing']['point'];banks=terrain['crossing']['banks']
        self.assertAlmostEqual((banks[0][0]+banks[1][0])/2,middle[0])
        self.assertAlmostEqual((banks[0][1]+banks[1][1])/2,middle[1])
        normal=[banks[1][i]-banks[0][i] for i in (0,1)]
        sides=[sum((terrain['anchors'][loc][i]-middle[i])*normal[i] for i in (0,1)) for loc in ('town','workshops')]
        self.assertLess(sides[0]*sides[1],0,'Town and workshops should lie on opposite banks')

    def test_advice_is_read_only_actionable_and_separates_vote_from_reach(self):
        session=new_session();before=deepcopy(session.payload());data=overview(session.state)
        self.assertEqual(before,session.payload())
        self.assertEqual(len(data['supporters']),5)
        self.assertLessEqual(len(data['recommendations']),2)
        self.assertEqual(len({r['person'] for r in data['recommendations']}),len(data['recommendations']))
        self.assertTrue(data['recommendations'])
        for r in data['recommendations']:
            self.assertEqual(r['forecast']['horizon'],5)
            self.assertIn('effects',r['forecast'])
            self.assertIn('Sen',r['forecast']['assumption'])
        for recommendation in data['recommendations']:
            command(session,'player',recommendation['kind'],_preview=True,**recommendation['params'])
        self.assertEqual(before,session.payload())
        self.assertEqual(sum(v['people'] for v in data['local'].values()),32)
        for pid,p in session.state['people'].items():
            self.assertEqual(data['metrics'][pid]['councillor'],pid in session.state['government']['council'])

    def test_higher_degree_without_trust_does_not_mean_more_effective_reach(self):
        state=new_session().state
        for e in state['edges'].values():
            if e['source']=='player':e['trust']={'governing':.1,'organizing':.1}
        data=overview(state)
        self.assertEqual(data['metrics']['player']['contacts'],0)
        self.assertEqual(data['metrics']['player']['reach'],0)
        self.assertGreater(data['metrics']['p04']['reach'],0)


if __name__=='__main__':unittest.main()

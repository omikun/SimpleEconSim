"""Strategic counterexamples to least-opposed/most-connected suggestions."""
from copy import deepcopy
import random
import unittest
from people_network.scenario import new_session
from people_network.advice import recommendations
from people_network.engine import command
from client.desktop.network_map import relationship_width


def edge(a,b,trust=.8):
    return dict(source=a,target=b,trust=dict(governing=trust,organizing=trust),capacity=.65,available=1.)


class StrategicAdviceTests(unittest.TestCase):
    def test_weakly_opposed_is_not_the_best_target_if_they_distrust_you(self):
        session=new_session();s=session.state
        for pid,p in s['people'].items():
            p['active']=pid in ('player','rival','p00','p01')
        s['people']['p00']['allegiance']=None
        s['people']['p01']['allegiance']=None
        s['people']['p00']['pressure'].update(player=.35,rival=.40)
        s['people']['p01']['pressure'].update(player=.28,rival=.45)
        s['edges']={'player>p00':edge('player','p00',.01),'player>p01':edge('player','p01',.95)}
        advice=recommendations(s)
        appeals=[r for r in advice if r['kind']=='approach']
        self.assertTrue(appeals)
        self.assertEqual(appeals[0]['person'],'p01','The stronger-trust target should beat the least-opposed target')
        self.assertGreater(appeals[0]['forecast']['contributions']['council_readiness'],0)

    def test_freeing_a_hauler_beats_organizing_the_last_repair_worker(self):
        s=new_session().state;s['round']=3
        s['rules'].update(work_required=1,haul_required=1,repair_rounds=1,anchor=0.,decay=0.,competition=0.)
        for pid,p in s['people'].items():
            p['active']=pid in ('player','rival','p00','p01')
            p['allegiance']='player' if pid!='rival' else 'rival'
            p['pressure'].update(player=.9 if pid!='rival' else .01,rival=.01 if pid!='rival' else .9,market=.9)
            p['task']='market' if pid in ('p00','p01') else None
            p['task_since']=0
        s['people']['p00']['skill']='haul';s['people']['p01']['skill']='work'
        s['people']['p01']['location']='village'
        s['project'].update(package='market',deadline=3)
        s['organizers']={'p00':dict(person='p00',issuer='player',channel='market',active_from=0,event='fixture')}
        s['edges']={'p00>p01':edge('p00','p01'),'player>p01':edge('player','p01')}
        advice=recommendations(s,'market')
        self.assertTrue(advice)
        self.assertEqual((advice[0]['person'],advice[0]['kind']),('p00','release'))
        self.assertGreater(advice[0]['forecast']['contributions']['complete'],0)
        self.assertNotIn(('p01','organize'),[(r['person'],r['kind']) for r in advice])

    def test_forecasts_are_read_only_and_respect_actual_information_and_budgets(self):
        session=new_session();before=deepcopy(session.payload());rng=random.getstate()
        advice=recommendations(session.state,decision_start=session.decision_start)
        self.assertEqual(before,session.payload());self.assertEqual(rng,random.getstate())
        for r in advice:
            command(session,'player',r['kind'],_preview=True,**r['params'])
        self.assertEqual(before,session.payload())
        # Mutating returned advice must not poison subsequent cache hits.
        advice[0]['forecast']['effects']['votes']=999
        self.assertNotEqual(recommendations(session.state)[0]['forecast']['effects']['votes'],999)
        command(session,'player','approach',target='p00',channel='player')
        command(session,'player','approach',target='p01',channel='player')
        self.assertEqual(recommendations(session.state,decision_start=session.decision_start),[])

    def test_relationship_thickness_varies_by_trust_capacity_context_and_availability(self):
        weak=edge('a','b',.1);strong=edge('a','b',.95)
        self.assertGreater(relationship_width(strong),relationship_width(weak))
        strong['trust']['organizing']=.1
        self.assertGreater(relationship_width(strong,'player'),relationship_width(strong,'market'))
        strong['available']=0.
        self.assertEqual(relationship_width(strong),0)


if __name__=='__main__':unittest.main()

"""Behavioral contracts for the isolated graph laboratory."""
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from people_network.scenario import new_session, validate
from people_network.model import CHANNELS, state_digest
from people_network.graph import Graph
from people_network.dynamics import advance
from people_network.engine import command, step, CommandError
from people_network.events import explain
from people_network.persistence import save, load, replay


def passive_fixture():
    s = new_session().state
    s['rules'].update(anchor=0., decay=0., competition=0.)
    for p in s['people'].values():
        p['pressure'] = {k:0. for k in CHANNELS}
    s['edges'] = {}
    return s


def edge(source,target,trust=1.):
    return dict(source=source,target=target,trust=dict(governing=trust,organizing=trust),capacity=1.,available=1.)


class GraphDynamicsTests(unittest.TestCase):
    def test_pulse_takes_one_hop_and_cannot_cross_disconnected_component(self):
        s=passive_fixture()
        s['edges']={'a':edge('player','p00'),'b':edge('p00','p01')}
        s['people']['player']['pressure']['player']=1.
        fields,parts=advance(s,{})
        self.assertGreater(fields['p00']['player'],0)
        self.assertEqual(fields['p01']['player'],0)
        self.assertEqual(fields['p02']['player'],0)
        for pid,p in s['people'].items():p['pressure']=fields[pid]
        next_fields,_=advance(s,{})
        self.assertGreater(next_fields['p01']['player'],0)
        self.assertEqual(next_fields['p02']['player'],0)

    def test_directional_trust_and_cut_queries(self):
        s=passive_fixture();s['edges']={'a':edge('player','p00'),'b':edge('p00','p01')}
        g=Graph(s)
        self.assertEqual(g.path('player','p01'),['player','p00','p01'])
        self.assertEqual(g.path('p01','player'),[])
        self.assertIn(('p00','player'),g.cut_edges())
        self.assertEqual(len(g.components()),30)
        s['edges']['a']['available']=0.
        self.assertEqual(Graph(s).path('player','p01'),[])

    def test_opposing_fields_preserve_high_high_and_low_low(self):
        s=passive_fixture();s['edges']={'a':edge('player','p00'),'b':edge('rival','p00')}
        s['people']['player']['pressure']['player']=1.
        s['people']['rival']['pressure']['rival']=1.
        fields,_=advance(s,{})
        self.assertGreater(fields['p00']['player'],0)
        self.assertAlmostEqual(fields['p00']['player'],fields['p00']['rival'])
        self.assertEqual(fields['p01']['player'],0)

    def test_source_removed_decay_stability_and_insertion_order(self):
        s=new_session().state
        s['rules']['anchor']=0.
        first,_=advance(s,{})
        reverse=deepcopy(s)
        reverse['people']=dict(reversed(list(reverse['people'].items())))
        reverse['edges']=dict(reversed(list(reverse['edges'].items())))
        second,_=advance(reverse,{})
        self.assertEqual(first,second)
        previous=math.fsum(p['pressure']['player'] for p in s['people'].values())
        for _ in range(120):
            fields,parts=advance(s,{})
            for pid,p in s['people'].items():p['pressure']=fields[pid]
            self.assertTrue(all(0<=v<=1 for p in fields.values() for v in p.values()))
        self.assertLess(math.fsum(p['pressure']['player'] for p in s['people'].values()),previous*.2)

    def test_exact_attribution_including_clamp(self):
        s=passive_fixture();s['people']['player']['pressure']['player']=.99
        fields,parts=advance(s,{'player':{'player':.6}})
        p=parts['player']['player']
        self.assertEqual(fields['player']['player'],1.)
        self.assertLess(p['clamp'],0)
        self.assertAlmostEqual(p['after']-p['before'],sum(p[k] for k in ('incoming','source','anchor','decay','opposition','clamp')))


class NetworkGameTests(unittest.TestCase):
    def test_initial_council_and_identity_in_both_starts(self):
        for start,count,holder in [('governing',5,'player'),('displaced',4,'rival')]:
            session=new_session(start)
            s=session.state
            self.assertEqual(len(s['people']),32)
            self.assertEqual(s['government']['officeholder'],holder)
            self.assertEqual(sum(s['people'][p]['allegiance']=='player' for p in s['government']['council']),count)
            self.assertEqual(s['people']['player']['allegiance'],'player')

    def test_invalid_commands_and_previews_are_read_only(self):
        session=new_session();old=deepcopy(session.payload())
        with self.assertRaises(CommandError):command(session,'player','appoint',target='rival')
        self.assertEqual(old,session.payload())
        command(session,'player','organize',target='player',channel='player',_preview=True)
        self.assertEqual(old,session.payload())
        command(session,'player','organize',target='player',channel='player')
        before=deepcopy(session.payload())
        with self.assertRaises(CommandError):command(session,'player','organize',target='player',channel='market')
        self.assertEqual(before,session.payload())

    def test_introduction_adds_one_channel_after_mutual_agreement(self):
        session=new_session();s=session.state
        a,b='p00','p01'
        s['edges'].pop(f'{a}>{b}',None)
        command(session,'player','introduce',target=a,other=b)
        self.assertIn(f'{a}>{b}',s['edges'])
        self.assertEqual(s['graph_revision'],1)
        self.assertEqual(s['ap']['player'],1)

    def test_promises_have_real_deadlines_and_cannot_overbook_posts(self):
        session=new_session();s=session.state
        command(session,'player','promise',target='p00',term='liaison')
        command(session,'player','promise',target='p01',term='liaison')
        step(session,rival=False)
        with self.assertRaises(CommandError):command(session,'player','promise',target='p02',term='liaison')
        command(session,'player','appoint',target='p00')
        step(session,rival=False);step(session,rival=False)
        self.assertEqual([p['status'] for p in s['promises']],['fulfilled','broken'])
        self.assertEqual(sum(e['kind']=='promise_result' for e in session.events),2)
        before=s['edges']['player>p01']['trust']['governing']
        step(session,rival=False)
        self.assertEqual(s['edges']['player>p01']['trust']['governing'],before)

    def test_organizing_cannot_double_count_work(self):
        session=new_session();s=session.state
        command(session,'player','organize',target='player',channel='upstream')
        command(session,'player','adopt',channel='upstream')
        step(session,rival=False)
        with self.assertRaises(CommandError):command(session,'player','work')
        for p in s['people'].values():p.update(task='upstream',task_since=-1)
        step(session,rival=False)
        event=next(e for e in reversed(session.events) if e['kind']=='project_progress')
        self.assertNotIn('player',event['contributors'])
        self.assertEqual(sum(event['counts'].values()),len(set(event['contributors'])))

    def test_sources_share_sender_and_receiver_budget(self):
        session=new_session();s=session.state
        for pid in ['player','p00','p01','p02','p03']:
            s['organizers'][pid]=dict(person=pid,issuer='player',channel='player',event='fixture',active_from=0)
        # Many duplicate invitations cannot exceed shared attention.
        s['invitations']=[dict(sender='player',target='p00',channel='player',due=0,event='fixture') for _ in range(100)]
        step(session,rival=False)
        sources=session.history[-1]['sources']
        self.assertLessEqual(sum(sources['p00'].values()),s['rules']['source_budget']+1e-12)
        self.assertLessEqual(sum(sum(v.values()) for v in sources.values()),5*s['rules']['output_budget']+1e-12)

    def test_candidate_hysteresis_does_not_flip_on_small_margin_jitter(self):
        session=new_session();s=session.state
        s['edges']={};s['rules'].update(anchor=0.,decay=0.,competition=0.)
        p=s['people']['p00'];p['pressure'].update(player=.51,rival=.49)
        for _ in range(6):step(session,rival=False)
        self.assertEqual(p['allegiance'],'player')
        self.assertFalse(any(e['kind']=='allegiance' and e['subject']=='p00' for e in session.events))

    def test_office_transfer_has_response_round_and_preserves_obligations(self):
        session=new_session('displaced');s=session.state
        # Controlled institution fixture; five supporters maintained by explicit interests.
        s['edges']={};s['rules'].update(anchor=0.,decay=0.,competition=0.)
        for pid in s['government']['council'][:5]:
            p=s['people'][pid];p['pressure'].update(player=.85,rival=.05);p['allegiance']='player'
        s['edges']['player>p00']=edge('player','p00')
        command(session,'player','promise',target='p00',term='liaison')
        step(session,rival=False);step(session,rival=False)
        command(session,'player','challenge')
        step(session,rival=False)
        self.assertEqual(s['government']['officeholder'],'rival')
        step(session,rival=False)
        self.assertEqual(s['government']['officeholder'],'player')
        self.assertEqual(s['people']['player']['name'],'You — Iskra')
        self.assertEqual(s['promises'][0]['status'],'pending')
        self.assertEqual(s['promises'][0]['due'],s['round']+1)
        command(session,'player','appoint',target='p00')
        step(session,rival=False)
        self.assertEqual(s['promises'][0]['status'],'fulfilled')

    def test_save_pending_decisions_resume_replay_and_corruption(self):
        session=new_session()
        command(session,'player','organize',target='player',channel='player')
        for _ in range(5):step(session)
        command(session,'player','approach',target='p00',channel='upstream')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'save.json';save(session,path);other=load(path)
            self.assertEqual(state_digest(session.state),state_digest(replay(other).state))
            for _ in range(5):step(session);step(other)
            self.assertEqual(session.payload(),other.payload())
            path.write_text('{"payload":0}')
            with self.assertRaises(ValueError):load(path)
        self.assertEqual(state_digest(session.state),state_digest(replay(session).state))

    def test_compact_trace_reconstruction_and_tracing_does_not_change_outcomes(self):
        a,b=new_session(),new_session();b.tracing=False
        for _ in range(15):step(a);step(b)
        self.assertEqual(state_digest(a.state),state_digest(b.state))
        info=explain(a,'p00',0,14)
        for p in info['channels'].values():
            self.assertAlmostEqual(p['residual'],0,places=12)
            self.assertAlmostEqual(sum(p['edges'].values()),p['incoming'],places=12)
        self.assertFalse(any(e['kind']=='edge_step' for e in a.events))
        self.assertLess(len(a.events),len(a.state['edges'])*len(CHANNELS)*15)

    def test_organization_survives_coordinator_absence_and_external_input_replays(self):
        from people_network.engine import set_availability
        session=new_session();s=session.state
        org=s['organizations']['craft'];old=org['coordinator'];members=list(org['members'])
        set_availability(session,old,False)
        self.assertEqual(org['members'],members)
        self.assertNotEqual(org['coordinator'],old)
        self.assertIsNotNone(org['coordinator'])
        self.assertEqual(Graph(s).contacts(old),[])
        for _ in range(4):step(session)
        self.assertEqual(state_digest(session.state),state_digest(replay(session).state))

    def test_complete_legal_govern_displacement_restore_govern_path(self):
        path=Path(__file__).resolve().parents[1]/'scenarios/people_network/playthroughs/govern_restore.json'
        session=new_session()
        for row in json.loads(path.read_text()):
            for c in row:command(session,c['issuer'],c['kind'],**c['params'])
            step(session)
        transfers=[e for e in session.events if e['kind']=='office_transfer']
        self.assertEqual([e['after'] for e in transfers[:2]],['rival','player'])
        self.assertEqual([e['round']+1 for e in transfers[:2]],[11,23])
        self.assertEqual(session.history[22]['after']['government']['officeholder'],'player')
        self.assertTrue(any(e['kind']=='agreement_honored' and e.get('leader')=='player' and e['round']>=23 for e in session.events))
        self.assertTrue(any(e['kind']=='organizer_exhausted' for e in session.events))
        self.assertEqual(state_digest(session.state),state_digest(replay(session).state))

    def test_global_random_and_economic_import_isolation(self):
        before=random.getstate();session=new_session()
        for _ in range(3):step(session)
        self.assertEqual(before,random.getstate())
        code=('import sys; import people_network.cli; import client.desktop.network_lab; '
              'assert not any(k in sys.modules for k in '
              "['sim_engine','core.sim_engine','sim_world','client.desktop.app','forex'])")
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()

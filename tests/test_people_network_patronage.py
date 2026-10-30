"""Political trade-offs, conservation, consent, audiences and replay in Patronage."""
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest

from people_network.scenario import new_session, validate
from people_network.engine import command, step, CommandError
from people_network.persistence import save, load, replay
from people_network.model import state_digest
from people_network.accounts import account
from people_network.institutions import control_graph
from people_network.knowledge import visible, public_view, publish
from people_network.patronage import result, visible_summary

ROOT=Path(__file__).resolve().parents[1]


def play(name, rounds=None, seed=4243, tracing=True):
    session=new_session(seed=seed,ruleset='patronage')
    session.tracing=tracing
    rows=json.loads((ROOT/'scenarios/people_network/playthroughs'/f'patronage_{name}.json').read_text())
    for row in rows[:rounds]:
        for action in row:command(session,action['issuer'],action['kind'],**action['params'])
        step(session)
        validate(session.state)
    return session


class PatronageTests(unittest.TestCase):
    def setUp(self):self.session=new_session(ruleset='patronage')

    def test_opt_in_preserves_classic_and_has_a_separate_schema(self):
        before=random.getstate()
        classic=new_session();patron=self.session
        self.assertEqual(classic.state['version'],2)
        self.assertNotIn('patronage',classic.state)
        self.assertEqual(patron.payload()['version'],3)
        self.assertEqual(random.getstate(),before)
        with self.assertRaises(CommandError):command(classic,'player','award_contract',route='public')
        self.assertNotEqual(classic.state['content_digest'],patron.state['content_digest'])

    def test_right_permissions_and_rejected_commands_are_atomic(self):
        session=new_session('displaced',ruleset='patronage')
        for kind,params in [('award_contract',dict(route='public')),('grant_access',dict(target='p24')),('exempt',dict(target='p08')),('audit',{})]:
            before=deepcopy(session.payload())
            with self.assertRaises(CommandError):command(session,'player',kind,**params)
            self.assertEqual(before,session.payload())
        before=deepcopy(self.session.payload())
        command(self.session,'player','award_contract',route='public',_preview=True)
        self.assertEqual(before,self.session.payload())

    def test_public_contract_pays_thirty_actual_wages_and_keeps_six(self):
        s=self.session
        command(s,'player','award_contract',route='public')
        self.assertEqual(s.state['patronage']['accounts']['escrow:bridge'],30)
        for _ in range(4):step(s,rival=False)
        p=s.state['patronage']
        self.assertTrue(s.state['project']['complete'])
        self.assertEqual(p['contract']['paid'],30)
        self.assertEqual(p['accounts']['bridge_fund'],6)
        self.assertEqual(p['accounts']['escrow:bridge'],0)
        self.assertEqual(sum(p['accounts'].values()),164)
        self.assertFalse(p['rights']['hiring']['active'])

    def test_merchant_and_bonus_pay_from_one_reserved_margin(self):
        s=play('brokers',rounds=3)
        p=s.state['patronage']
        self.assertTrue(s.state['project']['complete'])
        margins=[e for e in s.events if e['kind']=='payment' and e['reason'] in ('earned contractor margin','earned completion bonus')]
        self.assertEqual(sorted(e['after'] for e in margins),[2,4])
        self.assertEqual(sum(p['accounts'].values()),164)
        self.assertFalse(p['rights']['contract']['active'])
        self.assertTrue(p['rights']['access']['active'])
        self.assertTrue(any(d['patron']=='p16' and d['strength']>0 for d in p['dependencies'].values()))

    def test_hiring_patron_can_withhold_and_bonus_changes_the_choice(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','hiring_office',holder='p16')
        step(s,rival=False)
        step(s,rival=False)
        self.assertTrue(s.state['patronage']['withheld'])
        self.assertFalse(s.state['project']['complete'])
        self.assertEqual(s.state['patronage']['contract']['paid'],10)
        command(s,'player','completion_bonus')
        step(s,rival=False)
        self.assertFalse(s.state['patronage']['withheld'])
        self.assertEqual(s.state['project']['streak'],1)
        # A late incentive change cannot recover the spent first-round wages.
        # The on-time variation has enough funds to finish all three rounds.
        on_time=play('brokers',rounds=3)
        self.assertTrue(on_time.state['project']['complete'])

    def test_council_ballots_are_not_assigned_by_jobs_or_representatives(self):
        s=play('brokers',rounds=3)
        jobs=[f['terms'] for f in s.state['patronage']['facts'].values() if f['kind']=='job_response' and f['terms']['status']=='delivered']
        self.assertTrue(any(s.state['people'][j['worker']]['allegiance']=='rival' for j in jobs))
        self.assertTrue(any(d['patron']=='p16' and s.state['people'][d['worker']]['allegiance']=='rival' for d in s.state['patronage']['dependencies'].values()))
        command(s,'player','agreement',group='growers')
        agreement=next(a for a in s.state['agreements'] if a['leader']=='player' and a['group']=='growers')
        self.assertEqual(agreement['signatories'],['p08'])
        # Even a breached agreement cannot command the coordinator's neighbors.
        agreement.update(status='breached',breaches=1)
        from people_network.coalitions import failed_conditions
        self.assertTrue(failed_conditions(s.state,'p08','player'))
        self.assertFalse(failed_conditions(s.state,'p09','player'))

    def test_a_rallying_worker_cannot_also_deliver_a_paid_job(self):
        s=self.session
        command(s,'player','award_contract',route='public')
        command(s,'player','organize',target='p01',channel='player')
        step(s,rival=False);step(s,rival=False)
        for job in s.state['patronage']['last_jobs']:
            self.assertFalse(job['worker']=='p01' and job['status']=='delivered')
        for event in s.events:
            if event['kind'] in ('project_progress','project_completed'):
                self.assertEqual(len(event['contributors']),len(set(event['contributors'])))

    def test_withheld_paid_queue_does_not_veto_independent_volunteers(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','hiring_office',holder='p16')
        step(s,rival=False)
        for person in s.state['people'].values():person.update(task='upstream',task_since=-3)
        step(s,rival=False)
        self.assertTrue(s.state['patronage']['withheld'])
        self.assertEqual(s.state['project']['streak'],2)

    def test_no_free_toll_income_and_personal_exemption_has_local_scope(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','grant_access',target='p24',fee=2)
        self.assertEqual(s.state['patronage']['total_tolls'],0)
        step(s,rival=False)
        command(s,'player','exempt',target='p08')
        for _ in range(3):step(s,rival=False)
        receipts=[f['terms'] for f in s.state['patronage']['facts'].values() if f['kind']=='access_receipt']
        self.assertTrue(any(r['person']=='p08' and r['fee']==0 for r in receipts))
        self.assertTrue(any(r['person']=='p09' and r['fee']==2 for r in receipts))
        payments=[e for e in s.events if e['kind']=='payment' and e['reason']=='actual bridge toll']
        self.assertEqual(sum(e['after'] for e in payments),s.state['patronage']['total_tolls'])
        self.assertEqual(sum(s.state['patronage']['accounts'].values()),164)

    def test_terms_are_private_until_receipt_audit_or_disclosure(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','grant_access',target='p24',fee=2)
        step(s,rival=False)
        command(s,'player','exempt',target='p08')
        fid=next(fid for fid,f in s.state['patronage']['facts'].items() if f['kind']=='exemption')
        self.assertTrue(visible(s.state,'p08',fid))
        self.assertFalse(visible(s.state,'p09',fid))
        self.assertFalse(any(f['id']==fid for f in public_view(s.state,'rival')))
        command(s,'player','audit')
        step(s,rival=False)
        self.assertFalse(visible(s.state,'p09',fid))
        step(s,rival=False)
        self.assertTrue(any(d['fact']==fid and d['actor']=='p00' for d in s.state['patronage']['disclosures']))
        for _ in range(3):step(s,rival=False)
        self.assertTrue(visible(s.state,'p09',fid))
        self.assertTrue(any(e['kind']=='evidence_reaction' and e['subject']=='p09' and e['fact']==fid for e in s.events))

    def test_disclosure_travels_one_directed_hop_and_requires_a_witness(self):
        s=self.session
        command(s,'player','free_access')
        fid=s.state['patronage']['free_claims'][0]['fact']
        with self.assertRaises(ValueError):publish(s,'player','nonexistent')
        from people_network.knowledge import record,advance
        fid=record(s,'exemption','fixture',dict(person='p08',issuer='player'),['player'])
        s.state['edges']={}
        def edge(a,b):return dict(source=a,target=b,trust=dict(governing=.5,organizing=.5),capacity=.5,available=1.)
        s.state['edges']={'player>p00':edge('player','p00'),'p00>p09':edge('p00','p09')}
        publish(s,'player',fid)
        advance(s)
        self.assertTrue(visible(s.state,'p00',fid))
        self.assertFalse(visible(s.state,'p09',fid))
        advance(s)
        self.assertTrue(visible(s.state,'p09',fid))

    def test_tolls_can_contradict_a_public_promise_without_global_scandal(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','free_access')
        step(s,rival=False)
        command(s,'player','grant_access',target='p24',fee=2)
        for _ in range(2):step(s,rival=False)
        affected={e['subject'] for e in s.events if e['kind']=='evidence_reaction'}
        self.assertTrue(affected)
        self.assertNotIn('p00',affected)
        self.assertNotIn('p16',affected)
        for event in s.events:
            if event['kind']=='evidence_reaction':
                self.assertIn(event['fact'],s.state['patronage']['known'][event['subject']])
                self.assertGreaterEqual(len(event['parents']),2)

    def test_lawful_replacement_and_buyout_transfer_actual_compensation(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','hiring_office',holder='p16')
        step(s,rival=False)
        old=s.state['patronage']['accounts'][account('p16')]
        command(s,'player','hiring_office',holder='public_board')
        self.assertEqual(s.state['patronage']['accounts'][account('p16')],old+2)
        self.assertEqual(s.state['patronage']['accounts'][account('player')],2)
        command(s,'player','grant_access',target='p24')
        step(s,rival=False)
        command(s,'player','buyout_access')
        self.assertEqual(s.state['patronage']['accounts'][account('player')],0)
        self.assertFalse(s.state['patronage']['rights']['access']['active'])

    def test_private_exemption_cannot_buy_an_independent_auditor(self):
        s=self.session
        command(s,'player','award_contract',route='merchant')
        command(s,'player','grant_access',target='p24')
        step(s,rival=False)
        before=deepcopy(s.payload())
        with self.assertRaisesRegex(CommandError,'Amal refuses'):command(s,'player','exempt',target='p00')
        self.assertEqual(s.payload(),before)

    def test_displacement_preserves_contract_accounts_and_earned_dependence(self):
        s=new_session('displaced',ruleset='patronage')
        command(s,'rival','award_contract',route='merchant')
        command(s,'rival','grant_access',target='p24')
        # A legal support/challenge path from a controlled institution fixture.
        s.state['edges']={};s.state['rules'].update(anchor=0.,decay=0.,competition=0.)
        for pid in s.state['government']['council'][:5]:
            s.state['people'][pid]['allegiance']='player'
            s.state['people'][pid]['pressure'].update(player=.9,rival=.01)
        step(s,rival=False);step(s,rival=False)
        command(s,'player','challenge')
        step(s,rival=False);step(s,rival=False)
        self.assertEqual(s.state['government']['officeholder'],'player')
        self.assertEqual(s.state['patronage']['contract']['issuer'],'rival')
        self.assertEqual(s.state['patronage']['rights']['access']['issuer'],'rival')
        self.assertEqual(sum(s.state['patronage']['accounts'].values()),164)
        self.assertTrue(s.state['patronage']['dependencies'])

    def test_two_competitive_legal_routes_and_costs_are_separate(self):
        public=play('public');broker=play('brokers')
        for s in (public,broker):
            self.assertTrue(result(s.state)['won'])
            self.assertEqual(result(s.state)['votes'],5)
            self.assertEqual(state_digest(replay(s).state),state_digest(s.state))
            self.assertTrue(any(e['kind']=='mandate_secured' for e in s.events))
        self.assertEqual(result(public.state)['denied'],0)
        self.assertEqual(result(public.state)['fund'],6)
        self.assertEqual(result(broker.state)['denied'],3)
        self.assertEqual(result(broker.state)['tolls'],30)
        self.assertGreater(broker.state['patronage']['accounts'][account('p24')],public.state['patronage']['accounts'][account('p24')])

    def test_delivery_does_not_automatically_preserve_a_government(self):
        s=self.session
        command(s,'player','award_contract',route='public')
        command(s,'player','fund',group='growers',donor='trade')
        for _ in range(12):step(s)
        self.assertTrue(result(s.state)['delivery'])
        self.assertFalse(result(s.state)['power'])
        self.assertFalse(result(s.state)['won'])

    def test_legal_displacement_restoration_and_renewed_governing_obligations(self):
        session=play('restore')
        transfers=[(e['round']+1,e['after']) for e in session.events if e['kind']=='office_transfer']
        self.assertEqual(transfers,[(11,'rival'),(19,'player')])
        self.assertTrue(result(session.state)['won'])
        self.assertGreaterEqual(result(session.state)['votes'],5)
        restored=session.history[18]['after']
        self.assertTrue(restored['patronage']['rights']['access']['active'])
        self.assertEqual(restored['patronage']['rights']['access']['issuer'],'rival')
        self.assertEqual(session.state['patronage']['contract']['issuer'],'player')
        self.assertTrue(any(e['kind']=='agreement_breached' and e.get('leader')=='player' and e['round']>=19 for e in session.events))
        self.assertTrue(any(e['kind']=='agreement_honored' and e.get('leader')=='player' and e['round']>=21 for e in session.events))
        self.assertEqual(state_digest(replay(session).state),state_digest(session.state))

    def test_earlier_tolls_do_not_breach_a_later_free_access_promise(self):
        session=play('brokers')
        command(session,'player','free_access')
        command(session,'player','audit')
        for _ in range(4):step(session,rival=False)
        claims={claim['fact'] for claim in session.state['patronage']['free_claims']}
        for e in session.events:
            if e['kind']=='evidence_reaction' and session.state['patronage']['facts'][e['fact']]['kind']=='access_receipt':
                self.assertFalse(claims.intersection(e['parents']))

    def test_remaining_demand_and_payment_totals_reconcile(self):
        for name in ('public','brokers'):
            session=play(name)
            r=result(session.state)
            self.assertEqual(r['crossings']+r['denied']+r['waiting'],12*4)
        from people_network.advice import recommendations
        self.assertEqual(recommendations(self.session.state),[])

    def test_paid_work_reconstruction_links_to_real_wages_and_authority(self):
        session=play('brokers',rounds=3)
        from people_network.events import causal_chain
        completion=next(e for e in session.events if e['kind']=='project_completed')
        chain=causal_chain(session,completion['id'],limit=150)
        self.assertTrue(any(e['kind']=='payment' and e['reason']=='earned repair wage' for e in chain))
        self.assertTrue(any(e['kind']=='right_changed' and e['subject']=='hiring' for e in chain))

    def test_applicant_can_refuse_private_queue_and_keep_own_political_work(self):
        session=play('brokers',rounds=1)
        jobs=session.state['patronage']['last_jobs']
        self.assertTrue(any(j['worker']=='p17' and j['status']=='refused' and 'outside option' in j['reason'] for j in jobs))
        self.assertEqual(session.state['people']['p17']['allegiance'],'rival')

    def test_save_pending_actions_resume_replay_and_trace_independence(self):
        a=play('brokers');b=play('brokers',tracing=False)
        self.assertEqual(state_digest(a.state),state_digest(b.state))
        self.assertTrue(control_graph(a.state) or not a.state['patronage']['rights']['access']['active'])
        command(a,'player','audit')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';save(a,path);other=load(path)
            self.assertEqual(a.payload(),other.payload())
            self.assertEqual(state_digest(replay(other).state),state_digest(a.state))
            for _ in range(4):step(a);step(other)
            self.assertEqual(a.payload(),other.payload())
        from people_network.events import explain
        for p in explain(a,'p08',0,15)['channels'].values():
            self.assertAlmostEqual(p['residual'],0.,places=12)
            self.assertAlmostEqual(sum(p['interest_components'].values()),p['anchor'],places=12)

    def test_validator_rejects_unfunded_state_and_unknown_evidence(self):
        state=deepcopy(self.session.state)
        state['patronage']['accounts']['bridge_fund']+=1
        with self.assertRaises(ValueError):validate(state)
        state=deepcopy(self.session.state)
        state['patronage']['known']['rival'].append('nonexistent')
        with self.assertRaises(ValueError):validate(state)

    def test_known_dependence_does_not_expose_unseen_strength_changes(self):
        session=play('brokers',rounds=3)
        before=visible_summary(session.state)['dependencies']
        self.assertTrue(before)
        for d in session.state['patronage']['dependencies'].values():d['strength']=.99
        self.assertEqual(before,visible_summary(session.state)['dependencies'])


if __name__=='__main__':unittest.main()

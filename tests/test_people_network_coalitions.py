"""Substantive coalition trade-offs, independent of recommendation scoring."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from people_network.scenario import new_session,validate
from people_network.engine import command,step,CommandError
from people_network.coalitions import advance_demands,failed_conditions,terms,credibility
from people_network.persistence import save,load,replay
from people_network.model import state_digest,digest


class CoalitionMechanicsTests(unittest.TestCase):
    def test_budget_is_conserved_and_cannot_meet_every_request(self):
        session=new_session();s=session.state
        self.assertGreater(sum(o['funding_need'] for o in s['organizations'].values()),s['government']['budget_total'])
        command(session,'player','fund',group='growers',donor='trade')
        self.assertEqual(s['government']['allocations'],dict(civic=1,growers=2,craft=1,trade=0))
        self.assertEqual(sum(s['government']['allocations'].values()),4)
        before=deepcopy(session.payload())
        with self.assertRaises(CommandError):command(session,'player','fund',group='craft',donor='trade')
        self.assertEqual(before,session.payload())
        s['government']['allocations']['trade']=1
        with self.assertRaises(ValueError):validate(s)

    def test_public_delivery_helps_one_group_and_hurts_another(self):
        session=new_session();s=session.state
        command(session,'player','fund',group='growers',donor='trade')
        for _ in range(5):step(session,rival=False)
        self.assertGreater(s['organizations']['growers']['standing']['player'],s['organizations']['trade']['standing']['player'])
        self.assertLess(s['organizations']['trade']['standing']['player'],0)
        self.assertAlmostEqual(s['organizations']['trade']['standing']['rival'],0)
        self.assertEqual(len(s['people']),32)
        self.assertTrue(any(e['kind']=='group_mood' for e in session.events))

    def conditional_fixture(self):
        session=new_session();s=session.state
        s['rules'].update(anchor=0.,decay=0.,competition=0.)
        for p in s['people'].values():p['pressure'].update(player=.85,rival=.05)
        # The group's existing councillor is free to support the player, but not
        # automatically bound to do so by a positive agreement.
        s['people']['p08']['allegiance']='player'
        return session

    def test_breach_withholds_support_even_under_high_personal_pressure(self):
        session=self.conditional_fixture();s=session.state
        command(session,'player','agreement',group='growers')
        for _ in range(3):step(session,rival=False)
        a=s['agreements'][0]
        self.assertEqual(a['status'],'breached')
        self.assertIsNone(s['people']['p08']['allegiance'])
        self.assertGreater(s['people']['p08']['pressure']['player'],s['people']['p08']['pressure']['rival'])
        event=next(e for e in reversed(session.events) if e['kind']=='allegiance' and e['subject']=='p08')
        self.assertEqual(event['withheld_for'],['growers'])
        self.assertIn(a['last_event'],event['parents'])

    def test_repairing_an_agreement_requires_two_delivered_rounds(self):
        session=self.conditional_fixture();s=session.state
        command(session,'player','agreement',group='growers')
        for _ in range(3):step(session,rival=False)
        command(session,'player','fund',group='growers',donor='trade')
        step(session,rival=False)
        self.assertEqual(s['agreements'][0]['status'],'repairing')
        self.assertTrue(failed_conditions(s,'p08','player'))
        step(session,rival=False)
        self.assertEqual(s['agreements'][0]['status'],'honored')
        self.assertFalse(failed_conditions(s,'p08','player'))
        self.assertEqual(s['people']['p08']['allegiance'],'player')

    def test_fulfilled_agreement_is_continuing_not_a_one_time_vote_purchase(self):
        session=self.conditional_fixture();s=session.state
        command(session,'player','agreement',group='growers')
        command(session,'player','fund',group='growers',donor='trade')
        for _ in range(2):step(session,rival=False)
        self.assertEqual(s['agreements'][0]['status'],'honored')
        command(session,'player','fund',group='trade',donor='growers')
        step(session,rival=False)
        self.assertEqual(s['agreements'][0]['status'],'breached')
        with self.assertRaises(CommandError):command(session,'player','agreement',group='growers')

    def test_opposition_cannot_spend_budget_and_obligations_survive_office_changes(self):
        session=new_session('displaced');s=session.state
        with self.assertRaises(CommandError):command(session,'player','fund',group='growers',donor='trade')
        command(session,'player','agreement',group='growers')
        for _ in range(3):advance_demands(session)
        self.assertEqual(s['agreements'][0]['office_rounds'],0)
        s['government']['officeholder']='player'
        for _ in range(3):advance_demands(session)
        self.assertEqual(s['agreements'][0]['status'],'breached')
        old=s['agreements'][0]['office_rounds']
        s['government']['officeholder']='rival';advance_demands(session)
        self.assertEqual(s['agreements'][0]['status'],'suspended')
        self.assertEqual(s['agreements'][0]['office_rounds'],old)
        s['government']['officeholder']='player';advance_demands(session)
        self.assertEqual(s['agreements'][0]['status'],'breached')
        self.assertGreater(s['agreements'][0]['office_rounds'],old)

    def test_group_agreement_never_assigns_positive_votes(self):
        session=new_session();s=session.state
        s['rules'].update(anchor=0.,decay=0.,competition=0.)
        for p in s['people'].values():p['pressure'].update(player=0.,rival=.9)
        before={p:s['people'][p]['allegiance'] for p in s['organizations']['growers']['members']}
        command(session,'player','agreement',group='growers')
        self.assertEqual(before,{p:s['people'][p]['allegiance'] for p in before})
        command(session,'player','fund',group='growers',donor='trade')
        for _ in range(2):step(session,rival=False)
        self.assertEqual(s['agreements'][0]['status'],'honored')
        self.assertFalse(any(s['people'][p]['allegiance']=='player' for p in before))

    def test_representation_and_workload_are_actual_conditions(self):
        session=new_session();s=session.state
        self.assertIn('no liaison from this group',terms(s,'civic','player'))
        command(session,'player','appoint',target='p00')
        self.assertNotIn('no liaison from this group',terms(s,'civic','player'))
        for pid in s['organizations']['craft']['members'][:3]:
            s['organizers'][pid]=dict(person=pid,issuer='player',channel='player',event='fixture',active_from=0)
        self.assertTrue(any('maximum 2' in t for t in terms(s,'craft','player')))

    def test_organizing_costs_strain_without_any_public_project(self):
        session=new_session();s=session.state
        command(session,'player','organize',target='player',channel='player')
        for _ in range(4):step(session,rival=False)
        self.assertIsNone(s['project']['package'])
        self.assertNotIn('player',s['organizers'])
        self.assertEqual(s['people']['player']['fatigue'],3)
        with self.assertRaises(CommandError):command(session,'player','organize',target='player',channel='player')
        for _ in range(2):step(session,rival=False)
        command(session,'player','organize',target='player',channel='player')
        self.assertIn('player',s['organizers'])
        self.assertTrue(any(e['kind']=='organizer_exhausted' for e in session.events))

    def test_council_requires_relationships_across_communities(self):
        s=new_session().state
        counts={loc:sum(s['people'][p]['location']==loc for p in s['government']['council']) for loc in s['locations']}
        self.assertTrue(all(n>=2 for n in counts.values()))
        self.assertEqual(sum(counts.values()),9)

    def test_conditional_program_changes_interests_without_assigning_votes(self):
        offered=new_session('displaced');waiting=new_session('displaced')
        command(offered,'player','agreement',group='trade')
        step(offered,rival=False);step(waiting,rival=False)
        self.assertGreater(offered.state['people']['p25']['alignment']['player'],waiting.state['people']['p25']['alignment']['player'])
        self.assertTrue(any(e['kind']=='agreement_offered' for e in offered.events))

    def test_breaking_commitments_and_overpromising_reduce_credibility(self):
        session=new_session();s=session.state
        initial=credibility(s,'player')
        command(session,'player','agreement',group='growers')
        command(session,'player','agreement',group='trade')
        step(session,rival=False)
        command(session,'player','agreement',group='civic')
        command(session,'player','agreement',group='craft')
        self.assertLess(credibility(s,'player'),initial)
        overpromised=credibility(s,'player')
        for _ in range(3):step(session,rival=False)
        self.assertLess(credibility(s,'player'),overpromised)
        self.assertGreaterEqual(credibility(s,'player'),.15)

    def test_old_save_version_is_rejected_explicitly(self):
        import json
        session=new_session()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';save(session,path)
            data=json.loads(path.read_text());data['payload']['version']=1
            data['checksum']=digest(data['payload']);path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Unsupported save version'):load(path)

    def test_delivery_and_program_components_reconcile_to_interest_force(self):
        from people_network.events import explain
        session=new_session();command(session,'player','agreement',group='growers')
        for _ in range(4):step(session,rival=False)
        evidence=explain(session,'p08',0,3)
        for channel,p in evidence['channels'].items():
            self.assertAlmostEqual(sum(p['interest_components'].values()),p['anchor'],places=12)
            self.assertAlmostEqual(p['residual'],0,places=12)
        self.assertNotEqual(evidence['channels']['player']['interest_components']['agreement'],0)

    def test_save_resume_and_replay_include_agreements_budget_strain_and_moods(self):
        session=new_session();command(session,'player','agreement',group='growers')
        command(session,'player','organize',target='player',channel='player')
        for _ in range(5):step(session)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'save.json';save(session,path);other=load(path)
            for _ in range(5):step(session);step(other)
            self.assertEqual(session.payload(),other.payload())
            self.assertEqual(state_digest(session.state),state_digest(replay(session).state))


if __name__=='__main__':unittest.main()

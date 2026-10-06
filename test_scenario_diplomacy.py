"""French policy, funded naval participation, and negotiated terms."""

import unittest
import pickle
from unittest.mock import patch

from scenario_debt import outstanding
from scenario_diplomacy import advance, french_policy, make_offer, resolve_terms
from scenario_gunboat import advance_naval_crisis, begin_escalation
from scenario_geography import fleet_at
from scenario_egypt_1877 import classify_outcome, finish_due_campaign
from worldview_engine import build_world_view


class ScenarioDiplomacyTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.state = self.world['scenario_state']
        self.state['payment_status'] = 'defaulted'

    def test_independent_french_policies(self):
        with patch('scenario_diplomacy._energy', return_value=1.0):
            self.assertEqual(french_policy(self.world)[0], 'endorse')
            self.state['geography']['canal_open'] = False
            self.assertEqual(french_policy(self.world)[0], 'join_enforcement')
            self.state['geography']['canal_open'] = True
            self.state['diplomatic_crisis']['egyptian_proposal'] = 'mediation'
            self.assertEqual(french_policy(self.world)[0], 'mediate')
            self.state['diplomatic_crisis']['egyptian_proposal'] = 'joint_guarantee'
            self.assertEqual(french_policy(self.world)[0], 'joint_guarantor')
        self.state['diplomatic_crisis']['egyptian_proposal'] = None
        with patch('scenario_diplomacy._energy', return_value=4.5):
            self.assertEqual(french_policy(self.world)[0], 'abstain')
        with patch('scenario_diplomacy._energy', return_value=6.5):
            self.assertEqual(french_policy(self.world)[0], 'oppose')

    def test_france_can_fund_separate_fleet(self):
        begin_escalation(self.world, 'contested claim')
        self.state['geography']['canal_open'] = False
        self.world['turn'] = self.state['naval_crisis']['due_turn']
        with patch('scenario_diplomacy._energy', return_value=1.0):
            advance_naval_crisis(self.world)
        self.assertTrue(fleet_at(self.world, 'Britain', 'Alexandria'))
        self.assertTrue(fleet_at(self.world, 'France', 'Alexandria'))
        self.assertTrue(self.state['diplomatic_crisis']['french_authorization']['bombard'])
        self.assertEqual(self.state['geography']['fleets']['France']['transports'], 0)

    def test_french_terms_need_player_acceptance_and_transfer_cash(self):
        begin_escalation(self.world, 'contested claim')
        self.world['turn'] = 7
        ok, message = make_offer(self.world, 'request_french_mediation')
        self.assertTrue(ok, message)
        self.world['turn'] = 8
        with patch('scenario_diplomacy._energy', return_value=1.0):
            advance(self.world, 8, lambda *_: None)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'french_terms')
        egypt = next(n for n in self.world['nations'] if n.name == 'Egypt')
        egypt.government.agent.cash = max(egypt.government.agent.cash,
                                          outstanding(self.world) * .5)
        cash_before = sum(n.government.agent.cash for n in self.world['nations'])
        ok, message = resolve_terms(self.world, 'accept')
        self.assertTrue(ok, message)
        self.assertEqual(outstanding(self.world), 0.0)
        self.assertEqual(self.state['settlement_path'], 'french_mediation')
        self.assertEqual(sum(n.government.agent.cash for n in self.world['nations']), cash_before)

    def test_pending_french_offer_is_answered_before_final_debrief(self):
        self.world['turn'] = 20
        crisis = self.state['diplomatic_crisis']
        crisis['egyptian_proposal'] = 'mediation'
        crisis['proposal_due_turn'] = 20
        with patch('scenario_diplomacy._energy', return_value=1.0):
            finish_due_campaign(self.world)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'french_terms')
        self.assertIsNone(self.state['ending'])

    def test_scenario_diplomacy_state_survives_serialization(self):
        crisis = self.state['diplomatic_crisis']
        crisis['french_policy'] = 'join_enforcement'
        crisis['french_commitment'] = 'joint_enforcement'
        crisis['history'].append({'turn': 7, 'actor': 'France', 'decision': 'join_enforcement',
                                  'reason': 'Creditor exposure and canal denial.'})
        restored = pickle.loads(pickle.dumps(self.state))
        self.world['scenario_state'] = restored
        self.assertEqual(restored['diplomatic_crisis'], crisis)
        self.assertEqual(classify_outcome(self.world), 'unresolved_crisis')

    def test_old_scenario_state_lazily_initializes_diplomacy(self):
        from scenario_geography import foreign_decisions
        self.state.pop('diplomatic_crisis')
        decisions = foreign_decisions(self.world)
        self.assertIn(decisions['France'], ('endorse', 'abstain', 'oppose',
                                            'mediate', 'joint_guarantor', 'join_enforcement'))
        self.assertIn('diplomatic_crisis', self.state)


if __name__ == '__main__':
    unittest.main()

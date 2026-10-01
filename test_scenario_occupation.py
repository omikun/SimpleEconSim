"""Occupied institutions, conserved revenue, resistance and ending tests."""

import unittest

from scenario_campaign import bombard_alexandria, resolve_landing
from scenario_egypt_1877 import apply_action, finish_due_campaign
from scenario_geography import create_fleet, move_fleet
from scenario_occupation import advance, claim_institutions, intercept_revenue, resolve_capital
from worldview_engine import build_world_view


class ScenarioOccupationTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.state = self.world['scenario_state']
        self.egypt = next(n for n in self.world['nations'] if n.name == 'Egypt')
        self.britain = next(n for n in self.world['nations'] if n.name == 'Britain')

    def _foothold(self):
        create_fleet(self.world, 'Britain')
        move_fleet(self.world, 'Britain', 'Alexandria')
        bombard_alexandria(self.world)
        self.world['scenario_warning_modal'] = {'kind': 'landing_warning'}
        ok, _ = resolve_landing(self.world, 'evacuate_port')
        self.assertTrue(ok)
        self.world['scenario_warning_modal'] = None
        claim_institutions(self.world)

    def test_receipts_are_seized_only_under_held_institutions(self):
        gov = self.egypt.government
        self.assertEqual(intercept_revenue(self.world, gov, 'tariff', 20, 3), 0)
        self.state['campaign']['territorial_control']['Alexandria'] = 'Britain'
        claim_institutions(self.world)
        before = gov.agent.cash + self.britain.government.agent.cash
        amount = intercept_revenue(self.world, gov, 'tariff', 20, 3)
        self.assertGreater(amount, 0)
        self.assertLessEqual(amount, 6)
        self.assertAlmostEqual(before, gov.agent.cash + self.britain.government.agent.cash)
        self.assertEqual(self.state['occupation']['institutional_control']['customs'], 'Britain')
        self.assertEqual(self.state['occupation']['institutional_control']['cabinet'], 'Egypt')

    def test_foothold_pays_supply_and_warns_before_cairo_assault(self):
        self._foothold()
        self.world['turn'] += 2
        advance(self.world)
        self.assertGreater(self.state['occupation']['garrison_supply_paid'], 0)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'capital_warning')
        self.assertEqual(self.state['occupation']['formal_sovereign'], 'Egypt')
        ok, _ = resolve_capital(self.world, 'evacuate_cairo')
        self.assertTrue(ok)
        self.assertEqual(self.state['occupation']['institutional_control']['cabinet'], 'Britain')

    def test_resistance_can_force_negotiated_withdrawal(self):
        self._foothold()
        self.state['occupation']['resistance'] = .5
        egypt_before = self.egypt.government.agent.cash
        britain_before = self.britain.government.agent.cash
        ok, _ = apply_action(self.world, 'negotiate_withdrawal')
        self.assertTrue(ok)
        self.assertEqual(self.state['campaign']['territorial_control'], {})
        self.assertAlmostEqual(self.egypt.government.agent.cash, egypt_before - 30)
        self.assertAlmostEqual(self.britain.government.agent.cash, britain_before + 30)

    def test_ending_is_based_on_capital_control(self):
        self._foothold()
        self.state['campaign']['territorial_control']['Cairo'] = 'Britain'
        claim_institutions(self.world)
        self.world['turn'] = 20
        finish_due_campaign(self.world)
        self.assertEqual(self.state['ending'], 'occupation')
        self.assertIn('customs controller: Britain', self.state['debrief']['debt'])


if __name__ == '__main__':
    unittest.main()

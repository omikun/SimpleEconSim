"""Connected canal and supplied fleet behavior in the Egypt campaign."""

import unittest

from scenario_geography import (canal_access, create_fleet, fleet_at, foreign_decisions,
                                move_fleet, resupply)
from scenario_gunboat import advance_naval_crisis, begin_escalation, withdraw
from worldview_engine import build_world_view


class ScenarioGeographyTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.state = self.world['scenario_state']

    def test_canal_sites_are_connected_and_transit_collects_conserved_toll(self):
        geography = self.state['geography']
        self.assertIn('Port Said', geography['routes']['Mediterranean'])
        self.assertIn('Ismailia', geography['routes']['Port Said'])
        self.assertIn('Cairo', geography['routes']['Ismailia'])
        fleet = create_fleet(self.world, 'Britain')
        self.assertTrue(move_fleet(self.world, 'Britain', 'Port Said'))
        egypt = next(n for n in self.world['nations'] if n.name == 'Egypt')
        britain = next(n for n in self.world['nations'] if n.name == 'Britain')
        before = egypt.government.agent.cash + britain.government.agent.cash
        self.assertTrue(move_fleet(self.world, 'Britain', 'Ismailia'))
        self.assertEqual(geography['canal_tolls_collected'], 2)
        self.assertAlmostEqual(before, egypt.government.agent.cash + britain.government.agent.cash)
        self.assertEqual(fleet['location'], 'Ismailia')

    def test_canal_denial_blocks_transit_but_alexandria_stays_accessible(self):
        from scenario_egypt_1877 import apply_action
        ok, _ = apply_action(self.world, 'close_canal')
        self.assertTrue(ok)
        self.assertFalse(canal_access(self.world, 'Britain'))
        fleet = create_fleet(self.world, 'Britain')
        self.assertTrue(move_fleet(self.world, 'Britain', 'Port Said'))
        self.assertFalse(move_fleet(self.world, 'Britain', 'Ismailia'))
        fleet['location'] = 'Mediterranean'
        self.assertTrue(move_fleet(self.world, 'Britain', 'Alexandria'))

    def test_presence_coal_and_supply_control_blockade_eligibility(self):
        fleet = create_fleet(self.world, 'Britain')
        self.assertFalse(fleet_at(self.world, 'Britain', 'Alexandria'))
        self.assertTrue(move_fleet(self.world, 'Britain', 'Alexandria'))
        self.assertTrue(fleet_at(self.world, 'Britain', 'Alexandria'))
        fleet['coal'] = 0
        self.assertFalse(fleet_at(self.world, 'Britain', 'Alexandria'))
        resupply(self.world, 'Britain')
        self.assertTrue(fleet_at(self.world, 'Britain', 'Alexandria'))
        fleet['supplied'] = False
        self.assertFalse(fleet_at(self.world, 'Britain', 'Alexandria'))

    def test_foreign_policies_and_mobilization(self):
        self.state['payment_status'] = 'defaulted'
        begin_escalation(self.world, 'test')
        decision = foreign_decisions(self.world)
        self.assertEqual(decision['Britain'], 'intervene')
        self.assertIn(decision['France'], ('support_demand', 'abstain', 'oppose'))
        self.world['turn'] = self.state['naval_crisis']['due_turn']
        advance_naval_crisis(self.world)
        self.assertEqual(self.state['naval_crisis']['stage'], 'ultimatum')
        self.assertTrue(fleet_at(self.world, 'Britain', 'Alexandria'))
        withdraw(self.world, 'test withdrawal')
        self.assertFalse(fleet_at(self.world, 'Britain', 'Alexandria'))


if __name__ == '__main__':
    unittest.main()

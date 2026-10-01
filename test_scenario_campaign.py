"""Bombardment and landing outcomes use actual forts, people and army units."""

import unittest

from scenario_campaign import advance_expedition, bombard_alexandria, resolve_landing
from scenario_geography import create_fleet, move_fleet
from worldview_engine import build_world_view


class ScenarioCampaignTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.state = self.world['scenario_state']
        create_fleet(self.world, 'Britain')
        self.assertTrue(move_fleet(self.world, 'Britain', 'Alexandria'))

    def _landing_warning(self):
        self.state['naval_crisis'].update(stage='blockaded', port_tile=self.state['geography']['sites']['Alexandria']['tile'])
        self.assertTrue(advance_expedition(self.world))
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'landing_warning')

    def test_bombardment_damages_batteries_fleet_port_and_civilians(self):
        alexandria = next(tile for tile in self.world['tiles']
                          if tile.name == self.state['geography']['sites']['Alexandria']['tile'])
        before = self.state['campaign']['forts']['Alexandria'].copy()
        ok, _ = bombard_alexandria(self.world)
        self.assertTrue(ok)
        fort = self.state['campaign']['forts']['Alexandria']
        self.assertLess(fort['integrity'], before['integrity'])
        self.assertLess(fort['ammunition'], before['ammunition'])
        self.assertGreater(self.state['geography']['fleets']['Britain']['damage'], 0)
        self.assertGreater(self.state['campaign']['civilian_casualties'], 0)
        self.assertGreater(alexandria.scenario_infrastructure_damage, 0)

    def test_alexandria_landing_resolves_battle_and_losses(self):
        bombard_alexandria(self.world)
        self.world['turn'] += 1
        self._landing_warning()
        ok, message = resolve_landing(self.world, 'defend_alexandria')
        self.assertTrue(ok, message)
        battle = self.state['campaign']['battles'][-1]
        self.assertEqual(battle['location'], 'Alexandria')
        self.assertGreater(battle['atk_losses'] + battle['def_losses'], 0)
        self.assertIn(self.state['campaign']['expedition']['stage'], ('foothold', 'repelled'))

    def test_canal_route_requires_turns_and_access(self):
        bombard_alexandria(self.world)
        self.world['turn'] += 1
        self._landing_warning()
        ok, message = resolve_landing(self.world, 'defend_canal')
        self.assertTrue(ok, message)
        self.world['scenario_warning_modal'] = None
        for expected in ('Mediterranean', 'Port Said', 'Ismailia'):
            self.world['turn'] += 1
            self.assertTrue(advance_expedition(self.world))
            if expected != 'Ismailia' or 'Britain' in self.state['geography']['fleets']:
                self.assertEqual(self.state['geography']['fleets']['Britain']['location'], expected)
        self.world['turn'] += 1
        self.assertTrue(advance_expedition(self.world))
        self.assertEqual(self.state['campaign']['battles'][-1]['location'], 'Tel el Kebir')

    def test_closed_canal_prevents_canal_order(self):
        bombard_alexandria(self.world)
        self.world['turn'] += 1
        self._landing_warning()
        self.state['geography']['canal_open'] = False
        ok, _ = resolve_landing(self.world, 'defend_canal')
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()

"""Political authority and army decisions in the Egypt campaign."""

import unittest

from scenario_egypt_1877 import apply_action
from scenario_politics import advance, resolve
from scenario_situation import resolve_creditor_response
from worldview_engine import build_world_view, step_world


class ScenarioPoliticsTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.egypt = self.world['selected_nation']
        self.politics = self.world['scenario_state']['politics']

    def test_officer_pay_conserves_cash_and_improves_loyalty(self):
        households = [person for tile in self.egypt.tiles for person in tile.agents
                      if getattr(person, 'alive', True) and not getattr(person, 'is_government', False)
                      and not getattr(person, 'is_corporation', False)]
        before = self.egypt.government.agent.cash + sum(person.cash for person in households)
        loyalty = self.politics['army_loyalty']
        ok, _ = apply_action(self.world, 'pay_army_arrears')
        self.assertTrue(ok)
        self.assertGreater(self.politics['army_loyalty'], loyalty)
        after = self.egypt.government.agent.cash + sum(person.cash for person in households)
        self.assertAlmostEqual(before, after, places=5)

    def test_officer_movement_can_take_authority(self):
        self.politics['nationalist_movement'] = 0.75
        self.politics['army_loyalty'] = 0.35
        advance(self.world)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'officer_movement')
        ok, _ = resolve(self.world, 'support_urabi')
        self.assertTrue(ok)
        self.assertEqual(self.politics['governing_coalition'], 'nationalist')
        self.assertFalse(self.politics['palace_authority'] > self.politics['cabinet_authority'])

    def test_deposition_keeps_player_in_control_of_egypt(self):
        self.politics['palace_authority'] = 0.50
        self.world['scenario_state']['fiscal_autonomy'] = 0.70
        advance(self.world)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'dynastic_crisis')
        ok, _ = resolve(self.world, 'constitutional_compromise')
        self.assertTrue(ok)
        self.assertEqual(self.politics['ruler'], 'Tawfiq Pasha')
        self.assertEqual(self.politics['governing_coalition'], 'constitutional')
        self.assertEqual(self.world['player_nation_name'], 'Egypt')

    def test_controller_dismissal_invites_foreign_political_pressure(self):
        ok, _ = apply_action(self.world, 'dismiss_foreign_controllers')
        self.assertTrue(ok)
        step_world(self.world)
        self.assertEqual(self.world['scenario_warning_modal']['kind'], 'creditor_reaction')
        self.assertEqual(self.world['scenario_warning_modal']['action_id'], 'dismiss_foreign_controllers')
        pressure_authority = self.politics['palace_authority']
        ok, _ = resolve_creditor_response(self.world, 'restore_financial_controllers')
        self.assertTrue(ok)
        self.assertGreater(self.politics['palace_authority'], pressure_authority)


if __name__ == '__main__':
    unittest.main()

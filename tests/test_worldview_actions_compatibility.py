"""Legacy action entry points share desktop rules and retain campaign routing."""
import unittest
from unittest.mock import patch

from client.desktop import actions
from client.worldview import worldview_actions as legacy


class LegacyActionsTests(unittest.TestCase):
    def test_action_views_use_the_authoritative_functions(self):
        for name in ('draw_diplomacy_tab', 'draw_military_tab',
                     'draw_construction_tab', 'draw_innovation_tab',
                     'draw_sovereign_bonds_tab', 'get_active_nation',
                     'draw_top_bar_action_buttons', 'top_bar_action_hit'):
            with self.subTest(name=name):
                self.assertIs(getattr(legacy, name), getattr(actions, name))

    def test_campaign_guard_does_not_dispatch_ordinary_commands(self):
        world = {'scenario_id': 'labor_frontier_rivalry', 'actions_open': True}
        with patch.object(actions, 'actions_tab_hit') as dispatch:
            self.assertTrue(legacy.actions_tab_hit((0, 0), 0, 0, world))
        dispatch.assert_not_called()
        self.assertFalse(world['actions_open'])
        self.assertEqual(world['scenario_feedback'],
                         'Use the scenario decisions for this campaign.')

    def test_other_actions_forward_arguments_and_result(self):
        world = {'scenario_id': None}
        with patch.object(actions, 'actions_tab_hit', return_value=False) as dispatch:
            self.assertFalse(legacy.actions_tab_hit((1, 2), 3, 4, world))
        dispatch.assert_called_once_with((1, 2), 3, 4, world)

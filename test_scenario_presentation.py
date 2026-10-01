"""Guided information density and source labeling."""

import unittest

import pygame

from ui_targets import clear_targets
from worldview_camera import HEIGHT, MAP_RIGHT
from worldview_engine import build_world_view
from worldview_scenario_ui import draw_pressure_panel, draw_scenario_warning_modal, scenario_pressures


class ScenarioPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        self.world = build_world_view(scenario_id='egypt_1877')
        self.world['ui_mode'] = 'guided'
        self.surface = pygame.Surface((1400, 900))

    def test_three_pressure_cards_show_occupation_and_supply(self):
        state = self.world['scenario_state']
        state['campaign']['territorial_control']['Alexandria'] = 'Britain'
        state['occupation']['institutional_control']['customs'] = 'Britain'
        cards = scenario_pressures(self.world)
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[1]['title'], 'Occupation & revenue')
        self.assertIn('Britain', cards[1]['cause'])
        self.assertTrue(any('garrison supply' in detail for detail in cards[1]['details']))

    def test_long_action_list_scrolls_and_keeps_targets_inside_panel(self):
        state = self.world['scenario_state']
        self.world['turn'] = 6
        state['payment_status'] = 'unpaid'
        state['naval_crisis']['stage'] = 'mobilizing'
        state['politics']['army_loyalty'] = .4
        state['politics']['palace_authority'] = .4
        state['campaign']['territorial_control']['Alexandria'] = 'Britain'
        clear_targets(self.world)
        draw_pressure_panel(self.surface, self.world)
        maximum = self.world['guided_action_scroll_max']
        self.assertGreater(maximum, 0)
        top_actions = {target.action[1] for target in self.world['_ui_targets']
                       if target.scope == 'guided' and isinstance(target.action, tuple)
                       and target.action[0] == 'scenario_action'}
        self.world['guided_action_scroll'] = maximum
        clear_targets(self.world)
        draw_pressure_panel(self.surface, self.world)
        lower_targets = [target for target in self.world['_ui_targets']
                         if target.scope == 'guided' and isinstance(target.action, tuple)
                         and target.action[0] == 'scenario_action']
        self.assertIn('default_remittance', {target.action[1] for target in lower_targets})
        self.assertNotIn('default_remittance', top_actions)
        self.assertTrue(all(MAP_RIGHT < target.rect.x < 1400 and target.rect.bottom < HEIGHT - 50
                            for target in lower_targets))

    def test_log_labels_history_and_tuned_values(self):
        entries = self.world['scenario_state']['historical_log']
        self.assertEqual([entry['kind'] for entry in entries],
                         ['documented_history', 'tuned_game_value'])

    def test_landing_and_cairo_warning_render_with_choices(self):
        state = self.world['scenario_state']
        state['geography']['fleets']['Britain'] = {'transports': 40}
        for kind, minimum in (('landing_warning', 3), ('capital_warning', 2)):
            self.world['scenario_warning_modal'] = {'kind': kind}
            clear_targets(self.world)
            draw_scenario_warning_modal(self.surface, self.world)
            choices = [target for target in self.world['_ui_targets']
                       if target.scope == 'scenario_warning']
            self.assertGreaterEqual(len(choices), minimum)
            self.assertTrue(all(target.rect.bottom < HEIGHT for target in choices))


if __name__ == '__main__':
    unittest.main()

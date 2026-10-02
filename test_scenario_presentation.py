"""Guided information density and source labeling."""

import unittest

import pygame

from ui_targets import clear_targets
from worldview_camera import HEIGHT, MAP_RIGHT
from worldview_engine import build_world_view
from worldview_scenario_ui import (draw_pressure_panel, draw_scenario_warning_modal,
                                   scenario_pressures, scenario_warning_modal_hit)


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

    def test_pending_french_offer_promotes_a_foreign_decision_card(self):
        state = self.world['scenario_state']
        state['diplomatic_crisis']['egyptian_proposal'] = 'joint_guarantee'
        state['diplomatic_crisis']['proposal_due_turn'] = 8
        state['campaign']['territorial_control']['Alexandria'] = 'Britain'
        cards = scenario_pressures(self.world)
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[1]['title'], 'Foreign decision')
        self.assertIn('Paris replies on turn 8', cards[1]['value'])
        self.assertIn('5 units per turn', cards[1]['cause'])
        self.assertIn('Britain then accepts terms', cards[1]['details'][0])

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

    def test_french_terms_can_be_accepted_by_modal_click(self):
        from scenario_debt import outstanding
        self.world['turn'] = 8
        self.world['scenario_state']['payment_status'] = 'defaulted'
        self.world['scenario_warning_modal'] = {'kind': 'french_terms'}
        clear_targets(self.world)
        draw_scenario_warning_modal(self.surface, self.world)
        accept = next(target for target in self.world['_ui_targets']
                      if target.action == ('scenario_warning', 'diplomacy_response:accept'))
        scenario_warning_modal_hit(accept.rect.center, self.world)
        self.assertIsNone(self.world['scenario_warning_modal'])
        self.assertEqual(outstanding(self.world), 0.0)

    def test_long_debrief_scrolls_without_hiding_ending(self):
        state = self.world['scenario_state']
        state['ending'] = 'joint_financial_control'
        state['debrief'] = {
            'title': 'Joint creditor control', 'summary': 'Britain and France collect assigned receipts.',
            'food': 'Household access remains under review.', 'debt': 'A claim remains.',
            'control': 'Egypt governs Cairo.', 'diplomacy': 'France joined the agreement.',
            'politics': 'Legitimacy held.', 'authority': 'Egyptian cabinet.',
            'diplomacy_history': [{'actor': 'France', 'decision': 'joint_guarantor',
                                   'reason': 'Creditors expect receipts.'}] * 6,
            'actions': ['Egypt offered a joint guarantee with signed terms.'] * 8,
        }
        draw_pressure_panel(self.surface, self.world)
        self.assertGreater(self.world['guided_debrief_scroll_max'], 0)
        self.world['guided_debrief_scroll'] = self.world['guided_debrief_scroll_max']
        draw_pressure_panel(self.surface, self.world)
        self.assertEqual(self.world['guided_debrief_scroll'], self.world['guided_debrief_scroll_max'])


if __name__ == '__main__':
    unittest.main()

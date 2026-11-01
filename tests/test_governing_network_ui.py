"""Community concerns are visible without individual selection or map click-through."""

from copy import deepcopy
import unittest

import pygame

from governing_network import initialize
from tests.test_governing_network import fixture
from ui_targets import clear_targets, find_target
from client.desktop.panels.governing_network_ui import draw_society_observation


class SocietyPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        self.world = fixture()
        initialize(self.world, 'observe')
        self.surface = pygame.Surface((1400, 900))

    def draw(self):
        clear_targets(self.world)
        draw_society_observation(self.surface, self.world,
                                lambda size: pygame.font.Font(None, size), top=52)

    def test_hide_and_reopen_use_real_targets_in_both_clients_without_simulation_changes(self):
        from client.desktop.panels.scenario_ui import guided_ui_hit as primary_hit
        from worldview_scenario_ui import guided_ui_hit as legacy_hit
        for hit in (primary_hit, legacy_hit):
            before = deepcopy(self.world['scenario_state'])
            self.draw()
            target = next(t for t in self.world['_ui_targets'] if t.action == 'toggle_society_observation')
            self.assertTrue(hit(target.rect.center, self.world))
            self.assertTrue(self.world['_ui_society_observation_hidden'])
            self.draw()
            target = next(t for t in self.world['_ui_targets'] if t.action == 'toggle_society_observation')
            self.assertTrue(hit(target.rect.center, self.world))
            self.assertFalse(self.world['_ui_society_observation_hidden'])
            self.assertEqual(before, self.world['scenario_state'])

    def test_card_body_consumes_click_without_selecting_an_unseen_district(self):
        from client.desktop.panels.scenario_ui import guided_ui_hit
        self.draw()
        target = find_target(self.world, (40, 230), scope='guided')
        self.assertEqual(target.action, 'society_observation_body')
        self.assertTrue(guided_ui_hit((40, 230), self.world))
        self.assertNotIn('_ui_society_observation_hidden', self.world)

    def test_all_three_communities_and_read_only_limit_are_visible_at_once(self):
        rendered = []

        class RecordingFont:
            def __init__(self, size):
                self.font = pygame.font.Font(None, size)

            def size(self, text):
                return self.font.size(text)

            def render(self, text, *args):
                rendered.append(text)
                self_width = self.font.size(text)[0]
                if self_width > 384:
                    raise AssertionError('Community text extends beyond its card: ' + text)
                return self.font.render(text, *args)

        draw_society_observation(self.surface, self.world, RecordingFont, top=52)
        all_text = ' '.join(rendered)
        for phrase in ('Cultivators and workers', 'Grainholders and landowners',
                       'Merchants and exporters', 'underfed', 'unpaid taxes',
                       'Observation only', 'Existing politics'):
            self.assertIn(phrase, all_text)
        self.assertTrue(all(t.rect.right < 1060 and t.rect.bottom < 836
                            for t in self.world['_ui_targets']))

    def test_mode_off_adds_no_panel_or_targets(self):
        world = fixture()
        clear_targets(world)
        draw_society_observation(self.surface, world, lambda n: pygame.font.Font(None, n), top=52)
        self.assertEqual(world['_ui_targets'], [])


if __name__ == '__main__':
    unittest.main()

"""Desktop input/loading/render integration without an API key or GUI display."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pygame
from explanations import desktop
from test_ai_explainer_service import TraceFixture, FakeProvider, done


class DesktopExplainerTests(TraceFixture):
    # Reuse the trace fixture, not its backend tests.
    def setUp(self):
        super().setUp()
        pygame.init(); self.addCleanup(pygame.quit)
        self.surface = pygame.display.set_mode((1100, 850))
        self.world['selected_region'] = self.tile

    def test_chooser_loading_and_proposal_screen_remain_frame_safe(self):
        service = self.service(FakeProvider(True))
        with patch('explanations.desktop.default_service', return_value=service):
            desktop.draw(self.surface, self.world)
            self.assertEqual(0, service.provider.calls)
            self.assertFalse(desktop.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F10, unicode=''), self.world))
            event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12, unicode='')
            self.assertTrue(desktop.handle_event(event, self.world)); desktop.draw(self.surface, self.world)
            self.assertEqual(0, service.provider.calls)
            desktop.request(self.world, self.selection)
            desktop.draw(self.surface, self.world)
            job = self.world['_ai_explainer']['job']; ready = done(service, job)
            self.assertEqual('ready', ready['state'], ready['message'])
            self.world['_ai_explainer']['job'] = ready
            desktop.draw(self.surface, self.world)
            pygame.image.save(self.surface, str(Path(__file__).resolve().parents[1] / 'tmp/ai-explainer-desktop.png'))
            self.world['_ai_explainer']['scroll'] = 500; desktop.draw(self.surface, self.world)
            self.assertTrue(self.world['_ai_explainer']['buttons'])
            desktop.close(self.world)
            self.assertNotIn('_ai_explainer', self.world)

    def test_world_reset_closes_pending_explanation(self):
        service = self.service()
        with patch('explanations.desktop.default_service', return_value=service):
            desktop.request(self.world, self.selection)
            self.world['run_trace'] = SimpleNamespace(run_id='new-run')
            self.assertTrue(desktop.tick(self.world)); self.assertNotIn('_ai_explainer', self.world)


if __name__ == '__main__': unittest.main()

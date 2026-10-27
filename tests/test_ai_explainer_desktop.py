"""Desktop input/loading/render integration without an API key or GUI display."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from concurrent.futures import Future

import pygame
from explanations import desktop
from explanations.context import capture
from explanations.packet import build_packet
from test_ai_explainer_service import TraceFixture, FakeProvider, done


class DesktopExplainerTests(TraceFixture):
    # Reuse the trace fixture, not its backend tests.
    def setUp(self):
        super().setUp()
        pygame.init(); self.addCleanup(pygame.quit)
        self.surface = pygame.display.set_mode((1100, 850))
        self.world['selected_region'] = self.tile

    def wait_catalog(self):
        state = self.world['_ai_explainer']
        if state.get('catalog_future'):
            state['catalog_future'].result(timeout=5)
        desktop.tick(self.world)
        self.assertIsNone(state.get('catalog_error'))
        return state

    def test_picker_offers_only_recorded_stats_and_carries_all_dimensions(self):
        self.trace.snapshot(self.clock, subject={**self.subject, 'livelihood': 'food'},
                            metric_id='labor.primary_livelihood', unit='adults', before=4, after=3)
        service = self.service()
        with patch('explanations.desktop.default_service', return_value=service):
            desktop.chooser(self.world)
            options = desktop._matches(self.wait_catalog())
            self.assertEqual({'economy.gdp_nominal', 'labor.primary_livelihood'}, {o['metric_id'] for o in options})
            self.assertEqual(0, service.provider.calls)
            for option in options:
                selected = {**self.selection, 'metric_id': option['metric_id'],
                            'dimensions': {k: v for k, v in option['subject'].items() if k not in ('type', 'id')}}
                self.assertTrue(build_packet(capture(self.world, selected))['evidence'])
            desktop._choose(self.world, next(o for o in options if o['metric_id'] == 'labor.primary_livelihood'))
            self.assertEqual('ready', done(service, self.world['_ai_explainer']['job'])['state'])
            self.assertEqual('food', self.world['_ai_explainer']['selection']['dimensions']['livelihood'])

    def test_picker_follows_map_clicks_and_search_selects_another_tile(self):
        other = SimpleNamespace(name='C17', owner_nation=self.nation)
        self.world['tiles'].append(other)
        self.trace.snapshot(self.clock, subject={'type': 'tile', 'id': 'C17', 'good': 'food'},
                            metric_id='goods.price', unit='C', before=1, after=2)
        self.world['_causal_panel'] = {'row': None}
        desktop.chooser(self.world)
        self.assertIsNone(self.world['_causal_panel'])
        self.wait_catalog(); desktop.draw(self.surface, self.world)
        self.assertFalse(desktop.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
            button=1, pos=(10, 10)), self.world))
        self.world['selected_region'] = other  # The map handles the unconsumed click.
        self.assertTrue(desktop.tick(self.world))
        state = self.wait_catalog()
        self.assertEqual('tile:C17', state['entity'])
        self.assertEqual(['goods.price'], [o['metric_id'] for o in desktop._matches(state)])
        state.update(choosing_entity=True, text='Delta', index=0)
        desktop.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=''), self.world)
        self.wait_catalog(); desktop.tick(self.world)
        self.assertEqual('tile:Delta', state['entity'])

    def test_empty_turn_cannot_generate(self):
        service = self.service()
        with patch('explanations.desktop.default_service', return_value=service):
            desktop.chooser(self.world); self.wait_catalog()
            desktop.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, unicode=''), self.world)
            state = self.wait_catalog()
            self.assertEqual([], desktop._matches(state))
            stale = {'metric_id': 'economy.gdp_nominal', 'subject': self.subject}
            desktop._choose(self.world, stale)
            desktop._choose(self.world)
            self.assertTrue(state['chooser']); self.assertEqual(0, service.provider.calls)
            desktop.draw(self.surface, self.world)

    def test_new_map_selection_returns_result_to_picker_without_generation(self):
        service = self.service()
        other = SimpleNamespace(name='C2', owner_nation=self.nation)
        self.world['tiles'].append(other)
        with patch('explanations.desktop.default_service', return_value=service):
            desktop.request(self.world, self.selection)
            done(service, self.world['_ai_explainer']['job'])
            self.assertEqual(1, service.provider.calls)
            self.world['selected_region'] = other
            self.assertTrue(desktop.tick(self.world))
            state = self.wait_catalog()
            self.assertTrue(state['chooser']); self.assertEqual('tile:C2', state['entity'])
            self.assertEqual(1, service.provider.calls)

    def test_slow_catalog_does_not_block_ui_or_publish_stale_tile(self):
        old = Future(); new = Future()
        other = SimpleNamespace(name='C9', owner_nation=self.nation)
        self.world['tiles'].append(other)
        with patch('explanations.desktop._catalog_executor') as executor:
            executor.submit.side_effect = [old, new]
            old.set_running_or_notify_cancel()
            desktop.chooser(self.world)
            state = self.world['_ai_explainer']
            self.world['selected_region'] = other; desktop.tick(self.world)
            old.set_result([{'metric_id': 'economy.gdp_nominal', 'subject': self.subject}])
            desktop.tick(self.world)
            self.assertEqual([], state['options'])
            new.set_result([{'metric_id': 'goods.price', 'subject': {'type': 'tile', 'id': 'C9', 'good': 'food'}}])
            desktop.tick(self.world)
            self.assertEqual('tile:C9', state['entity'])
            self.assertEqual('goods.price', state['options'][0]['metric_id'])

    def test_native_save_omits_viewer_future_and_restores_live_drawer(self):
        from native_simulation_checkpoint import save_world
        state = {'chooser': True, 'catalog_future': Future()}
        self.world['_ai_explainer'] = state
        self.world['_trace_session'] = SimpleNamespace(run_trace=self.trace,
            pending_start=self.trace.count, tiles=[self.tile], nations=[self.nation], _trace_previous={})
        def save(simulation, directory):
            self.assertNotIn('_ai_explainer', simulation.world)
            return 'saved'
        with patch('trace_snapshots.sample', return_value={}), patch('native_simulation_checkpoint.save', side_effect=save):
            self.assertEqual('saved', save_world(self.world, self.root))
        self.assertIs(state, self.world['_ai_explainer'])

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

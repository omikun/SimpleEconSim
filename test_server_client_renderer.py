"""
test_server_client_renderer.py — Unit tests for the modular Server-Client-Renderer architecture.
"""

import os
import unittest
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
pygame.init()

from render_engine import Camera, RenderEngine
from render_engine.layers import LayerType, get_layer_by_hotkey, get_all_layers
from sim_server import SimServer, CommandType, ServerEvent
from sim_server.protocol import CommandMessage
from game_client import GameClient
from worldview_camera import HEX_SIZE


class TestRenderEngineAndCamera(unittest.TestCase):
    def setUp(self):
        self.cam = Camera(width=1600, height=900, map_right=1180, top_bar_h=46, ticker_h=30)
        self.bbox = (0.0, 0.0, 1000.0, 800.0)
        self.cam.set_bbox(self.bbox)

    def test_camera_zoom_and_pan(self):
        initial_zoom = self.cam.zoom
        self.cam.zoom_at(1.25, 590, 450)
        self.assertGreater(self.cam.zoom, initial_zoom)

        # Extreme zoom in clamped
        for _ in range(20):
            self.cam.zoom_at(1.5, 590, 450)
        self.assertLessEqual(self.cam.zoom, 4.0)

        # Extreme zoom out clamped
        for _ in range(20):
            self.cam.zoom_at(0.5, 590, 450)
        self.assertGreaterEqual(self.cam.zoom, 0.35)

    def test_camera_dict_sync(self):
        d = {'ox': 120.0, 'oy': -45.0, 'zoom': 1.4}
        self.cam.sync_from_dict(d)
        self.assertEqual(self.cam.ox, 120.0)
        self.assertEqual(self.cam.oy, -45.0)
        self.assertEqual(self.cam.zoom, 1.4)

        target = {}
        self.cam.sync_to_dict(target)
        self.assertEqual(target['ox'], 120.0)
        self.assertEqual(target['oy'], -45.0)
        self.assertEqual(target['zoom'], 1.4)

    def test_screen_hex_transformations(self):
        cx, cy = self.cam.hex_to_screen(500.0, 400.0)
        self.assertIsInstance(cx, (int, float))
        self.assertIsInstance(cy, (int, float))

    def test_render_layers(self):
        overview = get_layer_by_hotkey(pygame.K_1)
        self.assertIsNotNone(overview)
        self.assertEqual(overview.layer_type, LayerType.OVERVIEW)

        all_layers = get_all_layers()
        self.assertGreaterEqual(len(all_layers), 9)

    def test_render_engine_lifecycle(self):
        engine = RenderEngine(width=1600, height=900, map_right=1180, top_bar_h=46, ticker_h=30)
        engine.set_bbox(self.bbox)
        engine.invalidate_cache()
        self.assertIsNone(engine.terrain_renderer.cached_surface)


class TestSimServer(unittest.TestCase):
    def setUp(self):
        self.server = SimServer(seed=42, terrain_seed=42, nation_seed=42)

    def test_server_initialization(self):
        self.assertEqual(self.server.turn, 0)
        self.assertFalse(self.server.playing)
        self.assertGreater(len(self.server.tiles), 0)
        self.assertGreater(len(self.server.nations), 0)
        self.assertGreater(len(self.server.currencies), 0)

    def test_server_step(self):
        t1 = self.server.step()
        self.assertEqual(t1, 1)
        self.assertEqual(self.server.turn, 1)

        t2 = self.server.step()
        self.assertEqual(t2, 2)
        self.assertEqual(self.server.turn, 2)

    def test_server_play_pause(self):
        self.server.play()
        self.assertTrue(self.server.playing)
        self.server.pause()
        self.assertFalse(self.server.playing)
        is_playing = self.server.toggle_play()
        self.assertTrue(is_playing)
        self.assertTrue(self.server.playing)

    def test_server_commands(self):
        # Step command
        res = self.server.execute_command(CommandMessage(CommandType.STEP))
        self.assertTrue(res.get('success'))
        self.assertEqual(res.get('turn'), 1)

        # Play / Pause commands
        res_play = self.server.execute_command(CommandMessage(CommandType.PLAY))
        self.assertTrue(res_play.get('success'))
        self.assertTrue(self.server.playing)

        res_pause = self.server.execute_command(CommandMessage(CommandType.PAUSE))
        self.assertTrue(res_pause.get('success'))
        self.assertFalse(self.server.playing)

        # Set speed
        res_spd = self.server.execute_command(CommandMessage(CommandType.SET_SPEED, {'interval': 0.05}))
        self.assertTrue(res_spd.get('success'))
        self.assertAlmostEqual(self.server.turn_interval_sec, 0.05)

        # Policy command
        nation_name = self.server.nations[0].name
        res_pol = self.server.execute_command(CommandMessage(CommandType.SET_POLICY, {
            'nation': nation_name,
            'key': 'statutory_tax_rate',
            'val': 0.25
        }))
        self.assertTrue(res_pol.get('success'))
        self.assertEqual(getattr(self.server.nations[0], 'statutory_tax_rate', None), 0.25)

    def test_server_events(self):
        received_events = []

        def on_event(event_type, data):
            received_events.append((event_type, data))

        self.server.subscribe(on_event)
        self.server.step()
        self.server.unsubscribe(on_event)
        self.server.step()

        # Should have received TURN_ADVANCED from the first step only
        turn_advances = [e for e in received_events if e[0] == ServerEvent.TURN_ADVANCED]
        self.assertEqual(len(turn_advances), 1)
        self.assertEqual(turn_advances[0][1]['turn'], 1)

    def test_get_world_dict_compatibility(self):
        w = self.server.get_world_dict()
        required_keys = ['tiles', 'nations', 'currencies', 'pair_orders', 'by_name',
                         'layout', 'reverse', 'bbox', 'turn', 'playing', 'ticker_events']
        for k in required_keys:
            self.assertIn(k, w)


class TestGameClient(unittest.TestCase):
    def setUp(self):
        self.server = SimServer(seed=42, terrain_seed=42, nation_seed=42)
        self.client = GameClient(server=self.server)

    def test_client_init(self):
        self.assertIsNotNone(self.client.world)
        self.assertEqual(self.client.world['turn'], 0)
        self.assertIsNotNone(self.client.render_engine)

    def test_client_step_and_events(self):
        new_turn = self.client.step()
        self.assertEqual(new_turn, 1)
        self.assertEqual(self.client.world['turn'], 1)

    def test_client_toggle_play(self):
        playing = self.client.toggle_play()
        self.assertTrue(playing)
        self.assertTrue(self.server.playing)
        playing_again = self.client.toggle_play()
        self.assertFalse(playing_again)
        self.assertFalse(self.server.playing)

    def test_client_tile_selection(self):
        tile = self.client.world['tiles'][0]
        self.client.select_tile(tile)
        self.assertEqual(self.client.world['selected_region'], tile)
        self.assertTrue(self.client.world.get('build_panel_open'))


if __name__ == '__main__':
    unittest.main()

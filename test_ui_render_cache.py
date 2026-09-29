"""Focused checks for desktop UI map cache invalidation."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from worldview import _draw_cached_map, _mark_dirty
from worldview_map import _cached_scaled_terrain, draw_dynamic_map_overlays
from worldview_camera import HEIGHT, TOP_BAR_H, WIDTH


class TestDesktopMapCache(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = pygame.display.set_mode((WIDTH, HEIGHT))
        self.world = {'cam': {'zoom': 1.0, 'ox': 0, 'oy': 0}, '_map_generation_done': True}

    def test_ui_redraw_reuses_map_and_camera_or_content_change_invalidates(self):
        def paint_map(surface, *_args):
            surface.fill((20, 40, 60))

        with patch('worldview.draw_hex_map', side_effect=paint_map) as draw_map:
            _draw_cached_map(self.surface, self.world, None, None)
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertEqual(draw_map.call_count, 1)
            self.assertEqual(self.world['_map_cache_stats']['misses'], 1)
            self.assertEqual(self.world['_map_cache_stats']['hits'], 1)
            self.assertGreaterEqual(self.world['_map_cache_stats']['render_ms'], 0.0)
            self.assertEqual(self.surface.get_at((10, TOP_BAR_H + 1))[:3], (20, 40, 60))

            _mark_dirty(self.world, map_changed=False)
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertEqual(draw_map.call_count, 1)
            self.assertEqual(self.world['_map_cache_stats']['hits'], 2)

            self.world['cam']['ox'] = 25
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertEqual(draw_map.call_count, 2)

            _mark_dirty(self.world)
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertEqual(draw_map.call_count, 3)

    def test_initial_generation_draws_on_display_surface(self):
        self.world['_map_generation_done'] = False
        with patch('worldview.draw_hex_map') as draw_map:
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertIs(draw_map.call_args.args[0], self.surface)

    def test_scaled_terrain_cache_reuses_same_source_and_dimensions(self):
        terrain = pygame.Surface((128, 128))
        world = {}
        with patch('worldview_map.pygame.transform.smoothscale', wraps=pygame.transform.smoothscale) as scale:
            first = _cached_scaled_terrain(world, terrain, (64, 64))
            second = _cached_scaled_terrain(world, terrain, (64, 64))
            self.assertIs(first, second)
            self.assertEqual(scale.call_count, 1)
            self.assertEqual(world['_terrain_scale_cache_stats']['hits'], 1)
            self.assertEqual(world['_terrain_scale_cache_stats']['misses'], 1)
            self.assertGreaterEqual(world['_terrain_scale_cache_stats']['scale_ms'], 0.0)

            resized = _cached_scaled_terrain(world, terrain, (32, 32))
            self.assertIsNot(resized, first)
            self.assertEqual(scale.call_count, 2)
            self.assertEqual(world['_terrain_scale_cache_stats']['misses'], 2)

            replacement = pygame.Surface((128, 128))
            _cached_scaled_terrain(world, replacement, (32, 32))
            self.assertEqual(scale.call_count, 3)

    def test_static_map_cache_survives_animation_frame_changes(self):
        self.world['frame'] = 0
        with patch('worldview.draw_hex_map') as draw_map:
            _draw_cached_map(self.surface, self.world, None, None)
            self.world['frame'] = 1
            _draw_cached_map(self.surface, self.world, None, None)
        self.assertEqual(draw_map.call_count, 1)
        self.assertEqual(self.world['_map_cache_stats']['hits'], 1)

    def test_continuously_animated_map_keeps_frame_in_cache_key(self):
        self.world['_map_uses_continuous_animation'] = True
        self.world['frame'] = 0
        with patch('worldview.draw_hex_map') as draw_map:
            _draw_cached_map(self.surface, self.world, None, None)
            self.world['frame'] = 1
            _draw_cached_map(self.surface, self.world, None, None)
        self.assertEqual(draw_map.call_count, 2)

    def test_dynamic_map_pass_draws_water_and_edge_animations(self):
        tile = SimpleNamespace(name='ocean', is_water=True)
        self.world['_cached_hex_geom'] = [(tile, 40, 50, [(30, 40), (50, 40), (50, 60)])]
        with (
            patch('worldview_map.draw_elevation_terrain') as waves,
            patch('worldview_map.draw_edges') as edge_effects,
            patch('worldview_map.draw_trade_arrows') as trade_effects,
        ):
            draw_dynamic_map_overlays(self.surface, self.world)
        waves.assert_called_once()
        self.assertTrue(edge_effects.call_args.kwargs['only_animations'])
        trade_effects.assert_called_once()


if __name__ == '__main__':
    unittest.main()

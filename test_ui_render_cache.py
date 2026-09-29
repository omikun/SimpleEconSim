"""Focused checks for desktop UI map cache invalidation."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from worldview import _draw_cached_map, _mark_dirty
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
            self.assertEqual(self.surface.get_at((10, TOP_BAR_H + 1))[:3], (20, 40, 60))

            _mark_dirty(self.world, map_changed=False)
            _draw_cached_map(self.surface, self.world, None, None)
            self.assertEqual(draw_map.call_count, 1)

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


if __name__ == '__main__':
    unittest.main()

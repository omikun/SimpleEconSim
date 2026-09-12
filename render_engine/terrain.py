"""
render_engine/terrain.py — Terrain rendering and surface management.
"""

import pygame
from heightmap import get_cached_topographic_surface, _TOPOGRAPHIC_SURFACE_CACHE
from world_cache import save_map_cache, invalidate_map_cache
from render_engine.camera import Camera, MAP_PAD_RATIO


class TerrainRenderer:
    """Renders photorealistic topographic surfaces and blits them to the viewport."""

    def __init__(self):
        self.cached_surface = None
        self.current_seed = None
        self.canvas_w = 2400
        self.canvas_h = 1800

    def get_or_generate_surface(self, seed, bbox, tiles=None, layout=None,
                                progress_callback=None, force_regenerate=False):
        """Fetch or synthesize the continuous topographic elevation background."""
        if force_regenerate:
            self.invalidate()

        if self.cached_surface is not None and self.current_seed == seed:
            return self.cached_surface

        surf = get_cached_topographic_surface(
            seed, bbox, tiles=tiles, layout=layout,
            canvas_w=self.canvas_w, canvas_h=self.canvas_h,
            progress_callback=progress_callback
        )
        self.cached_surface = surf
        self.current_seed = seed
        return surf

    def invalidate(self):
        """Clear memory cache for topographic surface."""
        self.cached_surface = None
        self.current_seed = None
        _TOPOGRAPHIC_SURFACE_CACHE.clear()
        invalidate_map_cache()

    def draw_terrain(self, target_surface, camera: Camera, bbox, terrain_surface):
        """Blit the terrain surface transformed by the camera into target_surface."""
        if terrain_surface is None:
            return

        x0, y0, x1, y1 = bbox
        pad_x = (x1 - x0) * MAP_PAD_RATIO
        pad_y = (y1 - y0) * MAP_PAD_RATIO
        min_wx = x0 - pad_x
        min_wy = y0 - pad_y
        world_w = (x1 - x0) + 2 * pad_x
        world_h = (y1 - y0) + 2 * pad_y

        zoom = camera.zoom
        ox, oy = camera.ox, camera.oy

        screen_x = int(min_wx * zoom + ox)
        screen_y = int(min_wy * zoom + oy)
        screen_x1 = int((min_wx + world_w) * zoom + ox)
        screen_y1 = int((min_wy + world_h) * zoom + oy)
        screen_w = max(1, screen_x1 - screen_x)
        screen_h = max(1, screen_y1 - screen_y)

        # Scale surface to viewport projection
        if terrain_surface.get_width() != screen_w or terrain_surface.get_height() != screen_h:
            scaled_surf = pygame.transform.smoothscale(terrain_surface, (screen_w, screen_h))
        else:
            scaled_surf = terrain_surface

        target_surface.blit(scaled_surf, (screen_x, screen_y))

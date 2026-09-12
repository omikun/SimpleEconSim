"""
render_engine/core.py — Central RenderEngine orchestrator.

Coordinates camera, background topographic heightfield, vector hex overlays,
and visual layers. Usable in standalone graphics mode or driven by the GameClient.
"""

import time
import pygame
from render_engine.camera import (
    Camera, HEX_SIZE, WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
)
from render_engine.terrain import TerrainRenderer
from render_engine.hex_renderer import HexRenderer


class RenderEngine:
    """Standalone Graphics & Rendering Engine for REGNUM."""

    def __init__(self, width=WIDTH, height=HEIGHT, map_right=MAP_RIGHT,
                 top_bar_h=TOP_BAR_H, ticker_h=TICKER_H):
        self.width = width
        self.height = height
        self.map_right = map_right
        self.top_bar_h = top_bar_h
        self.ticker_h = ticker_h

        self.viewport_rect = pygame.Rect(0, top_bar_h, map_right, height - top_bar_h - ticker_h)
        self.camera = Camera(vw=map_right, vh=height - top_bar_h - ticker_h, v_x0=0, v_y0=top_bar_h)
        self.terrain_renderer = TerrainRenderer()
        self.hex_renderer = HexRenderer()

        self.last_frame_time_ms = 0.0
        self.fps = 0.0
        self._last_fps_calc = time.time()
        self._frame_count = 0

    def set_bbox(self, bbox):
        self.camera.bbox = bbox
        self.camera.clamp()

    def set_fonts(self, font, font_small):
        self.hex_renderer.set_fonts(font, font_small)

    def invalidate_cache(self):
        """Invalidate the procedural heightmap surface cache."""
        self.terrain_renderer.invalidate()

    def render_map_view(self, surface, seed, bbox, tiles, layout,
                        selected_name=None, hover_name=None,
                        show_grid=True, show_borders=True, show_labels=True,
                        progress_callback=None):
        """Render the complete hex map viewport into surface."""
        t_start = time.perf_counter()

        self.camera.bbox = bbox
        self.camera.clamp()

        # 1. Fetch / synthesize continuous topographic background
        topo_surf = self.terrain_renderer.get_or_generate_surface(
            seed, bbox, tiles=tiles, layout=layout, progress_callback=progress_callback
        )

        # 2. Set viewport clipping
        prev_clip = surface.get_clip()
        surface.set_clip(self.viewport_rect)

        # 3. Blit terrain heightmap
        self.terrain_renderer.draw_terrain(surface, self.camera, bbox, topo_surf)

        # 4. Compute geometry for hexes
        hex_geoms = []
        for t in tiles:
            name = getattr(t, 'name', None) or (t.get('name') if isinstance(t, dict) else str(t))
            coords = layout.get(name)
            if coords is None:
                continue
            cx, cy, pts = self.hex_renderer.compute_hex_corners(self.camera, coords[0], coords[1], HEX_SIZE)
            hex_geoms.append((t, cx, cy, pts))

        # 5. Overlays
        if show_grid:
            self.hex_renderer.draw_grid_lines(surface, hex_geoms)

        if show_borders:
            self.hex_renderer.draw_nation_borders(surface, hex_geoms, self.camera)

        self.hex_renderer.draw_selection(surface, hex_geoms, selected_name, hover_name)

        if show_labels:
            self.hex_renderer.draw_labels(surface, hex_geoms, self.camera)

        # Restore clip
        surface.set_clip(prev_clip)

        # Compute benchmark timings
        self.last_frame_time_ms = (time.perf_counter() - t_start) * 1000.0
        self._frame_count += 1
        now = time.time()
        if now - self._last_fps_calc >= 0.5:
            self.fps = self._frame_count / (now - self._last_fps_calc)
            self._frame_count = 0
            self._last_fps_calc = now

    def render_world(self, surface, world, show_grid=True, show_borders=True, show_labels=True, progress_callback=None):
        """Convenience method to render directly from a world dictionary or client state."""
        seed = world.get('terrain_seed', world.get('seed', 4242))
        bbox = world.get('bbox')
        tiles = world.get('tiles', [])
        layout = world.get('layout', {})
        selected = getattr(world.get('selected_region'), 'name', None) if world.get('selected_region') else None
        hover = getattr(world.get('hover_region'), 'name', None) if world.get('hover_region') else None
        if 'cam' in world:
            self.camera.sync_from_dict(world['cam'])
        self.render_map_view(
            surface=surface, seed=seed, bbox=bbox, tiles=tiles, layout=layout,
            selected_name=selected, hover_name=hover,
            show_grid=show_grid, show_borders=show_borders, show_labels=show_labels,
            progress_callback=progress_callback
        )

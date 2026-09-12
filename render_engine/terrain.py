"""
render_engine/terrain.py — Terrain rendering and surface management.
"""

import time
import pygame
from heightmap import _TOPOGRAPHIC_SURFACE_CACHE, get_cached_topographic_surface
from world_cache import save_map_cache, invalidate_map_cache
from render_engine.camera import Camera, MAP_PAD_RATIO
from render_engine.gpu import get_gpu_pipeline, is_gpu_available, load_gpu_settings


class TerrainRenderer:
    """Renders photorealistic topographic surfaces and blits them to the viewport."""

    def __init__(self, force_cpu: bool = False):
        self.canvas_w = 2400
        self.canvas_h = 1800
        self.force_cpu = force_cpu
        self.gpu_pipeline = get_gpu_pipeline(force_cpu=force_cpu)
        self.last_gen_time_ms = 0.0
        self.used_gpu = False

        # Dual Surface Caches — allows instant flipping back & forth between CPU and GPU
        self.cached_gpu_surface = None
        self.cached_gpu_seed = None
        self.cached_gpu_uniforms_key = None

        self.cached_cpu_surface = None
        self.cached_cpu_seed = None

    @property
    def cached_surface(self):
        """Return the active pipeline's cached surface."""
        return self.cached_cpu_surface if self.force_cpu else self.cached_gpu_surface

    @cached_surface.setter
    def cached_surface(self, surf):
        if self.force_cpu:
            self.cached_cpu_surface = surf
        else:
            self.cached_gpu_surface = surf

    @property
    def current_seed(self):
        return self.cached_cpu_seed if self.force_cpu else self.cached_gpu_seed

    def switch_pipeline(self, force_cpu=None) -> bool:
        """
        Switch between GPU and CPU pipelines without destroying the cached surface
        of the other pipeline. Returns True if now forced to CPU.
        """
        if force_cpu is None:
            self.force_cpu = not self.force_cpu
        else:
            self.force_cpu = bool(force_cpu)
        return self.force_cpu

    def get_or_generate_surface(self, seed, bbox, tiles=None, layout=None,
                                progress_callback=None, force_regenerate=False,
                                uniforms=None):
        """
        Fetch or synthesize the continuous topographic elevation background.
        Uses cached GPU or CPU surface when available for instantaneous display.
        """
        if force_regenerate:
            self.invalidate(all_pipelines=True)

        # 1. CPU Mode: Check cached CPU surface first
        if self.force_cpu:
            if self.cached_cpu_surface is not None and self.cached_cpu_seed == seed:
                self.used_gpu = False
                return self.cached_cpu_surface

            t0 = time.perf_counter()
            surf = get_cached_topographic_surface(
                seed, bbox, tiles=tiles, layout=layout,
                canvas_w=self.canvas_w, canvas_h=self.canvas_h,
                progress_callback=progress_callback
            )
            self.last_gen_time_ms = (time.perf_counter() - t0) * 1000.0
            self.cached_cpu_surface = surf
            self.cached_cpu_seed = seed
            self.used_gpu = False
            return surf

        # 2. GPU Mode: Load persistent shared settings if none provided
        effective_uniforms = dict(load_gpu_settings())
        if uniforms:
            effective_uniforms.update(uniforms)
        uniforms_key = tuple(sorted(effective_uniforms.items()))

        if (self.cached_gpu_surface is not None and
            self.cached_gpu_seed == seed and
            self.cached_gpu_uniforms_key == uniforms_key):
            self.used_gpu = True
            return self.cached_gpu_surface

        # Synthesize on GPU
        surf = None
        t0 = time.perf_counter()

        if is_gpu_available():
            try:
                pipeline = get_gpu_pipeline()
                surf = pipeline.render_topographic_surface(
                    seed=seed,
                    bbox=bbox,
                    tiles=tiles,
                    layout=layout,
                    width=self.canvas_w,
                    height=self.canvas_h,
                    uniforms=effective_uniforms,
                    progress_callback=progress_callback
                )
                self.used_gpu = True
            except Exception as e:
                print(f"[TerrainRenderer] GPU pipeline failed: {e}. Falling back to CPU.")
                self.used_gpu = False

        if surf is not None:
            self.last_gen_time_ms = (time.perf_counter() - t0) * 1000.0
            self.cached_gpu_surface = surf
            self.cached_gpu_seed = seed
            self.cached_gpu_uniforms_key = uniforms_key
            return surf

        # Fallback to CPU if GPU render failed
        surf = get_cached_topographic_surface(
            seed, bbox, tiles=tiles, layout=layout,
            canvas_w=self.canvas_w, canvas_h=self.canvas_h,
            progress_callback=progress_callback
        )
        self.last_gen_time_ms = (time.perf_counter() - t0) * 1000.0
        self.cached_cpu_surface = surf
        self.cached_cpu_seed = seed
        self.used_gpu = False
        return surf

    def invalidate(self, all_pipelines: bool = True):
        """Clear memory cache for topographic surface(s)."""
        if all_pipelines:
            self.cached_gpu_surface = None
            self.cached_gpu_seed = None
            self.cached_gpu_uniforms_key = None
            self.cached_cpu_surface = None
            self.cached_cpu_seed = None
            _TOPOGRAPHIC_SURFACE_CACHE.clear()
            invalidate_map_cache()
        elif self.force_cpu:
            self.cached_cpu_surface = None
            self.cached_cpu_seed = None
        else:
            self.cached_gpu_surface = None
            self.cached_gpu_seed = None
            self.cached_gpu_uniforms_key = None

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

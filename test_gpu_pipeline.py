"""
test_gpu_pipeline.py — Unit tests for the GPU terrain generation pipeline.
"""

import os
import unittest
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
pygame.init()

from render_engine.gpu import get_gpu_pipeline, is_gpu_available
from render_engine.gpu.base import BaseGPUTerrainPipeline
from render_engine.gpu.fallback_pipeline import CPUFallbackPipeline
from render_engine.gpu.moderngl_pipeline import ModernGLTerrainPipeline, MODERNGL_AVAILABLE
from render_engine.terrain import TerrainRenderer
from hexmap import rectangular_hex_layout, hex_bbox
from worldview_camera import HEX_SIZE
from render_dev_viewer import create_mock_island_tiles


class TestGPUPipeline(unittest.TestCase):
    def setUp(self):
        self.rows = 7
        self.cols = 9
        self.layout = rectangular_hex_layout(self.rows, self.cols)
        self.bbox = hex_bbox(self.layout, HEX_SIZE)
        self.tiles = create_mock_island_tiles(seed=4242, rows=self.rows, cols=self.cols)

    def test_pipeline_factory_and_detection(self):
        gpu_ok = is_gpu_available()
        self.assertIsInstance(gpu_ok, bool)

        pipeline = get_gpu_pipeline()
        self.assertIsInstance(pipeline, BaseGPUTerrainPipeline)

        if MODERNGL_AVAILABLE and gpu_ok:
            self.assertIsInstance(pipeline, ModernGLTerrainPipeline)
            self.assertTrue(pipeline.is_available())

    def test_force_cpu_fallback(self):
        cpu_pipeline = get_gpu_pipeline(force_cpu=True)
        self.assertIsInstance(cpu_pipeline, CPUFallbackPipeline)
        self.assertTrue(cpu_pipeline.is_available())

    def test_gpu_surface_rendering(self):
        if not is_gpu_available():
            self.skipTest("ModernGL GPU context is not available in this environment")

        pipeline = get_gpu_pipeline()
        surf = pipeline.render_topographic_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
            width=600,
            height=450,
        )
        self.assertIsInstance(surf, pygame.Surface)
        self.assertEqual(surf.get_size(), (600, 450))

    def test_terrain_renderer_integration(self):
        renderer = TerrainRenderer()
        self.assertIsInstance(renderer, TerrainRenderer)

        # Test generation through renderer
        surf = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIsInstance(surf, pygame.Surface)
        self.assertGreater(renderer.last_gen_time_ms, 0.0)

        # Test caching
        cached_surf = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIs(surf, cached_surf)

        # Test invalidation
        renderer.invalidate()
        self.assertIsNone(renderer.cached_surface)

    def test_shader_uniform_tuning(self):
        if not is_gpu_available():
            self.skipTest("ModernGL GPU context is not available in this environment")

        pipeline = get_gpu_pipeline()
        # All 16 technical controls
        all_16_uniforms = {
            'mountain_roughness': 1.8,
            'shelf_width_mult': 2.0,
            'ocean_depth_mult': 1.5,
            'river_width_mult': 1.6,
            'river_depth_mult': 1.3,
            'lake_depth_mult': 1.4,
            'forest_density': 1.3,
            'canopy_roughness': 1.5,
            'tree_scale': 1.2,
            'plains_grain': 1.4,
            'soil_patchiness': 1.6,
            'grass_warmth': 1.3,
            'sun_intensity': 1.4,
            'ambient_intensity': 0.7,
            'sun_azimuth': 315.0,
            'sun_elevation': 45.0,
        }
        surf = pipeline.render_topographic_surface(
            seed=999,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
            width=600,
            height=450,
            uniforms=all_16_uniforms
        )
        self.assertIsInstance(surf, pygame.Surface)
        self.assertEqual(surf.get_size(), (600, 450))

    def test_river_texture_generation(self):
        if not is_gpu_available():
            self.skipTest("ModernGL GPU context is not available in this environment")

        pipeline = get_gpu_pipeline()
        if not isinstance(pipeline, ModernGLTerrainPipeline):
            self.skipTest("ModernGL pipeline not active")

        # Test river texture generation
        w, h = 400, 300
        pipeline._build_river_texture(4242, self.bbox, w, h)
        self.assertIsNotNone(pipeline.river_tex)
        self.assertEqual(pipeline.river_tex.size, (w, h))
        self.assertEqual(pipeline.river_tex.components, 4)

    def test_slider_widget_logic(self):
        from render_dev_viewer import Slider

        slider = Slider("mountain_roughness", "Mtn Roughness", 0.1, 3.0, 1.0, step=0.05)
        self.assertEqual(slider.key, "mountain_roughness")
        self.assertAlmostEqual(slider.get_ratio(1.0), (1.0 - 0.1) / 2.9)
        self.assertAlmostEqual(slider.get_ratio(0.1), 0.0)
        self.assertAlmostEqual(slider.get_ratio(3.0), 1.0)
        self.assertAlmostEqual(slider.get_ratio(5.0), 1.0)
        self.assertAlmostEqual(slider.get_ratio(-1.0), 0.0)

        # val_from_pos test
        slider.track_rect = pygame.Rect(100, 50, 200, 6)
        # Position exactly at start
        val_start = slider.val_from_pos(100)
        self.assertAlmostEqual(val_start, 0.1)
        # Position at end
        val_end = slider.val_from_pos(300)
        self.assertAlmostEqual(val_end, 3.0)
        # Position at midpoint
        val_mid = slider.val_from_pos(200)
        self.assertAlmostEqual(val_mid, 1.55, places=2)

    def test_terrain_renderer_uniform_caching_and_invalidation(self):
        renderer = TerrainRenderer()
        uniforms_v1 = {'forest_density': 1.0, 'sun_azimuth': 315.0}
        surf_v1 = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
            uniforms=uniforms_v1,
        )

        # Same uniforms -> should return cached instance
        surf_cached = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
            uniforms=uniforms_v1,
        )
        self.assertIs(surf_v1, surf_cached)

        # Modified uniforms -> should trigger re-render
        uniforms_v2 = {'forest_density': 2.0, 'sun_azimuth': 315.0}
        surf_v2 = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
            uniforms=uniforms_v2,
        )
        self.assertIsNot(surf_v1, surf_v2)

    def test_dual_cache_cpu_gpu_flipping(self):
        """Verify that switching between GPU and CPU instantly retrieves the respective cached surface."""
        renderer = TerrainRenderer()

        # 1. Render in GPU mode
        renderer.force_cpu = False
        surf_gpu = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIsNotNone(surf_gpu)
        self.assertTrue(renderer.used_gpu)
        self.assertIs(renderer.cached_gpu_surface, surf_gpu)

        # 2. Switch to CPU mode and render
        renderer.switch_pipeline(force_cpu=True)
        self.assertTrue(renderer.force_cpu)
        surf_cpu = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIsNotNone(surf_cpu)
        self.assertFalse(renderer.used_gpu)
        self.assertIs(renderer.cached_cpu_surface, surf_cpu)

        # 3. Flip back to GPU mode — should instantly return cached GPU surface
        renderer.switch_pipeline(force_cpu=False)
        self.assertFalse(renderer.force_cpu)
        surf_gpu_again = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIs(surf_gpu, surf_gpu_again)

        # 4. Flip back to CPU mode — should instantly return cached CPU surface
        renderer.switch_pipeline(force_cpu=True)
        self.assertTrue(renderer.force_cpu)
        surf_cpu_again = renderer.get_or_generate_surface(
            seed=4242,
            bbox=self.bbox,
            tiles=self.tiles,
            layout=self.layout,
        )
        self.assertIs(surf_cpu, surf_cpu_again)

    def test_persistent_settings_and_backup(self):
        """Verify save, load, backup, and restore of persistent GPU settings."""
        from render_engine.gpu.settings import (
            load_gpu_settings,
            save_gpu_settings,
            revert_gpu_settings_backup,
            has_backup,
            SETTINGS_FILE,
            BACKUP_FILE,
        )
        import shutil

        # Backup existing files if present
        orig_settings = None
        orig_backup = None
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                orig_settings = f.read()
        if os.path.exists(BACKUP_FILE):
            with open(BACKUP_FILE, 'r') as f:
                orig_backup = f.read()

        try:
            # 1. Save new test settings
            test_v1 = {'mountain_roughness': 2.45, 'sun_intensity': 1.85}
            ok, msg = save_gpu_settings(test_v1)
            self.assertTrue(ok)
            loaded_v1 = load_gpu_settings()
            self.assertAlmostEqual(loaded_v1['mountain_roughness'], 2.45)
            self.assertAlmostEqual(loaded_v1['sun_intensity'], 1.85)

            # 2. Save second revision -> should create backup of test_v1
            test_v2 = {'mountain_roughness': 1.15, 'sun_intensity': 0.95}
            ok2, msg2 = save_gpu_settings(test_v2)
            self.assertTrue(ok2)
            self.assertTrue(has_backup())
            loaded_v2 = load_gpu_settings()
            self.assertAlmostEqual(loaded_v2['mountain_roughness'], 1.15)
            self.assertAlmostEqual(loaded_v2['sun_intensity'], 0.95)

            # 3. Revert backup -> should restore test_v1
            ok3, msg3, restored = revert_gpu_settings_backup()
            self.assertTrue(ok3)
            self.assertIsNotNone(restored)
            self.assertAlmostEqual(restored['mountain_roughness'], 2.45)
            self.assertAlmostEqual(restored['sun_intensity'], 1.85)

        finally:
            # Restore original environment
            if orig_settings is not None:
                with open(SETTINGS_FILE, 'w') as f:
                    f.write(orig_settings)
            elif os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)

            if orig_backup is not None:
                with open(BACKUP_FILE, 'w') as f:
                    f.write(orig_backup)
            elif os.path.exists(BACKUP_FILE):
                os.remove(BACKUP_FILE)


if __name__ == '__main__':
    unittest.main()

"""
render_engine/gpu/moderngl_pipeline.py — Multi-pass ModernGL terrain generation pipeline.

Features:
- Pass 1: Continuous Elevation, Hex Conformation, Ridged Mountains, and River/Lake Valley Carving
- Pass 2: Surface Normals, Slope Derivation, and Calm Water Surface Flattening
- Pass 3: Optical Bathymetry, Inland Lakes & Rivers, 2D Volumetric Forest Canopy, and Multi-Scale Plains
"""

import math
import time
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pygame

try:
    import moderngl
    MODERNGL_AVAILABLE = True
except ImportError:
    moderngl = None
    MODERNGL_AVAILABLE = False

from render_engine.gpu.base import BaseGPUTerrainPipeline
from render_engine.gpu.shaders import (
    QUAD_VERT,
    PASS1_ELEV_FRAG,
    PASS2_NORMAL_FRAG,
    PASS3_COMPOSITE_FRAG,
)
from hexmap import rectangular_hex_layout, axial_to_pixel
from worldview_camera import HEX_SIZE
from heightmap import HeightMapGenerator
from render_engine.gpu.settings import load_gpu_settings


class ModernGLTerrainPipeline(BaseGPUTerrainPipeline):
    """GPU-accelerated photorealistic terrain pipeline using multi-pass ModernGL shaders."""

    def __init__(self):
        self.ctx = None
        self.vbo = None

        # Programs & VAOs for 3-pass pipeline
        self.p1 = None
        self.vao1 = None
        self.p2 = None
        self.vao2 = None
        self.p3 = None
        self.vao3 = None

        # Textures & Framebuffers
        self.noise_tex = None
        self.biome_tex = None
        self.river_tex = None

        self.tex_elev = None
        self.tex_aux = None
        self.fbo1 = None

        self.tex_normal = None
        self.fbo2 = None

        self.color_tex = None
        self.fbo_final = None

        self.current_fbo_size = (0, 0)
        self._cached_river_seed = None
        self._cached_river_bbox = None
        self._initialized = False

        if MODERNGL_AVAILABLE:
            self._init_gl()

    def _init_gl(self):
        """Initialize headless ModernGL context, multi-pass shaders, and geometry buffers."""
        try:
            self.ctx = moderngl.create_context(standalone=True)

            # Compile programs for Pass 1, 2, and 3
            self.p1 = self.ctx.program(vertex_shader=QUAD_VERT, fragment_shader=PASS1_ELEV_FRAG)
            self.p2 = self.ctx.program(vertex_shader=QUAD_VERT, fragment_shader=PASS2_NORMAL_FRAG)
            self.p3 = self.ctx.program(vertex_shader=QUAD_VERT, fragment_shader=PASS3_COMPOSITE_FRAG)

            # Fullscreen quad covering normalized device coordinates [-1, 1]
            # Format: in_vert (x, y), in_texcoord (u, v)
            quad_data = np.array([
                -1.0, -1.0, 0.0, 1.0,
                 1.0, -1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 0.0,
                 1.0,  1.0, 1.0, 0.0,
            ], dtype='f4')

            self.vbo = self.ctx.buffer(quad_data.tobytes())
            self.vao1 = self.ctx.vertex_array(self.p1, [(self.vbo, '2f 2f', 'in_vert', 'in_texcoord')])
            self.vao2 = self.ctx.vertex_array(self.p2, [(self.vbo, '2f 2f', 'in_vert', 'in_texcoord')])
            self.vao3 = self.ctx.vertex_array(self.p3, [(self.vbo, '2f 2f', 'in_vert', 'in_texcoord')])

            # Procedural 256x256 permutation noise texture
            generator = HeightMapGenerator(seed=42)
            noise_data = generator.noise_table.astype('f4').tobytes()
            self.noise_tex = self.ctx.texture((256, 256), 1, noise_data, dtype='f4')
            self.noise_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.noise_tex.repeat_x = True
            self.noise_tex.repeat_y = True

            self._initialized = True
        except Exception as e:
            print(f"[ModernGLTerrainPipeline] Failed to initialize OpenGL context: {e}")
            self.release()

    def is_available(self) -> bool:
        return self._initialized and self.ctx is not None

    def _prepare_fbos(self, width: int, height: int):
        """Ensure intermediate and final Framebuffer Objects match target resolution."""
        if self.current_fbo_size == (width, height) and self.fbo_final is not None:
            return

        # Release previous framebuffers & textures
        for res in [self.tex_elev, self.tex_aux, self.fbo1,
                    self.tex_normal, self.fbo2,
                    self.color_tex, self.fbo_final]:
            if res is not None:
                res.release()

        # Pass 1 FBO (Elevation & Biomes MRT)
        self.tex_elev = self.ctx.texture((width, height), 4, dtype='f4')
        self.tex_aux = self.ctx.texture((width, height), 4, dtype='f4')
        self.fbo1 = self.ctx.framebuffer(color_attachments=[self.tex_elev, self.tex_aux])

        # Pass 2 FBO (Normals & Slope)
        self.tex_normal = self.ctx.texture((width, height), 4, dtype='f4')
        self.fbo2 = self.ctx.framebuffer(color_attachments=[self.tex_normal])

        # Pass 3 FBO (Final Composited Screen RGBA8)
        self.color_tex = self.ctx.texture((width, height), 4, dtype='f1')
        self.fbo_final = self.ctx.framebuffer(color_attachments=[self.color_tex])

        self.current_fbo_size = (width, height)

    def _build_biome_grid_texture(self, tiles, layout, grid_rows=9, grid_cols=9):
        """Encode tile biomes into a small float RGBA texture."""
        if layout is None:
            layout = rectangular_hex_layout(grid_rows, grid_cols)

        all_qs = [q for q, r in layout.values()]
        all_rs = [r for q, r in layout.values()]
        min_q, max_q = min(all_qs) - 2, max(all_qs) + 2
        min_r, max_r = min(all_rs) - 2, max(all_rs) + 2
        q_size = max_q - min_q + 1
        r_size = max_r - min_r + 1

        biome_data = np.zeros((r_size, q_size, 4), dtype='f4')

        if tiles:
            for t in tiles:
                coords = layout.get(getattr(t, 'name', None))
                if coords:
                    q, r = coords
                    is_ocean = getattr(t, 'is_ocean', False)
                    elev = getattr(t, 'elevation', 0.0)
                    biome = getattr(t, 'biome', 'plains')

                    if not is_ocean:
                        biome_data[r - min_r, q - min_q, 0] = 1.0
                        if biome == 'forest':
                            biome_data[r - min_r, q - min_q, 1] = 1.0
                        elif biome in ('mountains', 'snow_peaks') or elev >= 0.65:
                            biome_data[r - min_r, q - min_q, 2] = 2.0 if biome == 'snow_peaks' else 1.0
                        elif biome == 'hills':
                            biome_data[r - min_r, q - min_q, 3] = 1.0

        if self.biome_tex is not None:
            self.biome_tex.release()

        self.biome_tex = self.ctx.texture((q_size, r_size), 4, biome_data.tobytes(), dtype='f4')
        self.biome_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        return min_q, min_r, q_size, r_size

    def _build_river_texture(self, seed: int, bbox, width: int = 1200, height: int = 900, river_width_mult: float = 1.0):
        """
        Trace downhill hydraulic rivers & alpine lakes, rasterizing into a 4-channel texture:
        - R: River & lake water surface mask (feathered)
        - G: Accumulated flow & lake depth
        - B: Valley carve depth
        - A: Riparian vegetation margin
        """
        generator = HeightMapGenerator(seed=seed)
        rivers = generator.generate_river_paths()

        # 4 single-channel surfaces: Water, Flow, Carve, Riparian
        surf_w = pygame.Surface((width, height))
        surf_f = pygame.Surface((width, height))
        surf_c = pygame.Surface((width, height))
        surf_a = pygame.Surface((width, height))
        surf_w.fill((0, 0, 0))
        surf_f.fill((0, 0, 0))
        surf_c.fill((0, 0, 0))
        surf_a.fill((0, 0, 0))

        x0, y0, x1, y1 = bbox
        pad_x = (x1 - x0) * 0.18
        pad_y = (y1 - y0) * 0.18
        wx0, wx1 = x0 - pad_x, x1 + pad_x
        wy0, wy1 = y0 - pad_y, y1 + pad_y
        span_x = (x1 - x0) / 2.0
        span_y = (y1 - y0) / 2.0
        cx_center = (x0 + x1) / 2.0
        cy_center = (y0 + y1) / 2.0

        rw_mult = max(0.2, min(3.0, river_width_mult))

        for riv in rivers:
            n_pts = len(riv)
            if n_pts < 2:
                continue

            # Screen-space points
            pts = []
            for nx, ny in riv:
                px_w = nx * span_x + cx_center
                py_w = ny * span_y + cy_center
                sx = int((px_w - wx0) / (wx1 - wx0) * width)
                sy = int((py_w - wy0) / (wy1 - wy0) * height)
                pts.append((sx, sy))

            # Detect inland lake basin (if terminus didn't plunge to sea level)
            end_h = generator.get_continuous_height(riv[-1][0], riv[-1][1])
            is_lake = end_h > 0.02
            end_pt = pts[-1]

            # 1. Draw River segments along path
            for k in range(n_pts - 1):
                p0 = pts[k]
                p1 = pts[k + 1]
                prog = float(k) / max(1.0, float(n_pts - 1))
                flow = prog ** 0.7

                w_water = max(2, int((2.5 + 8.0 * flow) * rw_mult))
                w_carve = max(6, int((8.0 + 22.0 * flow) * rw_mult))
                w_rip = max(14, int((16.0 + 40.0 * flow) * rw_mult))

                flow_val = int(min(255, 60 + 195 * flow))

                pygame.draw.line(surf_a, (200, 200, 200), p0, p1, w_rip)
                pygame.draw.line(surf_c, (180, 180, 180), p0, p1, w_carve)
                pygame.draw.line(surf_w, (255, 255, 255), p0, p1, w_water)
                pygame.draw.line(surf_f, (flow_val, flow_val, flow_val), p0, p1, w_water)

            # 2. Draw Alpine Tarn Lake at sink terminus
            if is_lake:
                lake_r = max(12, int((14.0 + 18.0 * min(1.0, n_pts / 40.0)) * rw_mult))
                # Riparian margin
                pygame.draw.circle(surf_a, (230, 230, 230), end_pt, int(lake_r * 2.2))
                # Valley carve depression
                pygame.draw.circle(surf_c, (220, 220, 220), end_pt, int(lake_r * 1.5))
                # Lake water body
                pygame.draw.circle(surf_w, (255, 255, 255), end_pt, lake_r)
                # Deep lake depth
                pygame.draw.circle(surf_f, (240, 240, 240), end_pt, lake_r)

        # Pack into 4-channel texture buffer (R=water, G=flow, B=carve, A=riparian)
        w_arr = pygame.surfarray.pixels_red(surf_w)
        f_arr = pygame.surfarray.pixels_red(surf_f)
        c_arr = pygame.surfarray.pixels_red(surf_c)
        a_arr = pygame.surfarray.pixels_red(surf_a)

        # Transpose from Pygame (w, h) to OpenGL (h, w)
        tex_data = np.stack([
            np.transpose(w_arr, (1, 0)),
            np.transpose(f_arr, (1, 0)),
            np.transpose(c_arr, (1, 0)),
            np.transpose(a_arr, (1, 0)),
        ], axis=-1).astype(np.uint8)

        if self.river_tex is not None:
            self.river_tex.release()

        self.river_tex = self.ctx.texture((width, height), 4, tex_data.tobytes(), dtype='f1')
        self.river_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    @staticmethod
    def _set_uniform(prog, name: str, val):
        if name in prog:
            prog[name].value = val

    def render_topographic_surface(
        self,
        seed: int,
        bbox: Tuple[float, float, float, float],
        tiles: Optional[list] = None,
        layout: Optional[dict] = None,
        width: int = 2400,
        height: int = 1800,
        uniforms: Optional[Dict[str, Any]] = None,
        progress_callback=None,
    ) -> pygame.Surface:
        """Execute the multi-pass GPU shader pipeline to produce the Ultra-HD surface."""
        if not self.is_available():
            raise RuntimeError("ModernGL GPU context is not available.")

        if progress_callback:
            progress_callback(0.10, "Dispatching multi-pass GPU terrain pipeline...")

        x0, y0, x1, y1 = bbox
        pad_x = (x1 - x0) * 0.18
        pad_y = (y1 - y0) * 0.18
        min_wx = x0 - pad_x
        max_wx = x1 + pad_x
        min_wy = y0 - pad_y
        max_wy = y1 + pad_y

        span_x = (x1 - x0) / 2.0
        span_y = (y1 - y0) / 2.0
        cx_center = (x0 + x1) / 2.0
        cy_center = (y0 + y1) / 2.0

        u_dict = dict(load_gpu_settings())
        if uniforms:
            u_dict.update(uniforms)

        # Technical parameter uniforms
        mountain_roughness = float(u_dict.get('mountain_roughness', 1.0))
        shelf_width_mult = float(u_dict.get('shelf_width_mult', 1.0))
        ocean_depth_mult = float(u_dict.get('ocean_depth_mult', 1.0))
        river_depth_mult = float(u_dict.get('river_depth_mult', 1.0))
        river_width_mult = float(u_dict.get('river_width_mult', 1.0))
        lake_depth_mult = float(u_dict.get('lake_depth_mult', 1.0))

        forest_density = float(u_dict.get('forest_density', 1.0))
        canopy_roughness = float(u_dict.get('canopy_roughness', 1.0))
        tree_scale = float(u_dict.get('tree_scale', 1.0))

        plains_grain = float(u_dict.get('plains_grain', 1.0))
        soil_patchiness = float(u_dict.get('soil_patchiness', 1.0))
        grass_warmth = float(u_dict.get('grass_warmth', 1.0))

        sun_intensity = float(u_dict.get('sun_intensity', 1.0))
        ambient_intensity = float(u_dict.get('ambient_intensity', 0.6))
        sun_azimuth = float(u_dict.get('sun_azimuth', -135.0))
        sun_elevation = float(u_dict.get('sun_elevation', 42.0))

        # Calculate sun direction vector from azimuth & elevation
        az_rad = math.radians(sun_azimuth)
        el_rad = math.radians(max(5.0, min(88.0, sun_elevation)))
        sun_x = math.cos(el_rad) * math.cos(az_rad)
        sun_y = math.cos(el_rad) * math.sin(az_rad)
        sun_z = math.sin(el_rad)
        sun_len = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2) + 1e-6
        sun_dir = (sun_x / sun_len, sun_y / sun_len, sun_z / sun_len)

        # Upload biome texture, river map & prepare framebuffers
        min_q, min_r, q_size, r_size = self._build_biome_grid_texture(tiles, layout)
        self._build_river_texture(seed, bbox, river_width_mult=river_width_mult)
        self._prepare_fbos(width, height)

        # --- PASS 1: Continuous Elevation, Hex Conformation & Valley Carving ---
        if progress_callback:
            progress_callback(0.25, "Pass 1: Elevation, hex conformation & valley carving...")

        self.fbo1.use()
        self.ctx.viewport = (0, 0, width, height)
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)

        self.noise_tex.use(location=0)
        self.biome_tex.use(location=1)
        self.river_tex.use(location=2)

        self._set_uniform(self.p1, 'u_bbox', (float(min_wx), float(min_wy), float(max_wx), float(max_wy)))
        self._set_uniform(self.p1, 'u_center', (float(cx_center), float(cy_center)))
        self._set_uniform(self.p1, 'u_span', (float(span_x), float(span_y)))
        self._set_uniform(self.p1, 'u_hex_size', float(HEX_SIZE))
        self._set_uniform(self.p1, 'u_seed', float(seed % 10000))
        self._set_uniform(self.p1, 'u_grid_bounds', (float(min_q), float(min_r), float(q_size), float(r_size)))
        self._set_uniform(self.p1, 'u_noise_tex', 0)
        self._set_uniform(self.p1, 'u_biome_grid', 1)
        self._set_uniform(self.p1, 'u_river_tex', 2)
        self._set_uniform(self.p1, 'u_mountain_roughness', mountain_roughness)
        self._set_uniform(self.p1, 'u_shelf_width_mult', shelf_width_mult)
        self._set_uniform(self.p1, 'u_ocean_depth_mult', ocean_depth_mult)
        self._set_uniform(self.p1, 'u_river_depth_mult', river_depth_mult)
        self._set_uniform(self.p1, 'u_lake_depth_mult', lake_depth_mult)
        self.vao1.render(moderngl.TRIANGLE_STRIP)

        # --- PASS 2: Surface Normals & Water Surface Smoothing ---
        if progress_callback:
            progress_callback(0.55, "Pass 2: Finite-difference normals & water flattening...")

        self.fbo2.use()
        self.ctx.viewport = (0, 0, width, height)
        self.ctx.clear(0.0, 0.0, 1.0, 0.0)

        self.tex_elev.use(location=0)
        self.river_tex.use(location=1)
        self.noise_tex.use(location=2)
        self._set_uniform(self.p2, 'u_elev_tex', 0)
        self._set_uniform(self.p2, 'u_river_tex', 1)
        self._set_uniform(self.p2, 'u_noise_tex', 2)
        self._set_uniform(self.p2, 'u_resolution', (float(width), float(height)))
        self._set_uniform(self.p2, 'u_bbox', (float(min_wx), float(min_wy), float(max_wx), float(max_wy)))
        self.vao2.render(moderngl.TRIANGLE_STRIP)

        # --- PASS 3: Lighting, Bathymetry, Inland Water, Forest & Plains Compositor ---
        if progress_callback:
            progress_callback(0.75, "Pass 3: Lighting, bathymetry, forest canopy & plains...")

        self.fbo_final.use()
        self.ctx.viewport = (0, 0, width, height)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        self.tex_elev.use(location=0)
        self.tex_aux.use(location=1)
        self.tex_normal.use(location=2)
        self.river_tex.use(location=3)
        self.noise_tex.use(location=4)

        self._set_uniform(self.p3, 'u_elev_tex', 0)
        self._set_uniform(self.p3, 'u_aux_tex', 1)
        self._set_uniform(self.p3, 'u_normal_tex', 2)
        self._set_uniform(self.p3, 'u_river_tex', 3)
        self._set_uniform(self.p3, 'u_noise_tex', 4)
        self._set_uniform(self.p3, 'u_bbox', (float(min_wx), float(min_wy), float(max_wx), float(max_wy)))
        self._set_uniform(self.p3, 'u_seed', float(seed % 10000))

        self._set_uniform(self.p3, 'u_sun_dir', sun_dir)
        self._set_uniform(self.p3, 'u_sun_intensity', sun_intensity)
        self._set_uniform(self.p3, 'u_ambient_intensity', ambient_intensity)

        self._set_uniform(self.p3, 'u_forest_density', forest_density)
        self._set_uniform(self.p3, 'u_canopy_roughness', canopy_roughness)
        self._set_uniform(self.p3, 'u_tree_scale', tree_scale)
        self._set_uniform(self.p3, 'u_plains_grain', plains_grain)
        self._set_uniform(self.p3, 'u_soil_patchiness', soil_patchiness)
        self._set_uniform(self.p3, 'u_grass_warmth', grass_warmth)
        self._set_uniform(self.p3, 'u_lake_depth_mult', lake_depth_mult)

        self.vao3.render(moderngl.TRIANGLE_STRIP)

        if progress_callback:
            progress_callback(0.90, "Reading back GPU frame buffer...")

        # Read back RGBA8 pixels to host CPU memory
        raw_bytes = self.fbo_final.read(components=4, alignment=1)
        surf = pygame.image.frombuffer(raw_bytes, (width, height), 'RGBA')

        if progress_callback:
            progress_callback(1.0, "Multi-pass GPU terrain synthesis complete!")

        return surf

    def release(self):
        """Release all allocated ModernGL resources."""
        resources = [
            self.noise_tex, self.biome_tex, self.river_tex,
            self.tex_elev, self.tex_aux, self.fbo1,
            self.tex_normal, self.fbo2,
            self.color_tex, self.fbo_final,
            self.vbo,
            self.vao1, self.vao2, self.vao3,
            self.p1, self.p2, self.p3,
            self.ctx,
        ]
        for res in resources:
            if res is not None:
                try:
                    res.release()
                except Exception:
                    pass

        self.noise_tex = None
        self.biome_tex = None
        self.river_tex = None
        self.tex_elev = None
        self.tex_aux = None
        self.fbo1 = None
        self.tex_normal = None
        self.fbo2 = None
        self.color_tex = None
        self.fbo_final = None
        self.vbo = None
        self.vao1 = None
        self.vao2 = None
        self.vao3 = None
        self.p1 = None
        self.p2 = None
        self.p3 = None
        self.ctx = None
        self._initialized = False

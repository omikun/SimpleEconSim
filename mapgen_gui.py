#!/usr/bin/env python3
"""
mapgen_gui.py — Interactive Mapgen2-Style Polygonal Terrain Explorer & GUI.

Allows live interactive tweaking of all map generation, elevation hypsometry,
fractal micropoly subdivision, and multi-light shading knobs with immediate
visual canvas feedback and one-click 2D/3D exports.

Usage:
    python3 mapgen_gui.py [--seed 777] [--points 1000] [--polys 16000]
"""

import sys
import os
import math
import time
import random
from typing import Optional, Tuple, List, Dict, Any

import pygame
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from polygon_map import PolygonMapGenerator, BIOME_COLORS
from render_island_micropolys import (
    build_island_mesh,
    render_mesh,
    export_island_wireframe_usdz,
)

# ---------------------------------------------------------------------------
# Color Palette & Styling
# ---------------------------------------------------------------------------
BG_DARK = (18, 22, 28)
PANEL_BG = (26, 32, 42)
PANEL_BORDER = (42, 52, 68)
HEADER_BG = (34, 42, 56)
TEXT_WHITE = (240, 244, 250)
TEXT_MUTED = (140, 155, 175)
TEXT_ACCENT = (70, 180, 240)
BTN_DEFAULT = (44, 54, 70)
BTN_HOVER = (58, 72, 94)
BTN_ACTIVE = (40, 130, 220)
BTN_BORDER = (65, 80, 105)
SLIDER_TRACK = (38, 46, 60)
SLIDER_FILL = (45, 140, 230)
SLIDER_THUMB = (245, 248, 255)
SLIDER_THUMB_BORDER = (30, 100, 180)
SUCCESS_GREEN = (40, 190, 110)


def get_ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load native macOS typography directly to avoid directory scanning errors."""
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
    try:
        return pygame.font.SysFont("Helvetica", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


# ---------------------------------------------------------------------------
# UI Widgets: Slider, Button
# ---------------------------------------------------------------------------
class Slider:
    """Draggable slider with label, readout, step snapping, and live dragging."""

    def __init__(
        self,
        key: str,
        label: str,
        min_val: float,
        max_val: float,
        default_val: float,
        step: float = 0.05,
        fmt: str = "{:.2f}",
    ):
        self.key = key
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.default_val = default_val
        self.val = default_val
        self.step = step
        self.fmt = fmt

        self.track_rect = pygame.Rect(0, 0, 0, 0)
        self.thumb_rect = pygame.Rect(0, 0, 0, 0)
        self.is_dragging = False

    def update_from_pos(self, mx: int) -> bool:
        if self.track_rect.width <= 0:
            return False
        ratio = max(0.0, min(1.0, (mx - self.track_rect.x) / float(self.track_rect.width)))
        raw = self.min_val + ratio * (self.max_val - self.min_val)
        steps = round((raw - self.min_val) / self.step)
        new_val = max(self.min_val, min(self.max_val, self.min_val + steps * self.step))
        if abs(new_val - self.val) > 1e-5:
            self.val = new_val
            return True
        return False

    def draw(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        font: pygame.font.Font,
        font_small: pygame.font.Font,
        mouse_pos: Tuple[int, int],
    ):
        # 1. Label and Value Readout
        lbl_surf = font_small.render(self.label, True, TEXT_WHITE)
        surface.blit(lbl_surf, (x, y))

        val_str = self.fmt.format(self.val)
        val_surf = font_small.render(val_str, True, TEXT_ACCENT)
        surface.blit(val_surf, (x + width - val_surf.get_width(), y))

        # 2. Track Bar
        track_y = y + 17
        track_h = 5
        self.track_rect = pygame.Rect(x, track_y, width, track_h)
        pygame.draw.rect(surface, SLIDER_TRACK, self.track_rect, border_radius=3)

        ratio = (self.val - self.min_val) / max(1e-6, (self.max_val - self.min_val))
        fill_w = max(0, int(width * ratio))
        if fill_w > 0:
            fill_rect = pygame.Rect(x, track_y, fill_w, track_h)
            pygame.draw.rect(surface, SLIDER_FILL, fill_rect, border_radius=3)

        # 3. Draggable Thumb
        thumb_x = x + fill_w
        thumb_r = 6
        self.thumb_rect = pygame.Rect(thumb_x - thumb_r, track_y + track_h // 2 - thumb_r, thumb_r * 2, thumb_r * 2)

        is_hover = self.thumb_rect.collidepoint(mouse_pos) or self.is_dragging
        t_color = (255, 255, 255) if is_hover else SLIDER_THUMB
        pygame.draw.circle(surface, t_color, self.thumb_rect.center, thumb_r)
        pygame.draw.circle(surface, SLIDER_THUMB_BORDER, self.thumb_rect.center, thumb_r, width=2)


class Button:
    """Clickable button with active state, hover highlighting, and clean typography."""

    def __init__(self, key: str, label: str, rect: pygame.Rect = None):
        self.key = key
        self.label = label
        self.rect = rect or pygame.Rect(0, 0, 0, 0)
        self.is_active = False

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        mouse_pos: Tuple[int, int],
        bg_color: Optional[Tuple[int, int, int]] = None,
    ):
        mx, my = mouse_pos
        is_hover = self.rect.collidepoint(mx, my)

        if self.is_active:
            col = BTN_ACTIVE
            b_col = (100, 190, 255)
            t_col = (255, 255, 255)
        elif is_hover:
            col = BTN_HOVER
            b_col = (90, 115, 145)
            t_col = (255, 255, 255)
        else:
            col = bg_color or BTN_DEFAULT
            b_col = BTN_BORDER
            t_col = TEXT_WHITE

        pygame.draw.rect(surface, col, self.rect, border_radius=4)
        pygame.draw.rect(surface, b_col, self.rect, width=1, border_radius=4)

        t_surf = font.render(self.label, True, t_col)
        tx = self.rect.centerx - t_surf.get_width() // 2
        ty = self.rect.centery - t_surf.get_height() // 2
        surface.blit(t_surf, (tx, ty))


# ---------------------------------------------------------------------------
# Main Interactive GUI Application
# ---------------------------------------------------------------------------
class MapgenGUI:
    """Comprehensive Mapgen2 interactive graphical explorer."""

    def __init__(
        self,
        seed: int = 777,
        num_points: int = 1000,
        target_polys: int = 16000,
        window_size: Tuple[int, int] = (1280, 830),
    ):
        pygame.init()
        pygame.font.init()

        self.win_w, self.win_h = window_size
        self.canvas_size = 760
        self.canvas_rect = pygame.Rect(20, 20, self.canvas_size, self.canvas_size)

        self.screen = pygame.display.set_mode((self.win_w, self.win_h), pygame.RESIZABLE)
        pygame.display.set_caption("Mapgen2 Terrain Explorer — Micropoly Subdivision & Hypsometry")

        # Fonts
        self.font_title = get_ui_font(18, bold=True)
        self.font_ui = get_ui_font(13, bold=True)
        self.font_small = get_ui_font(11)
        self.font_tiny = get_ui_font(10)

        # State Variables
        self.seed = seed
        self.island_shape = "radial"
        self.view_mode = "micropolys"  # micropolys, biomes, elevation, moisture, watersheds, wireframe
        self.show_rivers = True
        self.show_roads = True
        self.show_lava = True
        self.show_noisy = True

        # Cache tiers
        self.gen: Optional[PolygonMapGenerator] = None
        self.triangles: List[Tuple] = []
        self.cached_canvas: Optional[pygame.Surface] = None
        self.status_msg = "Ready."
        self.status_time = time.time()
        self.gen_time_ms = 0.0
        self.render_time_ms = 0.0

        # Sliders
        self.sliders = {
            "height_scale": Slider("height_scale", "Height Scale (Relief)", 20.0, 180.0, 70.0, step=2.0, fmt="{:.0f}"),
            "sharpness": Slider("sharpness", "Mountain Sharpness (Power)", 0.70, 2.50, 1.00, step=0.05, fmt="{:.2f}"),
            "polys": Slider("polys", "Target Micropolygons", 1000, 32000, target_polys, step=1000, fmt="{:,.0f}"),
            "roughness": Slider("roughness", "Fractal Roughness", 0.0, 8.0, 3.0, step=0.2, fmt="{:.1f}"),
            "jitter": Slider("jitter", "Lateral Edge Jitter", 0.0, 0.40, 0.22, step=0.02, fmt="{:.2f}"),
            "smooth": Slider("smooth", "Normal Smoothing Ratio", 0.0, 1.0, 0.70, step=0.05, fmt="{:.2f}"),
            "alpha": Slider("alpha", "Ridge Alpha (α)", 0.0, 0.50, 0.25, step=0.02, fmt="{:.2f}"),
            "points": Slider("points", "Voronoi Points", 200, 2000, num_points, step=50, fmt="{:.0f}"),
            "rivers": Slider("rivers", "River Sources", 0, 50, 25, step=5, fmt="{:.0f}"),
        }

        # Buttons
        self.view_buttons = [
            Button("micropolys", "Micropolys"),
            Button("biomes", "Biomes"),
            Button("elevation", "Elevation"),
            Button("moisture", "Moisture"),
            Button("watersheds", "Watersheds"),
            Button("wireframe", "Wireframe"),
        ]

        self.shape_buttons = [
            Button("radial", "Radial"),
            Button("perlin", "Perlin"),
            Button("blob", "Blob"),
            Button("square", "Square"),
        ]

        self.feature_buttons = [
            Button("toggle_rivers", "Rivers: ON"),
            Button("toggle_roads", "Roads: ON"),
            Button("toggle_lava", "Lava: ON"),
            Button("toggle_noisy", "Noisy: ON"),
        ]

        self.action_buttons = {
            "random": Button("random", "Randomize Seed"),
            "save_png": Button("save_png", "Save PNG"),
            "export_usdz": Button("export_usdz", "Export 3D USDZ"),
            "reset": Button("reset", "Reset Defaults"),
        }

        # Initial Generation
        self.rebuild_map_graph()

    # -----------------------------------------------------------------------
    # Generation & Rendering Pipeline
    # -----------------------------------------------------------------------
    def rebuild_map_graph(self):
        """Tier 1: Rebuild base Voronoi graph and hydrology."""
        t0 = time.time()
        self.status_msg = f"Generating base mesh (seed {self.seed}, {int(self.sliders['points'].val)} points)..."

        self.gen = PolygonMapGenerator(
            seed=self.seed,
            width=self.canvas_size,
            height=self.canvas_size,
            num_points=int(self.sliders["points"].val),
            island_shape=self.island_shape,
            river_count=int(self.sliders["rivers"].val),
            mountain_sharpness=self.sliders["sharpness"].val,
            enable_corner_improvement=True,
            enable_roads=self.show_roads,
            enable_lava=self.show_lava,
            enable_noisy_edges=self.show_noisy,
        )
        self.gen_time_ms = (time.time() - t0) * 1000.0
        self.rebuild_micropoly_mesh()

    def rebuild_micropoly_mesh(self):
        """Tier 2: Subdivide mesh into micropolygons with 3D elevations."""
        if not self.gen:
            return
        t0 = time.time()
        self.triangles, _ = build_island_mesh(
            self.gen,
            width=self.canvas_size,
            height=self.canvas_size,
            mode="fractal",
            target_polys=int(self.sliders["polys"].val),
            roughness=self.sliders["roughness"].val,
            lateral_jitter=self.sliders["jitter"].val,
            elevation_alpha=self.sliders["alpha"].val,
            elev_scale=self.sliders["height_scale"].val,
            normal_smooth_ratio=self.sliders["smooth"].val,
        )
        self.render_time_ms = (time.time() - t0) * 1000.0
        self.redraw_canvas()

    def redraw_canvas(self):
        """Tier 3: Render current view mode to cached surface."""
        if not self.gen:
            return

        surf = pygame.Surface((self.canvas_size, self.canvas_size))
        surf.fill((13, 36, 82))  # Ocean deep blue

        mode = self.view_mode
        t0 = time.time()

        if mode == "micropolys":
            # 3D Shaded micropoly mesh with multi-light illumination
            surf = render_mesh(self.gen, self.triangles, width=self.canvas_size, height=self.canvas_size)

        elif mode == "biomes":
            # Classical Whittaker Biome view with noisy contours
            surf = self.gen.render_to_surface(
                width=self.canvas_size,
                height=self.canvas_size,
                use_brdf=True,
                use_noisy_edges=self.show_noisy,
                show_roads=self.show_roads,
                show_lava=self.show_lava,
                render_micropolys=False,
            )

        elif mode == "elevation":
            # Hypsometric gradient showing lowlands vs sharp mountain crests
            for c in self.gen.centers:
                if c.ocean:
                    col = (18, 48, 100)
                elif c.water:
                    col = (40, 110, 175)
                else:
                    # Lowlands: lush green -> golden foothills -> rocky brown -> alpine snow
                    e = min(1.0, max(0.0, c.elevation))
                    if e < 0.25:
                        t = e / 0.25
                        col = (int(50 + 60 * t), int(140 + 40 * t), int(50 + 30 * t))
                    elif e < 0.60:
                        t = (e - 0.25) / 0.35
                        col = (int(110 + 70 * t), int(180 - 40 * t), int(80 - 20 * t))
                    elif e < 0.82:
                        t = (e - 0.60) / 0.22
                        col = (int(180 - 40 * t), int(140 - 20 * t), int(60 + 40 * t))
                    else:
                        t = (e - 0.82) / 0.18
                        col = (int(140 + 110 * t), int(120 + 130 * t), int(100 + 155 * t))

                poly = self.gen.get_polygon_noisy_boundary(c) if self.show_noisy else [[cn.x, cn.y] for cn in c.corners]
                if len(poly) >= 3:
                    pygame.draw.polygon(surf, col, poly)

        elif mode == "moisture":
            # Moisture gradient from arid desert (yellow/brown) to humid rainforest (deep blue-green)
            for c in self.gen.centers:
                if c.ocean:
                    col = (18, 48, 100)
                elif c.water:
                    col = (40, 110, 175)
                else:
                    m = min(1.0, max(0.0, c.moisture))
                    col = (
                        int(210 * (1.0 - m) + 20 * m),
                        int(190 * (1.0 - m) + 160 * m),
                        int(90 * (1.0 - m) + 80 * m),
                    )
                poly = self.gen.get_polygon_noisy_boundary(c) if self.show_noisy else [[cn.x, cn.y] for cn in c.corners]
                if len(poly) >= 3:
                    pygame.draw.polygon(surf, col, poly)

        elif mode == "watersheds":
            # Distinct drainage basins flowing into ocean
            surf = self.gen.render_to_surface(
                width=self.canvas_size,
                height=self.canvas_size,
                use_brdf=False,
                show_watersheds=True,
                render_micropolys=False,
            )

        elif mode == "wireframe":
            # Debug Voronoi cell boundaries + dual Delaunay edges
            surf.fill((22, 26, 34))
            for e in self.gen.edges:
                if e.v0 and e.v1:
                    col = (60, 90, 130) if (e.d0 and e.d0.water and e.d1 and e.d1.water) else (140, 160, 190)
                    pygame.draw.line(surf, col, (e.v0.x, e.v0.y), (e.v1.x, e.v1.y), 1)
                if e.d0 and e.d1:
                    pygame.draw.line(surf, (180, 80, 80), (e.d0.x, e.d0.y), (e.d1.x, e.d1.y), 1)

        # Overlay rivers and roads if requested and not in 3D micropoly mode (which already has them)
        if mode not in ("micropolys", "biomes", "watersheds"):
            if self.show_rivers and self.gen.noisy_edges:
                for e in self.gen.edges:
                    if e.river > 0:
                        pts = self.gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                        if len(pts) >= 2:
                            w = min(4, max(1, int(1 + math.sqrt(e.river))))
                            pygame.draw.lines(surf, (35, 95, 175), False, pts, width=w)

        self.cached_canvas = surf
        dur = (time.time() - t0) * 1000.0
        self.status_msg = f"Rendered '{self.view_mode}' in {dur:.1f}ms | Polys: {len(self.triangles):,}"

    # -----------------------------------------------------------------------
    # Event Handling
    # -----------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            elif event.key == pygame.K_r:
                self.seed = random.randint(1, 99999)
                self.rebuild_map_graph()
            elif event.key == pygame.K_s:
                self.save_png_action()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos

                # 1. Slider Thumb Drags
                for s in self.sliders.values():
                    if s.thumb_rect.collidepoint(mx, my) or s.track_rect.collidepoint(mx, my):
                        s.is_dragging = True
                        if s.update_from_pos(mx):
                            self._on_slider_changed(s.key)
                        return True

                # 2. View Mode Buttons
                for btn in self.view_buttons:
                    if btn.rect.collidepoint(mx, my):
                        self.view_mode = btn.key
                        self.redraw_canvas()
                        return True

                # 3. Shape Buttons
                for btn in self.shape_buttons:
                    if btn.rect.collidepoint(mx, my):
                        self.island_shape = btn.key
                        self.rebuild_map_graph()
                        return True

                # 4. Feature Toggle Buttons
                for btn in self.feature_buttons:
                    if btn.rect.collidepoint(mx, my):
                        if btn.key == "toggle_rivers":
                            self.show_rivers = not self.show_rivers
                            btn.label = f"Rivers: {'ON' if self.show_rivers else 'OFF'}"
                        elif btn.key == "toggle_roads":
                            self.show_roads = not self.show_roads
                            btn.label = f"Roads: {'ON' if self.show_roads else 'OFF'}"
                        elif btn.key == "toggle_lava":
                            self.show_lava = not self.show_lava
                            btn.label = f"Lava: {'ON' if self.show_lava else 'OFF'}"
                        elif btn.key == "toggle_noisy":
                            self.show_noisy = not self.show_noisy
                            btn.label = f"Noisy: {'ON' if self.show_noisy else 'OFF'}"
                        self.redraw_canvas()
                        return True

                # 5. Action Buttons
                for key, btn in self.action_buttons.items():
                    if btn.rect.collidepoint(mx, my):
                        self._on_action_clicked(key)
                        return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                for s in self.sliders.values():
                    s.is_dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0]:
                mx, my = event.pos
                for s in self.sliders.values():
                    if s.is_dragging:
                        if s.update_from_pos(mx):
                            self._on_slider_changed(s.key)
                        return True

        return True

    def _on_slider_changed(self, key: str):
        """Intelligently branch update tiers based on changed knob."""
        if key in ("points", "rivers", "sharpness"):
            self.rebuild_map_graph()
        elif key in ("height_scale", "polys", "roughness", "jitter", "smooth", "alpha"):
            self.rebuild_micropoly_mesh()
        else:
            self.redraw_canvas()

    def _on_action_clicked(self, key: str):
        if key == "random":
            self.seed = random.randint(1, 99999)
            self.rebuild_map_graph()
        elif key == "save_png":
            self.save_png_action()
        elif key == "export_usdz":
            self.export_usdz_action()
        elif key == "reset":
            for s in self.sliders.values():
                s.val = s.default_val
            self.island_shape = "radial"
            self.view_mode = "micropolys"
            self.rebuild_map_graph()

    def save_png_action(self):
        """Export current map view to PNG."""
        if self.cached_canvas:
            out_path = os.path.abspath(f"island_seed_{self.seed}_{self.view_mode}.png")
            pygame.image.save(self.cached_canvas, out_path)
            self.status_msg = f"Saved PNG: {os.path.basename(out_path)}"
            self.status_time = time.time()

    def export_usdz_action(self):
        """Export 3D wireframe USDZ package for Quick Look."""
        if self.gen and self.triangles:
            out_path = os.path.abspath(f"island_seed_{self.seed}.usdz")
            export_island_wireframe_usdz(self.gen, self.triangles, out_path, wire_width=0.8)
            self.status_msg = f"Exported USDZ: {os.path.basename(out_path)}"
            self.status_time = time.time()

    # -----------------------------------------------------------------------
    # Main Render Loop & Layout
    # -----------------------------------------------------------------------
    def draw_ui(self):
        self.screen.fill(BG_DARK)
        mouse_pos = pygame.mouse.get_pos()

        # 1. Map Canvas
        if self.cached_canvas:
            self.screen.blit(self.cached_canvas, self.canvas_rect.topleft)
        pygame.draw.rect(self.screen, PANEL_BORDER, self.canvas_rect, width=2, border_radius=4)

        # 2. Bottom Status Bar
        stat_rect = pygame.Rect(20, 788, self.canvas_size, 32)
        pygame.draw.rect(self.screen, PANEL_BG, stat_rect, border_radius=4)
        pygame.draw.rect(self.screen, PANEL_BORDER, stat_rect, width=1, border_radius=4)

        # Inspect cell under cursor if over canvas
        hover_str = ""
        mx, my = mouse_pos
        if self.canvas_rect.collidepoint(mx, my) and self.gen:
            cx = mx - self.canvas_rect.x
            cy = my - self.canvas_rect.y
            nearest_center = self.gen.get_center_at(cx, cy)
            if nearest_center:
                hover_str = f" | Cell #{nearest_center.index} ({nearest_center.biome.upper()}) elv:{nearest_center.elevation:.2f} mst:{nearest_center.moisture:.2f}"

        stat_str = f"{self.status_msg}{hover_str}"
        stat_surf = self.font_small.render(stat_str, True, SUCCESS_GREEN if (time.time() - self.status_time < 3.0) else TEXT_WHITE)
        self.screen.blit(stat_surf, (stat_rect.x + 10, stat_rect.y + 8))

        # 3. Control Panel on Right
        panel_x = 800
        panel_y = 20
        panel_w = 460
        panel_h = 800

        p_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, PANEL_BG, p_rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_BORDER, p_rect, width=1, border_radius=6)

        cur_y = panel_y + 12

        # Title Header
        t_surf = self.font_title.render("MAPGEN2 TERRAIN CONTROLS", True, TEXT_WHITE)
        self.screen.blit(t_surf, (panel_x + 16, cur_y))
        cur_y += 28

        def draw_section_header(title: str):
            nonlocal cur_y
            h_rect = pygame.Rect(panel_x + 14, cur_y, panel_w - 28, 20)
            pygame.draw.rect(self.screen, HEADER_BG, h_rect, border_radius=3)
            lbl = self.font_ui.render(title, True, TEXT_ACCENT)
            self.screen.blit(lbl, (h_rect.x + 8, h_rect.y + 2))
            cur_y += 24

        # --- VIEW MODES ---
        draw_section_header("VIEW MODE")
        b_w = (panel_w - 28 - 10) // 3
        b_h = 24
        for i, btn in enumerate(self.view_buttons):
            bx = panel_x + 14 + (i % 3) * (b_w + 5)
            by = cur_y + (i // 3) * (b_h + 4)
            btn.rect = pygame.Rect(bx, by, b_w, b_h)
            btn.is_active = (btn.key == self.view_mode)
            btn.draw(self.screen, self.font_small, mouse_pos)
        cur_y += (b_h + 4) * 2 + 6

        # --- ISLAND SHAPE & FEATURES ---
        draw_section_header("ISLAND SHAPE & FEATURES")
        s_w = (panel_w - 28 - 15) // 4
        for i, btn in enumerate(self.shape_buttons):
            bx = panel_x + 14 + i * (s_w + 5)
            btn.rect = pygame.Rect(bx, cur_y, s_w, b_h)
            btn.is_active = (btn.key == self.island_shape)
            btn.draw(self.screen, self.font_small, mouse_pos)
        cur_y += b_h + 5

        # Feature toggles
        for i, btn in enumerate(self.feature_buttons):
            bx = panel_x + 14 + i * (s_w + 5)
            btn.rect = pygame.Rect(bx, cur_y, s_w, b_h - 2)
            btn.draw(self.screen, self.font_tiny, mouse_pos, bg_color=(38, 48, 62))
        cur_y += b_h + 8

        # --- SEED & BASE MESH ---
        draw_section_header(f"WORLD SEED: {self.seed}")
        btn_rand = self.action_buttons["random"]
        btn_rand.rect = pygame.Rect(panel_x + 14, cur_y, panel_w - 28, 24)
        btn_rand.draw(self.screen, self.font_ui, mouse_pos, bg_color=(45, 65, 90))
        cur_y += 30

        for k in ("points", "rivers"):
            self.sliders[k].draw(self.screen, panel_x + 14, cur_y, panel_w - 28, self.font_ui, self.font_small, mouse_pos)
            cur_y += 34

        # --- ELEVATION & HYPSOMETRIC SHARPNESS ---
        draw_section_header("ELEVATION & MOUNTAIN SHARPNESS")
        for k in ("height_scale", "sharpness", "alpha"):
            self.sliders[k].draw(self.screen, panel_x + 14, cur_y, panel_w - 28, self.font_ui, self.font_small, mouse_pos)
            cur_y += 34

        # --- MICROPOLY SUBDIVISION KNOBS ---
        draw_section_header("MICROPOLY SUBDIVISION")
        for k in ("polys", "roughness", "jitter", "smooth"):
            self.sliders[k].draw(self.screen, panel_x + 14, cur_y, panel_w - 28, self.font_ui, self.font_small, mouse_pos)
            cur_y += 34

        # --- ACTION BUTTONS ---
        cur_y += 4
        act_w = (panel_w - 28 - 10) // 3
        act_h = 30
        for i, key in enumerate(("save_png", "export_usdz", "reset")):
            btn = self.action_buttons[key]
            bx = panel_x + 14 + i * (act_w + 5)
            btn.rect = pygame.Rect(bx, cur_y, act_w, act_h)
            btn.draw(self.screen, self.font_ui, mouse_pos, bg_color=(35, 80, 130) if key != "reset" else (70, 45, 55))

        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
                    break
            self.draw_ui()
            clock.tick(60)

        pygame.quit()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Interactive Mapgen2 GUI Terrain Explorer")
    parser.add_argument("--seed", "-s", type=int, default=777, help="Random seed")
    parser.add_argument("--points", "-n", type=int, default=1000, help="Voronoi points")
    parser.add_argument("--polys", "-p", type=int, default=16000, help="Target micropolygons")
    args = parser.parse_args()

    gui = MapgenGUI(seed=args.seed, num_points=args.points, target_polys=args.polys)
    gui.run()


if __name__ == "__main__":
    main()

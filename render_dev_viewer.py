"""
render_dev_viewer.py — Standalone Graphics Development Viewer & Sandbox for REGNUM.

Runs the RenderEngine purely for graphics iteration without loading or ticking
any economic simulation models. Features GPU-accelerated and CPU fallback pipelines,
along with an interactive, scrollable technical controls panel with live sliders.

Usage:
    python render_dev_viewer.py [--seed 4242] [--rows 7] [--cols 9] [--gpu | --cpu]
"""

import sys
import os
import argparse
import random
import time
import pygame

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from hexmap import rectangular_hex_layout, hex_bbox, axial_to_pixel
from worldview_camera import HEX_SIZE, WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from render_engine import RenderEngine, Camera
from render_engine.layers import MAP_LAYERS, LAYER_KEYS
from render_engine.gpu import (
    is_gpu_available,
    load_gpu_settings,
    save_gpu_settings,
    revert_gpu_settings_backup,
    has_backup,
)
import heightmap


class MockTile:
    """Lightweight tile object for pure graphics rendering."""
    def __init__(self, name, row, col, q=0, r=0):
        self.name = name
        self.row = row
        self.col = col
        self.q = q
        self.r = r
        self.elevation = 0.1
        self.elevation_meters = 100.0
        self.biome = 'plains'
        self.is_ocean = False
        self.owner_nation = None
        self.display_name = name


def create_mock_island_tiles(seed=4242, rows=7, cols=9):
    """Generate a lightweight mock island tileset for pure graphics testing."""
    layout = rectangular_hex_layout(rows, cols)
    tiles = []
    for r in range(rows):
        for c in range(cols):
            name = f"r{r}c{c}"
            q, r_ax = layout.get(name, (0, 0))
            tiles.append(MockTile(name, r, c, q=q, r=r_ax))

    # Apply realistic procedural heightmap biomes and elevations
    heightmap.apply_heightmap_to_world(tiles, seed=seed, grid_rows=rows, grid_cols=cols)
    return tiles


class Slider:
    """Interactive GUI slider with label, readout, track, draggable thumb, and reset button."""

    def __init__(self, key: str, label: str, min_val: float, max_val: float,
                 default_val: float, step: float = 0.05, fmt: str = "{:.2f}", category: str = ""):
        self.key = key
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.default_val = default_val
        self.step = step
        self.fmt = fmt
        self.category = category

        self.track_rect = pygame.Rect(0, 0, 0, 0)
        self.thumb_rect = pygame.Rect(0, 0, 0, 0)
        self.reset_rect = pygame.Rect(0, 0, 0, 0)
        self.is_active = False

    def get_ratio(self, val: float) -> float:
        return max(0.0, min(1.0, (val - self.min_val) / (self.max_val - self.min_val)))

    def val_from_pos(self, mx: int) -> float:
        if self.track_rect.width <= 0:
            return self.default_val
        ratio = max(0.0, min(1.0, (mx - self.track_rect.x) / float(self.track_rect.width)))
        raw = self.min_val + ratio * (self.max_val - self.min_val)
        steps = round((raw - self.min_val) / self.step)
        return max(self.min_val, min(self.max_val, round(self.min_val + steps * self.step, 4)))

    def draw(self, surface: pygame.Surface, x: int, y: int, width: int, current_val: float,
             font: pygame.font.Font, font_small: pygame.font.Font, mouse_pos: tuple[int, int]):
        mx, my = mouse_pos

        # Row 1: Label (left), Value readout (center-right), Reset button (right)
        lbl_surf = font_small.render(self.label, True, (215, 225, 235))
        surface.blit(lbl_surf, (x, y))

        val_str = self.fmt.format(current_val)
        val_surf = font_small.render(val_str, True, (130, 215, 255))
        val_w = val_surf.get_width()
        surface.blit(val_surf, (x + width - 36 - val_w, y))

        # Reset button [↺]
        self.reset_rect = pygame.Rect(x + width - 24, y - 2, 20, 18)
        is_reset_hover = self.reset_rect.collidepoint(mx, my)
        reset_bg = (55, 65, 80) if is_reset_hover else (38, 44, 56)
        pygame.draw.rect(surface, reset_bg, self.reset_rect, border_radius=3)
        pygame.draw.rect(surface, (75, 85, 105), self.reset_rect, 1, border_radius=3)
        rst_txt = font_small.render("⟲", True, (255, 215, 100) if is_reset_hover else (160, 175, 195))
        surface.blit(rst_txt, (self.reset_rect.x + 4, self.reset_rect.y + 1))

        # Row 2: Track bar + filled progress + circular thumb
        track_y = y + 18
        track_h = 6
        self.track_rect = pygame.Rect(x, track_y, width, track_h)
        pygame.draw.rect(surface, (24, 28, 36), self.track_rect, border_radius=3)
        pygame.draw.rect(surface, (50, 58, 72), self.track_rect, 1, border_radius=3)

        ratio = self.get_ratio(current_val)
        fill_w = max(0, int(ratio * width))
        if fill_w > 0:
            fill_rect = pygame.Rect(x, track_y, fill_w, track_h)
            pygame.draw.rect(surface, (60, 140, 220), fill_rect, border_radius=3)

        thumb_x = x + fill_w
        thumb_y = track_y + track_h // 2
        thumb_r = 7
        self.thumb_rect = pygame.Rect(thumb_x - thumb_r, thumb_y - thumb_r, thumb_r * 2, thumb_r * 2)

        is_thumb_hover = self.thumb_rect.collidepoint(mx, my) or self.is_active
        thumb_color = (255, 255, 255) if is_thumb_hover else (180, 210, 240)
        pygame.draw.circle(surface, thumb_color, (thumb_x, thumb_y), thumb_r)
        pygame.draw.circle(surface, (30, 40, 55), (thumb_x, thumb_y), thumb_r, 1)


def main():
    parser = argparse.ArgumentParser(description="REGNUM Graphics Development Viewer")
    parser.add_argument('--seed', type=int, default=4242, help="Terrain procedural seed")
    parser.add_argument('--rows', type=int, default=7, help="Hex grid rows")
    parser.add_argument('--cols', type=int, default=9, help="Hex grid cols")
    parser.add_argument('--cpu', action='store_true', help="Force CPU NumPy terrain generation pipeline")
    parser.add_argument('--gpu', action='store_true', help="Force GPU ModernGL terrain generation pipeline")
    args = parser.parse_args()

    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"REGNUM Graphics Dev Viewer — Seed {args.seed}")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont('Arial', 14, bold=True)
    font_small = pygame.font.SysFont('Arial', 11)

    engine = RenderEngine(width=WIDTH, height=HEIGHT, map_right=MAP_RIGHT,
                          top_bar_h=TOP_BAR_H, ticker_h=TICKER_H)
    engine.set_fonts(font, font_small)

    if args.cpu:
        engine.terrain_renderer.force_cpu = True
    elif args.gpu:
        engine.terrain_renderer.force_cpu = False

    seed = args.seed
    rows, cols = args.rows, args.cols
    layout = rectangular_hex_layout(rows, cols)
    bbox = hex_bbox(layout, HEX_SIZE)
    engine.set_bbox(bbox)

    tiles = create_mock_island_tiles(seed=seed, rows=rows, cols=cols)

    show_grid = True
    show_borders = True
    show_labels = True
    selected_name = None
    hover_name = None

    # Load persistent shared GPU shader settings
    saved_settings = load_gpu_settings()
    uniforms = dict(saved_settings)

    # Register Technical Sliders using saved defaults
    def dval(key: str, fallback: float) -> float:
        return float(saved_settings.get(key, fallback))

    sliders = [
        # 1. Lighting & Atmosphere
        Slider('sun_intensity', 'Sun Intensity', 0.1, 3.0, dval('sun_intensity', 1.15), 0.05, "{:.2f}", "LIGHTING & ATMOSPHERE"),
        Slider('sun_azimuth', 'Sun Azimuth', -180.0, 180.0, dval('sun_azimuth', -135.0), 5.0, "{:.0f}°", "LIGHTING & ATMOSPHERE"),
        Slider('sun_elevation', 'Sun Elevation', 10.0, 85.0, dval('sun_elevation', 42.0), 1.0, "{:.0f}°", "LIGHTING & ATMOSPHERE"),
        Slider('ambient_intensity', 'Ambient Light', 0.1, 1.5, dval('ambient_intensity', 0.45), 0.05, "{:.2f}", "LIGHTING & ATMOSPHERE"),

        # 2. Mountains & Relief
        Slider('mountain_roughness', 'Mountain Crags', 0.1, 3.0, dval('mountain_roughness', 1.0), 0.05, "{:.2f}", "MOUNTAINS & RELIEF"),

        # 3. Water & Bathymetry
        Slider('shelf_width_mult', 'Shelf Reach', 0.2, 3.0, dval('shelf_width_mult', 1.0), 0.05, "{:.2f}", "WATER & BATHYMETRY"),
        Slider('ocean_depth_mult', 'Ocean Depth', 0.2, 3.0, dval('ocean_depth_mult', 1.0), 0.05, "{:.2f}", "WATER & BATHYMETRY"),
        Slider('river_width_mult', 'River Width', 0.2, 3.0, dval('river_width_mult', 1.0), 0.05, "{:.2f}", "WATER & BATHYMETRY"),
        Slider('river_depth_mult', 'River Carve Depth', 0.0, 3.0, dval('river_depth_mult', 1.0), 0.05, "{:.2f}", "WATER & BATHYMETRY"),
        Slider('lake_depth_mult', 'Lake Basin Depth', 0.2, 3.0, dval('lake_depth_mult', 1.0), 0.05, "{:.2f}", "WATER & BATHYMETRY"),

        # 4. Forest Canopy
        Slider('forest_density', 'Canopy Density', 0.0, 2.5, dval('forest_density', 1.0), 0.05, "{:.2f}", "FOREST CANOPY"),
        Slider('canopy_roughness', 'Canopy Roughness', 0.1, 2.5, dval('canopy_roughness', 1.0), 0.05, "{:.2f}", "FOREST CANOPY"),
        Slider('tree_scale', 'Crown Tree Scale', 0.4, 2.5, dval('tree_scale', 1.0), 0.05, "{:.2f}", "FOREST CANOPY"),

        # 5. Plains & Ground Cover
        Slider('plains_grain', 'Plains Micro-Grain', 0.0, 2.5, dval('plains_grain', 1.0), 0.05, "{:.2f}", "PLAINS & GROUND COVER"),
        Slider('soil_patchiness', 'Soil Patchiness', 0.0, 2.5, dval('soil_patchiness', 1.0), 0.05, "{:.2f}", "PLAINS & GROUND COVER"),
        Slider('grass_warmth', 'Grass Warmth', 0.5, 1.8, dval('grass_warmth', 1.0), 0.05, "{:.2f}", "PLAINS & GROUND COVER"),
    ]

    status_feedback = None  # (message_str, color_tuple, expire_timestamp)
    save_defaults_rect = pygame.Rect(0, 0, 0, 0)
    revert_backup_rect = pygame.Rect(0, 0, 0, 0)
    rand_seed_rect = pygame.Rect(0, 0, 0, 0)

    active_slider: Slider | None = None
    active_layer = 'physical'
    dragging = False
    drag_start = (0, 0)
    drag_cam_start = (0, 0)

    # Scrollable sidebar state
    scroll_y = 0
    max_scroll = 0
    scrollbar_dragging = False
    scrollbar_drag_start_y = 0
    scrollbar_start_scroll = 0

    running = True
    needs_redraw = True

    print("==================================================")
    print(" REGNUM Standalone Graphics Development Sandbox   ")
    print("==================================================")
    print(" Controls:")
    print("   [WASD / Arrow Keys] : Pan camera")
    print("   [+ / - / Scroll]    : Zoom camera / Scroll HUD")
    print("   [R / Home]          : Reset camera to fit map")
    print("   [N / P]             : Next / Previous seed")
    print("   [Space / X]         : Randomize terrain seed")
    print("   [U]                 : Toggle GPU vs CPU pipeline (instant flip)")
    print("   [Ctrl+S]            : Save current GPU settings as default (creates backup)")
    print("   [C]                 : Invalidate surface cache & re-render")
    print("   [G]                 : Toggle hex grid lines")
    print("   [B]                 : Toggle national borders")
    print("   [L]                 : Toggle tile labels")
    print("   [M] / [Ctrl+W]      : Toggle Mobile Web Server + QR code")
    print("   [1-9]               : Switch active visual layer")
    print("   [ESC]               : Quit")
    print("==================================================")

    hud_panel_x = MAP_RIGHT + 8
    hud_panel_w = WIDTH - MAP_RIGHT - 16
    hud_panel_h = HEIGHT - 16

    reset_all_rect = pygame.Rect(0, 0, 0, 0)
    pipeline_btn_rect = pygame.Rect(0, 0, 0, 0)
    web_btn_rect = pygame.Rect(0, 0, 0, 0)
    web_server = None
    show_qr_modal = False
    qr_surf = None
    modal_card_rect = pygame.Rect(0, 0, 0, 0)
    modal_close_rect = pygame.Rect(0, 0, 0, 0)
    scrollbar_rect = pygame.Rect(0, 0, 0, 0)
    scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)

    while running:
        clock.tick(60)
        mouse_pos = pygame.mouse.get_pos()
        is_over_hud = mouse_pos[0] >= MAP_RIGHT

        # Hover detection for hex tiles
        prev_hover = hover_name
        if not is_over_hud:
            q_r = engine.camera.screen_to_hex(mouse_pos[0], mouse_pos[1], HEX_SIZE)
            if q_r:
                rev = { (t.q, t.r): t.name for t in tiles }
                hover_name = rev.get(q_r)
            else:
                hover_name = None
        else:
            hover_name = None

        if hover_name != prev_hover:
            needs_redraw = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_n:
                    seed += 1
                    engine.invalidate_cache()
                    tiles = create_mock_island_tiles(seed=seed, rows=rows, cols=cols)
                    pygame.display.set_caption(f"REGNUM Graphics Dev Viewer — Seed {seed}")
                    needs_redraw = True
                elif event.key == pygame.K_p:
                    seed = max(1, seed - 1)
                    engine.invalidate_cache()
                    tiles = create_mock_island_tiles(seed=seed, rows=rows, cols=cols)
                    pygame.display.set_caption(f"REGNUM Graphics Dev Viewer — Seed {seed}")
                    needs_redraw = True
                elif event.key in (pygame.K_SPACE, pygame.K_x):
                    seed = random.randint(1, 99999)
                    engine.invalidate_cache()
                    tiles = create_mock_island_tiles(seed=seed, rows=rows, cols=cols)
                    pygame.display.set_caption(f"REGNUM Graphics Dev Viewer — Seed {seed}")
                    status_feedback = (f"Randomized seed to {seed}", (130, 215, 255), time.time() + 3.0)
                    needs_redraw = True
                    print(f"[Graphics Dev] Randomized terrain seed to: {seed}")
                elif event.key == pygame.K_u:
                    engine.terrain_renderer.switch_pipeline()
                    needs_redraw = True
                    mode_str = "CPU" if engine.terrain_renderer.force_cpu else "GPU"
                    status_feedback = (f"Switched pipeline to: {mode_str}", (120, 245, 150) if not engine.terrain_renderer.force_cpu else (245, 180, 80), time.time() + 3.0)
                    print(f"[Graphics Dev] Switched terrain pipeline to: {mode_str}")
                elif event.key == pygame.K_s and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                    ok, msg = save_gpu_settings(uniforms)
                    if ok:
                        for s in sliders:
                            s.default_val = uniforms[s.key]
                        status_feedback = ("Defaults saved (backup created)!", (120, 245, 150), time.time() + 4.0)
                elif event.key == pygame.K_ESCAPE:
                    if show_qr_modal:
                        show_qr_modal = False
                        needs_redraw = True
                    else:
                        running = False
                elif event.key in (pygame.K_m, pygame.K_q) or (event.key == pygame.K_w and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META))):
                    if web_server is None:
                        try:
                            from sim_server import SimServer, run_web_server
                            from sim_server.qr_code import generate_pygame_qr
                            sim = SimServer(seed=seed)
                            web_server = run_web_server(sim_server=sim, port=8080, wait_forever=False)
                            web_server.terrain_renderer = engine.terrain_renderer
                            qr_surf = generate_pygame_qr(web_server.base_url, module_px=6)
                            show_qr_modal = True
                            status_feedback = (f"Web Server online: {web_server.base_url}", (120, 245, 150), time.time() + 6.0)
                        except Exception as e:
                            status_feedback = (f"Web Server error: {e}", (245, 120, 120), time.time() + 4.0)
                    else:
                        if event.key == pygame.K_q or not show_qr_modal:
                            show_qr_modal = not show_qr_modal
                        else:
                            web_server.stop()
                            web_server = None
                            show_qr_modal = False
                            status_feedback = ("Web Server stopped", (245, 180, 80), time.time() + 3.0)
                    needs_redraw = True
                elif event.key in (pygame.K_r, pygame.K_HOME):
                    engine.camera.reset()
                    needs_redraw = True
                elif event.key == pygame.K_c:
                    engine.invalidate_cache()
                    needs_redraw = True
                    status_feedback = (f"Invalidated terrain surface cache for seed {seed}", (255, 220, 120), time.time() + 3.0)
                    print(f"[Graphics Dev] Invalidated heightmap surface cache for seed {seed}")
                elif event.key == pygame.K_g:
                    show_grid = not show_grid
                    needs_redraw = True
                elif event.key == pygame.K_b:
                    show_borders = not show_borders
                    needs_redraw = True
                elif event.key == pygame.K_l:
                    show_labels = not show_labels
                    needs_redraw = True
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    engine.camera.ox += 40
                    engine.camera.clamp()
                    needs_redraw = True
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    engine.camera.ox -= 40
                    engine.camera.clamp()
                    needs_redraw = True
                elif event.key in (pygame.K_UP, pygame.K_w):
                    engine.camera.oy += 40
                    engine.camera.clamp()
                    needs_redraw = True
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    engine.camera.oy -= 40
                    engine.camera.clamp()
                    needs_redraw = True
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    engine.camera.zoom_at(1.15, MAP_RIGHT // 2, HEIGHT // 2)
                    needs_redraw = True
                elif event.key == pygame.K_MINUS:
                    engine.camera.zoom_at(1.0 / 1.15, MAP_RIGHT // 2, HEIGHT // 2)
                    needs_redraw = True
                elif event.unicode in LAYER_KEYS:
                    active_layer = LAYER_KEYS[event.unicode]
                    needs_redraw = True

            elif event.type == pygame.MOUSEWHEEL:
                if is_over_hud:
                    # Scroll technical controls panel
                    scroll_y = max(0, min(max_scroll, scroll_y - event.y * 32))
                    needs_redraw = True
                else:
                    # Zoom map viewport
                    factor = 1.12 if event.y > 0 else (1.0 / 1.12)
                    engine.camera.zoom_at(factor, mouse_pos[0], mouse_pos[1])
                    needs_redraw = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if show_qr_modal:
                        if modal_close_rect.collidepoint(event.pos) or not modal_card_rect.collidepoint(event.pos):
                            show_qr_modal = False
                            needs_redraw = True
                        continue

                    if is_over_hud:
                        # 1. Pipeline toggle button
                        if pipeline_btn_rect.collidepoint(event.pos):
                            engine.terrain_renderer.switch_pipeline()
                            needs_redraw = True
                            mode_str = "CPU" if engine.terrain_renderer.force_cpu else "GPU"
                            status_feedback = (f"Switched pipeline to: {mode_str}", (120, 245, 150) if not engine.terrain_renderer.force_cpu else (245, 180, 80), time.time() + 3.0)

                        # 2. Save Defaults button
                        elif save_defaults_rect.collidepoint(event.pos):
                            ok, msg = save_gpu_settings(uniforms)
                            if ok:
                                for s in sliders:
                                    s.default_val = uniforms[s.key]
                                status_feedback = ("Defaults saved (backup created)!", (120, 245, 150), time.time() + 4.0)
                            else:
                                status_feedback = (msg, (245, 120, 120), time.time() + 4.0)
                            needs_redraw = True

                        # 3. Revert Backup button
                        elif revert_backup_rect.collidepoint(event.pos):
                            ok, msg, restored = revert_gpu_settings_backup()
                            if ok and restored:
                                uniforms.update(restored)
                                for s in sliders:
                                    s.default_val = uniforms[s.key]
                                status_feedback = ("Restored settings from backup!", (255, 215, 100), time.time() + 4.0)
                                engine.terrain_renderer.invalidate(all_pipelines=False)
                            else:
                                status_feedback = (msg, (245, 120, 120), time.time() + 4.0)
                            needs_redraw = True

                        # 4. Web Server button
                        elif web_btn_rect.collidepoint(event.pos):
                            if web_server is None:
                                try:
                                    from sim_server import SimServer, run_web_server
                                    from sim_server.qr_code import generate_pygame_qr
                                    sim = SimServer(seed=seed)
                                    web_server = run_web_server(sim_server=sim, port=8080, wait_forever=False)
                                    web_server.terrain_renderer = engine.terrain_renderer
                                    qr_surf = generate_pygame_qr(web_server.base_url, module_px=6)
                                    show_qr_modal = True
                                    status_feedback = (f"Web Server online: {web_server.base_url}", (120, 245, 150), time.time() + 6.0)
                                except Exception as e:
                                    status_feedback = (f"Web Server error: {e}", (245, 120, 120), time.time() + 4.0)
                            else:
                                show_qr_modal = not show_qr_modal
                            needs_redraw = True

                        # 5. Randomize Seed button
                        elif rand_seed_rect.collidepoint(event.pos):
                            seed = random.randint(1, 99999)
                            engine.invalidate_cache()
                            tiles = create_mock_island_tiles(seed=seed, rows=rows, cols=cols)
                            pygame.display.set_caption(f"REGNUM Graphics Dev Viewer — Seed {seed}")
                            status_feedback = (f"Randomized seed to {seed}", (130, 215, 255), time.time() + 3.0)
                            needs_redraw = True
                            print(f"[Graphics Dev] Randomized terrain seed to: {seed}")

                        # 5. Reset All button
                        elif reset_all_rect.collidepoint(event.pos):
                            for s in sliders:
                                uniforms[s.key] = s.default_val
                            status_feedback = ("Reset all sliders to defaults", (255, 220, 120), time.time() + 3.0)
                            needs_redraw = True

                        # 6. Scrollbar click/drag
                        elif scrollbar_thumb_rect.collidepoint(event.pos):
                            scrollbar_dragging = True
                            scrollbar_drag_start_y = event.pos[1]
                            scrollbar_start_scroll = scroll_y
                        elif scrollbar_rect.collidepoint(event.pos):
                            ratio = (event.pos[1] - scrollbar_rect.y) / float(scrollbar_rect.height)
                            scroll_y = max(0, min(max_scroll, int(ratio * max_scroll)))
                            needs_redraw = True

                        # 7. Sliders hit test
                        else:
                            for s in sliders:
                                if s.reset_rect.collidepoint(event.pos):
                                    uniforms[s.key] = s.default_val
                                    needs_redraw = True
                                    break
                                elif s.track_rect.collidepoint(event.pos) or s.thumb_rect.collidepoint(event.pos):
                                    active_slider = s
                                    s.is_active = True
                                    uniforms[s.key] = s.val_from_pos(event.pos[0])
                                    needs_redraw = True
                                    break
                    else:
                        if hover_name:
                            selected_name = hover_name if selected_name != hover_name else None
                            needs_redraw = True

                elif event.button in (2, 3):  # Middle or Right drag viewport
                    if not is_over_hud:
                        dragging = True
                        drag_start = event.pos
                        drag_cam_start = (engine.camera.ox, engine.camera.oy)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if active_slider:
                        active_slider.is_active = False
                        active_slider = None
                    scrollbar_dragging = False
                elif event.button in (2, 3):
                    dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if active_slider:
                    new_val = active_slider.val_from_pos(event.pos[0])
                    if uniforms[active_slider.key] != new_val:
                        uniforms[active_slider.key] = new_val
                        needs_redraw = True
                elif scrollbar_dragging and max_scroll > 0:
                    delta_y = event.pos[1] - scrollbar_drag_start_y
                    scroll_track_h = max(1, scrollbar_rect.height - scrollbar_thumb_rect.height)
                    scroll_delta = int((delta_y / float(scroll_track_h)) * max_scroll)
                    scroll_y = max(0, min(max_scroll, scrollbar_start_scroll + scroll_delta))
                    needs_redraw = True
                elif dragging:
                    dx = event.pos[0] - drag_start[0]
                    dy = event.pos[1] - drag_start[1]
                    engine.camera.ox = drag_cam_start[0] + dx
                    engine.camera.oy = drag_cam_start[1] + dy
                    engine.camera.clamp()
                    needs_redraw = True

        if needs_redraw:
            screen.fill((20, 22, 28))

            # 1. Render Map Viewport
            engine.render_map_view(
                screen, seed, bbox, tiles, layout,
                selected_name=selected_name, hover_name=hover_name,
                show_grid=show_grid, show_borders=show_borders, show_labels=show_labels,
                uniforms=uniforms
            )

            # 2. Draw Graphics Developer HUD (Right sidebar frame)
            hud_rect = pygame.Rect(hud_panel_x, 8, hud_panel_w, hud_panel_h)
            pygame.draw.rect(screen, (26, 30, 40), hud_rect, border_radius=8)
            pygame.draw.rect(screen, (48, 54, 70), hud_rect, 1, border_radius=8)

            y_top = 18

            # Header Title & Action Buttons
            title_txt = font.render("GRAPHICS DEV HUD", True, (255, 215, 95))
            screen.blit(title_txt, (hud_panel_x + 14, y_top))

            # [💾 Save Defs] button
            save_defaults_rect = pygame.Rect(hud_panel_x + hud_panel_w - 180, y_top - 2, 92, 20)
            is_save_hover = save_defaults_rect.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (45, 75, 55) if is_save_hover else (30, 48, 36), save_defaults_rect, border_radius=3)
            pygame.draw.rect(screen, (70, 150, 95), save_defaults_rect, 1, border_radius=3)
            save_txt = font_small.render("💾 Save Defs", True, (160, 255, 180) if is_save_hover else (120, 225, 150))
            screen.blit(save_txt, (save_defaults_rect.x + 6, save_defaults_rect.y + 2))

            # [⟲ Backup] button (restores previous settings if backup exists)
            backup_available = has_backup()
            revert_backup_rect = pygame.Rect(hud_panel_x + hud_panel_w - 82, y_top - 2, 68, 20)
            is_rev_hover = revert_backup_rect.collidepoint(mouse_pos) and backup_available
            rev_bg = ((60, 52, 36) if is_rev_hover else (40, 36, 28)) if backup_available else (28, 30, 36)
            pygame.draw.rect(screen, rev_bg, revert_backup_rect, border_radius=3)
            pygame.draw.rect(screen, (150, 130, 60) if backup_available else (48, 52, 62), revert_backup_rect, 1, border_radius=3)
            rev_txt = font_small.render("⟲ Backup", True, (255, 220, 120) if is_rev_hover else ((180, 160, 95) if backup_available else (85, 90, 105)))
            screen.blit(rev_txt, (revert_backup_rect.x + 7, revert_backup_rect.y + 2))
            y_top += 26

            # Pipeline Toggle Badge & Mobile Web Server Button
            pipeline_name = "GPU (Metal 4.1)" if engine.terrain_renderer.used_gpu else "CPU (NumPy)"
            pipe_color = (120, 245, 150) if engine.terrain_renderer.used_gpu else (245, 180, 80)
            pipe_w = hud_panel_w - 28 - 98
            pipeline_btn_rect = pygame.Rect(hud_panel_x + 14, y_top, pipe_w, 22)
            pygame.draw.rect(screen, (36, 42, 54), pipeline_btn_rect, border_radius=4)
            pygame.draw.rect(screen, (60, 70, 90), pipeline_btn_rect, 1, border_radius=4)

            p_surf = font_small.render(f"Pipeline: {pipeline_name} [U]", True, pipe_color)
            screen.blit(p_surf, (pipeline_btn_rect.x + 8, pipeline_btn_rect.y + 4))

            # [📱 Web] button
            web_btn_rect = pygame.Rect(hud_panel_x + 14 + pipe_w + 6, y_top, 92, 22)
            is_web_on = web_server is not None
            is_web_hover = web_btn_rect.collidepoint(mouse_pos)
            web_bg = (35, 75, 55) if is_web_on else ((48, 56, 70) if is_web_hover else (34, 40, 52))
            web_border = (80, 200, 120) if is_web_on else ((70, 90, 120) if is_web_hover else (55, 65, 85))
            pygame.draw.rect(screen, web_bg, web_btn_rect, border_radius=4)
            pygame.draw.rect(screen, web_border, web_btn_rect, 1, border_radius=4)
            web_text = "📱 Web: ON" if is_web_on else "📱 Web [M]"
            web_txt_color = (130, 255, 170) if is_web_on else (185, 200, 225)
            web_surf = font_small.render(web_text, True, web_txt_color)
            screen.blit(web_surf, (web_btn_rect.x + 7, web_btn_rect.y + 4))
            y_top += 28

            # Quick Metrics Bar with [🎲 Rand] button
            seed_lbl = font_small.render(f"Seed: {seed}", True, (215, 225, 240))
            screen.blit(seed_lbl, (hud_panel_x + 14, y_top))
            seed_w = seed_lbl.get_width()

            # [🎲 Rand] button
            rand_seed_rect = pygame.Rect(hud_panel_x + 14 + seed_w + 8, y_top - 2, 56, 18)
            is_rand_hover = rand_seed_rect.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (48, 62, 82) if is_rand_hover else (34, 42, 56), rand_seed_rect, border_radius=3)
            pygame.draw.rect(screen, (75, 105, 145), rand_seed_rect, 1, border_radius=3)
            rand_txt = font_small.render("🎲 Rand", True, (180, 220, 255) if is_rand_hover else (140, 180, 220))
            screen.blit(rand_txt, (rand_seed_rect.x + 5, rand_seed_rect.y + 1))

            metrics_str = f"Map: {engine.terrain_renderer.last_gen_time_ms:.1f}ms  FPS: {engine.fps:.1f}"
            m_surf = font_small.render(metrics_str, True, (160, 180, 200))
            screen.blit(m_surf, (rand_seed_rect.x + rand_seed_rect.w + 10, y_top))
            y_top += 20

            # Status / Feedback toast (if active)
            if status_feedback and status_feedback[2] > time.time():
                fb_msg, fb_col, _ = status_feedback
                fb_surf = font_small.render(fb_msg, True, fb_col)
                screen.blit(fb_surf, (hud_panel_x + 14, y_top))
                y_top += 18

            # Overlays row & Reset All button
            reset_all_rect = pygame.Rect(hud_panel_x + hud_panel_w - 90, y_top, 76, 20)
            rst_all_hover = reset_all_rect.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (55, 65, 80) if rst_all_hover else (38, 44, 56), reset_all_rect, border_radius=3)
            pygame.draw.rect(screen, (85, 95, 115), reset_all_rect, 1, border_radius=3)
            rst_all_txt = font_small.render("⟲ Reset All", True, (255, 220, 120) if rst_all_hover else (180, 195, 215))
            screen.blit(rst_all_txt, (reset_all_rect.x + 6, reset_all_rect.y + 2))

            ovl_str = f"Grid:{'ON' if show_grid else 'OFF'}  Borders:{'ON' if show_borders else 'OFF'}  Labels:{'ON' if show_labels else 'OFF'}"
            ovl_surf = font_small.render(ovl_str, True, (135, 150, 170))
            screen.blit(ovl_surf, (hud_panel_x + 14, y_top + 2))
            y_top += 26

            # Horizontal Separator
            pygame.draw.line(screen, (45, 52, 68), (hud_panel_x + 8, y_top), (hud_panel_x + hud_panel_w - 8, y_top), 1)
            y_top += 8

            # 3. Scrollable Technical Controls List
            scroll_area_y = y_top
            scroll_area_h = hud_panel_h - (scroll_area_y - 8) - 10
            slider_w = hud_panel_w - 38

            # Pre-calculate content height for scroll bounds
            content_h = 0
            cur_cat = None
            for s in sliders:
                if s.category != cur_cat:
                    cur_cat = s.category
                    content_h += 30
                content_h += 38
            content_h += 20

            max_scroll = max(0, content_h - scroll_area_h)
            scroll_y = max(0, min(max_scroll, scroll_y))

            # Set clipping rect for smooth scrolling
            old_clip = screen.get_clip()
            clip_rect = pygame.Rect(hud_panel_x + 6, scroll_area_y, hud_panel_w - 18, scroll_area_h)
            screen.set_clip(clip_rect)

            curr_y = scroll_area_y - scroll_y
            cur_cat = None

            for s in sliders:
                # Category Header
                if s.category != cur_cat:
                    cur_cat = s.category
                    cat_surf = font.render(cur_cat, True, (245, 205, 95))
                    screen.blit(cat_surf, (hud_panel_x + 14, curr_y + 4))
                    curr_y += 28

                # Draw Slider Widget
                s.draw(screen, hud_panel_x + 14, curr_y, slider_w, uniforms[s.key], font, font_small, mouse_pos)
                curr_y += 38

            screen.set_clip(old_clip)

            # 4. Draw Scrollbar Track & Thumb
            if max_scroll > 0:
                scrollbar_rect = pygame.Rect(hud_panel_x + hud_panel_w - 12, scroll_area_y, 6, scroll_area_h)
                pygame.draw.rect(screen, (32, 36, 48), scrollbar_rect, border_radius=3)

                thumb_h = max(24, int((scroll_area_h / float(content_h)) * scroll_area_h))
                thumb_y = scroll_area_y + int((scroll_y / float(max_scroll)) * (scroll_area_h - thumb_h))
                scrollbar_thumb_rect = pygame.Rect(scrollbar_rect.x, thumb_y, 6, thumb_h)

                thumb_hover = scrollbar_thumb_rect.collidepoint(mouse_pos) or scrollbar_dragging
                thumb_col = (110, 130, 160) if thumb_hover else (70, 80, 100)
                pygame.draw.rect(screen, thumb_col, scrollbar_thumb_rect, border_radius=3)
            else:
                scrollbar_rect = pygame.Rect(0, 0, 0, 0)
                scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)

            # 5. Draw QR Code Modal Dialog if active
            if show_qr_modal and qr_surf is not None and web_server is not None:
                dim_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                dim_surf.fill((0, 0, 0, 195))
                screen.blit(dim_surf, (0, 0))

                modal_w = max(340, qr_surf.get_width() + 60)
                modal_h = qr_surf.get_height() + 150
                modal_x = (MAP_RIGHT - modal_w) // 2
                modal_y = (HEIGHT - modal_h) // 2
                modal_card_rect = pygame.Rect(modal_x, modal_y, modal_w, modal_h)

                # Card Background & Border
                pygame.draw.rect(screen, (20, 24, 32), modal_card_rect, border_radius=12)
                pygame.draw.rect(screen, (80, 120, 170), modal_card_rect, 2, border_radius=12)

                # Title
                m_title = font.render("📱 REGNUM MOBILE CLIENT", True, (245, 210, 95))
                screen.blit(m_title, (modal_x + (modal_w - m_title.get_width()) // 2, modal_y + 16))

                # Close Button [✕]
                modal_close_rect = pygame.Rect(modal_x + modal_w - 32, modal_y + 12, 22, 22)
                is_close_hover = modal_close_rect.collidepoint(mouse_pos)
                pygame.draw.rect(screen, (55, 65, 80) if is_close_hover else (30, 36, 48), modal_close_rect, border_radius=4)
                close_x = font_small.render("✕", True, (240, 240, 240))
                screen.blit(close_x, (modal_close_rect.x + 6, modal_close_rect.y + 3))

                # QR Code Surface
                qr_x = modal_x + (modal_w - qr_surf.get_width()) // 2
                qr_y = modal_y + 44
                screen.blit(qr_surf, (qr_x, qr_y))

                # URL String
                url_surf = font.render(web_server.base_url, True, (100, 220, 255))
                screen.blit(url_surf, (modal_x + (modal_w - url_surf.get_width()) // 2, qr_y + qr_surf.get_height() + 10))

                # Subtitle Instructions
                sub_surf = font_small.render("Point iPhone Camera at code or press [Q] / click outside to close", True, (160, 175, 195))
                screen.blit(sub_surf, (modal_x + (modal_w - sub_surf.get_width()) // 2, qr_y + qr_surf.get_height() + 34))

            pygame.display.flip()
            needs_redraw = False

    if web_server is not None:
        web_server.stop()
    pygame.quit()


if __name__ == '__main__':
    main()

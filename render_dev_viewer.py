"""
render_dev_viewer.py — Standalone Graphics Development Viewer & Sandbox for REGNUM.

Runs the RenderEngine purely for graphics iteration without loading or ticking
any economic simulation models.

Usage:
    python render_dev_viewer.py [--seed 4242] [--rows 7] [--cols 9]
"""

import sys
import os
import argparse
import pygame

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from hexmap import rectangular_hex_layout, hex_bbox, axial_to_pixel
from worldview_camera import HEX_SIZE, WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H
from render_engine import RenderEngine, Camera
from render_engine.layers import MAP_LAYERS, LAYER_KEYS
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


def main():
    parser = argparse.ArgumentParser(description="REGNUM Graphics Development Viewer")
    parser.add_argument('--seed', type=int, default=4242, help="Terrain procedural seed")
    parser.add_argument('--rows', type=int, default=7, help="Hex grid rows")
    parser.add_argument('--cols', type=int, default=9, help="Hex grid cols")
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

    active_layer = 'physical'
    dragging = False
    drag_start = (0, 0)
    drag_cam_start = (0, 0)

    running = True
    needs_redraw = True

    print("==================================================")
    print(" REGNUM Standalone Graphics Development Sandbox   ")
    print("==================================================")
    print(" Controls:")
    print("   [WASD / Arrow Keys] : Pan camera")
    print("   [+ / - / Scroll]    : Zoom camera")
    print("   [R / Home]          : Reset camera to fit map")
    print("   [N / P]             : Next / Previous seed")
    print("   [C]                 : Invalidate surface cache & re-render")
    print("   [G]                 : Toggle hex grid lines")
    print("   [B]                 : Toggle national borders")
    print("   [L]                 : Toggle tile labels")
    print("   [1-9]               : Switch active visual layer")
    print("   [ESC]               : Quit")
    print("==================================================")

    while running:
        clock.tick(60)
        mouse_pos = pygame.mouse.get_pos()

        # Hover detection
        prev_hover = hover_name
        q_r = engine.camera.screen_to_hex(mouse_pos[0], mouse_pos[1], HEX_SIZE)
        if q_r:
            rev = { (t.q, t.r): t.name for t in tiles }
            hover_name = rev.get(q_r)
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
                elif event.key in (pygame.K_r, pygame.K_HOME):
                    engine.camera.reset()
                    needs_redraw = True
                elif event.key == pygame.K_c:
                    engine.invalidate_cache()
                    needs_redraw = True
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
                factor = 1.12 if event.y > 0 else (1.0 / 1.12)
                engine.camera.zoom_at(factor, mouse_pos[0], mouse_pos[1])
                needs_redraw = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (2, 3):  # Middle or Right drag
                    dragging = True
                    drag_start = event.pos
                    drag_cam_start = (engine.camera.ox, engine.camera.oy)
                elif event.button == 1:  # Left click selection
                    if hover_name:
                        selected_name = hover_name if selected_name != hover_name else None
                        needs_redraw = True

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (2, 3):
                    dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if dragging:
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
                show_grid=show_grid, show_borders=show_borders, show_labels=show_labels
            )

            # 2. Draw Graphics Developer HUD (Right sidebar & Top bar)
            hud_rect = pygame.Rect(MAP_RIGHT + 10, 10, WIDTH - MAP_RIGHT - 20, HEIGHT - 20)
            pygame.draw.rect(screen, (30, 34, 44), hud_rect, border_radius=8)
            pygame.draw.rect(screen, (50, 56, 72), hud_rect, 1, border_radius=8)

            y_offset = 24
            def draw_hud_line(text, color=(240, 245, 250), bold=False):
                nonlocal y_offset
                txt = font.render(text, True, color) if bold else font_small.render(text, True, color)
                screen.blit(txt, (MAP_RIGHT + 20, y_offset))
                y_offset += 20

            draw_hud_line("GRAPHICS DEV HUD", (255, 215, 95), bold=True)
            y_offset += 4
            draw_hud_line(f"Terrain Seed: {seed}", (140, 225, 255), bold=True)
            draw_hud_line(f"Render Time: {engine.last_frame_time_ms:.1f} ms")
            draw_hud_line(f"FPS: {engine.fps:.1f}")
            draw_hud_line(f"Camera Zoom: {engine.camera.zoom:.2f}x")
            draw_hud_line(f"Active Layer: {active_layer.upper()}")
            y_offset += 10

            draw_hud_line("OVERLAY TOGGLES:", (200, 210, 225), bold=True)
            draw_hud_line(f"  [G] Grid Lines: {'ON' if show_grid else 'OFF'}")
            draw_hud_line(f"  [B] Borders: {'ON' if show_borders else 'OFF'}")
            draw_hud_line(f"  [L] Labels: {'ON' if show_labels else 'OFF'}")
            y_offset += 10

            draw_hud_line("INSPECTION:", (200, 210, 225), bold=True)
            sel_tile = next((t for t in tiles if t.name == selected_name), None)
            hov_tile = next((t for t in tiles if t.name == hover_name), None)
            draw_hud_line(f"  Selected: {sel_tile.name if sel_tile else 'None'}")
            if sel_tile:
                draw_hud_line(f"    Biome: {sel_tile.biome}")
                draw_hud_line(f"    Elev: {int(sel_tile.elevation_meters)} m")
            draw_hud_line(f"  Hovered: {hov_tile.name if hov_tile else 'None'}")
            if hov_tile:
                draw_hud_line(f"    Biome: {hov_tile.biome}")
                draw_hud_line(f"    Elev: {int(hov_tile.elevation_meters)} m")
            y_offset += 10

            draw_hud_line("HOTKEYS:", (200, 210, 225), bold=True)
            draw_hud_line("  [N / P] : Next / Prev Seed")
            draw_hud_line("  [C]     : Invalidate Cache")
            draw_hud_line("  [R]     : Reset Camera")
            draw_hud_line("  [WASD]  : Pan Viewport")
            draw_hud_line("  [Scroll]: Smooth Zoom")

            pygame.display.flip()
            needs_redraw = False

    pygame.quit()


if __name__ == '__main__':
    main()

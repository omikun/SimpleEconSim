"""
REGNUM v3_wilderness — Pygame hex-world viewer for the 9x9 honeycomb.
Presentation layer over the conserved-money engine, modularized for extensibility.
"""

import os
import random
import sys

# IMPORTANT: keep this line BEFORE pygame so headless tests (SDL_VIDEODRIVER=dummy)
# and interactive runs both work.
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from logger import logInit

# Import sub-modules
from worldview_camera import (
    WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H, HEX_SIZE,
    clamp_cam, hex_px, tile_at
)
from worldview_charts import (
    PANEL_LEFT, sum_turns, tile_charts, chart_labels,
    plot_line_chart, plot_bar_pairs, plot_stacked_bars,
    draw_chart_cell, draw_chart_grid, draw_chart_large
)
from worldview_map import (
    NATION_COLORS, WILD_COLOR, WILD_EDGE, HEX_EDGE, TEXT, DIM, RED, GREEN, ACCENT, EDGE_LINE,
    nation_color, region_pop, homesteaders, tile_stats,
    draw_terrain_glyph, draw_pop_heat, trade_anim, draw_edges, draw_trade_arrows,
    draw_activity_badges, draw_pop_delta, province_members, draw_hex_map, pops_history
)
from worldview_ui import (
    PANEL_BG, selected_nation, draw_top_bar, draw_regime_readout,
    draw_panel, draw_ticker, draw_help
)
from worldview_engine import (
    get_layout, get_reverse_layout, build_world_view, ticker_push, step_world
)

FPS = 60
TURN_MS = 150
BG = (24, 24, 30)

# Backward-compatibility aliases for probe scripts & legacy callers
_layout = get_layout
_reverse_layout = get_reverse_layout
_clamp_cam = clamp_cam
_hex_px = hex_px
_tile_at = tile_at
_selected_nation = selected_nation
_ticker_push = ticker_push
_nation_color = nation_color
_region_pop = region_pop
_homesteaders = homesteaders
_tile_stats = tile_stats
_draw_terrain_glyph = draw_terrain_glyph
_draw_pop_heat = draw_pop_heat
_trade_anim = trade_anim
_draw_edges = draw_edges
_draw_trade_arrows = draw_trade_arrows
_draw_activity_badges = draw_activity_badges
_draw_pop_delta = draw_pop_delta
_province_members = province_members
_draw_hex_map = draw_hex_map
_draw_top_bar = draw_top_bar
_sum_turns = sum_turns
_tile_charts = tile_charts
_chart_labels = chart_labels
_plot_line_chart = plot_line_chart
_plot_bar_pairs = plot_bar_pairs
_plot_stacked_bars = plot_stacked_bars
_draw_chart_cell = draw_chart_cell
_draw_chart_grid = draw_chart_grid
_draw_chart_large = draw_chart_large
_draw_regime_readout = draw_regime_readout
_draw_panel = draw_panel
_draw_ticker = draw_ticker
_draw_help = draw_help


def render_frame(surface, world):
    """Draw one full frame (map + top bar + panel + ticker + help)."""
    font = pygame.font.Font(None, 28)
    font_small = pygame.font.Font(None, 22)
    surface.fill(BG)
    draw_top_bar(surface, world, font_small)
    draw_hex_map(surface, world, font, font_small)
    draw_panel(surface, world, font, font_small)
    draw_ticker(surface, world, font_small)
    draw_help(surface, world, font_small)


def main():
    seed = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--seed' and i + 1 < len(args):
            seed = int(args[i + 1])
            i += 2
        else:
            i += 1
    logInit()
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM v3 — Hex World")
    clock = pygame.time.Clock()

    world = build_world_view(seed=seed)
    pops_history.clear()
    for r in world['tiles']:
        if getattr(r, 'owner_nation', None) is not None:
            pops_history[r.name] = region_pop(r)

    last_tick = pygame.time.get_ticks()
    running = True
    drag = False
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked = tile_at(world, *event.pos)
                if clicked is not None:
                    world['selected_region'] = clicked
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                drag = True
                pygame.mouse.get_rel()
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                drag = False
            elif event.type == pygame.MOUSEMOTION and drag:
                dx, dy = pygame.mouse.get_rel()
                world['cam']['ox'] += dx
                world['cam']['oy'] += dy
                clamp_cam(world)
            elif event.type == pygame.MOUSEWHEEL:
                z = world['cam']['zoom']
                world['cam']['zoom'] = max(0.4, min(2.5, z * (1.15 ** event.y)))
                clamp_cam(world)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if world.get('help_open'):
                        world['help_open'] = False
                    else:
                        running = False
                elif event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_h or event.key == pygame.K_QUESTION:
                    world['help_open'] = not world.get('help_open', False)
                elif world.get('help_open'):
                    pass
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_s, pygame.K_RIGHT):
                    if not world['playing']:
                        step_world(world)
                elif event.key == pygame.K_TAB:
                    world['view'] = 0
                elif event.key == pygame.K_v:
                    world['scope'] = 'nation' if world.get('scope', 'tile') == 'tile' else 'tile'
                elif pygame.K_1 <= event.key <= pygame.K_6:
                    world['view'] = event.key - pygame.K_1 + 1
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    world['cam']['ox'] += 30
                    clamp_cam(world)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    world['cam']['ox'] -= 30
                    clamp_cam(world)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    world['cam']['oy'] += 30
                    clamp_cam(world)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    pass
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    world['cam']['zoom'] = min(2.5, world['cam']['zoom'] * 1.15)
                    clamp_cam(world)
                elif event.key == pygame.K_MINUS:
                    world['cam']['zoom'] = max(0.4, world['cam']['zoom'] / 1.15)
                    clamp_cam(world)

        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now
        world['frame'] = (world.get('frame', 0) + 1) % 600

        world['hover_region'] = None
        mx, my = pygame.mouse.get_pos()
        if mx < MAP_RIGHT and TOP_BAR_H <= my <= HEIGHT - TICKER_H:
            world['hover_region'] = tile_at(world, mx, my)

        render_frame(surface, world)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
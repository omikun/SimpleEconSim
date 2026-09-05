"""
REGNUM v3_wilderness — Pygame hex-world viewer for the 9x9 honeycomb.
Features cursor-anchored smooth map zoom, middle-mouse drag panning, WASD/arrow pan,
a 10-chart interactive sidebar, multi-province highlights, 3-tab comparative accounts suite,
and a 2-page paginated help guide with economic metrics glossary.
"""

import os
import random
import sys

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
from goods import Goods
from logger import logInit

# Import sub-modules
from worldview_camera import (
    WIDTH, HEIGHT, MAP_RIGHT, TOP_BAR_H, TICKER_H, HEX_SIZE,
    clamp_cam, zoom_cam_at, reset_cam, hex_px, tile_at
)
from worldview_charts import (
    PANEL_LEFT, sum_turns, tile_charts, chart_labels,
    plot_line_chart, plot_bar_pairs, plot_stacked_bars,
    draw_chart_cell, draw_chart_grid, draw_chart_large, chart_at_pixel
)
from worldview_map import (
    NATION_COLORS, WILD_COLOR, WILD_EDGE, HEX_EDGE, TEXT, DIM, RED, GREEN, ACCENT, EDGE_LINE,
    nation_color, region_pop, homesteaders, tile_stats,
    draw_terrain_glyph, draw_pop_heat, trade_anim, draw_edges, draw_trade_arrows,
    draw_activity_badges, draw_pop_delta, province_members, draw_hex_map, pops_history
)
from worldview_ui import (
    PANEL_BG, selected_nation, draw_top_bar, draw_top_bar_dropdown, draw_regime_readout,
    draw_panel, draw_ticker, draw_help, draw_zoom_hud, zoom_hud_hit,
    compare_btn_hit, help_page_hit, panel_tab_hit, get_font
)
from worldview_policies import (
    draw_policies_panel, policy_panel_hit
)
from worldview_compare import (
    draw_nations_comparison, compare_tab_hit
)
from worldview_actions import (
    draw_actions_modal, actions_tab_hit, top_bar_action_hit
)
from worldview_help import (
    draw_help_modal, help_modal_hit
)
from worldview_layers import (
    draw_layer_sidebar, layer_sidebar_hit, MAP_LAYERS
)
from worldview_build_panel import (
    draw_build_panel, build_panel_hit
)
from worldview_gov_panel import (
    draw_gov_panel, gov_panel_hit, draw_left_dock_buttons
)
from worldview_diplomacy_panel import (
    draw_diplomacy_panel, diplomacy_panel_hit
)
from worldview_debt_panel import (
    draw_debt_panel, debt_panel_hit
)
from worldview_science_panel import (
    draw_science_panel, science_panel_hit
)
from worldview_military_panel import (
    draw_military_panel, military_panel_hit
)
from worldview_left_dock import (
    open_left_panel, close_left_panels, is_any_left_panel_open, left_dock_buttons_hit
)
from worldview_transfer_dialog import (
    draw_transfer_dialog, transfer_dialog_hit
)
from worldview_tooltips import (
    draw_left_panel_tooltip
)
from worldview_engine import (
    get_layout, get_reverse_layout, build_world_view, ticker_push, step_world
)

FPS_ACTIVE = 60
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

# Backward-compatibility aliases for old FPS constants
FPS_PLAYING = FPS_ACTIVE
FPS_IDLE = 30
FPS = FPS_ACTIVE


def render_frame(surface, world, mouse_pos=None):
    """Draw one full frame (map + top bar + panel + ticker + zoom hud + comparison table + sovereign actions + help)."""
    world['_hovered_left_tooltip'] = None
    font = get_font(28)
    font_small = get_font(22)
    surface.fill(BG)
    # Check if a modal dialog covers the screen
    modal_active = bool(
        world.get('transfer_dialog', {}).get('open') or
        world.get('actions_modal_open') or
        world.get('help_open') or
        world.get('comparison_open')
    )
    effective_mouse = None if modal_active else mouse_pos

    draw_top_bar(surface, world, font_small, mouse_pos=effective_mouse)
    draw_hex_map(surface, world, font, font_small)
    draw_zoom_hud(surface, font_small, mouse_pos=effective_mouse)
    draw_layer_sidebar(surface, world, font_small, mouse_pos=effective_mouse)
    draw_left_dock_buttons(surface, world, font_small, mouse_pos=effective_mouse)
    draw_build_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_gov_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_diplomacy_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_debt_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_science_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_military_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_panel(surface, world, font, font_small, mouse_pos=effective_mouse)
    draw_ticker(surface, world, font_small)

    # Floating top-bar breakdown dropdown (renders on top of map, panel, sidebar, and ticker)
    if not modal_active:
        draw_top_bar_dropdown(surface, world, font_small, mouse_pos=mouse_pos)

    draw_nations_comparison(surface, world, font, font_small, mouse_pos=mouse_pos)
    draw_actions_modal(surface, world, font, font_small, mouse_pos=mouse_pos)
    draw_help_modal(surface, world, font, font_small)
    draw_transfer_dialog(surface, world, font, font_small, mouse_pos=mouse_pos)

    # Floating left-panel detailed button tooltips (disabled when modal dialog covers screen)
    if not modal_active:
        draw_left_panel_tooltip(surface, world, font_small, mouse_pos=mouse_pos)


def _mark_dirty(world):
    """Centralized helper to flag that a redraw is needed."""
    world['needs_redraw'] = True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="REGNUM v3 — Hex World")
    parser.add_argument('--seed', type=int, default=None, help='Unified master seed')
    parser.add_argument('--terrain-seed', type=int, default=None, help='Procedural heightmap terrain seed')
    parser.add_argument('--nation-seed', type=int, default=None, help='Starting nations selection and placement seed')
    args = parser.parse_args()
    logInit()
    pygame.init()
    surface = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("REGNUM v3 — Hex World")
    clock = pygame.time.Clock()

    from system_menu import setup_system_menu, RESTART_EVENT_TYPE
    setup_system_menu()

    world = build_world_view(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed)
    world['needs_redraw'] = True
    pops_history.clear()
    for r in world['tiles']:
        if getattr(r, 'owner_nation', None) is not None:
            pops_history[r.name] = region_pop(r)

    last_tick = pygame.time.get_ticks()
    running = True
    drag = False

    # Custom timer event for auto-play ticks (fires every TURN_MS when playing)
    AUTOPLAY_TIMER = pygame.USEREVENT + 1

    while running:
        # ── Event acquisition ──────────────────────────────────────────
        # Three modes:
        #  1. Modal open (compare/help) — static overlay, block thread → 0% CPU
        #  2. Active (playing or dragging) — poll at 60 FPS
        #  3. Idle, no modal — trade animation runs, poll at 30 FPS
        modal_open = world.get('compare_open') or world.get('help_open') or world.get('actions_open')
        is_active = world.get('playing') or drag
        if modal_open:
            # Static overlay — nothing animates, block until user does something.
            first = pygame.event.wait()
            events = [first] + list(pygame.event.get())
        elif is_active:
            events = pygame.event.get()
            clock.tick(FPS_ACTIVE)
        else:
            # Idle but trade animation still runs — tick at 30 FPS.
            events = pygame.event.get()
            clock.tick(30)

        now = pygame.time.get_ticks()
        mouse_pos = pygame.mouse.get_pos()

        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == RESTART_EVENT_TYPE:
                world = build_world_view(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed)
                world['needs_redraw'] = True
                pops_history.clear()
                for r in world['tiles']:
                    if getattr(r, 'owner_nation', None) is not None:
                        pops_history[r.name] = region_pop(r)
                _mark_dirty(world)
                continue
            elif event.type == pygame.ACTIVEEVENT:
                _mark_dirty(world)
            elif event.type == pygame.WINDOWEVENT if hasattr(pygame, 'WINDOWEVENT') else False:
                _mark_dirty(world)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                _mark_dirty(world)
                # 0a. Check if Fiscal Transfer Dialog is open
                if world.get('transfer_dialog', {}).get('open'):
                    if transfer_dialog_hit(event.pos, world):
                        continue

                # 0b. Check if Help Guide is open
                if world.get('help_open'):
                    if help_modal_hit(event.pos, world):
                        continue

                # 0c. Check if Comparison Table is open
                if world.get('compare_open'):
                    tab_hit = compare_tab_hit(event.pos, 30, 20, world=world)
                    if tab_hit is not None:
                        if tab_hit[0] == 'tab':
                            world['compare_tab'] = tab_hit[1]
                        elif tab_hit[0] == 'good':
                            world['compare_good'] = tab_hit[1]
                        continue
                    # Click outside header tabs or outside modal closes it
                    if event.pos[0] < 30 or event.pos[0] > WIDTH - 30 or event.pos[1] < 20 or event.pos[1] > HEIGHT - 20 or event.pos[1] < 48:
                        world['compare_open'] = False
                        continue

                # 0d. Check if Sovereign Actions Modal is open
                if world.get('actions_open'):
                    if actions_tab_hit(event.pos, 24, 16, world):
                        continue
                    # Click outside modal closes it
                    if event.pos[0] < 24 or event.pos[0] > WIDTH - 24 or event.pos[1] < 16 or event.pos[1] > HEIGHT - 16:
                        world['actions_open'] = False
                        continue

                # 1a. Check Top-Right Action buttons (Help / Compare / Diplomacy / Military)
                act_btn = top_bar_action_hit(event.pos)
                if act_btn == 'help':
                    world['help_open'] = not world.get('help_open', False)
                    continue
                elif act_btn == 'compare':
                    world['compare_open'] = not world.get('compare_open', False)
                    continue
                elif act_btn == 'diplomacy':
                    world['actions_open'] = True if (not world.get('actions_open') or world.get('actions_tab') != 1) else False
                    world['actions_tab'] = 1
                    continue
                elif act_btn == 'military':
                    world['actions_open'] = True if (not world.get('actions_open') or world.get('actions_tab') != 2) else False
                    world['actions_tab'] = 2
                    continue

                # 1b. Check Compare Nations top bar button fallback
                if compare_btn_hit(event.pos):
                    world['compare_open'] = not world.get('compare_open', False)
                    continue

                # 1c. Check Left Layer Sidebar toggle dock
                if layer_sidebar_hit(event.pos, world):
                    continue

                # 1d. Check Left Drawer hits (Build, Governance, Diplomacy, Debt, Science, Military)
                if left_dock_buttons_hit(event.pos, world):
                    continue
                if gov_panel_hit(event.pos, world):
                    continue
                if build_panel_hit(event.pos, world):
                    continue
                if diplomacy_panel_hit(event.pos, world):
                    continue
                if debt_panel_hit(event.pos, world):
                    continue
                if science_panel_hit(event.pos, world):
                    continue
                if military_panel_hit(event.pos, world):
                    continue

                # 2. Check Zoom HUD buttons
                hud_action = zoom_hud_hit(event.pos)
                if hud_action == 'in':
                    zoom_cam_at(world, 1.25, MAP_RIGHT // 2, HEIGHT // 2)
                elif hud_action == 'out':
                    zoom_cam_at(world, 1.0 / 1.25, MAP_RIGHT // 2, HEIGHT // 2)
                elif hud_action == 'reset':
                    reset_cam(world)
                else:
                    # 3a. Check Right Panel Tab switcher (Charts vs Policies)
                    tab_hit = panel_tab_hit(event.pos)
                    if tab_hit is not None:
                        world['panel_tab'] = tab_hit
                        continue

                    # 3b. Check Policies Action clicks
                    if world.get('panel_tab') == 'policies':
                        if policy_panel_hit(event.pos, world):
                            continue
                        if event.pos[0] < MAP_RIGHT:
                            clicked = tile_at(world, *event.pos)
                            if clicked is not None:
                                world['selected_region'] = clicked
                                world['build_panel_open'] = True
                                if getattr(clicked, 'owner_nation', None) is not None:
                                    world['selected_nation'] = clicked.owner_nation
                                    world['player_nation_name'] = clicked.owner_nation.name
                    elif world.get('panel_tab') == 'citizens':
                        from worldview_citizens import citizen_panel_hit
                        if citizen_panel_hit(event.pos, world):
                            continue
                        if event.pos[0] < MAP_RIGHT:
                            clicked = tile_at(world, *event.pos)
                            if clicked is not None:
                                world['selected_region'] = clicked
                                world['build_panel_open'] = True
                                if getattr(clicked, 'owner_nation', None) is not None:
                                    world['selected_nation'] = clicked.owner_nation
                                    world['player_nation_name'] = clicked.owner_nation.name
                    else:
                        # 3c. Check sidebar chart clicks
                        chart_top = 178 + TOP_BAR_H + 30
                        chart_bottom = HEIGHT - TICKER_H - 96
                        if world.get('view', 0) == 0:
                            clicked_chart = chart_at_pixel(event.pos, chart_top, chart_bottom, num_charts=10)
                            if clicked_chart is not None:
                                world['view'] = clicked_chart
                            else:
                                # 4. Check Hex tile picking
                                clicked = tile_at(world, *event.pos)
                                if clicked is not None:
                                    world['selected_region'] = clicked
                                    world['build_panel_open'] = True
                                    if getattr(clicked, 'owner_nation', None) is not None:
                                        world['selected_nation'] = clicked.owner_nation
                                        world['player_nation_name'] = clicked.owner_nation.name
                        else:
                            # Click in zoom view returns to grid view (or pins a tile)
                            if event.pos[0] >= PANEL_LEFT:
                                world['view'] = 0
                            else:
                                clicked = tile_at(world, *event.pos)
                                if clicked is not None:
                                    world['selected_region'] = clicked
                                    world['build_panel_open'] = True
                                    if getattr(clicked, 'owner_nation', None) is not None:
                                        world['selected_nation'] = clicked.owner_nation
                                        world['player_nation_name'] = clicked.owner_nation.name
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
                # Middle or Right mouse drag to pan
                drag = True
                _mark_dirty(world)
            elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
                drag = False
                _mark_dirty(world)
            elif event.type == pygame.MOUSEMOTION:
                if drag:
                    dx, dy = event.rel
                    world['cam']['ox'] += dx
                    world['cam']['oy'] += dy
                    clamp_cam(world)
                    _mark_dirty(world)
                # Hover detection handled below (batched after all events)
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if mx < MAP_RIGHT:
                    factor = 1.15 ** event.y
                    zoom_cam_at(world, factor, mx, my)
                    _mark_dirty(world)
            elif event.type == pygame.KEYDOWN:
                _mark_dirty(world)
                # If help guide is open, intercept page keys
                if world.get('help_open'):
                    if event.key in (pygame.K_1, pygame.K_KP1, pygame.K_PAGEUP, pygame.K_LEFT):
                        world['help_page'] = 1
                    elif event.key in (pygame.K_2, pygame.K_KP2, pygame.K_PAGEDOWN, pygame.K_RIGHT):
                        world['help_page'] = 2
                    elif event.key == pygame.K_TAB:
                        world['help_page'] = 2 if world.get('help_page', 1) == 1 else 1
                    elif event.key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_h, pygame.K_QUESTION):
                        world['help_open'] = False
                    continue

                # If Sovereign Actions modal is open, intercept navigation keys
                if world.get('actions_open'):
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        world['actions_tab'] = 1
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        world['actions_tab'] = 2
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        world['actions_tab'] = 3
                    elif event.key in (pygame.K_4, pygame.K_KP4):
                        world['actions_tab'] = 4
                    elif event.key == pygame.K_d:
                        world['actions_tab'] = 1
                    elif event.key == pygame.K_m:
                        world['actions_tab'] = 2
                    elif event.key == pygame.K_c:
                        world['actions_tab'] = 3
                    elif event.key == pygame.K_a:
                        world['actions_tab'] = 4
                    elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                        world['actions_tab'] = (world.get('actions_tab', 1) % 4) + 1
                    elif event.key == pygame.K_LEFT:
                        world['actions_tab'] = 4 if world.get('actions_tab', 1) == 1 else world.get('actions_tab', 1) - 1
                    elif event.key == pygame.K_SPACE:
                        world['playing'] = not world['playing']
                        last_tick = now
                    elif event.key in (pygame.K_n, pygame.K_PERIOD):
                        world['playing'] = False
                        step_world(world)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                        world['actions_open'] = False
                    continue

                # If help modal is open, intercept navigation keys
                if world.get('help_open'):
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        world['help_page'] = 1
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        world['help_page'] = 2
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        world['help_page'] = 3
                    elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                        world['help_page'] = (world.get('help_page', 1) % 3) + 1
                    elif event.key == pygame.K_LEFT:
                        world['help_page'] = 3 if world.get('help_page', 1) == 1 else world.get('help_page', 1) - 1
                    elif event.key in (pygame.K_ESCAPE, pygame.K_h, pygame.K_QUESTION):
                        world['help_open'] = False
                    _mark_dirty(world)
                    continue

                # If comparison modal is open, intercept navigation keys
                if world.get('compare_open'):
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        world['compare_tab'] = 1
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        world['compare_tab'] = 2
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        world['compare_tab'] = 3
                    elif event.key in (pygame.K_TAB, pygame.K_RIGHT):
                        world['compare_tab'] = (world.get('compare_tab', 1) % 3) + 1
                    elif event.key == pygame.K_LEFT:
                        world['compare_tab'] = 3 if world.get('compare_tab', 1) == 1 else world.get('compare_tab', 1) - 1
                    elif event.key == pygame.K_f:
                        world['compare_good'] = Goods.food
                    elif event.key == pygame.K_w:
                        world['compare_good'] = Goods.wood
                    elif event.key == pygame.K_u:
                        world['compare_good'] = Goods.furniture
                    elif event.key == pygame.K_SPACE:
                        world['playing'] = not world['playing']
                        last_tick = now
                    elif event.key in (pygame.K_n, pygame.K_PERIOD):
                        world['playing'] = False
                        step_world(world)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_c):
                        world['compare_open'] = False
                    continue

                if event.key == pygame.K_ESCAPE:
                    if world.get('view', 0) != 0:
                        world['view'] = 0
                    else:
                        running = False
                elif event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_d:
                    world['actions_open'] = not world.get('actions_open', False)
                    world['actions_tab'] = 1
                elif event.key == pygame.K_m:
                    world['actions_open'] = not world.get('actions_open', False)
                    world['actions_tab'] = 2
                elif event.key == pygame.K_c:
                    world['compare_open'] = not world.get('compare_open', False)
                elif event.key == pygame.K_r and (event.mod & (pygame.KMOD_META | pygame.KMOD_CTRL)):
                    world = build_world_view(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed)
                    world['needs_redraw'] = True
                    pops_history.clear()
                    for r in world['tiles']:
                        if getattr(r, 'owner_nation', None) is not None:
                            pops_history[r.name] = region_pop(r)
                    _mark_dirty(world)
                    continue
                elif event.key == pygame.K_h or event.key == pygame.K_QUESTION:
                    world['help_open'] = not world.get('help_open', False)
                elif event.key == pygame.K_SPACE:
                    world['playing'] = not world['playing']
                    last_tick = now
                elif event.key in (pygame.K_n, pygame.K_PERIOD):
                    world['playing'] = False
                    step_world(world)
                elif event.key in (pygame.K_h, pygame.K_SLASH, pygame.K_QUESTION):
                    world['help_open'] = not world.get('help_open', False)
                    _mark_dirty(world)
                elif event.key == pygame.K_b:
                    is_open = world.get('build_panel_open', False)
                    open_left_panel(world, None if is_open else 'build')
                    _mark_dirty(world)
                elif event.key == pygame.K_g:
                    is_open = world.get('gov_panel_open', False)
                    open_left_panel(world, None if is_open else 'governance')
                    _mark_dirty(world)
                elif event.key == pygame.K_d:
                    is_open = world.get('diplomacy_panel_open', False)
                    open_left_panel(world, None if is_open else 'diplomacy')
                    _mark_dirty(world)
                elif event.key == pygame.K_s:
                    is_open = world.get('debt_panel_open', False)
                    open_left_panel(world, None if is_open else 'debt')
                    _mark_dirty(world)
                elif event.key in (pygame.K_t, pygame.K_i):
                    is_open = world.get('science_panel_open', False)
                    open_left_panel(world, None if is_open else 'science')
                    _mark_dirty(world)
                elif event.key == pygame.K_m:
                    is_open = world.get('military_panel_open', False)
                    open_left_panel(world, None if is_open else 'military')
                    _mark_dirty(world)
                elif event.key == pygame.K_ESCAPE:
                    if world.get('citizen_chart_view', 0) != 0:
                        world['citizen_chart_view'] = 0
                    elif world.get('transfer_dialog', {}).get('open'):
                        world['transfer_dialog']['open'] = False
                    elif world.get('help_open'):
                        world['help_open'] = False
                    elif world.get('actions_open'):
                        world['actions_open'] = False
                    elif world.get('compare_open'):
                        world['compare_open'] = False
                    elif is_any_left_panel_open(world):
                        close_left_panels(world)
                    else:
                        world['selected_region'] = None
                    _mark_dirty(world)
                elif event.key == pygame.K_p:
                    world['panel_tab'] = 'policies' if world.get('panel_tab', 'charts') == 'charts' else 'charts'
                    _mark_dirty(world)
                elif event.key == pygame.K_TAB:
                    if world.get('panel_tab') == 'citizens':
                        world['citizen_chart_view'] = 0
                    elif world.get('panel_tab') == 'policies':
                        world['panel_tab'] = 'charts'
                    else:
                        world['view'] = 0
                elif event.key == pygame.K_v:
                    world['scope'] = 'nation' if world.get('scope', 'tile') == 'tile' else 'tile'
                    # Also cycle policy scope
                    curr_sc = world.get('policy_scope', 'tile')
                    world['policy_scope'] = 'province' if curr_sc == 'tile' else ('nation' if curr_sc == 'province' else 'tile')
                    _mark_dirty(world)
                elif event.key == pygame.K_l:
                    world['layers_collapsed'] = not world.get('layers_collapsed', False)
                    _mark_dirty(world)
                # Map info layer hotkeys (1..6)
                elif event.key in (pygame.K_F1, pygame.K_1, pygame.K_KP1):
                    world['map_layer'] = 'overview'
                    _mark_dirty(world)
                elif event.key in (pygame.K_F2, pygame.K_2, pygame.K_KP2):
                    world['map_layer'] = 'physical'
                    _mark_dirty(world)
                elif event.key in (pygame.K_F3, pygame.K_3, pygame.K_KP3):
                    world['map_layer'] = 'population'
                    _mark_dirty(world)
                elif event.key in (pygame.K_F4, pygame.K_4, pygame.K_KP4):
                    world['map_layer'] = 'economy'
                    _mark_dirty(world)
                elif event.key in (pygame.K_F5, pygame.K_5, pygame.K_KP5):
                    world['map_layer'] = 'production'
                    _mark_dirty(world)
                elif event.key in (pygame.K_F6, pygame.K_6, pygame.K_KP6):
                    world['map_layer'] = 'military'
                    _mark_dirty(world)
                elif event.key in (pygame.K_7, pygame.K_KP7):
                    world['view'] = 7
                elif event.key in (pygame.K_8, pygame.K_KP8):
                    world['view'] = 8
                elif event.key in (pygame.K_9, pygame.K_KP9):
                    world['view'] = 9
                elif event.key == pygame.K_0:
                    world['view'] = 10 if world.get('view') != 10 else 0
                elif event.key in (pygame.K_r, pygame.K_HOME):
                    reset_cam(world)
                # WASD and Arrow keys for smooth panning
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    world['cam']['ox'] += 40
                    clamp_cam(world)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    world['cam']['ox'] -= 40
                    clamp_cam(world)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    world['cam']['oy'] += 40
                    clamp_cam(world)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    world['cam']['oy'] -= 40
                    clamp_cam(world)
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    zoom_cam_at(world, 1.15, MAP_RIGHT // 2, HEIGHT // 2)
                elif event.key == pygame.K_MINUS:
                    zoom_cam_at(world, 1.0 / 1.15, MAP_RIGHT // 2, HEIGHT // 2)

        # ── Auto-play simulation tick ──────────────────────────────────
        if world['playing'] and now - last_tick >= TURN_MS:
            step_world(world)
            last_tick = now
            _mark_dirty(world)

        # ── Frame counter: always advance for trade animation ──────────
        # When a modal is open we skip advancing (nothing animates behind it).
        if not modal_open:
            world['frame'] = (world.get('frame', 0) + 1) % 600

        # ── Hover detection: only redraw if hovered region changed ─────
        prev_hover = world.get('hover_region')
        world['hover_region'] = None
        mx, my = mouse_pos
        if mx < MAP_RIGHT and TOP_BAR_H <= my <= HEIGHT - TICKER_H:
            world['hover_region'] = tile_at(world, mx, my)
        if world['hover_region'] is not prev_hover:
            _mark_dirty(world)

        # ── Animation tick: always redraw when no modal is blocking ─────
        # This keeps trade dots and any future animations alive at idle.
        if not modal_open:
            _mark_dirty(world)

        # ── Render only when dirty ─────────────────────────────────────
        if world.get('needs_redraw'):
            render_frame(surface, world, mouse_pos=mouse_pos)
            pygame.display.flip()
            world['needs_redraw'] = False

    pygame.quit()


if __name__ == "__main__":
    main()
"""
worldview_left_dock.py — Unified Left Dock & Drawer Navigation Manager for REGNUM.

Manages all left-hand drawers docked on the left of the hex map:
1. [🔨 Build Menu (B)]
2. [🏛️ Governance (G)]
3. [🤝 Diplomacy (D)]
4. [📜 Sovereign Debt (S)]
5. [🔬 Science & Tech (T)]
6. [⚔️ Military (M)]

Provides:
- draw_left_dock_buttons: Renders the 6 vertical toggle buttons when drawers are closed.
- draw_drawer_top_tabs: Sleek 6-tab icon switcher rendered at top of open drawers.
- open_left_panel / close_left_panels: Centralized panel state synchronization.
- left_dock_hit: Handles clicking dock buttons and drawer top tabs.
"""

from __future__ import annotations
import pygame
from worldview_camera import HEIGHT, TOP_BAR_H, TICKER_H
from worldview_map import ACCENT, TEXT, DIM, RED, GREEN
from ui_icons import get_icon

DOCK_X = 14
DOCK_Y = TOP_BAR_H + 10
DOCK_BTN_W = 158
DOCK_BTN_H = 28
DOCK_SPACING = 6

PANEL_X = 14
PANEL_Y = TOP_BAR_H + 10
PANEL_W = 310
PANEL_H = HEIGHT - TOP_BAR_H - TICKER_H - 18

PANELS_DEF = [
    ('build', 'Build (B)', 'hammer', 'b'),
    ('governance', 'Governance (G)', 'municipal', 'g'),
    ('diplomacy', 'Diplomacy (D)', 'crown', 'd'),
    ('debt', 'Debt & Bonds (S)', 'scale', 's'),
    ('science', 'Science (T)', 'rare_minerals', 't'),
    ('military', 'Military (M)', 'military', 'm'),
]


def get_active_left_panel(world: dict) -> str | None:
    """Return the identifier of the currently open left drawer, or None."""
    if world.get('build_panel_open'):
        world['left_panel'] = 'build'
        return 'build'
    if world.get('gov_panel_open'):
        world['left_panel'] = 'governance'
        return 'governance'
    if world.get('diplomacy_panel_open'):
        world['left_panel'] = 'diplomacy'
        return 'diplomacy'
    if world.get('debt_panel_open'):
        world['left_panel'] = 'debt'
        return 'debt'
    if world.get('science_panel_open'):
        world['left_panel'] = 'science'
        return 'science'
    if world.get('military_panel_open'):
        world['left_panel'] = 'military'
        return 'military'
    world['left_panel'] = None
    return None


def open_left_panel(world: dict, panel_name: str | None) -> None:
    """Set active left drawer, synchronizing all backward-compatible flags."""
    world['left_panel'] = panel_name
    world['build_panel_open'] = (panel_name == 'build')
    world['gov_panel_open'] = (panel_name == 'governance')
    world['diplomacy_panel_open'] = (panel_name == 'diplomacy')
    world['debt_panel_open'] = (panel_name == 'debt')
    world['science_panel_open'] = (panel_name == 'science')
    world['military_panel_open'] = (panel_name == 'military')

    if panel_name is not None:
        world['layers_collapsed'] = True


def close_left_panels(world: dict) -> None:
    """Close all left-hand drawer panels."""
    world['left_panel'] = None
    world['build_panel_open'] = False
    world['gov_panel_open'] = False
    world['diplomacy_panel_open'] = False
    world['debt_panel_open'] = False
    world['science_panel_open'] = False
    world['military_panel_open'] = False


def is_any_left_panel_open(world: dict) -> bool:
    """Return True if any left drawer is currently open."""
    return get_active_left_panel(world) is not None


def draw_left_dock_buttons(surface: pygame.Surface, world: dict, font_small: pygame.font.Font, mouse_pos=None) -> None:
    """Draw the floating vertical left dock toggle buttons when drawers are closed."""
    if is_any_left_panel_open(world):
        return

    mx, my = mouse_pos if mouse_pos else (-1, -1)
    x = DOCK_X
    btn_w = DOCK_BTN_W
    btn_h = DOCK_BTN_H

    for i, (p_id, p_label, p_icon, _) in enumerate(PANELS_DEF):
        by = DOCK_Y + i * (btn_h + DOCK_SPACING)
        rect = (x, by, btn_w, btn_h)
        from ui_targets import register_target
        register_target(world, rect, ('open_left_panel', p_id), tooltip_id=f"dock_{p_id}", scope='dock')
        is_hov = rect[0] <= mx <= rect[0] + btn_w and rect[1] <= my <= rect[1] + btn_h
        if is_hov:
            from worldview_tooltips import get_button_tooltip_data
            pinned = world.get('selected_region')
            tdata = get_button_tooltip_data(f"dock_{p_id}", world, pinned)
            if tdata:
                tdata['btn_rect'] = rect
                world['_hovered_left_tooltip'] = tdata

        btn_surf = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        btn_surf.fill((20, 22, 32, 240) if not is_hov else (34, 40, 58, 245))
        surface.blit(btn_surf, (x, by))
        pygame.draw.rect(surface, ACCENT if is_hov else (65, 70, 90), rect, 1, border_radius=5)

        ico = get_icon(p_icon, 14)
        surface.blit(ico, (x + 8, by + 7))
        txt = font_small.render(p_label, True, (255, 255, 255) if is_hov else TEXT)
        surface.blit(txt, (x + 28, by + 6))


def draw_drawer_top_tabs(surface: pygame.Surface, world: dict, x: int, y: int, w: int,
                         active_panel: str, font_small: pygame.font.Font, mouse_pos=None) -> int:
    """Render a compact 6-tab icon switcher along the top of an open drawer. Returns next Y pos."""
    mx, my = mouse_pos if mouse_pos else (-1, -1)
    tab_gap = 4
    total_tabs = len(PANELS_DEF)
    available_w = w - 16
    tab_w = (available_w - (total_tabs - 1) * tab_gap) // total_tabs
    tab_h = 24

    for i, (p_id, _, p_icon, _) in enumerate(PANELS_DEF):
        tx = x + 8 + i * (tab_w + tab_gap)
        t_rect = (tx, y, tab_w, tab_h)
        from ui_targets import register_target
        register_target(world, t_rect, ('open_left_panel', p_id), tooltip_id=f"dock_{p_id}", scope='drawer_tabs')
        is_sel = (active_panel == p_id)
        is_hov = t_rect[0] <= mx <= t_rect[0] + tab_w and t_rect[1] <= my <= t_rect[1] + tab_h
        if is_hov:
            from worldview_tooltips import get_button_tooltip_data
            pinned = world.get('selected_region')
            tdata = get_button_tooltip_data(f"dock_{p_id}", world, pinned)
            if tdata:
                tdata['btn_rect'] = t_rect
                world['_hovered_left_tooltip'] = tdata

        bg = (52, 72, 100) if is_sel else ((38, 42, 56) if is_hov else (26, 28, 38))
        bc = ACCENT if is_sel else ((85, 95, 120) if is_hov else (50, 55, 72))
        pygame.draw.rect(surface, bg, t_rect, border_radius=4)
        pygame.draw.rect(surface, bc, t_rect, 1, border_radius=4)

        ico = get_icon(p_icon, 14)
        surface.blit(ico, ico.get_rect(center=(tx + tab_w // 2, y + tab_h // 2)))

    return y + tab_h + 8


def left_dock_buttons_hit(pos: tuple[int, int], world: dict) -> bool:
    """Hit-test for closed left dock buttons. Returns True if a dock button was clicked."""
    if is_any_left_panel_open(world):
        return False

    if world is not None:
        from ui_targets import find_target
        t = find_target(world, pos, scope='dock')
        if t and isinstance(t.action, tuple) and t.action[0] == 'open_left_panel':
            open_left_panel(world, t.action[1])
            return True

    # Legacy fallback calculation
    mx, my = pos
    x = DOCK_X
    btn_w = DOCK_BTN_W
    btn_h = DOCK_BTN_H

    for i, (p_id, _, _, _) in enumerate(PANELS_DEF):
        by = DOCK_Y + i * (btn_h + DOCK_SPACING)
        if x <= mx <= x + btn_w and by <= my <= by + btn_h:
            open_left_panel(world, p_id)
            return True

    return False


def drawer_top_tabs_hit(pos: tuple[int, int], world: dict, x: int, y: int, w: int) -> bool:
    """Hit-test for 6-tab drawer top switcher. Returns True if a tab was clicked."""
    if world is not None:
        from ui_targets import find_target
        t = find_target(world, pos, scope='drawer_tabs')
        if t and isinstance(t.action, tuple) and t.action[0] == 'open_left_panel':
            open_left_panel(world, t.action[1])
            return True

    # Legacy fallback calculation
    mx, my = pos
    tab_gap = 4
    total_tabs = len(PANELS_DEF)
    available_w = w - 16
    tab_w = (available_w - (total_tabs - 1) * tab_gap) // total_tabs
    tab_h = 24

    for i, (p_id, _, _, _) in enumerate(PANELS_DEF):
        tx = x + 8 + i * (tab_w + tab_gap)
        if tx <= mx <= tx + tab_w and y <= my <= y + tab_h:
            open_left_panel(world, p_id)
            return True

    return False

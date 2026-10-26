"""
worldview_left_dock.py — Unified left dock & drawer navigation.

Backward-compatible facade re-exporting from client.desktop.panels.left_dock.
"""

from __future__ import annotations

import client.desktop.panels.left_dock as _impl
from client.desktop.panels.left_dock import (
    DOCK_X,
    DOCK_Y,
    DOCK_BTN_W,
    DOCK_BTN_H,
    DOCK_SPACING,
    PANEL_X,
    PANEL_Y,
    PANEL_W,
    PANEL_H,
    PANELS_DEF,
    get_active_left_panel,
    open_left_panel,
    close_left_panels,
    is_any_left_panel_open,
    draw_left_dock_buttons,
    draw_drawer_top_tabs,
    left_dock_buttons_hit,
    drawer_top_tabs_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'DOCK_X',
    'DOCK_Y',
    'DOCK_BTN_W',
    'DOCK_BTN_H',
    'DOCK_SPACING',
    'PANEL_X',
    'PANEL_Y',
    'PANEL_W',
    'PANEL_H',
    'PANELS_DEF',
    'get_active_left_panel',
    'open_left_panel',
    'close_left_panels',
    'is_any_left_panel_open',
    'draw_left_dock_buttons',
    'draw_drawer_top_tabs',
    'left_dock_buttons_hit',
    'drawer_top_tabs_hit',
]

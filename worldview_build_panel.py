"""
worldview_build_panel.py — Multi-tier infrastructure build panel.

Backward-compatible facade re-exporting from client.desktop.panels.build_panel.
"""

from __future__ import annotations

import client.desktop.panels.build_panel as _impl
from client.desktop.panels.build_panel import (
    BUILD_PANEL_X,
    BUILD_PANEL_Y,
    BUILD_PANEL_W,
    BUILD_PANEL_H,
    draw_build_panel,
    _draw_equalization_section,
    _get_tier_layout,
    _draw_tier_section,
    build_panel_hit,
    _handle_build_click,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'BUILD_PANEL_X',
    'BUILD_PANEL_Y',
    'BUILD_PANEL_W',
    'BUILD_PANEL_H',
    'draw_build_panel',
    '_draw_equalization_section',
    '_get_tier_layout',
    '_draw_tier_section',
    'build_panel_hit',
    '_handle_build_click',
]

"""
worldview_military_panel.py — Military & garrison defense drawer.

Backward-compatible facade re-exporting from client.desktop.panels.military_panel.
"""

from __future__ import annotations

import client.desktop.panels.military_panel as _impl
from client.desktop.panels.military_panel import (
    CARD_BG,
    CARD_BORDER,
    BTN_BG,
    BTN_HOVER,
    BTN_BORDER,
    _get_active_nation,
    _draw_btn,
    draw_military_panel,
    military_panel_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_BG',
    'CARD_BORDER',
    'BTN_BG',
    'BTN_HOVER',
    'BTN_BORDER',
    '_get_active_nation',
    '_draw_btn',
    'draw_military_panel',
    'military_panel_hit',
]

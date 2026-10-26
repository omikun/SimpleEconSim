"""
worldview_science_panel.py — Science, innovation & royal bounties drawer.

Backward-compatible facade re-exporting from client.desktop.panels.science_panel.
"""

from __future__ import annotations

import client.desktop.panels.science_panel as _impl
from client.desktop.panels.science_panel import (
    CARD_BG,
    CARD_BORDER,
    BTN_BG,
    BTN_HOVER,
    BTN_BORDER,
    _get_active_nation,
    _draw_btn,
    draw_science_panel,
    science_panel_hit,
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
    'draw_science_panel',
    'science_panel_hit',
]

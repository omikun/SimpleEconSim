"""
worldview_progress_panel.py — Progress & development drawer.

Backward-compatible facade re-exporting from client.desktop.panels.progress_panel.
"""

from __future__ import annotations

import client.desktop.panels.progress_panel as _impl
from client.desktop.panels.progress_panel import (
    CARD_BG,
    CARD_BORDER,
    SECTION_BG,
    _PROGRESS_BUTTONS,
    _get_active_nation,
    _collect_items_for_nation,
    draw_progress_panel,
    progress_panel_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_BG',
    'CARD_BORDER',
    'SECTION_BG',
    '_PROGRESS_BUTTONS',
    '_get_active_nation',
    '_collect_items_for_nation',
    'draw_progress_panel',
    'progress_panel_hit',
]

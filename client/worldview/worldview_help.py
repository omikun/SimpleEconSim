"""
worldview_help.py — Interactive system manual & seed registry.

Backward-compatible facade re-exporting from client.desktop.help.
"""

from __future__ import annotations

import client.desktop.help as _impl
from client.desktop.help import (
    HELP_PANEL_RECT,
    CLOSE_BTN_RECT,
    HELP_TAB1_RECT,
    HELP_TAB2_RECT,
    HELP_TAB3_RECT,
    draw_help_modal,
    help_modal_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'HELP_PANEL_RECT',
    'CLOSE_BTN_RECT',
    'HELP_TAB1_RECT',
    'HELP_TAB2_RECT',
    'HELP_TAB3_RECT',
    'draw_help_modal',
    'help_modal_hit',
]

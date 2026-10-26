"""
worldview_compare.py — Cross-nation comparison modal.

Backward-compatible facade re-exporting from client.desktop.inspect.compare.
"""

from __future__ import annotations

import client.desktop.inspect.compare as _impl
from client.desktop.inspect.compare import (
    BG_MODAL,
    BORDER_MODAL,
    ROW_BG1,
    ROW_BG2,
    SEC_BG,
    TAB_ACTIVE_BG,
    TAB_INACTIVE_BG,
    fmt_delta,
    draw_tab_headers,
    compare_tab_hit,
    get_prev,
    draw_tab1_macro,
    draw_tab2_goods,
    draw_tab3_fx_banking,
    _get_font,
    _OVERLAY_SURFACE,
    _get_overlay,
    draw_nations_comparison,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'BG_MODAL',
    'BORDER_MODAL',
    'ROW_BG1',
    'ROW_BG2',
    'SEC_BG',
    'TAB_ACTIVE_BG',
    'TAB_INACTIVE_BG',
    'fmt_delta',
    'draw_tab_headers',
    'compare_tab_hit',
    'get_prev',
    'draw_tab1_macro',
    'draw_tab2_goods',
    'draw_tab3_fx_banking',
    '_get_font',
    '_OVERLAY_SURFACE',
    '_get_overlay',
    'draw_nations_comparison',
]

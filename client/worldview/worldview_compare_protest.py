"""
worldview_compare_protest.py — Protest energy & grievance comparison tab.

Backward-compatible facade re-exporting from client.desktop.inspect.compare_protest.
"""

from __future__ import annotations

import client.desktop.inspect.compare_protest as _impl
from client.desktop.inspect.compare_protest import (
    ROW_BG1,
    ROW_BG2,
    SEC_BG,
    CARD_BG,
    CARD_BORDER,
    COL_OVERWORK,
    COL_ENCLOSURE,
    COL_HUNGER,
    COL_STRIKES,
    COL_STATE,
    COL_INEQ,
    _get_font,
    _safe_last,
    _extract_tile_grievances,
    draw_tab5_protest,
    all_tile_stats_tiles,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'ROW_BG1',
    'ROW_BG2',
    'SEC_BG',
    'CARD_BG',
    'CARD_BORDER',
    'COL_OVERWORK',
    'COL_ENCLOSURE',
    'COL_HUNGER',
    'COL_STRIKES',
    'COL_STATE',
    'COL_INEQ',
    '_get_font',
    '_safe_last',
    '_extract_tile_grievances',
    'draw_tab5_protest',
    'all_tile_stats_tiles',
]

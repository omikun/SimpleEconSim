"""
worldview_compare_extraction.py — Class wealth extraction comparison tab.

Backward-compatible facade re-exporting from client.desktop.inspect.compare_extraction.
"""

from __future__ import annotations

import client.desktop.inspect.compare_extraction as _impl
from client.desktop.inspect.compare_extraction import (
    ROW_BG1,
    ROW_BG2,
    SEC_BG,
    CARD_BG,
    CARD_BORDER,
    COL_TRIBUTE,
    COL_RENT,
    COL_SURPLUS,
    COL_TAX,
    COL_HEALTH,
    COL_ALIEN,
    _get_font,
    _safe_last,
    _get_tile_stats,
    draw_tab4_extraction,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'ROW_BG1',
    'ROW_BG2',
    'SEC_BG',
    'CARD_BG',
    'CARD_BORDER',
    'COL_TRIBUTE',
    'COL_RENT',
    'COL_SURPLUS',
    'COL_TAX',
    'COL_HEALTH',
    'COL_ALIEN',
    '_get_font',
    '_safe_last',
    '_get_tile_stats',
    'draw_tab4_extraction',
]

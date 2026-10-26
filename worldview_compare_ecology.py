"""
worldview_compare_ecology.py — Ecological & public health comparison tab.

Backward-compatible facade re-exporting from client.desktop.inspect.compare_ecology.
"""

from __future__ import annotations

import client.desktop.inspect.compare_ecology as _impl
from client.desktop.inspect.compare_ecology import (
    ROW_BG1,
    ROW_BG2,
    SEC_BG,
    CARD_BG,
    CARD_BORDER,
    COL_FERT,
    COL_NUTR,
    COL_SMOG,
    COL_WATER,
    COL_CHEM,
    COL_MALNUTR,
    COL_CHOLERA,
    COL_BRONCH,
    COL_TOXIC,
    COL_PUBLIC,
    COL_PRIVATE,
    _get_font,
    _safe_last,
    _extract_tile_stats,
    draw_tab6_ecology,
    _draw_ecology_summary_cards,
    _draw_country_table,
    _draw_province_table,
    _draw_city_table,
    _draw_table_header,
    _draw_table_row,
    handle_tab6_click,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'ROW_BG1',
    'ROW_BG2',
    'SEC_BG',
    'CARD_BG',
    'CARD_BORDER',
    'COL_FERT',
    'COL_NUTR',
    'COL_SMOG',
    'COL_WATER',
    'COL_CHEM',
    'COL_MALNUTR',
    'COL_CHOLERA',
    'COL_BRONCH',
    'COL_TOXIC',
    'COL_PUBLIC',
    'COL_PRIVATE',
    '_get_font',
    '_safe_last',
    '_extract_tile_stats',
    'draw_tab6_ecology',
    '_draw_ecology_summary_cards',
    '_draw_country_table',
    '_draw_province_table',
    '_draw_city_table',
    '_draw_table_header',
    '_draw_table_row',
    'handle_tab6_click',
]

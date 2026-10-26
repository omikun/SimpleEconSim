"""
worldview_citizens.py — Citizen status & demographics inspector.

Backward-compatible facade re-exporting from client.desktop.inspect.citizens.
"""

from __future__ import annotations

import client.desktop.inspect.citizens as _impl
from client.desktop.inspect.citizens import (
    PANEL_LEFT,
    PANEL_W,
    C_SERF,
    C_TENANT,
    C_PROLE,
    C_DISPOSS,
    C_GENTRY,
    C_BOURG,
    C_FORAGE,
    C_MARKET,
    C_HUNGER,
    C_COMMONS,
    C_RENT,
    C_ARREARS,
    C_GINI,
    C_PROTEST,
    _get_class_series,
    tile_citizen_charts,
    nation_citizen_charts,
    draw_citizens_panel,
    citizen_panel_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'PANEL_LEFT',
    'PANEL_W',
    'C_SERF',
    'C_TENANT',
    'C_PROLE',
    'C_DISPOSS',
    'C_GENTRY',
    'C_BOURG',
    'C_FORAGE',
    'C_MARKET',
    'C_HUNGER',
    'C_COMMONS',
    'C_RENT',
    'C_ARREARS',
    'C_GINI',
    'C_PROTEST',
    '_get_class_series',
    'tile_citizen_charts',
    'nation_citizen_charts',
    'draw_citizens_panel',
    'citizen_panel_hit',
]

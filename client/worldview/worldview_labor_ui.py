"""
worldview_labor_ui.py — Labor & livelihood dashboard.

Backward-compatible facade re-exporting from client.desktop.inspect.labor_ui.
"""

from __future__ import annotations

import client.desktop.inspect.labor_ui as _impl
from client.desktop.inspect.labor_ui import (
    PANEL_LEFT,
    PANEL_W,
    C_SHIFT,
    C_CAP,
    C_SV,
    C_ALIEN,
    C_HEALTH,
    C_VICE,
    C_CONSC,
    C_ENTERTAIN,
    C_PROTEST,
    C_STRIKE,
    C_SABOTAGE,
    C_MACHINES,
    tile_labor_charts,
    nation_labor_charts,
    draw_labor_dashboard,
    labor_panel_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'PANEL_LEFT',
    'PANEL_W',
    'C_SHIFT',
    'C_CAP',
    'C_SV',
    'C_ALIEN',
    'C_HEALTH',
    'C_VICE',
    'C_CONSC',
    'C_ENTERTAIN',
    'C_PROTEST',
    'C_STRIKE',
    'C_SABOTAGE',
    'C_MACHINES',
    'tile_labor_charts',
    'nation_labor_charts',
    'draw_labor_dashboard',
    'labor_panel_hit',
]

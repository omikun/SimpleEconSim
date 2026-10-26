"""
worldview_vis_radar.py — 4D alienation radar & electoral barometer.

Backward-compatible facade re-exporting from client.desktop.inspect.vis_radar.
"""

from __future__ import annotations

import client.desktop.inspect.vis_radar as _impl
from client.desktop.inspect.vis_radar import (
    CARD_BG,
    CARD_BORDER,
    COL_PROLE,
    COL_SERF,
    COL_BOURG,
    COL_POPULAR,
    COL_WARCHEST,
    _get_font,
    compute_alienation_4d,
    draw_alienation_radar,
    draw_electoral_barometer,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_BG',
    'CARD_BORDER',
    'COL_PROLE',
    'COL_SERF',
    'COL_BOURG',
    'COL_POPULAR',
    'COL_WARCHEST',
    '_get_font',
    'compute_alienation_4d',
    'draw_alienation_radar',
    'draw_electoral_barometer',
]

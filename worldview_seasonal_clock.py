"""
worldview_seasonal_clock.py — Seasonal & dual game clock UI.

Backward-compatible facade re-exporting from client.desktop.seasonal_clock.
"""

from __future__ import annotations

import client.desktop.seasonal_clock as _impl
from client.desktop.seasonal_clock import (
    SEASON_CLOCK_RECT,
    SEASON_METADATA,
    get_season_info,
    draw_seasonal_clock,
    draw_seasonal_clock_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'SEASON_CLOCK_RECT',
    'SEASON_METADATA',
    'get_season_info',
    'draw_seasonal_clock',
    'draw_seasonal_clock_tooltip',
]

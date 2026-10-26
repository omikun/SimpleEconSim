"""
worldview_vis_pyramid.py — Class wealth pyramid & Lorenz curve visualizer.

Backward-compatible facade re-exporting from client.desktop.inspect.vis_pyramid.
"""

from __future__ import annotations

import client.desktop.inspect.vis_pyramid as _impl
from client.desktop.inspect.vis_pyramid import (
    CARD_BG,
    CARD_BORDER,
    COL_APEX,
    COL_MID,
    COL_BASE,
    COL_SUBBASE,
    _get_font,
    _collect_agents_and_classes,
    draw_class_wealth_pyramid,
    draw_lorenz_curve,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_BG',
    'CARD_BORDER',
    'COL_APEX',
    'COL_MID',
    'COL_BASE',
    'COL_SUBBASE',
    '_get_font',
    '_collect_agents_and_classes',
    'draw_class_wealth_pyramid',
    'draw_lorenz_curve',
]

"""
worldview_layers.py — Map info layer drop-up dock.

Backward-compatible facade re-exporting from client.desktop.map.layers.
"""

from __future__ import annotations

import client.desktop.map.layers as _impl
from client.desktop.map.layers import (
    SIDEBAR_X,
    SIDEBAR_W,
    BTN_H,
    BTN_SPACING,
    MAP_LAYERS,
    DOCK_H,
    PILL_H,
    PILL_Y,
    DOCK_Y,
    SIDEBAR_Y,
    draw_layer_sidebar,
    layer_sidebar_hit,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'SIDEBAR_X',
    'SIDEBAR_W',
    'BTN_H',
    'BTN_SPACING',
    'MAP_LAYERS',
    'DOCK_H',
    'PILL_H',
    'PILL_Y',
    'DOCK_Y',
    'SIDEBAR_Y',
    'draw_layer_sidebar',
    'layer_sidebar_hit',
]

"""
worldview_vis_protest_attractor.py — Rebellion attractor 2D phase-space visualizer.

Backward-compatible facade re-exporting from client.desktop.inspect.vis_protest_attractor.
"""

from __future__ import annotations

import client.desktop.inspect.vis_protest_attractor as _impl
from client.desktop.inspect.vis_protest_attractor import (
    CARD_BG,
    CARD_BORDER,
    HAZARD_BG,
    HAZARD_BORDER,
    _get_font,
    draw_rebellion_attractor_phasespace,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_BG',
    'CARD_BORDER',
    'HAZARD_BG',
    'HAZARD_BORDER',
    '_get_font',
    'draw_rebellion_attractor_phasespace',
]

"""
worldview_vis_circuits.py — Circuit of capital Sankey & TRPF visualizer.

Backward-compatible facade re-exporting from client.desktop.inspect.vis_circuits.
"""

from __future__ import annotations

import client.desktop.inspect.vis_circuits as _impl
from client.desktop.inspect.vis_circuits import (
    COL_M,
    COL_C,
    COL_V,
    COL_P,
    COL_S,
    COL_RENT,
    COL_VICE,
    COL_ENT,
    COL_BACKLASH,
    CARD_BG,
    CARD_BORDER,
    _get_font,
    _draw_flow_ribbon,
    draw_circuit_of_capital_sankey,
    circuit_sankey_hit,
    draw_trpf_curve,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'COL_M',
    'COL_C',
    'COL_V',
    'COL_P',
    'COL_S',
    'COL_RENT',
    'COL_VICE',
    'COL_ENT',
    'COL_BACKLASH',
    'CARD_BG',
    'CARD_BORDER',
    '_get_font',
    '_draw_flow_ribbon',
    'draw_circuit_of_capital_sankey',
    'circuit_sankey_hit',
    'draw_trpf_curve',
]

"""
hexview.py — Pygame hex-map viewer for 2x3 layout.

Backward-compatible facade re-exporting from terrain.hex.hexview.
"""

from __future__ import annotations

import terrain.hex.hexview as _impl
from terrain.hex.hexview import (
    WIDTH,
    HEIGHT,
    MAP_RIGHT,
    PANEL_LEFT,
    HEX_SIZE,
    FPS_PLAYING,
    FPS_IDLE,
    FPS,
    TURN_MS,
    TOP_BAR_H,
    BG,
    _OFFSET_X,
    _OFFSET_Y,
    REVERSE_LAYOUT,
    ELECTION_C,
    COUP_C,
    _hex_px,
    _tile_at,
    build_world_view,
    step_world,
    _draw_top_bar,
    _draw_hex_map,
    _draw_panel,
    render_frame,
    main,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'WIDTH',
    'HEIGHT',
    'MAP_RIGHT',
    'PANEL_LEFT',
    'HEX_SIZE',
    'FPS_PLAYING',
    'FPS_IDLE',
    'FPS',
    'TURN_MS',
    'TOP_BAR_H',
    'BG',
    '_OFFSET_X',
    '_OFFSET_Y',
    'REVERSE_LAYOUT',
    'ELECTION_C',
    'COUP_C',
    '_hex_px',
    '_tile_at',
    'build_world_view',
    'step_world',
    '_draw_top_bar',
    '_draw_hex_map',
    '_draw_panel',
    'render_frame',
    'main',
]

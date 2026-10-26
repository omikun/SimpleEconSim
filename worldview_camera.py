"""
worldview_camera.py — Camera & coordinate projection.

Backward-compatible facade re-exporting from client.desktop.camera.
"""

from __future__ import annotations

import client.desktop.camera as _impl
from client.desktop.camera import (
    HEX_SIZE,
    WIDTH,
    HEIGHT,
    MAP_RIGHT,
    TOP_BAR_H,
    TICKER_H,
    _MARGIN,
    MAP_PAD_RATIO,
    get_map_bounds,
    get_min_zoom,
    _cam_mvp_cache,
    compute_pitch_yaw,
    get_camera_mvp,
    project_pts_3d_to_screen,
    project_polygon_3d_to_screen,
    world_to_screen,
    screen_to_world,
    clamp_cam,
    zoom_cam_at,
    reset_cam,
    hex_px,
    tile_at,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'HEX_SIZE',
    'WIDTH',
    'HEIGHT',
    'MAP_RIGHT',
    'TOP_BAR_H',
    'TICKER_H',
    '_MARGIN',
    'MAP_PAD_RATIO',
    'get_map_bounds',
    'get_min_zoom',
    '_cam_mvp_cache',
    'compute_pitch_yaw',
    'get_camera_mvp',
    'project_pts_3d_to_screen',
    'project_polygon_3d_to_screen',
    'world_to_screen',
    'screen_to_world',
    'clamp_cam',
    'zoom_cam_at',
    'reset_cam',
    'hex_px',
    'tile_at',
]

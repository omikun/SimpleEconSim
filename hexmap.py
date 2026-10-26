"""
hexmap.py — Axial hex geometry and pointy-top honeycomb layout.

Backward-compatible facade re-exporting from terrain.hex.hexmap.
"""

from __future__ import annotations

import terrain.hex.hexmap as _impl
from terrain.hex.hexmap import (
    _SQRT3,
    LAYOUT_2X3,
    axial_to_pixel,
    hex_corners,
    _axial_round,
    pixel_to_axial,
    hex_distance,
    adjacent,
    edge_list_from_tiles,
    assert_edges_are_hex_adjacent,
    HEX_DIRS,
    offset_to_axial,
    axial_to_offset,
    rectangular_hex_layout,
    axial_neighbors,
    hex_bbox,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    '_SQRT3',
    'LAYOUT_2X3',
    'axial_to_pixel',
    'hex_corners',
    '_axial_round',
    'pixel_to_axial',
    'hex_distance',
    'adjacent',
    'edge_list_from_tiles',
    'assert_edges_are_hex_adjacent',
    'HEX_DIRS',
    'offset_to_axial',
    'axial_to_offset',
    'rectangular_hex_layout',
    'axial_neighbors',
    'hex_bbox',
]

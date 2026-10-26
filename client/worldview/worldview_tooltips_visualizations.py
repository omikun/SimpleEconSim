"""
worldview_tooltips_visualizations.py — Specialized visualization tooltip providers.

Backward-compatible facade re-exporting from client.desktop.tooltips.visualizations.
"""

from __future__ import annotations

import client.desktop.tooltips.visualizations as _impl
from client.desktop.tooltips.visualizations import (
    _tip_extraction_controls,
    _tip_protest_controls,
    _tip_citizens_panel,
    _tip_labor_panel,
    _tip_electoral_barometer,
    _tip_map_layers,
    _tip_radar_axes,
    _tip_phase3_ecology,
    build_visualization_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    '_tip_extraction_controls',
    '_tip_protest_controls',
    '_tip_citizens_panel',
    '_tip_labor_panel',
    '_tip_electoral_barometer',
    '_tip_map_layers',
    '_tip_radar_axes',
    '_tip_phase3_ecology',
    'build_visualization_tooltip',
]

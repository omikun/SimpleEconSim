"""
worldview_tooltips.py — Core tooltip system.

Backward-compatible facade re-exporting from client.desktop.tooltips.core.
"""

from __future__ import annotations

import client.desktop.tooltips.core as _impl
from client.desktop.tooltips.core import (
    CARD_MAX_W,
    PADDING_X,
    PADDING_Y,
    wrap_text,
    _tip_city_scope,
    _tip_cadastre_scope,
    _tip_progress_ui,
    _tip_province_scope,
    _tip_nation_scope,
    _tip_frontier_scope,
    _tip_building_recipe,
    _tip_build_subcategory,
    _tip_tier_headers,
    _tip_dock_tabs,
    _build_button_tooltip_raw,
    _infer_icon_for_btn,
    get_button_tooltip_data,
    draw_left_panel_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'CARD_MAX_W',
    'PADDING_X',
    'PADDING_Y',
    'wrap_text',
    '_tip_city_scope',
    '_tip_cadastre_scope',
    '_tip_progress_ui',
    '_tip_province_scope',
    '_tip_nation_scope',
    '_tip_frontier_scope',
    '_tip_building_recipe',
    '_tip_build_subcategory',
    '_tip_tier_headers',
    '_tip_dock_tabs',
    '_build_button_tooltip_raw',
    '_infer_icon_for_btn',
    'get_button_tooltip_data',
    'draw_left_panel_tooltip',
]

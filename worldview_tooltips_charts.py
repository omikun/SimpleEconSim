"""
worldview_tooltips_charts.py — Chart & citizen tooltip providers.

Backward-compatible facade re-exporting from client.desktop.tooltips.charts.
"""

from __future__ import annotations

import client.desktop.tooltips.charts as _impl
from client.desktop.tooltips.charts import (
    build_sidebar_chart_tooltip,
    build_citizen_tooltip,
    build_labor_tooltip,
    build_compare_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'build_sidebar_chart_tooltip',
    'build_citizen_tooltip',
    'build_labor_tooltip',
    'build_compare_tooltip',
]

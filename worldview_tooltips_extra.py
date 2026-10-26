"""
worldview_tooltips_extra.py — Extended tooltip providers for drawers.

Backward-compatible facade re-exporting from client.desktop.tooltips.extra.
"""

from __future__ import annotations

import client.desktop.tooltips.extra as _impl
from client.desktop.tooltips.extra import (
    build_science_resource_tooltip,
    build_science_tech_tooltip,
    build_diplomacy_tooltip,
    build_debt_tooltip,
    build_military_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'build_science_resource_tooltip',
    'build_science_tech_tooltip',
    'build_diplomacy_tooltip',
    'build_debt_tooltip',
    'build_military_tooltip',
]

"""
worldview_tooltips_ecology.py — Ecology & public health tooltip providers.

Backward-compatible facade re-exporting from client.desktop.tooltips.ecology.
"""

from __future__ import annotations

import client.desktop.tooltips.ecology as _impl
from client.desktop.tooltips.ecology import (
    build_ecology_tooltip,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'build_ecology_tooltip',
]

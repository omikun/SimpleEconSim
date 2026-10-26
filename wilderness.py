"""
wilderness.py — Unclaimed-tile mechanics for the Call of Capital tile game.

Backward-compatible facade re-exporting from terrain.wilderness.wilderness.
"""

from __future__ import annotations

import terrain.wilderness.wilderness as _impl
from terrain.wilderness.wilderness import (
    FORAGE_INTERVAL,
    enter_wilderness,
    enter_claimed,
    forage,
    _GOODS_TRADE,
    _align_logs,
    step_wilderness,
)

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})

__all__ = [
    'FORAGE_INTERVAL',
    'enter_wilderness',
    'enter_claimed',
    'forage',
    '_GOODS_TRADE',
    '_align_logs',
    'step_wilderness',
]

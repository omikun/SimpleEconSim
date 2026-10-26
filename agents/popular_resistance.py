"""
popular_resistance.py — Popular resistance manager, commune declaration, and anti-enclosure revolts.

Facade module re-exporting from agents.resistance.
"""

from agents.resistance.models import (
    AssassinationPlot,
    RebellionConfig,
    ResistanceState,
)
from agents.resistance.manager import (
    PopularResistanceManager,
    get_popular_resistance_manager,
    reset_popular_resistance_manager,
    _safe_ticker_push,
)

__all__ = [
    'AssassinationPlot',
    'RebellionConfig',
    'ResistanceState',
    'PopularResistanceManager',
    'get_popular_resistance_manager',
    'reset_popular_resistance_manager',
    '_safe_ticker_push',
]

"""
micro package — Tile-level microeconomics, labor, production, markets, and regional stepping.
"""

from __future__ import annotations

from micro.region import (
    Region,
    DEFAULT_PROFESSION_DISTRIBUTION,
    MAX_AGENTS,
    count_agents,
    compute_gini,
    get_total_cash,
    step_economy,
)

__all__ = [
    "Region",
    "DEFAULT_PROFESSION_DISTRIBUTION",
    "MAX_AGENTS",
    "count_agents",
    "compute_gini",
    "get_total_cash",
    "step_economy",
]

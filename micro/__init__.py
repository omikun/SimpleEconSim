"""
micro package — Tile-level microeconomics, labor, production, markets, and regional stepping.
"""

from __future__ import annotations

import importlib as _importlib

from micro.region import (
    DEFAULT_PROFESSION_DISTRIBUTION,
    MAX_AGENTS,
    Region,
    audit_cash,
    compute_gini,
    count_agents,
    get_total_cash,
    step_economy,
)

_SUBMODULES = {
    "buildings": "buildings",
    "crop_credit": "crop_credit",
    "disease": "disease",
    "foraging": "foraging",
    "land_rent": "land_rent",
    "land_tenure": "land_tenure",
    "nutrition": "nutrition",
    "region_factions": "region_factions",
    "region_finance": "region_finance",
    "region_labor": "region_labor",
    "region_market": "region_market",
    "region_production": "region_production",
    "workhouse": "workhouse",
}


def __getattr__(name: str):
    if name in _SUBMODULES:
        return _importlib.import_module(_SUBMODULES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Region",
    "DEFAULT_PROFESSION_DISTRIBUTION",
    "MAX_AGENTS",
    "count_agents",
    "compute_gini",
    "get_total_cash",
    "step_economy",
    "audit_cash",
    *list(_SUBMODULES.keys()),
]

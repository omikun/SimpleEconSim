"""
micro/region package — Modular Region definition and stepping engine.
"""

from __future__ import annotations
from micro.region.helpers import (
    DEFAULT_PROFESSION_DISTRIBUTION,
    MAX_AGENTS,
    count_agents,
    compute_gini,
    get_total_cash,
)
from micro.region.core import Region
from micro.region.stepper import (
    step_economy,
    audit_cash,
    record_start,
    record_delta,
    total_cash,
    live,
    log_gdp,
    log_metrics,
    log_population_rate,
)

__all__ = [
    "DEFAULT_PROFESSION_DISTRIBUTION",
    "MAX_AGENTS",
    "count_agents",
    "compute_gini",
    "get_total_cash",
    "Region",
    "step_economy",
    "audit_cash",
    "record_start",
    "record_delta",
    "total_cash",
    "live",
    "log_gdp",
    "log_metrics",
    "log_population_rate",
]

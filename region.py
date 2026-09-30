"""
region.py — Backward-compatible facade for micro.region.
"""

from __future__ import annotations

from micro.region import (
    DEFAULT_PROFESSION_DISTRIBUTION,
    MAX_AGENTS,
    count_agents,
    compute_gini,
    get_total_cash,
    Region,
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

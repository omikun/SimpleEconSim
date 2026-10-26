"""
trace package — Causal trace recording, O(1) indexed querying, coverage verification,
and metric catalog definitions.
"""

from __future__ import annotations

from causal_contracts import CONTRACTS, verify_contract
from causal_gap_inventory import discover_financial_writes, inventory_summary
from desktop_trace_session import DesktopTraceSession
from metric_catalog import (
    LEGACY_HISTORY_TO_METRIC,
    METRICS,
    TRACE_INSTRUMENTED,
    inventory_region_histories,
)
from run_trace import RunTrace, verify
from trace_audit import audit
from trace_coverage import coverage
from trace_explanation import explain_metric
from trace_index import TraceIndex

__all__ = [
    "RunTrace",
    "verify",
    "TraceIndex",
    "DesktopTraceSession",
    "METRICS",
    "TRACE_INSTRUMENTED",
    "LEGACY_HISTORY_TO_METRIC",
    "inventory_region_histories",
    "CONTRACTS",
    "verify_contract",
    "discover_financial_writes",
    "inventory_summary",
    "audit",
    "coverage",
    "explain_metric",
]

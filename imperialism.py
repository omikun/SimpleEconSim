"""
imperialism.py — Backward-compatible facade for macro.imperialism.
"""

from __future__ import annotations

from macro.imperialism import (
    ThreatAssessment,
    CustomsReceivership,
    UnequalTreaty,
    CorePeripheryScore,
    ImperialismManager,
    get_imperialism_manager,
    evaluate_credible_takeover_threat,
    _disburse_agent_funds,
)

__all__ = [
    "ThreatAssessment",
    "CustomsReceivership",
    "UnequalTreaty",
    "CorePeripheryScore",
    "ImperialismManager",
    "get_imperialism_manager",
    "evaluate_credible_takeover_threat",
    "_disburse_agent_funds",
]

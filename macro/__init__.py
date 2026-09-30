"""
macro package — National governance, diplomacy, military, geopolitics, and imperialism.
"""

from __future__ import annotations

# Re-export key modules and classes
from macro.imperialism import (
    ThreatAssessment,
    CustomsReceivership,
    UnequalTreaty,
    CorePeripheryScore,
    ImperialismManager,
    get_imperialism_manager,
    evaluate_credible_takeover_threat,
)

__all__ = [
    "ThreatAssessment",
    "CustomsReceivership",
    "UnequalTreaty",
    "CorePeripheryScore",
    "ImperialismManager",
    "get_imperialism_manager",
    "evaluate_credible_takeover_threat",
]

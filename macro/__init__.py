"""
macro package — National governance, diplomacy, military, geopolitics, and imperialism.
"""

from __future__ import annotations

import importlib as _importlib

from macro.imperialism import (
    CorePeripheryScore,
    CustomsReceivership,
    ImperialismManager,
    ThreatAssessment,
    UnequalTreaty,
    evaluate_credible_takeover_threat,
    get_imperialism_manager,
)

_SUBMODULES = {
    "ai_nation": "ai_nation",
    "army": "army",
    "banking_policy": "banking_policy",
    "coup": "coup",
    "diplomacy": "diplomacy",
    "election": "election",
    "government": "government",
    "innovation": "innovation",
    "nation": "nation",
    "regime": "regime",
    "sovereign_bonds": "sovereign_bonds",
}


def __getattr__(name: str):
    if name in _SUBMODULES:
        return _importlib.import_module(_SUBMODULES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ThreatAssessment",
    "CustomsReceivership",
    "UnequalTreaty",
    "CorePeripheryScore",
    "ImperialismManager",
    "get_imperialism_manager",
    "evaluate_credible_takeover_threat",
    *list(_SUBMODULES.keys()),
]

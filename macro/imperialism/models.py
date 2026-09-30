"""
macro/imperialism/models.py — Data models for financial imperialism and debt enforcement.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class ThreatAssessment:
    """Calculus of military force, projection logistics, and takeover credibility."""
    creditor_name: str
    debtor_name: str
    creditor_force: float          # Combined combat strength of standing units + enforcers
    debtor_force: float            # Combined combat strength of debtor army + garrisons + militias
    force_ratio: float             # creditor_force / max(1.0, debtor_force)
    expeditionary_cost: float      # Estimated maintenance/transit cost per turn
    debt_amount: float             # Defaulted debt to collect
    logistics_viable: bool         # Creditor can afford projection and cost is rational
    resistance_deterrence: float   # Unrest & popular insurgency friction
    credibility_score: float       # S_cred: continuous credibility metric
    tier: str                      # 'Overwhelming Hegemony' | 'Credible Threat' | 'Contested / Risky' | 'Hollow Bluff'
    reason: str                    # Summary explanation


@dataclass
class CustomsReceivership:
    """An imperial customs receivership intercepting debtor state revenues."""
    receivership_id: str
    creditor_nation: str
    debtor_nation: str
    intercept_share: float = 0.40       # 40% of tariffs and taxes diverted (65% in Caisse)
    remaining_debt: float = 500.0       # Outstanding debt balance to collect
    total_collected: float = 0.0        # Cumulative diverted funds
    start_turn: int = 0
    status: str = "active"              # 'active' | 'cleared' | 'expelled' | 'suspended'
    enforcement_mode: str = "military"  # 'military' | 'hired_agents'
    agent_retainer_cost: float = 2.0    # per turn cost to maintain hired agents
    agents_hired: int = 1
    level: str = "customs"              # 'customs' | 'caisse_de_la_dette'
    turns_active: int = 0
    seized_tolls: float = 0.0           # Cumulative toll revenue seized from routes
    seized_granary_grain: float = 0.0   # Cumulative physical grain seized from granaries
    seized_royalties: float = 0.0       # Cumulative resource/timber/nitrate royalties seized
    creditor_obj: Optional[Any] = None


@dataclass
class UnequalTreaty:
    """Coerced treaty granting imperial concessions in exchange for debt relief."""
    treaty_id: str
    imperial_nation: str
    subject_nation: str
    treaty_type: str                    # 'tariff_exemption' | 'resource_concession'
    concession_tile: Optional[str] = None
    profit_repatriation_share: float = 0.50
    signed_turn: int = 0
    status: str = "active"              # 'active' | 'repudiated'


@dataclass
class CorePeripheryScore:
    """Structural economic standing of a sovereign nation."""
    nation_name: str
    external_debt_ratio: float          # foreign debt / treasury
    net_creditor_balance: float         # foreign bonds held - foreign bonds owed
    terms_of_trade_ratio: float         # manufactured exports / primary exports
    composite_index: float              # -1.0 (Periphery) to +1.0 (Imperial Core)
    tier: str                           # 'Imperial Core' | 'Semi-Periphery' | 'Indebted Periphery'

"""
agents package — Individual agent entities, labor relations, social classes, and popular resistance.
"""

from __future__ import annotations

from agent import Agent, initialize_agent, seed_traits
from agents.resistance import (
    AssassinationPlot,
    RebellionConfig,
    ResistanceState,
    PopularResistanceManager,
    get_popular_resistance_manager,
)

__all__ = [
    "Agent",
    "initialize_agent",
    "seed_traits",
    "AssassinationPlot",
    "RebellionConfig",
    "ResistanceState",
    "PopularResistanceManager",
    "get_popular_resistance_manager",
]

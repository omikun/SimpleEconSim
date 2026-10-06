"""Base interface for scenario dynamic modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseDynamicModule(ABC):
    """Abstract base class for reusable simulation dynamics modules."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        """Called once when scenario initializes to seed bonds, units, or state."""
        pass

    @abstractmethod
    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        """Called each turn to run module physics (e.g. debt intercept, fleet movement)."""
        pass

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return key diagnostic metrics for debrief or status display."""
        return {}

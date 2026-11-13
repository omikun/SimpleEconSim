"""Transient state for a single ordered elite decision, not a persisted plan."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EliteDecision:
    agent: Any
    region: Any
    turn: int
    shadow_cash: float
    luxuries: list
    result: dict = field(init=False)
    trace_enabled: bool = field(init=False)

    def __post_init__(self):
        self.trace_enabled = (getattr(self.region, '_run_trace', None) is not None
                              and getattr(self.region, '_collective_trace_clock', None) is not None)
        self.result = {
            'agent_id': self.agent.id, 'is_lord': getattr(self.agent, 'is_lord', False),
            'shadow_price_cash': self.shadow_cash, 'action_taken': None, 'details': {},
            'evaluation_event_ids': [], 'execution_event_ids': [],
        }

    def accept(self, outcome):
        if outcome is not None:
            for key in ('evaluation_event_ids', 'execution_event_ids'):
                self.result[key].extend(outcome.get(key, []))
        if not outcome or not outcome.get('action_taken'):
            return False
        self.result['action_taken'] = outcome['action_taken']
        self.result['details'] = outcome['details']
        return True

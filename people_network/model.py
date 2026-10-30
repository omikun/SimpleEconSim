"""JSON-owned session state and compact, time-ordered causal records."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json

VERSION = 2
CHANNELS = ('player', 'rival', 'upstream', 'market')
CANDIDATES = ('player', 'rival')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def state_digest(state):
    return digest({k: v for k, v in state.items() if k != 'event_sequence'})


@dataclass
class Session:
    state: dict
    initial: dict
    events: list = field(default_factory=list)
    history: list = field(default_factory=list)
    journal: list = field(default_factory=list)
    tracing: bool = True
    decision_start: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.decision_start:
            self.decision_start = deepcopy(self.state)

    def emit(self, kind, subject, before=None, after=None, parents=(), **details):
        self.state['event_sequence'] += 1
        eid = f"e{self.state['event_sequence']:06d}"
        if not self.tracing:
            return eid
        record = dict(id=eid, round=self.state['round'], kind=kind, subject=subject,
                      before=deepcopy(before), after=deepcopy(after),
                      parents=list(dict.fromkeys(p for p in parents if p)), **deepcopy(details))
        if self.tracing:
            self.events.append(record)
        return eid

    def payload(self):
        return dict(version=self.state['version'], state=self.state, initial=self.initial,
                    events=self.events, history=self.history, journal=self.journal,
                    tracing=self.tracing, decision_start=self.decision_start)

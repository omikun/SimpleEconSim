#!/usr/bin/env python3
"""
faction.py — Factions for the REGNUM tile game (M2.1).

Pure state module: a Faction is a named interest group with overlapping
agent membership (one agent can belong to many factions), ranked policy
demands, deterministic grievance tracking, and a support measure.

This module MUST NOT import from econsim / region / government — it is a
leaf-level data structure that sim tiles and the viewer both consume.
Conservation note: factions hold no money or goods; they only aggregate
agent state, so nothing is created or destroyed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


#: Faction kinds (gdd.md §6).
KINDS = {"ethnicity", "religion", "political", "class", "regional"}

#: Core economic-identity faction templates derived from M1 identity tags.
#: kind, name, and the tag whose value it matches (None = all).
IDENTITY_TEMPLATES = (
    ("ethnicity", "Yor", "ethnicity"),
    ("ethnicity", "Kest", "ethnicity"),
    ("ethnicity", "Veln", "ethnicity"),
    ("ethnicity", "Omar", "ethnicity"),
    ("religion", "Sol", "religion"),
    ("religion", "Luna", "religion"),
    ("religion", "Terra", "religion"),
    ("political", "Conservative", "politics"),
    ("political", "Liberal", "politics"),
    ("political", "Populist", "politics"),
)


@dataclass
class Demand:
    """A ranked policy demand the faction cares about.

    Fields
    ------
    name : str
        Policy key ('tax_cut', 'welfare', 'tariff', 'native_rights',
        'immigration', etc.).
    weight : float
        Relative importance to this faction (higher = more strongly felt).
    satisfied : float
        0..1 — how much the demand is currently met by the regime.
    """

    name: str
    weight: float = 1.0
    satisfied: float = 0.0


@dataclass
class Faction:
    """A named interest group.

    Attributes
    ----------
    name : str
        Unique faction identifier (e.g. 'Sol', 'Kest', 'Liberal').
    kind : str
        One of KINDS.
    membership : set[int]
        Agent ids belonging to this faction (overlapping allowed).
    demands : list[Demand]
        Ranked policy demands.
    grievances : dict[str, float]
        Accumulated grievance sources -> magnitude ('.hunger', '.tax',
        '.gini', '.unemployment', '.repression', '.broken_promises').
    influence : float
        Influence in government / society (0..1).
    support : float
        Support fraction among eligible agents (0..1), computed live.
    """

    name: str
    kind: str
    membership: set = field(default_factory=set)
    demands: list = field(default_factory=list)
    grievances: dict = field(default_factory=dict)
    influence: float = 0.1
    support: float = 0.0

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"bad faction kind: {self.kind!r}")

    # ------------------------------------------------------------------
    # Membership (overlapping — one agent may belong to many factions)
    # ------------------------------------------------------------------

    def add_member(self, agent):
        """Add *agent* to this faction's membership by id."""
        self.membership.add(agent.id)

    def remove_member(self, agent):
        """Remove *agent* from this faction (idempotent)."""
        self.membership.discard(agent.id)

    def has_member(self, agent):
        """True if *agent* is a member."""
        return agent.id in self.membership

    # ------------------------------------------------------------------
    # Demands
    # ------------------------------------------------------------------

    def add_demand(self, name, weight=1.0, satisfied=0.0):
        """Append or replace a demand of *name*."""
        for d in self.demands:
            if d.name == name:
                d.weight = weight
                d.satisfied = satisfied
                return
        self.demands.append(Demand(name, weight, satisfied))

    def set_satisfied(self, name, satisfied):
        """Set satisfaction (0..1) of a demand."""
        for d in self.demands:
            if d.name == name:
                d.satisfied = max(0.0, min(1.0, satisfied))
                return

    # ------------------------------------------------------------------
    # Grievances (accumulated, source-keyed)
    # ------------------------------------------------------------------

    def add_grievance(self, source, amount):
        """Accumulate *amount* (≥0) under *source*."""
        if amount <= 0:
            return
        self.grievances[source] = self.grievances.get(source, 0.0) + amount

    def total_grievance(self):
        """Weighted total grievance (0..∞, interpreted by the unrest layer)."""
        return max(0.0, sum(self.grievances.values()))

    def decay_grievances(self, factor=0.95):
        """Fade all grievances each turn (memory-like decay)."""
        for k in list(self.grievances):
            nv = self.grievances[k] * factor
            if nv < 1e-4:
                del self.grievances[k]
            else:
                self.grievances[k] = nv

    # ------------------------------------------------------------------
    # Support (live, from demand satisfaction + grievances)
    # ------------------------------------------------------------------

    def compute_support(self, eligible_ids):
        """Support = membership in *eligible_ids* weighted by demand
        satisfaction minus grievance drag.

        Returns a float in [0, 1]: the fraction of *eligible_ids* who are
        members, tempered by (1 - unweighted demand satisfaction) so that a
        faction whose demands are met holds ~1.0 support while a fully
        unsatisfied faction degrades toward 0.
        """
        if not eligible_ids:
            return 0.0
        members = [aid for aid in self.membership if aid in eligible_ids]
        if not members:
            return 0.0
        base = len(members) / len(eligible_ids)
        total_w = sum(d.weight for d in self.demands) or 1.0
        sat = sum(d.weight * d.satisfied for d in self.demands) / total_w
        # Grievance drag: each point of normalized grievance shaves 3% off.
        drag = min(1.0, 0.03 * max(0.0, self.total_grievance()))
        self.support = max(0.0, min(1.0, base * (0.2 + 0.8 * sat) * (1 - drag)))
        return self.support

    # ------------------------------------------------------------------

    def __repr__(self):
        return (f"Faction({self.name!r}, kind={self.kind!r}, "
                f"members={len(self.membership)}, "
                f"grievance={self.total_grievance():.2f}, "
                f"support={self.support:.2f})")


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def faction_for_identity(kind, tag):
    """Return an identity-derived Faction template.

    Used to auto-create factions from M1 identity tags (SOL/Luna/Terra,
    ethnic groups, political ideologies) so every tile gets a lively
    faction mix without manual wiring.
    """
    return Faction(name=tag.capitalize(), kind=kind)


class FactionSystem:
    """Tracks a set of factions for one tile (or nation).

    The tile steps it each turn:
      - compute_support from its eligible agent ids
      - decay grievances
    """

    def __init__(self):
        self.factions = {}

    def register(self, faction):
        """Add a faction (by name) if not already present."""
        self.factions.setdefault(faction.name, faction)
        return self.factions[faction.name]

    def get(self, name):
        return self.factions.get(name)

    def step(self, eligible_ids):
        """One turn: refresh support and decay grievances for all factions."""
        for f in self.factions.values():
            f.compute_support(eligible_ids)
            f.decay_grievances()

    def overlaps(self):
        """Return a list of (agent_id, [faction names]) for agents in 2+."""
        from collections import defaultdict
        by_agent = defaultdict(list)
        for f in self.factions.values():
            for aid in f.membership:
                by_agent[aid].append(f.name)
        return [(aid, names) for aid, names in by_agent.items() if len(names) > 1]
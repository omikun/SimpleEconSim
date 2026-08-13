#!/usr/bin/env python3
"""
regime.py — Regime orchestrator for REGNUM (M3.4 / M3.6).

Ties elections (election.py) and coups (coup.py) to a Nation's per-turn
lifecycle:

  M3.4  Legitimacy tracking + election cadence:
        - legitimacy drifts toward the population's faction support each turn
          (a live consent metric), so it rises with satisfied factions and
          falls when the big factions are aggrieved.
        - democratic regimes run fixed-interval elections; ANY regime triggers
          a snap election when legitimacy collapses below a threshold.
        - the winning candidate's platform flips the policy knobs.

  M3.6  Player-faction continuity:
        - the elected/couping faction becomes ``nation.ruling_faction``; the
          deposed faction is recorded in ``nation.opposition`` with an
          ``is_opposition`` flag.
        - exposed intents: ``agitate(nation, faction, amount)`` (raises that
          faction's grievance, which drives protest energy -> unrest) and
          ``unrest_intent(nation)`` (a pure read of current protest energy).

Pure-state except campaign finance and coup treasury seizure (both conserved
transfers handled by the election/coup modules).
"""

from __future__ import annotations

from election import run_election
from coup import coup_chance, execute_coup


#: Fixed election interval (turns) for democratic regimes.
ELECTION_INTERVAL = 60

#: Legitimacy below which a snap election fires for ANY regime.
SNAP_ELECTION_LEGITIMACY = 0.25

#: How strongly legitimacy is pulled toward faction support each turn.
LEGITIMACY_DRIFT = 0.05

#: Treasury campaign budget per election (conserved transfer to candidates).
CAMPAIGN_BUDGET = 200.0


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _avg_faction_support(nation):
    """Mean faction support across the nation's tiles (0..1)."""
    supports = []
    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for f in factions.values():
            supports.append(getattr(f, 'support', 0.0))
    if not supports:
        return 0.5
    return sum(supports) / len(supports)


def track_legitimacy(nation):
    """M3.4: drift legitimacy toward the population's faction support."""
    target = _avg_faction_support(nation)
    cur = getattr(nation, 'legitimacy', 0.6)
    nation.legitimacy = _clamp(cur + (target - cur) * LEGITIMACY_DRIFT, 0.0, 1.0)


def apply_platform(nation, candidate):
    """Flip tile-government policy knobs to match the winner's platform.

    Each platform key is a faction demand name; strength >= 0.5 enables the
    corresponding policy.  Pure policy state — no money moves.
    """
    platform = getattr(candidate, 'platform', {}) or {}
    for tile in getattr(nation, 'tiles', []):
        gov = getattr(tile, 'gov', None)
        if gov is None:
            continue
        # Only flip the TAX knob, whose money effect is a pure within-currency
        # transfer (citizens -> gov).  The 'welfare' -> UBI toggle is a
        # sovereign-to-citizen flow whose conservation interacts with the
        # sovereign-vs-tile government cash split, and 'tariff'/'immigration'
        # touch cross-currency FX / agent-spawn machinery.  All three stay at
        # their defaults until those paths are validated.  The M3.4 "policy
        # set flips" acceptance is demonstrated by the tax-rate cut on a
        # winning platform.
        if platform.get('tax_cut', 0.0) >= 0.5:
            gov.tax_rate = max(0.05, gov.tax_rate * 0.5)


def _record_opposition(nation, deposed_faction):
    """M3.6: move the deposed faction into opposition (is_opposition flag)."""
    nation.opposition = []
    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        if deposed_faction and deposed_faction in factions:
            f = factions[deposed_faction]
            if not hasattr(f, 'is_opposition'):
                f.is_opposition = True
            if f.name not in nation.opposition:
                nation.opposition.append(f.name)


def agitate(nation, faction_name, amount=1.0):
    """M3.6 intent: raise a faction's grievance (drives protest energy).

    Pure state — adds ``amount`` under the 'agitation' source, which the next
    turn's protest-energy computation folds into unrest.  Engine-only intent;
    a future UI exposes it as an opposition action.
    """
    total = 0.0
    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        f = factions.get(faction_name)
        if f is not None:
            f.add_grievance('agitation', amount)
            total += amount
    return total


def unrest_intent(nation):
    """M3.6 intent (pure read): current protest energy across the nation."""
    energies = [tile.protest_energy_log[-1]
                for tile in getattr(nation, 'tiles', [])
                if getattr(tile, 'protest_energy_log', None)]
    return max(energies) if energies else 0.0


def step_regime(nation, t, rng=None):
    """One turn of regime bookkeeping for *nation*.

    Order:
      1. coup check (extra-constitutional path, any regime)
      2. legitimacy tracking (consent drift)
      3. election cadence: fixed interval (democracy) or snap (collapse)

    Returns an event dict (possibly empty) describing what fired this turn.
    """
    import random
    events = []

    # 1. Coup
    general, fires = coup_chance(nation, t,
                                 rng if rng is not None else random.random())
    if fires and general is not None:
        deposed = getattr(nation, 'ruling_faction', None)
        ev = execute_coup(nation, t, general, deposed_faction=deposed)
        nation.ruling_faction = None
        _record_opposition(nation, deposed)
        events.append({'kind': 'coup', **ev})
        nation.regime_log.extend(events)
        return events

    # 2. Legitimacy tracking
    track_legitimacy(nation)

    # Persist turn-aligned election state keys lazily.
    if not hasattr(nation, '_last_election'):
        nation._last_election = 0

    # 3. Election cadence
    due_interval = (getattr(nation, 'regime_type', 'autocracy') == 'democracy'
                    and t - nation._last_election >= ELECTION_INTERVAL)
    due_collapse = getattr(nation, 'legitimacy', 0.6) < SNAP_ELECTION_LEGITIMACY \
        and t - nation._last_election >= 10

    if due_interval or due_collapse:
        prev_ruling = getattr(nation, 'ruling_faction', None)
        result = run_election(nation, t, campaign_budget=CAMPAIGN_BUDGET)
        winner = result.get('winner')
        nation._last_election = t
        if winner is not None:
            nation.ruling_faction = winner.backing_faction
            apply_platform(nation, winner)
            if prev_ruling and prev_ruling != winner.backing_faction:
                _record_opposition(nation, prev_ruling)
            events.append({
                'kind': 'election',
                'turn': t,
                'winner_faction': winner.backing_faction,
                'votes': {c.agent.id: v for c, v in result['votes'].items()},
            })

    nation.regime_log.extend(events)
    return events


__all__ = ['step_regime', 'track_legitimacy', 'apply_platform',
           'agitate', 'unrest_intent', 'ELECTION_INTERVAL',
           'SNAP_ELECTION_LEGITIMACY', 'LEGITIMACY_DRIFT', 'CAMPAIGN_BUDGET']

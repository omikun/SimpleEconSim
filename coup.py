#!/usr/bin/env python3
"""
coup.py — Regime coups for the REGNUM tile game (M3.5).

Pure gameplay module.  A coup is an extra-constitutional regime change led by
a "general": an ambitious, popular (charismatic) and personally-loyal adult
resident who is not a corporation or the government itself.

Conservation note: the ONLY money movement is ``seize_treasury``, which
transfers cash from the tile government agents to the general.  Those gov
agents are appended to ``region.agents`` and counted by the per-currency
audit, so the transfer preserves the currency total.  The "purge" writes
``mem_casualties`` / ``mem_promises`` memory seeds on the deposed faction's
members (pure state) — no wealth is destroyed; the deposed elite's portable
wealth simply stays with its owners (the M4 refugee seam reads it later).
"""

from __future__ import annotations


#: Legitimacy below which a coup can trigger (matches unrest._takeover).
COUP_LEGITIMACY_TRIGGER = 0.4

#: General eligibility: min weighted score to be a viable coup leader.
GENERAL_SCORE_MIN = 0.5

#: Trait weights for the general score (ambition drives the attempt, charisma
#: is the popularity proxy, loyalty keeps a general's backers intact).
GENERAL_AMBITON_W = 0.4
GENERAL_CHARISMA_W = 0.4
GENERAL_LOYALTY_W = 0.2


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _general_score(a):
    """Weighted coup-viability score of a resident agent."""
    ambition = getattr(a, 'ambition', 0.5)
    charisma = getattr(a, 'charisma', 0.5)
    loyalty = getattr(a, 'loyalty', 0.5)
    return (GENERAL_AMBITON_W * ambition
            + GENERAL_CHARISMA_W * charisma
            + GENERAL_LOYALTY_W * loyalty)


def find_generals(nation, t):
    """Return a list of ``(agent, score)`` viable generals, best first.

    A general is a living, adult, non-corp, non-gov resident whose weighted
    trait score clears ``GENERAL_SCORE_MIN``.
    """
    out = []
    for tile in getattr(nation, 'tiles', []):
        for a in getattr(tile, 'agents', []):
            if (not getattr(a, 'alive', True)
                    or getattr(a, 'is_corporation', False)
                    or getattr(a, 'is_government', False)
                    or a.age(t) <= 20):
                continue
            score = _general_score(a)
            if score >= GENERAL_SCORE_MIN:
                out.append((a, score))
    out.sort(key=lambda p: p[1], reverse=True)
    return out


def coup_chance(nation, t, rng=None):
    """Determine whether a coup should trigger this turn.

    A coup is possible only when regime legitimacy has collapsed below
    ``COUP_LEGITIMACY_TRIGGER`` AND at least one viable general exists.  The
    probability scales with the best general's score and the legitimacy
    shortfall.  Deterministic when *rng* is supplied as a float in [0,1).

    Returns ``(general, fires)`` where *general* is the leading candidate (or
    None).
    """
    legitimacy = getattr(nation, 'legitimacy', 0.6)
    if legitimacy >= COUP_LEGITIMACY_TRIGGER:
        return None, False
    generals = find_generals(nation, t)
    if not generals:
        return None, False
    general, score = generals[0]
    shortfall = COUP_LEGITIMACY_TRIGGER - legitimacy
    p = score * (0.25 + 1.5 * shortfall)
    p = _clamp(p, 0.0, 0.95)
    if rng is None:
        import random
        rng = random.random()
    return general, rng < p


def seize_treasury(nation, general, t):
    """M3.5: transfer all tile-government cash to the coup leader (conserved).

    Returns the total amount seized.
    """
    total = 0.0
    for tile in getattr(nation, 'tiles', []):
        gov_agent = getattr(getattr(tile, 'gov', None), 'agent', None)
        if gov_agent is None:
            continue
        cash = max(0.0, gov_agent.cash)
        if cash <= 0:
            continue
        gov_agent.cash -= cash
        general.cash += cash
        total += cash
    return total


def _purge(nation, t, deposed_faction):
    """Write memory seeds on the deposed faction's members (pure state).

    Each member of *deposed_faction* (across all tiles) records a casualty and
    a broken promise, so future grievance rises — but no wealth is destroyed.
    Returns the number of agents purged (memory-seeded).
    """
    if deposed_faction is None:
        return 0
    seeded = 0
    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        f = factions.get(deposed_faction)
        if f is None:
            continue
        for a in getattr(tile, 'agents', []):
            if a.id in f.membership:
                a.mem_push('mem_casualties', 1.0)
                a.mem_push('mem_promises', 1.0)
                seeded += 1
    return seeded


def execute_coup(nation, t, general, deposed_faction=None):
    """Run a coup: seize the treasury, flip the regime, purge the old elite.

    - ``seized``: total treasury cash moved to the general (conserved).
    - ``regime``: regime_type flips to 'autocracy' (military/strongman rule).
    - ``purged``: deposed-faction members recorded as casualties/broken
      promises (memory seeds only — no wealth destroyed).
    - ``legitimacy``: reset to a low-but-stable post-coup baseline, so the
      new regime is fragile and can itself be overturned.

    Returns a result dict.
    """
    old_regime = getattr(nation, 'regime_type', 'autocracy')
    deposed = deposed_faction if deposed_faction is not None \
        else getattr(nation, '_incumbent_faction', None)

    seized = seize_treasury(nation, general, t)
    purged = _purge(nation, t, deposed)

    nation.regime_type = 'autocracy'
    nation.legitimacy = 0.3
    nation._incumbent_faction = None

    return {
        'turn': t,
        'general_id': general.id,
        'old_regime': old_regime,
        'new_regime': nation.regime_type,
        'seized': seized,
        'purged': purged,
        'deposed_faction': deposed,
    }


__all__ = ['find_generals', 'coup_chance', 'seize_treasury',
           'execute_coup', 'COUP_LEGITIMACY_TRIGGER', 'GENERAL_SCORE_MIN']
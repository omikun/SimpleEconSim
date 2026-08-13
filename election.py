#!/usr/bin/env python3
"""
election.py — Regime elections for the REGNUM tile game (M3.1–M3.3).

Pure gameplay module.  It GENERATES candidates (from agent charisma + faction
membership), lets a treasury finance campaigns (conserved transfer: tile-gov
cash -> candidate cash, popularity accruing at a charisma-diluted rate), and
tallies a faction-weighted vote where members vote their factions and defect
when they remember broken promises (``mem_promises``).

Conservation note: the ONLY money movement here is campaign finance, which
transfers cash from a tile government agent to the candidate agent.  Both are
counted by ``forex.audit_currency_total`` (the tile gov agent is appended to
``region.agents``), so the per-currency total is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    from goods import Goods
except ImportError:  # pragma: no cover - goods not needed at runtime
    Goods = None


#: Minimum adult age for voting (matches the region.py "adults" cutoff).
VOTING_AGE = 20

#: Cap on the candidate pool size.
MAX_CANDIDATES = 8

#: Popularity earned per dollar spent, for a charisma==1.0 candidate.
POPULARITY_PER_DOLLAR = 1.0 / 2000.0

#: Charisma dilution floor: a charisma==0.0 candidate still gets this
#: fraction of the popularity-per-dollar that a charisma==1.0 candidate does.
CHARISMA_DILUTION_FLOOR = 0.5

#: How many candidates receive an even split of a campaign budget.
MAX_CAMPAIGNED = 4


@dataclass(eq=False)
class Candidate:
    """A candidate in a regime election.

    Attributes
    ----------
    agent : Agent
        The candidate agent (a living adult resident).
    backing_faction : str | None
        Name of the faction backing this candidate (None for independents).
    platform : dict[str, float]
        Policy demands promised (demand name -> strength 0..1).
    popularity : float
        Aggregate popularity score (charisma + faction backing + campaign).
    """

    agent: object
    backing_faction: str | None = None
    platform: dict = field(default_factory=dict)
    popularity: float = 0.0


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _is_voter(a, t):
    """True if *a* is a living, adult, non-corp, non-gov agent."""
    return (getattr(a, 'alive', True)
            and not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and a.age(t) > VOTING_AGE)


def _all_voters(nation, t):
    """Every adult voter across the nation's tiles."""
    out = []
    for tile in getattr(nation, 'tiles', []):
        out.extend(a for a in getattr(tile, 'agents', [])
                   if _is_voter(a, t))
    return out


def _platform_from_faction(faction):
    """Ranked demand -> promised-strength platform (from faction demands)."""
    return {d.name: _clamp(d.weight, 0.0, 1.0) for d in faction.demands}


def _base_popularity(agent, faction):
    """Charisma weighted by the backing faction's support (0..1)."""
    support = getattr(faction, 'support', 0.0)
    return _clamp(getattr(agent, 'charisma', 0.5) * (0.5 + 0.5 * support),
                  0.0, 1.0)


def generate_candidates(nation, t):
    """M3.1: build the candidate pool from charisma + faction membership.

    One candidate per faction (the highest-charisma adult member, aggregated
    across all of the nation's tiles), plus top-charisma independents to fill
    a minimum field.  Platforms are taken from each faction's demands.
    """
    faction_pool = {}  # name -> {'faction': Faction, 'members': [Agent]}
    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for f in factions.values():
            members = [a for a in getattr(tile, 'agents', [])
                       if a.id in f.membership and _is_voter(a, t)]
            if not members:
                continue
            entry = faction_pool.setdefault(f.name,
                                            {'faction': f, 'members': []})
            entry['members'].extend(members)

    candidates = []
    seen = set()
    for name, entry in faction_pool.items():
        f = entry['faction']
        leader = max(entry['members'], key=lambda a: getattr(a, 'charisma', 0.0))
        candidates.append(Candidate(
            agent=leader,
            backing_faction=name,
            platform=_platform_from_faction(f),
            popularity=_base_popularity(leader, f),
        ))
        seen.add(leader.id)

    # Independents fill up to a minimum viable field (top charisma).
    if len(candidates) < 2:
        voters = sorted(_all_voters(nation, t),
                        key=lambda a: getattr(a, 'charisma', 0.0), reverse=True)
        for a in voters:
            if a.id in seen:
                continue
            candidates.append(Candidate(
                agent=a, backing_faction=None, platform={},
                popularity=getattr(a, 'charisma', 0.5)))
            seen.add(a.id)
            if len(candidates) >= 2:
                break

    candidates.sort(key=lambda c: c.popularity, reverse=True)
    return candidates[:MAX_CANDIDATES]


def campaign_finance(nation, candidate, amount, t):
    """M3.2: move treasury cash to a candidate; popularity accrues.

    Transfers *amount* of cash from the nation's tile treasuries (richest
    first) to the candidate's own cash — a conserved transfer, since both the
    tile government agent and the candidate agent are counted in the
    per-currency audit.  Popularity gained is charisma-diluted: a low-charisma
    candidate converts each dollar into less popularity.

    Returns ``(spent, popularity_gained)``.
    """
    if amount <= 0 or candidate.agent is None:
        return 0.0, 0.0
    remaining = amount
    tiles = sorted(getattr(nation, 'tiles', []),
                   key=lambda t: getattr(getattr(t, 'gov', None), 'agent', None)
                   and t.gov.agent.cash, reverse=True) \
        if getattr(nation, 'tiles', []) else []
    for tile in tiles:
        gov_agent = getattr(getattr(tile, 'gov', None), 'agent', None)
        if gov_agent is None:
            continue
        cash = max(0.0, gov_agent.cash)
        if cash <= 0:
            continue
        take = min(cash, remaining)
        gov_agent.cash -= take
        candidate.agent.cash += take
        remaining -= take
        if remaining <= 0:
            break

    spent = amount - remaining
    if spent <= 0:
        return 0.0, 0.0

    charisma = getattr(candidate.agent, 'charisma', 0.5)
    dilution = CHARISMA_DILUTION_FLOOR + (1.0 - CHARISMA_DILUTION_FLOOR) * charisma
    gain = spent * dilution * POPULARITY_PER_DOLLAR
    candidate.popularity += gain
    return spent, gain


def _best_by_charisma(candidates):
    return max(candidates, key=lambda c: getattr(c.agent, 'charisma', 0.0))


def faction_weighted_vote(nation, candidates, t):
    """M3.3: adult voters vote their factions, defecting on broken promises.

    Each voter's single vote goes to the candidate backing their most
    influential faction (support x (1 + influence) weighted).  A voter who
    remembers broken promises (``mem_promises`` > 0.5) from the INCUMBENT
    faction defects entirely to the strongest rival — so betraying a big
    faction flips the election.

    Returns ``{candidate: votes}``.
    """
    by_faction = {c.backing_faction: c for c in candidates
                  if c.backing_faction is not None}
    incumbent = getattr(nation, '_incumbent_faction', None)
    incumbent_cand = by_faction.get(incumbent)
    rivals = [c for c in candidates if c is not incumbent_cand] or candidates

    votes = {c: 0.0 for c in candidates}

    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for a in getattr(tile, 'agents', []):
            if not _is_voter(a, t):
                continue
            memberships = [f for f in factions.values() if a.id in f.membership]
            if not memberships:
                votes[_best_by_charisma(candidates)] += 1.0
                continue
            top_f = max(memberships,
                        key=lambda f: f.support * (1.0 + f.influence))
            preferred = by_faction.get(top_f.name) or _best_by_charisma(candidates)
            betrayal = a.mem_avg('mem_promises', 0.0)
            if preferred is incumbent_cand and betrayal > 0.5:
                preferred = _best_by_charisma(rivals)
            votes[preferred] += max(0.05, top_f.support * (1.0 + top_f.influence))
    return votes


def run_election(nation, t, campaign_budget=0.0):
    """Run a full election: candidate pool -> (optional) campaign -> vote.

    Does NOT mutate policy knobs itself — the regime orchestrator applies the
    winner's platform afterward (see regime.apply_platform).  Records the
    incumbent faction for future betrayal memory.

    Returns a result dict: {turn, winner, votes, candidates}.
    """
    candidates = generate_candidates(nation, t)
    if not candidates:
        return {'turn': t, 'winner': None, 'votes': {}, 'candidates': []}

    if campaign_budget > 0:
        n = min(len(candidates), MAX_CAMPAIGNED)
        share = campaign_budget / n
        for c in candidates[:n]:
            campaign_finance(nation, c, share, t)

    votes = faction_weighted_vote(nation, candidates, t)
    winner = max(votes, key=lambda c: votes[c]) if votes else candidates[0]
    nation._incumbent_faction = winner.backing_faction
    return {'turn': t, 'winner': winner, 'votes': votes,
            'candidates': candidates}


__all__ = ['Candidate', 'generate_candidates', 'campaign_finance',
           'faction_weighted_vote', 'run_election',
           'VOTING_AGE', 'MAX_CANDIDATES',
           'POPULARITY_PER_DOLLAR', 'CHARISMA_DILUTION_FLOOR']
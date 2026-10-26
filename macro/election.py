#!/usr/bin/env python3
"""
election.py — Regime elections for the Call of Capital tile game (M3.1–M3.3).

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
from treasury_trace import begin_public_change, finish_public_change

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


def _election_trace_context(nation, turn, action_id, shared=None):
    """Return a shared causal context when a region has run tracing enabled."""
    if shared is not None:
        return shared
    regions = list(getattr(nation, 'tiles', ()))
    region = next((tile for tile in regions
                   if getattr(tile, '_run_trace', None) is not None
                   and getattr(tile, '_collective_trace_clock', None) is not None),
                  None)
    if region is None:
        return None
    clock = region._collective_trace_clock
    trace_turn = int(clock.get('turn', turn))
    return {'region': region, 'clock': clock, 'turn': trace_turn,
            'operation_id': (f'election:{action_id}:'
                             f'{getattr(nation, "name", "unnamed")}:'
                             f'{trace_turn}:{int(clock.get("next", 0))}'),
            'event_ids': [], 'candidate_pool_event_id': None}


def _emit_election_trace(context, *, kind, subject, metric_id, unit,
                         after, inputs, before=None, record_class='outcome',
                         cause_event_ids=None, **extra):
    if context is None:
        return None
    from run_trace import emit
    event_inputs = dict(inputs or {})
    event_inputs.setdefault('operation_id', context['operation_id'])
    event_inputs.setdefault('turn', context['turn'])
    event_id = emit(
        context['region'], kind=kind, record_class=record_class,
        phase='election', subject=subject, metric_id=metric_id,
        unit=unit, before=before, after=after, inputs=event_inputs,
        cause_event_ids=cause_event_ids, **extra)
    if event_id is not None:
        context.setdefault('event_ids', []).append(event_id)
    return event_id


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


def generate_candidates(nation, t, *, _trace_context=None):
    """M3.1: build the candidate pool from charisma + faction membership.

    One candidate per faction (the highest-charisma adult member, aggregated
    across all of the nation's tiles), plus top-charisma independents to fill
    a minimum field.  Platforms are taken from each faction's demands.
    """
    trace_context = _election_trace_context(
        nation, t, 'candidate_pool', _trace_context)
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
    candidate_evaluations = []
    for name, entry in faction_pool.items():
        f = entry['faction']
        leader = max(entry['members'], key=lambda a: getattr(a, 'charisma', 0.0))
        popularity = _base_popularity(leader, f)
        candidate = Candidate(
            agent=leader,
            backing_faction=name,
            platform=_platform_from_faction(f),
            popularity=popularity,
        )
        candidates.append(candidate)
        if trace_context is not None:
            charisma_leaders = sorted(
                entry['members'],
                key=lambda member: getattr(member, 'charisma', 0.0),
                reverse=True)[:3]
            candidate_evaluations.append({
                'candidate_id': str(leader.id),
                'candidate_type': 'faction_leader',
                'backing_faction': name,
                'eligible_faction_members': len(entry['members']),
                'leader_charisma': float(getattr(leader, 'charisma', 0.0)),
                'faction_support': float(getattr(f, 'support', 0.0)),
                'base_popularity': float(popularity),
                'top_charisma_members': [
                    {'agent_id': str(member.id),
                     'charisma': float(getattr(member, 'charisma', 0.0))}
                    for member in charisma_leaders],
                'leader_tie_rule': 'first_member_in_nation_tile_order',
                'platform': candidate.platform,
            })
        seen.add(leader.id)

    # Independents fill up to a minimum viable field (top charisma).
    independent_slots_needed = max(0, 2 - len(candidates))
    independent_candidates = []
    independent_voters_scanned = 0
    if len(candidates) < 2:
        voters = sorted(_all_voters(nation, t),
                        key=lambda a: getattr(a, 'charisma', 0.0), reverse=True)
        for a in voters:
            independent_voters_scanned += 1
            if a.id in seen:
                continue
            candidate = Candidate(
                agent=a, backing_faction=None, platform={},
                popularity=getattr(a, 'charisma', 0.5))
            candidates.append(candidate)
            independent_candidates.append({
                'candidate_id': str(a.id),
                'charisma': float(getattr(a, 'charisma', 0.5)),
                'popularity': float(candidate.popularity),
            })
            seen.add(a.id)
            if len(candidates) >= 2:
                break

    candidates.sort(key=lambda c: c.popularity, reverse=True)
    ranked_candidates = candidates
    selected_candidates = ranked_candidates[:MAX_CANDIDATES]
    if trace_context is not None:
        selected_ids = {candidate.agent.id for candidate in selected_candidates}
        ranked_rows = [
            {'rank': rank, 'candidate_id': str(candidate.agent.id),
             'backing_faction': candidate.backing_faction,
             'candidate_type': ('independent'
                                if candidate.backing_faction is None
                                else 'faction_leader'),
             'charisma': float(getattr(candidate.agent, 'charisma', 0.0)),
             'popularity': float(candidate.popularity),
             'selected': candidate.agent.id in selected_ids}
            for rank, candidate in enumerate(ranked_candidates, 1)]
        pool_event_id = _emit_election_trace(
            trace_context, kind='election_candidate_pool_decision',
            subject={'type': 'nation',
                     'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.election_candidate_pool', unit='candidates',
            before=len(ranked_candidates), after=len(selected_candidates),
            record_class='decision',
            inputs={'candidate_count_before_limit': len(ranked_candidates),
                    'candidate_count_after_limit': len(selected_candidates),
                    'candidate_limit': MAX_CANDIDATES,
                    'faction_candidate_evaluations': candidate_evaluations,
                    'independent_slots_needed': independent_slots_needed,
                    'independent_candidates_selected': independent_candidates,
                    'independent_voters_scanned': independent_voters_scanned,
                    'ranking_rule': 'stable_descending_base_popularity',
                    'candidate_ranking': ranked_rows,
                    'selected_candidate_ids':
                    [str(candidate.agent.id) for candidate in selected_candidates],
                    'excluded_by_candidate_limit':
                    [row['candidate_id'] for row in ranked_rows
                     if not row['selected']],
                    'reason': ('candidate_pool_built' if selected_candidates
                               else 'no_eligible_faction_leaders_or_voters')})
        trace_context['candidate_pool_event_id'] = pool_event_id
    return selected_candidates


def campaign_finance(nation, candidate, amount, t, *, _trace_context=None):
    """M3.2: move treasury cash to a candidate; popularity accrues.

    Transfers *amount* from the nation's tile treasuries (richest first) to
    the candidate. If the candidate holds the nation's currency in a wallet,
    the cash expense and wallet receipt are posted as linked legs instead of
    reporting wallet value as hand-cash income. Popularity gained is
    charisma-diluted: a low-charisma candidate converts each unit into less
    popularity.

    Returns ``(spent, popularity_gained)``.
    """
    trace_context = _election_trace_context(
        nation, t, 'campaign_finance', _trace_context)
    if amount <= 0 or candidate.agent is None:
        return 0.0, 0.0
    remaining = amount
    candidate_tile = next(
        (tile for tile in getattr(nation, 'tiles', [])
         if candidate.agent in getattr(tile, 'agents', ())),
        None)
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
        source_cash_before = float(gov_agent.cash)
        candidate_currency = (getattr(candidate.agent, 'home_currency', None)
                              or getattr(nation, 'currency', None))
        wallet_settlement = bool(
            candidate_currency
            and candidate_currency != getattr(nation, 'currency', None))
        if wallet_settlement:
            from forex import fx_add, fx_balance
            candidate_balance_before = float(
                fx_balance(candidate.agent, nation.currency))
            fx_add(candidate.agent, nation.currency, take)
            candidate_balance_after = float(
                fx_balance(candidate.agent, nation.currency))
        else:
            candidate_balance_before = float(candidate.agent.cash)
            _public_write = begin_public_change(None, candidate.agent)
            candidate.agent.cash += take
            finish_public_change(_public_write, 'election:campaign_finance',
                                 inputs={'source_writer': 'election.py:campaign_finance:c49e09a08ec6be19:1', 'semantic_operation_id': locals().get('operation_id')})
            candidate_balance_after = float(candidate.agent.cash)
        _public_write = begin_public_change(None, gov_agent)
        gov_agent.cash -= take
        finish_public_change(_public_write, 'election:campaign_finance',
                             inputs={'source_writer': 'election.py:campaign_finance:4ecca5aad103abb8:1', 'semantic_operation_id': locals().get('operation_id')})
        source_cash_after = float(gov_agent.cash)
        nation_name = getattr(nation, 'name', 'nation')
        tile_name = getattr(tile, 'name', f'tile-{gov_agent.id}')
        transfer_id = (f'election-campaign:{nation_name}:{t}:'
                       f'{candidate.agent.id}:{tile_name}')
        detail = {'transfer_id': transfer_id, 'nation': nation_name,
                  'source_tile': tile_name,
                  'candidate_tile': getattr(candidate_tile, 'name', tile_name),
                  'treasury_id': gov_agent.id,
                  'candidate_id': candidate.agent.id,
                  'amount': float(take), 'currency': nation.currency,
                  'tender': 'wallet' if wallet_settlement else 'cash',
                  'treasury_cash_before': source_cash_before,
                  'treasury_cash_after': source_cash_after,
                  'candidate_balance_before': candidate_balance_before,
                  'candidate_balance_after': candidate_balance_after,
                  'reason': 'election_campaign_finance'}
        from economy.actor_accounts import record as record_economic_event
        record_economic_event(
            tile, 'election_campaign_spending', turn=t,
            payer_id=gov_agent.id, amount=take,
            asset_id=transfer_id, source_id=transfer_id,
            currency=nation.currency, detail=detail)
        destination_tile = candidate_tile or tile
        record_economic_event(
            destination_tile,
            'wallet_transfer_in' if wallet_settlement
            else 'election_campaign_receipt',
            turn=t, recipient_id=candidate.agent.id, amount=take,
            asset_id=transfer_id, source_id=transfer_id,
            currency=nation.currency, detail=detail)
        campaign_decision_id = (trace_context.get('current_campaign_decision_id')
                                if trace_context is not None else None)
        trace_detail = dict(detail)
        if trace_context is not None:
            trace_detail['operation_id'] = trace_context['operation_id']
            trace_detail['campaign_decision_event_id'] = campaign_decision_id
        _emit_election_trace(
            trace_context, kind='election_campaign_transfer',
            record_class='transfer',
            subject={'type': 'election_campaign', 'id': transfer_id,
                     'candidate_id': candidate.agent.id, 'tile': tile_name},
            metric_id='finance.election_campaign', unit=nation.currency,
            before=source_cash_before, after=source_cash_after,
            inputs=trace_detail,
            cause_event_ids=([campaign_decision_id]
                             if campaign_decision_id else None))
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


def faction_weighted_vote(nation, candidates, t, *, _trace_context=None):
    """M3.3: adult voters vote their factions, defecting on broken promises.

    Each voter's single vote goes to the candidate backing their most
    influential faction (support x (1 + influence) weighted).  A voter who
    remembers broken promises (``mem_promises`` > 0.5) from the INCUMBENT
    faction defects entirely to the strongest rival — so betraying a big
    faction flips the election.

    Returns ``{candidate: votes}``.
    """
    trace_context = _election_trace_context(
        nation, t, 'faction_weighted_vote', _trace_context)
    by_faction = {c.backing_faction: c for c in candidates
                  if c.backing_faction is not None}
    incumbent = getattr(nation, '_incumbent_faction', None)
    incumbent_cand = by_faction.get(incumbent)
    rivals = [c for c in candidates if c is not incumbent_cand] or candidates

    votes = {c: 0.0 for c in candidates}
    voter_event_ids = {candidate: [] for candidate in candidates}
    eligible_voter_count = 0
    no_membership_voter_count = 0
    betrayal_defector_count = 0

    for tile in getattr(nation, 'tiles', []):
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for a in getattr(tile, 'agents', []):
            if not _is_voter(a, t):
                continue
            eligible_voter_count += 1
            memberships = [f for f in factions.values() if a.id in f.membership]
            if not memberships:
                preferred = _best_by_charisma(candidates)
                vote_weight = 1.0
                no_membership_voter_count += 1
                reason = 'no_membership_charisma_fallback'
                membership_rows = []
                preferred_before_betrayal = preferred
                betrayal = None
                top_f = None
            else:
                membership_rows = [
                    {'faction': f.name, 'support': float(f.support),
                     'influence': float(f.influence),
                     'weighted_influence':
                     float(f.support * (1.0 + f.influence))}
                    for f in memberships]
                top_f = max(memberships,
                            key=lambda f: f.support * (1.0 + f.influence))
                preferred_before_betrayal = (by_faction.get(top_f.name)
                                             or _best_by_charisma(candidates))
                preferred = preferred_before_betrayal
                betrayal = a.mem_avg('mem_promises', 0.0)
                vote_weight = max(0.05, top_f.support * (1.0 + top_f.influence))
                if preferred is incumbent_cand and betrayal > 0.5:
                    preferred = _best_by_charisma(rivals)
                    betrayal_defector_count += 1
                    reason = 'broken_promise_defection'
                elif top_f.name not in by_faction:
                    reason = 'faction_candidate_missing_charisma_fallback'
                else:
                    reason = 'most_influential_faction_alignment'
            votes[preferred] += vote_weight
            if trace_context is not None:
                cause_event_ids = ([trace_context['candidate_pool_event_id']]
                                   if trace_context.get('candidate_pool_event_id')
                                   else None)
                voter_event_id = _emit_election_trace(
                    trace_context, kind='election_voter_decision',
                    subject={'type': 'tile/agent', 'id': str(a.id),
                             'tile': tile.name},
                    metric_id='scenario.election_voter_decision',
                    unit='candidate_id', after=str(preferred.agent.id),
                    record_class='decision',
                    inputs={'voter_id': str(a.id),
                            'eligible_for_vote': True,
                            'faction_memberships': membership_rows,
                            'selected_membership_faction':
                            getattr(top_f, 'name', None),
                            'preferred_candidate_before_betrayal':
                            str(preferred_before_betrayal.agent.id),
                            'incumbent_faction': incumbent,
                            'incumbent_candidate_id':
                            (str(incumbent_cand.agent.id)
                             if incumbent_cand is not None else None),
                            'promise_memory': betrayal,
                            'betrayal_threshold': 0.5,
                            'rival_candidate_ids':
                            [str(candidate.agent.id) for candidate in rivals],
                            'charisma_fallback_candidate_ids':
                            [str(candidate.agent.id) for candidate in candidates],
                            'selected_candidate_id': str(preferred.agent.id),
                            'vote_weight': vote_weight,
                            'reason': reason},
                    cause_event_ids=cause_event_ids)
                if voter_event_id is not None:
                    voter_event_ids[preferred].append(voter_event_id)

    if trace_context is not None:
        tally_event_ids = []
        for candidate in candidates:
            cause_event_ids = list(voter_event_ids[candidate])
            candidate_pool_event_id = trace_context.get('candidate_pool_event_id')
            if candidate_pool_event_id and candidate_pool_event_id not in cause_event_ids:
                cause_event_ids.append(candidate_pool_event_id)
            tally_event_id = _emit_election_trace(
                trace_context, kind='election_candidate_vote_tally',
                subject={'type': 'nation/candidate',
                         'id': str(candidate.agent.id)},
                metric_id='scenario.election_vote_tally',
                unit='weighted_votes', after=float(votes[candidate]),
                before=0.0, record_class='calculation',
                inputs={'candidate_id': str(candidate.agent.id),
                        'backing_faction': candidate.backing_faction,
                        'candidate_popularity': float(candidate.popularity),
                        'candidate_charisma': float(
                            getattr(candidate.agent, 'charisma', 0.0)),
                        'eligible_voters': eligible_voter_count,
                        'no_membership_voters': no_membership_voter_count,
                        'broken_promise_defectors_total':
                        betrayal_defector_count,
                        'weighted_vote_total': float(votes[candidate]),
                        'voter_decision_event_count':
                        len(voter_event_ids[candidate]),
                        'formula_id': 'election.faction_weighted_vote.v1'},
                cause_event_ids=cause_event_ids or None)
            if tally_event_id:
                tally_event_ids.append(tally_event_id)
        trace_context['vote_tally_event_ids'] = tally_event_ids
        trace_context['eligible_voter_count'] = eligible_voter_count
        trace_context['no_membership_voter_count'] = no_membership_voter_count
        trace_context['broken_promise_defector_count'] = betrayal_defector_count
    return votes


def run_election(nation, t, campaign_budget=0.0):
    """Run a full election: candidate pool -> (optional) campaign -> vote.

    Does NOT mutate policy knobs itself — the regime orchestrator applies the
    winner's platform afterward (see regime.apply_platform).  Records the
    incumbent faction for future betrayal memory.

    Returns a result dict: {turn, winner, votes, candidates}.
    """
    trace_context = _election_trace_context(nation, t, 'run_election')
    candidates = generate_candidates(nation, t, _trace_context=trace_context)
    candidate_pool_event_id = (trace_context.get('candidate_pool_event_id')
                               if trace_context is not None else None)
    if not candidates:
        if trace_context is not None:
            _emit_election_trace(
                trace_context, kind='election_result',
                subject={'type': 'nation',
                         'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.election_result', unit='candidate_id',
                after='no_candidates',
                inputs={'campaign_budget_requested': float(campaign_budget),
                        'candidate_count': 0,
                        'reason': 'candidate_pool_empty'},
                cause_event_ids=([candidate_pool_event_id]
                                 if candidate_pool_event_id else None))
        return {'turn': t, 'winner': None, 'votes': {}, 'candidates': []}

    initial_popularity = {candidate: float(candidate.popularity)
                          for candidate in candidates}
    campaign_gate_id = None
    campaign_allocation_rows = []
    campaign_spent_total = 0.0
    if trace_context is not None:
        campaign_gate_id = _emit_election_trace(
            trace_context, kind='election_campaign_budget_gate',
            record_class='decision',
            subject={'type': 'nation',
                     'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.election_campaign_gate', unit='enabled',
            before=False, after=bool(campaign_budget > 0),
            inputs={'campaign_budget_requested': float(campaign_budget),
                    'candidate_count': len(candidates),
                    'maximum_candidates_to_campaign': MAX_CAMPAIGNED,
                    'reason': ('campaign_budget_provided'
                               if campaign_budget > 0 else
                               'no_campaign_budget')},
            cause_event_ids=([candidate_pool_event_id]
                             if candidate_pool_event_id else None))
    if campaign_budget > 0:
        n = min(len(candidates), MAX_CAMPAIGNED)
        share = campaign_budget / n
        for c in candidates[:n]:
            candidate_id = str(c.agent.id)
            popularity_before = float(c.popularity)
            decision_id = None
            if trace_context is not None:
                decision_id = _emit_election_trace(
                    trace_context, kind='election_campaign_candidate_budget',
                    record_class='decision',
                    subject={'type': 'nation/candidate', 'id': candidate_id},
                    metric_id='scenario.election_campaign_budget',
                    unit=getattr(nation, 'currency', None) or 'local_currency',
                    after=float(share),
                    inputs={'campaign_budget_requested': float(campaign_budget),
                            'campaigned_candidate_count': n,
                            'equal_candidate_share': float(share),
                            'candidate_rank_before_campaign':
                            candidates.index(c) + 1,
                            'candidate_popularity_before': popularity_before},
                    cause_event_ids=([campaign_gate_id]
                                     if campaign_gate_id else None))
                trace_context['current_campaign_decision_id'] = decision_id
            transfer_start = (len(trace_context['event_ids'])
                              if trace_context is not None else 0)
            spent, popularity_gained = campaign_finance(
                nation, c, share, t, _trace_context=trace_context)
            campaign_spent_total += spent
            new_transfer_ids = (
                trace_context['event_ids'][transfer_start:]
                if trace_context is not None else [])
            if trace_context is not None:
                trace_context['current_campaign_decision_id'] = None
                budget_outcome_id = _emit_election_trace(
                    trace_context, kind='election_campaign_candidate_outcome',
                    subject={'type': 'nation/candidate', 'id': candidate_id},
                    metric_id='scenario.election_campaign_budget',
                    unit=getattr(nation, 'currency', None) or 'local_currency',
                    before=float(share), after=float(spent),
                    inputs={'requested_share': float(share),
                            'actual_spending': float(spent),
                            'unspent_share': float(share - spent),
                            'candidate_popularity_before': popularity_before,
                            'candidate_popularity_after': float(c.popularity),
                            'popularity_gain_reported': float(popularity_gained),
                            'transfer_event_ids': new_transfer_ids},
                    cause_event_ids=([decision_id] + new_transfer_ids
                                     if decision_id else new_transfer_ids or None))
                charisma = float(getattr(c.agent, 'charisma', 0.5))
                charisma_dilution = (
                    CHARISMA_DILUTION_FLOOR
                    + (1.0 - CHARISMA_DILUTION_FLOOR) * charisma)
                _emit_election_trace(
                    trace_context, kind='election_campaign_popularity_change',
                    subject={'type': 'nation/candidate', 'id': candidate_id},
                    metric_id='politics.election_campaign_popularity',
                    unit='points', before=popularity_before,
                    after=float(c.popularity), record_class='calculation',
                    formula_id='election.campaign_popularity.v1',
                    inputs={'candidate_id': candidate_id,
                            'cash_spent': float(spent),
                            'charisma': charisma,
                            'charisma_dilution_floor':
                            CHARISMA_DILUTION_FLOOR,
                            'charisma_dilution_multiplier':
                            charisma_dilution,
                            'popularity_per_currency_unit':
                            POPULARITY_PER_DOLLAR,
                            'reported_popularity_gain':
                            float(popularity_gained),
                            'formula':
                            'cash_spent * charisma_dilution_multiplier * popularity_per_currency_unit'},
                    cause_event_ids=([budget_outcome_id]
                                     if budget_outcome_id else
                                     new_transfer_ids or None))
            campaign_allocation_rows.append({
                'candidate_id': candidate_id,
                'requested_share': float(share),
                'actual_spending': float(spent),
                'popularity_before': popularity_before,
                'popularity_after': float(c.popularity),
                'popularity_gain_reported': float(popularity_gained),
            })

    # Capitalist PAC backlash: enragers fund the opposition if pro-labor laws exist
    popularity_before_backlash = {candidate: float(candidate.popularity)
                                  for candidate in candidates}
    backlash_donations = 0.0
    try:
        from labor_politics import capitalist_electoral_backlash
        backlash_donations = capitalist_electoral_backlash(
            nation, candidates, t)
    except ImportError:
        pass

    votes = faction_weighted_vote(
        nation, candidates, t, _trace_context=trace_context)
    winner = max(votes, key=lambda c: votes[c]) if votes else candidates[0]
    incumbent_before = getattr(nation, '_incumbent_faction', None)
    nation._incumbent_faction = winner.backing_faction
    if trace_context is not None:
        tally_event_ids = trace_context.get('vote_tally_event_ids', [])
        cause_event_ids = ([candidate_pool_event_id] if candidate_pool_event_id
                           else []) + tally_event_ids
        final_candidate_rows = [
            {'candidate_id': str(candidate.agent.id),
             'backing_faction': candidate.backing_faction,
             'charisma': float(getattr(candidate.agent, 'charisma', 0.0)),
             'popularity_before_campaign': initial_popularity[candidate],
             'popularity_before_backlash': popularity_before_backlash[candidate],
             'popularity_after_election_effects': float(candidate.popularity),
             'weighted_votes': float(votes.get(candidate, 0.0)),
             'candidate_popularity_used_in_vote': False}
            for candidate in candidates]
        _emit_election_trace(
            trace_context, kind='election_result',
            subject={'type': 'nation/candidate',
                     'id': str(winner.agent.id)},
            metric_id='scenario.election_result', unit='candidate_id',
            after=str(winner.agent.id),
            inputs={'campaign_budget_requested': float(campaign_budget),
                    'campaign_spending_total': float(campaign_spent_total),
                    'capitalist_backlash_donations':
                    float(backlash_donations),
                    'candidate_count': len(candidates),
                    'candidate_profiles': final_candidate_rows,
                    'winner_faction': winner.backing_faction,
                    'winner_weighted_votes': float(votes.get(winner, 0.0)),
                    'weighted_vote_tally': {
                        str(candidate.agent.id): float(votes.get(candidate, 0.0))
                        for candidate in candidates},
                    'eligible_voters': trace_context.get(
                        'eligible_voter_count'),
                    'no_membership_voters': trace_context.get(
                        'no_membership_voter_count'),
                    'broken_promise_defectors': trace_context.get(
                        'broken_promise_defector_count'),
                    'candidate_popularity_used_in_candidate_pool': True,
                    'candidate_popularity_used_in_vote': False,
                    'base_popularity_order_used_as_vote_tiebreak': True,
                    'winner_rule':
                    'highest_weighted_faction_vote_total_then_first_candidate_in_base_popularity_order',
                    'vote_rule': 'highest_weighted_faction_vote_total',
                    'tie_rule': 'first_candidate_in_base_popularity_order',
                    'incumbent_faction_before': incumbent_before,
                    'incumbent_faction_after': winner.backing_faction,
                    'campaign_allocations': campaign_allocation_rows},
            cause_event_ids=cause_event_ids or None)
    return {'turn': t, 'winner': winner, 'votes': votes,
            'candidates': candidates}


__all__ = ['Candidate', 'generate_candidates', 'campaign_finance',
           'faction_weighted_vote', 'run_election',
           'VOTING_AGE', 'MAX_CANDIDATES',
           'POPULARITY_PER_DOLLAR', 'CHARISMA_DILUTION_FLOOR']

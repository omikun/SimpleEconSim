#!/usr/bin/env python3
"""
coup.py — Regime coups for the Call of Capital tile game (M3.5).

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


def assess_coup(nation, t, rng=None):
    """Return the leading coup candidate, outcome, and reconstructable inputs.

    This is the authoritative force-ratio calculation.  The detail dictionary
    is also consumed by the causal trace so the recorded decision matches the
    exact calculation used by gameplay.
    """
    legitimacy = getattr(nation, 'legitimacy', 0.6)
    if legitimacy >= COUP_LEGITIMACY_TRIGGER:
        return None, False, {
            'reason_code': 'legitimacy_above_trigger',
            'legitimacy': legitimacy,
            'legitimacy_trigger': COUP_LEGITIMACY_TRIGGER,
            'candidate_scan_performed': False,
        }
    generals = find_generals(nation, t)
    if not generals:
        return None, False, {
            'reason_code': 'no_eligible_general',
            'legitimacy': legitimacy,
            'legitimacy_trigger': COUP_LEGITIMACY_TRIGGER,
            'candidate_scan_performed': True,
            'eligible_general_count': 0,
            'general_score_minimum': GENERAL_SCORE_MIN,
        }
    general, score = generals[0]

    candidate_scores = [
        {'general_id': str(candidate.id), 'weighted_score': candidate_score}
        for candidate, candidate_score in generals
    ]
    trait_scores = {
        'ambition': getattr(general, 'ambition', 0.5),
        'charisma': getattr(general, 'charisma', 0.5),
        'loyalty': getattr(general, 'loyalty', 0.5),
    }

    # Calculate Conspirator Armed Force
    general_cash = getattr(general, 'cash', 0.0)
    trait_force = score * 25.0
    cash_force = min(50.0, general_cash * 0.5)
    conspirator_force = trait_force + cash_force

    # Calculate Loyalist Defense Force
    loyalist_units = []
    defector_units = []
    def unit_detail(unit):
        return {
            'unit_id': str(getattr(unit, 'unit_id', getattr(unit, 'id', 'unknown'))),
            'region_name': str(getattr(unit, 'region_name', '')),
            'soldiers': getattr(unit, 'soldiers', 0),
            'morale': getattr(unit, 'morale', 1.0),
            'strength': unit.strength,
        }

    for u in getattr(nation, 'military_units', []):
        if getattr(u, 'soldiers', 0) <= 0:
            continue
        # Unpaid, low-morale, or co-located units join conspirators
        if getattr(u, 'morale', 1.0) < 0.40 or getattr(u, 'region_name', '') == getattr(general, 'region', None):
            defector_units.append(u)
        else:
            loyalist_units.append(u)

    defector_force = sum(u.strength for u in defector_units)
    loyalist_unit_force = sum(u.strength for u in loyalist_units)
    conspirator_force += defector_force
    loyalist_force = loyalist_unit_force

    # Government treasury can mobilize palace guards
    gov = getattr(nation, 'government', None)
    gov_cash = gov.agent.cash if (gov and hasattr(gov, 'agent')) else 0.0
    treasury_guard_force = min(40.0, gov_cash * 0.2)
    legitimacy_force = legitimacy * 30.0
    loyalist_force += treasury_guard_force + legitimacy_force

    # Coercive force ratio test
    # If rng is explicitly passed (e.g. legacy unit test harness), allow it as a margin factor
    rng_margin = 0.0
    if rng is not None:
        rng_margin = (rng - 0.5) * 10.0
        conspirator_force += rng_margin

    fires = (conspirator_force > loyalist_force)
    return general, fires, {
        'reason_code': ('conspirators_overmatch' if fires
                        else 'loyalist_force_holds'),
        'legitimacy': legitimacy,
        'legitimacy_trigger': COUP_LEGITIMACY_TRIGGER,
        'candidate_scan_performed': True,
        'eligible_general_count': len(generals),
        'general_score_minimum': GENERAL_SCORE_MIN,
        'candidate_scores': candidate_scores,
        'general_id': str(general.id),
        'general_region': str(getattr(general, 'region', '')),
        'general_traits': trait_scores,
        'general_weighted_score': score,
        'general_trait_weights': {
            'ambition': GENERAL_AMBITON_W,
            'charisma': GENERAL_CHARISMA_W,
            'loyalty': GENERAL_LOYALTY_W,
        },
        'general_cash': general_cash,
        'general_trait_force': trait_force,
        'general_cash_force': cash_force,
        'defector_units': [unit_detail(u) for u in defector_units],
        'defector_force': defector_force,
        'loyalist_units': [unit_detail(u) for u in loyalist_units],
        'loyalist_unit_force': loyalist_unit_force,
        'government_cash': gov_cash,
        'treasury_guard_force': treasury_guard_force,
        'legitimacy_defense_force': legitimacy_force,
        'rng_draw': rng,
        'rng_margin': rng_margin,
        'conspirator_force': conspirator_force,
        'loyalist_force': loyalist_force,
        'force_margin': conspirator_force - loyalist_force,
        'comparison': 'conspirator_force > loyalist_force',
        'fires': fires,
    }


def coup_chance(nation, t, rng=None):
    """Determine whether a coup strikes and succeeds this turn.

    Grounded in the Monopoly of Violence and Coercion Calculus: low legitimacy
    and an eligible general are required, then conspirator armed force must
    strictly exceed loyalist state force.  The existing optional RNG margin is
    preserved for callers that supply it.

    Returns ``(general, fires)`` where *general* is the leading candidate (or None).
    """
    general, fires, _detail = assess_coup(nation, t, rng)
    return general, fires


def seize_treasury(nation, general, t, *, decision_event_id=None,
                   trace_event_ids=None):
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
        government_cash_before = float(gov_agent.cash)
        general_cash_before = float(general.cash)
        gov_agent.cash -= cash
        general.cash += cash
        total += cash
        operation_id = (f'coup-treasury:{nation.name}:{int(t)}:'
                        f'{tile.name}:{general.id}')
        currency = (getattr(tile, 'home_currency', None)
                    or getattr(nation, 'currency', None)
                    or 'local_currency')
        general_currency = (getattr(general, 'home_currency', None)
                            or currency)
        from economy.actor_accounts import record as record_economic_event
        journal_event = record_economic_event(
            tile, 'coup_treasury_seizure', turn=t,
            payer_id=gov_agent.id, recipient_id=general.id, amount=cash,
            source_id=operation_id, currency=currency,
            detail={'nation': nation.name, 'tile': tile.name,
                    'general_id': general.id, 'reason': 'successful_coup'})
        from finance_trace import (account_ref, cash_transfer_contract,
                                   emit_cash_transfer)
        contract = cash_transfer_contract(
            operation_id, 'coup_treasury_seizure', amount=cash,
            currency=currency,
            payer_account=account_ref(
                'government_wallet', str(gov_agent.id), currency,
                agent_id=str(gov_agent.id), tile=tile.name,
                nation_id=nation.name,
                balance_before=government_cash_before,
                balance_after=float(gov_agent.cash),
                balance_scope='cash_wallet'),
            payee_account=account_ref(
                'general_wallet', str(general.id), general_currency,
                agent_id=str(general.id), tile=tile.name,
                balance_before=general_cash_before,
                balance_after=float(general.cash),
                balance_scope='cash_wallet'),
            counterparty_leg_status='both_cash_balances_captured',
            political_operation='coup', nation=nation.name, tile=tile.name)
        transfer_event_id = emit_cash_transfer(
            tile, kind='coup_treasury_seizure', contract=contract,
            phase='politics',
            subject={'type': 'nation/operation', 'id': operation_id,
                     'nation': nation.name, 'tile': tile.name},
            inputs={'turn': int(t), 'nation': nation.name,
                    'general_id': str(general.id), 'tile': tile.name,
                    'operation_id': operation_id,
                    'actor_account_event_id': journal_event['id']
                    if journal_event is not None else None},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
        if trace_event_ids is not None and transfer_event_id is not None:
            trace_event_ids.append(transfer_event_id)
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


def execute_coup(nation, t, general, deposed_faction=None, *,
                 decision_event_id=None):
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

    seizure_event_ids = []
    legitimacy_before = float(getattr(nation, 'legitimacy', 0.3))
    seized = seize_treasury(
        nation, general, t, decision_event_id=decision_event_id,
        trace_event_ids=seizure_event_ids)
    purged = _purge(nation, t, deposed)

    nation.regime_type = 'autocracy'
    nation.legitimacy = 0.3
    nation._incumbent_faction = None

    if nation.tiles:
        from run_trace import emit
        cause_event_ids = ([decision_event_id] if decision_event_id else [])
        cause_event_ids.extend(seizure_event_ids)
        emit(nation.tiles[0], kind='coup_executed', record_class='outcome',
             phase='politics',
             subject={'type': 'nation', 'id': nation.name},
             metric_id='politics.coup_execution', unit='boolean',
             before=False, after=True, formula_id='coup.execution.v1',
             inputs={'turn': int(t), 'general_id': str(general.id),
                     'deposed_faction': deposed,
                     'old_regime': old_regime,
                     'new_regime': nation.regime_type,
                     'legitimacy_before': legitimacy_before,
                     'legitimacy_after': float(nation.legitimacy),
                     'seized_treasury_cash': float(seized),
                     'purged_member_count': int(purged),
                     'seizure_event_ids': seizure_event_ids},
             cause_event_ids=cause_event_ids or None)

    return {
        'turn': t,
        'general_id': general.id,
        'old_regime': old_regime,
        'new_regime': nation.regime_type,
        'seized': seized,
        'purged': purged,
        'deposed_faction': deposed,
    }


__all__ = ['find_generals', 'assess_coup', 'coup_chance', 'seize_treasury',
           'execute_coup', 'COUP_LEGITIMACY_TRIGGER', 'GENERAL_SCORE_MIN']

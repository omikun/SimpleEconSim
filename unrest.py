#!/usr/bin/env python3
"""
unrest.py — Escalation ladder + repression for Call of Capital M2.5/M2.6.

Pure gameplay logic consuming per-tile signals (factions, protest energy,
gov policy knobs) and generating CONSUMED/TRANSFERRED effects:

Escalation ladder (smooth pressure curves; realized events remain discrete):
  1. Unrest        : production efficiency drops (striker withholding).
  2. Protests      : agents withhold production (strike); exports slow.
  3. Mob / riots   : looted food moves to protestors; burned goods counted
                     as consumption; funds move to fundraiser agents —
                     NOTHING created, everything moves.
  4. Forced compromise : the government adopts the largest faction's top
                     demand (policy flip) or loses legitimacy sharply.
  5. Takeover      : if mob outnumbers + legitimacy collapsed, the popular
                     front replaces the regime (same regime-change seam).

Repression (M2.6): costs legitimacy + popularity, writes memory seeds
(mem_promises broken, mem_casualties) that raise FUTURE grievance.
"""

from __future__ import annotations

from goods import Goods
from random_cache import rand


#: Reference energy levels used by alerts and older callers.
UNREST_THRESHOLD = 2.0
PROTEST_THRESHOLD = 4.0
MOB_THRESHOLD = 6.5
COMPROMISE_THRESHOLD = 8.0
TAKEOVER_THRESHOLD = 9.5


def smoothstep(low: float, high: float, value: float) -> float:
    """Cubic response with zero slope at both ends of a pressure range."""
    x = max(0.0, min(1.0, (value - low) / (high - low)))
    return x * x * (3.0 - 2.0 * x)


def unrest_intensities(energy: float) -> dict[str, float]:
    """Continuous likelihood and scale for each kind of collective action."""
    return {
        'unrest': smoothstep(0.0, 4.0, energy),
        'protest': smoothstep(2.0, 6.5, energy),
        'mob': smoothstep(4.0, 9.0, energy),
        'compromise': smoothstep(6.5, 10.0, energy),
        'takeover': smoothstep(8.0, 10.0, energy),
    }


def _mob_size(region, t):
    """Estimate the mob: hungry + unemployed non-corp adults."""
    return sum(1 for a in region.agents
               if not a.is_corporation and not a.is_government
               and (a.hungry_steps > 0
                    or (a.age(t) > 20 and a.employer is None and not a.is_trader)))


def _loot_and_burn(region, t, mob):
    """Stage 3 effects: move food/wood/furniture from producers to the mob,
    and count a small fraction burned as consumption.  All transfers —
    nothing is created or destroyed beyond the consumption accounting."""
    looted_food = min(mob, sum(1 for a in region.agents
                               if not a.is_corporation
                               and a.inv_get(Goods.food) > 2))
    # Move 1 food per looted producer to the mob (conserved).
    producers = [a for a in region.agents
                 if not a.is_corporation and not a.is_government
                 and a.inv_get(Goods.food) > 4]
    recipients = [a for a in region.agents
                  if not a.is_corporation and not a.is_government
                  and a.hungry_steps > 0]
    moved = 0
    for p in producers:
        if moved >= looted_food or not recipients:
            break
        give = min(p.inv_get(Goods.food) - 4, 1)
        if give > 0:
            p.inv_add(Goods.food, -give)
            recipients[0].inv_add(Goods.food, give)
            moved += give
            recipients.pop(0)
            # Burned share: 1 furniture per 2 mob members counts as
            # consumption (existing consumption accounting consumes it).
            # Guard: recipients may have been exhausted by the pop above.
            if moved % 2 == 0 and recipients:
                burner = recipients[0]
                if burner.inv_get(Goods.furniture) > 0:
                    burner.inv_add(Goods.furniture, -1)
    return moved


def _forced_compromise(region, t):
    """Stage 4: flip the largest faction's top policy demand.

    Since the sim has no explicit 'policy' object beyond the Government
    knobs, the compromise is: set the largest grievance faction's top demand
    satisfied = 1.0 and record a legitimacy hit.  Returns the flipped demand
    name (for logging) or None.
    """
    factions = region.factions.factions
    if not factions:
        return None
    concessions = getattr(region, 'compromise_concessions', None)
    if concessions is None:
        concessions = set()
        region.compromise_concessions = concessions
    for faction in sorted(factions.values(), key=lambda f: f.total_grievance(), reverse=True):
        demand = next((d for d in faction.demands if d.name not in concessions), None)
        if demand is None:
            continue
        concessions.add(demand.name)
        demand.satisfied = 1.0
        if demand.name == 'tax_cut' and getattr(region, 'gov', None) is not None:
            region.gov.tax_rate = max(0.0, float(region.gov.tax_rate) - 0.03)
        # One concession has one political cost. Repeating a previously
        # granted demand cannot drain legitimacy every subsequent turn.
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            owner.legitimacy = max(0.0, owner.legitimacy - 0.04)
        return demand.name
    return None


def _takeover(region, t, mob):
    """Stage 5: popular-front takeover — requires overcoming local armed garrisons.

    If a military garrison is stationed on the tile, the crowd must overpower
    the armed soldiers. If the garrison repels the mob, casualties are inflicted
    and takeover fails.
    Returns True if a takeover fired.
    """
    owner = getattr(region, 'owner_nation', None)
    trace_subject = {'type': 'tile', 'id': getattr(region, 'name', 'unknown')}

    def emit_decision(success, reason_code, inputs, *, kind='takeover_decision'):
        from run_trace import emit
        return emit(
            region, kind=kind, record_class='outcome',
            subject=trace_subject, metric_id='politics.takeover_decision',
            unit='boolean', after=success,
            formula_id='unrest.takeover_force_gate.v1',
            inputs={'reason_code': reason_code, 'mob_size': mob,
                    'resident_count': len(getattr(region, 'agents', [])),
                    **inputs})

    if owner is None:
        emit_decision(False, 'no_nation_owner', {},
                      kind='takeover_attempt_failed')
        return False

    legitimacy = float(owner.legitimacy)
    resident_count = len(region.agents)
    crowd_share = mob / max(1, resident_count)
    legitimacy_pressure = 1.0 - smoothstep(0.10, 0.55, legitimacy)
    crowd_pressure = smoothstep(0.03, 0.20, crowd_share)
    attempt_chance = legitimacy_pressure * crowd_pressure
    attempt_draw = rand.random() if attempt_chance > 0 else None
    attempt_inputs = {
        'legitimacy': legitimacy,
        'legitimacy_pressure': legitimacy_pressure,
        'legitimacy_smoothstep_range': [0.10, 0.55],
        'crowd_share': crowd_share,
        'crowd_pressure': crowd_pressure,
        'crowd_smoothstep_range': [0.03, 0.20],
        'attempt_chance': attempt_chance,
        'attempt_draw': attempt_draw,
        'attempt_rng_stream': 'unrest.rand',
    }
    if attempt_draw is not None and attempt_draw < attempt_chance:
        # Garrison combat check: armed soldiers defend the state seat
        garrison_units = []
        garrison_force = 0.0
        for unit in getattr(region, 'military_units', []):
            soldiers = getattr(unit, 'soldiers', 0)
            if soldiers <= 0:
                continue
            morale = float(getattr(unit, 'morale', 1.0))
            strength = unit.strength
            morale_multiplier = smoothstep(0.0, 0.6, morale)
            contribution = strength * morale_multiplier
            garrison_force += contribution
            garrison_units.append({
                'unit_id': str(getattr(
                    unit, 'unit_id', getattr(unit, 'id', 'unknown'))),
                'soldiers': soldiers,
                'morale': morale,
                'strength': strength,
                'morale_multiplier': morale_multiplier,
                'force_contribution': contribution,
            })
        mob_force = mob * 1.5

        repel_chance = garrison_force / max(1.0, garrison_force + mob_force)
        repel_draw = rand.random() if repel_chance > 0 else None
        force_inputs = {
            **attempt_inputs,
            'garrison_units': garrison_units,
            'garrison_force': garrison_force,
            'mob_force': mob_force,
            'repel_chance': repel_chance,
            'repel_draw': repel_draw,
            'repel_rng_stream': 'unrest.rand',
        }
        if repel_draw is not None and repel_draw < repel_chance:
            # Garrison repels the insurrection!
            casualties = []
            for a in region.agents:
                if not a.is_corporation and not a.is_government and a.hungry_steps > 0:
                    a.mem_push('mem_casualties', 1.0)
                    a.mem_push('mem_promises', 0.5)
                    casualties.append(str(a.id))
            protest_before = None
            protest_after = None
            if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
                energy_before = region.protest_energy_log[-1]
                region.protest_energy_log[-1] = max(2.0, region.protest_energy_log[-1] - 2.5)
                protest_before = energy_before
                protest_after = region.protest_energy_log[-1]
                from run_trace import emit
                emit(region, kind='garrison_repels_takeover', record_class='outcome',
                     subject={'type': 'tile', 'id': region.name},
                     metric_id='politics.protest_energy', unit='score',
                     before=energy_before, after=region.protest_energy_log[-1],
                     formula_id='unrest.garrison_repel.v1',
                     inputs={'attempt_chance': attempt_chance, 'attempt_draw': attempt_draw,
                             'repel_chance': repel_chance, 'repel_draw': repel_draw,
                             'garrison_force': garrison_force, 'mob_force': mob_force})
            emit_decision(False, 'garrison_repels_mob', {
                **force_inputs,
                'seeded_casualty_agent_ids': casualties,
                'seeded_casualty_count': len(casualties),
                'protest_energy_before': protest_before,
                'protest_energy_after': protest_after,
            })
            return False

        # Garrison overwhelmed or disbanded
        legitimacy_before = owner.legitimacy
        owner.legitimacy = 0.0
        # regime_type flips toward the largest grievance faction kind
        biggest = max(region.factions.factions.values(),
                      key=lambda f: f.total_grievance())
        if biggest.kind == 'political':
            owner.regime_type = 'autocracy' if owner.regime_type == 'democracy' \
                else 'democracy'
        from run_trace import emit
        emit(region, kind='takeover_succeeded', record_class='outcome',
             subject={'type': 'nation', 'id': owner.name},
             metric_id='politics.legitimacy', unit='ratio',
             before=legitimacy_before, after=owner.legitimacy,
             inputs={'attempt_chance': attempt_chance, 'attempt_draw': attempt_draw,
                     'repel_chance': repel_chance, 'repel_draw': repel_draw,
                     'garrison_force': garrison_force, 'mob_force': mob_force,
                     'new_regime': owner.regime_type})
        emit_decision(True,
                      'garrison_overwhelmed' if garrison_force > 0
                      else 'no_garrison_defense', {
                          **force_inputs,
                          'legitimacy_before': legitimacy_before,
                          'legitimacy_after': owner.legitimacy,
                          'new_regime': owner.regime_type,
                          'leading_grievance_faction': biggest.name,
                          'leading_grievance_kind': biggest.kind,
                      })
        return True
    reason_code = ('attempt_chance_zero' if attempt_draw is None
                   else 'attempt_draw_rejected')
    emit_decision(False, reason_code, attempt_inputs,
                  kind='takeover_attempt_failed')
    return False


def step_unrest(region, t):
    """Draw a discrete event from smoothly increasing unrest intensities.

    Returns a dict describing what happened this turn, e.g.
    {'stage': 'mob', 'looted': N, 'legitimacy': 0.6, 'takeover': False}.
    """
    energy = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    events = {'stage': 'calm', 'looted': 0, 'takeover': False}

    mob = _mob_size(region, t)
    intensity = unrest_intensities(energy)
    events['intensities'] = intensity
    roll = rand.random() if intensity['unrest'] > 0 else 1.0
    effective_mob = max(1, round(mob * intensity['mob'])) if mob else 0

    if roll < intensity['takeover']:
        if _takeover(region, t, mob):
            events['stage'] = 'takeover'
            events['takeover'] = True
        else:
            events['stage'] = 'mob'        # mob without legitimacy collapse or repelled by garrison
            events['looted'] = _loot_and_burn(region, t, effective_mob)
    elif roll < intensity['compromise']:
        flipped = _forced_compromise(region, t)
        events['stage'] = 'compromise'
        events['flipped'] = flipped
    elif roll < intensity['mob']:
        events['stage'] = 'mob'
        events['looted'] = _loot_and_burn(region, t, effective_mob)
    elif roll < intensity['protest']:
        events['stage'] = 'protest'
    elif roll < intensity['unrest']:
        events['stage'] = 'unrest'

    # Record in a log for the viewer (pure state).
    region.unrest_log.append(events)
    from run_trace import emit
    emit(region, kind='unrest_roll', record_class='outcome',
         subject={'type': 'tile', 'id': region.name},
         metric_id='politics.unrest_event', unit='stage', after=events['stage'],
         formula_id='unrest.intensities.v1',
         inputs={'energy': energy, 'intensities': intensity, 'mob_size': mob,
                 'effective_mob': effective_mob, 'rng_draw': roll if intensity['unrest'] > 0 else None,
                 'rng_stream': 'unrest.rand', 'result': events})
    return events


def apply_repression(region, t, cost_legitimacy=0.15, force_override=False,
                     *, operation_id=None, trace_event_ids=None):
    """Quell protest via coercive force backed by standing garrisons or police.

    - Requires standing military units or employed police on the tile.
    - Physical clash inflicts casualties (mem_casualties) and breaks protest lines.
    - If no armed force is present, returns 0.
    """
    garrison_units = [u for u in getattr(region, 'military_units', []) if getattr(u, 'soldiers', 0) > 0]
    police_count = getattr(region, 'police_employed', 0)

    owner = getattr(region, 'owner_nation', None)
    legitimacy_before = (float(getattr(owner, 'legitimacy', 0.0))
                         if owner is not None else None)
    protest_log = getattr(region, 'protest_energy_log', None)
    protest_before = float(protest_log[-1]) if protest_log else None

    def emit_repression_outcome(outcome, seeded=0, seeded_agent_ids=()):
        from run_trace import emit

        legitimacy_after = (float(getattr(owner, 'legitimacy', 0.0))
                            if owner is not None else None)
        protest_after = (float(protest_log[-1]) if protest_log else None)
        grievance_total_after = sum(
            float(value)
            for faction in getattr(getattr(region, 'factions', None),
                                   'factions', {}).values()
            for value in getattr(faction, 'grievances', {}).values())
        clock = getattr(region, '_collective_trace_clock', {})
        event_operation_id = (operation_id or
                              f"repression:{getattr(region, 'name', 'unknown')}:{int(t)}:"
                              f"{int(clock.get('next', 0))}")
        event_id = emit(
            region, kind='repression_resolved', record_class='outcome',
            subject={'type': 'tile', 'id': region.name},
            metric_id='politics.repression', unit='agents',
            before=0, after=int(seeded),
            formula_id='unrest.apply_repression.v1',
            inputs={'operation_id': event_operation_id, 'turn': int(t),
                    'outcome': outcome, 'force_override': bool(force_override),
                    'police_employed': int(police_count),
                    'garrison_units': [
                        {'id': str(getattr(unit, 'unit_id',
                                           getattr(unit, 'name', index))),
                         'soldiers': int(getattr(unit, 'soldiers', 0)),
                         'strength': float(getattr(unit, 'strength', 0.0))}
                        for index, unit in enumerate(garrison_units)],
                    'legitimacy_cost_requested': float(cost_legitimacy),
                    'legitimacy_before': legitimacy_before,
                    'legitimacy_after': legitimacy_after,
                    'protest_energy_before': protest_before,
                    'protest_energy_after': protest_after,
                    'faction_grievance_total_before': grievance_total_before,
                    'faction_grievance_total_after': grievance_total_after,
                    'seeded_agent_ids': [str(agent_id)
                                         for agent_id in seeded_agent_ids],
                    'seeded_agent_count': int(seeded)})
        if event_id is not None and trace_event_ids is not None:
            trace_event_ids.append(event_id)
        return event_id

    grievance_total_before = sum(
        float(value)
        for faction in getattr(getattr(region, 'factions', None),
                               'factions', {}).values()
        for value in getattr(faction, 'grievances', {}).values())

    if not garrison_units and police_count == 0 and not force_override:
        emit_repression_outcome('no_force_available')
        return 0

    if owner is not None:
        owner.legitimacy = max(0.0, owner.legitimacy - cost_legitimacy)

    # Quell: cut each faction's most recent grievance adds
    for f in region.factions.factions.values():
        for k in list(f.grievances):
            f.grievances[k] *= 0.5

    # Reduce protest energy on tile
    if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
        region.protest_energy_log[-1] = max(0.0, region.protest_energy_log[-1] - 2.0)

    # Seed memory for casualties from armed dispersal
    seeded = 0
    seeded_agent_ids = []
    for f in region.factions.factions.values():
        for aid in list(f.membership):
            for a in region.agents:
                if a.id == aid:
                    a.mem_push('mem_casualties', 1.0)
                    a.mem_push('mem_promises', 1.0)
                    seeded += 1
                    seeded_agent_ids.append(a.id)
                    break
    emit_repression_outcome('repressed', seeded, seeded_agent_ids)
    return seeded


__all__ = ['step_unrest', 'apply_repression', 'smoothstep', 'unrest_intensities',
           'UNREST_THRESHOLD', 'PROTEST_THRESHOLD', 'MOB_THRESHOLD',
           'COMPROMISE_THRESHOLD', 'TAKEOVER_THRESHOLD']

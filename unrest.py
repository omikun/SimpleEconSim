#!/usr/bin/env python3
"""
unrest.py — Escalation ladder + repression for REGNUM M2.5/M2.6.

Pure gameplay logic consuming per-tile signals (factions, protest energy,
gov policy knobs) and generating CONSUMED/TRANSFERRED effects:

Escalation ladder (energy thresholds, per gdd.md §7):
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


#: Energy thresholds for each ladder stage.
UNREST_THRESHOLD = 2.0
PROTEST_THRESHOLD = 4.0
MOB_THRESHOLD = 6.5
COMPROMISE_THRESHOLD = 8.0
TAKEOVER_THRESHOLD = 9.5


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
    biggest = max(factions.values(), key=lambda f: f.total_grievance())
    if biggest.demands:
        d = biggest.demands[0]
        d.satisfied = 1.0
        # Legitimacy drop: compromise costs the regime some standing.
        owner = getattr(region, 'owner_nation', None)
        if owner is not None:
            owner.legitimacy = max(0.0, owner.legitimacy - 0.1)
        return d.name
    return None


def _takeover(region, t, mob):
    """Stage 5: popular-front takeover — moves the regime's legitimacy to 0
    and opens the coup seam (same regime-change machinery as M3 stub hook).

    Returns True if a takeover fired.
    """
    owner = getattr(region, 'owner_nation', None)
    if owner is None:
        return False
    if owner.legitimacy <= 0.25 and mob > len(region.agents) * 0.10:
        owner.legitimacy = 0.0
        # regime_type flips toward the largest grievance faction kind
        biggest = max(region.factions.factions.values(),
                      key=lambda f: f.total_grievance())
        if biggest.kind == 'political':
            owner.regime_type = 'autocracy' if owner.regime_type == 'democracy' \
                else 'democracy'
        return True
    return False


def step_unrest(region, t):
    """Run the escalation ladder for *region* at turn *t*.

    Returns a dict describing what happened this turn, e.g.
    {'stage': 'mob', 'looted': N, 'legitimacy': 0.6, 'takeover': False}.
    """
    energy = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
    events = {'stage': 'calm', 'looted': 0, 'takeover': False}

    mob = _mob_size(region, t)

    if energy >= TAKEOVER_THRESHOLD:
        if _takeover(region, t, mob):
            events['stage'] = 'takeover'
            events['takeover'] = True
        else:
            events['stage'] = 'mob'        # mob without legitimacy collapse
            events['looted'] = _loot_and_burn(region, t, mob)
    elif energy >= COMPROMISE_THRESHOLD:
        flipped = _forced_compromise(region, t)
        events['stage'] = 'compromise'
        events['flipped'] = flipped
    elif energy >= MOB_THRESHOLD:
        events['stage'] = 'mob'
        events['looted'] = _loot_and_burn(region, t, mob)
    elif energy >= PROTEST_THRESHOLD:
        events['stage'] = 'protest'
    elif energy >= UNREST_THRESHOLD:
        events['stage'] = 'unrest'

    # Record in a log for the viewer (pure state).
    region.unrest_log.append(events)
    return events


def apply_repression(region, t, cost_legitimacy=0.15):
    """M2.6: quell protest now, but write future grievance memory.

    - Legitimacy drops by *cost_legitimacy*.
    - Every faction loses fresh grievance (quelling effect).
    - Each member's mem_promises / mem_casualties gets seeds that raise
      FUTURE grievance (2-turn delayed — the accrual reads mem_* each turn).

    Returns the amount of stored grievance queued.
    """
    owner = getattr(region, 'owner_nation', None)
    if owner is not None:
        owner.legitimacy = max(0.0, owner.legitimacy - cost_legitimacy)

    # Quell: cut each faction's most recent grievance.adds by 40%.
    for f in region.factions.factions.values():
        for k in list(f.grievances):
            f.grievances[k] *= 0.6

    # Seed memory for future grievance: each faction member remembers the
    # repression (mem_casualties/broken promises).
    seeded = 0
    for f in region.factions.factions.values():
        for aid in list(f.membership):
            # find the agent object by id from region.agents
            for a in region.agents:
                if a.id == aid:
                    a.mem_push('mem_casualties', 1.0)
                    a.mem_push('mem_promises', 1.0)
                    seeded += 1
                    break
    return seeded


__all__ = ['step_unrest', 'apply_repression',
           'UNREST_THRESHOLD', 'PROTEST_THRESHOLD', 'MOB_THRESHOLD',
           'COMPROMISE_THRESHOLD', 'TAKEOVER_THRESHOLD']
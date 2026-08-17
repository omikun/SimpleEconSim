"""
migration.py — real agent movement for v3_wilderness (REGNUM).

M1.5 emitted a score-only migration intent log; this module turns that into
ACTUAL conserved movement.  Each turn, a claimed tile under pressure pushes a
bounded number of residents toward the best adjacent tile.  Every leg is a
pure transfer:

  - cash  : withdrawn from the origin bank / hand cash, carried to the dest,
  - goods : inventory moves with the agent,
  - citizenship: origin gov loses the citizen, dest gov gains it,
  - homeland: ``origin_nation`` NEVER changes (only citizenship moves) — this
    is what keeps the 50% claim rule meaningful.

Landing rules (locked with the user):
  - unclaimed tile   -> ``wilderness.enter_wilderness``: walletize cash,
                        is_homesteader=True.
  - claimed tile     -> ``wilderness.enter_claimed``: de-cash the tile's
                        currency, homesteader status LOST.
  - homesteading is a POOR person's route: company owners and wealthy agents
    never become homesteaders (they may still move between claimed tiles).

Cooldown: an agent cannot move again within ``MIGRATION_COOLDOWN`` turns
(``last_migration_turn``), preventing ping-pong between two tiles.

Conservation: origin-currency cash is walletized BEFORE the destination resets
``home_currency`` (enter_wilderness sets it to None, whose walletize no-ops),
so the withdrawn deposit stays visible to ``audit_currency_total``.
"""

import random
import forex as fx
import wilderness as wd


# Bounds for one turn of migration.
MIGRATION_COOLDOWN = 20            # turns an agent must wait between moves
# The M1.5 intent score saturates around 0-1.5 in practice (wage memory +
# a small price differential); 3.0 never fired, so no homesteaders ever
# appeared.  0.2 = any non-trivial distress starts pushing; per-tile max +
# cooldown keep movement bounded.
MIGRATION_PRESSURE_THRESHOLD = 0.2 # source ``_migration_intent_score`` gate
MIGRATION_MAX_PER_TILE = 3         # resignations per source tile per turn
# Homesteading is a poor person's route: agents with total wealth above this
# cap never settle wilderness (they may still move between claimed tiles).
MIGRATION_MAX_WEALTH = 60.0


def _homestead_eligible(agent):
    """May *agent* become a homesteader on an unclaimed tile?

    Ruling: company owners and wealthy agents never homestead — only the poor
    go the homesteader route.  ``company_owned`` marks the founder/owner of a
    corporation; ``wealth()`` is cash + deposits + inventory - debt.
    """
    if getattr(agent, 'company_owned', None) is not None:
        return False
    if getattr(agent, 'is_government', False):
        return False
    if getattr(agent, 'is_corporation', False):
        return False
    if agent.wealth() > MIGRATION_MAX_WEALTH:
        return False
    return True


def _pick_destination(source, agent):
    """Best adjacent tile for *agent* to move to (None if none qualify).

    Preference order:
      1. unclaimed wilderness neighbors (frontier homesteading) — ONLY if the
         agent is homestead-eligible (poor, not an owner);
      2. claimed neighbors NOT of the agent's origin nation (foreign move);
      3. claimed neighbors of the same nation (internal move, lowest pull).
    """
    best_wild = None
    best_foreign = None
    best_same = None
    for other in source.neighbors.values():
        if other is source:
            continue
        if getattr(other, 'wilderness', False):
            if best_wild is None:
                best_wild = other
            continue
        owner = getattr(other, 'owner_nation', None)
        me = getattr(agent, 'origin_nation', None)
        if owner is None:
            continue
        if owner.name != me:
            if best_foreign is None:
                best_foreign = other
        else:
            if best_same is None:
                best_same = other
    if best_wild is not None and _homestead_eligible(agent):
        return best_wild
    return best_foreign or best_same


def _withdraw_origin(origin, agent):
    """Empty the agent's deposit at the ORIGIN bank into hand cash (transfer).

    The destination re-registers the agent with its own bank; keeping the
    deposit at the origin would strand money at the old ledger.  Pure
    transfer — nothing is created or destroyed.
    """
    bank = getattr(origin, 'bank', None)
    if bank is None:
        return
    dep = bank.deposits.get(agent, 0)
    if dep > 0:
        bank.Withdraw(agent, dep)


def migrate_one(t, source, agent, destination):
    """Move *agent* from *source* to *destination* (conserved transfer).

    Rolls:
      1. withdraw the origin deposit into hand cash, then walletize the
         origin currency BEFORE the destination resets home_currency,
      2. detach from the source (agents list + citizenship),
      3. attach to the destination — homesteader status / wallet rules are
         handled by wilderness.enter_wilderness / enter_claimed,
      4. stamp the cooldown.
    Returns True on success.
    """
    # 1. Liquid cash: origin deposit -> hand cash (kept by the agent).
    #    Capture the origin currency FIRST - by the time enter_wilderness
    #    runs, home_currency is already None on a wilderness landing, so
    #    its walletize no-ops and the withdrawn cash would be stranded
    #    invisible to audit_currency_total (probe: a882 GA -51.29).
    # Origin tile's currency is authoritative (the agent physically held
    # cash there) - agent.home_currency may be None for legacy orphans.
    origin_currency = source.home_currency or getattr(agent, 'home_currency', None)
    _withdraw_origin(source, agent)
    if agent.cash > 0 and origin_currency:
        fx.walletize(agent, origin_currency)

    # 2. Detach from origin.
    if agent in source.agents:
        source.agents.remove(agent)
    origin_gov = getattr(source, 'gov', None)
    if origin_gov is not None:
        origin_gov.citizen_ids.discard(agent.id)

    # 3. Attach to destination: unclaimed -> homesteader; claimed ->
    #    homesteader status LOST + de-cash the destination currency.
    if getattr(destination, 'wilderness', False):
        wd.enter_wilderness(destination, agent, t)
    else:
        wd.enter_claimed(destination, agent, t)
        dest_gov = getattr(destination, 'gov', None)
        if dest_gov is not None:
            dest_gov._add_citizen(agent)

    # 4. Cooldown stamp.
    agent.last_migration_turn = t
    return True


def run_migrations(t, regions, rng=None):
    """One turn of real migration across *regions* (v3).

    For each CLAIMED tile whose ``_migration_intent_score()`` clears the
    pressure threshold, move up to ``MIGRATION_MAX_PER_TILE`` eligible
    residents toward the best adjacent tile.  Wilderness tiles never push
    (natives are a scalar; homesteaders stay put on their claim).

    Eligibility: adult (age>20) non-corp, non-gov, non-trader, unemployed
    residents past the cooldown.  Homesteader destinations additionally
    require the agent to be poor and not a company owner.

    Returns the list of migration events: {t, agent_id, from, to, via}.
    """
    rng = rng if rng is not None else random
    events = []
    for source in regions:
        if getattr(source, 'wilderness', False):
            continue
        if not source.agents:
            continue
        if getattr(source, 'gov', None) is None:
            continue
        score = source._migration_intent_score()
        if score < MIGRATION_PRESSURE_THRESHOLD:
            continue
        pool = [
            a for a in source.agents
            if getattr(a, 'alive', True)
            and not getattr(a, 'is_corporation', False)
            and not getattr(a, 'is_government', False)
            and not getattr(a, 'is_trader', False)
            and getattr(a, 'employer', None) is None
            and a.age(t) > 20
            and t - getattr(a, 'last_migration_turn', 0) >= MIGRATION_COOLDOWN
        ]
        if not pool:
            continue
        rng.shuffle(pool)
        moved = 0
        for agent in pool:
            if moved >= MIGRATION_MAX_PER_TILE:
                break
            dest = _pick_destination(source, agent)
            if dest is None:
                continue
            via = 'homestead' if getattr(dest, 'wilderness', False) else 'settle'
            if migrate_one(t, source, agent, dest):
                events.append({'t': t, 'agent_id': agent.id,
                               'from': source.name, 'to': dest.name,
                               'via': via})
                moved += 1
    return events
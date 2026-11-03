"""Delayed household migration after loss of viable local subsistence.

Goods and money move with real people. Movement is open unless an explicit
law restricts it; destination commons capacity is reserved before travel.
"""

import forex as fx
import wilderness as wd


MIGRATION_COOLDOWN = 20
MIGRATION_MAX_PER_TILE = 3


def _pick_destination(source, agent):
    """Compatibility query using the same explicit movement-law interface."""
    from foraging import capacity, commons_access
    candidates = [tile for tile in source.neighbors.values() if tile is not source
                  and not getattr(tile, 'is_ocean', False) and commons_access(tile) > 0
                  and movement_policy(source, tile, agent)[0]]
    return max(candidates, key=lambda tile: (capacity(tile), tile.name), default=None)


def _withdraw_origin(origin, agent, t=None):
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
        bank.Withdraw(agent, dep, trace_region=origin, t=t,
                      reason='migration_deposit_portability')


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
    if getattr(agent, 'military_unit_id', None):
        return False
    # 1. Liquid cash: origin deposit -> hand cash (kept by the agent).
    #    Capture the origin currency FIRST - by the time enter_wilderness
    #    runs, home_currency is already None on a wilderness landing, so
    #    its walletize no-ops and the withdrawn cash would be stranded
    #    invisible to audit_currency_total (probe: a882 GA -51.29).
    # Origin tile's currency is authoritative (the agent physically held
    # cash there) - agent.home_currency may be None for legacy orphans.
    origin_currency = source.home_currency or getattr(agent, 'home_currency', None)
    _withdraw_origin(source, agent, t=t)
    if agent.cash > 0 and origin_currency:
        fx.walletize(agent, origin_currency, trace_region=source, t=t)

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


def movement_policy(source, destination, person):
    """Future law interface: a declared restriction needs actual enforcement."""
    for tile in (source, destination):
        policy = getattr(tile, 'movement_policy', {})
        enforcement = max(0, min(1, float(policy.get('enforcement', 0))))
        restricted = policy.get('permit_required', False) and not getattr(person, 'movement_permit', False)
        if policy.get('closed', False) and enforcement >= 1:
            return False, 'denied_passage'
        if restricted and enforcement > 0:
            return False, 'deterred_by_movement_law'
    return True, 'permitted'


def arrive_subsistence_moves(t, regions):
    lookup = {r.name: r for r in regions}
    events = []
    for source in regions:
        pending = []
        for move in getattr(source, 'subsistence_journeys', []):
            if move['arrival_turn'] > t:
                pending.append(move)
                continue
            destination = lookup.get(move['destination'])
            if destination is None:
                pending.append(move)
                continue
            for person in list(source.agents):
                if person.id not in move['member_ids'] or not person.alive:
                    continue
                employer = getattr(person, 'employer', None)
                if employer is not None:
                    if person in employer.employees:
                        employer.employees.remove(person)
                    person.employer = None
                    agreement = getattr(person, 'labor_agreement', None)
                    if agreement:
                        agreement.active = False
                if migrate_one(t, source, person, destination):
                    person.previous_plot_id = person.assigned_plot_id
                    person.assigned_plot_id = None
                    person.subsistence_arrival_turn = t
                    person.subsistence_travel_work = .5
                    person.subsistence_journey = None
                    events.append({'t': t, 'agent_id': person.id, 'from': source.name,
                                   'to': destination.name, 'via': 'subsistence', 'planned': False})
                    from run_trace import emit
                    emit(source, kind='subsistence_migration_arrival', record_class='outcome',
                         subject={'type': 'agent', 'id': person.id, 'tile': source.name},
                         metric_id='people.migration', unit='people', after=1,
                         inputs={'destination': destination.name, 'arrival_turn': t,
                                 'departure_turn': move['departure_turn'], 'food_carried': person.inv_get(__import__('goods').Goods.food, 0)})
        source.subsistence_journeys = pending
    return events


def run_migrations(t, regions, rng=None):
    """Plan one-turn household moves after loss of viable local subsistence."""
    from households import rebuild, demand, human, food
    from nutrition import basic_food_units
    from foraging import capacity, commons_access, potential
    from career_transitions import working_adult, profession
    from run_trace import emit
    reserved = {}
    for source in regions:
        for move in getattr(source, 'subsistence_journeys', []):
            reserved[move['destination']] = reserved.get(move['destination'], 0) + move['meal_need']
    events = []
    for source in regions:
        rebuild(source, t)
        moved = 0
        for row in source.households.values():
            if moved >= MIGRATION_MAX_PER_TILE:
                break
            person = next((a for a in source.agents if a.id == row['buyer_id']), None)
            if person is None or not working_adult(person, t) or getattr(person, 'subsistence_journey', None):
                continue
            family = [a for a in source.agents if a.id in row['members'] and human(a)]
            meal_need = sum(basic_food_units(a) for a in family)
            # Use the actual closing gap and inability to buy the next meal.
            missing = max(0, meal_need - sum(food(a) for a in family))
            bank = getattr(source, 'bank', None)
            funds = person.cash + (bank.deposits.get(person, 0) if bank and not getattr(bank, 'is_frozen', False) else 0)
            price = max(.01, source.recipes[__import__('goods').Goods.food]['price'])
            local_food = sum(potential(a, source) for a in family)
            from food_access import food_surplus
            offered = sum(food_surplus(a, source) for a in source.agents if a not in family)
            purchased = min(offered, max(0, funds) / price)
            if not missing or purchased + local_food >= missing:
                continue
            if t - person.last_migration_turn < MIGRATION_COOLDOWN and person.last_migration_turn > 0:
                continue
            # A funded local vacancy is an avenue; speculative quotes are not.
            from labor_choice import evaluate_offer
            state = getattr(source, 'career_transition_state', {})
            old = profession(person)
            budget = state.get('budgets', {}).get(old.name if old else '', {})
            departure_possible = old is None or budget.get('used', 0) < budget.get('quota', 0)
            if purchased > 0 and departure_possible and any(
                   f.is_corporation and not getattr(f, 'business_closed', False)
                   and evaluate_offer(person, f, source, t, career_phase=True).accepted
                   and f.wage / price + local_food >= missing
                   for f in source.agents):
                continue
            choices = []
            for dest in sorted(source.neighbors.values(), key=lambda r: r.name):
                if dest is source or getattr(dest, 'is_ocean', False) or commons_access(dest) <= 0:
                    continue
                from terrain_edges import get_edge_manager
                edges = get_edge_manager()
                if edges is not None and edges.get_friction(source.name, dest.name) == float('inf'):
                    continue
                allowed, reason = movement_policy(source, dest, person)
                if not allowed:
                    source.subsistence_migration_log = [*getattr(source, 'subsistence_migration_log', []),
                        {'turn': t, 'person_id': person.id, 'destination': dest.name, 'reason': reason}][-100:]
                    continue
                local = sum(max(0, basic_food_units(a) - food(a)) for a in dest.agents if human(a))
                spare = capacity(dest, t) - local - reserved.get(dest.name, 0)
                if spare >= meal_need:
                    choices.append((spare, dest.name, dest))
            if not choices:
                continue
            _, _, destination = max(choices, key=lambda item: (item[0], item[1]))
            move = {'departure_turn': t, 'arrival_turn': t + 1, 'destination': destination.name,
                    'member_ids': list(row['members']), 'meal_need': meal_need,
                    'reason': 'commons_closed' if commons_access(source) <= 0 else 'local_subsistence_failed'}
            source.subsistence_journeys = [*getattr(source, 'subsistence_journeys', []), move]
            for member in family:
                member.subsistence_journey = dict(move)
            reserved[destination.name] = reserved.get(destination.name, 0) + meal_need
            emit(source, kind='subsistence_migration_planned', record_class='decision',
                 subject={'type': 'agent', 'id': person.id, 'tile': source.name},
                 metric_id='people.migration_intent', unit='people', after=len(family), inputs=move)
            events.append({'t': t, 'agent_id': person.id, 'from': source.name,
                           'to': destination.name, 'via': 'subsistence', 'planned': True})
            moved += 1
    return events

"""Scenario Caisse obligations backed by sovereign bonds and recorded receipts."""

from __future__ import annotations

from sovereign_bonds import SovereignBond, get_bond_market


PURPOSE = 'scenario_caisse'


def _nation(world, name):
    return next((nation for nation in world.get('nations', []) if nation.name == name), None)


def bonds(world):
    ids = set(world.get('scenario_state', {}).get('debt_bond_ids', []))
    return [bond for bond in get_bond_market().bonds if bond.bond_id in ids]


def outstanding(world):
    return round(sum(bond.principal for bond in bonds(world)
                     if bond.status in ('active', 'defaulted')), 2)


def initialize(world):
    state = world['scenario_state']
    from scenario_situation import situation_template
    amount = float(situation_template()['debt_rules'].get('initial_claim', state['scheduled_remittance']))
    due = int(state['payment_window_turn'])
    market = get_bond_market()
    ids = []
    for creditor in ('Britain', 'France'):
        bond_id = f'egypt_caisse_{creditor.lower()}'
        market.bonds[:] = [bond for bond in market.bonds if bond.bond_id != bond_id]
        market.bonds.append(SovereignBond(
            bond_id=bond_id, issuer_nation='Egypt', holder_nation=creditor,
            principal=round(amount / 2, 2), coupon_rate=0.0,
            duration_turns=int(world['scenario']['horizon_turns']), issued_turn=1,
            maturity_turn=int(world['scenario']['horizon_turns']) + 1,
            status='active', bond_purpose=PURPOSE,
        ))
        ids.append(bond_id)
    state['debt_bond_ids'] = ids
    state['debt_ledger'] = []
    state['assigned_revenues'] = {'tax': 0.25, 'tariff': 0.5, 'rail': 0.0, 'port': 0.0}
    state['collection_assignment'] = None
    state['debt_collection_turn'] = 0
    state['debt_collected_this_turn'] = 0.0
    egypt = _nation(world, 'Egypt')
    governments = {egypt.government}
    governments.update(tile.gov for tile in egypt.tiles if getattr(tile, 'gov', None))
    governments.update(province.gov for province in getattr(egypt, 'provinces', [])
                       if getattr(province, 'gov', None))
    for government in governments:
        government.scenario_debt_world = world


def _entry(world, kind, amount, **details):
    world['scenario_state'].setdefault('debt_ledger', []).append({
        'turn': int(world.get('turn', 0)), 'kind': kind,
        'amount': round(float(amount), 2), **details,
    })


def revise(world, amount, due_turn=None):
    """Change the unsettled obligation without creating or paying cash."""
    active = [bond for bond in bonds(world) if bond.status in ('active', 'defaulted')]
    if not active:
        return
    per_creditor = round(float(amount) / len(active), 2)
    remaining = round(float(amount), 2)
    for index, bond in enumerate(active):
        bond.principal = per_creditor if index < len(active) - 1 else remaining
        remaining -= bond.principal
    state = world['scenario_state']
    state['scheduled_remittance'] = round(float(amount), 2)
    if due_turn is not None:
        state['payment_window_turn'] = int(due_turn)
    _sync_registered_defaults(world)
    _entry(world, 'revision', amount, due_turn=state['payment_window_turn'])


def adjust_service(world, amount, due_turn=None):
    """Revise the next instalment and its matching share of bond principal."""
    state = world['scenario_state']
    old = float(state['scheduled_remittance'])
    new = round(max(0.0, float(amount)), 2)
    delta = new - old
    active = [bond for bond in bonds(world) if bond.status in ('active', 'defaulted')]
    if active and abs(delta) > .001:
        remaining = delta
        for index, bond in enumerate(active):
            share = round(delta / len(active), 2) if index < len(active) - 1 else remaining
            remaining -= share
            bond.principal = round(max(0.0, bond.principal + share), 2)
    state['scheduled_remittance'] = new
    if due_turn is not None:
        state['payment_window_turn'] = int(due_turn)
    _sync_registered_defaults(world)
    _entry(world, 'service_revision', new, due_turn=state['payment_window_turn'])


def write_down(world, amount):
    """Forgive a bounded portion of principal under an explicit concession."""
    active = [bond for bond in bonds(world) if bond.status in ('active', 'defaulted')]
    owed = sum(bond.principal for bond in active)
    amount = round(min(max(0.0, float(amount)), owed), 2)
    if amount <= 0.0:
        return 0.0
    remaining = amount
    for index, bond in enumerate(active):
        share = round(amount * bond.principal / owed, 2) if index < len(active) - 1 else remaining
        remaining -= share
        bond.principal = round(max(0.0, bond.principal - share), 2)
        _entry(world, 'concession', share, creditor=bond.holder_nation, bond_id=bond.bond_id)
        if bond.principal <= .01:
            bond.principal = 0.0
            bond.status = 'redeemed'
    _sync_registered_defaults(world)
    return amount


def reinstate_claim(world, amount, due_turn):
    """Restore the conditional part of a signed write-down after breach."""
    contracts = bonds(world)
    if not contracts:
        return
    remaining = round(float(amount), 2)
    for index, bond in enumerate(contracts):
        share = round(float(amount) / len(contracts), 2) if index < len(contracts) - 1 else remaining
        remaining -= share
        bond.principal = round(bond.principal + share, 2)
        bond.status = 'active'
    state = world['scenario_state']
    state['scheduled_remittance'] = outstanding(world)
    state['payment_window_turn'] = int(due_turn)
    _sync_registered_defaults(world)
    _entry(world, 'conditional_write_down_revoked', amount, due_turn=due_turn)


def set_collection_assignment(world, per_turn, origin):
    """Record who may intercept which actual receipts under signed terms."""
    state = world['scenario_state']
    cap = max(0.0, float(per_turn))
    remaining = outstanding(world)
    state['creditor_levy_per_turn'] = cap if remaining > .01 else 0.0
    state['creditor_levy_remaining'] = remaining if cap else 0.0
    state['collection_assignment'] = ({
        'status': 'active', 'origin': origin, 'signed_turn': int(world.get('turn', 0)),
        'sources': dict(state.get('assigned_revenues', {})), 'per_turn_cap': cap,
        'creditors': {bond.holder_nation: bond.principal for bond in bonds(world)
                      if bond.principal > 0},
    } if cap and remaining > .01 else None)


def pay(world, amount, kind='payment', forgive_remainder=False):
    """Transfer payment to actual holders; optionally write down the rest."""
    egypt = _nation(world, 'Egypt')
    contracts = [bond for bond in bonds(world) if bond.status in ('active', 'defaulted')]
    owed = sum(bond.principal for bond in contracts)
    amount = round(min(float(amount), owed), 2)
    if not contracts or egypt is None or egypt.government.agent.cash < amount:
        return False, 'The treasury cannot cover this debt payment.'
    remaining = amount
    for index, bond in enumerate(contracts):
        share = round(amount * bond.principal / owed, 2) if index < len(contracts) - 1 else remaining
        remaining -= share
        creditor = _nation(world, bond.holder_nation)
        if creditor is None:
            return False, f'{bond.holder_nation} creditor account is unavailable.'
        egypt.government.agent.cash -= share
        creditor.government.agent.cash += share
        bond.principal = round(max(0.0, bond.principal - share), 2)
        _entry(world, kind, share, creditor=creditor.name, bond_id=bond.bond_id)
        if bond.principal <= 0.01:
            bond.principal = 0.0
            bond.status = 'redeemed'
    if forgive_remainder:
        for bond in contracts:
            if bond.principal > 0:
                _entry(world, 'concession', bond.principal,
                       creditor=bond.holder_nation, bond_id=bond.bond_id)
                bond.principal = 0.0
            bond.status = 'redeemed'
    _sync_registered_defaults(world)
    state = world['scenario_state']
    if outstanding(world) <= .01:
        state['scheduled_remittance'] = 0.0
        state['creditor_levy_per_turn'] = 0.0
        state['creditor_levy_remaining'] = 0.0
        if state.get('collection_assignment'):
            state['collection_assignment']['status'] = 'discharged'
    return True, ''


def _sync_registered_defaults(world):
    from imperialism import get_imperialism_manager
    by_id = {bond.bond_id: bond for bond in bonds(world)}
    for entry in get_imperialism_manager().delinquent_defaults:
        bond = by_id.get(entry.get('bond_id'))
        if bond is not None:
            entry['principal'] = bond.principal
            if bond.status == 'redeemed':
                entry['status'] = 'settled_by_scenario'


def default(world):
    from imperialism import get_imperialism_manager
    manager = get_imperialism_manager()
    existing = {item['bond_id'] for item in manager.delinquent_defaults}
    for bond in bonds(world):
        if bond.status == 'active':
            bond.status = 'defaulted'
        if bond.bond_id not in existing:
            manager.register_default(bond, world, int(world['turn']))
    _entry(world, 'default', outstanding(world))


def intercept_assigned_revenue(world, government, source, gross, turn):
    """Intercept only money actually received by an Egyptian government."""
    state = world.get('scenario_state', {})
    if state.get('ending') or float(state.get('creditor_levy_per_turn', 0.0)) <= 0:
        return 0.0
    assignment = state.get('collection_assignment')
    if assignment is not None and assignment.get('status') != 'active':
        return 0.0
    sources = assignment['sources'] if assignment else state.get('assigned_revenues', {})
    if source not in sources:
        return 0.0
    if state.get('debt_collection_turn') != turn:
        state['debt_collection_turn'] = turn
        state['debt_collected_this_turn'] = 0.0
    room = max(0.0, float(assignment['per_turn_cap'] if assignment else state['creditor_levy_per_turn'])
               - float(state.get('debt_collected_this_turn', 0.0)))
    share = float(sources[source])
    amount = round(min(float(gross) * share, room, outstanding(world),
                       max(0.0, government.agent.cash)), 6)
    if amount <= 0:
        return 0.0
    contracts = [bond for bond in bonds(world) if bond.status in ('active', 'defaulted')]
    owed = sum(bond.principal for bond in contracts)
    unpaid = amount
    for index, bond in enumerate(contracts):
        allocation = round(amount * bond.principal / owed, 6) if index < len(contracts) - 1 else unpaid
        unpaid -= allocation
        creditor = _nation(world, bond.holder_nation)
        if creditor is None:
            continue
        government.agent.cash -= allocation
        creditor.government.agent.cash += allocation
        bond.principal = round(max(0.0, bond.principal - allocation), 6)
        _entry(world, 'assigned_revenue', allocation, turn=turn, source=source,
               creditor=creditor.name, bond_id=bond.bond_id)
        if bond.principal <= 0.01:
            bond.principal = 0.0
            bond.status = 'redeemed'
    state['debt_collected_this_turn'] = round(state['debt_collected_this_turn'] + amount, 6)
    state['creditor_levy_remaining'] = outstanding(world)
    state['scheduled_remittance'] = outstanding(world)
    if assignment:
        assignment['creditors'] = {bond.holder_nation: bond.principal for bond in bonds(world)
                                   if bond.principal > 0}
    if state['creditor_levy_remaining'] <= 0.01:
        state['creditor_levy_per_turn'] = 0.0
        state['payment_status'] = 'paid'
        if state.get('collection_assignment'):
            state['collection_assignment']['status'] = 'discharged'
    _sync_registered_defaults(world)
    return amount


def collected_this_turn(world):
    state = world.get('scenario_state', {})
    return float(state.get('debt_collected_this_turn', 0.0)) if state.get('debt_collection_turn') == world.get('turn') else 0.0

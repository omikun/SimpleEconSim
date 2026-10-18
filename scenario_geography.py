"""Strategic Egyptian sites, canal access, and supplied naval squadrons.

Sites are anchored to generated tiles. The route graph is deliberately small:
Guided play issues strategic orders while the shared terrain remains procedural.
"""

from __future__ import annotations


def _trace_canal_toll(world, payer, payee, *, amount, turn, origin, destination,
                      total_before, total_after, payer_before, payer_after,
                      payee_before, payee_after):
    """Record the simulated canal toll, including its unconverted currency legs."""
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract
    from run_trace import emit

    trace_region = next((tile for tile in getattr(payee, 'tiles', [])
                         if getattr(tile, '_run_trace', None) is not None), None)
    if trace_region is None:
        trace_region = next((tile for tile in world.get('tiles', [])
                             if getattr(tile, '_run_trace', None) is not None), None)
    if trace_region is None:
        return None

    payer_currency = getattr(payer, 'currency', None) or 'local_currency'
    payee_currency = getattr(payee, 'currency', None) or 'local_currency'
    operation_id = (f'canal-toll:{int(turn)}:{payer.name}:{origin}:{destination}:'
                    f'{float(total_before):.6f}')
    payer_cash = account_ref(
        'government_treasury', payer.government.name, payer_currency,
        nation_id=payer.name, subaccount='government_agent.cash',
        balance_before=float(payer_before), balance_after=float(payer_after),
        balance_scope='government_agent.cash')
    payee_cash = account_ref(
        'government_treasury', payee.government.name, payee_currency,
        nation_id=payee.name, subaccount='government_agent.cash',
        balance_before=float(payee_before), balance_after=float(payee_after),
        balance_scope='government_agent.cash')
    currency_details = {
        'counterparty_currency': payee_currency,
        'counterparty_currency_mismatch': payer_currency != payee_currency,
        'currency_conversion_applied': False,
        'mutation_reference': {'turn': int(turn), 'origin': origin,
                               'destination': destination},
    }
    common = {
        'amount': float(amount), 'amount_currency': payer_currency,
        'payer_account': payer_cash,
        'payee_account': payee_cash, 'local_cash_leg_amount': float(amount),
        'counterparty_leg_status': 'both_treasury_balances_recorded',
        **currency_details,
    }
    payer_contract = transfer_contract(
        operation_id, 'canal_transit_toll', side='payer',
        local_cash_leg_currency=payer_currency, **common)
    payee_contract = transfer_contract(
        operation_id, 'canal_transit_toll', side='payee',
        local_cash_leg_currency=payee_currency, **common)
    payer_event_id = emit_treasury_leg(
        trace_region, kind='canal_transit_toll_payment',
        nation_name=payer.name, currency=payer_currency,
        signed_amount=-float(amount), contract=payer_contract,
        phase='scenario_geography',
        inputs={'turn': int(turn), 'origin': origin,
                'destination': destination, 'operation_id': operation_id})
    payee_event_id = emit_treasury_leg(
        trace_region, kind='canal_transit_toll_receipt',
        nation_name=payee.name, currency=payee_currency,
        signed_amount=float(amount), contract=payee_contract,
        phase='scenario_geography',
        inputs={'turn': int(turn), 'origin': origin,
                'destination': destination, 'operation_id': operation_id})
    causes = [event_id for event_id in (payer_event_id, payee_event_id)
              if event_id is not None]
    return emit(
        trace_region, kind='canal_transit_toll_assessment',
        record_class='outcome', phase='scenario_geography',
        subject={'type': 'nation_pair/operation', 'id': operation_id},
        metric_id='finance.canal_toll', unit=payer_currency,
        before=float(total_before), after=float(total_after),
        formula_id='scenario.canal_transit_toll.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'payer_nation': payer.name, 'payee_nation': payee.name,
                'origin': origin, 'destination': destination,
                'amount': float(amount), 'amount_currency': payer_currency,
                'payer_balance_before': float(payer_before),
                'payer_balance_after': float(payer_after),
                'payee_balance_before': float(payee_before),
                'payee_balance_after': float(payee_after),
                'currency_conversion_applied': False,
                'counterparty_currency_mismatch': payer_currency != payee_currency},
        cause_event_ids=causes or None)


ROUTES = {
    'Mediterranean': ('Alexandria', 'Port Said'),
    'Alexandria': ('Mediterranean', 'Nile Delta'),
    'Port Said': ('Mediterranean', 'Ismailia'),
    'Ismailia': ('Port Said', 'Tel el Kebir'),
    'Tel el Kebir': ('Ismailia', 'Cairo'),
    'Nile Delta': ('Alexandria', 'Cairo'),
    'Cairo': ('Nile Delta', 'Tel el Kebir', 'Upper Egypt'),
    'Upper Egypt': ('Cairo',),
}


def initialize(world):
    egypt = next(n for n in world['nations'] if n.name == 'Egypt')
    locations = {getattr(tile, 'scenario_location', ''): tile for tile in egypt.tiles}
    required = ('Alexandria', 'Nile Delta', 'Cairo', 'Upper Egypt')
    if any(name not in locations for name in required):
        raise ValueError('The Egypt campaign needs its coastal and Nile corridor tiles.')
    delta = locations['Nile Delta']
    cairo = locations['Cairo']
    # The named canal sites are strategic points on the existing Delta/Cairo
    # corridor; they do not claim additional generated land tiles.
    sites = {name: {'tile': tile.name, 'position': tuple(tile.centroid)}
             for name, tile in locations.items() if name in ROUTES}
    dx, dy = delta.centroid
    cx, cy = cairo.centroid
    sites['Port Said'] = {'tile': delta.name,
                         'position': (dx + 0.35 * abs(dx - cx), dy - 0.10 * abs(dy - cy))}
    sites['Ismailia'] = {'tile': delta.name,
                         'position': (dx + 0.25 * abs(dx - cx), (dy + cy) / 2)}
    ismailia_x, ismailia_y = sites['Ismailia']['position']
    sites['Tel el Kebir'] = {'tile': locations['Nile Valley'].name,
                             'position': ((ismailia_x + cx) / 2 - .08 * abs(dx - cx),
                                          (ismailia_y + cy) / 2)}
    sites['Mediterranean'] = {'tile': None, 'position': None}
    world['scenario_state']['geography'] = {
        'sites': sites, 'routes': {name: list(edges) for name, edges in ROUTES.items()},
        'canal_open': True, 'canal_controller': 'Egypt', 'transit_rights': ['Egypt', 'Britain', 'France'],
        'canal_tolls_collected': 0.0, 'fleets': {}, 'diplomacy': {},
    }


def site(world, name):
    return world['scenario_state']['geography']['sites'][name]


def canal_access(world, nation_name):
    geography = world['scenario_state']['geography']
    return geography['canal_open'] and nation_name in geography['transit_rights']


def create_fleet(world, nation_name, *, ships=4, guns=80, coal=5, transports=40):
    fleet = {'nation': nation_name, 'location': 'Mediterranean', 'ships': int(ships),
             'guns': float(guns), 'coal': int(coal), 'transports': int(transports),
             'supplied': True, 'damage': 0.0, 'movement': 1}
    world['scenario_state']['geography']['fleets'][nation_name] = fleet
    return fleet


def fleet_at(world, nation_name, location):
    fleet = world['scenario_state']['geography']['fleets'].get(nation_name)
    return bool(fleet and fleet['location'] == location and fleet['ships'] > 0
                and fleet['coal'] > 0 and fleet['supplied'])


def move_fleet(world, nation_name, destination):
    geography = world['scenario_state']['geography']
    fleet = geography['fleets'].get(nation_name)
    if not fleet or not fleet['supplied'] or fleet['coal'] <= 0:
        return False
    location = fleet['location']
    if destination not in geography['routes'].get(location, ()):
        return False
    if destination in ('Tel el Kebir', 'Cairo', 'Nile Delta', 'Upper Egypt'):
        return False  # These are army routes, not navigable fleet positions.
    if destination == 'Ismailia' and not canal_access(world, nation_name):
        return False
    toll_event_id = None
    origin = fleet['location']
    if destination == 'Ismailia' and nation_name != 'Egypt':
        payer = next((n for n in world['nations'] if n.name == nation_name), None)
        egypt = next((n for n in world['nations'] if n.name == 'Egypt'), None)
        toll = 2.0
        if payer is None or egypt is None or payer.government.agent.cash < toll:
            return False
        payer_before = float(payer.government.agent.cash)
        egypt_before = float(egypt.government.agent.cash)
        total_before = float(geography['canal_tolls_collected'])
        payer.government.agent.cash -= toll
        egypt.government.agent.cash += toll
        geography['canal_tolls_collected'] += toll
        toll_event_id = _trace_canal_toll(
            world, payer, egypt, amount=toll,
            turn=int(world.get('turn', 0)), origin=origin,
            destination=destination, total_before=total_before,
            total_after=float(geography['canal_tolls_collected']),
            payer_before=payer_before,
            payer_after=float(payer.government.agent.cash),
            payee_before=egypt_before,
            payee_after=float(egypt.government.agent.cash))
    coal_before = int(fleet['coal'])
    fleet['coal'] -= 1
    fleet['location'] = destination
    from run_trace import emit
    trace_region = next((tile for tile in world.get('tiles', [])
                         if getattr(tile, '_run_trace', None) is not None), None)
    if trace_region is None:
        for nation in world.get('nations', []):
            trace_region = next((tile for tile in getattr(nation, 'tiles', [])
                                 if getattr(tile, '_run_trace', None) is not None), None)
            if trace_region is not None:
                break
    emit(
        trace_region, kind='scenario_fleet_movement', record_class='outcome',
        phase='scenario_geography',
        subject={'type': 'nation/fleet', 'id': nation_name},
        metric_id='military.fleet_position', unit='site',
        before=origin, after=destination,
        formula_id='scenario.fleet_movement_gate.v1',
        inputs={'nation': nation_name, 'coal_before': coal_before,
                'coal_after': int(fleet['coal']), 'supplied': bool(fleet['supplied']),
                'toll_required': destination == 'Ismailia' and nation_name != 'Egypt',
                'toll_event_id': toll_event_id},
        cause_event_ids=([toll_event_id] if toll_event_id is not None else None))
    return True


def resupply(world, nation_name, amount=2):
    fleet = world['scenario_state']['geography']['fleets'].get(nation_name)
    if fleet and fleet['ships'] > 0:
        fleet['coal'] += int(amount)
        fleet['supplied'] = True


def foreign_decisions(world):
    """Foreign powers evaluate and record their crisis policies each turn."""
    from scenario_diplomacy import _evaluate, _trace_decision
    french, british, french_event_id, british_event_id = _evaluate(world)
    state = world['scenario_state']
    naval_stage = state.get('naval_crisis', {}).get('stage', 'none')
    ottoman_mediation = naval_stage in ('mobilizing', 'ultimatum', 'blockaded')
    ottoman = 'offer_mediation' if ottoman_mediation else 'observe'
    _trace_decision(
        world, actor='Ottoman Empire', decision='respond_to_foreign_crisis',
        policy=ottoman, cause_event_ids=([british_event_id]
                                         if british_event_id else
                                         [french_event_id]
                                         if french_event_id else None),
        inputs={
            'naval_crisis_stage': naval_stage,
            'candidates': [
                {'candidate': 'offer_mediation',
                 'eligible': ottoman_mediation,
                 'selected': ottoman_mediation,
                 'reason': ('active_naval_escalation'
                            if ottoman_mediation else
                            'no_active_naval_escalation')},
                {'candidate': 'observe', 'eligible': not ottoman_mediation,
                 'selected': not ottoman_mediation,
                 'reason': ('no_active_naval_escalation'
                            if not ottoman_mediation else
                            'mediation_offered_during_escalation')},
            ],
        })
    state['geography']['diplomacy'] = {
        'Britain': british,
        'France': french,
        'Ottoman Empire': ottoman,
    }
    return state['geography']['diplomacy']


def close_canal(world):
    state = world['scenario_state']
    geography = state['geography']
    if not geography['canal_open']:
        return False, 'The canal is already closed to foreign transit.'
    geography['canal_open'] = False
    geography['transit_rights'] = ['Egypt']
    state['creditor_confidence'] = max(0.0, state['creditor_confidence'] - 0.10)
    return True, 'Cairo closes foreign canal transit. British access is denied, while creditor confidence falls.'

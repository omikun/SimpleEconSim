"""Measured occupation, contested receipts, resistance, and withdrawal."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

from army import resolve_battle

OCCUPIED_RECEIPT_CAP = 20.0


def initialize(world):
    world['scenario_state']['occupation'] = {
        'formal_sovereign': 'Egypt', 'institutional_control': {'customs': 'Egypt', 'cabinet': 'Egypt'},
        'resistance': 0.10, 'collaboration': 0.10, 'boycott_until': 0,
        'strike_until': 0, 'garrison_supply_paid': 0.0, 'collected_this_turn': 0.0,
        'collection_turn': 0, 'revenue_ledger': [], 'events': [], 'capital_warning_resolved': False,
        'withdrawal_proposal': None, 'withdrawal_replies': [],
    }


def _nation(world, name):
    return next((nation for nation in world['nations'] if nation.name == name), None)


def _government_nation(world, government):
    for nation in world.get('nations', []):
        if getattr(nation, 'government', None) is government:
            return nation
    for tile in world.get('tiles', []):
        if getattr(tile, 'gov', None) is government:
            return getattr(tile, 'owner_nation', None)
    return None


def _trace_region(world, government, nation):
    for tile in world.get('tiles', []):
        if getattr(tile, 'gov', None) is government:
            return tile
    return next(iter(getattr(nation, 'tiles', [])), None)


def _emit_revenue_assessment(world, government, *, turn, source, amount,
                             operation_id=None, inputs=None, cause_event_ids=None):
    payer_nation = _government_nation(world, government)
    region = _trace_region(world, government, payer_nation)
    if region is None:
        return None
    from run_trace import emit
    currency = (getattr(payer_nation, 'currency', None)
                or getattr(region, 'home_currency', None) or 'local_currency')
    return emit(
        region, kind='occupation_revenue_assessment', record_class='calculation',
        phase='scenario_occupation',
        subject={'type': 'nation/operation',
                 'id': operation_id or f'{source}:{government.name}:{int(turn)}'},
        metric_id='finance.occupation_transfer', unit=currency,
        before=0.0, after=float(amount),
        formula_id='occupation.revenue_cap_and_resistance.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'source': source, 'amount': float(amount), **(inputs or {})},
        cause_event_ids=cause_event_ids)


def _record_occupation_cash_transfer(world, *, payer_nation, payee_nation,
                                     payer_government, payee_government,
                                     amount, turn, operation_id, source,
                                     payer_before, payee_before, inputs=None):
    """Trace both treasury legs and the exact occupation transfer."""
    if payer_nation is None:
        return []
    region = _trace_region(world, payer_government, payer_nation)
    if region is None:
        return []
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract
    payer_currency = (getattr(payer_nation, 'currency', None)
                      or getattr(region, 'home_currency', None) or 'local_currency')
    payee_currency = getattr(payee_nation, 'currency', None) or payer_currency
    payer_after = float(payer_government.agent.cash)
    payee_after = float(payee_government.agent.cash)
    payer_account = account_ref(
        'nation_treasury', payer_government.name, payer_currency,
        nation_id=payer_nation.name, subaccount='government_agent.cash',
        balance_before=float(payer_before), balance_after=payer_after,
        balance_scope='government_agent.cash')
    payee_account = account_ref(
        'nation_treasury', payee_government.name, payee_currency,
        nation_id=payee_nation.name, subaccount='government_agent.cash',
        balance_before=float(payee_before), balance_after=payee_after,
        balance_scope='government_agent.cash')
    common = {
        'amount': float(amount), 'amount_currency': payer_currency,
        'payer_account': payer_account, 'payee_account': payee_account,
        'local_cash_leg_amount': float(amount),
        'local_cash_leg_currency': payer_currency,
        'counterparty_leg_status': 'both_treasury_balances_captured',
        'counterparty_currency': payee_currency,
        'counterparty_currency_mismatch': payer_currency != payee_currency,
        'currency_conversion_applied': False,
        'mutation_reference': {'turn': int(turn), 'source': source,
                               'operation_id': operation_id}}
    payer_contract = transfer_contract(
        operation_id, 'occupation_revenue_or_settlement', side='payer', **common)
    payee_contract = transfer_contract(
        operation_id, 'occupation_revenue_or_settlement', side='payee', **common)
    payer_event_id = emit_treasury_leg(
        region, kind='occupation_treasury_payment',
        nation_name=payer_nation.name, currency=payer_currency,
        signed_amount=-float(amount), contract=payer_contract,
        phase='scenario_occupation',
        inputs={'source': source, 'turn': int(turn), **(inputs or {})})
    payee_event_id = emit_treasury_leg(
        region, kind='occupation_treasury_receipt',
        nation_name=payee_nation.name, currency=payee_currency,
        signed_amount=float(amount), contract=payee_contract,
        phase='scenario_occupation',
        inputs={'source': source, 'turn': int(turn), **(inputs or {})})
    causes = [event_id for event_id in (payer_event_id, payee_event_id)
              if event_id is not None]
    outcome_id = _emit_revenue_assessment(
        world, payer_government, turn=turn, source=source, amount=amount,
        operation_id=operation_id, inputs=inputs,
        cause_event_ids=causes or None)
    return causes + ([outcome_id] if outcome_id is not None else [])


def _settle_occupation_payment(world, *, source, amount, turn):
    egypt = _nation(world, 'Egypt')
    britain = _nation(world, 'Britain')
    if egypt is None or britain is None:
        return None
    occupation = world['scenario_state']['occupation']
    ordinal = sum(1 for row in occupation['revenue_ledger']
                  if row.get('turn') == int(turn) and row.get('source') == source)
    operation_id = (f'occupation-settlement:{source}:{egypt.name}:{britain.name}:'
                    f'{int(turn)}:{ordinal + 1}')
    egypt_government = egypt.government
    britain_government = britain.government
    egypt_before = float(egypt_government.agent.cash)
    britain_before = float(britain_government.agent.cash)
    _trace_cash_write = _trace_public_begin(None, egypt_government.agent)
    egypt_government.agent.cash -= float(amount)
    _trace_public_finish(_trace_cash_write, 'scenario_occupation:_settle_occupation_payment',
                         inputs={"source_writer": 'scenario_occupation.py:_settle_occupation_payment:2aed3b129d4110bd:1'})
    _trace_cash_write = _trace_public_begin(None, britain_government.agent)
    britain_government.agent.cash += float(amount)
    _trace_public_finish(_trace_cash_write, 'scenario_occupation:_settle_occupation_payment',
                         inputs={"source_writer": 'scenario_occupation.py:_settle_occupation_payment:9433aa31f016b821:1'})
    occupation['revenue_ledger'].append({
        'turn': int(turn), 'source': source, 'amount': float(amount),
        'holder': britain.name, 'operation_id': operation_id})
    _record_occupation_cash_transfer(
        world, payer_nation=egypt, payee_nation=britain,
        payer_government=egypt_government, payee_government=britain_government,
        amount=amount, turn=turn, operation_id=operation_id, source=source,
        payer_before=egypt_before, payee_before=britain_before,
        inputs={'settlement': True})
    return operation_id


def _event(world, message):
    state = world['scenario_state']['occupation']
    state['events'].append({'turn': int(world['turn']), 'text': message})
    world['scenario_feedback'] = message
    from scenario_history import record as record_history
    record_history(world, message, historical_parallel='British troops take Cairo' in message)
    from client.desktop.engine import ticker_push
    ticker_push(world, int(world['turn']), 'OCCUPATION', message, (218, 144, 105))


def intercept_revenue(world, government, source, gross, turn):
    """Seize a bounded share of receipts only where Britain holds an institution."""
    state = world.get('scenario_state', {})
    if state.get('ending') or 'occupation' not in state:
        return 0.0
    occupation = state['occupation']
    control = occupation['institutional_control']
    if source not in ('tariff', 'tax'):
        return 0.0
    control_key = 'customs' if source == 'tariff' else 'cabinet'
    controller = control.get(control_key)
    if controller != 'Britain':
        _emit_revenue_assessment(
            world, government, turn=turn, source=source, amount=0.0,
            inputs={'gross_receipt': float(gross), 'control_institution': control_key,
                    'institution_controller': controller,
                    'reason': 'institution_not_occupied'})
        return 0.0
    if occupation['collection_turn'] != turn:
        occupation['collection_turn'] = turn
        occupation['collected_this_turn'] = 0.0
    collected_before = float(occupation['collected_this_turn'])
    room = max(0.0, OCCUPIED_RECEIPT_CAP - occupation['collected_this_turn'])
    boycott = .25 if turn <= occupation['boycott_until'] else 1.0
    strike = .5 if turn <= occupation['strike_until'] else 1.0
    resistance = float(occupation['resistance'])
    port_damage = float(state.get('campaign', {}).get('infrastructure_damage', {}).get('Alexandria', 0.0))
    port_factor = (1 - port_damage) if source == 'tariff' else 1.0
    base_rate = .35 if source == 'tariff' else .20
    resistance_factor = 1 - .6 * resistance
    rate = base_rate * resistance_factor * boycott * strike * port_factor
    government_cash_before = float(government.agent.cash)
    amount = round(min(float(gross) * max(0, rate), room,
                       max(0, government.agent.cash)), 6)
    if amount <= 0:
        reason = ('collection_cap_reached' if room <= 0 else
                  'treasury_empty' if government_cash_before <= 0 else
                  'no_eligible_receipts')
        _emit_revenue_assessment(
            world, government, turn=turn, source=source, amount=0.0,
            inputs={'gross_receipt': float(gross), 'base_rate': base_rate,
                    'resistance': resistance,
                    'resistance_factor': resistance_factor,
                    'boycott_factor': boycott, 'strike_factor': strike,
                    'port_damage': port_damage, 'port_factor': port_factor,
                    'effective_rate': rate, 'collection_cap': OCCUPIED_RECEIPT_CAP,
                    'collected_before': collected_before, 'room': room,
                    'government_cash_before': government_cash_before,
                    'reason': reason})
        return 0.0
    britain = _nation(world, 'Britain')
    if britain is None:
        _emit_revenue_assessment(
            world, government, turn=turn, source=source, amount=0.0,
            inputs={'gross_receipt': float(gross), 'effective_rate': rate,
                    'reason': 'occupier_not_found'})
        return 0.0
    payer_nation = _government_nation(world, government)
    britain_government = britain.government
    britain_cash_before = float(britain_government.agent.cash)
    ordinal = sum(1 for row in occupation['revenue_ledger']
                  if row.get('turn') == int(turn) and row.get('source') == source)
    operation_id = (f'occupation-revenue:{getattr(payer_nation, "name", government.name)}:'
                    f'{source}:{int(turn)}:{ordinal + 1}')
    _trace_cash_write = _trace_public_begin(None, government.agent)
    government.agent.cash -= amount
    _trace_public_finish(_trace_cash_write, 'scenario_occupation:intercept_revenue',
                         inputs={"source_writer": 'scenario_occupation.py:intercept_revenue:7d0d1bf6a38ac115:1'})
    _trace_cash_write = _trace_public_begin(None, britain_government.agent)
    britain_government.agent.cash += amount
    _trace_public_finish(_trace_cash_write, 'scenario_occupation:intercept_revenue',
                         inputs={"source_writer": 'scenario_occupation.py:intercept_revenue:6e7f523f0d73fc60:1'})
    occupation['collected_this_turn'] += amount
    occupation['revenue_ledger'].append({'turn': turn, 'source': source, 'amount': amount,
                                         'holder': 'Britain', 'resistance': resistance,
                                         'operation_id': operation_id})
    transfer_inputs = {
        'gross_receipt': float(gross), 'base_rate': base_rate,
        'resistance': resistance, 'resistance_factor': resistance_factor,
        'boycott_factor': boycott, 'strike_factor': strike,
        'port_damage': port_damage, 'port_factor': port_factor,
        'effective_rate': rate, 'collection_cap': OCCUPIED_RECEIPT_CAP,
        'collected_before': collected_before,
        'collected_after': float(occupation['collected_this_turn']),
        'room_before': room, 'government_cash_before': government_cash_before,
        'government_cash_after': float(government.agent.cash)}
    _record_occupation_cash_transfer(
        world, payer_nation=payer_nation, payee_nation=britain,
        payer_government=government, payee_government=britain_government,
        amount=amount, turn=turn, operation_id=operation_id, source=source,
        payer_before=government_cash_before, payee_before=britain_cash_before,
        inputs=transfer_inputs)
    return amount


def claim_institutions(world):
    state = world['scenario_state']
    control = state['campaign']['territorial_control']
    institutions = state['occupation']['institutional_control']
    institutions['customs'] = 'Britain' if control.get('Alexandria') == 'Britain' else 'Egypt'
    institutions['cabinet'] = 'Britain' if control.get('Cairo') == 'Britain' else 'Egypt'
    if institutions['cabinet'] == 'Britain':
        state['fiscal_autonomy'] = min(float(state.get('fiscal_autonomy', 1)), .30)
    elif institutions['customs'] == 'Britain':
        state['fiscal_autonomy'] = min(float(state.get('fiscal_autonomy', 1)), .65)


def _occupying_units(world):
    return [unit for unit in _nation(world, 'Britain').military_units
            if unit.unit_id.startswith('guided_british_landing_') and unit.soldiers > 0]


def _occupation_action_state(world, occupation, egypt):
    britain = _nation(world, 'Britain')
    units = [unit for unit in getattr(britain, 'military_units', [])
             if str(getattr(unit, 'unit_id', '')).startswith('guided_british_landing_')]
    proposal = occupation.get('withdrawal_proposal')
    return {
        'resistance': float(occupation['resistance']),
        'collaboration': float(occupation['collaboration']),
        'boycott_until': int(occupation['boycott_until']),
        'strike_until': int(occupation['strike_until']),
        'withdrawal_proposal': dict(proposal) if proposal else None,
        'egypt_legitimacy': (float(egypt.legitimacy) if egypt is not None else None),
        'egypt_treasury_cash': (
            float(egypt.government.agent.cash) if egypt is not None else None),
        'civilian_casualty_counter': int(
            world.get('scenario_state', {}).get('campaign', {}).get(
                'civilian_casualties', 0)),
        'garrison_units': [
            {'unit_id': str(getattr(unit, 'unit_id', 'unknown')),
             'soldiers': int(getattr(unit, 'soldiers', 0))}
            for unit in units],
    }


def _trace_occupation_action(world, *, action_id, operation_id, turn,
                             success, reason, before, after, details=None):
    from run_trace import emit

    egypt = _nation(world, 'Egypt')
    region = _trace_region(world,
                           getattr(egypt, 'government', None), egypt)
    return emit(
        region, kind=('occupation_player_action_resolved' if success else
                      'occupation_player_action_rejected'),
        record_class='outcome' if success else 'decision',
        phase='occupation',
        subject={'type': 'nation/action',
                 'id': f'{getattr(egypt, "name", "Egypt")}:{action_id}',
                 'nation': getattr(egypt, 'name', 'Egypt'),
                 'action_id': action_id},
        metric_id='scenario.occupation_action', unit='success',
        before=0, after=int(bool(success)),
        formula_id='occupation.player_action.v1',
        inputs={'operation_id': operation_id, 'action_id': action_id,
                'turn': int(turn), 'success': bool(success), 'reason': reason,
                'state_before': before, 'state_after': after,
                **(details or {})})


def _occupation_action_operation_id(world, occupation, action_id, turn):
    egypt = _nation(world, 'Egypt')
    region = _trace_region(world,
                           getattr(egypt, 'government', None), egypt)
    clock = getattr(region, '_collective_trace_clock', None)
    if clock is not None:
        ordinal = int(clock.get('next', 1))
    else:
        ordinal = len(occupation.get('events', [])) + 1
    return f'occupation-action:{action_id}:{int(turn)}:{ordinal}'


def _move_occupation_force_to_cairo(world):
    egypt = _nation(world, 'Egypt')
    cairo = next(tile for tile in egypt.tiles if getattr(tile, 'scenario_location', '') == 'Cairo')
    for unit in _occupying_units(world):
        old = next((tile for tile in world['tiles'] if tile.name == unit.region_name), None)
        if old is not None and unit in getattr(old, 'military_units', []):
            old.military_units.remove(unit)
        if not hasattr(cairo, 'military_units'):
            cairo.military_units = []
        cairo.military_units.append(unit)
        unit.region_name = cairo.name


def reserve_occupation_window(world):
    """Keep several turns for occupied receipts and Egyptian responses."""
    state = world['scenario_state']
    if not any(owner == 'Britain' for owner in state['campaign']['territorial_control'].values()):
        return
    if state.get('occupation_start_turn') is None:
        state['occupation_start_turn'] = int(world['turn'])
    from scenario_egypt_1877 import ensure_campaign_horizon
    minimum = int(world['scenario'].get('occupation_min_turns', 5))
    ensure_campaign_horizon(world, state['occupation_start_turn'] + minimum - 1)


def advance(world):
    state = world['scenario_state']
    campaign = state['campaign']
    expedition = campaign['expedition']
    occupation = state['occupation']
    claim_institutions(world)
    held = [site for site, owner in campaign['territorial_control'].items() if owner == 'Britain']
    if not held:
        return
    reserve_occupation_window(world)
    britain = _nation(world, 'Britain')
    egypt = _nation(world, 'Egypt')
    units = _occupying_units(world)
    if not units:
        withdraw(world, 'Without a landing garrison Britain abandons its Egyptian foothold.', cause='unsustainable')
        return
    # Wages are paid by shared step_armies; this expedition supply cost is a
    # separate conserved transfer to households and can become unsustainable.
    from scenario_gunboat import _emit_naval_trace, _transfer_to_households
    supply = 2.0 + sum(unit.soldiers for unit in units) * .025
    supply_event_ids = []
    supply_before = float(occupation['garrison_supply_paid'])
    if not _transfer_to_households(
            world, britain, supply, source='british_occupation_garrison_supply',
            phase='occupation', trace_event_ids=supply_event_ids):
        unit_effects = []
        for unit in units:
            morale_before = float(unit.morale)
            soldiers_before = int(unit.soldiers)
            unit.morale = max(.1, unit.morale - .25)
            unit.soldiers = max(0, unit.soldiers - 3)
            unit_effects.append({'unit_id': unit.unit_id,
                                 'morale_before': morale_before,
                                 'morale_after': float(unit.morale),
                                 'soldiers_before': soldiers_before,
                                 'soldiers_after': int(unit.soldiers)})
        _emit_naval_trace(
            world, britain,
            kind='occupation_garrison_supply_failure', record_class='outcome',
            phase='occupation', subject={'type': 'scenario/nation', 'id': britain.name},
            metric_id='scenario.occupation_supply',
            inputs={'turn': int(world['turn']), 'supply_cost': supply,
                    'reason': 'treasury_or_recipient_unavailable',
                    'garrison_effects': unit_effects,
                    'garrison_withdraws': sum(unit.soldiers for unit in units) < 8},
            cause_event_ids=supply_event_ids or None)
        if sum(unit.soldiers for unit in units) < 8:
            withdraw(world, 'The occupying garrison runs short of supply and withdraws.',
                     cause='unsustainable',
                     cause_event_ids=supply_event_ids or None)
            return
    else:
        occupation['garrison_supply_paid'] += supply
        _emit_naval_trace(
            world, britain,
            kind='occupation_garrison_supply_outcome', record_class='outcome',
            phase='occupation', subject={'type': 'scenario/nation', 'id': britain.name},
            metric_id='scenario.occupation_supply', unit='cash',
            before=supply_before, after=float(occupation['garrison_supply_paid']),
            inputs={'turn': int(world['turn']), 'supply_cost': supply,
                    'cumulative_supply_paid_before': supply_before,
                    'cumulative_supply_paid_after': float(occupation['garrison_supply_paid'])},
            cause_event_ids=supply_event_ids or None)
    unrest = sum(float(getattr(tile, 'unrest_level', 0)) for tile in egypt.tiles) / max(1, len(egypt.tiles))
    movement = float(state.get('politics', {}).get('nationalist_movement', 0))
    injuries = int(campaign['civilian_casualties'])
    change = .025 + .025 * unrest + .025 * movement + min(.03, injuries * .005) - .04 * occupation['collaboration']
    occupation['resistance'] = min(1.0, max(0.0, occupation['resistance'] + change))
    if occupation['resistance'] >= .70:
        for unit in units:
            unit.soldiers = max(0, unit.soldiers - 1)
            unit.morale = max(.1, unit.morale - .03)
        _event(world, 'Egyptian resistance disrupts garrison supply and costs Britain troops.')
    proposal = occupation.get('withdrawal_proposal')
    if proposal and int(world['turn']) >= int(proposal['reply_turn']):
        egypt_cash = float(egypt.government.agent.cash)
        recent_receipts = (float(occupation['collected_this_turn'])
                           if occupation.get('collection_turn') == int(world['turn']) else 0.0)
        strained = recent_receipts < supply * .75 and occupation['resistance'] >= .35
        accepted = (occupation['resistance'] >= .60 or strained
                    or float(britain.government.agent.cash) < supply * 4)
        accepted = accepted and egypt_cash >= float(proposal['amount'])
        occupation['withdrawal_replies'].append({
            'turn': int(world['turn']), 'accepted': accepted,
            'resistance': round(float(occupation['resistance']), 3),
            'receipts': round(recent_receipts, 2), 'supply': round(supply, 2),
        })
        occupation['withdrawal_proposal'] = None
        if accepted:
            amount = float(proposal['amount'])
            _settle_occupation_payment(
                world, source='withdrawal_settlement', amount=amount,
                turn=int(world['turn']))
            withdraw(world, 'Britain accepts withdrawal terms as resistance and supply costs erode its position.',
                     cause='negotiated_withdrawal')
            _event(world, f'Britain accepts Cairo’s {amount:.0f}-unit withdrawal offer; Egyptian institutions return to local control.')
            return
        _event(world, 'Britain rejects Cairo’s withdrawal offer while the garrison can still collect and hold territory. No offer cash was spent.')
    if (expedition['stage'] == 'foothold' and not occupation['capital_warning_resolved']
            and 'Cairo' not in held and int(world['turn']) >= int(expedition.get('foothold_turn', world['turn'])) + 2
            and not world.get('scenario_warning_modal')):
        world['scenario_warning_modal'] = {'kind': 'capital_warning'}
        world['playing'] = False
        _event(world, 'The British foothold threatens Cairo. Choose how Egypt will defend the capital.')


def response_options(world):
    state = world['scenario_state']
    egypt = _nation(world, 'Egypt')
    return [
        {'id': 'defend_cairo', 'label': 'Defend Cairo', 'enabled': True,
         'tooltip': 'Fight the British expedition at Cairo using any surviving Egyptian garrison; terrain and morale determine losses and control.'},
        {'id': 'evacuate_cairo', 'label': 'Evacuate the capital', 'enabled': True,
         'tooltip': 'Preserve the Egyptian army but give Britain control of Cairo and its tax administration.'},
        {'id': 'negotiate_capital', 'label': 'Offer withdrawal terms',
         'enabled': egypt.government.agent.cash >= 40,
         'tooltip': 'Pay 40 treasury units as a negotiated settlement. Britain leaves its foothold and fiscal autonomy recovers.'},
    ]


def resolve_capital(world, response_id):
    if world.get('scenario_warning_modal', {}).get('kind') != 'capital_warning':
        return False, 'No capital defense decision is pending.'
    option = next((item for item in response_options(world) if item['id'] == response_id), None)
    if not option or not option['enabled']:
        return False, 'That defense order is unavailable.'
    state = world['scenario_state']
    occupation = state['occupation']
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    occupation['capital_warning_resolved'] = True
    if response_id == 'negotiate_capital':
        _settle_occupation_payment(
            world, source='postwar_settlement', amount=40.0,
            turn=int(world['turn']))
        state['payment_status'] = 'restructured'
        withdraw(world, 'Cairo negotiates a postwar settlement; Britain withdraws from Egyptian territory.', cause='settlement')
    elif response_id == 'evacuate_cairo':
        state['campaign']['territorial_control']['Cairo'] = 'Britain'
        _move_occupation_force_to_cairo(world)
        claim_institutions(world)
        _event(world, 'The Egyptian cabinet evacuates Cairo; Britain controls the tax office and the port.')
    else:
        attackers = _occupying_units(world)
        egypt = _nation(world, 'Egypt')
        cairo = next(tile for tile in egypt.tiles if getattr(tile, 'scenario_location', '') == 'Cairo')
        defenders = [unit for unit in getattr(cairo, 'military_units', [])
                     if unit.nation_name == 'Egypt' and unit.soldiers > 0]
        soldiers_before = sum(unit.soldiers for unit in attackers + defenders)
        attack_strength_before = sum(unit.strength for unit in attackers)
        defense_strength_before = sum(unit.strength for unit in defenders) * 1.35
        battle = resolve_battle(attackers, defenders, defense_bonus=1.35)
        from run_trace import emit
        emit(cairo, kind='war_battle_outcome', record_class='outcome', phase='scenario',
             subject={'type': 'tile', 'id': cairo.name,
                      'attacker': 'Britain', 'defender': 'Egypt'},
             metric_id='war.battle', unit='soldiers', before=soldiers_before,
             after=sum(unit.soldiers for unit in attackers + defenders),
             inputs={'attack_strength_before': attack_strength_before,
                     'defense_strength_before': defense_strength_before,
                     'defense_bonus': 1.35, 'location': 'Cairo', **battle})
        battle.update(location='Cairo', turn=int(world['turn']))
        state['campaign']['battles'].append(battle)
        if battle['winner'] == 'attacker':
            state['campaign']['territorial_control']['Cairo'] = 'Britain'
            emit(cairo, kind='war_territory_transfer', record_class='outcome', phase='scenario',
                 subject={'type': 'tile', 'id': cairo.name},
                 metric_id='war.territory_control', before='Egypt', after='Britain',
                 inputs={'battle_winner': battle['winner'], 'location': 'Cairo',
                         'operation': 'capital_defense'})
            _move_occupation_force_to_cairo(world)
            claim_institutions(world)
            _event(world, f'British troops take Cairo; British losses {battle["atk_losses"]}, Egyptian losses {battle["def_losses"]}.')
        else:
            _event(world, f'Cairo repels the British advance; British losses {battle["atk_losses"]}, Egyptian losses {battle["def_losses"]}.')
            if sum(unit.soldiers for unit in attackers) < 8:
                withdraw(world, 'British losses force withdrawal from Egypt.', cause='military_defeat')
    record_change(world, response_id, before, snapshot(world))
    state.setdefault('actions_taken', []).append({'turn': int(world['turn']), 'action': response_id,
                                                   'message': world['scenario_feedback']})
    return True, world['scenario_feedback']


def withdraw(world, reason, *, cause='other', cause_event_ids=None):
    state = world['scenario_state']
    state['campaign']['territorial_control'].clear()
    state['occupation_start_turn'] = None
    state['campaign']['expedition']['stage'] = 'withdrawn'
    for unit in list(_occupying_units(world)):
        _nation(world, 'Britain').military_units.remove(unit)
        tile = next((t for t in world['tiles'] if t.name == unit.region_name), None)
        if tile and unit in getattr(tile, 'military_units', []):
            tile.military_units.remove(unit)
    claim_institutions(world)
    state['fiscal_autonomy'] = max(.55, float(state.get('fiscal_autonomy', 0)))
    from scenario_gunboat import withdraw as naval_withdraw
    naval_withdraw(world, reason, cause=cause,
                   cause_event_ids=cause_event_ids)


def apply_action(world, action_id):
    state = world['scenario_state']
    occupation = state['occupation']
    turn = int(world['turn'])
    operation_id = _occupation_action_operation_id(
        world, occupation, action_id, turn)
    egypt = _nation(world, 'Egypt')
    before = _occupation_action_state(world, occupation, egypt)
    held = any(owner == 'Britain' for owner in state['campaign']['territorial_control'].values())
    if not held:
        _trace_occupation_action(
            world, action_id=action_id, operation_id=operation_id, turn=turn,
            success=False, reason='no_foreign_garrison_to_confront',
            before=before, after=before, details={'foreign_territory_held': False})
        return False, 'There is no foreign garrison to confront.'
    details = {'foreign_territory_held': True}
    if action_id == 'organize_boycott':
        occupation['boycott_until'] = int(world['turn']) + 2
        occupation['resistance'] = min(1.0, occupation['resistance'] + .12)
        details.update({
            'resistance_rule': 'min(1.0, resistance_before + 0.12)',
            'boycott_until_rule': 'turn + 2',
            'receipt_effect_window_turns': 2})
        message = 'Egyptian merchants boycott occupied customs; receipts available to Britain shrink for two turns.'
    elif action_id == 'call_general_strike':
        occupation['strike_until'] = int(world['turn']) + 2
        occupation['resistance'] = min(1.0, occupation['resistance'] + .15)
        egypt.legitimacy = min(1.0, egypt.legitimacy + .03)
        details.update({
            'resistance_rule': 'min(1.0, resistance_before + 0.15)',
            'strike_until_rule': 'turn + 2',
            'legitimacy_rule': 'min(1.0, legitimacy_before + 0.03)',
            'receipt_effect_window_turns': 2})
        message = 'A general strike disrupts occupied tax and customs offices for two turns.'
    elif action_id == 'coordinate_insurgency':
        units = _occupying_units(world)
        if not units:
            _trace_occupation_action(
                world, action_id=action_id, operation_id=operation_id, turn=turn,
                success=False, reason='no_occupation_force_in_reach',
                before=before, after=before, details=details)
            return False, 'There is no occupation force in reach.'
        selected_unit = units[0]
        unit_id = str(getattr(selected_unit, 'unit_id', 'unknown'))
        soldiers_before = int(selected_unit.soldiers)
        selected_unit.soldiers = max(0, selected_unit.soldiers - 3)
        occupation['resistance'] = min(1.0, occupation['resistance'] + .18)
        egypt.legitimacy = max(0.0, egypt.legitimacy - .03)
        casualties_before = int(state['campaign'].get('civilian_casualties', 0))
        state['campaign']['civilian_casualties'] += 1
        details.update({
            'selected_garrison_unit_id': unit_id,
            'selected_unit_soldiers_before': soldiers_before,
            'selected_unit_soldiers_after': int(selected_unit.soldiers),
            'soldier_loss_rule': 'max(0, soldiers_before - 3)',
            'resistance_rule': 'min(1.0, resistance_before + 0.18)',
            'legitimacy_rule': 'max(0.0, legitimacy_before - 0.03)',
            'civilian_casualty_counter_before': casualties_before,
            'civilian_casualty_counter_after': int(
                state['campaign']['civilian_casualties']),
            'civilian_casualty_counter_increment': 1})
        message = 'Insurgents cost the British garrison three troops; one civilian is injured and legitimacy falls.'
    elif action_id == 'collaborate_with_occupation':
        occupation['collaboration'] = min(1.0, occupation['collaboration'] + .25)
        occupation['resistance'] = max(0.0, occupation['resistance'] - .18)
        egypt.legitimacy = max(0.0, egypt.legitimacy - .05)
        details.update({
            'collaboration_rule': 'min(1.0, collaboration_before + 0.25)',
            'resistance_rule': 'max(0.0, resistance_before - 0.18)',
            'legitimacy_rule': 'max(0.0, legitimacy_before - 0.05)'})
        message = 'Local collaboration calms resistance but reduces Egyptian legitimacy and strengthens occupation.'
    elif action_id == 'negotiate_withdrawal':
        cost = 30.0
        if egypt.government.agent.cash < cost:
            _trace_occupation_action(
                world, action_id=action_id, operation_id=operation_id, turn=turn,
                success=False, reason='insufficient_egyptian_treasury_cash',
                before=before, after=before,
                details={**details, 'required_cash': cost,
                         'egypt_treasury_cash_before': float(
                             egypt.government.agent.cash),
                         'cash_paid_now': 0.0})
            return False, 'The treasury needs 30 units for withdrawal terms.'
        if occupation.get('withdrawal_proposal'):
            _trace_occupation_action(
                world, action_id=action_id, operation_id=operation_id, turn=turn,
                success=False, reason='withdrawal_proposal_pending',
                before=before, after=before,
                details={**details, 'required_cash': cost,
                         'existing_proposal': dict(occupation['withdrawal_proposal']),
                         'egypt_treasury_cash_before': float(
                             egypt.government.agent.cash),
                         'cash_paid_now': 0.0})
            return False, 'Britain has not answered the current withdrawal offer.'
        occupation['withdrawal_proposal'] = {'turn': int(world['turn']),
                                             'reply_turn': int(world['turn']) + 1,
                                             'amount': cost}
        details.update({'required_cash': cost,
                        'egypt_treasury_cash_before': float(
                            egypt.government.agent.cash),
                        'cash_paid_now': 0.0,
                        'payment_status': 'proposal_only_no_cash_transfer',
                        'reply_turn': turn + 1})
        message = ('Cairo offers 30 units for a British withdrawal. London answers next turn; '
                   'cash transfers only if it accepts.')
    else:
        _trace_occupation_action(
            world, action_id=action_id, operation_id=operation_id, turn=turn,
            success=False, reason='unknown_occupation_decision',
            before=before, after=before, details=details)
        return False, 'Unknown occupation decision.'
    _event(world, message)
    after = _occupation_action_state(world, occupation, egypt)
    _trace_occupation_action(
        world, action_id=action_id, operation_id=operation_id, turn=turn,
        success=True, reason='occupation_action_applied',
        before=before, after=after, details=details)
    return True, message

"""The bounded naval escalation loop for the Egypt Guided situation.

This uses the shared blockade's trade effect and the campaign's supplied fleet.
"""

from __future__ import annotations

from macro.imperialism.manager import get_imperialism_manager
from scenario_geography import create_fleet, fleet_at, foreign_decisions, move_fleet, resupply
from scenario_situation import situation_template


def _nation(world: dict, name: str):
    return next((nation for nation in world.get('nations', []) if nation.name == name), None)


def _alexandria(egypt):
    return next((tile for tile in egypt.tiles
                 if getattr(tile, 'scenario_location', '') == 'Alexandria'), None)


def _protest(world: dict, name: str) -> float:
    report = next((entry for entry in world.get('scenario_state', {}).get('foreign_reports', [])
                   if entry['nation'] == name), None)
    return float(report['energy']) if report else 0.0


def _trace_region(world: dict, nation=None):
    candidates = list(getattr(nation, 'tiles', ())) if nation is not None else []
    candidates.extend(world.get('tiles', ()))
    return next((tile for tile in candidates
                 if (getattr(tile, '_run_trace', None) is not None
                     and getattr(tile, '_collective_trace_clock', None) is not None)), None)


def _emit_naval_trace(world: dict, nation=None, **event):
    region = _trace_region(world, nation)
    if region is None:
        return None
    from run_trace import emit
    return emit(region, **event)


def _transfer_to_households(world: dict, nation, amount: float, *, source: str,
                            turn: int | None = None, cause_event_ids=None,
                            trace_event_ids=None, phase: str = 'naval_crisis') -> bool:
    """Pay a scenario mobilization/supply cost to the first eligible resident."""
    turn = int(world.get('turn', 0) if turn is None else turn)
    trace_region = _trace_region(world, nation)
    trace_clock = (getattr(trace_region, '_collective_trace_clock', None)
                   if trace_region is not None else None)
    nation_name = getattr(nation, 'name', 'missing_nation')
    operation_id = (f'scenario-household-cost:{source}:{nation_name}:'
                    f'{turn}:{int(trace_clock.get("next", 0))}'
                    if trace_clock is not None else None)
    treasury = getattr(getattr(nation, 'government', None), 'agent', None)
    treasury_cash_before = float(getattr(treasury, 'cash', 0.0)) if treasury else None
    recipient = None
    recipient_tile = None
    reason = None
    if nation is None or treasury is None:
        reason = 'payer_nation_or_treasury_unavailable'
    elif treasury_cash_before < amount:
        reason = 'treasury_cash_below_cost'
    else:
        for tile in getattr(nation, 'tiles', ()):
            recipient = next((agent for agent in getattr(tile, 'agents', ())
                              if getattr(agent, 'alive', True)
                              and not getattr(agent, 'is_government', False)
                              and not getattr(agent, 'is_corporation', False)), None)
            if recipient is not None:
                recipient_tile = tile
                break
        if recipient is None:
            reason = 'no_eligible_household_recipient'
    funded = reason is None
    funding_event_id = _emit_naval_trace(
        world, nation,
        kind='scenario_household_cost_funding_decision',
        record_class='decision', phase=phase,
        subject={'type': 'scenario/nation', 'id': nation_name},
        metric_id='scenario.household_cost_funding',
        inputs={'operation_id': operation_id, 'turn': turn, 'source': source,
                'amount_requested': float(amount),
                'treasury_cash_before': treasury_cash_before,
                'cash_shortfall': max(0.0, float(amount)
                                      - (treasury_cash_before or 0.0)),
                'eligible_recipient_found': recipient is not None,
                'recipient_selection_rule': 'first living non-government non-corporation agent in nation tile order',
                'funded': funded,
                'reason': reason or 'treasury_and_recipient_available'},
        cause_event_ids=cause_event_ids)
    if funding_event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(funding_event_id)
    if not funded:
        outcome_id = _emit_naval_trace(
            world, nation,
            kind='scenario_household_cost_outcome',
            record_class='outcome', phase=phase,
            subject={'type': 'scenario/nation', 'id': nation_name},
            metric_id='scenario.household_cost_payment',
            inputs={'operation_id': operation_id, 'turn': turn, 'source': source,
                    'success': False, 'reason': reason,
                    'amount_requested': float(amount),
                    'cash_debited': 0.0, 'recipient_id': None},
            cause_event_ids=([funding_event_id] if funding_event_id else
                             cause_event_ids))
        if outcome_id is not None and trace_event_ids is not None:
            trace_event_ids.append(outcome_id)
        return False

    treasury_cash_before = float(treasury.cash)
    recipient_cash_before = float(recipient.cash)
    treasury.cash -= amount
    recipient.cash += amount
    treasury_cash_after = float(treasury.cash)
    recipient_cash_after = float(recipient.cash)
    payment_event_id = None
    if trace_region is not None:
        from finance_trace import account_ref, cash_transfer_contract, emit_cash_transfer
        currency = (getattr(nation, 'currency', None)
                    or getattr(recipient_tile, 'home_currency', None)
                    or 'local_currency')
        recipient_currency = (getattr(recipient, 'home_currency', None)
                              or currency)
        contract = cash_transfer_contract(
            operation_id, 'scenario_household_cost', amount=float(amount),
            currency=currency,
            payer_account=account_ref(
                'government_treasury', str(treasury.id), currency,
                nation_id=nation_name, balance_before=treasury_cash_before,
                balance_after=treasury_cash_after,
                balance_scope='government_agent.cash'),
            payee_account=account_ref(
                'agent_wallet', str(recipient.id), recipient_currency,
                agent_id=str(recipient.id), tile=recipient_tile.name,
                balance_before=recipient_cash_before,
                balance_after=recipient_cash_after,
                balance_scope='cash_wallet'),
            counterparty_leg_status='both_cash_wallets_captured',
            source=source, turn=turn)
        payment_event_id = emit_cash_transfer(
            trace_region, kind='scenario_household_cost_payment',
            contract=contract, phase=phase,
            subject={'type': 'tile/operation', 'id': operation_id,
                     'tile': recipient_tile.name},
            inputs={'turn': turn, 'source': source, 'nation': nation_name,
                    'recipient_id': str(recipient.id),
                    'recipient_tile': recipient_tile.name,
                    'amount_requested': float(amount),
                    'recipient_selection_rule':
                    'first living non-government non-corporation agent in nation tile order'},
            cause_event_ids=([funding_event_id] if funding_event_id else
                             cause_event_ids))
    if payment_event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(payment_event_id)
    outcome_id = _emit_naval_trace(
        world, nation,
        kind='scenario_household_cost_outcome',
        record_class='outcome', phase=phase,
        subject={'type': 'scenario/nation', 'id': nation_name},
        metric_id='scenario.household_cost_payment',
        before=treasury_cash_before, after=treasury_cash_after,
        unit=getattr(nation, 'currency', None) or 'local_currency',
        inputs={'operation_id': operation_id, 'turn': turn, 'source': source,
                'success': True, 'reason': 'paid_to_household_recipient',
                'amount_paid': float(amount),
                'treasury_cash_before': treasury_cash_before,
                'treasury_cash_after': treasury_cash_after,
                'recipient_id': str(recipient.id),
                'recipient_cash_before': recipient_cash_before,
                'recipient_cash_after': recipient_cash_after,
                'recipient_tile': recipient_tile.name,
                'payment_event_id': payment_event_id},
        cause_event_ids=([event_id for event_id in
                          (funding_event_id, payment_event_id) if event_id]
                         or cause_event_ids))
    if outcome_id is not None and trace_event_ids is not None:
        trace_event_ids.append(outcome_id)
    return True


def _record(world: dict, text: str, kind: str = 'NAVAL') -> None:
    state = world['scenario_state']
    state.setdefault('naval_news', []).append({'turn': int(world['turn']), 'text': text})
    world['scenario_feedback'] = text
    if kind == 'WAR':
        from scenario_history import record as record_history
        record_history(world, text, historical_parallel='Alexandria' in text)
    from client.desktop.engine import ticker_push
    ticker_push(world, int(world['turn']), kind, text, (230, 126, 95))


def begin_escalation(world: dict, reason: str) -> None:
    state = world['scenario_state']
    crisis = state.setdefault('naval_crisis', {'stage': 'none'})
    if crisis['stage'] not in ('none', 'withdrawn'):
        return
    crisis.update(stage='mobilizing', reason=reason, due_turn=int(world['turn']) + 1,
                  last_offer_turn=-1, french_support=False)
    state['naval_withdrawal_cause'] = None
    state.get('diplomatic_crisis', {})['policy_lock'] = None
    from scenario_egypt_1877 import enter_chapter_two
    enter_chapter_two(world, 'naval mobilization')
    _record(world, 'Cairo refused collection. Britain is weighing a naval expedition to Alexandria.')


def _remove_squadron(world: dict) -> None:
    state = world['scenario_state']
    crisis = state.get('naval_crisis', {})
    geography = state.get('geography', {})
    geography.get('fleets', {}).pop('Britain', None)
    geography.get('fleets', {}).pop('France', None)
    if crisis.get('port_tile'):
        manager = get_imperialism_manager()
        if manager.blockade_enforcers.get(crisis['port_tile']) == 'Britain':
            manager.lift_blockade(crisis['port_tile'], world, int(world['turn']))
    crisis['unit_id'] = None


def withdraw(world: dict, reason: str, *, cause: str = 'other',
             cause_event_ids=None) -> None:
    state = world['scenario_state']
    crisis = state['naval_crisis']
    stage_before = crisis.get('stage', 'none')
    fleets_before = {name: dict(fleet) for name, fleet in
                     state.get('geography', {}).get('fleets', {}).items()}
    _remove_squadron(world)
    crisis['stage'] = 'withdrawn'
    state['naval_withdrawal_cause'] = cause
    _record(world, reason)
    turn = int(world.get('turn', 0))
    trace_region = _trace_region(world)
    clock = (getattr(trace_region, '_collective_trace_clock', None)
             if trace_region is not None else None)
    operation_id = (f'naval-withdrawal:{turn}:{stage_before}:'
                    f'{int(clock.get("next", 0))}' if clock is not None else None)
    _emit_naval_trace(
        world, kind='naval_crisis_withdrawal', record_class='outcome',
        phase='naval_crisis',
        subject={'type': 'scenario', 'id': 'naval_crisis'},
        metric_id='scenario.naval_crisis_stage',
        before=stage_before, after=crisis['stage'],
        inputs={'operation_id': operation_id, 'turn': turn,
                'cause': cause, 'reason': reason,
                'fleet_state_before': fleets_before,
                'fleet_state_after': dict(state.get('geography', {}).get('fleets', {}))},
        cause_event_ids=cause_event_ids)


def coastal_balance(world: dict) -> dict:
    """Show the same force comparison used by mobilization and bombardment."""
    rules = situation_template()['naval_crisis']
    egypt = _nation(world, 'Egypt')
    alexandria = _alexandria(egypt) if egypt else None
    defenders = sum(float(getattr(unit, 'strength', 0.0))
                    for unit in getattr(alexandria, 'military_units', [])
                    if unit.nation_name == 'Egypt') if alexandria else 0.0
    crisis = world['scenario_state'].get('naval_crisis', {})
    fleet = world['scenario_state'].get('geography', {}).get('fleets', {}).get('Britain')
    force = (float(fleet['guns']) * max(0.0, 1.0 - float(fleet['damage']))
             if fleet else float(rules['british_squadron_strength']))
    batteries = float(crisis.get('battery_strength', rules['alexandria_battery_strength']))
    defense = batteries + defenders
    return {'british_force': force, 'egyptian_defense': defense,
            'ratio': force / max(1.0, defense)}


def _force_ratio(world: dict) -> float:
    return coastal_balance(world)['ratio']


def reinforce_batteries(world: dict) -> tuple[bool, str]:
    crisis = world.get('scenario_state', {}).get('naval_crisis', {})
    if crisis.get('stage') != 'mobilizing' or crisis.get('reinforced'):
        return False, 'The Alexandria batteries cannot be reinforced now.'
    rules = situation_template()['naval_crisis']
    cost = float(rules['battery_reinforcement_cost'])
    egypt = _nation(world, 'Egypt')
    payment_event_ids = []
    if not _transfer_to_households(
            world, egypt, cost, source='alexandria_battery_reinforcement',
            trace_event_ids=payment_event_ids):
        return False, f'The treasury needs {cost:,.0f} units and local workers to prepare the batteries.'
    strength_before = float(crisis.get('battery_strength',
                                       rules['alexandria_battery_strength']))
    crisis['battery_strength'] = (float(rules['alexandria_battery_strength'])
                                  + float(rules['battery_reinforcement_strength']))
    crisis['reinforced'] = True
    _emit_naval_trace(
        world, egypt,
        kind='naval_battery_reinforcement_outcome', record_class='outcome',
        phase='naval_crisis', subject={'type': 'scenario/tile', 'id': 'Alexandria'},
        metric_id='military.battery_strength', unit='strength',
        before=strength_before, after=float(crisis['battery_strength']),
        inputs={'turn': int(world['turn']), 'treasury_cost': cost,
                'reinforced': True,
                'funding_event_ids': payment_event_ids},
        cause_event_ids=payment_event_ids or None)
    return True, f'Paid {cost:,.0f} to prepare Alexandria’s defenses; battery strength is now {crisis["battery_strength"]:.0f}.'


def advance_naval_crisis(world: dict) -> None:
    """Mobilize only if power, money, domestic politics, and a coastal target permit it."""
    state = world.get('scenario_state', {})
    crisis = state.get('naval_crisis', {})
    stage = crisis.get('stage', 'none')
    if stage not in ('mobilizing', 'ultimatum', 'blockaded', 'mediation') or world.get('scenario_warning_modal'):
        return
    turn = int(world['turn'])
    rules = situation_template()['naval_crisis']
    egypt, britain, france = (_nation(world, name) for name in ('Egypt', 'Britain', 'France'))
    alexandria = _alexandria(egypt) if egypt else None
    if not egypt or not britain or not alexandria or not getattr(alexandria, 'is_coast', False):
        withdraw(world, 'No enforceable coastal approach exists at Alexandria; the naval claim lapses.', cause='no_access')
        return
    if state.get('payment_status') in ('paid', 'restructured'):
        withdraw(world, 'The debt settlement ends the naval confrontation.', cause='settlement')
        return
    british_unrest = _protest(world, 'Britain')
    decisions = foreign_decisions(world)
    if british_unrest >= float(rules['max_british_protest_energy']):
        withdraw(world, 'Domestic unrest in Britain makes the Alexandria expedition untenable.', cause='unsustainable')
        return
    if stage == 'mobilizing':
        if turn < int(crisis['due_turn']):
            return
        if decisions['Britain'] != 'intervene':
            withdraw(world, 'London declines an expedition after reviewing its claim, treasury, and domestic unrest.', cause='unsustainable')
            return
        if _force_ratio(world) < float(rules['minimum_force_ratio']):
            withdraw(world, 'Egyptian coastal defenses make the British naval threat a bluff.', cause='deterrence')
            return
        from scenario_diplomacy import mobilization_cost
        british_cost = mobilization_cost(decisions['France'])
        british_payment_event_ids = []
        if not _transfer_to_households(
                world, britain, british_cost, source='british_squadron_mobilization',
                trace_event_ids=british_payment_event_ids):
            withdraw(world, 'Britain cannot finance and supply a squadron for Alexandria.',
                     cause='unsustainable',
                     cause_event_ids=british_payment_event_ids or None)
            return
        fleet = create_fleet(world, 'Britain', guns=rules['british_squadron_strength'])
        if not move_fleet(world, 'Britain', 'Alexandria'):
            withdraw(world, 'The British squadron lacks coal for the Alexandria passage.',
                     cause='unsustainable',
                     cause_event_ids=british_payment_event_ids or None)
            return
        french_joined = False
        french_payment_event_ids = []
        if decisions['France'] == 'join_enforcement' and france is not None:
            if _transfer_to_households(
                    world, france, 30.0, source='french_squadron_mobilization',
                    trace_event_ids=french_payment_event_ids):
                create_fleet(world, 'France', ships=2, guns=35, coal=5, transports=0)
                french_joined = move_fleet(world, 'France', 'Alexandria')
                if not french_joined:
                    state['geography']['fleets'].pop('France', None)
        if not state.get('diplomatic_crisis', {}).get('policy_lock'):
            state['diplomatic_crisis']['policy_lock'] = decisions['France']
        crisis.update(stage='ultimatum', unit_id='guided_british_fleet', port_tile=alexandria.name,
                      french_support=decisions['France'] in ('endorse', 'join_enforcement', 'joint_guarantor'),
                      french_fleet_joined=french_joined,
                      french_fleet_ever_joined=french_joined)
        mobilization_causes = [event_id for event_id in
                               british_payment_event_ids + french_payment_event_ids]
        _emit_naval_trace(
            world, britain,
            kind='naval_squadron_mobilization_outcome', record_class='outcome',
            phase='naval_crisis', subject={'type': 'scenario', 'id': 'naval_crisis'},
            metric_id='military.fleet_mobilization', before='mobilizing', after='ultimatum',
            inputs={'turn': turn, 'british_cost': float(british_cost),
                    'british_fleet': dict(fleet),
                    'french_policy': decisions['France'],
                    'french_fleet_joined': bool(french_joined),
                    'french_payment_event_ids': french_payment_event_ids,
                    'british_payment_event_ids': british_payment_event_ids},
            cause_event_ids=mobilization_causes or None)
        partner = {'endorse': 'France supports the demand but sends no ships',
                   'abstain': 'France abstains', 'oppose': 'France opposes armed enforcement',
                   'mediate': 'France proposes mediation',
                   'joint_guarantor': 'France offers a shared revenue guarantee',
                   'join_enforcement': ('A funded French squadron joins Britain' if french_joined
                                        else 'French naval funding fails; Britain proceeds alone')}[decisions['France']]
        _record(world, f'A British squadron reaches Alexandria; {partner}. London demands Cairo yield customs or disarm the coastal batteries.')
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    upkeep = float(rules['upkeep_per_turn']) + (4.0 if decisions['France'] == 'oppose' else 0.0)
    british_upkeep_event_ids = []
    if not _transfer_to_households(
            world, britain, upkeep, source='british_fleet_upkeep',
            trace_event_ids=british_upkeep_event_ids):
        withdraw(world, 'Britain cannot pay the fleet’s continuing supply costs; the squadron withdraws.',
                 cause='unsustainable',
                 cause_event_ids=british_upkeep_event_ids or None)
        return
    if fleet_at(world, 'France', 'Alexandria'):
        french_upkeep_event_ids = []
        if not _transfer_to_households(
                world, france, 6.0, source='french_fleet_upkeep',
                trace_event_ids=french_upkeep_event_ids):
            french_fleet_before = dict(state['geography']['fleets'].get('France', {}))
            state['geography']['fleets'].pop('France', None)
            crisis['french_fleet_joined'] = False
            state['diplomatic_crisis']['french_commitment'] = 'none'
            state['diplomatic_crisis']['french_authorization'] = {
                'demonstrate': False, 'blockade': False, 'bombard': False}
            _record(world, 'French naval supply fails; the French squadron withdraws while Britain remains.')
            _emit_naval_trace(
                world, france,
                kind='naval_french_squadron_supply_failure', record_class='outcome',
                phase='naval_crisis', subject={'type': 'scenario/fleet', 'id': 'France'},
                metric_id='military.fleet_presence', before='Alexandria', after='withdrawn',
                inputs={'turn': turn, 'reason': 'treasury_or_recipient_unavailable',
                        'fleet_state_before': french_fleet_before,
                        'british_fleet_remains': True,
                        'funding_event_ids': french_upkeep_event_ids},
                cause_event_ids=french_upkeep_event_ids or None)
    resupply(world, 'Britain', 1)
    if not fleet_at(world, 'Britain', 'Alexandria'):
        withdraw(world, 'The British squadron is absent or unsupplied; the Alexandria blockade ends.', cause='unsustainable')
        return
    if stage == 'ultimatum':
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    if stage == 'mediation':
        if turn < int(crisis['mediation_due_turn']):
            return
        from scenario_diplomacy import _record as record_diplomacy
        french_policy = state.get('diplomatic_crisis', {}).get('french_policy')
        britain_accepts = french_policy != 'join_enforcement' or _protest(world, 'Britain') >= 3.0
        from scenario_debt import outstanding
        claim = outstanding(world)
        if (britain_accepts and claim > 0
                and egypt.government.agent.cash >= claim * 0.5):
            from scenario_debt import pay as pay_debt
            amount = claim * 0.5
            ok, _ = pay_debt(world, amount, kind='ottoman_mediation', forgive_remainder=True)
            if ok:
                state['payment_status'] = 'restructured'
                state['settlement_path'] = 'ottoman_mediation'
                state['diplomatic_crisis']['ottoman_offer']['status'] = 'accepted'
                record_diplomacy(world, 'Britain', 'accept_ottoman_terms', 'Britain accepts half the claim rather than prolonging an expensive expedition.')
                withdraw(world, f'Ottoman mediation secures a {amount:,.0f}-unit settlement; the fleet withdraws.', cause='settlement')
                return
        record_diplomacy(world, 'Britain', 'reject_ottoman_terms', 'A funded coalition or inadequate Egyptian payment prevents a mediated settlement.')
        state['diplomatic_crisis']['ottoman_offer']['status'] = 'rejected'
        crisis['stage'] = 'ultimatum'
        _record(world, 'Ottoman mediation fails to secure terms. The British ultimatum resumes.')
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    if stage == 'blockaded' and crisis.get('last_offer_turn') != turn:
        from scenario_campaign import advance_expedition
        if advance_expedition(world):
            return
        if state.get('campaign', {}).get('expedition', {}).get('stage') == 'foothold':
            return
        _record(world, 'The blockade of Alexandria continues to interrupt its coastal routes. Cairo may settle or hold out.')
        world['scenario_warning_modal'] = {'kind': 'naval_blockade'}
        world['playing'] = False


def naval_response_options(world: dict, kind: str) -> list[dict]:
    state = world.get('scenario_state', {})
    rules = situation_template()['naval_crisis']
    egypt = _nation(world, 'Egypt')
    cash = float(egypt.government.agent.cash) if egypt else 0.0
    from scenario_debt import outstanding
    settlement = round(outstanding(world)
                       * float(rules['settlement_fraction']), 2)
    common = [
        {'id': 'naval_settle', 'label': f'Settle for {settlement:,.0f}',
         'tooltip': f'Pay {settlement:,.0f} units now, end the claim and blockade, and concede 10 points of fiscal autonomy. The squadron withdraws.',
         'enabled': cash >= settlement},
        {'id': 'naval_accept_control', 'label': 'Accept customs oversight',
         'tooltip': 'Consent to a 5-unit levy each turn and lose 15 points of fiscal autonomy. The squadron withdraws; the default remains unsettled.',
         'enabled': True},
    ]
    if kind == 'naval_ultimatum':
        balance = coastal_balance(world)
        politics = state.get('politics', {})
        unreliable_command = (politics.get('governing_coalition') == 'palace'
                              and float(politics.get('army_loyalty', 1.0)) < 0.35)
        return common + [
            {'id': 'naval_seek_mediation', 'label': 'Seek Ottoman mediation',
             'tooltip': 'Ask the Ottoman government to mediate. Britain waits one turn while paying fleet upkeep. If Egypt can pay half the claim, mediation settles the debt; otherwise the ultimatum returns.',
             'enabled': True},
            {'id': 'naval_disarm', 'label': 'Disarm coastal batteries',
             'tooltip': 'Avoid bombardment and the blockade, but lose 8 points of legitimacy and 5 points of autonomy. The debt claim remains unresolved.',
             'enabled': True},
            {'id': 'naval_defend', 'label': 'Defend Alexandria',
             'tooltip': (('Unavailable: the garrison will not follow an isolated palace order. '
                          if unreliable_command else '')
                         + f'Keep the forts and gain 3 points of legitimacy. Current British force is {balance["british_force"]:.0f} '
                         f'against {balance["egyptian_defense"]:.0f} coastal defense (ratio {balance["ratio"]:.2f}); '
                         'if the force advantage holds, the fleet bombards the batteries and blockades the port.'),
             'enabled': not unreliable_command},
        ]
    return common + [
        {'id': 'naval_hold', 'label': 'Hold out another turn',
         'tooltip': 'Keep cash and autonomy. The coastal blockade continues; Britain pays supply costs and may withdraw if its treasury or domestic stability fails.',
         'enabled': True},
    ]


def resolve_naval_response(world: dict, response_id: str) -> tuple[bool, str]:
    state = world.get('scenario_state', {})
    crisis = state.get('naval_crisis', {})
    stage = crisis.get('stage')
    kind = 'naval_ultimatum' if stage == 'ultimatum' else 'naval_blockade' if stage == 'blockaded' else None
    if kind is None:
        return False, 'There is no naval demand awaiting a response.'
    response = next((option for option in naval_response_options(world, kind)
                     if option['id'] == response_id), None)
    if response is None or not response['enabled']:
        return False, 'That naval response is unavailable.'
    egypt = _nation(world, 'Egypt')
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    if response_id == 'naval_settle':
        from scenario_debt import pay as pay_debt, outstanding
        rules = situation_template()['naval_crisis']
        amount = round(outstanding(world) * float(rules['settlement_fraction']), 2)
        ok, reason = pay_debt(world, amount, kind='naval_settlement', forgive_remainder=True)
        if not ok:
            return False, reason
        state['payment_status'] = 'restructured'
        state['settlement_path'] = 'naval_settlement'
        state['creditor_levy_per_turn'] = 0.0
        state['creditor_levy_remaining'] = 0.0
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.10)
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + 0.15)
        withdraw(world, f'Cairo pays {amount:,.0f} and negotiates a settlement; the British squadron withdraws.', cause='settlement')
    elif response_id == 'naval_accept_control':
        from scenario_debt import set_collection_assignment
        set_collection_assignment(world, 5.0, origin='naval_ultimatum')
        state['financial_control_origin'] = 'naval_ultimatum'
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.15)
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + 0.05)
        withdraw(world, 'Cairo accepts a customs levy under naval pressure; the squadron withdraws.', cause='concession')
    elif response_id == 'naval_disarm':
        egypt.legitimacy = max(0.0, egypt.legitimacy - 0.08)
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.05)
        crisis['battery_strength'] = 0.0
        state['disarmed_batteries'] = True
        withdraw(world, 'Cairo disarms Alexandria’s batteries. The fleet withdraws, but the debt claim survives.', cause='disarmament')
    elif response_id == 'naval_seek_mediation':
        crisis['stage'] = 'mediation'
        crisis['mediation_due_turn'] = int(world['turn']) + 1
        state['diplomatic_crisis']['ottoman_offer'] = {'turn': int(world['turn']),
            'payment_fraction': .5, 'status': 'pending'}
        _record(world, 'Cairo requests Ottoman mediation; the fleet remains supplied off Alexandria pending a reply.')
    elif response_id == 'naval_defend':
        egypt.legitimacy = min(1.0, egypt.legitimacy + 0.03)
        if not fleet_at(world, 'Britain', 'Alexandria'):
            withdraw(world, 'No supplied squadron remains off Alexandria to enforce the ultimatum.', cause='unsustainable')
        elif _force_ratio(world) < float(situation_template()['naval_crisis']['minimum_force_ratio']):
            withdraw(world, 'Alexandria’s defenses deter the squadron; Britain abandons its ultimatum.', cause='deterrence')
        else:
            alexandria = _alexandria(egypt)
            manager = get_imperialism_manager()
            ok, message = manager.impose_naval_blockade(_nation(world, 'Britain'), egypt,
                                                       alexandria, int(world['turn']), world)
            if not ok:
                withdraw(world, f'Britain cannot enforce the blockade: {message}', cause='unsustainable')
            else:
                crisis['stage'] = 'blockaded'
                from scenario_campaign import bombard_alexandria
                _, bombardment = bombard_alexandria(world)
                crisis['battery_strength'] = max(0.0, float(crisis.get('battery_strength',
                    situation_template()['naval_crisis']['alexandria_battery_strength'])) * 0.25)
                egypt.legitimacy = max(0.0, egypt.legitimacy - 0.08)
                _record(world, bombardment + ' The port is blockaded; a landing may follow.', 'WAR')
                world['scenario_warning_modal'] = {'kind': 'naval_blockade'}
                world['playing'] = False
    elif response_id == 'naval_hold':
        crisis['last_offer_turn'] = int(world['turn'])
        _record(world, 'Cairo holds out. Britain must keep paying for the blockade.')
    else:
        return False, 'Unknown naval response.'
    record_change(world, response_id, before, snapshot(world))
    state.setdefault('actions_taken', []).append({'turn': int(world['turn']), 'action': response_id,
                                                   'message': world['scenario_feedback']})
    return True, world['scenario_feedback']

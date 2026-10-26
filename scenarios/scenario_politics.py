"""Egypt's incumbent, cabinet, officers, and civilian coalition in Guided play."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

from army import MilitaryUnit
from scenario_situation import situation_template


def _egypt(world):
    return next((nation for nation in world.get('nations', []) if nation.name == 'Egypt'), None)


def _state(world):
    return world['scenario_state']['politics']


def _clamp(value):
    return max(0.0, min(1.0, float(value)))


def _event(world, text):
    state = _state(world)
    state.setdefault('events', []).append({'turn': int(world['turn']), 'text': text})
    world['scenario_feedback'] = text
    from client.desktop.engine import ticker_push
    ticker_push(world, int(world['turn']), 'POLITICS', text, (193, 160, 220))


def _trace_region(world, nation):
    candidates = list(getattr(nation, 'tiles', ()))
    candidates.extend(world.get('tiles', ()))
    return next((tile for tile in candidates
                 if (getattr(tile, '_run_trace', None) is not None
                     and getattr(tile, '_collective_trace_clock', None) is not None)), None)


def _emit_politics_trace(world, nation, **event):
    region = _trace_region(world, nation)
    if region is None:
        return None
    from run_trace import emit
    return emit(region, **event)


def _officer_payment_operation_id(world, nation):
    region = _trace_region(world, nation)
    if region is None:
        return None
    clock = region._collective_trace_clock
    return (f"army-arrears:{nation.name}:{int(world.get('turn', 0))}:"
            f"{int(clock.get('next', 0))}")


def _political_state_values(state):
    return {key: float(state[key]) for key in (
        'army_loyalty', 'civilian_support', 'nationalist_movement',
        'palace_authority', 'cabinet_authority')}


def _political_evaluation_id(world, nation):
    region = _trace_region(world, nation)
    if region is None:
        return None
    return (f"scenario-politics:{nation.name}:{int(world.get('turn', 0))}:"
            f"{int(region._collective_trace_clock.get('next', 0))}")


def _response_state_snapshot(world, nation):
    politics = _state(world)
    scenario = world.get('scenario_state', {})
    unrest_by_tile = {
        str(getattr(tile, 'name', index)):
        float(getattr(tile, 'unrest_level', 0.0))
        for index, tile in enumerate(nation.tiles)
    }
    unrest_values = list(unrest_by_tile.values())
    return {
        'political': {
            'ruler': politics['ruler'],
            'governing_coalition': politics['governing_coalition'],
            'officer_access': float(politics['officer_access']),
            'army_loyalty': float(politics['army_loyalty']),
            'palace_authority': float(politics['palace_authority']),
            'civilian_support': float(politics['civilian_support']),
            'nationalist_movement': float(politics['nationalist_movement']),
            'cabinet_authority': float(politics['cabinet_authority']),
            'representative_cabinet': bool(politics['representative_cabinet']),
            'controllers_dismissed': bool(politics['controllers_dismissed']),
            'officers_promoted': bool(politics['officers_promoted']),
            'deposition_resolved': bool(politics['deposition_resolved']),
            'crisis_resolved': bool(politics['crisis_resolved']),
        },
        'scenario': {
            'fiscal_autonomy': float(scenario.get('fiscal_autonomy', 1.0)),
            'creditor_confidence': float(scenario.get('creditor_confidence', 0.0)),
            'chapter': int(scenario.get('chapter', 1)),
        },
        'legitimacy': float(getattr(nation, 'legitimacy', 0.0)),
        'unrest_by_tile': unrest_by_tile,
        'unrest_summary': {
            'tile_count': len(unrest_values),
            'mean': sum(unrest_values) / max(1, len(unrest_values)),
            'minimum': min(unrest_values) if unrest_values else None,
            'maximum': max(unrest_values) if unrest_values else None,
        },
    }


def _trace_political_response_gate(world, nation, kind, response_id,
                                   available_response_ids, reason):
    if nation is None:
        return None
    turn = int(world.get('turn', 0))
    operation_id = _political_evaluation_id(world, nation)
    return _emit_politics_trace(
        world, nation,
        kind='scenario_political_response_gate_evaluation',
        record_class='decision', phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': nation.name},
        metric_id='scenario.political_response_gate', unit='available',
        after=False,
        inputs={'operation_id': operation_id, 'turn': turn,
                'crisis_kind': kind, 'response_id': response_id,
                'available_response_ids': list(available_response_ids),
                'available': False, 'reason': reason})


def initialize(world):
    egypt = _egypt(world)
    rules = situation_template()['politics']
    world['scenario_state']['politics'] = {
        'ruler': 'Ismail Pasha', 'governing_coalition': 'palace',
        'officer_access': 0.35, 'army_loyalty': 0.75,
        'palace_authority': 0.85, 'civilian_support': 0.22,
        'nationalist_movement': 0.20, 'cabinet_authority': 0.20,
        'officers_paid': False, 'officers_promoted': False,
        'representative_cabinet': False, 'controllers_dismissed': False,
        'crisis_resolved': False, 'deposition_resolved': False,
        'events': [],
    }
    alexandria = next((tile for tile in egypt.tiles
                       if getattr(tile, 'scenario_location', '') == 'Alexandria'), None)
    if alexandria is not None:
        if not hasattr(alexandria, 'military_units'):
            alexandria.military_units = []
        unit = MilitaryUnit('egypt_alexandria_garrison', 'Egypt', alexandria.name,
                            soldiers=int(rules['alexandria_garrison_soldiers']),
                            wage_per_soldier=0.2, food_per_soldier=0.0,
                            is_garrison=True)
        egypt.military_units.append(unit)
        alexandria.military_units.append(unit)
        world['scenario_state']['politics']['garrison_id'] = unit.unit_id


def _garrison(world):
    egypt = _egypt(world)
    unit_id = _state(world).get('garrison_id')
    return next((unit for unit in egypt.military_units if unit.unit_id == unit_id), None) if egypt else None


def metrics(world):
    state = _state(world)
    return {key: state[key] for key in ('ruler', 'governing_coalition', 'officer_access',
                                         'army_loyalty', 'palace_authority', 'civilian_support',
                                         'nationalist_movement', 'cabinet_authority')}


def apply_action(world, action_id):
    """These are major domestic decisions; caller enforces the one-per-turn rule."""
    state = _state(world)
    egypt = _egypt(world)
    if action_id == 'pay_army_arrears':
        cost = float(situation_template()['politics']['officer_pay_cost'])
        treasury = egypt.government.agent
        treasury_before = float(treasury.cash)
        operation_id = _officer_payment_operation_id(world, egypt)
        turn = int(world.get('turn', 0))
        if state['officers_paid']:
            funding_event_id = _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_funding_decision', record_class='decision',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='politics.officer_arrears_funding',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'amount_requested': cost,
                        'treasury_cash_before': treasury_before,
                        'officers_paid': True, 'funded': False,
                        'reason': 'arrears_package_already_funded'})
            _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_payment_outcome', record_class='outcome',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='scenario.officer_arrears_payment',
                before=treasury_before, after=treasury_before,
                unit=getattr(egypt, 'currency', None) or 'local_currency',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'success': False, 'reason': 'arrears_package_already_funded',
                        'cash_debited': 0.0},
                cause_event_ids=[funding_event_id] if funding_event_id else None)
            return False, 'The officer arrears package has already been funded.'

        if treasury_before < cost:
            funding_event_id = _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_funding_decision', record_class='decision',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='politics.officer_arrears_funding',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'amount_requested': cost,
                        'treasury_cash_before': treasury_before,
                        'cash_shortfall': cost - treasury_before,
                        'officers_paid': False, 'funded': False,
                        'reason': 'treasury_cash_below_cost'})
            _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_payment_outcome', record_class='outcome',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='scenario.officer_arrears_payment',
                before=treasury_before, after=treasury_before,
                unit=getattr(egypt, 'currency', None) or 'local_currency',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'success': False, 'reason': 'insufficient_treasury_cash',
                        'amount_requested': cost, 'cash_debited': 0.0},
                cause_event_ids=[funding_event_id] if funding_event_id else None)
            return False, f'The treasury needs {cost:,.0f} units to pay officer arrears.'
        garrison_tile = next((tile for tile in egypt.tiles if getattr(tile, 'scenario_location', '') == 'Alexandria'), None)
        recipient_tiles = [garrison_tile] if garrison_tile else list(egypt.tiles)
        selected_recipients = [
            (tile, agent) for tile in recipient_tiles
            for agent in getattr(tile, 'agents', [])
            if getattr(agent, 'alive', True)
            and not getattr(agent, 'is_government', False)
            and not getattr(agent, 'is_corporation', False)]
        recipients = [agent for _tile, agent in selected_recipients]
        if not recipients:
            funding_event_id = _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_funding_decision', record_class='decision',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='politics.officer_arrears_funding',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'amount_requested': cost,
                        'treasury_cash_before': treasury_before,
                        'eligible_recipient_count': 0,
                        'recipient_selection_rule':
                        'living non-government non-corporation agents in Alexandria, or all Egyptian tiles if Alexandria is absent',
                        'officers_paid': False, 'funded': False,
                        'reason': 'no_household_recipients'})
            _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_payment_outcome', record_class='outcome',
                phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='scenario.officer_arrears_payment',
                before=treasury_before, after=treasury_before,
                unit=getattr(egypt, 'currency', None) or 'local_currency',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'success': False, 'reason': 'no_household_recipients',
                        'amount_requested': cost, 'cash_debited': 0.0},
                cause_event_ids=[funding_event_id] if funding_event_id else None)
            return False, 'No Egyptian households can receive military pay.'

        recipient_balances = [float(agent.cash) for agent in recipients]
        funding_event_id = _emit_politics_trace(
            world, egypt,
            kind='officer_arrears_funding_decision', record_class='decision',
            phase='scenario_action',
            subject={'type': 'scenario/nation', 'id': egypt.name},
            metric_id='politics.officer_arrears_funding',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'amount_requested': cost, 'treasury_cash_before': treasury_before,
                    'eligible_recipient_count': len(recipients),
                    'recipient_ids': [str(agent.id) for agent in recipients],
                    'recipient_selection_rule':
                    'living non-government non-corporation agents in Alexandria, or all Egyptian tiles if Alexandria is absent',
                    'officers_paid': False, 'funded': True,
                    'reason': 'treasury_and_households_available'})
        currency = (getattr(egypt, 'currency', None)
                    or getattr(garrison_tile, 'home_currency', None)
                    or 'local_currency')
        payee_balances = []
        each = cost / len(recipients)
        _public_write = begin_public_change(None, treasury)
        treasury.cash -= cost
        finish_public_change(_public_write, 'scenario_politics:apply_action',
                             inputs={'source_writer': 'scenario_politics.py:apply_action:127c4d087b7bb921:1', 'semantic_operation_id': locals().get('operation_id')})
        treasury_after = float(treasury.cash)
        for (recipient_tile, agent), recipient_before in zip(
                selected_recipients, recipient_balances):
            _public_write = begin_public_change(None, agent)
            agent.cash += each
            finish_public_change(_public_write, 'scenario_politics:apply_action',
                                 inputs={'source_writer': 'scenario_politics.py:apply_action:4375ce8f5644507e:1', 'semantic_operation_id': locals().get('operation_id')})
            recipient_currency = (getattr(agent, 'home_currency', None) or currency)
            payee_balances.append({
                'agent_id': str(agent.id), 'tile': recipient_tile.name,
                'currency': recipient_currency,
                'balance_before': recipient_before,
                'balance_after': float(agent.cash), 'amount': each})
        from finance_trace import account_ref, transfer_contract
        from run_trace import emit
        region = _trace_region(world, egypt)
        transfer_event_id = None
        receipt_event_ids = []
        if region is not None:
            payer = account_ref(
                'government_treasury', str(treasury.id), currency,
                nation_id=egypt.name, balance_before=treasury_before,
                balance_after=treasury_after,
                balance_scope='government_agent.cash')
            payee_pool = {
                'type': 'household_wallet_pool', 'id': operation_id,
                'currency': currency, 'recipient_count': len(recipients),
                'members': payee_balances,
            }
            payer_contract = transfer_contract(
                operation_id, 'officer_arrears_payment', side='payer',
                amount=cost, amount_currency=currency, payer_account=payer,
                payee_account=payee_pool, local_cash_leg_amount=cost,
                local_cash_leg_currency=currency,
                counterparty_leg_status='individual_household_receipts_recorded',
                source='egypt_officer_arrears', turn=turn)
            transfer_event_id = emit(
                region, kind='officer_arrears_treasury_debit',
                record_class='transfer', phase='scenario_action',
                subject={'type': 'scenario/nation', 'id': egypt.name},
                metric_id='finance.treasury_flow', unit=currency,
                after=-cost,
                inputs={'operation_id': operation_id,
                        'recipient_count': len(recipients),
                        'transfer_contract': payer_contract},
                cause_event_ids=[funding_event_id] if funding_event_id else None)
            for agent, payment in zip(recipients, payee_balances):
                payee_currency = payment['currency']
                receipt_contract = transfer_contract(
                    operation_id, 'officer_arrears_payment', side='payee',
                    amount=each, amount_currency=currency, payer_account=payer,
                    payee_account=account_ref(
                        'agent_wallet', payment['agent_id'], payee_currency,
                        tile=payment['tile'], balance_before=payment['balance_before'],
                        balance_after=payment['balance_after'],
                        balance_scope='cash_wallet'),
                    local_cash_leg_amount=each,
                    local_cash_leg_currency=payee_currency,
                    currency_conversion_applied=False,
                    counterparty_leg_status='paired_to_aggregate_source_debit',
                    source='egypt_officer_arrears', turn=turn,
                    aggregate_source_amount=cost)
                receipt_id = emit(
                    region, kind='officer_arrears_household_receipt',
                    record_class='transfer', phase='scenario_action',
                    subject={'type': 'agent', 'id': payment['agent_id'],
                             'tile': payment['tile']},
                    metric_id='finance.household_cash_receipt', unit=payee_currency,
                    after=each,
                    inputs={'operation_id': operation_id,
                            'transfer_contract': receipt_contract},
                    cause_event_ids=([transfer_event_id] if transfer_event_id
                                     else None))
                if receipt_id is not None:
                    receipt_event_ids.append(receipt_id)
        state['officers_paid'] = True
        loyalty_before = float(state['army_loyalty'])
        state['army_loyalty'] = _clamp(state['army_loyalty'] + 0.22)
        unit = _garrison(world)
        morale_before = float(unit.morale) if unit else None
        if unit:
            unit.morale = _clamp(unit.morale + 0.20)
        message = f'Paid {cost:,.0f} units in officer arrears; army loyalty and garrison morale improved.'
        outcome_id = _emit_politics_trace(
            world, egypt,
            kind='officer_arrears_payment_outcome', record_class='outcome',
            phase='scenario_action',
            subject={'type': 'scenario/nation', 'id': egypt.name},
            metric_id='politics.army_loyalty', before=loyalty_before,
            after=float(state['army_loyalty']), unit='ratio',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'success': True, 'reason': 'households_paid',
                    'amount_paid': cost, 'officer_arrears_flag': True,
                    'garrison_id': unit.unit_id if unit else None,
                    'garrison_morale_before': morale_before,
                    'garrison_morale_after': float(unit.morale) if unit else None,
                    'funding_event_id': funding_event_id,
                    'treasury_payment_event_id': transfer_event_id,
                    'household_receipt_event_ids': receipt_event_ids},
            cause_event_ids=[event_id for event_id in
                             ([funding_event_id, transfer_event_id]
                              + receipt_event_ids) if event_id] or None)
        if unit is not None:
            _emit_politics_trace(
                world, egypt,
                kind='officer_arrears_garrison_morale_outcome',
                record_class='outcome', phase='scenario_action',
                subject={'type': 'nation/unit', 'id': unit.unit_id,
                         'nation': egypt.name},
                metric_id='military.garrison_morale',
                before=morale_before, after=float(unit.morale), unit='ratio',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'reason': 'officer_arrears_paid',
                        'garrison_id': unit.unit_id,
                        'morale_change': float(unit.morale) - morale_before,
                        'loyalty_outcome_event_id': outcome_id},
                cause_event_ids=([event_id for event_id in
                                  ([funding_event_id, transfer_event_id, outcome_id]
                                   + receipt_event_ids) if event_id] or None))
    elif action_id == 'promote_egyptian_officers':
        if state['officers_promoted']:
            return False, 'The officer promotion reform has already been enacted.'
        state['officers_promoted'] = True
        state['officer_access'] = _clamp(state['officer_access'] + 0.40)
        state['army_loyalty'] = _clamp(state['army_loyalty'] + 0.12)
        state['palace_authority'] = _clamp(state['palace_authority'] - 0.08)
        message = 'Promoted Egyptian officers; loyalty rose, while the palace gave up some control of appointments.'
    elif action_id == 'invite_representative_cabinet':
        if state['representative_cabinet']:
            return False, 'A representative cabinet has already been invited.'
        state['representative_cabinet'] = True
        state['governing_coalition'] = 'constitutional'
        state['cabinet_authority'] = _clamp(state['cabinet_authority'] + 0.35)
        state['palace_authority'] = _clamp(state['palace_authority'] - 0.18)
        state['civilian_support'] = _clamp(state['civilian_support'] + 0.15)
        egypt.legitimacy = _clamp(egypt.legitimacy + 0.05)
        message = 'Invited a representative cabinet; civilian support and legitimacy improved, while palace authority narrowed.'
    elif action_id == 'dismiss_foreign_controllers':
        if state['controllers_dismissed']:
            return False, 'The foreign controllers have already been dismissed.'
        state['controllers_dismissed'] = True
        scenario = world['scenario_state']
        scenario['fiscal_autonomy'] = _clamp(scenario['fiscal_autonomy'] + 0.15)
        scenario['creditor_confidence'] = _clamp(scenario['creditor_confidence'] - 0.20)
        state['nationalist_movement'] = _clamp(state['nationalist_movement'] + 0.12)
        state['palace_authority'] = _clamp(state['palace_authority'] - 0.12)
        message = 'Dismissed foreign controllers; Egypt recovered fiscal discretion, but creditor confidence and palace support fell.'
    else:
        return False, 'Unknown political decision.'
    _event(world, message)
    return True, message


def advance(world):
    """Update support from measured welfare, military supply, and foreign control."""
    state = _state(world)
    scenario = world['scenario_state']
    egypt = _egypt(world)
    state_before = _political_state_values(state)
    unit = _garrison(world)
    morale = float(unit.morale) if unit else 0.0
    people = [person for tile in egypt.tiles for person in tile.agents
              if getattr(person, 'alive', True) and not getattr(person, 'is_government', False)
              and not getattr(person, 'is_corporation', False)
              and not getattr(person, 'is_trader', False)]
    from nutrition import deficit_fraction
    hunger = sum(deficit_fraction(person) for person in people) / max(1, len(people))
    unrest_values = [float(getattr(tile, 'unrest_level', 0.0))
                     for tile in egypt.tiles]
    unrest = sum(unrest_values) / max(1, len(egypt.tiles))
    fiscal_autonomy = float(scenario.get('fiscal_autonomy', 1.0))
    foreign_control = 1.0 - fiscal_autonomy
    extraction_raw = float(scenario.get('extraction_level', 0))
    extraction = min(1.0, extraction_raw)
    naval_stage = scenario.get('naval_crisis', {}).get('stage')
    naval_coercion = (0.30 if naval_stage == 'blockaded' else
                     0.12 if naval_stage == 'ultimatum' else 0.0)
    loyalty_formula_inputs = {
        'base': 0.15, 'morale_coefficient': 0.45,
        'officer_access_coefficient': 0.25,
        'foreign_control_penalty': 0.20,
        'unrest_penalty': 0.10,
    }
    loyalty_target = (loyalty_formula_inputs['base']
                      + loyalty_formula_inputs['morale_coefficient'] * morale
                      + loyalty_formula_inputs['officer_access_coefficient']
                      * float(state['officer_access'])
                      - loyalty_formula_inputs['foreign_control_penalty']
                      * foreign_control
                      - loyalty_formula_inputs['unrest_penalty'] * unrest
                      - naval_coercion)
    ruler_loyalty_modifier = 0.0
    if state['ruler'] == 'Tawfiq Pasha' and state['controllers_dismissed'] and not state['officers_promoted']:
        ruler_loyalty_modifier = -0.16  # Unreformed officers distrust a restored palace.
        loyalty_target += ruler_loyalty_modifier
    state['army_loyalty'] = _clamp(0.65 * state['army_loyalty']
                                   + 0.35 * loyalty_target)
    civilian_target = (0.12 + 0.35 * unrest + 0.28 * hunger + 0.15 * extraction
                       + (0.12 if state['representative_cabinet'] else 0.0))
    state['civilian_support'] = _clamp(0.7 * state['civilian_support']
                                      + 0.3 * civilian_target)
    grievance = (0.24 * foreign_control + 0.20 * (1.0 - state['officer_access'])
                 + 0.16 * (1.0 - state['army_loyalty'])
                 + 0.14 * state['civilian_support'])
    naval_grievance_bonus = (0.16 if naval_stage in
                             ('mobilizing', 'ultimatum', 'blockaded') else 0.0)
    grievance += naval_grievance_bonus
    movement_delta = max(-0.025, grievance * 0.20 - 0.025)
    state['nationalist_movement'] = _clamp(state['nationalist_movement']
                                          + movement_delta)
    palace_authority_delta = (-0.025 * foreign_control - 0.03 * unrest
                              - (0.035 if naval_stage == 'blockaded' else 0.0))
    state['palace_authority'] = _clamp(state['palace_authority']
                                      + palace_authority_delta)
    cabinet_authority_delta = (0.01 if state['representative_cabinet'] else 0.0)
    state['cabinet_authority'] = _clamp(state['cabinet_authority']
                                       + cabinet_authority_delta)
    state_after = _political_state_values(state)
    turn = int(world.get('turn', 0))
    operation_id = _political_evaluation_id(world, egypt)
    evaluation_event_id = _emit_politics_trace(
        world, egypt,
        kind='scenario_politics_dynamics_calculation', record_class='calculation',
        phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': egypt.name},
        metric_id='scenario.politics_dynamics',
        inputs={
            'operation_id': operation_id, 'turn': turn,
            'model': 'egypt_political_support.v1',
            'population_inputs': {
                'eligible_household_count': len(people),
                'mean_hunger_fraction': hunger,
                'territory_count': len(unrest_values),
                'mean_unrest': unrest,
                'minimum_tile_unrest': min(unrest_values) if unrest_values else None,
                'maximum_tile_unrest': max(unrest_values) if unrest_values else None,
            },
            'military_inputs': {
                'garrison_id': unit.unit_id if unit else None,
                'garrison_morale': morale,
                'officer_access': float(state['officer_access']),
                'naval_stage': naval_stage,
                'naval_loyalty_penalty': naval_coercion,
            },
            'foreign_control_inputs': {
                'fiscal_autonomy': fiscal_autonomy,
                'foreign_control': foreign_control,
                'extraction_raw': extraction_raw,
                'extraction_used': extraction,
            },
            'political_conditions': {
                'ruler': state['ruler'],
                'controllers_dismissed': bool(state['controllers_dismissed']),
                'officers_promoted': bool(state['officers_promoted']),
                'representative_cabinet': bool(state['representative_cabinet']),
                'ruler_loyalty_modifier': ruler_loyalty_modifier,
            },
            'formula_coefficients': {
                'army_loyalty': loyalty_formula_inputs,
                'army_loyalty_previous_weight': 0.65,
                'army_loyalty_target_weight': 0.35,
                'civilian_support_previous_weight': 0.70,
                'civilian_support_target_weight': 0.30,
                'civilian_target': {
                    'base': 0.12, 'unrest': 0.35, 'hunger': 0.28,
                    'extraction': 0.15, 'representative_cabinet_bonus': 0.12,
                },
                'nationalist_grievance': {
                    'foreign_control': 0.24, 'officer_access_deficit': 0.20,
                    'army_loyalty_deficit': 0.16, 'civilian_support': 0.14,
                    'naval_crisis_bonus': 0.16,
                },
                'nationalist_movement': {
                    'grievance_weight': 0.20, 'base_decay': 0.025,
                    'minimum_delta': -0.025,
                },
                'palace_authority': {
                    'foreign_control_penalty': 0.025,
                    'unrest_penalty': 0.03,
                    'blockade_penalty': 0.035,
                },
                'cabinet_authority': {
                    'representative_cabinet_growth': 0.01,
                },
            },
            'intermediate_values': {
                'loyalty_target': loyalty_target,
                'civilian_support_target': civilian_target,
                'nationalist_grievance': grievance,
                'naval_grievance_bonus_applied': naval_grievance_bonus,
                'nationalist_movement_delta': movement_delta,
                'palace_authority_delta': palace_authority_delta,
                'cabinet_authority_delta': cabinet_authority_delta,
            },
            'political_state_before': state_before,
            'political_state_after': state_after,
            'crisis_gates_skipped': bool(world.get('scenario_warning_modal')),
        })
    outcome_metrics = {
        'army_loyalty': ('politics.army_loyalty', 'ratio'),
        'civilian_support': ('politics.civilian_support', 'ratio'),
        'nationalist_movement': ('politics.nationalist_movement', 'ratio'),
        'palace_authority': ('politics.palace_authority', 'ratio'),
        'cabinet_authority': ('politics.cabinet_authority', 'ratio'),
    }
    for field, (metric_id, unit_name) in outcome_metrics.items():
        if state_before[field] == state_after[field]:
            continue
        _emit_politics_trace(
            world, egypt,
            kind='scenario_politics_metric_outcome', record_class='outcome',
            phase='scenario_politics',
            subject={'type': 'scenario/nation/metric', 'id': egypt.name,
                     'metric': field},
            metric_id=metric_id, before=state_before[field],
            after=state_after[field], unit=unit_name,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'calculation_event_id': evaluation_event_id,
                    'formula_output': field},
            cause_event_ids=[evaluation_event_id] if evaluation_event_id else None)
    if world.get('scenario_warning_modal'):
        return
    rules = situation_template()['politics']
    restoration_reaction_pending = (
        any(item.get('action_id') == 'dismiss_foreign_controllers'
            for item in scenario.get('creditor_reactions', []))
        if state['controllers_dismissed'] else False)
    dynastic_gate_inputs = {
        'deposition_resolved': bool(state['deposition_resolved']),
        'ruler': state['ruler'],
        'expected_ruler': 'Ismail Pasha',
        'palace_authority': float(state['palace_authority']),
        'palace_authority_threshold': float(rules['deposition_authority_threshold']),
        'fiscal_autonomy': fiscal_autonomy,
        'fiscal_autonomy_threshold': float(rules['deposition_autonomy_threshold']),
        'controllers_dismissed': bool(state['controllers_dismissed']),
        'dismissal_reaction_pending': restoration_reaction_pending,
    }
    dynastic_triggered = (
        not state['deposition_resolved'] and state['ruler'] == 'Ismail Pasha'
        and state['palace_authority'] <= rules['deposition_authority_threshold']
        and (fiscal_autonomy <= rules['deposition_autonomy_threshold']
             or (state['controllers_dismissed'] and restoration_reaction_pending)))
    dynastic_gate_event_id = _emit_politics_trace(
        world, egypt,
        kind='scenario_political_crisis_gate_evaluation', record_class='decision',
        phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': egypt.name},
        metric_id='scenario.political_crisis_gate', unit='triggered',
        after=dynastic_triggered,
        inputs={'operation_id': operation_id, 'turn': turn,
                'gate': 'dynastic_crisis', 'triggered': dynastic_triggered,
                'conditions': dynastic_gate_inputs},
        cause_event_ids=[evaluation_event_id] if evaluation_event_id else None)
    if dynastic_triggered:
        world['scenario_warning_modal'] = {'kind': 'dynastic_crisis'}
        world['playing'] = False
        _event(world, 'Ismail’s palace has lost authority under creditor pressure; the succession is contested.')
        return
    officer_movement_triggered = (
        not state['crisis_resolved']
        and state['nationalist_movement'] >= rules['movement_threshold']
        and state['army_loyalty'] <= rules['army_loyalty_threshold'])
    officer_gate_event_id = _emit_politics_trace(
        world, egypt,
        kind='scenario_political_crisis_gate_evaluation', record_class='decision',
        phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': egypt.name},
        metric_id='scenario.political_crisis_gate', unit='triggered',
        after=officer_movement_triggered,
        inputs={'operation_id': operation_id, 'turn': turn,
                'gate': 'officer_movement',
                'triggered': officer_movement_triggered,
                'conditions': {
                    'crisis_resolved': bool(state['crisis_resolved']),
                    'nationalist_movement': float(state['nationalist_movement']),
                    'movement_threshold': float(rules['movement_threshold']),
                    'army_loyalty': float(state['army_loyalty']),
                    'army_loyalty_threshold': float(rules['army_loyalty_threshold']),
                }},
        cause_event_ids=([evaluation_event_id, dynastic_gate_event_id]
                         if evaluation_event_id and dynastic_gate_event_id else
                         [event_id for event_id in
                          (evaluation_event_id, dynastic_gate_event_id) if event_id]
                         or None))
    if officer_movement_triggered:
        world['scenario_warning_modal'] = {'kind': 'officer_movement'}
        world['playing'] = False
        _event(world, 'Egyptian officers and civilian supporters demand a change in governing authority.')


def response_options(world, kind):
    state = _state(world)
    if kind == 'dynastic_crisis':
        return [
            {'id': 'accept_tawfiq', 'label': 'Accept Tawfiq’s succession',
             'tooltip': 'Tawfiq becomes khedive; palace authority recovers 20 points, but nationalist support rises 10 points.'},
            {'id': 'constitutional_compromise', 'label': 'Constitutional compromise',
             'tooltip': 'Tawfiq becomes khedive under a representative cabinet; cabinet authority and civilian support rise, fiscal autonomy recovers 10 points.'},
            {'id': 'defend_ismail', 'label': 'Defend Ismail’s rule',
             'tooltip': 'Keep Ismail; creditor confidence falls 15 points and palace authority depends on army loyalty.'},
        ]
    if kind == 'officer_movement':
        return [
            {'id': 'support_urabi', 'label': 'Support ‘Urabi’s cabinet',
             'tooltip': 'The officer-civilian coalition governs; recover 15 points of fiscal autonomy, gain 8 points of legitimacy, lose 20 points of creditor confidence.'},
            {'id': 'constitutional_officers', 'label': 'Share authority with officers',
             'tooltip': 'The constitutional cabinet shares power; army loyalty and civilian support recover, while palace authority falls.'},
            {'id': 'back_palace', 'label': 'Back the palace',
             'tooltip': f'Keep palace rule. With army loyalty {state["army_loyalty"]:.0%}, a weak command may lose control and raise unrest.'},
        ]
    return []


def resolve(world, response_id):
    warning = world.get('scenario_warning_modal') or {}
    kind = warning.get('kind')
    if kind not in ('dynastic_crisis', 'officer_movement'):
        _trace_political_response_gate(
            world, _egypt(world), kind, response_id, (),
            'no_political_transition_awaiting_decision')
        return False, 'There is no political transition awaiting a decision.'
    available_response_ids = [item['id'] for item in response_options(world, kind)]
    if response_id not in available_response_ids:
        _trace_political_response_gate(
            world, _egypt(world), kind, response_id, available_response_ids,
            'response_unavailable_for_crisis')
        return False, 'That political response is unavailable.'
    state = _state(world)
    scenario = world['scenario_state']
    egypt = _egypt(world)
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    political_before = _response_state_snapshot(world, egypt)
    turn = int(world.get('turn', 0))
    operation_id = _political_evaluation_id(world, egypt)
    decision_event_id = _emit_politics_trace(
        world, egypt,
        kind='scenario_political_response_decision', record_class='decision',
        phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': egypt.name},
        metric_id='scenario.political_response', before=kind,
        after=response_id, unit='response',
        inputs={'operation_id': operation_id, 'turn': turn,
                'crisis_kind': kind, 'response_id': response_id,
                'available_response_ids': [item['id']
                                           for item in response_options(world, kind)],
                'political_state_before': {
                    key: value for key, value in political_before.items()
                    if key != 'unrest_by_tile'},
                'unrest_before': political_before['unrest_summary']})
    if kind == 'dynastic_crisis':
        state['deposition_resolved'] = True
        if response_id == 'defend_ismail':
            scenario['creditor_confidence'] = _clamp(scenario['creditor_confidence'] - 0.15)
            state['palace_authority'] = _clamp(state['palace_authority'] + 0.15 * state['army_loyalty'])
            message = 'Ismail holds the palace with uncertain army backing.'
        else:
            state['ruler'] = 'Tawfiq Pasha'
            state['palace_authority'] = _clamp(state['palace_authority'] + 0.20)
            if response_id == 'constitutional_compromise':
                state['governing_coalition'] = 'constitutional'
                state['representative_cabinet'] = True
                state['cabinet_authority'] = _clamp(state['cabinet_authority'] + 0.25)
                state['civilian_support'] = _clamp(state['civilian_support'] + 0.10)
                scenario['fiscal_autonomy'] = _clamp(scenario['fiscal_autonomy'] + 0.10)
                message = 'Tawfiq takes office under a constitutional cabinet; the player continues as Egypt’s governing coalition.'
            else:
                state['nationalist_movement'] = _clamp(state['nationalist_movement'] + 0.10)
                message = 'Tawfiq succeeds Ismail; nationalist opposition gains support.'
    else:
        state['crisis_resolved'] = True
        if response_id == 'support_urabi':
            state['governing_coalition'] = 'nationalist'
            state['cabinet_authority'] = _clamp(state['cabinet_authority'] + 0.40)
            state['palace_authority'] = _clamp(state['palace_authority'] - 0.35)
            scenario['fiscal_autonomy'] = _clamp(scenario['fiscal_autonomy'] + 0.15)
            scenario['creditor_confidence'] = _clamp(scenario['creditor_confidence'] - 0.20)
            egypt.legitimacy = _clamp(egypt.legitimacy + 0.08)
            message = '‘Urabi’s officer-civilian cabinet takes governing authority from the palace.'
        elif response_id == 'constitutional_officers':
            state['governing_coalition'] = 'constitutional'
            state['army_loyalty'] = _clamp(state['army_loyalty'] + 0.18)
            state['civilian_support'] = _clamp(state['civilian_support'] + 0.08)
            state['palace_authority'] = _clamp(state['palace_authority'] - 0.18)
            message = 'The palace and officers share authority through a constitutional cabinet.'
        else:
            egypt.legitimacy = _clamp(egypt.legitimacy - 0.05)
            for tile in egypt.tiles:
                tile.unrest_level = _clamp(float(getattr(tile, 'unrest_level', 0.0))
                                           + 0.12 * (1 - state['army_loyalty']))
            message = 'The palace resists the movement; weak army loyalty makes repression costly.'
    from scenario_egypt_1877 import enter_chapter_two
    enter_chapter_two(world, 'succession' if kind == 'dynastic_crisis' else 'officer movement')
    political_after = _response_state_snapshot(world, egypt)
    response_event_id = _emit_politics_trace(
        world, egypt,
        kind='scenario_political_response_applied', record_class='outcome',
        phase='scenario_politics',
        subject={'type': 'scenario/nation', 'id': egypt.name},
        metric_id='scenario.political_response', before='pending',
        after=response_id, unit='response',
        inputs={'operation_id': operation_id, 'turn': turn,
                'crisis_kind': kind, 'response_id': response_id,
                'message': message,
                'political_state_before': {
                    key: value for key, value in political_before.items()
                    if key != 'unrest_by_tile'},
                'political_state_after': {
                    key: value for key, value in political_after.items()
                    if key != 'unrest_by_tile'},
                'unrest_before': political_before['unrest_summary'],
                'unrest_after': political_after['unrest_summary']},
        cause_event_ids=[decision_event_id] if decision_event_id else None)
    response_metrics = {
        'army_loyalty': ('politics.army_loyalty', 'ratio'),
        'palace_authority': ('politics.palace_authority', 'ratio'),
        'civilian_support': ('politics.civilian_support', 'ratio'),
        'nationalist_movement': ('politics.nationalist_movement', 'ratio'),
        'cabinet_authority': ('politics.cabinet_authority', 'ratio'),
        'legitimacy': ('politics.legitimacy', 'ratio'),
        'fiscal_autonomy': ('scenario.fiscal_autonomy', 'ratio'),
        'creditor_confidence': ('scenario.creditor_confidence', 'ratio'),
    }
    scalar_before = {
        **political_before['political'],
        **political_before['scenario'],
        'legitimacy': political_before['legitimacy'],
    }
    scalar_after = {
        **political_after['political'],
        **political_after['scenario'],
        'legitimacy': political_after['legitimacy'],
    }
    for field, (metric_id, unit_name) in response_metrics.items():
        if scalar_before[field] == scalar_after[field]:
            continue
        _emit_politics_trace(
            world, egypt,
            kind='scenario_political_response_metric_outcome',
            record_class='outcome', phase='scenario_politics',
            subject={'type': 'scenario/nation/metric', 'id': egypt.name,
                     'metric': field},
            metric_id=metric_id, before=scalar_before[field],
            after=scalar_after[field], unit=unit_name,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'crisis_kind': kind, 'response_id': response_id,
                    'response_event_id': response_event_id},
            cause_event_ids=([response_event_id] if response_event_id else
                             [decision_event_id] if decision_event_id else None))
    for field, metric_id in (
            ('ruler', 'scenario.ruler_transition'),
            ('governing_coalition', 'scenario.governing_coalition')):
        before_value = political_before['political'][field]
        after_value = political_after['political'][field]
        if before_value == after_value:
            continue
        _emit_politics_trace(
            world, egypt,
            kind='scenario_political_response_category_outcome',
            record_class='outcome', phase='scenario_politics',
            subject={'type': 'scenario/nation/metric', 'id': egypt.name,
                     'metric': field},
            metric_id=metric_id, before=before_value, after=after_value,
            unit='category',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'crisis_kind': kind, 'response_id': response_id,
                    'response_event_id': response_event_id},
            cause_event_ids=([response_event_id] if response_event_id else
                             [decision_event_id] if decision_event_id else None))
    for tile_name, unrest_before in political_before['unrest_by_tile'].items():
        unrest_after = political_after['unrest_by_tile'].get(tile_name, unrest_before)
        if unrest_before == unrest_after:
            continue
        _emit_politics_trace(
            world, egypt,
            kind='scenario_political_response_unrest_outcome',
            record_class='outcome', phase='scenario_politics',
            subject={'type': 'tile', 'id': tile_name},
            metric_id='politics.unrest_level', before=unrest_before,
            after=unrest_after, unit='ratio',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'crisis_kind': kind, 'response_id': response_id,
                    'army_loyalty': float(state['army_loyalty']),
                    'unrest_formula': 'clamp(before + 0.12 * (1 - army_loyalty))',
                    'response_event_id': response_event_id},
            cause_event_ids=([response_event_id] if response_event_id else
                             [decision_event_id] if decision_event_id else None))
    _event(world, message)
    from scenario_history import record as record_history
    record_history(world, message, historical_parallel=response_id in ('accept_tawfiq', 'support_urabi'))
    record_change(world, response_id, before, snapshot(world))
    scenario.setdefault('actions_taken', []).append({'turn': int(world['turn']),
                                                      'action': response_id, 'message': message})
    return True, message

"""Alexandria fort damage and a supplied British landing campaign."""

from __future__ import annotations

from army import MilitaryUnit, resolve_battle
from scenario_geography import fleet_at, move_fleet


def initialize(world):
    world['scenario_state']['campaign'] = {
        'forts': {'Alexandria': {'integrity': 100.0, 'ammunition': 8},
                  'Ismailia': {'integrity': 65.0, 'ammunition': 5}},
        'trench_strength': {'Tel el Kebir': 65.0},
        'civilian_casualties': 0, 'infrastructure_damage': {},
        'expedition': {'stage': 'none', 'route': None, 'landing_due_turn': None},
        'battles': [], 'territorial_control': {},
    }


def _nation(world, name):
    return next((nation for nation in world['nations'] if nation.name == name), None)


def _tile(world, location):
    tile_name = world['scenario_state']['geography']['sites'][location]['tile']
    return next((tile for tile in world['tiles'] if tile.name == tile_name), None)


def _bombardment_state(world, tile):
    campaign = world['scenario_state']['campaign']
    fort = campaign['forts']['Alexandria']
    fleet = world['scenario_state']['geography']['fleets'].get('Britain', {})
    households = [agent for agent in tile.agents
                  if getattr(agent, 'alive', True)
                  and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False)]
    return {
        'fort_integrity': float(fort['integrity']),
        'fort_ammunition': int(fort['ammunition']),
        'british_fleet_damage': float(fleet.get('damage', 0.0)),
        'civilian_casualty_counter': int(campaign['civilian_casualties']),
        'infrastructure_damage': float(
            campaign['infrastructure_damage'].get('Alexandria', 0.0)),
        'tile_unrest': float(getattr(tile, 'unrest_level', 0.0)),
        'landing_due_turn': campaign['expedition'].get('landing_due_turn'),
        'eligible_households': [
            {'agent_id': str(getattr(agent, 'id', 'unknown')),
             'health_attrition': float(getattr(agent, 'health_attrition', 0.0))}
            for agent in households],
    }


def _trace_bombardment(world, tile, *, operation_id, success, reason,
                       before, after, details=None):
    from run_trace import emit
    return emit(
        tile, kind=('alexandria_bombardment_resolved' if success else
                    'alexandria_bombardment_rejected'),
        record_class='outcome' if success else 'decision', phase='campaign',
        subject={'type': 'nation/action', 'id': 'Britain:bombard_Alexandria',
                 'nation': 'Britain', 'action_id': 'bombard_Alexandria'},
        metric_id='scenario.bombardment', unit='success',
        before=0, after=int(bool(success)),
        formula_id='campaign.alexandria_bombardment.v1',
        inputs={'operation_id': operation_id, 'turn': int(world['turn']),
                'success': bool(success), 'reason': reason,
                'state_before': before, 'state_after': after,
                **(details or {})})


def bombard_alexandria(world):
    tile = _tile(world, 'Alexandria')
    turn = int(world['turn'])
    clock = getattr(tile, '_collective_trace_clock', None)
    ordinal = int(clock.get('next', 1)) if clock is not None else turn
    operation_id = f'alexandria-bombardment:{turn}:{ordinal}'
    before = _bombardment_state(world, tile)
    if not fleet_at(world, 'Britain', 'Alexandria'):
        fleet = world['scenario_state']['geography']['fleets'].get('Britain')
        if fleet is None:
            reason = 'british_fleet_missing'
        elif fleet.get('location') != 'Alexandria':
            reason = 'british_fleet_not_at_alexandria'
        elif int(fleet.get('ships', 0)) <= 0:
            reason = 'british_fleet_has_no_ships'
        elif int(fleet.get('coal', 0)) <= 0:
            reason = 'british_fleet_out_of_coal'
        else:
            reason = 'british_fleet_unsupplied'
        _trace_bombardment(
            world, tile, operation_id=operation_id, success=False,
            reason=reason, before=before, after=before,
            details={'british_fleet_state': dict(fleet) if fleet else None})
        return False, 'No supplied British fleet is off Alexandria.'
    state = world['scenario_state']['campaign']
    fort = state['forts']['Alexandria']
    fleet = world['scenario_state']['geography']['fleets']['Britain']
    fort_integrity_before = float(fort['integrity'])
    fort_ammunition_before = int(fort['ammunition'])
    fleet_damage_before = float(fleet['damage'])
    france = world['scenario_state']['geography']['fleets'].get('France')
    french_fleet_present = bool(
        france and fleet_at(world, 'France', 'Alexandria'))
    french_authorized = bool(
        world['scenario_state'].get('diplomatic_crisis', {})
        .get('french_authorization', {}).get('bombard'))
    french_fire = bool(france and french_fleet_present and french_authorized)
    battery_active = fort['ammunition'] > 0 and fort['integrity'] > 0
    if battery_active:
        fleet['damage'] = min(0.95, fleet['damage'] + 0.05 * fort['integrity'] / 100)
        fort['ammunition'] = max(0, fort['ammunition'] - 3)
    french_guns = france['guns'] * (1 - france['damage']) if french_fire else 0.0
    british_effective_guns = fleet['guns'] * (1 - fleet['damage'])
    strike = max(8.0, (british_effective_guns + french_guns) * 0.70)
    fort['integrity'] = max(0.0, fort['integrity'] - strike)
    alexandria = _tile(world, 'Alexandria')
    damage = min(1.0, state['infrastructure_damage'].get('Alexandria', 0.0) + strike / 300)
    state['infrastructure_damage']['Alexandria'] = damage
    alexandria.scenario_infrastructure_damage = damage
    households = [agent for agent in alexandria.agents if getattr(agent, 'alive', True)
                  and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False)]
    casualties = min(len(households), max(1, int(strike / 24)))
    injured_households = []
    for agent in households[:casualties]:
        attrition_before = float(getattr(agent, 'health_attrition', 0.0))
        agent.health_attrition = min(2.5, attrition_before + 0.50)
        injured_households.append({
            'agent_id': str(getattr(agent, 'id', 'unknown')),
            'health_attrition_before': attrition_before,
            'health_attrition_after': float(agent.health_attrition),
        })
    state['civilian_casualties'] += casualties
    alexandria.unrest_level = min(1.0, float(getattr(alexandria, 'unrest_level', 0)) + 0.20)
    state['expedition']['landing_due_turn'] = int(world['turn']) + 1
    message = (f'British guns damage Alexandria’s fort to {fort["integrity"]:.0f}% integrity; '
               f'{casualties} civilians are injured and port damage reaches {damage:.0%}.')
    after = _bombardment_state(world, alexandria)
    _trace_bombardment(
        world, alexandria, operation_id=operation_id, success=True,
        reason='supplied_british_fleet_at_alexandria', before=before, after=after,
        details={
            'fort_battery_active': battery_active,
            'fort_integrity_before': fort_integrity_before,
            'fort_ammunition_before': fort_ammunition_before,
            'fort_ammunition_spent': (fort_ammunition_before
                                      - int(fort['ammunition'])),
            'fleet_damage_before': fleet_damage_before,
            'fleet_damage_after': float(fleet['damage']),
            'british_guns': float(fleet['guns']),
            'british_effective_guns_after_battery_hit': float(british_effective_guns),
            'french_fleet_present': french_fleet_present,
            'french_bombardment_authorized': french_authorized,
            'french_fire_authorized': french_fire,
            'french_effective_guns': float(french_guns),
            'strike': float(strike),
            'strike_rule': 'max(8.0, (british_effective_guns + french_guns) * 0.70)',
            'fort_integrity_rule': 'max(0.0, integrity_before - strike)',
            'infrastructure_damage_rule': 'min(1.0, previous_damage + strike / 300)',
            'eligible_household_count': len(households),
            'casualty_rule': 'min(eligible_households, max(1, int(strike / 24)))',
            'casualties': int(casualties),
            'injured_households': injured_households,
            'health_attrition_increment': 0.50,
            'health_attrition_cap': 2.5,
            'unrest_rule': 'min(1.0, unrest_before + 0.20)',
            'landing_due_turn_rule': 'turn + 1',
            'result_message': message})
    return True, message


def landing_options(world):
    state = world['scenario_state']
    from scenario_projects import effectiveness
    line = effectiveness(world, 'canal_line', 'Tel el Kebir')
    egypt = _nation(world, 'Egypt')
    from scenario_debt import outstanding
    cost = outstanding(world) * .5
    return [
        {'id': 'defend_alexandria', 'label': 'Defend Alexandria', 'enabled': True,
         'tooltip': 'Fight a landing at Alexandria with the local garrison and damaged batteries. The shared battle model determines losses and control.'},
        {'id': 'defend_canal', 'label': 'Hold the canal line', 'enabled': True,
         'tooltip': ('Move the Alexandria garrison to Tel el Kebir. '
                     f'Paid works add {55 * line:.0f} trench strength now. '
                     'If the canal is open Britain must sail via Port Said and Ismailia, paying supply and tolls. '
                     'If access is closed it may change course to the less defended Alexandria port.')},
        {'id': 'evacuate_port', 'label': 'Evacuate Alexandria', 'enabled': True,
         'tooltip': 'Withdraw the garrison to Cairo without battle; Britain takes the port, while the army survives.'},
        {'id': 'negotiate_landing', 'label': f'Negotiate • pay {cost:.0f}',
         'enabled': egypt.government.agent.cash >= cost,
         'tooltip': f'Pay {cost:.0f} now to settle the claim and stop the landing; give up 10 points of fiscal autonomy.'},
    ]


def _move_egypt_garrison(world, destination):
    egypt = _nation(world, 'Egypt')
    unit_id = world['scenario_state']['politics'].get('garrison_id')
    unit = next((u for u in egypt.military_units if u.unit_id == unit_id), None)
    if unit is None:
        return None
    old_tile = next((tile for tile in egypt.tiles if tile.name == unit.region_name), None)
    new_tile = _tile(world, destination)
    if old_tile is not None and unit in getattr(old_tile, 'military_units', []):
        old_tile.military_units.remove(unit)
    if not hasattr(new_tile, 'military_units'):
        new_tile.military_units = []
    new_tile.military_units.append(unit)
    unit.region_name = new_tile.name
    return unit


def _battle(world, location, *, trace_event_ids=None):
    state = world['scenario_state']['campaign']
    fleet = world['scenario_state']['geography']['fleets']['Britain']
    egypt = _nation(world, 'Egypt')
    britain = _nation(world, 'Britain')
    tile = _tile(world, location)
    troops = int(fleet['transports'])
    attackers = MilitaryUnit(f'guided_british_landing_{location}', 'Britain', tile.name,
                             soldiers=troops, morale=max(.4, 1.0 - fleet['damage']),
                             wage_per_soldier=.05, food_per_soldier=0)
    defenders = [unit for unit in getattr(tile, 'military_units', [])
                 if unit.nation_name == 'Egypt' and unit.soldiers > 0]
    integrity = (state['forts'][location]['integrity'] if location in state['forts']
                 else state['trench_strength'].get(location, 0))
    project_bonus = 0.0
    if location == 'Tel el Kebir':
        from scenario_projects import effectiveness
        project_bonus = 55.0 * effectiveness(world, 'canal_line', location)
        integrity += project_bonus
    bonus = 1.0 + integrity / 100 * .5
    soldiers_before = troops + sum(unit.soldiers for unit in defenders)
    attack_strength_before = attackers.strength
    defense_strength_before = sum(unit.strength for unit in defenders) * bonus
    outcome = resolve_battle([attackers], defenders, defense_bonus=bonus)
    from run_trace import emit
    battle_event_id = emit(
        tile, kind='war_battle_outcome', record_class='outcome', phase='scenario',
        subject={'type': 'tile', 'id': tile.name,
                 'attacker': 'Britain', 'defender': 'Egypt'},
        metric_id='war.battle', unit='soldiers', before=soldiers_before,
        after=attackers.soldiers + sum(unit.soldiers for unit in defenders),
        inputs={'attack_strength_before': attack_strength_before,
                'defense_strength_before': defense_strength_before,
                'defense_bonus': bonus, 'location': location,
                'project_defense_bonus': project_bonus, **outcome})
    if battle_event_id is not None and trace_event_ids is not None:
        trace_event_ids.append(battle_event_id)
    fleet['transports'] = attackers.soldiers
    outcome.update(location=location, turn=int(world['turn']),
                   egyptian_defenders=sum(unit.soldiers for unit in defenders),
                   defense_project_bonus=round(project_bonus, 2))
    state['battles'].append(outcome)
    if project_bonus:
        from scenario_projects import damage_project
        damage_project(world, 'canal_line', location, .35,
                       cause_event_ids=[battle_event_id]
                       if battle_event_id is not None else None)
    if outcome['winner'] == 'attacker':
        state['territorial_control'][location] = 'Britain'
        control_event_id = emit(
            tile, kind='war_territory_transfer', record_class='outcome', phase='scenario',
            subject={'type': 'tile', 'id': tile.name},
            metric_id='war.territory_control', before='Egypt', after='Britain',
            inputs={'battle_winner': outcome['winner'], 'location': location,
                    'operation': 'guided_landing'})
        if control_event_id is not None and trace_event_ids is not None:
            trace_event_ids.append(control_event_id)
        state['expedition']['stage'] = 'foothold'
        state['expedition']['foothold_turn'] = int(world['turn'])
        britain.military_units.append(attackers)
        if not hasattr(tile, 'military_units'):
            tile.military_units = []
        tile.military_units.append(attackers)
        egypt.legitimacy = max(0.0, egypt.legitimacy - .05)
        result = f'British troops gain a foothold at {location}'
    else:
        state['expedition']['stage'] = 'repelled'
        result = f'Egyptian defenses repel the landing at {location}'
    return (f'{result}; British losses {outcome["atk_losses"]}, '
            f'Egyptian losses {outcome["def_losses"]}.')


def _expedition_operation_id(world):
    tile = _tile(world, 'Alexandria')
    clock = getattr(tile, '_collective_trace_clock', None)
    ordinal = int(clock.get('next', 1)) if clock is not None else int(world['turn'])
    return f'expedition-step:{int(world["turn"])}:{ordinal}'


def _trace_expedition_step(world, *, operation_id, status, reason,
                           before, after, details=None, cause_event_ids=None):
    from run_trace import emit
    tile = _tile(world, 'Alexandria')
    record_class = 'decision' if status == 'gate_blocked' else 'outcome'
    return emit(
        tile, kind='expedition_step_resolved', record_class=record_class,
        phase='campaign',
        subject={'type': 'scenario/operation', 'id': operation_id},
        metric_id='scenario.expedition_step', unit='stage',
        before=before['expedition_stage'], after=after['expedition_stage'],
        formula_id='campaign.expedition_step.v1',
        inputs={'operation_id': operation_id, 'turn': int(world['turn']),
                'status': status, 'reason': reason,
                'state_before': before, 'state_after': after,
                **(details or {})},
        cause_event_ids=cause_event_ids)


def _fleet_movement_failure_reason(world, nation_name, destination):
    geography = world['scenario_state']['geography']
    fleet = geography['fleets'].get(nation_name)
    if fleet is None:
        return 'fleet_missing'
    if not fleet.get('supplied'):
        return 'fleet_unsupplied'
    if int(fleet.get('coal', 0)) <= 0:
        return 'fleet_out_of_coal'
    origin = fleet.get('location')
    if destination not in geography['routes'].get(origin, ()):
        return 'destination_not_on_route'
    if destination in ('Tel el Kebir', 'Cairo', 'Nile Delta', 'Upper Egypt'):
        return 'destination_is_army_route_not_navigable'
    from scenario_geography import canal_access
    if destination == 'Ismailia' and not canal_access(world, nation_name):
        return 'canal_access_denied'
    if destination == 'Ismailia' and nation_name != 'Egypt':
        payer = next((n for n in world['nations'] if n.name == nation_name), None)
        egypt = _nation(world, 'Egypt')
        if payer is None or egypt is None:
            return 'canal_toll_treasury_unavailable'
        if payer.government.agent.cash < 2.0:
            return 'canal_toll_unaffordable'
    return 'fleet_movement_rejected'


def advance_expedition(world):
    """Return True when campaign movement or a landing decision took the turn."""
    state = world['scenario_state']
    campaign = state['campaign']
    expedition = campaign['expedition']
    stage = expedition['stage']
    turn = int(world['turn'])
    if stage == 'none' and state['naval_crisis'].get('stage') == 'blockaded':
        due = expedition.get('landing_due_turn')
        if due is not None and turn >= due:
            before = _landing_action_state(world)
            operation_id = _expedition_operation_id(world)
            fleet = state['geography']['fleets'].get('Britain')
            if not fleet_at(world, 'Britain', 'Alexandria'):
                if fleet is None:
                    reason = 'british_fleet_missing'
                elif fleet.get('location') != 'Alexandria':
                    reason = 'british_fleet_not_at_alexandria'
                elif int(fleet.get('ships', 0)) <= 0:
                    reason = 'british_fleet_has_no_ships'
                elif int(fleet.get('coal', 0)) <= 0:
                    reason = 'british_fleet_out_of_coal'
                else:
                    reason = 'british_fleet_unsupplied'
                _trace_expedition_step(
                    world, operation_id=operation_id, status='gate_blocked',
                    reason=reason, before=before, after=before,
                    details={'landing_due_turn': int(due), 'turn': turn,
                             'british_fleet_state': dict(fleet) if fleet else None,
                             'required_location': 'Alexandria'})
                return False
            if fleet['transports'] < 10:
                _trace_expedition_step(
                    world, operation_id=operation_id, status='gate_blocked',
                    reason='transport_capacity_below_minimum',
                    before=before, after=before,
                    details={'landing_due_turn': int(due), 'turn': turn,
                             'transport_capacity': int(fleet['transports']),
                             'minimum_transport_capacity': 10})
                return False
            world['scenario_warning_modal'] = {'kind': 'landing_warning'}
            world['playing'] = False
            after = _landing_action_state(world)
            _trace_expedition_step(
                world, operation_id=operation_id, status='landing_warning_opened',
                reason='fleet_and_transport_gates_passed', before=before, after=after,
                details={'landing_due_turn': int(due), 'turn': turn,
                         'transport_capacity': int(fleet['transports']),
                         'minimum_transport_capacity': 10,
                         'warning_modal_opened': True, 'playing_after': False})
            return True
    if stage in ('sailing_canal', 'marching_tel'):
        fleet = state['geography']['fleets']['Britain']
        before = _landing_action_state(world)
        operation_id = _expedition_operation_id(world)
        from scenario_gunboat import _transfer_to_households, withdraw
        from scenario_gunboat import _record
        from scenario_situation import situation_template
        cost = float(situation_template()['naval_crisis']['upkeep_per_turn'])
        step_event_ids = []
        if not _transfer_to_households(
                world, _nation(world, 'Britain'), cost,
                source='british_canal_expedition_supply', phase='campaign',
                trace_event_ids=step_event_ids):
            expedition['stage'] = 'repelled'
            withdraw(world, 'Britain cannot supply its canal expedition; the squadron withdraws.',
                     cause='unsustainable',
                     cause_event_ids=step_event_ids or None)
            after = _landing_action_state(world)
            _trace_expedition_step(
                world, operation_id=operation_id,
                status='supply_failure_withdrawal',
                reason='expedition_supply_gate_failed', before=before, after=after,
                details={'stage_at_start': stage, 'upkeep_requested': cost,
                         'supply_event_ids': list(step_event_ids)},
                cause_event_ids=step_event_ids or None)
            return True
        details = {'stage_at_start': stage, 'upkeep_requested': cost,
                   'upkeep_paid': True,
                   'supply_event_ids': list(step_event_ids)}
        if stage == 'marching_tel':
            message = _battle(world, 'Tel el Kebir',
                              trace_event_ids=step_event_ids)
            _record(world, message, 'WAR')
            if expedition['stage'] == 'repelled':
                withdraw(world, 'Egyptian defenders hold Tel el Kebir; the British expedition withdraws.',
                         cause='military_defeat',
                         cause_event_ids=step_event_ids or None)
            after = _landing_action_state(world)
            won = after['expedition_stage'] != 'repelled'
            _trace_expedition_step(
                world, operation_id=operation_id, status='battle_resolved',
                reason=('british_force_gained_foothold' if won
                        else 'egyptian_defense_repelled_british_force'),
                before=before, after=after,
                details={**details, 'battle_location': 'Tel el Kebir',
                         'battle_result': dict(campaign['battles'][-1]),
                         'result_message': message},
                cause_event_ids=step_event_ids or None)
            return True
        route = {'Alexandria': 'Mediterranean', 'Mediterranean': 'Port Said',
                 'Port Said': 'Ismailia'}
        origin = fleet['location']
        destination = route.get(origin)
        moved = (move_fleet(world, 'Britain', destination,
                            trace_event_ids=step_event_ids)
                 if destination is not None else False)
        if not moved:
            movement_reason = (_fleet_movement_failure_reason(
                world, 'Britain', destination) if destination is not None
                else 'no_mapped_fleet_destination')
            expedition['stage'] = 'repelled'
            withdraw(world, 'Canal denial or lost supply stops the British landing campaign.',
                     cause='deterrence',
                     cause_event_ids=step_event_ids or None)
            after = _landing_action_state(world)
            _trace_expedition_step(
                world, operation_id=operation_id, status='movement_blocked',
                reason=movement_reason, before=before, after=after,
                details={**details, 'fleet_origin': origin,
                         'planned_destination': destination,
                         'fleet_state_after_supply': dict(fleet)},
                cause_event_ids=step_event_ids or None)
            return True
        if destination == 'Ismailia':
            expedition['stage'] = 'marching_tel'
            message = 'British troops land at Ismailia and prepare to march toward the Tel el Kebir line.'
            _record(world, message, 'WAR')
        else:
            message = f'British expedition advances from {origin} to {destination}.'
        after = _landing_action_state(world)
        _trace_expedition_step(
            world, operation_id=operation_id, status='fleet_moved',
            reason='supply_paid_and_route_step_completed', before=before, after=after,
            details={**details, 'fleet_origin': origin,
                     'fleet_destination': destination,
                     'result_message': message},
            cause_event_ids=step_event_ids or None)
        return True
    return False


def _landing_action_state(world):
    state = world['scenario_state']
    campaign = state['campaign']
    expedition = campaign['expedition']
    egypt = _nation(world, 'Egypt')
    britain = _nation(world, 'Britain')
    fleet = state.get('geography', {}).get('fleets', {}).get('Britain', {})
    garrison_id = state.get('politics', {}).get('garrison_id')
    garrison = next((unit for unit in getattr(egypt, 'military_units', [])
                     if getattr(unit, 'unit_id', None) == garrison_id), None)
    landing_units = [
        {'unit_id': str(getattr(unit, 'unit_id', 'unknown')),
         'region': str(getattr(unit, 'region_name', '')),
         'soldiers': int(getattr(unit, 'soldiers', 0))}
        for unit in getattr(britain, 'military_units', [])
        if str(getattr(unit, 'unit_id', '')).startswith('guided_british_landing_')]
    from scenario_debt import outstanding
    return {
        'expedition_stage': expedition.get('stage'),
        'expedition_route': expedition.get('route'),
        'landing_due_turn': expedition.get('landing_due_turn'),
        'territorial_control': dict(campaign.get('territorial_control', {})),
        'battle_count': len(campaign.get('battles', [])),
        'last_battle': (dict(campaign['battles'][-1])
                        if campaign.get('battles') else None),
        'british_fleet': {key: fleet.get(key) for key in
                          ('location', 'transports', 'damage', 'guns')},
        'egyptian_garrison': (
            {'unit_id': str(garrison.unit_id),
             'region': str(garrison.region_name),
             'soldiers': int(garrison.soldiers)} if garrison else None),
        'british_landing_units': landing_units,
        'egypt_treasury_cash': (float(egypt.government.agent.cash)
                                if egypt is not None else None),
        'britain_treasury_cash': (float(britain.government.agent.cash)
                                  if britain is not None else None),
        'egypt_legitimacy': (float(egypt.legitimacy)
                             if egypt is not None else None),
        'egypt_fiscal_autonomy': float(state.get('fiscal_autonomy', 0.0)),
        'egypt_payment_status': state.get('payment_status'),
        'debt_outstanding': float(outstanding(world)),
        'debt_ledger_count': len(state.get('debt_ledger', [])),
        'naval_crisis_stage': state.get('naval_crisis', {}).get('stage'),
        'canal_open': state.get('geography', {}).get('canal_open'),
    }


def _landing_action_operation_id(world, response_id):
    tile = _tile(world, 'Alexandria')
    clock = getattr(tile, '_collective_trace_clock', None)
    ordinal = int(clock.get('next', 1)) if clock is not None else int(world['turn'])
    return f'landing-response:{response_id}:{int(world["turn"])}:{ordinal}'


def _trace_landing_response(world, *, response_id, operation_id, success,
                            reason, before, after, details=None,
                            cause_event_ids=None):
    from run_trace import emit
    tile = _tile(world, 'Alexandria')
    egypt = _nation(world, 'Egypt')
    changed = before != after
    return emit(
        tile, kind=('landing_response_resolved' if success else
                    'landing_response_rejected'),
        record_class='outcome' if success or changed else 'decision',
        phase='campaign',
        subject={'type': 'nation/action',
                 'id': f'{getattr(egypt, "name", "Egypt")}:{response_id}',
                 'nation': getattr(egypt, 'name', 'Egypt'),
                 'action_id': response_id},
        metric_id='scenario.landing_response', unit='success',
        before=0, after=int(bool(success)),
        formula_id='campaign.landing_response.v1',
        inputs={'operation_id': operation_id, 'response_id': response_id,
                'turn': int(world['turn']), 'success': bool(success),
                'reason': reason, 'state_before': before,
                'state_after': after, **(details or {})},
        cause_event_ids=cause_event_ids)


def resolve_landing(world, response_id):
    state = world['scenario_state']
    expedition = state['campaign']['expedition']
    operation_id = _landing_action_operation_id(world, response_id)
    before_state = _landing_action_state(world)
    if (world.get('scenario_warning_modal') or {}).get('kind') != 'landing_warning':
        _trace_landing_response(
            world, response_id=response_id, operation_id=operation_id,
            success=False, reason='no_landing_decision_pending',
            before=before_state, after=before_state)
        return False, 'No landing decision is pending.'
    option = next((item for item in landing_options(world) if item['id'] == response_id), None)
    if not option or not option['enabled']:
        details = {'option_found': option is not None,
                   'option_enabled': bool(option and option['enabled'])}
        reason = ('unknown_landing_response' if option is None
                  else 'landing_response_funding_gate')
        if response_id == 'negotiate_landing':
            from scenario_debt import outstanding
            egypt = _nation(world, 'Egypt')
            amount = round(outstanding(world) * .5, 2)
            details.update({
                'required_cash': amount,
                'egypt_treasury_cash': float(egypt.government.agent.cash),
                'debt_outstanding': float(outstanding(world)),
                'payment_gate_met': egypt.government.agent.cash >= amount})
        _trace_landing_response(
            world, response_id=response_id, operation_id=operation_id,
            success=False, reason=reason, before=before_state,
            after=before_state, details=details)
        return False, 'That landing order is unavailable.'
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    action_details = {'option_label': option['label'],
                      'decision_basis': 'player_selected_landing_response'}
    cause_event_ids = []
    if response_id == 'defend_alexandria':
        message = _battle(world, 'Alexandria', trace_event_ids=cause_event_ids)
        action_details['battle_location'] = 'Alexandria'
        if expedition['stage'] == 'repelled':
            from scenario_gunboat import withdraw
            withdraw(world, message, cause='military_defeat')
    elif response_id == 'defend_canal':
        moved_garrison = _move_egypt_garrison(world, 'Tel el Kebir')
        from scenario_geography import canal_access
        from scenario_projects import effectiveness
        from scenario_situation import situation_template
        from scenario_gunboat import withdraw
        britain = _nation(world, 'Britain')
        line = effectiveness(world, 'canal_line', 'Tel el Kebir')
        upkeep = float(situation_template()['naval_crisis']['upkeep_per_turn'])
        forecast = 3 * upkeep + 2 + 12 * line
        access = bool(canal_access(world, 'Britain'))
        action_details.update({
            'garrison_moved': moved_garrison is not None,
            'garrison_unit_id': (str(moved_garrison.unit_id)
                                 if moved_garrison is not None else None),
            'canal_access': access, 'canal_line_effectiveness': float(line),
            'upkeep_per_turn': upkeep, 'forecast_cash_required': forecast,
            'british_cash_available': float(britain.government.agent.cash)})
        if not access:
            message = _battle(world, 'Alexandria',
                              trace_event_ids=cause_event_ids)
            expedition['route'] = 'Alexandria after canal denial'
            action_details['route_decision'] = 'canal_denial_reroutes_landing'
            if expedition['stage'] == 'repelled':
                withdraw(world, message, cause='military_defeat')
        elif britain.government.agent.cash < forecast:
            expedition['stage'] = 'repelled'
            action_details['route_decision'] = 'expedition_unaffordable'
            withdraw(world, 'Britain cannot fund a canal march against the prepared line.', cause='deterrence')
            message = world['scenario_feedback']
        elif line >= .5 and britain.government.agent.cash < forecast + 12:
            expedition['landing_due_turn'] = int(world['turn']) + 2
            state['naval_crisis']['last_offer_turn'] = int(world['turn'])
            action_details['route_decision'] = 'delay_for_egyptian_terms'
            action_details['delay_turns'] = 2
            message = ('Britain delays the canal march and maintains the costly blockade '
                       'while London weighs Egyptian terms.')
        else:
            expedition.update(stage='sailing_canal', route='Port Said–Ismailia–Tel el Kebir')
            state['naval_crisis']['stage'] = 'campaign'
            action_details['route_decision'] = 'funded_canal_expedition'
            message = ('Egyptian troops hold Tel el Kebir; Britain must pay to sail via '
                       'Port Said and Ismailia before marching inland.')
        port = state['naval_crisis'].get('port_tile')
        from macro.imperialism.manager import get_imperialism_manager
        manager = get_imperialism_manager()
        if port and manager.blockade_enforcers.get(port) == 'Britain':
            if expedition['stage'] == 'sailing_canal':
                manager.lift_blockade(port, world, int(world['turn']))
                action_details['blockade_lifted_at_port'] = port
        from scenario_gunboat import _record
        _record(world, message)
        message = world['scenario_feedback']
    elif response_id == 'evacuate_port':
        moved_garrison = _move_egypt_garrison(world, 'Cairo')
        state['campaign']['territorial_control']['Alexandria'] = 'Britain'
        expedition['stage'] = 'foothold'
        expedition['foothold_turn'] = int(world['turn'])
        alexandria = _tile(world, 'Alexandria')
        fleet = state['geography']['fleets']['Britain']
        landing = MilitaryUnit('guided_british_landing_Alexandria', 'Britain', alexandria.name,
                               soldiers=int(fleet['transports']), wage_per_soldier=.05,
                               food_per_soldier=0)
        _nation(world, 'Britain').military_units.append(landing)
        alexandria.military_units.append(landing)
        action_details.update({
            'garrison_moved': moved_garrison is not None,
            'garrison_unit_id': (str(moved_garrison.unit_id)
                                 if moved_garrison is not None else None),
            'landing_unit_id': landing.unit_id,
            'landing_unit_soldiers': int(landing.soldiers),
            'landing_tile': alexandria.name})
        message = 'The Egyptian garrison withdraws to Cairo; Britain lands at an undefended Alexandria.'
    else:
        from scenario_debt import pay as pay_debt, outstanding
        amount = outstanding(world) * .5
        ok, reason = pay_debt(world, amount, kind='landing_settlement', forgive_remainder=True)
        if not ok:
            after_state = _landing_action_state(world)
            _trace_landing_response(
                world, response_id=response_id, operation_id=operation_id,
                success=False, reason='debt_settlement_payment_failed',
                before=before_state, after=after_state,
                details={**action_details, 'payment_reason': reason,
                         'requested_payment': float(amount),
                         'debt_ledger_entries_added': state.get(
                             'debt_ledger', [])[before_state['debt_ledger_count']:]})
            return False, reason
        state['payment_status'] = 'restructured'
        autonomy_before = float(state['fiscal_autonomy'])
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - .10)
        expedition['stage'] = 'settled'
        from scenario_gunboat import withdraw
        withdraw(world, 'Cairo negotiates a settlement before the landing; the fleet withdraws.', cause='settlement')
        action_details.update({'requested_payment': float(amount),
                               'payment_status': 'paid_and_remaining_claim_forgiven',
                               'fiscal_autonomy_before': autonomy_before,
                               'fiscal_autonomy_after': float(state['fiscal_autonomy']),
                               'fiscal_autonomy_rule': 'max(0.0, before - 0.10)'})
        message = world['scenario_feedback']
    from scenario_gunboat import _record
    _record(world, message, 'WAR')
    from scenario_occupation import reserve_occupation_window
    reserve_occupation_window(world)
    record_change(world, response_id, before, snapshot(world))
    state.setdefault('actions_taken', []).append({'turn': int(world['turn']), 'action': response_id,
                                                   'message': message})
    after_state = _landing_action_state(world)
    action_details['result_message'] = message
    if response_id == 'negotiate_landing':
        action_details['debt_ledger_entries_added'] = state.get(
            'debt_ledger', [])[before_state['debt_ledger_count']:]
    _trace_landing_response(
        world, response_id=response_id, operation_id=operation_id,
        success=True, reason='landing_response_applied',
        before=before_state, after=after_state, details=action_details,
        cause_event_ids=cause_event_ids or None)
    return True, message

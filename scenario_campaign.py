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


def bombard_alexandria(world):
    if not fleet_at(world, 'Britain', 'Alexandria'):
        return False, 'No supplied British fleet is off Alexandria.'
    state = world['scenario_state']['campaign']
    fort = state['forts']['Alexandria']
    fleet = world['scenario_state']['geography']['fleets']['Britain']
    if fort['ammunition'] > 0 and fort['integrity'] > 0:
        fleet['damage'] = min(0.95, fleet['damage'] + 0.05 * fort['integrity'] / 100)
        fort['ammunition'] = max(0, fort['ammunition'] - 3)
    strike = max(8.0, fleet['guns'] * (1 - fleet['damage']) * 0.70)
    fort['integrity'] = max(0.0, fort['integrity'] - strike)
    alexandria = _tile(world, 'Alexandria')
    damage = min(1.0, state['infrastructure_damage'].get('Alexandria', 0.0) + strike / 300)
    state['infrastructure_damage']['Alexandria'] = damage
    alexandria.scenario_infrastructure_damage = damage
    households = [agent for agent in alexandria.agents if getattr(agent, 'alive', True)
                  and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False)]
    casualties = min(len(households), max(1, int(strike / 24)))
    for agent in households[:casualties]:
        agent.health_attrition = min(2.5, float(getattr(agent, 'health_attrition', 0.0)) + 0.50)
    state['civilian_casualties'] += casualties
    alexandria.unrest_level = min(1.0, float(getattr(alexandria, 'unrest_level', 0)) + 0.20)
    state['expedition']['landing_due_turn'] = int(world['turn']) + 1
    return True, (f'British guns damage Alexandria’s fort to {fort["integrity"]:.0f}% integrity; '
                  f'{casualties} civilians are injured and port damage reaches {damage:.0%}.')


def landing_options(world):
    state = world['scenario_state']
    can_canal = state['geography']['canal_open']
    egypt = _nation(world, 'Egypt')
    cost = float(state.get('scheduled_remittance', 0)) * .5
    return [
        {'id': 'defend_alexandria', 'label': 'Defend Alexandria', 'enabled': True,
         'tooltip': 'Fight a landing at Alexandria with the local garrison and damaged batteries. The shared battle model determines losses and control.'},
        {'id': 'defend_canal', 'label': 'Hold the canal line', 'enabled': can_canal,
         'tooltip': 'Move the Alexandria garrison to Tel el Kebir, west of Ismailia. Britain must sail via Port Said, pay tolls, then march to the defensive line.'},
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


def _battle(world, location):
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
    bonus = 1.0 + integrity / 100 * .5
    outcome = resolve_battle([attackers], defenders, defense_bonus=bonus)
    fleet['transports'] = attackers.soldiers
    outcome.update(location=location, turn=int(world['turn']),
                   egyptian_defenders=sum(unit.soldiers for unit in defenders))
    state['battles'].append(outcome)
    if outcome['winner'] == 'attacker':
        state['territorial_control'][location] = 'Britain'
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


def advance_expedition(world):
    """Return True when campaign movement or a landing decision took the turn."""
    state = world['scenario_state']
    campaign = state['campaign']
    expedition = campaign['expedition']
    stage = expedition['stage']
    if stage == 'none' and state['naval_crisis'].get('stage') == 'blockaded':
        due = expedition.get('landing_due_turn')
        if due is not None and int(world['turn']) >= due:
            if not fleet_at(world, 'Britain', 'Alexandria'):
                return False
            if state['geography']['fleets']['Britain']['transports'] < 10:
                return False
            world['scenario_warning_modal'] = {'kind': 'landing_warning'}
            world['playing'] = False
            return True
    if stage in ('sailing_canal', 'marching_tel'):
        fleet = state['geography']['fleets']['Britain']
        from scenario_gunboat import _transfer_to_households, withdraw
        from scenario_situation import situation_template
        cost = float(situation_template()['naval_crisis']['upkeep_per_turn'])
        if not _transfer_to_households(_nation(world, 'Britain'), cost):
            expedition['stage'] = 'repelled'
            withdraw(world, 'Britain cannot supply its canal expedition; the squadron withdraws.', cause='unsustainable')
            return True
        if stage == 'marching_tel':
            message = _battle(world, 'Tel el Kebir')
            from scenario_gunboat import _record
            _record(world, message, 'WAR')
            if expedition['stage'] == 'repelled':
                withdraw(world, 'Egyptian defenders hold Tel el Kebir; the British expedition withdraws.', cause='military_defeat')
            return True
        route = {'Alexandria': 'Mediterranean', 'Mediterranean': 'Port Said',
                 'Port Said': 'Ismailia'}
        destination = route.get(fleet['location'])
        if destination is None or not move_fleet(world, 'Britain', destination):
            expedition['stage'] = 'repelled'
            withdraw(world, 'Canal denial or lost supply stops the British landing campaign.', cause='deterrence')
            return True
        if destination == 'Ismailia':
            expedition['stage'] = 'marching_tel'
            from scenario_gunboat import _record
            _record(world, 'British troops land at Ismailia and prepare to march toward the Tel el Kebir line.', 'WAR')
        return True
    return False


def resolve_landing(world, response_id):
    state = world['scenario_state']
    expedition = state['campaign']['expedition']
    if world.get('scenario_warning_modal', {}).get('kind') != 'landing_warning':
        return False, 'No landing decision is pending.'
    option = next((item for item in landing_options(world) if item['id'] == response_id), None)
    if not option or not option['enabled']:
        return False, 'That landing order is unavailable.'
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    if response_id == 'defend_alexandria':
        message = _battle(world, 'Alexandria')
        if expedition['stage'] == 'repelled':
            from scenario_gunboat import withdraw
            withdraw(world, message, cause='military_defeat')
    elif response_id == 'defend_canal':
        _move_egypt_garrison(world, 'Tel el Kebir')
        expedition.update(stage='sailing_canal', route='Port Said–Ismailia–Tel el Kebir')
        state['naval_crisis']['stage'] = 'campaign'
        port = state['naval_crisis'].get('port_tile')
        from macro.imperialism.manager import get_imperialism_manager
        manager = get_imperialism_manager()
        if port and manager.blockade_enforcers.get(port) == 'Britain':
            manager.lift_blockade(port, world, int(world['turn']))
        from scenario_gunboat import _record
        _record(world, 'Egyptian troops hold Tel el Kebir; Britain must sail via Port Said and Ismailia before marching inland.')
        message = world['scenario_feedback']
    elif response_id == 'evacuate_port':
        _move_egypt_garrison(world, 'Cairo')
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
        message = 'The Egyptian garrison withdraws to Cairo; Britain lands at an undefended Alexandria.'
    else:
        from scenario_debt import pay as pay_debt
        amount = float(state['scheduled_remittance']) * .5
        ok, reason = pay_debt(world, amount, kind='landing_settlement', forgive_remainder=True)
        if not ok:
            return False, reason
        state['payment_status'] = 'restructured'
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - .10)
        expedition['stage'] = 'settled'
        from scenario_gunboat import withdraw
        withdraw(world, 'Cairo negotiates a settlement before the landing; the fleet withdraws.', cause='settlement')
        message = world['scenario_feedback']
    from scenario_gunboat import _record
    _record(world, message, 'WAR')
    record_change(world, response_id, before, snapshot(world))
    state.setdefault('actions_taken', []).append({'turn': int(world['turn']), 'action': response_id,
                                                   'message': message})
    return True, message

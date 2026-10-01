"""Egypt's incumbent, cabinet, officers, and civilian coalition in Guided play."""

from __future__ import annotations

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
        if state['officers_paid']:
            return False, 'The officer arrears package has already been funded.'
        cost = float(situation_template()['politics']['officer_pay_cost'])
        if egypt.government.agent.cash < cost:
            return False, f'The treasury needs {cost:,.0f} units to pay officer arrears.'
        garrison_tile = next((tile for tile in egypt.tiles if getattr(tile, 'scenario_location', '') == 'Alexandria'), None)
        recipients = [agent for tile in ([garrison_tile] if garrison_tile else egypt.tiles)
                      for agent in getattr(tile, 'agents', [])
                      if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                      and not getattr(agent, 'is_corporation', False)]
        if not recipients:
            return False, 'No Egyptian households can receive military pay.'
        egypt.government.agent.cash -= cost
        each = cost / len(recipients)
        for agent in recipients:
            agent.cash += each
        state['officers_paid'] = True
        state['army_loyalty'] = _clamp(state['army_loyalty'] + 0.22)
        unit = _garrison(world)
        if unit:
            unit.morale = _clamp(unit.morale + 0.20)
        message = f'Paid {cost:,.0f} units in officer arrears; army loyalty and garrison morale improved.'
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
    unit = _garrison(world)
    morale = float(unit.morale) if unit else 0.0
    people = [person for tile in egypt.tiles for person in tile.agents
              if getattr(person, 'alive', True) and not getattr(person, 'is_government', False)
              and not getattr(person, 'is_corporation', False)
              and not getattr(person, 'is_trader', False)]
    hunger = sum(getattr(person, 'hungry_steps', 0) > 0 for person in people) / max(1, len(people))
    unrest = sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in egypt.tiles) / max(1, len(egypt.tiles))
    foreign_control = 1.0 - float(scenario.get('fiscal_autonomy', 1.0))
    extraction = min(1.0, float(scenario.get('extraction_level', 0)))
    naval_stage = scenario.get('naval_crisis', {}).get('stage')
    naval_coercion = (0.30 if naval_stage == 'blockaded' else
                     0.12 if naval_stage == 'ultimatum' else 0.0)
    new_loyalty = (0.15 + 0.45 * morale + 0.25 * state['officer_access']
                   - 0.20 * foreign_control - 0.10 * unrest - naval_coercion)
    state['army_loyalty'] = _clamp(0.65 * state['army_loyalty'] + 0.35 * new_loyalty)
    civilian_target = (0.12 + 0.35 * unrest + 0.28 * hunger + 0.15 * extraction
                       + (0.12 if state['representative_cabinet'] else 0.0))
    state['civilian_support'] = _clamp(0.7 * state['civilian_support'] + 0.3 * civilian_target)
    grievance = (0.24 * foreign_control + 0.20 * (1.0 - state['officer_access'])
                 + 0.16 * (1.0 - state['army_loyalty']) + 0.14 * state['civilian_support'])
    if naval_stage in ('mobilizing', 'ultimatum', 'blockaded'):
        grievance += 0.16
    state['nationalist_movement'] = _clamp(state['nationalist_movement']
                                          + max(-0.025, grievance * 0.20 - 0.025))
    state['palace_authority'] = _clamp(state['palace_authority']
                                      - 0.025 * foreign_control - 0.03 * unrest
                                      - (0.035 if naval_stage == 'blockaded' else 0.0))
    state['cabinet_authority'] = _clamp(state['cabinet_authority']
                                       + (0.01 if state['representative_cabinet'] else 0.0))
    if world.get('scenario_warning_modal'):
        return
    rules = situation_template()['politics']
    if (not state['deposition_resolved'] and state['ruler'] == 'Ismail Pasha'
            and state['palace_authority'] <= rules['deposition_authority_threshold']
            and scenario.get('fiscal_autonomy', 1.0) <= rules['deposition_autonomy_threshold']):
        world['scenario_warning_modal'] = {'kind': 'dynastic_crisis'}
        world['playing'] = False
        _event(world, 'Ismail’s palace has lost authority under creditor pressure; the succession is contested.')
    elif (not state['crisis_resolved']
          and state['nationalist_movement'] >= rules['movement_threshold']
          and state['army_loyalty'] <= rules['army_loyalty_threshold']):
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
        return False, 'There is no political transition awaiting a decision.'
    if response_id not in {item['id'] for item in response_options(world, kind)}:
        return False, 'That political response is unavailable.'
    state = _state(world)
    scenario = world['scenario_state']
    egypt = _egypt(world)
    from scenario_status import snapshot, record_change
    before = snapshot(world)
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
    _event(world, message)
    record_change(world, response_id, before, snapshot(world))
    scenario.setdefault('actions_taken', []).append({'turn': int(world['turn']),
                                                      'action': response_id, 'message': message})
    return True, message

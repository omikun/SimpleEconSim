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


def _transfer_to_households(nation, amount: float) -> bool:
    """Pay mobilization/supply costs to citizens instead of destroying cash."""
    if nation is None or nation.government.agent.cash < amount:
        return False
    recipient = next((agent for tile in nation.tiles for agent in tile.agents
                      if getattr(agent, 'alive', True)
                      and not getattr(agent, 'is_government', False)
                      and not getattr(agent, 'is_corporation', False)), None)
    if recipient is None:
        return False
    nation.government.agent.cash -= amount
    recipient.cash += amount
    return True


def _record(world: dict, text: str, kind: str = 'NAVAL') -> None:
    state = world['scenario_state']
    state.setdefault('naval_news', []).append({'turn': int(world['turn']), 'text': text})
    world['scenario_feedback'] = text
    from client.desktop.engine import ticker_push
    ticker_push(world, int(world['turn']), kind, text, (230, 126, 95))


def begin_escalation(world: dict, reason: str) -> None:
    state = world['scenario_state']
    crisis = state.setdefault('naval_crisis', {'stage': 'none'})
    if crisis['stage'] not in ('none', 'withdrawn'):
        return
    crisis.update(stage='mobilizing', reason=reason, due_turn=int(world['turn']) + 1,
                  last_offer_turn=-1, french_support=False)
    _record(world, 'Cairo refused collection. Britain is weighing a naval expedition to Alexandria.')


def _remove_squadron(world: dict) -> None:
    state = world['scenario_state']
    crisis = state.get('naval_crisis', {})
    geography = state.get('geography', {})
    geography.get('fleets', {}).pop('Britain', None)
    if crisis.get('port_tile'):
        manager = get_imperialism_manager()
        if manager.blockade_enforcers.get(crisis['port_tile']) == 'Britain':
            manager.lift_blockade(crisis['port_tile'], world, int(world['turn']))
    crisis['unit_id'] = None


def withdraw(world: dict, reason: str) -> None:
    crisis = world['scenario_state']['naval_crisis']
    _remove_squadron(world)
    crisis['stage'] = 'withdrawn'
    _record(world, reason)


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
    if not _transfer_to_households(_nation(world, 'Egypt'), cost):
        return False, f'The treasury needs {cost:,.0f} units and local workers to prepare the batteries.'
    crisis['battery_strength'] = (float(rules['alexandria_battery_strength'])
                                  + float(rules['battery_reinforcement_strength']))
    crisis['reinforced'] = True
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
        withdraw(world, 'No enforceable coastal approach exists at Alexandria; the naval claim lapses.')
        return
    if state.get('payment_status') in ('paid', 'restructured'):
        withdraw(world, 'The debt settlement ends the naval confrontation.')
        return
    british_unrest = _protest(world, 'Britain')
    decisions = foreign_decisions(world)
    if british_unrest >= float(rules['max_british_protest_energy']):
        withdraw(world, 'Domestic unrest in Britain makes the Alexandria expedition untenable.')
        return
    if stage == 'mobilizing':
        if turn < int(crisis['due_turn']):
            return
        if decisions['Britain'] != 'intervene':
            withdraw(world, 'London declines an expedition after reviewing its claim, treasury, and domestic unrest.')
            return
        if _force_ratio(world) < float(rules['minimum_force_ratio']):
            withdraw(world, 'Egyptian coastal defenses make the British naval threat a bluff.')
            return
        if not _transfer_to_households(britain, float(rules['mobilization_cost'])):
            withdraw(world, 'Britain cannot finance and supply a squadron for Alexandria.')
            return
        fleet = create_fleet(world, 'Britain', guns=rules['british_squadron_strength'])
        if not move_fleet(world, 'Britain', 'Alexandria'):
            withdraw(world, 'The British squadron lacks coal for the Alexandria passage.')
            return
        crisis.update(stage='ultimatum', unit_id='guided_british_fleet', port_tile=alexandria.name,
                      french_support=decisions['France'] == 'support_demand')
        partner = {'support_demand': 'France supports the demand but sends no ships',
                   'abstain': 'France abstains', 'oppose': 'France opposes armed enforcement'}[decisions['France']]
        _record(world, f'A British squadron reaches Alexandria; {partner}. London demands Cairo yield customs or disarm the coastal batteries.')
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    if not _transfer_to_households(britain, float(rules['upkeep_per_turn'])):
        withdraw(world, 'Britain cannot pay the fleet’s continuing supply costs; the squadron withdraws.')
        return
    resupply(world, 'Britain', 1)
    if not fleet_at(world, 'Britain', 'Alexandria'):
        withdraw(world, 'The British squadron is absent or unsupplied; the Alexandria blockade ends.')
        return
    if stage == 'ultimatum':
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    if stage == 'mediation':
        if turn < int(crisis['mediation_due_turn']):
            return
        if (float(state.get('creditor_confidence', 0.0)) >= 0.55
                and float(state.get('scheduled_remittance', 0)) > 0
                and egypt.government.agent.cash >= float(state['scheduled_remittance']) * 0.5):
            from scenario_debt import pay as pay_debt
            amount = float(state['scheduled_remittance']) * 0.5
            ok, _ = pay_debt(world, amount, kind='ottoman_mediation', forgive_remainder=True)
            if ok:
                state['payment_status'] = 'restructured'
                withdraw(world, f'Ottoman mediation secures a {amount:,.0f}-unit settlement; the fleet withdraws.')
                return
        crisis['stage'] = 'ultimatum'
        _record(world, 'Ottoman mediation fails to secure terms. The British ultimatum resumes.')
        world['scenario_warning_modal'] = {'kind': 'naval_ultimatum'}
        world['playing'] = False
        return
    if stage == 'blockaded' and crisis.get('last_offer_turn') != turn:
        _record(world, 'The blockade of Alexandria continues to interrupt its coastal routes. Cairo may settle or hold out.')
        world['scenario_warning_modal'] = {'kind': 'naval_blockade'}
        world['playing'] = False


def naval_response_options(world: dict, kind: str) -> list[dict]:
    state = world.get('scenario_state', {})
    rules = situation_template()['naval_crisis']
    egypt = _nation(world, 'Egypt')
    cash = float(egypt.government.agent.cash) if egypt else 0.0
    settlement = round(float(state.get('scheduled_remittance', 0.0))
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
             'tooltip': 'Ask the Ottoman government to mediate. Britain waits one turn while paying fleet upkeep. If confidence is at least 55% and Egypt can pay half the claim, the mediated settlement ends the crisis; otherwise the ultimatum returns.',
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
        from scenario_debt import pay as pay_debt
        rules = situation_template()['naval_crisis']
        amount = round(float(state['scheduled_remittance']) * float(rules['settlement_fraction']), 2)
        ok, reason = pay_debt(world, amount, kind='naval_settlement', forgive_remainder=True)
        if not ok:
            return False, reason
        state['payment_status'] = 'restructured'
        state['creditor_levy_per_turn'] = 0.0
        state['creditor_levy_remaining'] = 0.0
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.10)
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + 0.15)
        withdraw(world, f'Cairo pays {amount:,.0f} and negotiates a settlement; the British squadron withdraws.')
    elif response_id == 'naval_accept_control':
        state['creditor_levy_per_turn'] = 5.0
        from scenario_debt import outstanding
        state['creditor_levy_remaining'] = outstanding(world)
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.15)
        state['creditor_confidence'] = min(1.0, state['creditor_confidence'] + 0.05)
        withdraw(world, 'Cairo accepts a customs levy under naval pressure; the squadron withdraws.')
    elif response_id == 'naval_disarm':
        egypt.legitimacy = max(0.0, egypt.legitimacy - 0.08)
        state['fiscal_autonomy'] = max(0.0, state['fiscal_autonomy'] - 0.05)
        crisis['battery_strength'] = 0.0
        withdraw(world, 'Cairo disarms Alexandria’s batteries. The fleet withdraws, but the debt claim survives.')
    elif response_id == 'naval_seek_mediation':
        crisis['stage'] = 'mediation'
        crisis['mediation_due_turn'] = int(world['turn']) + 1
        _record(world, 'Cairo requests Ottoman mediation; the fleet remains supplied off Alexandria pending a reply.')
    elif response_id == 'naval_defend':
        egypt.legitimacy = min(1.0, egypt.legitimacy + 0.03)
        if not fleet_at(world, 'Britain', 'Alexandria'):
            withdraw(world, 'No supplied squadron remains off Alexandria to enforce the ultimatum.')
        elif _force_ratio(world) < float(situation_template()['naval_crisis']['minimum_force_ratio']):
            withdraw(world, 'Alexandria’s defenses deter the squadron; Britain abandons its ultimatum.')
        else:
            alexandria = _alexandria(egypt)
            manager = get_imperialism_manager()
            ok, message = manager.impose_naval_blockade(_nation(world, 'Britain'), egypt,
                                                       alexandria, int(world['turn']), world)
            if not ok:
                withdraw(world, f'Britain cannot enforce the blockade: {message}')
            else:
                crisis['stage'] = 'blockaded'
                crisis['battery_strength'] = max(0.0, float(crisis.get('battery_strength',
                    situation_template()['naval_crisis']['alexandria_battery_strength'])) * 0.25)
                alexandria.unrest_level = min(1.0, float(alexandria.unrest_level) + 0.20)
                egypt.legitimacy = max(0.0, egypt.legitimacy - 0.08)
                _record(world, 'British guns strike Alexandria’s batteries. The port is blockaded; unrest rises there and government legitimacy falls.', 'WAR')
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

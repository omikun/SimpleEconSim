"""One-decision national policy and border contest for the bounded scenario."""

from __future__ import annotations

from army import recruit_unit
from diplomacy import TreatyType, get_diplomacy
from intents import DeclareWarIntent, MoveArmyIntent
from war_logic import WarAim
from labor_frontier_labor import _approve, _protect, _event
from labor_frontier_market import start_machinery_project


NAP = TreatyType.NON_AGGRESSION.value


def initialize_rivalry(world):
    state = world['scenario_state']
    state['rival_plan'] = {'goal': 'hold', 'reason': 'Opening border posture',
                           'announced_turn': None, 'last_action_turn': -1}
    state['border_history'] = []
    state['standstill_until'] = 0
    state['war_declared_turn'] = None
    # The shared diplomacy service survives successive authored-world fixtures.
    diplomacy = get_diplomacy()
    pair = diplomacy._pair_key('Meridian', 'Vesper')
    diplomacy.active_wars.discard(pair)
    diplomacy.war_records.pop(pair, None)
    diplomacy.treaties = [t for t in diplomacy.treaties
                          if {t.nation_a, t.nation_b} != {'Meridian', 'Vesper'}]
    diplomacy.betrayal_memory.pop(('Meridian', 'Vesper'), None)
    diplomacy.betrayal_memory.pop(('Vesper', 'Meridian'), None)
    diplomacy.set_relation('Meridian', 'Vesper', 0.1)


def _nation(world, name):
    return next(n for n in world['nations'] if n.name == name)


def _border(world, name):
    return next((r for r in world['tiles'] if r.scenario_location == 'borderland'
                 and r.owner_nation.name == name), None)


def _border_strength(nation, region):
    if region is None:
        return 0.0
    return sum(u.strength for u in nation.military_units
               if u.region_name == region.name and u.soldiers > 0)


def _runway(nation):
    payroll = sum(u.soldiers * u.wage_per_soldier for u in nation.military_units)
    return nation.government.agent.cash / payroll if payroll > 0 else 99.0


def _can_supply(nation, region):
    return (region is not None and region.owner_nation is nation
            and nation.government.food_inventory >= 4 and _runway(nation) >= 2)


def _other(world, nation):
    return next(n for n in world['nations'] if n is not nation)


def _record(world, turn, nation, action, message):
    world['scenario_state']['border_history'].append(
        {'turn': turn, 'nation': nation.name, 'action': action, 'message': message})
    world['scenario_state']['border_history'] = world['scenario_state']['border_history'][-80:]
    _event(world, turn, 'BORDER', message, nation=nation.name, action=action)


def apply_border_action(world, action_id, nation_name, turn):
    """Execute one concrete decision; caller owns the per-turn budget."""
    nation = _nation(world, nation_name)
    opponent = _other(world, nation)
    home, target = _border(world, nation.name), _border(world, opponent.name)
    diplomacy = get_diplomacy()
    state = world['scenario_state']
    if action_id == 'recruit_border':
        if not _can_supply(nation, home) or _runway(nation) < 4:
            return False, 'Need a held border, four rations, and four payrolls of cash.'
        unit = recruit_unit(nation, home, 4, wage=2.0, t=turn)
        if unit is None:
            return False, 'Four willing residents or the first payroll are unavailable.'
        unit.is_garrison = True
        message = f'{nation.name} enlists four named residents at {home.name}; cash and food upkeep begin next turn.'
    elif action_id == 'declare_border_war':
        if target is None or home is None:
            return False, 'No held border faces a foreign border district.'
        if state['standstill_until'] > turn or diplomacy.has_treaty(nation.name, opponent.name, NAP):
            return False, 'The border standstill is still binding.'
        if diplomacy.are_at_war(nation.name, opponent.name):
            return False, 'War is already declared.'
        if not _can_supply(nation, home):
            return False, 'The border force lacks food or two payrolls of cash.'
        ok, message = DeclareWarIntent(nation.name, opponent.name,
                                       reason='limited border contest',
                                       aim=WarAim('border_tile', target.name)).execute(
                                           world['by_name'], {n.name: n for n in world['nations']}, turn)
        if not ok:
            return False, message
        state['war_declared_turn'] = turn
    elif action_id == 'attack_border':
        if not diplomacy.are_at_war(nation.name, opponent.name):
            return False, 'A declared war is required.'
        if state.get('war_declared_turn') is None or turn <= state['war_declared_turn']:
            return False, 'Hostile entry requires a full response turn after declaration.'
        if not _can_supply(nation, home) or target is None:
            return False, 'A supplied border force and foreign border target are required.'
        unit = next((u for u in nation.military_units if u.region_name == home.name
                     and u.soldiers > 0), None)
        if unit is None:
            return False, 'No deployed border unit can attack.'
        if _border_strength(nation, home) <= 0:
            return False, 'No effective border strength remains.'
        ok, message = MoveArmyIntent(nation.name, unit.unit_id, home.name,
                                     target.name).execute(
                                         world['by_name'], {n.name: n for n in world['nations']}, turn)
        if not ok:
            return False, message
    elif action_id == 'propose_standstill':
        if diplomacy.are_at_war(nation.name, opponent.name):
            return False, 'Offer peace before a standstill.'
        if state['standstill_until'] > turn:
            return False, 'A standstill is already active.'
        if home is None or target is None:
            return False, 'Both countries must hold a border district.'
        my_strength = _border_strength(nation, home)
        their_strength = _border_strength(opponent, target)
        if (their_strength > my_strength * 1.6 and _runway(opponent) > 5
                and opponent.government.food_inventory >= 8):
            return False, f'{opponent.name} rejects: its supplied local force has a clear advantage.'
        ok, message = diplomacy.propose_treaty(nation.name, opponent.name,
                                               NAP, t=turn, world=world)
        if not ok:
            return False, message
        state['standstill_until'] = turn + 4
        message = f'{nation.name} and {opponent.name} agree to a four-turn border standstill.'
    elif action_id == 'offer_peace':
        if not diplomacy.are_at_war(nation.name, opponent.name):
            return False, 'There is no war to end.'
        result = diplomacy.sign_peace(nation.name, opponent.name, t=turn,
                                      _trace_world=world)
        if not result['success']:
            return False, result['message']
        message = result['message']
        state['war_declared_turn'] = None
    else:
        return False, f'Unknown border action: {action_id}'
    _record(world, turn, nation, action_id, message)
    return True, message


def _choose_rival(world, turn):
    state = world['scenario_state']
    rival = _nation(world, 'Vesper')
    player = _nation(world, 'Meridian')
    home, target = _border(world, rival.name), _border(world, player.name)
    if home is None or target is None:
        return 'hold', 'The remaining border is not a reachable foreign district.'
    own = state.get('market_summary', {}).get(rival.name, {}).get('units_sold', 0)
    foreign = state.get('market_summary', {}).get(player.name, {}).get('units_sold', 0)
    strength = _border_strength(rival, home)
    threat = _border_strength(player, target)
    runoff = _runway(rival)
    diplomacy = get_diplomacy()
    if diplomacy.are_at_war(rival.name, player.name):
        if (strength > threat * 1.35 and _can_supply(rival, home)
                and turn > (state.get('war_declared_turn') or turn)):
            return 'attack_border', 'Local superiority, food, and two payrolls support an expedition.'
        if not _can_supply(rival, home):
            return 'offer_peace', 'Supply or payroll cannot sustain the border campaign.'
        return 'hold', 'Border force cannot yet overcome the defended district.'
    if state['standstill_until'] > turn:
        return 'hold', 'The active standstill prevents hostile entry.'
    record = state['restrictions'].get(rival.name)
    if record and record['status'] == 'proposed' and own < foreign and home.gov.agent.cash >= 6:
        return 'approve_petition', 'Lost orders make the estate press for cheaper cotton labor.'
    if record and record['status'] in ('active', 'suspended') and own >= foreign and home.gov.agent.cash < 6:
        return 'protect_access', 'The patrol costs more than the observed market benefit.'
    if threat > strength * 1.1 and runoff >= 4 and rival.government.food_inventory >= 8:
        return 'recruit_border', 'A funded local garrison can deter the stronger neighbor.'
    if own < foreign and runoff >= 5:
        return 'invest', 'Lost paid orders justify a funded productive response.'
    if (strength > threat * 1.5 and runoff >= 5
            and rival.government.food_inventory >= 10):
        plan = state['rival_plan']
        if plan['goal'] != 'mobilize':
            return 'mobilize', 'A reachable district offers cotton, but an expedition needs public warning.'
        if turn > plan['announced_turn']:
            return 'declare_border_war', 'Local superiority and funded supply support a limited war.'
    if own > 0 and foreign > 0 and runoff < 5 and not diplomacy.has_treaty(rival.name, player.name, NAP):
        return 'propose_standstill', 'Trade receipts are safer than an unaffordable expedition.'
    return 'hold', 'Industrial, fiscal, and border evidence favors restraint.'


def advance_rival(world, turn):
    """One strategic government decision after market settlement each turn."""
    state = world['scenario_state']
    if state.get('ending'):
        return
    diplomacy = get_diplomacy()
    if state['standstill_until'] and turn >= state['standstill_until']:
        diplomacy.cancel_treaty('Meridian', 'Vesper', NAP, t=turn,
                                reason='Four-turn review period ended',
                                _trace_world=world)
        state['standstill_until'] = 0
    action, reason = _choose_rival(world, turn)
    plan = state['rival_plan']
    plan.update({'goal': action, 'reason': reason, 'last_action_turn': turn})
    if action == 'mobilize':
        plan['announced_turn'] = turn
        _record(world, turn, _nation(world, 'Vesper'), 'mobilize',
                f'Vesper publicly mobilizes at the border: {reason}')
        return
    if action in ('hold', 'invest'):
        if action == 'invest':
            ok, message = start_machinery_project(world, 'Vesper', turn,
                                                   public_contribution=15)
            if ok:
                _record(world, turn, _nation(world, 'Vesper'), action, message)
        return
    if action in ('approve_petition', 'protect_access'):
        handler = _approve if action == 'approve_petition' else _protect
        ok, message = handler(world, 'Vesper', turn)
    else:
        ok, message = apply_border_action(world, action, 'Vesper', turn)
    if ok and action in ('approve_petition', 'protect_access'):
        _record(world, turn, _nation(world, 'Vesper'), action, message)
    if not ok:
        plan['goal'] = 'hold'
        plan['reason'] = message

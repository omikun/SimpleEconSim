"""Shared, read-only player projection for the labor frontier scenario."""

from __future__ import annotations

from goods import Goods
from diplomacy import get_diplomacy
from labor_frontier_labor import _districts, _firm, RELIEF_UNITS
from labor_frontier_rivalry import _border_strength, _runway


def _ordinary(person):
    return (person.alive and not person.is_corporation and not person.is_government
            and not person.is_trader)


def _action(action_id, label, detail, enabled, reason='', group=''):
    return {'id': action_id, 'label': label, 'detail': detail,
            'enabled': bool(enabled), 'reason': '' if enabled else reason,
            'group': group}


def project(world):
    state = world['scenario_state']
    player = next(n for n in world['nations'] if n.name == world['player_nation_name'])
    rival = next(n for n in world['nations'] if n is not player)
    capital, border = _districts(world, player.name)
    rival_capital, rival_border = _districts(world, rival.name)
    people = [a for region in player.tiles for a in region.agents if _ordinary(a)]
    hungry = sum(a.hungry_steps > 0 for a in people)
    paid = sum(bool(a.employer is not None or getattr(a, 'military_unit_id', None))
               for a in people)
    initial = set(state.get('starting_person_ids', ()))
    surviving_initial = sum(a.id in initial for region in world['tiles'] for a in region.agents
                            if a.alive and _ordinary(a))
    rights = (sum(right.usable_share > 0 for rows in border.access_rights.values()
                  for right in rows if right.resource == 'commons_food') if border else 0)
    own_market = state.get('market_summary', {}).get(player.name, {})
    rival_market = state.get('market_summary', {}).get(rival.name, {})
    mill = _firm(capital, Goods.cloth)
    estate = _firm(border, Goods.cotton)
    treasury = player.government.agent.cash
    food = int(player.government.food_inventory)
    force = _border_strength(player, border)
    other_force = _border_strength(rival, rival_border)
    upkeep = sum(u.soldiers * u.wage_per_soldier for u in player.military_units)
    rations = sum(u.soldiers * u.food_per_soldier for u in player.military_units)
    runway = _runway(player)
    food_runway = food / rations if rations else 99.0
    turn = int(world.get('turn', 0))
    spent = state.get('major_action_turn') == turn
    ending = bool(state.get('ending'))
    record = state.get('restrictions', {}).get(player.name)
    record_status = record['status'] if record else 'none'
    war = get_diplomacy().are_at_war(player.name, rival.name)
    standstill = max(0, int(state.get('standstill_until', 0)) - turn)
    status = ('War declared' if war else
              f'Standstill: {standstill} turns' if standstill else 'No border pact')
    cards = [
        {'title': 'Livelihoods',
         'value': f'{len(people) - hungry}/{len(people)} fed · {rights} usable commons rights',
         'cause': f'{paid} residents have paid work or service; {surviving_initial}/{len(initial)} starting residents survive across both states.',
         'tone': 'urgent' if hungry > len(people) * .2 else 'warning' if rights == 0 else 'good'},
        {'title': 'Economic position',
         'value': f'Cloth sold {own_market.get("units_sold", 0)} vs {rival_market.get("units_sold", 0)}',
         'cause': f'Mill cash {mill.cash:.0f}; public cloth tax {own_market.get("public_tax", 0):.1f}; treasury {treasury:.0f}; payroll runway {runway:.1f} turns.' if mill else 'The textile mill is unavailable.',
         'tone': 'warning' if own_market.get('units_sold', 0) < rival_market.get('units_sold', 0) else 'good'},
        {'title': 'Border power',
         'value': f'{force:.1f} local strength vs {other_force:.1f} · {status}',
         'cause': f'{food} food in reserve ({food_runway:.1f} ration turns). Rival plan: {state.get("rival_plan", {}).get("goal", "hold")}; {state.get("rival_plan", {}).get("reason", "")}',
         'tone': 'urgent' if war and force < other_force else 'warning' if force < other_force else 'good'},
    ]
    actions = []
    petition = record_status == 'proposed' and turn <= record['deadline_turn'] if record else False
    actions.append(_action('approve_petition', 'Approve commons closure',
                           'Owner paid petition fee; public patrol costs 3 per turn after one turn.',
                           petition, 'No live petition in its response window.', 'Livelihoods'))
    actions.append(_action('protect_access', 'Protect commons access',
                           'Reject petition or repeal the targeted closure; patrol ends.',
                           record_status in ('proposed', 'approved', 'active', 'suspended'),
                           'No pending or active closure.', 'Livelihoods'))
    can_terms = bool(mill and mill.owner and mill.owner.cash >= 20 and treasury >= 10
                     and mill.employees)
    actions.append(_action('fair_terms', 'Back better terms',
                           'Owner contributes 20; treasury 10; workers must accept.',
                           can_terms, 'Requires a mill with workers, owner cash 20, and treasury 10.', 'Economic position'))
    can_machinery = bool(mill and mill.owner and mill.owner.cash >= 30 and treasury >= 15
                         and not any(p['nation'] == player.name and p['status'] == 'active'
                                     for p in state.get('machinery_projects', ())))
    actions.append(_action('cofund_machinery', 'Cofund machinery',
                           'Owner 30 + treasury 15; two iron and one coal are purchased; two turns.',
                           can_machinery, 'Requires owner cash 30, treasury 15, and no active project; physical inputs are checked on order.', 'Economic position'))
    actions.append(_action('release_relief', 'Release six food',
                           'Three border residents receive two food each; troops share this reserve.',
                           bool(border and food >= RELIEF_UNITS),
                           'Need a held border and six food in the public reserve.', 'Livelihoods'))
    actions.append(_action('recruit_border', 'Recruit four residents',
                           'Offer wage 2 each; first payroll 8; four rations per turn.',
                           bool(border and treasury >= max(8, 4 * upkeep) and food >= 4),
                           'Need a held border, four rations, and four payrolls of cash; willing residents are checked on order.', 'Border power'))
    can_war = bool(border and rival_border and not war and not standstill and runway >= 2 and food >= 4)
    actions.append(_action('declare_border_war', 'Declare limited war',
                           'Announced now; hostile entry permitted after a response turn.',
                           can_war, 'Need a supplied held border, two payrolls, and no active standstill.', 'Border power'))
    can_attack = bool(war and border and rival_border and force > 0 and food >= 4
                      and runway >= 2 and state.get('war_declared_turn') is not None
                      and turn > state['war_declared_turn'])
    actions.append(_action('attack_border', 'Attack rival border',
                           'All local units fight; casualties and control follow the battle result.',
                           can_attack, 'Need declared war, a full response turn, local forces, food, and payroll.', 'Border power'))
    actions.append(_action('propose_standstill', 'Offer four-turn standstill',
                           'Neighbor accepts only if the defended alternative is less attractive.',
                           bool(border and rival_border and not war and not standstill),
                           'Both borders must be held, at peace, and outside an active standstill.', 'Border power'))
    actions.append(_action('offer_peace', 'Offer peace',
                           'Stop the war; border control remains where the battles left it.',
                           war, 'There is no active war.', 'Border power'))
    if spent or ending:
        for action in actions:
            action['enabled'] = False
            action['reason'] = 'Scenario ended.' if ending else 'One major decision already taken this turn.'
    districts = [{'name': region.name, 'owner': region.owner_nation.name,
                  'people': sum(_ordinary(a) for a in region.agents),
                  'units': sum(u.soldiers for u in getattr(region, 'military_units', [])),
                  'commons_rights': sum(right.usable_share > 0 for rows in getattr(region, 'access_rights', {}).values()
                                        for right in rows if right.resource == 'commons_food'),
                  'role': region.scenario_location}
                 for region in world['tiles']]
    debrief = None
    if ending:
        debrief = {'title': 'Labor and frontier settlement',
                   'summary': f'Meridian holds {len(player.tiles)} districts and sold {own_market.get("units_sold", 0)} cloth in the last turn; Vesper holds {len(rival.tiles)} and sold {rival_market.get("units_sold", 0)}.',
                   'people': f'{len(people) - hungry}/{len(people)} Meridian residents fed; {surviving_initial}/{len(initial)} starting residents survive across both states.',
                   'capacity': f'Treasury {treasury:.0f}, food {food}, border strength {force:.1f}, payroll runway {runway:.1f} turns.',
                   'commitments': f'{len([p for p in state.get("machinery_projects", ()) if p["status"] == "active"])} machinery projects active; border status: {status}.'}
    return {'scenario_name': 'Labor, Territory, and Rivalry',
            'mandate': 'Compete for cloth markets and territory while protecting or exploiting citizens.',
            'turn': turn, 'horizon_turns': 20, 'countdown_turns': max(0, 20 - turn),
            'pressures': cards, 'actions': actions, 'timeline': state.get('timeline', [])[-8:],
            'districts': districts, 'debrief': debrief, 'ending': ending,
            'major_action_spent': spent, 'sovereign_cash': round(treasury, 3),
            'resident_count': len(people), 'active': True}

"""Turn-to-turn provenance for the Egypt guided status bar."""

from __future__ import annotations


STAT_KEYS = ('cash', 'maize', 'hunger', 'legitimacy', 'unrest', 'creditors', 'autonomy')

ACTION_LABELS = {
    'release_maize': 'Released public maize',
    'prioritize_domestic_grain': 'Retained grain for domestic supply',
    'reduce_fellahin_tax': 'Reduced local taxes',
    'raise_local_taxes': 'Raised local taxes',
    'pay_remittance': 'Paid debt service',
    'concede_revenue': 'Conceded revenue oversight',
    'defer_remittance': 'Deferred debt service',
    'default_remittance': 'Defaulted on debt service',
    'pay_army_arrears': 'Paid officer arrears',
    'promote_egyptian_officers': 'Promoted Egyptian officers',
    'invite_representative_cabinet': 'Invited representative cabinet',
    'dismiss_foreign_controllers': 'Dismissed foreign controllers',
    'reinforce_alexandria': 'Prepared Alexandria batteries',
    'close_canal': 'Closed foreign canal transit',
    'defend_alexandria': 'Defended Alexandria against landing',
    'defend_canal': 'Defended the Ismailia canal line',
    'evacuate_port': 'Evacuated Alexandria',
    'negotiate_landing': 'Negotiated before landing',
    'organize_boycott': 'Organized customs boycott',
    'call_general_strike': 'Called general strike',
    'coordinate_insurgency': 'Coordinated resistance',
    'collaborate_with_occupation': 'Collaborated with occupation',
    'negotiate_withdrawal': 'Negotiated withdrawal',
    'defend_cairo': 'Defended Cairo',
    'evacuate_cairo': 'Evacuated Cairo',
    'negotiate_capital': 'Negotiated at Cairo',
}

PHASE_LABELS = {
    'projects': 'Strategic projects and construction',
    'local': 'Local economy and household food access',
    'trade': 'Trade and migration',
    'regime': 'Faction support and regime politics',
    'military': 'Military upkeep and supplies',
    'resistance': 'Popular resistance and imperial policy',
    'markets': 'Financial markets and other turn effects',
    'bonds': 'Sovereign bond payments',
    'catalyst': 'National crisis event',
    'scenario': 'Scenario deadline and outcome rules',
    'levy': 'Creditor collection levy',
    'deadline': 'Debt-service deadline',
    'protest_pressure': 'Egyptian district protest pressure',
    'creditor_reaction': 'Caisse reaction to the last decision',
    'politics': 'Egyptian officers and civilian coalition',
    'naval_crisis': 'Naval pressure and expedition upkeep',
    'campaign': 'Fleet movement and land campaign',
    'occupation': 'Occupied institutions and resistance',
}


def snapshot(world: dict) -> dict | None:
    """Capture exactly the quantities displayed in the guided national bar."""
    nation = next((n for n in world.get('nations', [])
                   if n.name == world.get('player_nation_name')), None)
    if nation is None:
        return None
    tiles = list(getattr(nation, 'tiles', []))
    people = [agent for tile in tiles for agent in getattr(tile, 'agents', [])
              if getattr(agent, 'alive', True)
              and not getattr(agent, 'is_government', False)
              and not getattr(agent, 'is_corporation', False)
              and not getattr(agent, 'is_trader', False)]
    hungry = sum(getattr(agent, 'hungry_steps', 0) > 0 for agent in people)
    state = world.get('scenario_state', {})
    return {
        'cash': float(nation.government.agent.cash),
        'maize': int(getattr(nation.government, 'food_inventory', 0)),
        'hunger': hungry / max(1, len(people)),
        'legitimacy': float(getattr(nation, 'legitimacy', 0.5)),
        'unrest': sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles) / max(1, len(tiles)),
        'creditors': float(state.get('creditor_confidence', 0.6)),
        'autonomy': float(state.get('fiscal_autonomy', 1.0)),
        'hungry_count': hungry,
        'household_count': len(people),
        'unrest_by_tile': {tile.name: float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles},
        'tile_names': {tile.name: (getattr(tile, 'scenario_location', None)
                                   or getattr(tile, 'display_name', tile.name)) for tile in tiles},
        'hungry_by_tile': {
            tile.name: sum(getattr(agent, 'hungry_steps', 0) > 0 for agent in getattr(tile, 'agents', [])
                           if getattr(agent, 'alive', True)
                           and not getattr(agent, 'is_government', False)
                           and not getattr(agent, 'is_corporation', False)
                           and not getattr(agent, 'is_trader', False))
            for tile in tiles
        },
    }


def initialize(world: dict) -> None:
    current = snapshot(world)
    if current is not None:
        world['scenario_status_history'] = {
            'baseline': current,
            'comparison': current,
            'comparison_turn': int(world.get('turn', 0)),
            'factors': [],
            'pending': [],
        }


def record_change(world: dict, source: str, before: dict | None, after: dict | None) -> None:
    """Store the measured change from one simulation phase or player decision."""
    if before is None or after is None:
        return
    history = world.get('scenario_status_history')
    if history is None:
        return
    changes = {key: after[key] - before[key] for key in STAT_KEYS
               if abs(after[key] - before[key]) > 1e-9}
    if not changes:
        return
    details = {}
    for stat, field, unit in (('hunger', 'hungry_by_tile', 'hungry households'),
                              ('unrest', 'unrest_by_tile', 'unrest')):
        if stat not in changes:
            continue
        tile_changes = [(name, value - before[field].get(name, 0))
                        for name, value in after[field].items()]
        tile_changes = sorted((item for item in tile_changes if abs(item[1]) > 1e-9),
                              key=lambda item: abs(item[1]), reverse=True)
        if tile_changes:
            details[stat] = ', '.join(f'{after["tile_names"].get(name, name)} {change:+.0f}' if stat == 'hunger'
                                      else f'{after["tile_names"].get(name, name)} {change:+.2f}'
                                      for name, change in tile_changes[:3]) + f' {unit}'
    if source == 'local' and 'cash' in changes:
        nation = next((n for n in world.get('nations', [])
                       if n.name == world.get('player_nation_name')), None)
        tax = sum(float(getattr(tile, 'tax_distribution_log', [{}])[-1].get('national', 0.0))
                  for tile in getattr(nation, 'tiles', [])
                  if getattr(tile, 'tax_distribution_log', None))
        if tax:
            details['cash'] = f'National tax receipts +{tax:,.2f}; other local flows {changes["cash"] - tax:+,.2f}.'
    if source == 'regime' and 'legitimacy' in changes:
        nation = next((n for n in world.get('nations', [])
                       if n.name == world.get('player_nation_name')), None)
        if nation is not None:
            from regime import _avg_faction_support
            details['legitimacy'] = f'Current mean faction support: {_avg_faction_support(nation):.0%}.'
    history['pending'].append({'source': source, 'changes': changes, 'details': details})


def finish_turn(world: dict, turn: int) -> None:
    """Keep the old turn's starting state as the comparison until the next turn."""
    current = snapshot(world)
    history = world.get('scenario_status_history')
    if current is None or history is None:
        return
    history['comparison'] = history['baseline']
    history['comparison_turn'] = int(turn) - 1
    history['factors'] = history['pending']
    history['baseline'] = current
    history['pending'] = []


def display_change(world: dict, stat: str, current: dict) -> tuple[float | None, int | None, list[dict]]:
    history = world.get('scenario_status_history')
    if not history:
        return None, None, []
    previous = history.get('comparison')
    if not previous or stat not in previous:
        return None, None, []
    factors = [factor for factor in history.get('factors', []) + history.get('pending', [])
               if stat in factor.get('changes', {})]
    return current[stat] - previous[stat], history.get('comparison_turn'), factors

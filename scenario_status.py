"""Turn-to-turn provenance for the Egypt guided status bar."""

from __future__ import annotations

from goods import Goods


STAT_KEYS = ('cash', 'tax', 'debt', 'maize', 'hunger', 'legitimacy', 'unrest', 'creditors', 'autonomy')

ACTION_LABELS = {
    'release_maize': 'Released public maize',
    'repair_delta_channels': 'Repaired Delta Nile channels',
    'repair_upper_channels': 'Repaired Upper Egypt channels',
    'build_revenue_office': 'Staffed Alexandria revenue office',
    'prepare_canal_line': 'Funded Tel el Kebir defenses',
    'repair_canal_line': 'Repaired Tel el Kebir defenses',
    'publish_revenue_accounts': 'Published Egyptian revenue accounts',
    'refuse_revenue_inspection': 'Refused Caisse revenue inspection',
    'prioritize_domestic_grain': 'Retained grain for domestic supply',
    'enact_grain_entitlement': 'Levied private surplus for relief',
    'end_grain_entitlement': 'Ended the private grain entitlement',
    'recall_district_reserves': 'Called district cash reserves to Cairo',
    'reduce_fellahin_tax': 'Reduced local taxes',
    'raise_local_taxes': 'Raised local taxes',
    'intensify_requisitions': 'Intensified emergency requisitions',
    'district_relief': 'Fed an underfed district',
    'district_tax_relief': 'Cut a district tax rate',
    'district_negotiate': 'Paid a local settlement',
    'district_repress': 'Dispersed a district protest',
    'buy_private_grain': 'Bought private maize for relief stores',
    'requisition_private_grain': 'Requisitioned private maize',
    'open_private_grain_market': 'Allowed private maize sales',
    'district_arrears_relief': 'Forgave local tax arrears',
    'district_support_mutual_aid': 'Supported mutual aid',
    'district_bargain_workers': 'Bargained with local workers',
    'district_break_strike': 'Broke a local strike',
    'extend_collection_term': 'Extended Caisse inspection for a lower levy',
    'comply_oversight': 'Funded Caisse inspection',
    'seek_narrower_oversight': 'Proposed narrower Caisse inspection',
    'revoke_oversight': 'Revoked Caisse oversight',
    'request_french_mediation': 'Requested French mediation',
    'offer_joint_guarantee': 'Offered a joint creditor guarantee',
    'seek_french_opposition': 'Sought French opposition to unilateral force',
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
    'political_economy': 'Private grain, taxes, tenure, and collective action',
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
    from nutrition import deficit_fraction, fat_kg
    hungry = sum(deficit_fraction(agent) > 0 for agent in people)
    calorie_gap = sum(deficit_fraction(agent) for agent in people) / max(1, len(people))
    mean_fat = sum(fat_kg(agent) for agent in people) / max(1, len(people))
    total_deficit = sum(float(getattr(agent, 'calorie_deficit_kcal', 0.0)) for agent in people)
    total_surplus = sum(float(getattr(agent, 'calorie_surplus_kcal', 0.0)) for agent in people)
    state = world.get('scenario_state', {})
    from scenario_debt import outstanding
    tax_by_tile = {
        tile.name: dict(tile.tax_distribution_log[-1]) if getattr(tile, 'tax_distribution_log', None)
        else {'total': 0.0, 'national': 0.0, 'provincial': 0.0, 'municipal': 0.0}
        for tile in tiles
    }
    tax_tiers = {key: sum(float(row.get(key, 0.0)) for row in tax_by_tile.values())
                 for key in ('total', 'national', 'provincial', 'municipal')}
    private_cash = sorted(max(0.0, float(agent.cash)) for agent in people)
    total_private_cash = sum(private_cash)
    top_count = max(1, (len(private_cash) + 4) // 5)
    private_food = sum(agent.inv_get(Goods.food, 0) for tile in tiles
                       for agent in getattr(tile, 'agents', [])
                       if getattr(agent, 'alive', True)
                       and not getattr(agent, 'is_government', False))
    return {
        'cash': float(nation.government.agent.cash),
        'tax': tax_tiers['total'],
        'debt': outstanding(world),
        'maize': int(getattr(nation.government, 'food_inventory', 0)),
        'hunger': calorie_gap,
        'calorie_gap': calorie_gap,
        'mean_fat_kg': mean_fat,
        'total_deficit_kcal': total_deficit,
        'total_surplus_kcal': total_surplus,
        'legitimacy': float(getattr(nation, 'legitimacy', 0.5)),
        'unrest': sum(float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles) / max(1, len(tiles)),
        'creditors': float(state.get('creditor_confidence', 0.6)),
        'autonomy': float(state.get('fiscal_autonomy', 1.0)),
        'hungry_count': hungry,
        'household_count': len(people),
        'private_food': private_food,
        'top_fifth_cash_share': sum(private_cash[-top_count:]) / total_private_cash if total_private_cash else 0.0,
        'bottom_quarter_cash_share': sum(private_cash[:len(private_cash) // 4]) / total_private_cash if total_private_cash else 0.0,
        'unrest_by_tile': {tile.name: float(getattr(tile, 'unrest_level', 0.0)) for tile in tiles},
        'tile_names': {tile.name: (getattr(tile, 'scenario_location', None)
                                   or getattr(tile, 'display_name', tile.name)) for tile in tiles},
        'tax_by_tile': tax_by_tile,
        'tax_tiers': tax_tiers,
        'hungry_by_tile': {
            tile.name: sum(deficit_fraction(agent) > 0 for agent in getattr(tile, 'agents', [])
                           if getattr(agent, 'alive', True)
                           and not getattr(agent, 'is_government', False)
                           and not getattr(agent, 'is_corporation', False)
                           and not getattr(agent, 'is_trader', False))
            for tile in tiles
        },
        'calorie_gap_by_tile': {
            tile.name: (sum(deficit_fraction(agent) for agent in getattr(tile, 'agents', [])
                            if getattr(agent, 'alive', True)
                            and not getattr(agent, 'is_government', False)
                            and not getattr(agent, 'is_corporation', False)
                            and not getattr(agent, 'is_trader', False))
                        / max(1, sum(1 for agent in getattr(tile, 'agents', [])
                                     if getattr(agent, 'alive', True)
                                     and not getattr(agent, 'is_government', False)
                                     and not getattr(agent, 'is_corporation', False)
                                     and not getattr(agent, 'is_trader', False))))
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
            'social_costs': {
                'household_hunger_turns': current['hungry_count'],
                'peak_hungry': current['hungry_count'],
                'peak_hunger_turn': int(world.get('turn', 0)),
                'private_food_at_peak': current['private_food'],
                'tax_collected': 0.0,
                'total_deficit_kcal': 0.0,
                'total_surplus_kcal': 0.0,
                'opening_top_fifth_cash_share': current['top_fifth_cash_share'],
                'opening_bottom_quarter_cash_share': current['bottom_quarter_cash_share'],
                'last_recorded_turn': int(world.get('turn', 0)),
            },
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
    for stat, field, unit in (('hunger', 'calorie_gap_by_tile', 'mean calorie gap'),
                              ('unrest', 'unrest_by_tile', 'unrest')):
        if stat not in changes:
            continue
        tile_changes = [(name, value - before[field].get(name, 0))
                        for name, value in after[field].items()]
        tile_changes = sorted((item for item in tile_changes if abs(item[1]) > 1e-9),
                              key=lambda item: abs(item[1]), reverse=True)
        if tile_changes:
            details[stat] = ', '.join(f'{after["tile_names"].get(name, name)} {change * 100:+.1f}pp' if stat == 'hunger'
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


def record_social_costs(world: dict, turn: int, current: dict | None = None) -> None:
    """Count each completed campaign turn once, including an early ending turn."""
    current = current or snapshot(world)
    history = world.get('scenario_status_history')
    if current is None or history is None:
        return
    social = history.setdefault('social_costs', {})
    if turn <= social.get('last_recorded_turn', -1):
        return
    social['household_hunger_turns'] = social.get('household_hunger_turns', 0) + current['hungry_count']
    social['tax_collected'] = social.get('tax_collected', 0.0) + current['tax']
    social['total_deficit_kcal'] = social.get('total_deficit_kcal', 0.0) + current['total_deficit_kcal']
    social['total_surplus_kcal'] = social.get('total_surplus_kcal', 0.0) + current['total_surplus_kcal']
    if current['hungry_count'] > social.get('peak_hungry', 0):
        social['peak_hungry'] = current['hungry_count']
        social['peak_hunger_turn'] = turn
        social['private_food_at_peak'] = current['private_food']
    social['last_recorded_turn'] = turn


def finish_turn(world: dict, turn: int) -> None:
    """Keep the old turn's starting state as the comparison until the next turn."""
    current = snapshot(world)
    history = world.get('scenario_status_history')
    if current is None or history is None:
        return
    record_social_costs(world, turn, current)
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

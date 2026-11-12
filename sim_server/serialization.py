"""JSON-safe tile and plot serialization for web and desktop clients."""

from typing import Any, Dict, Optional

from goods import Goods
from client.desktop.map.map_renderer import get_nation_color
from collective_action import organization_summary, recent_collective_events
from collective_politics import political_summary


def serialize_plot(plot) -> Dict[str, Any]:
    """Serialize a LandPlot into a JSON-compatible dictionary."""
    return {
        'plot_id': plot.plot_id,
        'name': getattr(plot, 'name', '') or plot.plot_id,
        'display_name': getattr(plot, 'display_name', plot.plot_id),
        'tile_name': plot.tile_name,
        'lord_id': plot.lord_id,
        'controlled_by_id': getattr(plot, 'controlled_by_id', plot.lord_id),
        'fraction': float(plot.fraction),
        'tenure': plot.tenure.value if hasattr(plot.tenure, 'value') else str(plot.tenure),
        'rent_rate': float(plot.rent_rate),
        'production_type': getattr(plot, 'production_type', 'arable'),
        'pasture_since': getattr(plot, 'pasture_since', -1),
        'tenant_ids': list(getattr(plot, 'tenant_ids', [])),
        'tenant_count': len(getattr(plot, 'tenant_ids', [])),
        'tribute_rate': float(getattr(plot, 'tribute_rate', 0.0)),
        'customary_rights_retained': getattr(plot.tenure, 'value', str(plot.tenure)) in ('feudal', 'leasehold', 'commons'),
    }

def serialize_tile(tile, layout: Optional[Dict[str, Any]] = None, turn: int = 0,
                   summary: bool = False) -> Dict[str, Any]:
    has_centroid = getattr(tile, 'centroid', None) is not None
    centroid = [round(float(v), 2) for v in tile.centroid] if has_centroid else None
    has_polygon = getattr(tile, 'polygon', None) is not None and len(tile.polygon) > 0
    polygon = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in tile.polygon] if has_polygon else None
    neighbors = list(tile.neighbors.keys()) if hasattr(tile, 'neighbors') and isinstance(tile.neighbors, dict) else []

    t_col = getattr(tile, 'terrain_color', getattr(tile, 'color', None))
    if t_col and isinstance(t_col, (list, tuple)) and len(t_col) >= 3:
        tile_color = '#%02x%02x%02x' % tuple(int(c) for c in t_col[:3])
    elif isinstance(t_col, str):
        tile_color = t_col
    else:
        tile_color = None

    if summary:
        if polygon is not None:
            q, r = 0, 0
        elif layout and tile.name in layout:
            q, r = layout[tile.name]
        else:
            q, r = getattr(tile, 'q', 0), getattr(tile, 'r', 0)
        tenure = getattr(tile, 'tenure', None)
        owner = getattr(tile, 'owner_nation', None)
        nation_rgb = get_nation_color(owner.name) if owner else None
        return {
            'name': tile.name,
            'display_name': getattr(tile, 'display_name', getattr(tile, 'city_name', tile.name)),
            'q': q, 'r': r,
            'centroid': centroid,
            'polygon': polygon,
            'neighbors': neighbors,
            'nation': owner.name if owner else None,
            'nation_color': '#%02x%02x%02x' % nation_rgb if nation_rgb else None,
            'color': tile_color,
            'elevation': float(getattr(tile, 'elevation', 0.0)),
            'elevation_meters': float(getattr(tile, 'elevation_meters', 0.0)),
            'biome': getattr(tile, 'biome', 'plains'),
            'is_ocean': bool(getattr(tile, 'is_ocean', False)),
            'population': tile.total_population[-1] if getattr(tile, 'total_population', None) else len(getattr(tile, 'agents', [])),
            'active_collective_strikes': sum(
                bool(org.active_strike_id)
                for org in getattr(tile, 'collective_organizations', {}).values()),
            'gdp': round(float(tile.gdp_log[-1]), 1) if getattr(tile, 'gdp_log', None) else 0.0,
            'protest_energy': round(float(tile.protest_energy_log[-1]), 2) if getattr(tile, 'protest_energy_log', None) else 0.0,
            'buildings_count': len(getattr(tile, 'buildings', [])),
            'garrison': int(getattr(tile, 'garrison', 0)),
            'enclosed_fraction': float(getattr(tenure, 'enclosed_fraction', 0.0)) if tenure else 0.0,
            'exploitation_rate': float(tile.rate_of_exploitation_log[-1]) if getattr(tile, 'rate_of_exploitation_log', None) else 0.0,
            'pollution_air': float(getattr(tile, 'pollution_air', 0.0)),
        }

    tenure = getattr(tile, 'tenure', None)
    plots_data = [serialize_plot(p) for p in getattr(tenure, 'plots', [])] if tenure else []

    from workhouse import has_workhouse, get_workhouse_census, get_workhouse_inmates
    wh_active = has_workhouse(tile)
    wh_inmates = [a.id for a in get_workhouse_inmates(tile)]
    wh_census = get_workhouse_census(tile) if wh_active else []

    survey_debts = [
        {
            'agent_id': d.get('tenant_id', d.get('agent_id')),
            'plot_id': d.get('plot_id'),
            'fee': float(d.get('fee', 15.0)),
            'deadline': int(d.get('deadline', 0)),
        }
        for d in getattr(tile, 'enclosure_survey_debts', [])
    ]

    shift_h = float(tile.avg_shift_hours_log[-1]) if getattr(tile, 'avg_shift_hours_log', None) else 8.0
    max_workday = float(getattr(tile, 'max_workday_hours', 12.0))
    sv = float(tile.surplus_value_log[-1]) if getattr(tile, 'surplus_value_log', None) else 0.0
    roe = float(tile.rate_of_exploitation_log[-1]) if getattr(tile, 'rate_of_exploitation_log', None) else 0.0

    grid_r = getattr(tile, 'grid_r', getattr(tile, 'row', 0))
    grid_c = getattr(tile, 'grid_c', getattr(tile, 'col', 0))

    if layout and tile.name in layout:
        q, r = layout[tile.name]
    elif tile.name.startswith('r') and 'c' in tile.name:
        try:
            parts = tile.name[1:].split('c')
            r_idx, c_idx = int(parts[0]), int(parts[1])
            from hexmap import offset_to_axial
            q, r = offset_to_axial(c_idx, r_idx)
        except Exception:
            q, r = getattr(tile, 'q', 0), getattr(tile, 'r', 0)
    elif grid_r is not None and grid_c is not None:
        from hexmap import offset_to_axial
        q, r = offset_to_axial(grid_c, grid_r)
    else:
        q = getattr(tile, 'q', 0)
        r = getattr(tile, 'r', 0)

    # Market prices
    market_prices = {}
    market_activity = {}
    for g, rec in getattr(tile, 'recipes', {}).items():
        g_name = g.name if hasattr(g, 'name') else str(g)
        if isinstance(rec, dict) and 'price' in rec:
            market_prices[g_name] = round(float(rec['price']), 2)
            funded = getattr(tile, 'demand_log', {}).get(g, [])
            offered = getattr(tile, 'supply_log', {}).get(g, [])
            traded = getattr(tile, 'sold_log', {}).get(g, [])
            matching_trades = [e for e in getattr(tile, 'market_trade_events', [])
                               if e.get('turn') == turn and e.get('good') == g_name]
            buyers = {}
            sellers = {}
            for event in matching_trades:
                buyers[event['buyer_id']] = buyers.get(event['buyer_id'], 0) + event['quantity']
                sellers[event['seller_id']] = sellers.get(event['seller_id'], 0) + event['quantity']
            physical_need = None
            if getattr(g, 'name', '') == 'food':
                from nutrition import appetite_units
                physical_need = sum(max(0, appetite_units(a) - a.inv_get(g, 0))
                                    for a in getattr(tile, 'agents', []) if getattr(a, 'alive', True)
                                    and not getattr(a, 'is_corporation', False)
                                    and not getattr(a, 'is_trader', False))
            market_activity[g_name] = {
                'funded_demand': int(funded[-1]) if funded else 0,
                'offered_supply': int(offered[-1]) if offered else 0,
                'quantity_traded': int(traded[-1]) if traded else 0,
                'physical_need': int(physical_need) if physical_need is not None else None,
                'top_buyers': [{'agent_id': ident, 'quantity': qty}
                               for ident, qty in sorted(buyers.items(), key=lambda pair: (-pair[1], pair[0]))[:3]],
                'top_sellers': [{'agent_id': ident, 'quantity': qty}
                                for ident, qty in sorted(sellers.items(), key=lambda pair: (-pair[1], pair[0]))[:3]],
                'trades': matching_trades,
            }

    # Stockpiles
    stockpiles = {}
    for g, amt in getattr(tile, 'stockpiles', {}).items():
        g_name = g.name if hasattr(g, 'name') else str(g)
        stockpiles[g_name] = round(float(amt), 1)

    economic_actors = []
    for actor in getattr(tile, 'agents', []):
        if not getattr(actor, 'alive', True) or not (
                getattr(actor, 'is_corporation', False) or getattr(actor, 'is_lord', False)
                or getattr(actor, 'is_trader', False)):
            continue
        actor_name = getattr(actor, 'display_name', None)
        if not isinstance(actor_name, str) or not actor_name:
            actor_name = f"Actor {actor.id}"
        economic_actors.append({'id': int(actor.id), 'name': actor_name,
                                'cash': round(float(getattr(actor, 'cash', 0.0)), 2),
                                'output': getattr(getattr(actor, 'output', None), 'name', None),
                                'type': ('corporation' if getattr(actor, 'is_corporation', False)
                                         else 'trader' if getattr(actor, 'is_trader', False) else 'landholder')})

    # Completed Buildings
    buildings_list = []
    for b in getattr(tile, 'buildings', []):
        b_name = getattr(b, 'display_name', getattr(b, 'name', str(b)))
        buildings_list.append(b_name)

    # Active Construction Projects
    projects_list = []
    for p in getattr(tile, 'construction_projects', []):
        p_name = getattr(p.recipe, 'display_name', getattr(p.recipe, 'name', 'Project'))
        base_t = max(1, int(getattr(p, 'total_turns',
                                   getattr(p.recipe, 'base_turns', 1))))
        turns_left = int(getattr(p, 'turns_left',
                                 getattr(p, 'turns_remaining', base_t)))
        prog = max(0.0, min(1.0, float(getattr(p, 'progress_pct',
                                               100.0 * (1.0 - turns_left / base_t))) / 100.0))
        projects_list.append({
            'name': p_name,
            'turns_left': turns_left,
            'total_turns': int(base_t),
            'progress': round(prog * 100, 0),
            'private_owner_id': getattr(p, 'private_owner_id', None),
            'action': getattr(p, 'adoption_action', 'public'),
            'status': p.status,
        })

    # Ecological Metrics
    eco = {
        'soil_fertility': round(float(getattr(tile, 'soil_fertility', 1.0)) * 100, 0),
        'pollution_air': round(float(getattr(tile, 'pollution_air', 0.0)), 1),
        'nutrition_density': round(float(getattr(tile, 'nutrition_density', 1.0)) * 100, 0)
    }

    # Citizens Roster (first 25 living non-corp agents)
    citizens = []
    for a in getattr(tile, 'agents', []):
        if not getattr(a, 'alive', True) or getattr(a, 'is_corporation', False) or getattr(a, 'is_government', False):
            continue
        f_obj = getattr(a, 'faction', None)
        f_name = f_obj.name if f_obj and hasattr(f_obj, 'name') else 'None'
        from livelihood_access import effective_access
        claims = [c for c in getattr(tile, 'cash_obligations', [])
                  if c.debtor_id == a.id and c.status == 'active']
        due = [c for c in claims if c.due_turn <= turn]
        agreement = getattr(a, 'labor_agreement', None)
        decisions = [d for d in getattr(tile, 'labor_decision_log', [])
                     if d.get('worker_id') == a.id][-3:]
        livelihood_options = [d for d in getattr(tile, 'livelihood_decision_events', [])
                              if d.get('person_id') == a.id][-1:]
        timeline = sorted([e for e in (getattr(tile, 'access_events', [])
                                 + getattr(tile, 'obligation_events', [])
                                 + getattr(tile, 'lien_events', [])
                                 + getattr(tile, 'crop_share_events', [])
                                 + getattr(tile, 'labor_events', [])
                                 + getattr(tile, 'career_events', [])
                                 + getattr(tile, 'labor_status_events', []))
                    if e.get('person_id', e.get('debtor_id', e.get('worker_id', e.get('tenant_id')))) == a.id],
                         key=lambda e: int(e.get('turn', e.get('t', 0))))[-8:]
        if getattr(a, 'in_workhouse', False):
            labor_regime = 'workhouse'
        elif getattr(a, 'employer', None) is not None:
            labor_regime = 'wage+tenant' if getattr(a, 'assigned_plot_id', None) else 'wage'
        elif getattr(a, 'assigned_plot_id', None):
            labor_regime = 'sharecropper' if any(x.active and x.tenant_id == a.id and x.type == 'crop_share'
                                                 for x in getattr(tile, 'tenancy_agreements', [])) else 'tenant/subsistence'
        else:
            labor_regime = 'unemployed'
        citizens.append({
            'id': str(a.id),
            'age': int(a.age(turn)) if hasattr(a, 'age') else 30,
            'career': (getattr(getattr(a, 'primary_livelihood', None), 'name', None)
                       or ('Trader' if getattr(a, 'is_trader', False)
                           else 'Homesteader' if getattr(a, 'is_homesteader', False)
                           else 'Citizen')),
            'primary_livelihood': getattr(getattr(a, 'primary_livelihood', None), 'name', None),
            'employment_status': ('military' if getattr(a, 'military_unit_id', None)
                                  else 'trader' if getattr(a, 'is_trader', False)
                                  else 'constable' if getattr(a, 'social_class', None) == 'constable'
                                  else 'workhouse' if getattr(a, 'in_workhouse', False)
                                  else 'employed' if a.employer is not None
                                  else 'independent'),
            'food_foraged': int(getattr(a, 'food_foraged', 0)),
            'temporary_work_share': round(float(getattr(a, 'temporary_work_share', 0.0)), 2),
            'wage': round(float(getattr(a, 'wage', 0.0)), 2),
            'cash': round(float(getattr(a, 'cash', 0.0)), 1),
            'hungry': bool(getattr(a, 'hungry_steps', 0) > 0),
            'happiness': round(float(getattr(a, 'happiness', 1.0)), 2),
            'legal_food_access': round(effective_access(a, tile, 'commons_food', official=True), 3),
            'usable_food_access': round(effective_access(a, tile, 'commons_food'), 3),
            'obligations': [{'id': c.id, 'origin': c.origin, 'creditor_id': c.creditor_id,
                             'balance': round(c.balance, 2), 'due_turn': c.due_turn}
                            for c in claims],
            'cash_due': round(sum(c.balance for c in due), 2),
            'labor_regime': labor_regime,
            'labor_hours': round(float(getattr(agreement, 'hours', getattr(a, 'shift_hours', 0.0))), 1),
            'labor_pace': round(float(getattr(agreement, 'pace', 1.0)), 2),
            'real_wage_after_deductions': round(max(0.0, float(getattr(a, 'realized_wage', 0.0))
                                                   - float(getattr(a, 'authorized_deductions', 0.0))), 2),
            'ability_to_quit': 'penalty claim may apply' if getattr(tile, 'labor_laws', {}).get('quit_penalty') == 'enacted' else 'lawful exit',
            'recent_reasons': [{'turn': int(d.get('turn', 0)), 'reason': str(d.get('reason', '')),
                                'accepted': bool(d.get('accepted', False)),
                                'offer': float(d.get('offer', 0.0)),
                                'reservation': float(d.get('reservation', 0.0))}
                               for d in decisions],
            'livelihood_options': livelihood_options,
            'timeline': timeline,
            'work_fatigue': round(float(getattr(a, 'work_fatigue', 0.0)), 2),
            'alienation': round(float(getattr(a, 'alienation', 0.0)), 2),
            'faction': f_name
        })
        if len(citizens) >= 25:
            break

    gdp_val = float(tile.gdp_log[-1]) if getattr(tile, 'gdp_log', None) else 0.0
    unrest_val = float(tile.protest_energy_log[-1]) if getattr(tile, 'protest_energy_log', None) else 0.0

    # Economic charts data (10 series)
    from goods import Goods
    g_price = lambda gd: [round(float(p), 2) for p in tile.price_log.get(gd, [])[-30:]]
    g_prod = lambda gd: [round(float(p), 2) for p in tile.production_log.get(gd, [])[-30:]]
    g_inv = lambda gd: [round(float(p), 1) for p in tile.inventory_log.get(gd, [])[-30:]]
    def g_dem(good):
        chart_log = getattr(tile, 'market_demand_ratio_chart_log', {}) or {}
        if good in chart_log:
            points = chart_log[good]
            return [round(float(row['value']), 2) for row in points[-30:]]
        return [round(float(value), 2)
                for value in tile.demand_ratio_log.get(good, [])[-30:]]

    chart_goods = sorted(
        (good for good in getattr(tile, 'market_chart_goods',
                                  (Goods.food, Goods.wood, Goods.furniture,
                                   Goods.transport))
         if good not in (Goods.gov, Goods.none)),
        key=lambda good: good.name)
    market_price_series = {
        good.name: g_price(good) for good in chart_goods}
    market_production_series = {
        good.name: g_prod(good) for good in chart_goods}
    market_demand_ratio_series = {
        good.name: g_dem(good) for good in chart_goods}
    market_inventory_series = {
        good.name: g_inv(good) for good in chart_goods}

    pop_series = (tile.total_population or [])[-30:]
    hunger_keys = (Goods.food, Goods.wood, Goods.furniture, 'trader')
    hunger_histories = [list((getattr(tile, 'hungry_log', {}) or {}).get(key, []))
                        for key in hunger_keys]
    hunger_length = max((len(history) for history in hunger_histories), default=0)
    hungry_series = [
        sum(int(history[index]) for history in hunger_histories
            if index < len(history))
        for index in range(max(0, hunger_length - 30), hunger_length)]
    tot_exp = [round(float(value), 1)
               for value in getattr(tile, 'export_value_log', [])[-30:]]
    tot_imp = [round(float(value), 1)
               for value in getattr(tile, 'import_value_log', [])[-30:]]
    trade_balance_series = [round(float(value), 1)
                            for value in getattr(tile, 'net_trade_value_log', [])[-30:]]

    t_gov = getattr(tile, 'gov', None)
    t_income = getattr(t_gov, 'income_log', []) if t_gov is not None else []
    tax_series = [round(e.get('tax', 0.0), 2) for e in t_income][-30:]
    tariff_series = [round(e.get('tariff', 0.0), 2) for e in t_income][-30:]
    inherit_series = [round(e.get('inheritance', 0.0), 2) for e in t_income][-30:]

    protest_series = [round(float(p), 2) for p in (tile.protest_energy_log or [])][-30:]
    gdp_series = [round(float(g), 1) for g in (tile.gdp_log or [])][-30:]
    gini_series = [round(float(g) * 100.0, 1) for g in (tile.gini_log.get(Goods.food, []) or [])][-30:]
    migr_series = [round(float(m), 1) for m in (getattr(tile, 'migration_intent_log', []) or [])][-30:]
    commons_series = [round(float(c) * 100.0, 1) for c in (getattr(tile, 'tenure_log', []) or [])][-30:]

    # Ecological & Epidemics charts (6 series)
    fert_series = [round(float(f) * 100.0, 1) for f in (getattr(tile, 'soil_fertility_log', []) or [])][-30:]
    nutr_series = [round(float(n) * 100.0, 1) for n in (getattr(tile, 'nutrition_density_log', []) or [])][-30:]
    smog_series = [round(float(s), 1) for s in (getattr(tile, 'pollution_air_log', []) or [])][-30:]
    water_series = [round(float(w), 1) for w in (getattr(tile, 'pollution_water_log', []) or [])][-30:]
    soil_series = [round(float(s), 1) for s in (getattr(tile, 'pollution_soil_log', []) or [])][-30:]

    d_cases = (getattr(tile, 'disease_cases_log', []) or [])[-30:]
    malnutr_series = [c.get('malnutrition', 0) if isinstance(c, dict) else 0 for c in d_cases]
    cholera_series = [c.get('waterborne', 0) if isinstance(c, dict) else 0 for c in d_cases]
    respir_series = [c.get('respiratory', 0) if isinstance(c, dict) else 0 for c in d_cases]
    chem_series = [c.get('chemical', 0) if isinstance(c, dict) else 0 for c in d_cases]

    priv_spend = [round(float(s), 1) for s in (getattr(tile, 'medical_spending_private_log', []) or [])][-30:]
    pub_spend = [round(float(s), 1) for s in (getattr(tile, 'medical_spending_public_log', []) or [])][-30:]
    untreated_series = (getattr(tile, 'untreated_cases_log', []) or [])[-30:]
    fatalities_series = (getattr(tile, 'disease_fatalities_log', []) or [])[-30:]
    health_attr_series = [round(float(h) * 100.0, 1) for h in (getattr(tile, 'avg_health_attrition_log', []) or [])][-30:]

    # Labor & Alienation chart series
    shifts_series = [round(float(s), 1) for s in (getattr(tile, 'avg_shift_hours_log', []) or [])][-30:]
    sv_rates_series = [round(float(v) * 100.0, 1) for v in (getattr(tile, 'rate_of_exploitation_log', []) or [])][-30:]
    effective_caps = [round(float(v), 1) for v in
                      (getattr(tile, 'workday_cap_log', []) or [])][-30:]
    alienation_series = [round(float(a) * 100.0, 1) for a in (getattr(tile, 'avg_alienation_log', []) or [])][-30:]
    health_series = health_attr_series
    consc_series = [round(float(c) * 100.0, 1) for c in (getattr(tile, 'avg_consciousness_log', []) or [])][-30:]
    entertain_series = [round(float(e) * 100.0, 1) for e in (getattr(tile, 'entertainment_log', []) or [])][-30:]
    strikers_series = (getattr(tile, 'strikers_log', []) or [])[-30:]
    broken_series = (getattr(tile, 'sabotage_log', []) or [])[-30:]
    machines_series = (getattr(tile, 'broken_machinery_log', []) or [])[-30:]
    accidents_series = (getattr(tile, 'workplace_accidents_log', []) or [])[-30:]

    # Social Class charts (4 series)
    clogs = (getattr(tile, 'social_class_log', []) or [])[-30:]
    serfs_series = [d.get('serf', 0) for d in clogs]
    tenants_series = [d.get('tenant', 0) for d in clogs]
    proles_series = [d.get('proletarian', 0) for d in clogs]
    disposs_series = [d.get('dispossessed', 0) for d in clogs]
    gentry_series = [d.get('lord', 0) + d.get('landlord', 0) for d in clogs]
    bourg_series = [d.get('petty_bourgeois', 0) + d.get('industrialist', 0) for d in clogs]
    foraged_series = (getattr(tile, 'food_foraged_log', []) or [])[-30:]
    purchased_series = (getattr(tile, 'food_purchased_log', []) or [])[-30:]
    rent_series = [round(float(r), 1) for r in (getattr(tile, 'rent_collected_log', []) or [])][-30:]
    arrears_series = [round(float(a), 1) for a in (getattr(tile, 'rent_arrears_log', []) or [])][-30:]
    living_people = [a for a in getattr(tile, 'agents', []) if a.alive and not a.is_trader
                     and not a.is_government and not a.is_corporation and not getattr(a, 'is_lord', False)]
    labor_counts = {
        'subsistence': sum(1 for a in living_people if a.employer is None and a.assigned_plot_id and not getattr(a, 'in_workhouse', False)),
        'tenant_sharecropper': sum(1 for a in living_people if any(x.active and x.tenant_id == a.id for x in getattr(tile, 'tenancy_agreements', []))),
        'wage': sum(1 for a in living_people if a.employer is not None),
        'unemployed': sum(1 for a in living_people if a.employer is None and not a.assigned_plot_id and not getattr(a, 'in_workhouse', False)),
        'compulsory': sum(1 for a in living_people if getattr(a, 'in_workhouse', False)),
    }
    all_residents = [a for a in getattr(tile, 'agents', []) if a.alive
                     and not a.is_government and not a.is_corporation]
    adult_residents = [a for a in all_residents
                       if not (getattr(a, 'is_native_child', False) and a.age(turn) < 14)]
    livelihood_counts = {}
    for a in adult_residents:
        livelihood = getattr(getattr(a, 'primary_livelihood', None), 'name', 'none')
        livelihood_counts[livelihood] = livelihood_counts.get(livelihood, 0) + 1
    labor_counts.update({
        'adult_residents': len(adult_residents),
        'traders': sum(1 for a in adult_residents if getattr(a, 'is_trader', False)),
        'military': sum(1 for a in adult_residents if getattr(a, 'military_unit_id', None)),
        'hungry_adults': sum(1 for a in adult_residents if getattr(a, 'hungry_steps', 0) > 0),
        'foraging_adults': sum(1 for a in adult_residents if getattr(a, 'food_foraged', 0) > 0),
        'average_foraged_food': round(sum(getattr(a, 'food_foraged', 0) for a in adult_residents)
                                      / max(1, len(adult_residents)), 2),
        'average_temporary_work_share': round(sum(getattr(a, 'temporary_work_share', 0.0)
                                                   for a in adult_residents)
                                              / max(1, len(adult_residents)), 3),
    })
    bank = getattr(tile, 'bank', None)
    financial_institution = None
    if bank is not None:
        capital = float(getattr(bank, 'capital', 0.0))
        deposits = float(getattr(bank, 'total_deposits', 0.0))
        liabilities = float(getattr(bank, 'total_liabilities', 0.0))
        financial_institution = {
            'type': 'commercial_bank',
            'currency': getattr(tile, 'home_currency', None),
            'capital': round(capital, 2),
            'equity': round(capital + deposits - liabilities, 2),
            'deposits': round(deposits, 2),
            'liabilities': round(liabilities, 2),
            'cumulative_bond_writeoffs': round(float(
                getattr(bank, 'cumulative_writedowns', 0.0)), 2),
            'deposit_frozen': bool(getattr(bank, 'is_frozen', False)),
            'foreign_reserves': {
                str(currency): round(float(amount), 2)
                for currency, amount in getattr(bank, 'foreign_reserves', {}).items()},
            'sovereign_bonds_held': [
                {'bond_id': row.get('bond_id'),
                 'principal': round(float(row.get('principal', 0.0)), 2),
                 'coupon': round(float(row.get('coupon', 0.0)), 4)}
                for row in getattr(bank, 'sovereign_bonds_held', [])],
        }

    return {
        'name': tile.name,
        'display_name': getattr(tile, 'display_name', getattr(tile, 'city_name', tile.name)),
        'row': grid_r if grid_r is not None else 0,
        'col': grid_c if grid_c is not None else 0,
        'q': q,
        'r': r,
        'centroid': centroid,
        'polygon': polygon,
        'neighbors': neighbors,
        'nation': tile.owner_nation.name if getattr(tile, 'owner_nation', None) else None,
        'color': tile_color,
        'elevation': float(getattr(tile, 'elevation', 0.0)),
        'elevation_meters': float(getattr(tile, 'elevation_meters', 0.0)),
        'biome': getattr(tile, 'biome', 'plains'),
        'is_ocean': getattr(tile, 'is_ocean', False),
        'wilderness': getattr(tile, 'wilderness', False),
        'cost_of_living': float(getattr(tile, 'cost_of_living', 1.0)),
        'gdp': round(gdp_val, 1),
        'protest_energy': round(unrest_val, 2),
        'market_prices': market_prices,
        'market_activity': market_activity,
        'stockpiles': stockpiles,
        'economic_actors': economic_actors,
        'actor_accounts': sorted(
            (dict(row) for row in getattr(tile, 'actor_turn_accounts', [])
             if ((row['type'] in ('corporation', 'grower') and
                 (row['event_ids'] or row['sales_cash'] or row['crop_value']))
                 or row.get('company_debt_written_off', 0.0)
                 or row.get('company_receivable_written_off', 0.0)
                 or row.get('tax_arrears_written_off', 0.0)
                 or row.get('tax_receivable_written_off', 0.0)
                 or row.get('cash_obligation_written_off', 0.0)
                 or row.get('obligation_receivable_written_off', 0.0)
                 or row.get('crop_lien_debt_settled', 0.0)
                 or row.get('crop_lien_receivable_settled', 0.0)
                 or row.get('crop_share_rent_paid', 0.0)
                 or row.get('crop_share_rent_received', 0.0)
                 or row.get('opening_wage_arrears_payable', 0.0)
                 or row.get('closing_wage_arrears_payable', 0.0)
                 or row.get('opening_wage_arrears_claim', 0.0)
                 or row.get('closing_wage_arrears_claim', 0.0)
                 or row.get('wage_arrears_accrued', 0.0)
                 or row.get('wage_arrears_payable_paid', 0.0)
                 or row.get('wage_arrears_payable_written_off', 0.0)
                 or row.get('wage_arrears_claim_accrued', 0.0)
                 or row.get('wage_arrears_claim_paid', 0.0)
                 or row.get('wage_arrears_claim_written_off', 0.0)
                 or row.get('wage_arrears_claim_inherited', 0.0))),
            key=lambda row: (-row['crop_value'] - row['sales_cash']
                             - row.get('crop_lien_receivable_settled', 0.0)
                             - row.get('crop_share_rent_received', 0.0)
                             - row.get('company_debt_written_off', 0.0)
                             - row.get('company_receivable_written_off', 0.0),
                             -row.get('tax_arrears_written_off', 0.0)
                             -row.get('tax_receivable_written_off', 0.0)
                             -row.get('cash_obligation_written_off', 0.0)
                             -row.get('obligation_receivable_written_off', 0.0),
                             row['actor_id']))[:20],
        'economic_events': list(getattr(tile, 'economic_events', [])[-20:]),
        'financial_institution': financial_institution,
        'buildings': buildings_list,
        'construction_projects': projects_list,
        'garrison': int(getattr(tile, 'garrison', 0)),
        'ecology': eco,
        'citizens': citizens,
        'food_support': __import__('food_outlook').snapshot(tile),
        'production_needs': __import__('production_needs').needs(tile),
        'production_programs': list(getattr(tile, 'production_programs', ())),
        'farms': [{'id': f['id'], 'operator_id': f['operator_id'], 'area': f['area'],
                   'planted_area': (f.get('crop') or {}).get('planted_area', 0),
                   'harvested': (f.get('crop') or {}).get('harvested', 0),
                   'seed_units': f['food_milli'] / 1000}
                  for f in getattr(tile, 'farms', {}).values()],
        'labor_institutions': {
            'career_transitions': getattr(tile, 'career_transition_state', None),
            'counts': labor_counts,
            'livelihoods': dict(sorted(livelihood_counts.items())),
            'affected_households': len({c.debtor_id for c in getattr(tile, 'cash_obligations', []) if c.status == 'active'}),
            'obligations': [{'id': c.id, 'debtor_id': c.debtor_id, 'creditor_id': c.creditor_id,
                             'origin': c.origin, 'balance': round(c.balance, 2),
                             'due_turn': c.due_turn, 'status': c.status}
                            for c in getattr(tile, 'cash_obligations', [])],
            'paid_this_turn': [e for e in getattr(tile, 'obligation_events', []) if e.get('turn', turn) == turn],
            'cases': [{'id': c.id, 'kind': c.kind, 'target_person_id': c.target_person_id,
                       'state': c.state, 'outcome': c.outcome, 'officer_cost': c.officer_cost}
                      for c in getattr(tile, 'enforcement_cases', [])],
            'enforcement_costs': round(sum(c.officer_cost for c in getattr(tile, 'enforcement_cases', [])), 2),
            'laws': dict(getattr(tile, 'labor_laws', {})),
            'cash_tax_per_person': float(getattr(tile, 'cash_tax_per_person', 0.0)),
        },
        'collective_action': {
            'organizations': organization_summary(tile),
            'events': recent_collective_events(tile, 16),
            'politics': political_summary(tile),
        },
        'charts': {
            'economic': {
                'prices': market_price_series,
                'pop_hunger': {'pop': pop_series, 'hungry': hungry_series},
                'production': market_production_series,
                'trade_flow': {'export': tot_exp, 'import': tot_imp,
                               'balance': trade_balance_series},
                'gov_income': {'tax': tax_series, 'tariff': tariff_series, 'inheritance': inherit_series},
                'gini_migration': {'gini': gini_series, 'migration': migr_series},
                'inventories': market_inventory_series,
                'protest_commons': {'protest': protest_series, 'commons': commons_series},
                'gdp': gdp_series,
                'demand_ratio': market_demand_ratio_series,
            },
            'ecological': {
                'soil_nutrition': {'soil': fert_series, 'nutrition': nutr_series},
                'pollution': {'smog': smog_series, 'water': water_series, 'soil': soil_series},
                'epidemics': {'malnutrition': malnutr_series, 'cholera': cholera_series, 'bronchitis': respir_series, 'toxic': chem_series},
                'healthcare_outlay': {'private': priv_spend, 'public': pub_spend},
                'untreated_fatalities': {'untreated': untreated_series, 'fatalities': fatalities_series},
                'health_attrition': health_attr_series,
            },
            'labor': {
                'shifts_exploitation': {'shifts': shifts_series, 'caps': effective_caps, 'sv_rate': sv_rates_series},
                'alienation_health': {'alienation': alienation_series, 'health': health_series},
                'consciousness_pacification': {'consciousness': consc_series, 'entertainment': entertain_series, 'protest': protest_series},
                'workplace_resistance': {'strikers': strikers_series, 'sabotage': broken_series, 'broken': machines_series},
                'workplace_conditions': {'accidents': accidents_series,
                                         'entertainment': entertain_series,
                                         'sabotage': broken_series,
                                         'broken': machines_series},
            },
            'citizens': {
                'classes': {'serf': serfs_series, 'tenant': tenants_series, 'worker': proles_series, 'dispossessed': disposs_series, 'gentry': gentry_series, 'artisan': bourg_series},
                'food_source': {'foraged': foraged_series, 'market': purchased_series, 'hungry': hungry_series},
                'commons_rent': {'commons': commons_series, 'rent': rent_series, 'arrears': arrears_series},
                'disparity_unrest': {'gini': gini_series, 'protest': protest_series},
            }
        },
        'tenure': {
            'commons_access': float(getattr(tenure, 'commons_access', 1.0)) if tenure else 1.0,
            'feudal_fraction': float(getattr(tenure, 'feudal_fraction', 0.0)) if tenure else 0.0,
            'enclosed_fraction': float(getattr(tenure, 'enclosed_fraction', 0.0)) if tenure else 0.0,
            'pasture_fraction': float(getattr(tenure, 'pasture_fraction', 0.0)) if tenure else 0.0,
            'arable_fraction': float(getattr(tenure, 'arable_fraction', 0.0)) if tenure else 0.0,
            'plots': plots_data,
            'survey_debts': survey_debts,
            'water_rights_initialized': bool(getattr(tile, 'water_rights_initialized', False)),
            'water_source_capacity': float(getattr(tile, 'water_source_capacity', 0.0)),
            'water_allocation_turn': int(getattr(tile, 'water_allocation_turn', -1)),
            'water_allocations': dict(getattr(tile, 'water_allocations', {})),
            'water_rights': [
                {'id': r.id, 'plot_id': r.plot_id, 'holder_id': r.holder_id, 'units': r.units}
                for r in getattr(tile, 'water_rights', [])],
            'offtake_contracts': [dict(c) for c in getattr(tile, 'offtake_contracts', [])
                                  if c.get('status') == 'active'],
            'supply_proposals': [dict(c) for c in getattr(tile, 'supply_proposals', [])[-20:]],
            'supply_proposal_events': list(getattr(tile, 'supply_proposal_events', [])[-20:]),
            'offtake_events': list(getattr(tile, 'offtake_events', [])[-20:]),
            'land_transfer_events': list(getattr(tile, 'land_transfer_events', [])[-20:]),
            'water_right_events': list(getattr(tile, 'water_right_events', [])[-20:]),
            'water_allocation_events': list(getattr(tile, 'water_allocation_events', [])[-10:]),
            'market_charters': [dict(c) for c in getattr(tile, 'market_charters', [])
                                if c.get('status') == 'active'],
            'concession_petitions': [dict(c) for c in getattr(tile, 'concession_petitions', [])
                                     if c.get('status') == 'proposed'],
            'concession_events': list(getattr(tile, 'concession_events', [])[-20:]),
            'land_leases': [dict(c) for c in getattr(tile, 'land_leases', [])
                            if c.get('status') == 'active'],
        },
        'workhouse': {
            'active': wh_active,
            'inmate_count': len(wh_inmates),
            'inmate_ids': wh_inmates,
            'census': wh_census,
        },
        'labor': {
            'shift_hours': shift_h,
            'max_workday_hours': max_workday,
            'ten_hour_act': bool(getattr(tile, 'ten_hour_act', max_workday <= 10.0)),
            'surplus_value': sv,
            'rate_of_exploitation': roe,
        },
        'population': tile.total_population[-1] if getattr(tile, 'total_population', None) else len(getattr(tile, 'agents', [])),
    }

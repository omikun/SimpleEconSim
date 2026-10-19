"""Read-only end-of-turn observations and explicit provenance gaps."""

from goods import Goods


def _agent_role(agent):
    if getattr(agent, 'is_corporation', False):
        return 'corporation'
    if getattr(agent, 'is_government', False):
        return 'government'
    return 'person'


def resident_census(tiles):
    """Capture immutable location fields for the living resident population."""
    census = {}
    for tile in tiles:
        owner = getattr(tile, 'owner_nation', None)
        nation = getattr(owner, 'name', None) or 'Unclaimed'
        for person in getattr(tile, 'agents', ()):
            if (not getattr(person, 'alive', True)
                    or getattr(person, 'is_corporation', False)
                    or getattr(person, 'is_government', False)):
                continue
            person_id = getattr(person, 'id', None)
            if person_id in census:
                raise AssertionError(f'duplicate living person id {person_id}')
            census[person_id] = {'agent': person, 'tile': tile.name, 'nation': nation}
    return census


def entity_role_census(tiles):
    """Remember entity roles so person/corporation conversions are visible."""
    return {getattr(agent, 'id', None): _agent_role(agent)
            for tile in tiles for agent in getattr(tile, 'agents', ())}


def _territorial_mix_evidence(metric_id, nation_name, good_name, current_members,
                              previous_members, previous_values, current_values,
                              previous_tile_currencies, current_tile_currencies,
                              previous_nation_currency, current_nation_currency):
    """Show changing territory coverage separately from continuing-tile values."""
    previous_members = list(previous_members or ())
    previous_set, current_set = set(previous_members), set(current_members)
    common = sorted(previous_set & current_set)

    def member_key(tile_name):
        if metric_id == 'living.cost_of_living':
            return (metric_id, tile_name)
        if metric_id == 'goods.national_food_price':
            return ('goods.price', tile_name, good_name)
        return (metric_id, tile_name, good_name)

    if metric_id == 'goods.national_food_price':
        common_with_values = common
        prior_values = [previous_values.get(member_key(tile_name),
                                            (None, None, 0.0))[2]
                        for tile_name in common_with_values]
        current_member_values = [current_values.get(member_key(tile_name),
                                                     (None, None, 0.0))[2]
                                 for tile_name in common_with_values]
    else:
        common_with_values = [tile_name for tile_name in common
                              if member_key(tile_name) in previous_values
                              and member_key(tile_name) in current_values]
        prior_values = [previous_values[member_key(tile_name)][2]
                        for tile_name in common_with_values]
        current_member_values = [current_values[member_key(tile_name)][2]
                                 for tile_name in common_with_values]
    prior_common_mean = (sum(prior_values) / len(prior_values)
                         if prior_values else None)
    current_common_mean = (sum(current_member_values) / len(current_member_values)
                           if current_member_values else None)
    national_key = ((metric_id, nation_name)
                    if metric_id in ('living.cost_of_living',
                                     'goods.national_food_price') else
                    (metric_id, nation_name, good_name))
    prior_national = previous_values.get(national_key)
    current_national = current_values.get(national_key)
    continuing_change = (current_common_mean - prior_common_mean
                         if prior_common_mean is not None
                         and current_common_mean is not None else None)
    national_change = (current_national[2] - prior_national[2]
                       if prior_national is not None and current_national is not None
                       else None)
    current_currencies = {current_tile_currencies.get(tile_name)
                          for tile_name in current_set}
    previous_currencies = {previous_tile_currencies.get(tile_name)
                           for tile_name in previous_set}
    currencies_stable = (
        previous_nation_currency == current_nation_currency
        and all(previous_tile_currencies.get(tile_name)
                == current_tile_currencies.get(tile_name)
                for tile_name in common_with_values)
        and len(current_currencies) <= 1
        and len(previous_currencies) <= 1
        and current_currencies == previous_currencies
        and None not in current_currencies
        and None not in previous_currencies)
    composition_residual = (national_change - continuing_change
                            if national_change is not None
                            and continuing_change is not None
                            and currencies_stable else None)
    return {
        'previous_member_tiles': previous_members,
        'current_member_tiles': list(current_members),
        'added_member_tiles': sorted(current_set - previous_set),
        'removed_member_tiles': sorted(previous_set - current_set),
        'common_member_tiles': common_with_values,
        'membership_changed': previous_set != current_set,
        'previous_nation_mean': prior_national[2] if prior_national else None,
        'current_nation_mean': current_national[2] if current_national else None,
        'national_mean_change': national_change,
        'prior_common_member_mean': prior_common_mean,
        'current_common_member_mean': current_common_mean,
        'continuing_member_mean_change': continuing_change,
        'territorial_composition_residual': composition_residual,
        'currency_membership_stable': currencies_stable,
        'delta_decomposition_status': (
            'arithmetic_decomposition_available'
            if composition_residual is not None else
            'mixed_or_changed_currency' if not currencies_stable else
            'no_prior_common_members_or_value'),
        'delta_decomposition_note': (
            'Continuing-member change plus territorial residual is an arithmetic '
            'decomposition, not an independent causal share.'),
    }


def resident_population_bridges(previous, current, previous_roles, tiles, turn,
                                flow_event_ids=None):
    """Reconcile resident census changes for tiles and territorial nations.

    Residents are living agents excluding corporations and governments. The
    bridge uses identity and location changes rather than inferring deaths from
    disappearance. The observed census difference must equal its classified
    births, entries, movements, deaths, and role conversions; anything else is
    retained as an explicit unknown exit or residual.
    """
    from collections import Counter, defaultdict

    tiles_by_name = {tile.name: tile for tile in tiles}
    tile_nations = {
        tile.name: (getattr(getattr(tile, 'owner_nation', None), 'name', None)
                    or 'Unclaimed') for tile in tiles}
    current_agents = {}
    for tile in tiles:
        for agent in getattr(tile, 'agents', ()):
            current_agents[getattr(agent, 'id', None)] = {
                'agent': agent, 'tile': tile.name,
                'nation': tile_nations[tile.name], 'role': _agent_role(agent)}

    sources = flow_event_ids or {}
    tile_flows = defaultdict(lambda: defaultdict(list))
    nation_flows = defaultdict(lambda: defaultdict(list))

    def add(table, location, kind, person_id, **details):
        item = {'agent_id': str(person_id), **details}
        for event_id in sources.get(str(person_id), ()):
            item.setdefault('cause_event_ids', []).append(event_id)
        table[location][kind].append(item)

    def movement(person_id, old, new):
        if old['tile'] != new['tile']:
            add(tile_flows, old['tile'], 'departures', person_id,
                destination=new['tile'])
            add(tile_flows, new['tile'], 'arrivals', person_id,
                origin=old['tile'])
        if old['nation'] != new['nation']:
            basis = ('cross_tile_migration' if old['tile'] != new['tile']
                     else 'territorial_membership_change')
            add(nation_flows, old['nation'], 'departures', person_id,
                destination=new['nation'], basis=basis,
                origin_tile=old['tile'], destination_tile=new['tile'])
            add(nation_flows, new['nation'], 'arrivals', person_id,
                origin=old['nation'], basis=basis,
                origin_tile=old['tile'], destination_tile=new['tile'])

    def death_location(prior, agent):
        location = (getattr(agent, 'death_region', None)
                    or getattr(agent, 'region', None))
        if location not in tiles_by_name:
            location = prior['tile']
        return {'tile': location, 'nation': tile_nations.get(location, prior['nation'])}

    for person_id in previous.keys() | current.keys():
        prior = previous.get(person_id)
        now = current.get(person_id)
        if prior is None:
            if previous_roles.get(person_id) in ('corporation', 'government'):
                add(tile_flows, now['tile'], 'role_conversions_in', person_id,
                    from_role=previous_roles[person_id])
                add(nation_flows, now['nation'], 'role_conversions_in', person_id,
                    from_role=previous_roles[person_id], tile=now['tile'])
            elif (getattr(now['agent'], 'is_native_child', False)
                  and getattr(now['agent'], 'birth_round', None) == turn):
                add(tile_flows, now['tile'], 'births', person_id,
                    parent_id=getattr(getattr(now['agent'], 'parent', None), 'id', None))
                add(nation_flows, now['nation'], 'births', person_id,
                    tile=now['tile'])
            else:
                add(tile_flows, now['tile'], 'external_entries', person_id)
                add(nation_flows, now['nation'], 'external_entries', person_id,
                    tile=now['tile'])
            continue

        if now is not None:
            movement(person_id, prior, now)
            continue

        agent = prior['agent']
        raw = current_agents.get(person_id)
        if not getattr(agent, 'alive', True):
            destination = death_location(prior, agent)
            movement(person_id, prior, destination)
            cause = getattr(agent, 'death_cause', None) or 'unclassified'
            add(tile_flows, destination['tile'], 'deaths', person_id,
                death_cause=cause)
            add(nation_flows, destination['nation'], 'deaths', person_id,
                death_cause=cause, tile=destination['tile'])
        elif raw is not None and raw['role'] in ('corporation', 'government'):
            movement(person_id, prior, raw)
            add(tile_flows, raw['tile'], 'role_conversions_out', person_id,
                to_role=raw['role'])
            add(nation_flows, raw['nation'], 'role_conversions_out', person_id,
                to_role=raw['role'], tile=raw['tile'])
        else:
            add(tile_flows, prior['tile'], 'unknown_exits', person_id)
            add(nation_flows, prior['nation'], 'unknown_exits', person_id,
                tile=prior['tile'])

    def bridge_rows(before_counts, after_counts, flows, scope):
        rows = []
        for location in sorted(before_counts.keys() | after_counts.keys() | flows.keys()):
            before = int(before_counts[location])
            after = int(after_counts[location])
            entries = flows.get(location, {})
            counts = {kind: len(people) for kind, people in entries.items()}
            expected = (before + counts.get('births', 0)
                        + counts.get('external_entries', 0)
                        + counts.get('arrivals', 0)
                        + counts.get('role_conversions_in', 0)
                        - counts.get('departures', 0)
                        - counts.get('deaths', 0)
                        - counts.get('role_conversions_out', 0)
                        - counts.get('unknown_exits', 0))
            residual = after - expected
            unknown_exits = counts.get('unknown_exits', 0)
            explanation_complete = residual == 0 and unknown_exits == 0
            if before == after and not any(counts.values()):
                continue
            event_ids = sorted({event_id for people in entries.values()
                                for item in people
                                for event_id in item.get('cause_event_ids', ())})
            rows.append({
                'scope': scope, 'id': location, 'before': before, 'after': after,
                'inputs': {'turn': int(turn), 'flows': dict(entries),
                           'flow_counts': counts, 'expected_after': expected,
                           'unexplained_residual': residual,
                           'explanation_complete': explanation_complete,
                           'reconciled': residual == 0,
                           'resident_definition': 'living agents excluding corporations and governments'},
                'cause_event_ids': event_ids})
        return rows

    before_tile = Counter(row['tile'] for row in previous.values())
    after_tile = Counter(row['tile'] for row in current.values())
    before_nation = Counter(row['nation'] for row in previous.values())
    after_nation = Counter(row['nation'] for row in current.values())
    return (bridge_rows(before_tile, after_tile, tile_flows, 'tile')
            + bridge_rows(before_nation, after_nation, nation_flows, 'nation'))


def sample(tiles, nations):
    values = {}
    for tile in tiles:
        tile_subject = {'type': 'tile', 'id': tile.name}
        bank = getattr(tile, 'bank', None)
        if bank is not None:
            capital = float(getattr(bank, 'capital', 0.0))
            deposits = float(getattr(bank, 'total_deposits', 0.0))
            liabilities = float(getattr(bank, 'total_liabilities', 0.0))
            for metric_id, value in (
                    ('finance.bank_capital', capital),
                    ('finance.bank_equity', capital + deposits - liabilities),
                    ('finance.bank_deposits', deposits),
                    ('finance.bank_liabilities', liabilities),
                    ('finance.bank_cumulative_writedowns', float(
                        getattr(bank, 'cumulative_writedowns', 0.0)))):
                values[(metric_id, tile.name)] = (tile_subject, 'local_currency', value)
        for good, recipe in tile.recipes.items():
            if not isinstance(good, Goods):
                continue
            if recipe is not None and 'price' in recipe:
                subject = {**tile_subject, 'good': good.name}
                values[('goods.price', tile.name, good.name)] = (
                    subject, 'local_currency_per_unit', float(recipe['price']))
                for metric_id, field, unit in (
                        ('goods.production', 'production_log', 'units_per_turn'),
                        ('goods.demand', 'demand_log', 'units_offered'),
                        ('goods.supply', 'supply_log', 'units_offered'),
                        ('goods.sold', 'sold_log', 'units'),
                        ('goods.producer_inventory', 'inventory_log', 'units')):
                    history = getattr(tile, field, {}).get(good, ())
                    if history:
                        values[(metric_id, tile.name, good.name)] = (
                            subject, unit, float(history[-1]))
        for profession, history in getattr(tile, 'population_log', {}).items():
            if not history or int(history[-1]) == 0:
                continue
            profession_name = getattr(profession, 'name', str(profession))
            subject = {**tile_subject, 'profession': profession_name}
            values[('people.profession_population', tile.name, profession_name)] = (
                subject, 'people', int(history[-1]))
        for good, history in getattr(tile, 'gini_log', {}).items():
            if not isinstance(good, Goods) or not history:
                continue
            subject = {**tile_subject, 'good': good.name}
            values[('economy.gini', tile.name, good.name)] = (
                subject, 'ratio', float(history[-1]))
        values[('people.population', tile.name)] = (
            tile_subject, 'people', tile.total_population[-1]
            if getattr(tile, 'total_population', None) else len(tile.agents))
        values[('people.deaths', tile.name)] = (
            tile_subject, 'people_per_turn', int(getattr(tile, 'deaths_this_turn', 0)))
        values[('people.births', tile.name)] = (
            tile_subject, 'people_per_turn', int(getattr(tile, 'births_this_turn', 0)))
        government = getattr(tile, 'gov', None)
        income_history = getattr(government, 'income_log', ()) if government else ()
        if income_history:
            income = income_history[-1]
            values[('finance.government_income', tile.name)] = (
                tile_subject,
                getattr(tile, 'home_currency', None) or 'local_currency',
                sum(float(income.get(key, 0.0))
                    for key in ('tax', 'tariff', 'inheritance')))
        for metric_id, field in (
                ('trade.export_value', 'export_value_log'),
                ('trade.import_value', 'import_value_log'),
                ('trade.net_value', 'net_trade_value_log')):
            history = getattr(tile, field, ())
            if history:
                values[(metric_id, tile.name)] = (
                    tile_subject,
                    getattr(tile, 'home_currency', None) or 'local_currency',
                    float(history[-1]))
        for metric_id, field, unit in (
                ('labor.average_shift_hours', 'avg_shift_hours_log', 'hours'),
                ('labor.average_alienation', 'avg_alienation_log', 'ratio'),
                ('labor.average_class_consciousness', 'avg_consciousness_log', 'ratio'),
                ('labor.exploitation_rate', 'rate_of_exploitation_log', 'ratio'),
                ('labor.strikers', 'strikers_log', 'people')):
            history = getattr(tile, field, ())
            if history:
                values[(metric_id, tile.name)] = (
                    tile_subject, unit, float(history[-1]))
        values[('people.residents', tile.name)] = (
            tile_subject, 'people', sum(
                1 for person in tile.agents if person.alive
                and not person.is_corporation and not person.is_government))
        adults = [person for person in tile.agents if person.alive
                  and not person.is_corporation and not person.is_government
                  and not (getattr(person, 'is_native_child', False)
                           and person.age(getattr(tile, '_last_turn', 0)) < 14)]
        livelihood_counts = {}
        status_counts = {}
        temporary_share = 0.0
        for person in adults:
            livelihood = getattr(getattr(person, 'primary_livelihood', None), 'name', 'none')
            livelihood_counts[livelihood] = livelihood_counts.get(livelihood, 0) + 1
            status = ('military' if getattr(person, 'military_unit_id', None) else
                      'trader' if getattr(person, 'is_trader', False) else
                      'constable' if getattr(person, 'social_class', None) == 'constable' else
                      'workhouse' if getattr(person, 'in_workhouse', False) else
                      'employed' if getattr(person, 'employer', None) is not None else 'independent')
            status_counts[status] = status_counts.get(status, 0) + 1
            temporary_share += float(getattr(person, 'temporary_work_share', 0.0))
        for livelihood, count in livelihood_counts.items():
            values[('labor.primary_livelihood', tile.name, livelihood)] = (
                {**tile_subject, 'livelihood': livelihood}, 'adults', count)
        for status, count in status_counts.items():
            values[('labor.employment_status', tile.name, status)] = (
                {**tile_subject, 'status': status}, 'adults', count)
        values[('labor.hungry_adults', tile.name)] = (
            tile_subject, 'adults', sum(1 for person in adults
                                        if getattr(person, 'hungry_steps', 0) > 0))
        values[('labor.temporary_work_share', tile.name)] = (
            tile_subject, 'adult_turn_share', temporary_share / max(1, len(adults)))
        if tile.protest_energy_log:
            values[('politics.protest_energy', tile.name)] = (
                tile_subject, 'score', float(tile.protest_energy_log[-1]))
        if tile.unrest_log:
            values[('politics.unrest_event', tile.name)] = (
                tile_subject, 'stage', tile.unrest_log[-1].get('stage', 'calm'))
        for metric_id, field, unit in (
                ('ecology.soil_fertility', 'soil_fertility', 'ratio'),
                ('ecology.nutrition_density', 'nutrition_density', 'ratio'),
                ('ecology.pollution_air', 'pollution_air', 'index'),
                ('ecology.pollution_water', 'pollution_water', 'index'),
                ('ecology.pollution_soil', 'pollution_soil', 'index')):
            if hasattr(tile, field):
                values[(metric_id, tile.name)] = (
                    tile_subject, unit, float(getattr(tile, field)))
        bodily_wear_history = getattr(tile, 'avg_health_attrition_log', ())
        if bodily_wear_history:
            values[('health.average_bodily_wear', tile.name)] = (
                tile_subject, 'attrition_points',
                float(bodily_wear_history[-1]))
        disease_cases = {disease: sum(
            1 for person in tile.agents
            if getattr(person, 'alive', True)
            and disease in (getattr(person, 'diseases', []) or []))
            for disease in ('malnutrition', 'waterborne', 'respiratory', 'chemical', 'pestilence')}
        for disease, count in disease_cases.items():
            values[('health.disease_cases', tile.name, disease)] = (
                {**tile_subject, 'disease': disease}, 'people', count)
        private_medical = getattr(tile, 'medical_spending_private_log', ())
        public_medical = getattr(tile, 'medical_spending_public_log', ())
        if private_medical or public_medical:
            private_cost = float(private_medical[-1]) if private_medical else 0.0
            public_cost = float(public_medical[-1]) if public_medical else 0.0
            values[('health.medical_spending', tile.name)] = (
                tile_subject, 'local_currency', private_cost + public_cost)
        for metric_id, field, unit in (
                ('health.untreated_cases', 'untreated_cases_log', 'cases'),
                ('health.fatalities', 'disease_fatalities_log', 'people')):
            history = getattr(tile, field, ())
            if history:
                values[(metric_id, tile.name)] = (
                    tile_subject, unit, float(history[-1]))
        for metric_id, field in (
                ('finance.rent_collected', 'rent_collected_log'),
                ('finance.rent_arrears', 'rent_arrears_log')):
            history = getattr(tile, field, ())
            if history:
                values[(metric_id, tile.name)] = (
                    tile_subject, 'local_currency', float(history[-1]))
        for project in getattr(tile, 'construction_projects', []):
            if getattr(project, 'status', '') in ('completed', 'cancelled'):
                continue
            project_subject = {**tile_subject, 'project_id': project.project_id}
            values[('construction.progress', tile.name, project.project_id)] = (
                project_subject, 'percent', float(project.progress_pct))
        if getattr(tile, 'gdp_log', None):
            values[('economy.gdp_nominal', tile.name)] = (
                tile_subject, 'local_currency_per_turn', float(tile.gdp_log[-1]))
        if getattr(tile, 'cost_of_living', None) is not None:
            values[('living.cost_of_living', tile.name)] = (
                tile_subject, 'local_currency_per_basket', float(tile.cost_of_living))
    for nation in nations:
        subject = {'type': 'nation', 'id': nation.name}
        values[('finance.treasury', nation.name)] = (
            subject, nation.currency, float(nation.treasury()['total']))
        values[('politics.legitimacy', nation.name)] = (
            subject, 'ratio', float(nation.legitimacy))
        members = list(nation.tiles)
        values[('people.population', nation.name)] = (
            subject, 'people', sum(tile.total_population[-1]
                                   if getattr(tile, 'total_population', None) else len(tile.agents)
                                   for tile in members))
        values[('people.deaths', nation.name)] = (
            subject, 'people_per_turn',
            sum(int(getattr(tile, 'deaths_this_turn', 0)) for tile in members))
        values[('people.births', nation.name)] = (
            subject, 'people_per_turn',
            sum(int(getattr(tile, 'births_this_turn', 0)) for tile in members))
        values[('people.residents', nation.name)] = (
            subject, 'people',
            sum(values[('people.residents', tile.name)][2] for tile in members))
        professions = {key[2] for key in values
                       if key[0] == 'people.profession_population'
                       and key[1] in {tile.name for tile in members}}
        for profession_name in professions:
            values[('people.profession_population', nation.name, profession_name)] = (
                {**subject, 'profession': profession_name}, 'people',
                sum(values.get(('people.profession_population', tile.name,
                                profession_name), (None, 'people', 0))[2]
                    for tile in members))
        values[('economy.gdp_nominal', nation.name)] = (
            subject, nation.currency + '_per_turn',
            sum(tile.gdp_log[-1] if getattr(tile, 'gdp_log', None) else 0.0
                for tile in members))
        values[('politics.protest_energy', nation.name)] = (
            subject, 'mean_score',
            sum(tile.protest_energy_log[-1] if getattr(tile, 'protest_energy_log', None)
                else 0.0 for tile in members) / max(1, len(members)))
        values[('living.cost_of_living', nation.name)] = (
            subject, 'mean_local_currency_per_basket',
            sum(tile.cost_of_living for tile in members) / max(1, len(members))
            if members else 1.0)
        national_goods = sorted(
            {good for tile in members for good, recipe in tile.recipes.items()
             if isinstance(good, Goods) and recipe is not None
             and 'price' in recipe}, key=lambda good: good.value)
        for good in national_goods:
            covered_prices = [float(tile.recipes[good]['price']) for tile in members
                              if good in tile.recipes
                              and tile.recipes[good] is not None
                              and 'price' in tile.recipes[good]]
            if not covered_prices:
                continue
            values[('goods.national_reference_price', nation.name, good.name)] = (
                {**subject, 'good': good.name},
                'mean_local_currency_per_unit',
                sum(covered_prices) / len(covered_prices))
        food_history_values = [
            float(tile.recipes[Goods.food]['price'])
            if Goods.food in tile.recipes and tile.recipes[Goods.food] is not None
            and 'price' in tile.recipes[Goods.food] else 0.0
            for tile in members]
        values[('goods.national_food_price', nation.name)] = (
            {**subject, 'good': Goods.food.name},
            'mean_local_currency_per_unit',
            sum(food_history_values) / len(members) if members else 1.0)
    return values


def gini_metric_evidence(tile, good, turn, before, after):
    """Replay the existing 10-turn cash-Gini refresh or its held-value branch."""
    members = (sorted(
        ({'agent_id': str(agent.id), 'cash': float(agent.cash)}
         for agent in getattr(tile, 'agents', ())
         if not getattr(agent, 'is_trader', False)
         and getattr(agent, 'output', None) == good),
        key=lambda row: (row['cash'], row['agent_id']))
        if good != Goods.gov else [])
    cash_values = [row['cash'] for row in members]
    count = len(cash_values)
    total_cash = sum(cash_values)
    weighted_cash = sum((index + 1) * cash
                        for index, cash in enumerate(cash_values))
    refresh_turn = int(turn) % 10 == 0
    if refresh_turn:
        replay = ((2.0 * weighted_cash) / (count * total_cash)
                  - (count + 1.0) / count
                  if count and total_cash > 0 else 0.0)
        matches = replay == float(after)
        return {
            'kind': 'gini_series_calculation',
            'record_class': 'calculation' if matches else 'observation',
            'formula_id': 'gini.cash_by_output.v1',
            'confidence': 'exact' if matches else 'unknown',
            'explanation_status': ('recomputed_from_cash_holdings' if matches
                                   else 'replay_mismatch'),
            'inputs': {'refresh_interval_turns': 10,
                       'recomputed_this_turn': True,
                       'output_good': good.name,
                       'member_count': count,
                       'members_sorted_by_cash': members,
                       'total_cash': total_cash,
                       'weighted_cash_sum': weighted_cash,
                       'formula_result': replay,
                       'recorded_gini': float(after),
                       'replay_matches': matches}}
    if before is None:
        return {
            'kind': 'gini_series_initial_observation',
            'record_class': 'observation',
            'formula_id': 'gini.initial_log_value.v1',
            'confidence': 'unknown',
            'explanation_status': 'previous_series_value_unavailable',
            'inputs': {'refresh_interval_turns': 10,
                       'recomputed_this_turn': False,
                       'output_good': good.name,
                       'recorded_gini': float(after)}}
    matches = float(before) == float(after)
    return {
        'kind': 'gini_series_calculation',
        'record_class': 'calculation' if matches else 'observation',
        'formula_id': 'gini.retain_previous_value.v1',
        'confidence': 'exact' if matches else 'unknown',
        'explanation_status': ('held_between_refreshes' if matches
                               else 'unexpected_change_between_refreshes'),
        'inputs': {'refresh_interval_turns': 10,
                   'recomputed_this_turn': False,
                   'output_good': good.name,
                   'previous_gini': float(before),
                   'recorded_gini': float(after),
                   'replay_matches': matches}}


def record(server):
    current = sample(server.tiles, server.nations)
    previous = getattr(server, '_trace_previous', {})
    previous_nation_membership = getattr(
        server, '_trace_previous_nation_membership', {})
    previous_tile_currencies = getattr(
        server, '_trace_previous_tile_currencies', {})
    previous_nation_currencies = getattr(
        server, '_trace_previous_nation_currencies', {})
    current_nation_membership = {
        nation.name: [tile.name for tile in nation.tiles]
        for nation in server.nations}
    current_tile_currencies = {
        tile.name: getattr(tile, 'home_currency', None) for tile in server.tiles}
    # Keep zero-valued profession keys in the internal baseline so a later
    # return to a profession has a real before value, without snapshotting
    # unchanged zero categories every turn.
    for key, (subject, unit, _before) in previous.items():
        if key[0] == 'people.profession_population' and key not in current:
            current[key] = (subject, unit, 0)
    current_people = resident_census(server.tiles)
    current_roles = entity_role_census(server.tiles)
    previous_people = getattr(server, '_trace_previous_people', None)
    previous_roles = getattr(server, '_trace_previous_roles', {})
    clock = getattr(server.tiles[0], '_collective_trace_clock', None) if server.tiles else None
    if clock is not None:
        clock['phase'] = 'snapshot'
        if previous_people is not None:
            for bridge in resident_population_bridges(
                    previous_people, current_people, previous_roles, server.tiles,
                    clock.get('turn', 0),
                    getattr(server.run_trace, '_person_flow_events', {})):
                server.run_trace.emit(
                    clock, kind='resident_population_bridge', record_class='audit',
                    phase='snapshot',
                    subject={'type': bridge['scope'], 'id': bridge['id']},
                    metric_id='people.residents', unit='people',
                    before=bridge['before'], after=bridge['after'],
                    formula_id='population.resident_census_bridge.v1',
                    inputs=bridge['inputs'],
                    cause_event_ids=bridge['cause_event_ids'],
                    confidence=('exact' if bridge['inputs']['explanation_complete']
                                else 'unknown'),
                    explanation_status=(
                        'flows_reconciled'
                        if bridge['inputs']['explanation_complete'] else
                        'unknown_exit_present'
                        if bridge['inputs']['reconciled'] else
                        'unexplained_population_residual'))
        for tile in server.tiles:
            for metric_id, field, formula_id in (
                    ('people.births', 'births_this_turn', 'people.registered_births.v1'),
                    ('people.deaths', 'deaths_this_turn', 'people.registered_deaths.v1')):
                server.run_trace.emit(
                    clock, kind='person_event_count', record_class='calculation',
                    phase='snapshot', subject={'type': 'tile', 'id': tile.name},
                    metric_id=metric_id, unit='people_per_turn',
                    after=int(getattr(tile, field, 0)), formula_id=formula_id,
                    inputs={'deaths_by_cause': getattr(tile, 'deaths_by_cause_this_turn', {})}
                    if metric_id == 'people.deaths' else {})
            server.run_trace.emit(
                clock, kind='living_person_count', record_class='calculation',
                phase='snapshot', subject={'type': 'tile', 'id': tile.name},
                metric_id='people.residents', unit='people',
                after=current[('people.residents', tile.name)][2],
                formula_id='people.living_nonentity_agents.v1')
        for nation in server.nations:
            members = [tile.name for tile in nation.tiles]
            treasury = nation.treasury()
            old_treasury = previous.get(('finance.treasury', nation.name))
            if old_treasury is not None:
                actual_delta = treasury['total'] - old_treasury[2]
                flows = server.run_trace._treasury_flows.get(nation.name, [])
                known_delta = sum(flow['amount'] for flow in flows)
                by_kind = {}
                for flow in flows:
                    by_kind[flow['kind']] = by_kind.get(flow['kind'], 0.0) + flow['amount']
                server.run_trace.emit(clock, kind='treasury_reconciliation',
                                      record_class='audit', phase='snapshot',
                                      subject={'type': 'nation', 'id': nation.name},
                                      metric_id='finance.treasury', unit=nation.currency,
                                      before=old_treasury[2], after=treasury['total'],
                                      confidence='exact' if abs(actual_delta - known_delta) < 1e-8
                                      else 'unknown',
                                      inputs={'known_flow_total': known_delta,
                                              'unattributed_residual': actual_delta - known_delta,
                                              'flow_totals_by_kind': by_kind},
                                      cause_event_ids=[flow['event_id'] for flow in flows])
            server.run_trace.emit(clock, kind='treasury_components',
                                  record_class='observation', phase='snapshot',
                                  subject={'type': 'nation', 'id': nation.name},
                                  metric_id='finance.treasury', unit=nation.currency,
                                  after=treasury['total'],
                                  inputs={'sovereign_cash': treasury['sovereign_cash'],
                                          'provincial_cash': treasury['provincial_cash'],
                                          'municipal_cash': treasury['municipal_cash'],
                                          'cash_total': treasury['cash'],
                                          'deposits': treasury['deposits'],
                                          'member_tiles': members})
            for metric_id, unit, values_by_tile, reducer in (
                    ('people.population', 'people',
                     [current[('people.population', tile)][2] for tile in members], 'sum'),
                    ('people.deaths', 'people_per_turn',
                     [current[('people.deaths', tile)][2] for tile in members], 'sum'),
                    ('people.births', 'people_per_turn',
                     [current[('people.births', tile)][2] for tile in members], 'sum'),
                    ('people.residents', 'people',
                     [current[('people.residents', tile)][2] for tile in members], 'sum'),
                    ('economy.gdp_nominal', nation.currency + '_per_turn',
                     [current.get(('economy.gdp_nominal', tile), (None, None, 0.0))[2]
                      for tile in members], 'sum'),
                    ('politics.protest_energy', 'mean_score',
                     [current.get(('politics.protest_energy', tile), (None, None, 0.0))[2]
                      for tile in members], 'mean'),
                    ('living.cost_of_living', 'mean_local_currency_per_basket',
                     [current.get(('living.cost_of_living', tile), (None, None, 1.0))[2]
                      for tile in members], 'mean')):
                key = (metric_id, nation.name)
                if key not in current:
                    continue
                aggregate_inputs = {
                    'member_tiles': members,
                    'member_values': values_by_tile,
                    'denominator': max(1, len(members)) if reducer == 'mean' else None}
                if reducer == 'mean' and not values_by_tile:
                    aggregate_inputs['empty_value'] = current[key][2]
                aggregate_before = previous.get(key)
                aggregate_causes = []
                if metric_id == 'people.deaths':
                    by_cause = {}
                    for tile in nation.tiles:
                        for cause, count in getattr(tile, 'deaths_by_cause_this_turn', {}).items():
                            by_cause[cause] = by_cause.get(cause, 0) + count
                    aggregate_inputs['deaths_by_cause'] = by_cause
                elif metric_id == 'living.cost_of_living':
                    member_records = []
                    for tile_name, value in zip(members, values_by_tile):
                        tile = next(tile for tile in nation.tiles
                                    if tile.name == tile_name)
                        calculation_event_id = server.run_trace.turn_living_cost_event_id(
                            tile_name)
                        member_records.append({
                            'tile_id': tile_name,
                            'owner_nation_at_snapshot': getattr(
                                getattr(tile, 'owner_nation', None), 'name', None),
                            'local_currency': getattr(tile, 'home_currency', None),
                            'local_basket_value': value,
                            'basket_calculation_event_id': calculation_event_id})
                        if calculation_event_id is not None:
                            aggregate_causes.append(calculation_event_id)
                    aggregate_inputs.update({
                        'territory_membership': member_records,
                        'member_currencies': [row['local_currency']
                                              for row in member_records],
                        'target_nation_currency': getattr(nation, 'currency', None),
                        'currency_conversion_applied': False,
                        'currency_semantics': 'unconverted_mean_of_local_currency_baskets',
                        'unconverted_mixed_currency': len({
                            row['local_currency'] for row in member_records
                            if row['local_currency'] is not None}) > 1,
                        'basket_components': [
                            {'good': 'food', 'weight': 4.0},
                            {'good': 'wood', 'weight': 1.0},
                            {'good': 'furniture', 'weight': 0.25}],
                        'product_mix_changed': False,
                        'coverage': {'member_tiles': len(members),
                                     'tiles_with_basket': len(member_records),
                                     'tiles_with_current_calculation': sum(
                                         row['basket_calculation_event_id'] is not None
                                         for row in member_records),
                                     'tiles_without_current_calculation': [
                                         row['tile_id'] for row in member_records
                                         if row['basket_calculation_event_id'] is None]},
                        'membership_turn': clock.get('turn', 0)})
                    aggregate_inputs.update(_territorial_mix_evidence(
                        metric_id, nation.name, None, members,
                        previous_nation_membership.get(nation.name, ()),
                        previous, current, previous_tile_currencies,
                        current_tile_currencies,
                        previous_nation_currencies.get(nation.name),
                        getattr(nation, 'currency', None)))
                server.run_trace.emit(clock, kind='national_aggregate',
                                      record_class='calculation', phase='snapshot',
                                      subject={'type': 'nation', 'id': nation.name},
                                      metric_id=metric_id, unit=unit,
                                      before=(aggregate_before[2]
                                              if metric_id == 'living.cost_of_living'
                                              and aggregate_before is not None else None),
                                      after=current[key][2],
                                      formula_id=f'aggregate.{reducer}.v1',
                                      inputs=aggregate_inputs,
                                      cause_event_ids=aggregate_causes or None)
            for key, (subject, unit, after) in current.items():
                if (key[0] != 'goods.national_reference_price'
                        or subject.get('type') != 'nation'
                        or subject.get('id') != nation.name):
                    continue
                good_name = subject['good']
                member_records = []
                uncovered_tiles = []
                for tile_name in members:
                    tile = next(tile for tile in nation.tiles
                                if tile.name == tile_name)
                    tile_price_key = ('goods.price', tile_name, good_name)
                    tile_price = current.get(tile_price_key)
                    if tile_price is None:
                        uncovered_tiles.append(tile_name)
                        continue
                    source_event_id = server.run_trace.latest_reference_price_event_id(
                        tile_name, good_name)
                    member_records.append({
                        'tile_id': tile_name,
                        'owner_nation_at_snapshot': getattr(
                            getattr(tile, 'owner_nation', None), 'name', None),
                        'local_currency': getattr(tile, 'home_currency', None),
                        'reference_price': tile_price[2],
                        'source_price_event_id': source_event_id,
                        'source_price_link_status': (
                            'linked' if source_event_id is not None
                            else 'no_prior_price_record')})
                covered_tiles = [row['tile_id'] for row in member_records]
                member_values = [row['reference_price'] for row in member_records]
                source_event_ids = [row['source_price_event_id']
                                    for row in member_records
                                    if row['source_price_event_id'] is not None]
                prior_covered_tiles = [tile_name for tile_name in
                                       previous_nation_membership.get(nation.name, ())
                                       if ('goods.price', tile_name, good_name) in previous]
                aggregate_inputs = {
                    'good': good_name,
                    'member_tiles': members,
                    'territory_membership': [
                        {'tile_id': tile.name,
                         'owner_nation_at_snapshot': getattr(
                             getattr(tile, 'owner_nation', None), 'name', None),
                         'local_currency': getattr(tile, 'home_currency', None)}
                        for tile in nation.tiles],
                    'covered_member_tiles': covered_tiles,
                    'previous_covered_member_tiles': prior_covered_tiles,
                    'uncovered_member_tiles': uncovered_tiles,
                    'member_price_records': member_records,
                    'member_values': member_values,
                    'denominator': len(member_values),
                    'coverage_count': len(member_values),
                    'territory_count': len(members),
                    'coverage_share': len(member_values) / max(1, len(members)),
                    'member_currencies': [row['local_currency']
                                          for row in member_records],
                    'target_nation_currency': getattr(nation, 'currency', None),
                    'currency_conversion_applied': False,
                    'currency_semantics': 'unconverted_mean_of_local_reference_prices',
                    'unconverted_mixed_currency': len({
                        row['local_currency'] for row in member_records
                        if row['local_currency'] is not None}) > 1,
                    'price_basis': 'displayed_recipe_reference',
                    'membership_turn': clock.get('turn', 0)}
                aggregate_inputs.update(_territorial_mix_evidence(
                    'goods.national_reference_price', nation.name, good_name,
                    covered_tiles, prior_covered_tiles,
                    previous, current, previous_tile_currencies,
                    current_tile_currencies,
                    previous_nation_currencies.get(nation.name),
                    getattr(nation, 'currency', None)))
                aggregate_inputs['territory_membership_changed'] = (
                    set(members) != set(previous_nation_membership.get(
                        nation.name, ())))
                aggregate_inputs['price_coverage_changed'] = (
                    set(covered_tiles) != set(prior_covered_tiles))
                server.run_trace.emit(
                    clock, kind='national_reference_price_aggregate',
                    record_class='calculation', phase='snapshot',
                    subject=subject, metric_id='goods.national_reference_price',
                    unit=unit,
                    before=(previous[key][2] if key in previous else None),
                    after=after, formula_id='aggregate.mean.v1',
                    inputs=aggregate_inputs,
                    cause_event_ids=source_event_ids or None)
            food_history_key = ('goods.national_food_price', nation.name)
            if food_history_key in current:
                food_records = []
                food_contributions = []
                food_source_event_ids = []
                for tile in nation.tiles:
                    recipe = tile.recipes.get(Goods.food)
                    has_price = recipe is not None and 'price' in recipe
                    reference_price = (float(recipe['price']) if has_price else None)
                    contribution = reference_price if reference_price is not None else 0.0
                    source_event_id = (server.run_trace.latest_reference_price_event_id(
                        tile.name, Goods.food.name) if has_price else None)
                    food_records.append({
                        'tile_id': tile.name,
                        'owner_nation_at_snapshot': getattr(
                            getattr(tile, 'owner_nation', None), 'name', None),
                        'local_currency': getattr(tile, 'home_currency', None),
                        'reference_price': reference_price,
                        'legacy_mean_contribution': contribution,
                        'source_price_event_id': source_event_id,
                        'source_price_link_status': (
                            'linked' if source_event_id is not None
                            else 'no_prior_price_record')})
                    food_contributions.append(contribution)
                    if source_event_id is not None:
                        food_source_event_ids.append(source_event_id)
                denominator = max(1, len(members))
                food_inputs = {
                    'good': Goods.food.name,
                    'history_field': 'sim_server._nation_history.food_price',
                    'member_tiles': members,
                    'previous_member_tiles': previous_nation_membership.get(
                        nation.name, []),
                    'current_member_tiles': members,
                    'added_member_tiles': sorted(
                        set(members) - set(previous_nation_membership.get(
                            nation.name, ()))),
                    'removed_member_tiles': sorted(
                        set(previous_nation_membership.get(nation.name, ()))
                        - set(members)),
                    'membership_changed': set(members) != set(
                        previous_nation_membership.get(nation.name, ())),
                    'territory_membership': food_records,
                    'member_price_records': food_records,
                    'previous_member_price_records': [
                        {'tile_id': tile_name,
                         'reference_price': (
                             previous[('goods.price', tile_name, Goods.food.name)][2]
                             if ('goods.price', tile_name, Goods.food.name) in previous
                             else None)}
                        for tile_name in previous_nation_membership.get(
                            nation.name, ())],
                    'member_values': food_contributions,
                    'denominator': denominator,
                    'empty_value': 1.0 if not members else 0.0,
                    'coverage_count': sum(
                        row['reference_price'] is not None for row in food_records),
                    'territory_count': len(members),
                    'coverage_share': sum(
                        row['reference_price'] is not None for row in food_records)
                        / max(1, len(members)),
                    'unpriced_member_tiles': [row['tile_id'] for row in food_records
                                              if row['reference_price'] is None],
                    'missing_recipe_contribution_policy': 'zero_in_legacy_display_mean',
                    'no_territory_fallback': 1.0 if not members else None,
                    'interpretation_status': (
                        'empty_territory_history_fallback'
                        if not members else 'legacy_food_price_mean'),
                    'member_currencies': [row['local_currency']
                                          for row in food_records],
                    'target_nation_currency': getattr(nation, 'currency', None),
                    'currency_conversion_applied': False,
                    'currency_semantics': 'unconverted_mean_of_local_reference_prices',
                    'unconverted_mixed_currency': len({
                        row['local_currency'] for row in food_records
                        if row['local_currency'] is not None}) > 1,
                    'membership_turn': clock.get('turn', 0)}
                food_inputs.update(_territorial_mix_evidence(
                    'goods.national_food_price', nation.name, Goods.food.name,
                    members, previous_nation_membership.get(nation.name, ()),
                    previous, current, previous_tile_currencies,
                    current_tile_currencies,
                    previous_nation_currencies.get(nation.name),
                    getattr(nation, 'currency', None)))
                server.run_trace.emit(
                    clock, kind='national_food_price_history_aggregate',
                    record_class='calculation', phase='snapshot',
                    subject=current[food_history_key][0],
                    metric_id='goods.national_food_price',
                    unit=current[food_history_key][1],
                    before=(previous[food_history_key][2]
                            if food_history_key in previous else None),
                    after=current[food_history_key][2],
                    formula_id='aggregate.mean.v1', inputs=food_inputs,
                    cause_event_ids=food_source_event_ids or None)
            for key, (subject, unit, after) in current.items():
                if (key[0] != 'people.profession_population'
                        or subject.get('type') != 'nation'
                        or subject.get('id') != nation.name):
                    continue
                profession_name = subject['profession']
                member_values = [current.get(
                    ('people.profession_population', tile, profession_name),
                    (None, 'people', 0.0))[2] for tile in members]
                prior_member_values = [previous.get(
                    ('people.profession_population', tile, profession_name),
                    (None, 'people', 0.0))[2] for tile in members]
                if member_values == prior_member_values:
                    continue
                server.run_trace.emit(
                    clock, kind='national_aggregate',
                    record_class='calculation', phase='snapshot',
                    subject=subject, metric_id='people.profession_population',
                    unit=unit, after=after,
                    formula_id='aggregate.sum.v1',
                    inputs={'member_tiles': members,
                            'member_values': member_values,
                            'profession': profession_name,
                            'denominator': None})
        for key, (subject, unit, after) in current.items():
            before = previous[key][2] if key in previous else None
            if key[0] == 'people.profession_population' and before == after:
                continue
            if key[0] == 'economy.gini':
                tile = next((row for row in server.tiles
                             if row.name == subject['id']), None)
                good = next((candidate for candidate in getattr(tile, 'gini_log', {})
                             if getattr(candidate, 'name', None) == subject.get('good')),
                            None)
                if tile is not None and good is not None:
                    evidence = gini_metric_evidence(
                        tile, good, clock.get('turn', 0), before, after)
                    server.run_trace.emit(
                        clock, subject=subject, metric_id=key[0], unit=unit,
                        before=before, after=after, **evidence)
            if key[0] == 'goods.price':
                server.run_trace.price_bridge(clock, subject=subject,
                                              before=before, after=after, unit=unit)
            server.run_trace.snapshot(clock, subject=subject, metric_id=key[0],
                                      unit=unit, before=before, after=after)
    server._trace_previous = current
    server._trace_previous_people = current_people
    server._trace_previous_roles = current_roles
    server._trace_previous_nation_membership = current_nation_membership
    server._trace_previous_tile_currencies = current_tile_currencies
    server._trace_previous_nation_currencies = {
        nation.name: getattr(nation, 'currency', None)
        for nation in server.nations}

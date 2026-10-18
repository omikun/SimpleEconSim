"""Read-only end-of-turn observations and explicit provenance gaps."""

from goods import Goods


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
        values[('people.population', tile.name)] = (
            tile_subject, 'people', tile.total_population[-1]
            if getattr(tile, 'total_population', None) else len(tile.agents))
        values[('people.deaths', tile.name)] = (
            tile_subject, 'people_per_turn', int(getattr(tile, 'deaths_this_turn', 0)))
        values[('people.births', tile.name)] = (
            tile_subject, 'people_per_turn', int(getattr(tile, 'births_this_turn', 0)))
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
    return values


def record(server):
    current = sample(server.tiles, server.nations)
    previous = getattr(server, '_trace_previous', {})
    clock = getattr(server.tiles[0], '_collective_trace_clock', None) if server.tiles else None
    if clock is not None:
        clock['phase'] = 'snapshot'
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
                if metric_id == 'people.deaths':
                    by_cause = {}
                    for tile in nation.tiles:
                        for cause, count in getattr(tile, 'deaths_by_cause_this_turn', {}).items():
                            by_cause[cause] = by_cause.get(cause, 0) + count
                    aggregate_inputs['deaths_by_cause'] = by_cause
                server.run_trace.emit(clock, kind='national_aggregate',
                                      record_class='calculation', phase='snapshot',
                                      subject={'type': 'nation', 'id': nation.name},
                                      metric_id=metric_id, unit=unit,
                                      after=current[key][2],
                                      formula_id=f'aggregate.{reducer}.v1',
                                      inputs=aggregate_inputs)
        for key, (subject, unit, after) in current.items():
            before = previous[key][2] if key in previous else None
            if key[0] == 'goods.price':
                server.run_trace.price_bridge(clock, subject=subject,
                                              before=before, after=after, unit=unit)
            server.run_trace.snapshot(clock, subject=subject, metric_id=key[0],
                                      unit=unit, before=before, after=after)
    server._trace_previous = current

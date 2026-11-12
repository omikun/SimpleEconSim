"""Region population and economy telemetry sampling."""

from statistics import mean
from typing import Any

from goods import Goods
from micro.region.helpers import compute_gini
import region_logistics as _logistics


def _trace_profession_population(region: Any, by_output: dict) -> None:
    """Record changing members of the legacy profession-population measure."""
    run_trace = getattr(region, '_run_trace', None)
    if run_trace is None:
        return
    previous = getattr(region, '_trace_profession_members', None)
    current = {
        getattr(group, 'name', str(group)): {
            getattr(agent, 'id', None): agent for agent in agents}
        for group, agents in by_output.items()
    }
    if previous is not None:
        old_profession = {agent_id: name for name, members in previous.items()
                          for agent_id in members}
        new_profession = {agent_id: name for name, members in current.items()
                          for agent_id in members}
        flow_events = {}
        flow_events.update(getattr(run_trace, '_previous_person_flow_events', {}))
        flow_events.update(getattr(run_trace, '_person_flow_events', {}))
        for group, members in by_output.items():
            name = getattr(group, 'name', str(group))
            old_members = previous.get(name, {})
            new_members = current.get(name, {})
            removed_ids = old_members.keys() - new_members.keys()
            added_ids = new_members.keys() - old_members.keys()
            if not removed_ids and not added_ids:
                continue

            changes = []
            cause_ids = set()
            for person_id in sorted(removed_ids | added_ids, key=str):
                agent = new_members.get(person_id) or old_members.get(person_id)
                changes.append({
                    'agent_id': str(person_id),
                    'from_profession': old_profession.get(person_id),
                    'to_profession': new_profession.get(person_id),
                    'role': ('corporation' if getattr(agent, 'is_corporation', False)
                             else 'government' if getattr(agent, 'is_government', False)
                             else 'trader' if getattr(agent, 'is_trader', False)
                             else 'person'),
                    'alive': bool(getattr(agent, 'alive', True)),
                    'death_cause': getattr(agent, 'death_cause', None),
                    'region': getattr(agent, 'region', None),
                    'last_migration_turn': getattr(agent, 'last_migration_turn', None),
                })
                for event_id in flow_events.get(str(person_id), ()):
                    cause_ids.add(event_id)

            history = getattr(region, 'population_log', {}).get(group, ())
            before = history[-1] if history else len(old_members)
            after = len(members)
            from run_trace import emit
            emit(region, kind='profession_population_count', record_class='calculation',
                 phase='local',
                 subject={'type': 'tile', 'id': region.name, 'profession': name},
                 metric_id='people.profession_population', unit='people',
                 before=int(before), after=int(after),
                 formula_id='population.profession_membership_count.v1',
                 inputs={'profession': name,
                         'counting_rule': ('all entries in trader_agents'
                                           if name == 'trader' else
                                           'non-trader agents whose output equals this '
                                           'profession; government output excluded'),
                         'added_agent_ids': sorted(map(str, added_ids)),
                         'removed_agent_ids': sorted(map(str, removed_ids)),
                         'membership_changes': changes,
                         'member_count': int(after),
                         'previous_membership_available': True},
                 cause_event_ids=sorted(cause_ids))
    region._trace_profession_members = current


def log_metrics(region: Any, t: int):
    agents = region.agents
    by_output = {g: [] for g in region.goods}
    by_output['trader'] = []
    food_agents = []
    total_cash_by_output = {g: 0.0 for g in region.goods}
    total_inv_by_output = {g: 0.0 for g in region.goods if g != Goods.gov}
    total_inv_trader = 0.0

    for a in agents:
        if a.is_trader or not a.alive:
            continue
        if a.is_corporation:
            if a.output in total_cash_by_output:
                total_cash_by_output[a.output] += a.cash
            if a.output in total_inv_by_output:
                total_inv_by_output[a.output] += a.inv_get(a.output, 0)
            continue
        if a.output == Goods.food:
            food_agents.append(a)
            by_output[Goods.food].append(a)
            total_cash_by_output[Goods.food] += a.cash
            if Goods.food != Goods.gov:
                total_inv_by_output[Goods.food] += a.inv_get(Goods.food, 0)
        elif a.output != Goods.gov and a.output in by_output:
            o = a.output
            by_output[o].append(a)
            total_cash_by_output[o] += a.cash
            if o != Goods.gov:
                total_inv_by_output[o] += a.inv_get(o, 0)

    trader_agents = region.trader_agents
    by_output['trader'] = trader_agents
    for a in trader_agents:
        total_inv_trader += a.inv_get(Goods.food, 0) + a.inv_get(Goods.wood, 0) + a.inv_get(Goods.furniture, 0)

    _trace_profession_population(region, by_output)

    compute_gini_this_turn = (t % 10 == 0)
    from gini_trace import record_sample as record_gini_sample

    for g in region.goods:
        grp = by_output[g]
        pop = len(grp)
        region.population_log[g].append(pop)
        region.cash_log[g].append(total_cash_by_output.get(g, 0.0))
        if compute_gini_this_turn:
            region.gini_log[g].append(compute_gini(grp, g))
        else:
            region.gini_log[g].append(region.gini_log[g][-1] if region.gini_log[g] else 0)
        record_gini_sample(region,grp,g,t,region.gini_log[g])
        if g != Goods.gov:
            region.inventory_log[g].append(total_inv_by_output.get(g, 0.0))
            from run_trace import emit
            emit(region, kind='producer_inventory_total', record_class='calculation',
                 subject={'type': 'tile', 'id': region.name, 'good': g.name},
                 metric_id='goods.producer_inventory', unit='units',
                 after=region.inventory_log[g][-1],
                 formula_id='inventory.sum_producer_holdings.v1',
                 inputs={'holdings': [{'agent_id': a.id, 'units': a.inv_get(g, 0)}
                                     for a in agents if a.alive and not a.is_trader and a.output == g]})
            non_prod = [a.inv_get(g, 0) for a in agents if a.output != g and not a.is_trader]
            region.per_capita_inventory[g].append(mean(non_prod) if non_prod else 0)
            region.price_log[g].append(region.recipes[g]['price'])

    tr_len = len(trader_agents)
    region.population_log['trader'].append(tr_len)
    region.cash_log['trader'].append(sum(a.cash for a in trader_agents))
    if compute_gini_this_turn:
        region.gini_log['trader'].append(compute_gini(trader_agents, Goods.food))
    else:
        region.gini_log['trader'].append(region.gini_log['trader'][-1] if region.gini_log['trader'] else 0)
    record_gini_sample(region,trader_agents,Goods.food,t,region.gini_log['trader'],series_name='trader')
    region.hungry_log['trader'].append(sum(1 for a in trader_agents if a.hungry_steps > 0))
    region.inventory_log['trader'].append(total_inv_trader)
    non_trader = [a.inv_get(Goods.food, 0) for a in trader_agents if a.output != Goods.food]
    region.per_capita_inventory['trader'].append(mean(non_trader) if non_trader else 0)
    region.production_log['trader'].append(0)
    region.gdp_by_profession_log['trader'].append(0)

    trader_cash_by_agent = [{'agent_id': int(agent.id),
                             'cash': float(agent.cash)}
                            for agent in trader_agents]
    trader_cash_total = sum(row['cash'] for row in trader_cash_by_agent)
    region.trader_cash_log.append(trader_cash_total)
    from run_trace import emit
    emit(region, kind='trader_cash_total_calculation',
         record_class='calculation', phase='demographics',
         subject={'type': 'tile', 'id': region.name},
         metric_id='trade.trader_cash',
         unit=getattr(region, 'home_currency', None) or 'local_currency',
         before=(region.trader_cash_log[-2]
                 if len(region.trader_cash_log) > 1 else None),
         after=trader_cash_total,
         formula_id='trade.trader_cash_sum_wallets.v1',
         inputs={'traders': trader_cash_by_agent,
                 'trader_count': len(trader_cash_by_agent),
                 'currency': getattr(region, 'home_currency', None)
                 or 'local_currency'})
    hunger_groups = {}
    for good in (Goods.food, Goods.wood, Goods.furniture):
        history = region.hungry_log.get(good, ())
        hunger_groups[good.name] = int(history[-1]) if history else 0
    trader_hunger = region.hungry_log.get('trader', ())
    hunger_groups['trader'] = int(trader_hunger[-1]) if trader_hunger else 0
    emit(region, kind='population_hunger_count_calculation',
         record_class='calculation', phase='demographics',
         subject={'type': 'tile', 'id': region.name},
         metric_id='people.hungry', unit='people',
         after=sum(hunger_groups.values()),
         formula_id='population.sum_hungry_output_groups.v1',
         inputs={'group_counts': hunger_groups,
                 'included_groups': list(hunger_groups),
                 'counting_rule': 'sum disjoint producer-output and trader cohorts',
                 'source': 'Live hunger histories for this turn'})
    pipeline_goods = [Goods.food, Goods.wood, Goods.furniture]
    pipeline_routes = []
    pipeline_shipments = []
    pipeline_qty = 0
    for route in _logistics.all_routes(region):
        goods_totals = {good.name: route.in_transit_total(good)
                        for good in pipeline_goods}
        route_total = sum(goods_totals.values())
        pipeline_qty += route_total
        pipeline_routes.append({
            'route': str(route.name), 'destination': route.dst.name,
            'goods_units': goods_totals, 'total_goods_units': route_total})
        for entry in getattr(route, 'in_transit', ()):
            if entry[1] not in pipeline_goods:
                continue
            shipment_id = entry[5] if len(entry) > 5 else None
            pipeline_shipments.append({
                'shipment_id': shipment_id,
                'trader_id': int(getattr(entry[0], 'id', -1)),
                'good': entry[1].name, 'quantity': entry[2],
                'turns_remaining': int(entry[3]), 'route': str(route.name)})
    region.pipeline_depth_log.append(pipeline_qty)
    pipeline_causes = []
    shipment_event = getattr(getattr(region, '_run_trace', None),
                             'shipment_event_id', None)
    if callable(shipment_event):
        for shipment in pipeline_shipments:
            event_id = shipment_event(shipment['shipment_id'], 'departure')
            shipment['departure_event_id'] = event_id
            shipment['departure_trace_status'] = (
                'linked' if event_id is not None else 'no_departure_record')
            if event_id is not None:
                pipeline_causes.append(event_id)
    emit(region, kind='trade_pipeline_depth_calculation',
         record_class='calculation', phase='demographics',
         subject={'type': 'tile', 'id': region.name},
         metric_id='trade.pipeline_depth', unit='goods_units',
         before=(region.pipeline_depth_log[-2]
                 if len(region.pipeline_depth_log) > 1 else None),
         after=pipeline_qty,
         formula_id='trade.pipeline_depth_in_transit_goods.v1',
         inputs={'routes': pipeline_routes,
                 'shipments': pipeline_shipments,
                 'included_goods': [good.name for good in pipeline_goods],
                 'included_state': 'in_transit',
                 'excluded_states': ['pending', 'parked'],
                 'aggregation_rule': 'sum quantities across listed goods and routes'},
         cause_event_ids=pipeline_causes or None)
    infant_fatalities = getattr(region, 'infant_fatalities_this_turn', 0)
    region.infant_fatalities_log.append(infant_fatalities)
    from run_trace import emit
    emit(region, kind='infant_fatalities_turn_total', record_class='calculation',
         phase='demographics', subject={'type': 'tile', 'id': region.name},
         metric_id='health.infant_fatalities', unit='people_per_turn',
         before=0, after=infant_fatalities,
         formula_id='demographics.infant_fatalities_sum.v1',
         inputs={'deaths_recorded_during_turn': infant_fatalities})
    region.infant_fatalities_this_turn = 0


def log_population_rate(region: Any, turn: int | None = None):
    history = list(getattr(region, 'total_population', ()))
    population_samples = [int(value) for value in history[-10:]]
    baseline = population_samples[0] if len(population_samples) >= 10 else None
    current = population_samples[-1] if population_samples else 0
    if baseline is not None and baseline > 0:
        population_change_pct = (current - baseline) / baseline * 100
        window_status = 'full_window'
    elif baseline == 0:
        population_change_pct = 0
        window_status = 'zero_baseline'
    else:
        population_change_pct = 0
        window_status = 'insufficient_history'
    previous = (region.population_change_rate_log[-1]
                if region.population_change_rate_log else None)
    region.population_change_rate_log.append(population_change_pct)
    from run_trace import emit
    emit(region, kind='population_change_rate_calculation',
         record_class='calculation', phase='demographics',
         subject={'type': 'tile', 'id': region.name},
         metric_id='people.population_change_rate',
         unit='percent_over_sample_window', before=previous,
         after=population_change_pct,
         formula_id='population.rate_from_last_ten_samples.v1',
         inputs={'turn': int(turn if turn is not None else
                             getattr(region, '_last_turn', 0)),
                 'population_samples': population_samples,
                 'sample_count': len(population_samples),
                 'window_sample_count': 10,
                 'baseline_population': baseline,
                 'current_population': current,
                 'window_status': window_status,
                 'population_basis': 'total_population profession-count history',
                 'formula': '(current - baseline) / baseline * 100; zero if fewer than ten samples or baseline is zero'})

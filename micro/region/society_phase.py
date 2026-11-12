"""Tax, labor metrics, demographics, and social class for a region."""
import region_finance as _fin
import social_class as _sclass


def run(region, t, flags, legacy):
    from micro.region.stepper import (audit_cash, record_delta, log_gdp,
                                      sample_effective_workday_cap, live)
    # Tax
    record_delta(region)
    _fin.collect_tax(region, t)
    if len(region.tax_distribution_log) < len(region.rent_collected_log):
        region.tax_distribution_log.append({'total': 0.0, 'municipal': 0.0, 'provincial': 0.0, 'national': 0.0})
        from finance_trace import emit_tax_distribution
        emit_tax_distribution(
            region, turn=t, closing=region.tax_distribution_log[-1],
            reason='no_local_tax_collection_at_nonseat')
    audit_cash(region, t, "tax_done")

    log_gdp(region)

    # Surplus value & labor metrics (P2.1)
    from labor_contract import aggregate_tile_surplus
    surplus_stats = aggregate_tile_surplus(region, turn=t)
    sample_effective_workday_cap(region)
    region.avg_shift_hours_log.append(surplus_stats['avg_shift_hours'])
    region.surplus_value_log.append(surplus_stats['total_surplus_value'])
    region.rate_of_exploitation_log.append(surplus_stats['avg_rate_of_exploitation'])
    from run_trace import emit
    for metric_id, history, value, unit, kind, formula_id, inputs in (
            ('labor.average_shift_hours', region.avg_shift_hours_log,
             surplus_stats['avg_shift_hours'], 'hours',
             'labor_shift_hours_calculation',
             'labor.weighted_average_shift_hours.v1',
             surplus_stats['avg_shift_hours_inputs']),
            ('labor.exploitation_rate', region.rate_of_exploitation_log,
             surplus_stats['avg_rate_of_exploitation'], 'ratio',
             'labor_exploitation_rate_calculation',
             'labor.surplus_over_variable_capital.v1',
             surplus_stats['exploitation_inputs'])):
        emit(region, kind=kind, record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name}, metric_id=metric_id,
             unit=unit,
             before=history[-2] if len(history) > 1 else None,
             after=float(value), formula_id=formula_id, inputs=inputs)

    surplus_inputs = surplus_stats['surplus_inputs']
    surplus_causes = [row['source_event_id']
                      for row in surplus_inputs['firms']
                      if row.get('included_in_current_turn')
                      and row.get('source_event_id') is not None]
    emit(region, kind='labor_surplus_value_calculation',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='labor.surplus_value',
         unit=getattr(region, 'home_currency', None) or 'local_currency',
         before=(region.surplus_value_log[-2]
                 if len(region.surplus_value_log) > 1 else None),
         after=float(surplus_stats['total_surplus_value']),
         formula_id='labor.surplus_value_current_turn.v1',
         inputs=surplus_inputs,
         cause_event_ids=surplus_causes or None)

    if t > 0 and t % 10 == 0:
        _fin.recalculate_multipliers(region)

    # Demographics & Lifecycle
    prior_agents = list(region.agents)
    next_agents = live(region, t, gameplay_flags=flags)
    from agriculture import settle_succession
    settle_succession(region, prior_agents, next_agents)
    surviving_ids = {a.id for a in next_agents}
    for firm in prior_agents:
        if not getattr(firm, 'is_corporation', False):
            continue
        retained = []
        for worker in getattr(firm, 'employees', []):
            if getattr(worker, 'alive', True) and worker.id in surviving_ids:
                retained.append(worker)
            else:
                if getattr(worker, 'employer', None) is firm:
                    worker.employer = None
                agreement = getattr(worker, 'labor_agreement', None)
                if agreement is not None:
                    agreement.active = False
        firm.employees[:] = retained
    from livelihood_access import remove_access
    for departed in prior_agents:
        if not getattr(departed, 'alive', True) and departed.id not in surviving_ids:
            remove_access(region, departed.id)
            for plot in getattr(getattr(region, 'tenure', None), 'plots', []):
                if departed.id in plot.tenant_ids:
                    plot.tenant_ids.remove(departed.id)
    region.agents = next_agents
    from households import rebuild as rebuild_households
    rebuild_households(region, t)
    from food_economy import finish_turn as finish_food_turn
    finish_food_turn(region, t)
    region.trader_agents = [a for a in region.agents if a.is_trader]
    from collective_action import record_essential_needs
    record_essential_needs(region, t)
    audit_cash(region, t, "live_done")

    # Dynamic social class evaluation (P1.4)
    class_dist = _sclass.update_tile_social_classes(region)
    region.social_class_log.append(class_dist)
    from run_trace import emit
    class_groups = {
        'serf': ('serf',),
        'tenant': ('tenant',),
        'worker': ('proletarian',),
        'dispossessed': ('dispossessed',),
        'gentry': ('lord', 'landlord'),
        'artisan': ('petty_bourgeois', 'industrialist'),
    }
    previous_classes = (region.social_class_log[-2]
                        if len(region.social_class_log) > 1 else {})
    for group, members in class_groups.items():
        member_class_counts = {
            name: int(class_dist.get(name, 0)) for name in members}
        count = sum(member_class_counts.values())
        before = sum(int(previous_classes.get(name, 0)) for name in members)
        emit(region, kind='social_class_population_calculation',
             record_class='calculation', phase='local',
             subject={'type': 'tile', 'id': region.name,
                      'class_group': group},
             metric_id='society.class_population', unit='people',
             before=before, after=count,
             formula_id='social_class.group_population.v1',
             inputs={'class_group': group, 'member_classes': list(members),
                     'member_class_counts': member_class_counts,
                     'counting_rule': 'sum living agents assigned to member classes'})

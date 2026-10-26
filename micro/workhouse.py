"""
workhouse.py — Parish Workhouse & Vagrancy Enforcement Engine for Call of Capital.

Implements the English Poor Laws & Workhouse System:
1. New vagrancy arrests require an active law and funded enforcement capacity.
2. Inmates receive bare-subsistence gruel (1 food/turn) provided by the
   municipality (conserved food transfer or market purchase).
3. Inmates perform compulsory hard labor. It is not cash revenue until a buyer
   purchases a real good or service from the municipality.
4. If the municipality suffers a fiscal drought (no food in stock and no cash to buy gruel),
   inmates starve, triggering a Workhouse Bread Riot that damages municipal order
   and escalates popular unrest.
"""
from treasury_trace import begin_public_change, finish_public_change

from goods import Goods


def has_workhouse(region) -> bool:
    """Return True if the region has a completed, active Parish Workhouse."""
    return any(b.name == 'workhouse' for b in getattr(region, 'buildings', []))


def get_workhouse_inmates(region) -> list:
    """Return list of currently confined living workhouse inmates."""
    return [a for a in getattr(region, 'agents', []) if a.alive and getattr(a, 'in_workhouse', False)]


def get_workhouse_census(region) -> dict:
    """Return summary statistics of workhouse confinement on this tile."""
    inmates = get_workhouse_inmates(region)
    return {
        'has_workhouse': has_workhouse(region),
        'inmate_count': len(inmates),
        'inmates': [a.id for a in inmates],
    }


def _record_workhouse_turn(region, turn, *, reason, inmate_ids_before,
                           events, fed_inmate_ids=(), starving_inmate_ids=(),
                           food_needed=0, food_provided=0,
                           forced_labor_hours=0.0, revenue=0.0):
    """Trace the confinement census and noncash work performed this turn."""
    from run_trace import emit

    inmate_ids_after = sorted(a.id for a in get_workhouse_inmates(region))
    resolved_case_ids = sorted({int(case_id) for event in events
                                for case_id in event.get('case_ids', ())})
    affected_ids = set(inmate_ids_before) | set(inmate_ids_after)
    affected_ids.update(fed_inmate_ids)
    affected_ids.update(starving_inmate_ids)
    resolved_case_ids = sorted(set(resolved_case_ids) | {
        int(case.id) for case in getattr(region, 'enforcement_cases', ())
        if case.kind == 'vagrancy' and case.state == 'resolved'
        and int(case.target_person_id) in affected_ids})
    trace = getattr(region, '_run_trace', None)
    cause_event_ids = []
    latest_metric = getattr(trace, 'latest_metric_event_id', None)
    if callable(latest_metric):
        for case_id in resolved_case_ids:
            event_id = latest_metric(
                'labor.enforcement_case',
                {'type': 'labor_case', 'id': case_id,
                 'tile': getattr(region, 'name', 'unknown')})
            if event_id is not None:
                cause_event_ids.append(event_id)
        for person_id in sorted(affected_ids):
            event_id = latest_metric(
                'labor.status_change',
                {'type': 'agent', 'id': person_id,
                 'tile': getattr(region, 'name', 'unknown')})
            if event_id is not None:
                cause_event_ids.append(event_id)
    cause_event_ids = list(dict.fromkeys(cause_event_ids))
    event_summaries = [{key: event.get(key) for key in (
        'event', 'count', 'case_ids', 'starving_count', 'inmates', 'fed',
        'starving', 'forced_labor_hours', 'fed_inmate_ids',
        'starving_inmate_ids', 'revenue') if key in event}
        for event in events]
    forced_event_id = emit(
        region, kind='workhouse_forced_labor_calculation',
        record_class='calculation', phase='labor_enforcement',
        subject={'type': 'tile', 'id': getattr(region, 'name', 'unknown')},
        metric_id='labor.forced_labor_hours', unit='hours_per_turn',
        after=float(forced_labor_hours),
        formula_id='labor.workhouse_hours_from_fed_inmates.v1',
        inputs={'turn': int(turn), 'reason': reason,
                'fed_inmate_ids': sorted(fed_inmate_ids),
                'fed_inmate_count': len(fed_inmate_ids),
                'hours_per_fed_inmate': 8.0,
                'forced_labor_hours': float(forced_labor_hours),
                'starving_inmate_ids': sorted(starving_inmate_ids),
                'starving_inmate_count': len(starving_inmate_ids),
                'food_needed': int(food_needed),
                'food_provided': int(food_provided),
                'cash_revenue': float(revenue),
                'operation_events': event_summaries},
        cause_event_ids=cause_event_ids or None)
    before_count = len(inmate_ids_before)
    census_causes = list(cause_event_ids)
    if forced_event_id is not None:
        census_causes.append(forced_event_id)
    emit(region, kind='workhouse_inmate_census',
         record_class='calculation', phase='labor_enforcement',
         subject={'type': 'tile', 'id': getattr(region, 'name', 'unknown')},
         metric_id='labor.workhouse_inmates', unit='people',
         before=before_count, after=len(inmate_ids_after),
         formula_id='labor.workhouse_inmate_census.v1',
         inputs={'turn': int(turn), 'reason': reason,
                 'has_workhouse': has_workhouse(region),
                 'inmate_ids_before': sorted(inmate_ids_before),
                 'inmate_ids_after': inmate_ids_after,
                 'resolved_case_ids': resolved_case_ids,
                 'operation_events': event_summaries},
         cause_event_ids=census_causes or None)


def step_workhouse(region, t: int) -> list[dict]:
    """Execute one turn of Parish Workhouse operations in *region*.

    Returns event records for logging and UI ticker.
    """
    if getattr(region, 'workhouse_last_step_turn', None) == t:
        return []
    region.workhouse_last_step_turn = t
    inmate_ids_before = sorted(a.id for a in get_workhouse_inmates(region))

    if not has_workhouse(region):
        # If workhouse building is lost/destroyed, all inmates are released
        for a in getattr(region, 'agents', []):
            if getattr(a, 'in_workhouse', False):
                a.in_workhouse = False
                from labor_choice import record_labor_status
                record_labor_status(region, a, t, before='workhouse',
                                    after='independent', reason='workhouse_closed')
        _record_workhouse_turn(
            region, t, reason='workhouse_absent',
            inmate_ids_before=inmate_ids_before, events=[])
        return []

    events = []
    gov = getattr(region, 'gov', None)
    gov_agent = gov.agent if gov else None
    food_price = getattr(region, 'food_price', 1.0)

    # Arrests now require a named, resolved vagrancy case and paid officer.
    from labor_cases import process_vagrancy_cases
    prior_inmates = {a.id for a in get_workhouse_inmates(region)}
    resolved_case_ids = process_vagrancy_cases(region, t)
    arrested_count = sum(1 for a in region.agents if getattr(a, 'in_workhouse', False)
                         and a.id not in prior_inmates)

    if arrested_count > 0:
        events.append({
            't': t,
            'event': 'VAGRANCY_ARRESTS',
            'tile': region.name,
            'count': arrested_count,
            'case_ids': resolved_case_ids,
            'message': f"Parish Constables on {region.name} rounded up {arrested_count} vagrants and confined them to the Workhouse."
        })

    # 2. Process active inmates
    inmates = get_workhouse_inmates(region)
    if not inmates:
        _record_workhouse_turn(
            region, t, reason='no_inmates_after_hearing',
            inmate_ids_before=inmate_ids_before, events=events)
        return events

    # Release any inmates who secured private employment or left destitute state
    active_inmates = []
    for inmate in inmates:
        if inmate.employer is not None or getattr(inmate, 'is_lord', False):
            inmate.in_workhouse = False
            from labor_choice import record_labor_status
            record_labor_status(region, inmate, t, before='workhouse',
                                after='employed' if inmate.employer is not None else 'independent',
                                reason='workhouse_release', employer_after=inmate.employer)
        else:
            active_inmates.append(inmate)

    if not active_inmates:
        _record_workhouse_turn(
            region, t, reason='all_inmates_released',
            inmate_ids_before=inmate_ids_before, events=events)
        return events

    total_inmates = len(active_inmates)

    # 3. Subsistence Gruel: Municipal Provision
    # Municipality must provide 1 food per inmate
    food_needed = total_inmates
    food_provided = 0

    if gov_agent:
        gov_stock = min(food_needed, max(0, int(gov_agent.inv_get(Goods.food, 0))))
        if gov_stock:
            food_provided += gov_stock

        # Purchase only from a named agent with physical food inventory.
        # Cash and food move directly between the government, seller, and inmate.
        remaining = food_needed - food_provided
        for inmate in active_inmates[food_provided:]:
            if remaining <= 0 or gov_agent.cash < food_price:
                break
            seller = next((a for a in sorted(region.agents, key=lambda x: x.id)
                           if a is not gov_agent and a is not inmate
                           and not getattr(a, 'is_corporation', False)
                           and getattr(a, 'alive', True)
                           and a.inv_get(Goods.food, 0) >= 1), None)
            if seller is None:
                break
            seller.inv_add(Goods.food, -1)
            _public_write = begin_public_change(None, gov_agent)
            gov_agent.cash -= food_price
            finish_public_change(_public_write, 'workhouse:step_workhouse',
                                 inputs={'source_writer': 'workhouse.py:step_workhouse:c0e1de98a028b103:1', 'semantic_operation_id': locals().get('operation_id')})
            _public_write = begin_public_change(None, seller)
            seller.cash += food_price
            finish_public_change(_public_write, 'workhouse:step_workhouse',
                                 inputs={'source_writer': 'workhouse.py:step_workhouse:48356d58069dc56c:1', 'semantic_operation_id': locals().get('operation_id')})
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(
                region, 'workhouse_food_purchase', turn=t,
                payer_id=gov_agent.id, recipient_id=seller.id,
                good=Goods.food, quantity=1, amount=food_price,
                detail={'inmate_id': inmate.id})
            gov_agent.inv_add(Goods.food, 1)
            food_provided += 1
            remaining -= 1

    fed_inmates = active_inmates[:food_provided]
    starving_inmates = active_inmates[food_provided:]

    for inmate in fed_inmates:
        if gov_agent and gov_agent.inv_get(Goods.food, 0) > 0:
            gov_agent.inv_add(Goods.food, -1)
        inmate.inv_add(Goods.food, 1)
        inmate.hungry_steps = 0
        inmate.mem_push('mem_workhouse', 0.5)

    # 4. Record labor without creating unsourced treasury revenue.
    forced_hours = len(fed_inmates) * 8.0
    region.forced_labor_hours = getattr(region, 'forced_labor_hours', 0.0) + forced_hours
    total_revenue = 0.0

    # 5. Handle Fiscal Drought & Workhouse Bread Riots
    if starving_inmates:
        for inmate in starving_inmates:
            inmate.hungry_steps += 1
            inmate.mem_push('mem_starvation', 1.0)
            inmate.mem_push('mem_workhouse', 1.0)

        # Spike tile protest energy
        if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
            region.protest_energy_log[-1] = min(10.0, region.protest_energy_log[-1] + 2.5)

        # Starvation bread riot: inmates break out and raid local granaries
        events.append({
            't': t,
            'event': 'WORKHOUSE_BREAD_RIOT',
            'tile': region.name,
            'starving_count': len(starving_inmates),
            'message': (f"Fiscal Drought on {region.name}: Municipal treasury empty! "
                        f"{len(starving_inmates)} Workhouse inmates denied gruel and launched a Bread Riot.")
        })

        # If starved for 3+ turns, workhouse authority collapses and inmates are expelled
        for inmate in starving_inmates:
            if inmate.hungry_steps >= 3:
                inmate.in_workhouse = False
                from labor_choice import record_labor_status
                record_labor_status(region, inmate, t, before='workhouse',
                                    after='independent', reason='workhouse_food_failure')

    events.append({
        't': t,
        'event': 'WORKHOUSE_OPERATIONS',
        'tile': region.name,
        'inmates': total_inmates,
        'revenue': total_revenue,
        'fed': len(fed_inmates),
        'starving': len(starving_inmates),
        'forced_labor_hours': forced_hours,
        'message': (f"Parish Workhouse on {region.name}: {total_inmates} inmates confined; "
                    f"{forced_hours:.1f} compulsory labor hours recorded, with no sale revenue.")
    })

    events[-1]['fed_inmate_ids'] = [inmate.id for inmate in fed_inmates]
    events[-1]['starving_inmate_ids'] = [inmate.id for inmate in starving_inmates]
    _record_workhouse_turn(
        region, t, reason='workhouse_operations',
        inmate_ids_before=inmate_ids_before, events=events,
        fed_inmate_ids=[inmate.id for inmate in fed_inmates],
        starving_inmate_ids=[inmate.id for inmate in starving_inmates],
        food_needed=food_needed, food_provided=food_provided,
        forced_labor_hours=forced_hours, revenue=total_revenue)

    return events

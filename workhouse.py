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


def step_workhouse(region, t: int) -> list[dict]:
    """Execute one turn of Parish Workhouse operations in *region*.

    Returns event records for logging and UI ticker.
    """
    if getattr(region, 'workhouse_last_step_turn', None) == t:
        return []
    region.workhouse_last_step_turn = t

    if not has_workhouse(region):
        # If workhouse building is lost/destroyed, all inmates are released
        for a in getattr(region, 'agents', []):
            if getattr(a, 'in_workhouse', False):
                a.in_workhouse = False
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
        return events

    # Release any inmates who secured private employment or left destitute state
    active_inmates = []
    for inmate in inmates:
        if inmate.employer is not None or getattr(inmate, 'is_lord', False):
            inmate.in_workhouse = False
        else:
            active_inmates.append(inmate)

    if not active_inmates:
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
            gov_agent.cash -= food_price
            seller.cash += food_price
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

    return events

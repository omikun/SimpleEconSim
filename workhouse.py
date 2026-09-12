"""
workhouse.py — Parish Workhouse & Vagrancy Enforcement Engine for REGNUM.

Implements the English Poor Laws & Workhouse System:
1. Dispossessed, landless, and unemployed vagrants are arrested and confined to
   the Parish Workhouse.
2. Inmates receive bare-subsistence gruel (1 food/turn) provided by the
   municipality (conserved food transfer or market purchase).
3. Inmates perform compulsory hard labor (oakum picking, stone breaking)
   generating municipal revenue directly credited to the municipal treasury.
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

    # 1. Arrest & Confine unattached vagrants (dispossessed & destitute)
    candidates = [
        a for a in region.agents
        if a.alive
        and not a.is_trader
        and not a.is_government
        and not getattr(a, 'is_lord', False)
        and getattr(a, 'employer', None) is None
        and not getattr(a, 'in_workhouse', False)
        and (a.social_class == 'dispossessed' or (getattr(a, 'assigned_plot_id', None) is None and a.cash < 5.0))
    ]

    arrested_count = 0
    for pauper in candidates:
        pauper.in_workhouse = True
        pauper.social_class = 'dispossessed'
        pauper.mem_push('mem_workhouse', 1.0)
        arrested_count += 1

    if arrested_count > 0:
        events.append({
            't': t,
            'event': 'VAGRANCY_ARRESTS',
            'tile': region.name,
            'count': arrested_count,
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
        gov_food = gov_agent.inv_get(Goods.food, 0)
        if gov_food >= food_needed:
            # Conserved transfer from municipal granary
            gov_agent.inv_add(Goods.food, -food_needed)
            food_provided = food_needed
        else:
            # Provide whatever gov has
            if gov_food > 0:
                gov_agent.inv_add(Goods.food, -gov_food)
                food_provided += gov_food
            remaining = food_needed - food_provided
            # Buy remaining food from market if gov has cash
            cost = remaining * food_price
            if gov_agent.cash >= cost:
                gov_agent.cash -= cost
                food_provided += remaining

    fed_inmates = active_inmates[:food_provided]
    starving_inmates = active_inmates[food_provided:]

    for inmate in fed_inmates:
        inmate.inv_add(Goods.food, 1)
        inmate.hungry_steps = 0
        inmate.mem_push('mem_workhouse', 0.5)

    # 4. Compulsory Municipal Labor
    # Inmates generate municipal revenue from forced labor (stone breaking, oakum picking)
    revenue_per_inmate = 1.50
    total_revenue = round(len(fed_inmates) * revenue_per_inmate, 2)
    if gov_agent and total_revenue > 0:
        gov_agent.cash += total_revenue

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
        'message': (f"Parish Workhouse on {region.name}: {total_inmates} inmates confined. "
                    f"Generated ${total_revenue:.1f} municipal revenue.")
    })

    return events

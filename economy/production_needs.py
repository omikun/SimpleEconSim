"""Commodity needs and feasible responses, derived without changing the world."""
from goods import Goods


def needs(region):
    from food_outlook import snapshot
    from career_transitions import profession, working_adult
    from households import human
    from collections import Counter
    turn = int(getattr(region, '_last_turn', 0))
    people = [a for a in region.agents if human(a)]
    counts = Counter(profession(a) for a in people if working_adult(a, turn))
    logs = getattr(region, 'production_log', {})
    averages = {g: sum(logs.get(g, [])[-10:]) / max(1, len(logs.get(g, [])[-10:])) for g in region.recipes}
    inputs = Counter()
    for g, recipe in region.recipes.items():
        ingredient = recipe.get('input')
        if ingredient is not None and recipe.get('production', 0) > 0:
            inputs[ingredient] += averages.get(g, 0) * recipe.get('numInput', 0) / recipe['production']
    outlook = snapshot(region)
    ordinary = {Goods.food: outlook['minimum_meal_units'], Goods.wood: len(people) * .5,
                Goods.cloth: len(people) * .1}
    work = getattr(region, 'work_allocations', {}).get('people', {})
    by_id = {a.id: a for a in people}
    rows = []
    for good, recipe in region.recipes.items():
        if good in (Goods.none, Goods.gov, Goods.transport):
            continue
        requirement = ordinary.get(good, 0) + inputs[good]
        stock = sum(max(0, a.inv_get(good, 0)) for a in region.agents)
        output = averages.get(good, 0)
        if good == Goods.food:
            output = outlook['expected_harvest'] / 10 + outlook['forecast_commons_food_units']
            stock = outlook['stocks']['total']
        funded = getattr(region, 'demand_log', {}).get(good, [])[-3:]
        funded_orders = sum(funded) / max(1, len(funded))
        # Household restocking orders are not additional recurring consumption.
        gap = max(0, requirement - output)
        ingredient = recipe.get('input')
        held_input = sum(a.inv_get(ingredient, 0) for a in region.agents) if ingredient else 0
        if good == Goods.food:
            seeds = sum(f.get('food_milli', 0) / 1000 for f in getattr(region, 'farms', {}).values())
            farms = getattr(region, 'farms', {})
            dormant = [f for f in farms.values() if not f.get('crop') or f['crop']['closed']]
            seed_need = sum(f['area'] * 6 for f in dormant)
            # Read recorded demand for work; never create operations in this projection.
            from agriculture import stage, WORK_PER_AREA, work_productivity
            label = stage(region)
            actors = {a.id: a for a in region.agents}
            requested = sum(f['crop']['planted_area'] * WORK_PER_AREA.get(label, 0) / work_productivity(region, actors.get(f['operator_id']), label)
                            for f in farms.values() if f.get('crop') and not f['crop']['closed'])
            delivered = outlook['effective_farm_work']
            constraint = ('seed_or_working_capital' if seeds + .001 < seed_need * .5 else
                          'seasonal_labor' if requested > delivered + .01 else 'land_or_productivity')
            if outlook['diagnosis'] == 'access':
                constraint = 'household_access'
            if not getattr(region, 'farms', {}):
                constraint = 'land_access'
        elif ingredient is not None and recipe.get('numInput', 0) > 0 and held_input < recipe['numInput']:
            constraint = f'input:{ingredient.name}'
        elif counts.get(good, 0) == 0 and recipe.get('setup_good'):
            constraint = 'equipment_and_entry'
        else:
            constraint = 'labor_or_productivity'
        if gap <= .001:
            constraint = 'covered'
        response = ('relief' if constraint == 'household_access' else
                    'working_capital' if constraint == 'seed_or_working_capital' else
                    'seasonal_hiring' if constraint == 'seasonal_labor' else
                    'working_capital' if constraint.startswith('input:') else
                    'entry_and_equipment' if constraint == 'equipment_and_entry' else
                    'access_policy' if constraint == 'land_access' else 'procurement')
        primary = counts.get(good, 0)
        per_worker = output / primary if primary else 0
        effective = outlook['effective_farm_work'] if good == Goods.food else sum(
            row.get('activities', {}).get('main', 0) for pid, row in work.items()
            if pid in by_id and profession(by_id[pid]) == good)
        rows.append({'good': good.name, 'workers': primary, 'effective_work': round(effective, 3), 'output_per_turn': round(output, 3),
                     'requirements_per_turn': round(requirement, 3), 'productive_input_need': round(inputs[good], 3),
                     'funded_orders': round(funded_orders, 3), 'stocks': round(stock, 3),
                     'coverage_turns': round(stock / requirement, 2) if requirement else None,
                     'gap_per_turn': round(gap, 3), 'constraint': constraint, 'response': response,
                     'extra_workers_estimate': round(gap / per_worker, 1) if gap and per_worker and constraint in ('labor_or_productivity', 'seasonal_labor') else None,
                     'essential': good in ordinary or inputs[good] > 0,
                     'reference_price': recipe.get('price', 0)})
    return rows

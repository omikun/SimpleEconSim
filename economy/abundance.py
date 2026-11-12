"""Budgeted household uses and production-earned proficiency.

Balance constants are gameplay parameters. No inventory expires in this model.
Plans reserve cash once across all goods; the auction still transfers every unit
and every payment. Author-controlled campaigns retain their existing rules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from goods import Goods


@dataclass(frozen=True)
class Use:
    weight: float
    saturation: int
    flow: float  # units used per turn; durable stocks are worn fractionally


USES = {
    Goods.wood: Use(1.2, 8, 1.0),
    Goods.furniture: Use(1.0, 5, 0.066),
    Goods.cloth: Use(1.1, 6, 0.25),
    Goods.prepared_food: Use(1.4, 8, 0.0),  # eaten by the calorie system
    Goods.sugar: Use(0.6, 4, 0.5),
    Goods.tea: Use(0.6, 4, 0.5),
    Goods.tobacco: Use(0.3, 3, 0.25),
    Goods.rum: Use(0.4, 3, 0.25),
    Goods.fine_textiles: Use(0.5, 3, 0.1),
    Goods.porcelain: Use(0.4, 3, 0.05),
    Goods.foreign_luxuries: Use(0.3, 2, 0.1),
}


def enabled(region):
    from world_config import gameplay_flags_for
    return (region is not None and gameplay_flags_for(region).abundance
            and getattr(region, 'abundance_enabled', False)
            and not getattr(region, 'wilderness', False))


def household(agent):
    return (getattr(agent, 'alive', True)
            and not any(getattr(agent, field, False) for field in
                        ('is_corporation', 'is_government', 'is_trader', 'military_unit_id')))


def proficiency(agent, good):
    work = getattr(agent, 'productive_practice', {}).get(good.name, 0.0)
    return 1.0 + 0.60 * (1.0 - math.exp(-max(0.0, work) / 30.0))


def funded_demand(region, good):
    """Reachable recent orders, including the first buyers of an emerging use."""
    history = list(getattr(region, 'demand_log', {}).get(good, []))[-4:]
    observed = sum(history) / len(history) if history else 0.0
    sales = list(getattr(region, 'sold_log', {}).get(good, []))[-4:]
    realized = sum(sales) / len(sales) if sales else 0.0
    households = sum(plan.get(good, {}).get('quantity', 0)
                     for plan in getattr(region, 'household_orders', {}).values())
    return max(observed, realized, households)


def learn(region, agent, good, work, turn):
    """Only completed productive work earns practice, once per operation."""
    if not enabled(region) or work <= 0:
        return
    history = dict(getattr(agent, 'productive_practice', {}))
    before = history.get(good.name, 0.0)
    history[good.name] = before + work
    agent.productive_practice = history
    from run_trace import emit
    emit(region, kind='productive_practice', record_class='outcome', phase='production',
         subject={'type': 'agent', 'id': agent.id, 'good': good.name, 'tile': region.name},
         metric_id='production.practice', unit='work_turns', before=before,
         after=history[good.name], formula_id='production.practice.v1',
         inputs={'work_completed': work, 'turn': turn,
                 'productivity_after': proficiency(agent, good)})


def household_plan(region, agent):
    """Allocate one funded basket, protecting meals and working inputs first.

    A 50% price allowance funds auction competition. Marginal benefit falls
    with existing stock. Savings release gradually rather than all at once.
    """
    from nutrition import appetite_units
    recipes = region.recipes
    parent = getattr(agent, 'parent', None)
    if (getattr(agent, 'is_native_child', False)
            and agent.age(getattr(region, '_last_turn', 0)) < 14
            and parent is not None and parent.alive and parent in region.agents):
        return {}
    cash = max(0.0, float(agent.remainingCash))
    remaining = cash
    orders = {}
    production = recipes.get(agent.output, {}) if agent.employer is None else {}
    productive_good = production.get('input')
    input_reserve = max(0, int(production.get('numInput', 0))) * 2
    dependents = sum(appetite_units(child) for child in getattr(agent, 'descendants', ())
                     if getattr(child, 'alive', False)
                     and getattr(child, 'is_native_child', False)
                     and child.age(getattr(region, '_last_turn', 0)) < 14
                     and getattr(child, 'region', None) == getattr(agent, 'region', None))
    meal = appetite_units(agent) + dependents

    def add(good, wanted, reason):
        nonlocal remaining
        price = max(0.1, float(recipes.get(good, {}).get('price', 0.1)))
        limit = 1.5 * price
        quantity = min(max(0, int(wanted)), int((remaining + 1e-9) / limit))
        if quantity:
            row = orders.setdefault(good, {'quantity': 0, 'limit': limit, 'uses': []})
            row['quantity'] += quantity
            row['uses'].append(reason)
            remaining -= quantity * limit

    from food_access import household_demand
    food_plan = household_demand(agent, region)
    add(Goods.food, math.ceil(food_plan['desired']), 'meals_and_replenishment')
    if productive_good in recipes and input_reserve:
        held = agent.inv_get(productive_good, 0)
        already = orders.get(productive_good, {}).get('quantity', 0)
        protected_meals = 2 * meal if productive_good == Goods.food else 0
        add(productive_good, input_reserve + protected_meals - held - already,
            'working_inputs')
    setup = production.get('setup_good')
    if setup is not None and not getattr(agent, 'workshop_equipped', False):
        add(setup, production.get('setup_units', 1) - agent.inv_get(setup, 0), 'workshop_equipment')

    # A stable spending anchor is independent of the food price. Cheap staples
    # therefore leave more money for other uses instead of shrinking all wants.
    resources = cash + max(0.0, float(getattr(agent, 'wage', 0.0)))
    discretionary = min(remaining, max(0.0, 0.25 * resources))
    spent = 0.0
    while True:
        best = None
        for good, use in USES.items():
            if good not in recipes or good == agent.output or good == setup:
                continue
            held = max(0, agent.inv_get(good, 0))
            if good == productive_good:
                held = max(0, held - input_reserve)
            planned = orders.get(good, {}).get('quantity', 0)
            position = held + planned
            if position >= use.saturation:
                continue
            price = max(0.1, float(recipes[good]['price']))
            limit = 1.5 * price
            benefit = resources * 0.12 * use.weight / (1 + position)
            if benefit < limit or spent + limit > discretionary + 1e-9:
                continue
            score = benefit / limit
            if best is None or score > best[0]:
                best = (score, good, limit)
        if best is None:
            break
        _, good, limit = best
        add(good, 1, 'comfort_and_variety')
        spent += limit
    return orders


def prepare_household_orders(region, turn):
    plans, funding = {}, {}
    bank = getattr(region, 'bank', None)
    for a in region.agents:
        if not household(a):
            continue
        liquid = a.cash + (bank.deposits.get(a, 0) if bank is not None else 0)
        a.remainingCash = max(0.0, liquid)
        proposed = household_plan(region, a)
        required = sum(row['quantity'] * row['limit'] for row in proposed.values())
        ids = []
        if bank is not None and required > a.cash:
            bank.Withdraw(a, min(bank.deposits.get(a, 0), required-a.cash),
                          trace_region=region, t=turn, reason='fund_market_bid', trace_event_ids=ids)
        a.remainingCash = max(0.0, a.cash)
        plans[a.id] = proposed if required <= a.cash + 1e-8 else household_plan(region, a)
        funding[a.id] = ids
    region.household_orders = plans
    region.household_budget_funding = funding
    region.household_orders_turn = turn
    region.household_budget_active = True
    from run_trace import emit
    for agent in region.agents:
        if agent.id not in plans:
            continue
        plan = plans[agent.id]
        emit(region, kind='household_budget_plan', record_class='decision', phase='market',
             subject={'type': 'agent', 'id': agent.id, 'tile': region.name},
             metric_id='living.planned_spending', unit='local_currency',
             after=sum(row['quantity'] * row['limit'] for row in plan.values()),
             formula_id='demand.funded_basket.v1',
             cause_event_ids=funding.get(agent.id) or None,
             inputs={'cash_budget': max(0, agent.remainingCash),
                     'orders': {g.name: row for g, row in plan.items()}})


def order(region, agent, good):
    if (not enabled(region) or not household(agent)
            or not getattr(region, 'household_budget_active', False)
            or getattr(region, 'household_orders_turn', None) != getattr(region, '_last_turn', None)):
        return None
    return getattr(region, 'household_orders', {}).get(agent.id, {}).get(
        good, {'quantity': 0, 'limit': 0.0, 'uses': []})


def consume_uses(region, agent):
    """Real household use, with fractional wear carried across turns."""
    from economy.actor_accounts import record
    from run_trace import emit
    wear = dict(getattr(agent, 'household_use_remainders', {}))
    consumed = {}
    recipe = region.recipes.get(agent.output, {}) if agent.employer is None else {}
    for good, use in USES.items():
        if use.flow <= 0 or good == agent.output:
            continue
        before = int(agent.inv_get(good, 0))
        reserve = 2 * recipe.get('numInput', 0) if recipe.get('input') == good else 0
        if recipe.get('setup_good') == good:
            reserve += recipe.get('setup_units', 1)
        available = max(0, before - reserve)
        if not available:
            continue
        accrued = wear.get(good.name, 0.0) + use.flow * min(available, use.saturation)
        quantity = min(available, int(accrued + 1e-9))
        wear[good.name] = accrued - quantity
        if not quantity:
            continue
        agent.inv_add(good, -quantity)
        consumed[good] = quantity
        record(region, 'household_consumption', payer_id=agent.id, good=good, quantity=quantity)
        emit(region, kind='household_nonfood_consumption', record_class='outcome', phase='demographics',
             subject={'type': 'tile/agent/good', 'id': str(agent.id), 'tile': region.name, 'good': good.name},
             metric_id='goods.household_consumption', unit='units', before=before, after=before-quantity,
             formula_id='demand.household_use.v1',
             inputs={'units_consumed': quantity, 'protected_input_units': reserve,
                     'use_rate': use.flow, 'wear_remainder': wear[good.name]})
    agent.household_use_remainders = wear
    return consumed


def consider_workshops(region, turn):
    """Compatibility entry point; workshop choices belong to the career phase."""
    from career_transitions import step_careers
    return step_careers(region, turn, independent=enabled(region))


def produce_workshop(region, agent, recipe, totals, receipt_ids, turn):
    """Transform inputs into higher-value goods with real work and equipment.

    Equipment remains owned inventory, reserved from household use and sale.
    Better technique increases throughput, never output per physical input.
    """
    from engineering import production_work_share, record_operation
    from region_production import terrain_bonus
    from economy.actor_accounts import record
    from run_trace import emit
    if not enabled(region):
        return
    if agent.inv_get(recipe['setup_good'], 0) < recipe['setup_units']:
        agent.workshop_equipped = False
        return
    agent.workshop_equipped = True
    if agent.is_corporation:
        workers = [a for a in agent.employees if a.alive and not a.is_striking
                   and not a.in_revolt and a.id not in getattr(region, 'pollution_revolt_ids', set())]
    else:
        workers = [agent]
    from work_allocation import main_work
    work = sum(main_work(region, a, turn, default=1.0) for a in workers)
    practice = sum(proficiency(a, agent.output) for a in workers) / max(1, len(workers))
    throughput = recipe['production'] * work * practice * terrain_bonus(region, agent.output, producer=agent)
    from nutrition import appetite_units
    input_good = recipe['input']
    input_per_output = recipe['numInput'] / recipe['production']
    if agent.output == Goods.prepared_food:
        input_per_output = max(1, input_per_output)
    protected = 0
    if input_good == Goods.food and not agent.is_corporation:
        protected = appetite_units(agent)
        protected += sum(appetite_units(child) for child in getattr(agent, 'descendants', ())
                         if child.alive and child.is_native_child and child.age(turn) < 14)
    if input_good == recipe['setup_good']:
        protected += recipe['setup_units']
    before = agent.inv_get(input_good, 0)
    stock = agent.inv_get(agent.output, 0)
    room = max(0, recipe['maxinv'] * max(1, len(workers)) - stock)
    units = min(max(0, int(throughput)), max(0, int((before - protected) / input_per_output)), room)
    if units <= 0:
        return
    inputs_used = math.ceil(units * input_per_output)
    completed_work = work * min(1.0, units / max(1.0, throughput))
    agent.inv_add(input_good, -inputs_used)
    agent.inv_add(agent.output, units)
    if input_good in (Goods.food, Goods.prepared_food):
        from food_accounts import record as food_record
        loss = inputs_used - (units if agent.output in (Goods.food, Goods.prepared_food) else 0)
        if loss:
            food_record(region, 'food_processing_loss', loss, source=agent, good=input_good)
    record(region, 'input_consumed', payer_id=agent.id, good=input_good, quantity=inputs_used,
           amount=inputs_used * max(0, agent.cost_get(input_good, 0)))
    record(region, 'production', recipient_id=agent.id, good=agent.output, quantity=units)
    totals[agent.output] = totals.get(agent.output, 0) + units
    event_id = emit(region, kind='workshop_production', record_class='outcome', phase='production',
                    subject={'type': 'agent', 'id': agent.id, 'tile': region.name, 'good': agent.output.name},
                    metric_id='goods.production', unit='units', before=0, after=units,
                    formula_id='production.workshop.v1',
                    inputs={'throughput': throughput, 'input_inventory_before': before,
                            'protected_meals': protected, 'storage_room': room,
                            'input_good': input_good.name, 'input_per_output': input_per_output,
                            'input_units': inputs_used, 'input_inventory_after': before-inputs_used,
                            'output_inventory_before': stock, 'output_inventory_after': stock+units,
                            'equipment_good': recipe['setup_good'].name,
                            'equipment_units': recipe['setup_units'], 'work_completed': completed_work})
    if event_id is not None:
        receipt_ids.append(event_id)
    record_operation(region, agent, agent.output, completed_work, len(workers), turn, event_id)
    for worker in workers:
        learn(region, worker, agent.output, min(1, completed_work / max(1, len(workers))), turn)

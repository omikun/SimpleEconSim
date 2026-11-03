"""
Demographics consumption: daily food intake, luxury goods consumption, and bottleneck weights.
"""

from goods import Goods
from agent import get_input_commodity, get_output_commodity
from logger import loginfo
from random_cache import rand


def compute_bottleneck_weights(ctx, agents, choices_list):
    """Hoisted computation: which sector is most input-constrained?"""
    bottleneck_sector = Goods.none
    bottleneck_ratio = 0
    weights = [1] * len(choices_list)
    for candidate_good in ctx.goods:
        if candidate_good == Goods.gov:
            continue
        recipe = ctx.recipes.get(candidate_good)
        if recipe and recipe.get('numInput', 0) > 0:
            input_good = recipe['input']
            number_consumers = sum(
                1 for a in agents
                if get_input_commodity(a) == input_good and not a.is_corporation
                and a.employer is None
            )
            number_producers = sum(
                1 for a in agents
                if a.output == input_good and not a.is_corporation
                and a.employer is None
            )
            pressure = (number_consumers * recipe['numInput']) / max(1, number_producers)
            if pressure > bottleneck_ratio and pressure > 2.0:
                bottleneck_ratio = pressure
                bottleneck_sector = input_good
    if bottleneck_sector != Goods.none:
        weights = [3 if g == bottleneck_sector else 1 for g in choices_list]
    return weights


def consume_goods(ctx, agent, number_food_consumed, number_wood_consumed, number_furniture_consumed):
    """Consume non-food luxuries; nutrition is accounted for in one place."""
    from abundance import enabled, consume_uses
    region = getattr(ctx, 'source_region', None)
    if enabled(region):
        used = consume_uses(region, agent)
        return (number_food_consumed, number_wood_consumed + used.get(Goods.wood, 0),
                number_furniture_consumed + used.get(Goods.furniture, 0))
    mult = getattr(agent, 'consumption_multiplier', 1.0)
    consumed_components = {}
    inventory_before = {}

    def record_consumption(good, quantity, mechanism, **evidence):
        inventory_before.setdefault(good, int(agent.inv_get(good, 0)))
        consumed_components.setdefault(good, []).append(
            {'mechanism': mechanism, 'quantity': int(quantity), **evidence})

    if mult > 1.0:
        for luxury_good in ctx.goods:
            if luxury_good in (Goods.food, Goods.prepared_food, Goods.gov):
                continue
            if luxury_good == Goods.transport:
                continue
            if agent.inv_get(luxury_good, 0) > 0 and get_output_commodity(agent) != luxury_good:
                recipes = getattr(ctx, 'recipes', getattr(getattr(ctx, 'source_region', None), 'recipes', {}))
                recipe = recipes.get(get_output_commodity(agent), {})
                # Keep two batches of working inputs; discretionary use gets the excess.
                reserve = (2 * int(recipe.get('numInput', 0))
                           * max(1, len(getattr(agent, 'employees', ())) if getattr(agent, 'is_corporation', False) else 1)
                           if get_input_commodity(agent) == luxury_good else 0)
                available = max(0, agent.inv_get(luxury_good, 0) - reserve)
                consume_qty = min(max(1, int(mult * 0.5)), available, 5)
                if consume_qty > 0:
                    stock_before = int(agent.inv_get(luxury_good, 0))
                    inventory_before.setdefault(luxury_good, stock_before)
                    agent.inv_add(luxury_good, -consume_qty)
                    record_consumption(
                        luxury_good, consume_qty, 'wealth_multiplier',
                        consumption_multiplier=float(mult),
                        stock_before=stock_before,
                        requested_quantity=max(1, int(mult * 0.5)),
                        maximum_quantity=5, protected_input_units=reserve)
                    if luxury_good == Goods.furniture:
                        number_furniture_consumed += consume_qty
                    elif luxury_good == Goods.wood:
                        number_wood_consumed += consume_qty
                    loginfo('', agent.name(),
                            'wealth consumption (mult=' + str(round(mult, 2))
                            + '), consumed', consume_qty,
                            ctx.profession[luxury_good])
    if agent.inv_get(Goods.wood, 0) > 2 and get_input_commodity(agent) != Goods.wood \
       and get_output_commodity(agent) != Goods.wood:
        stock_before = int(agent.inv_get(Goods.wood, 0))
        inventory_before.setdefault(Goods.wood, stock_before)
        agent.inv_add(Goods.wood, -1)
        record_consumption(Goods.wood, 1, 'wood_stockpile_drawdown',
                           stock_before=stock_before, threshold_units=2)
        number_wood_consumed += 1
    if (agent.inv_get(Goods.furniture, 0) > 0
            and get_output_commodity(agent) != Goods.furniture):
        furniture_draw = rand.random()
        if furniture_draw < .066:
            stock_before = int(agent.inv_get(Goods.furniture, 0))
            inventory_before.setdefault(Goods.furniture, stock_before)
            agent.inv_add(Goods.furniture, -1)
            record_consumption(
                Goods.furniture, 1, 'furniture_stochastic_wear',
                stock_before=stock_before, random_draw=float(furniture_draw),
                consumption_threshold=0.066)
            number_furniture_consumed += 1
    _trace_nonfood_consumption(
        ctx, agent, inventory_before, consumed_components, mult)
    return number_food_consumed, number_wood_consumed, number_furniture_consumed


def _trace_nonfood_consumption(ctx, agent, inventory_before, components, mult):
    if not components:
        return
    region = getattr(ctx, 'source_region', None)
    if region is None:
        return
    from run_trace import emit

    turn = int(getattr(region, '_last_turn', 0) or 0)
    output_good = getattr(get_output_commodity(agent), 'name', None)
    input_good = getattr(get_input_commodity(agent), 'name', None)
    for good in sorted(components, key=lambda item: item.value):
        before = int(inventory_before[good])
        after = int(agent.inv_get(good, 0))
        emit(
            region, kind='household_nonfood_consumption',
            record_class='outcome', phase='demographics',
            subject={'type': 'tile/agent/good', 'id': str(agent.id),
                     'tile': region.name, 'good': good.name},
            metric_id='goods.household_consumption', unit='units',
            before=before, after=after,
            formula_id='demographics.nonfood_consumption.v1',
            inputs={'operation_id':
                    f'nonfood-consumption:{region.name}:{turn}:{agent.id}:{good.name}',
                    'turn': turn, 'agent_id': int(agent.id),
                    'good': good.name, 'units_consumed': before - after,
                    'consumption_multiplier': float(mult),
                    'output_good': output_good, 'input_good': input_good,
                    'consumption_components': components[good]})


def _food_wallet_units(agent, wallet_name):
    wallet = getattr(agent, wallet_name, None)
    if wallet is None:
        return 0
    try:
        return float(wallet[Goods.food.value])
    except (IndexError, KeyError, TypeError):
        return 0


def _trace_food_intake(region, agent, *, turn, outcome, desired, eaten,
                       reserved_before, reserved_consumed, from_inventory,
                       from_foreign, from_export, local_before, local_after,
                       foreign_before, foreign_after, export_before, export_after,
                       deficit_before, deficit_after,
                       reserve_before, reserve_after, hunger_before,
                       hunger_after, calorie_need, metabolic_factor,
                       candidate_private_grain_purchase_events=(), from_prepared=0):
    if region is None:
        return None
    from run_trace import emit

    from nutrition import CALORIES_PER_FOOD
    operation_id = f'food-intake:{region.name}:{float(turn)}:{agent.id}'
    return emit(
        region, kind='household_food_intake', record_class='calculation',
        phase='demographics',
        subject={'type': 'tile/agent', 'id': str(agent.id),
                 'tile': region.name, 'good': Goods.food.name},
        metric_id='health.calorie_deficit', unit='kcal',
        before=float(deficit_before), after=float(deficit_after),
        formula_id='nutrition.intake_and_reserve.v1',
        inputs={'operation_id': operation_id, 'turn': float(turn),
                'agent_id': agent.id, 'outcome': outcome,
                'desired_food_units': float(desired),
                'eaten_food_units': float(eaten),
                'food_shortfall_units': max(0, float(desired) - float(eaten)),
                'food_sources': {
                    'emergency_ration_queue': float(reserved_consumed),
                    'household_inventory': float(from_inventory),
                    **({'prepared_food': float(from_prepared)} if from_prepared else {}),
                    'foreign_trader_inventory': float(from_foreign),
                    'export_trader_inventory': float(from_export)},
                'consumed_from_local_inventory_units': float(from_inventory),
                'candidate_private_grain_purchase_events': [
                    {'event_id': row['event_id'], 'turn': float(row['turn']),
                     'food_units': float(row['food_units'])}
                    for row in candidate_private_grain_purchase_events],
                'private_grain_purchase_source_attribution': (
                    'unknown_fungible_inventory' if from_inventory > 0 else
                    'not_applicable_no_local_inventory_consumed'),
                'household_food_inventory_before': float(local_before),
                'household_food_inventory_after': float(local_after),
                'foreign_food_inventory_before': float(foreign_before),
                'foreign_food_inventory_after': float(foreign_after),
                'export_food_inventory_before': float(export_before),
                'export_food_inventory_after': float(export_after),
                'emergency_ration_units_before': float(reserved_before),
                'emergency_ration_units_consumed': float(reserved_consumed),
                'emergency_ration_units_returned_to_inventory': max(
                    0, float(reserved_before) - float(reserved_consumed)),
                'effective_calorie_need_kcal': float(calorie_need),
                'calories_per_food_unit': CALORIES_PER_FOOD,
                'metabolic_need_factor': float(metabolic_factor),
                'calorie_deficit_before_kcal': float(deficit_before),
                'calorie_deficit_after_kcal': float(deficit_after),
                'energy_reserve_before_kcal': float(reserve_before),
                'energy_reserve_after_kcal': float(reserve_after),
                'hunger_steps_before': float(hunger_before),
                'hunger_steps_after': float(hunger_after)})


def consume_daily_food(agent, *, region=None, turn=None):
    """One physical meal and one nutrition update per person/turn."""
    from nutrition import appetite_units, effective_calorie_need, metabolic_need_factor, record_intake
    if turn is not None and getattr(agent, 'food_consumed_turn', None) == turn:
        return 0.0
    desired = appetite_units(agent)
    need = effective_calorie_need(agent)
    metabolic = metabolic_need_factor(agent)
    deficit_before, reserve_before = agent.calorie_deficit_kcal, agent.energy_reserve_kcal
    hunger_before = agent.hungry_steps
    local_before = agent.inv_get(Goods.food, 0)
    foreign_before = _food_wallet_units(agent, 'inventory_foreign')
    export_before = _food_wallet_units(agent, 'inventory_export')
    eaten = 0.0
    amounts = {}
    for good in (Goods.prepared_food, Goods.food):
        take = min(max(0, desired - eaten), max(0, agent.inv_get(good, 0)))
        if take and region is not None:
            from food_accounts import consume
            take = consume(region, agent, take, kind='meal', good=good)
        elif take:
            agent.inv_add(good, -take)
        amounts[good] = take
        eaten += take
    foreign = exported = 0.0
    if agent.is_trader and eaten < desired:
        for name in ('inventory_foreign', 'inventory_export'):
            wallet = getattr(agent, name)
            take = min(desired - eaten, max(0, wallet[Goods.food]))
            wallet[Goods.food] -= take
            eaten += take
            if name == 'inventory_foreign':
                foreign += take
            else:
                exported += take
            if take and region is not None:
                from food_accounts import record
                record(region, 'meal', take, source=agent, wallet=name)
    record_intake(agent, eaten)
    if turn is not None:
        agent.food_consumed_turn = turn
    trace_turn = int(turn or getattr(region, '_last_turn', 0))
    recorder = getattr(region, '_run_trace', None)
    recent = getattr(recorder, 'recent_private_grain_purchase_events', None)
    purchases = recent(agent.id, before_turn=trace_turn) if callable(recent) and amounts[Goods.food] else []
    if (eaten < desired or deficit_before > 0 or agent.calorie_deficit_kcal > 0
            or reserve_before != agent.energy_reserve_kcal or foreign or exported
            or amounts[Goods.prepared_food] or purchases):
        _trace_food_intake(region, agent, turn=int(turn or getattr(region, '_last_turn', 0)),
            outcome='shortfall' if eaten < desired else 'needs_met', desired=desired, eaten=eaten,
            reserved_before=0, reserved_consumed=0, from_inventory=amounts[Goods.food],
            from_prepared=amounts[Goods.prepared_food], from_foreign=foreign, from_export=exported,
            local_before=local_before, local_after=agent.inv_get(Goods.food, 0),
            foreign_before=foreign_before, foreign_after=_food_wallet_units(agent, 'inventory_foreign'),
            export_before=export_before, export_after=_food_wallet_units(agent, 'inventory_export'),
            deficit_before=deficit_before, deficit_after=agent.calorie_deficit_kcal,
            reserve_before=reserve_before, reserve_after=agent.energy_reserve_kcal,
            hunger_before=hunger_before, hunger_after=agent.hungry_steps,
            calorie_need=need, metabolic_factor=metabolic,
            candidate_private_grain_purchase_events=purchases)
    return eaten


def _trace_dependent_food_transfer(region, *, operation_id, turn, parent, child,
                                  amount, parent_before, parent_after,
                                  child_before, child_after, needed_units):
    if region is None:
        return None
    from finance_trace import account_ref
    from run_trace import emit

    contract = {
        'contract_version': 'goods_transfer.v1',
        'operation_id': operation_id,
        'operation_type': 'dependent_household_food_transfer',
        'good': Goods.food.name,
        'unit': 'food_units',
        'amount': int(amount),
        'payer_account': account_ref(
            'agent_inventory', str(parent.id), 'food_units',
            balance_before=int(parent_before), balance_after=int(parent_after),
            balance_scope='inventory.food'),
        'payee_account': account_ref(
            'agent_inventory', str(child.id), 'food_units',
            balance_before=int(child_before), balance_after=int(child_after),
            balance_scope='inventory.food'),
        'delivery_status': 'delivered_to_child_inventory',
        'counterparty_leg_status': 'both_household_food_inventories_captured',
    }
    return emit(
        region, kind='dependent_food_inventory_transfer',
        record_class='transfer', phase='demographics',
        subject={'type': 'tile/parent/child', 'id': operation_id,
                 'tile': region.name, 'parent_id': parent.id,
                 'child_id': child.id, 'good': Goods.food.name},
        metric_id='goods.dependent_food_transfer', unit='food_units',
        before=0, after=int(amount),
        formula_id='demographics.dependent_food_transfer.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'parent_id': parent.id, 'child_id': child.id,
                'child_need_units': int(needed_units),
                'parent_food_before': int(parent_before),
                'parent_food_after': int(parent_after),
                'child_food_before': int(child_before),
                'child_food_after': int(child_after),
                'transfer_contract': contract})


def transfer_dependent_food(agents, turn, *, region=None,
                            return_event_ids=False):
    """Share existing household food with under-14 children before eating."""
    from nutrition import appetite_units
    residents = set(agents)
    total = recipients = 0
    transfer_event_ids = []
    children = sorted(
        (a for a in agents if getattr(a, 'is_native_child', False)
         and a.alive and a.age(turn) < 14), key=lambda a: a.id)
    for child in children:
        parent = child.parent
        if parent not in residents or not parent.alive or parent.region != child.region:
            continue
        missing = max(0, appetite_units(child) - child.inv_get(Goods.food, 0)
                      - max(0, int(getattr(child, 'emergency_food_units', 0))))
        available = max(0, parent.inv_get(Goods.food, 0) - 1)
        amount = min(missing, available)
        if amount:
            parent_before = int(parent.inv_get(Goods.food, 0))
            child_before = int(child.inv_get(Goods.food, 0))
            parent.inv_add(Goods.food, -amount)
            child.inv_add(Goods.food, amount)
            region_name = (getattr(region, 'name', None)
                           or getattr(child, 'region', 'unknown'))
            operation_id = (f'dependent-food:{region_name}:'
                            f'{int(turn)}:{parent.id}:{child.id}')
            event_id = _trace_dependent_food_transfer(
                region, operation_id=operation_id, turn=turn,
                parent=parent, child=child, amount=amount,
                parent_before=parent_before,
                parent_after=int(parent.inv_get(Goods.food, 0)),
                child_before=child_before,
                child_after=int(child.inv_get(Goods.food, 0)),
                needed_units=missing)
            if event_id:
                transfer_event_ids.append(event_id)
            total += amount
            recipients += 1
    if return_event_ids:
        return total, recipients, transfer_event_ids
    return total, recipients

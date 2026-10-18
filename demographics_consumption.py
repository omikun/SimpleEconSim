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
    mult = getattr(agent, 'consumption_multiplier', 1.0)
    consumed_components = {}
    inventory_before = {}

    def record_consumption(good, quantity, mechanism, **evidence):
        inventory_before.setdefault(good, int(agent.inv_get(good, 0)))
        consumed_components.setdefault(good, []).append(
            {'mechanism': mechanism, 'quantity': int(quantity), **evidence})

    if mult > 1.0:
        for luxury_good in ctx.goods:
            if luxury_good in (Goods.food, Goods.gov):
                continue
            if luxury_good == Goods.transport:
                continue
            if agent.inv_get(luxury_good, 0) > 0 and get_output_commodity(agent) != luxury_good:
                consume_qty = min(max(1, int(mult * 0.5)),
                                  agent.inv_get(luxury_good, 0), 5)
                if consume_qty > 0:
                    stock_before = int(agent.inv_get(luxury_good, 0))
                    inventory_before.setdefault(luxury_good, stock_before)
                    agent.inv_add(luxury_good, -consume_qty)
                    record_consumption(
                        luxury_good, consume_qty, 'wealth_multiplier',
                        consumption_multiplier=float(mult),
                        stock_before=stock_before,
                        requested_quantity=max(1, int(mult * 0.5)),
                        maximum_quantity=5)
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
        return int(wallet[Goods.food.value])
    except (IndexError, KeyError, TypeError):
        return 0


def _trace_food_intake(region, agent, *, turn, outcome, desired, eaten,
                       reserved_before, reserved_consumed, from_inventory,
                       from_foreign, from_export, local_before, local_after,
                       foreign_before, foreign_after, export_before, export_after,
                       deficit_before, deficit_after,
                       reserve_before, reserve_after, hunger_before,
                       hunger_after, calorie_need, metabolic_factor):
    if region is None:
        return None
    from run_trace import emit

    operation_id = f'food-intake:{region.name}:{int(turn)}:{agent.id}'
    return emit(
        region, kind='household_food_intake', record_class='calculation',
        phase='demographics',
        subject={'type': 'tile/agent', 'id': str(agent.id),
                 'tile': region.name, 'good': Goods.food.name},
        metric_id='health.calorie_deficit', unit='kcal',
        before=float(deficit_before), after=float(deficit_after),
        formula_id='nutrition.intake_and_reserve.v1',
        inputs={'operation_id': operation_id, 'turn': int(turn),
                'agent_id': agent.id, 'outcome': outcome,
                'desired_food_units': int(desired),
                'eaten_food_units': int(eaten),
                'food_shortfall_units': max(0, int(desired) - int(eaten)),
                'food_sources': {
                    'emergency_ration_queue': int(reserved_consumed),
                    'household_inventory': int(from_inventory),
                    'foreign_trader_inventory': int(from_foreign),
                    'export_trader_inventory': int(from_export)},
                'household_food_inventory_before': int(local_before),
                'household_food_inventory_after': int(local_after),
                'foreign_food_inventory_before': int(foreign_before),
                'foreign_food_inventory_after': int(foreign_after),
                'export_food_inventory_before': int(export_before),
                'export_food_inventory_after': int(export_after),
                'emergency_ration_units_before': int(reserved_before),
                'emergency_ration_units_consumed': int(reserved_consumed),
                'emergency_ration_units_returned_to_inventory': max(
                    0, int(reserved_before) - int(reserved_consumed)),
                'effective_calorie_need_kcal': float(calorie_need),
                'metabolic_need_factor': float(metabolic_factor),
                'calorie_deficit_before_kcal': float(deficit_before),
                'calorie_deficit_after_kcal': float(deficit_after),
                'energy_reserve_before_kcal': float(reserve_before),
                'energy_reserve_after_kcal': float(reserve_after),
                'hunger_steps_before': float(hunger_before),
                'hunger_steps_after': float(hunger_after)})


def consume_daily_food(agent, *, region=None, turn=None):
    """Eat up to the appetite curve and record exact calorie balance."""
    from nutrition import (appetite_units, effective_calorie_need,
                          metabolic_need_factor, record_intake)
    desired = appetite_units(agent)
    need = effective_calorie_need(agent)
    metabolic_factor = metabolic_need_factor(agent)
    deficit_before = float(getattr(agent, 'calorie_deficit_kcal', 0.0))
    reserve_before = float(getattr(agent, 'energy_reserve_kcal', 0.0))
    hunger_before = float(getattr(agent, 'hungry_steps', 0.0))
    reserved = max(0, int(getattr(agent, 'emergency_food_units', 0)))
    agent.emergency_food_units = 0
    eaten = min(desired, reserved)
    from_reserved = eaten
    local_before = int(agent.inv_get(Goods.food, 0))
    foreign_before = _food_wallet_units(agent, 'inventory_foreign')
    export_before = _food_wallet_units(agent, 'inventory_export')
    from_inventory = min(max(0, desired - eaten), max(0, local_before))
    if from_inventory:
        agent.inv_add(Goods.food, -from_inventory)
        eaten += from_inventory
    if reserved > eaten:
        agent.inv_add(Goods.food, reserved - eaten)
    from_foreign = from_export = 0
    if agent.is_trader and eaten < desired:
        for wallet_name, stock in (('foreign', agent.inventory_foreign),
                                   ('export', agent.inventory_export)):
            take = min(desired - eaten, max(0, stock[Goods.food.value]))
            stock[Goods.food.value] -= take
            eaten += take
            if wallet_name == 'foreign':
                from_foreign += take
            else:
                from_export += take
            if eaten >= desired:
                break
    record_intake(agent, eaten)
    local_after = int(agent.inv_get(Goods.food, 0))
    foreign_after = _food_wallet_units(agent, 'inventory_foreign')
    export_after = _food_wallet_units(agent, 'inventory_export')
    deficit_after = float(getattr(agent, 'calorie_deficit_kcal', 0.0))
    reserve_after = float(getattr(agent, 'energy_reserve_kcal', 0.0))
    hunger_after = float(getattr(agent, 'hungry_steps', 0.0))
    outcome = ('shortfall' if eaten < desired else
               'surplus_intake' if reserve_after > reserve_before else
               'needs_met')
    if (eaten < desired or reserved > 0 or deficit_before > 0
            or deficit_after > 0 or reserve_after != reserve_before
            or from_foreign > 0 or from_export > 0):
        trace_turn = (int(turn) if turn is not None
                      else int(getattr(region, '_last_turn', 0)))
        _trace_food_intake(
            region, agent, turn=trace_turn, outcome=outcome,
            desired=desired, eaten=eaten, reserved_before=reserved,
            reserved_consumed=from_reserved, from_inventory=from_inventory,
            from_foreign=from_foreign, from_export=from_export,
            local_before=local_before, local_after=local_after,
            foreign_before=foreign_before, foreign_after=foreign_after,
            export_before=export_before, export_after=export_after,
            deficit_before=deficit_before, deficit_after=deficit_after,
            reserve_before=reserve_before, reserve_after=reserve_after,
            hunger_before=hunger_before, hunger_after=hunger_after,
            calorie_need=need, metabolic_factor=metabolic_factor)
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

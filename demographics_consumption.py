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
                    agent.inv_add(luxury_good, -consume_qty)
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
        agent.inv_add(Goods.wood, -1)
        number_wood_consumed += 1
    if agent.inv_get(Goods.furniture, 0) > 0 and get_output_commodity(agent) != Goods.furniture \
       and rand.random() < .066:
        agent.inv_add(Goods.furniture, -1)
        number_furniture_consumed += 1
    return number_food_consumed, number_wood_consumed, number_furniture_consumed


def consume_daily_food(agent):
    """Eat up to the appetite curve and record exact calorie balance."""
    from nutrition import appetite_units, record_intake
    desired = appetite_units(agent)
    reserved = max(0, int(getattr(agent, 'emergency_food_units', 0)))
    agent.emergency_food_units = 0
    eaten = min(desired, reserved)
    from_inventory = min(max(0, desired - eaten), max(0, agent.inv_get(Goods.food, 0)))
    if from_inventory:
        agent.inv_add(Goods.food, -from_inventory)
        eaten += from_inventory
    if reserved > eaten:
        agent.inv_add(Goods.food, reserved - eaten)
    if agent.is_trader and eaten < desired:
        for stock in (agent.inventory_foreign, agent.inventory_export):
            take = min(desired - eaten, max(0, stock[Goods.food.value]))
            stock[Goods.food.value] -= take
            eaten += take
            if eaten >= desired:
                break
    record_intake(agent, eaten)
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

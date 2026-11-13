"""Preflight and settle callback-free inventory transformations."""
import math
from goods import Goods
from food_inventory import EDIBLE, milli
from economy.actor_accounts import record
from economy.elite_cash import CashDistribution


def quantities(goods, *, outputs=False):
    result = {}
    for good, quantity in goods.items():
        good = good if isinstance(good, Goods) else Goods.__members__.get(str(good), str(good))
        quantity = float(quantity)
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError('Invalid inventory quantity')
        if outputs:
            quantity = int(quantity)  # Preserve the generic operator's existing yield rule.
        elif isinstance(good, Goods) and int(good) in EDIBLE and milli(quantity) / 1000 != quantity:
            raise ValueError('Input cannot be represented by food inventory')
        result[good] = result.get(good, 0) + quantity
    return result


def check_inputs(agent, inputs):
    for good, quantity in quantities(inputs).items():
        if agent.inv_get(good, 0) < quantity:
            return False, f'Missing input commodity: {good}'
    return True, 'OK'


def execute_inventory_transform(op, agent, region, turn, evaluation_event_id=None):
    try:
        inputs, outputs = quantities(op.input_goods), quantities(op.output_goods, outputs=True)
        fee = float(op.cash_cost)
        recipient = getattr(getattr(region, 'gov', None), 'agent', None)
        if not math.isfinite(fee) or fee < 0 or agent.cash < fee:
            raise ValueError('Insufficient cash or invalid operator fee')
        if fee and recipient is None:
            raise ValueError('operator_fee_requires_government_recipient')
        ok, reason = check_inputs(agent, inputs)
        if not ok:
            raise ValueError(reason)
    except (ValueError, TypeError, OverflowError) as error:
        return {'success': False, 'reason': str(error)}
    if fee:
        payment = CashDistribution(region, turn, 'operator_fee', 'operator_fee', {'operator': op.id})
        payment.debit(agent, fee, source_writer=__name__)
        payment.credit(recipient, fee, source_writer=__name__)
        payment.finish()
        from run_trace import emit
        emit(region, kind='elite_operator_fee', record_class='transfer', phase='labor',
             subject={'type': 'agent', 'id': agent.id}, metric_id='finance.operator_fee',
             unit=region.home_currency, after=fee,
             inputs={'operator': op.id, 'recipient_id': recipient.id},
             cause_event_ids=[evaluation_event_id] if evaluation_event_id else None)
    for good, quantity in inputs.items():
        agent.inv_add(good, -quantity)
        record(region, 'input_consumed', turn=turn, payer_id=agent.id,
               good=good, quantity=quantity, detail={'operator': op.id})
    for good, quantity in outputs.items():
        agent.inv_add(good, quantity)
        record(region, 'production', turn=turn, recipient_id=agent.id,
               good=good, quantity=quantity, detail={'operator': op.id})
    return {'success': True, 'yield': {getattr(g, 'name', str(g)): q for g, q in outputs.items()}}

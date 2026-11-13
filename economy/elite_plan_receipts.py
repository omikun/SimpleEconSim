"""Advance firm plans from source-owned settled events, independent of trace history."""


def observe_receipt(region, event):
    planner = getattr(region, 'elite_planner', None)
    if planner is None:
        return
    actors = {event['payer_id'], event['recipient_id']}
    for actor_id in actors:
        plan = planner._active_plans.get(actor_id)
        if not plan or plan.get('kind') != 'production_chain' or plan['status'] in ('completed', 'cancelled'):
            continue
        if event['id'] <= plan.get('last_receipt', 0) or event['turn'] < plan['created_turn']:
            continue
        plan['last_receipt'] = event['id']
        if event['kind'] == 'spot_sale':
            if actor_id == event['payer_id'] and event['good'] == plan['input_good']:
                detail = event['detail']
                if detail.get('plan_id') == plan['plan_id'] and detail.get('step_id') == plan['cursor']:
                    plan['input_filled'] += event['quantity']
                    plan['inputs_remaining'] = plan.get('inputs_remaining', 0) + event['quantity']
                    plan['input_cost'] += event['amount']
                    if plan['input_filled'] >= plan['purchase_quantity']:
                        plan['status'] = 'waiting_work'
            elif actor_id == event['recipient_id'] and event['good'] == plan['output_good']:
                # Sell opening inventory first; it is not newly planned output.
                opening = min(plan['opening_outputs'], event['quantity'])
                plan['opening_outputs'] -= opening
                planned = min(event['quantity'] - opening, plan['output_produced'] - plan['output_sold'])
                plan['output_sold'] += max(0, planned)
                if event['quantity']:
                    plan['sale_receipts'] += event['detail'].get('cash_receipt', event['amount']) * max(0, planned) / event['quantity']
        elif event['kind'] == 'input_consumed' and actor_id == event['payer_id'] and event['good'] == plan['input_good']:
            plan['inputs_remaining'] = max(0, plan.get('inputs_remaining', 0) - event['quantity'])
        elif event['kind'] == 'production' and actor_id == event['recipient_id'] and event['good'] == plan['output_good']:
            plan['output_produced'] += event['quantity']
        elif event['kind'] == 'wage' and actor_id == event['payer_id']:
            plan['wages_paid'] += event['amount']
        plan['review_turn'] = event['turn'] + 1
        if (event['kind'] == 'spot_sale' and event['recipient_id'] == actor_id
                and event['good'] == plan['output_good']
                and plan['cursor'] == len(plan['steps']) - 1 and plan['output_produced'] > 0
                and plan['output_sold'] >= plan['output_produced']
                and plan.get('inputs_remaining', 0) < plan.get('input_per_slot', float('inf'))
                and plan['input_filled'] >= plan['purchase_quantity']):
            plan.update(status='completed', completed_turn=event['turn'])

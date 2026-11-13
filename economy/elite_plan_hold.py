"""One-turn zero-input commitments, owned alongside production chains."""
from economy.production_math import output_units


def hold_reason(state):
    required = state.input_per_slot * state.slots
    if state.inputs >= required:
        return 'WAIT_INPUT', 'existing_inputs_cover_work'
    if state.demand <= 0:
        return 'DECLINE_INPUT', 'no_recent_funded_demand'
    if state.inputs + state.supply < state.input_per_slot:
        return 'DECLINE_INPUT', 'no_complete_batch_available'
    shortage = max(0, state.input_per_slot - state.inputs)
    if state.cash < shortage * state.input_price + state.payroll + state.liabilities:
        return 'DECLINE_INPUT', 'unaffordable_without_reserved_payroll'
    units = min(state.demand, output_units(state.slots, state.output_per_slot) * state.chance)
    if units * state.output_price <= required * state.input_price:
        return 'DECLINE_INPUT', 'nonpositive_material_contribution'
    return None


def hold_action(plan):
    return {'action_taken': plan['action'], 'details': {
        'plan_id': plan['plan_id'], 'reason': plan['reason'], 'input_quantity': 0}}


def create_hold(planner, firm, region, turn, state, choice):
    sequence = getattr(planner, '_next_plan_id', 1)
    planner._next_plan_id = sequence + 1
    action, reason = choice
    plan = dict(kind='production_hold', version=1, plan_id=f'{region.name}:{firm.id}:{sequence}',
                action=action, reason=reason, status='holding', firm_id=firm.id,
                deadline=turn, review_turn=turn + 1, input_good=state.input_good,
                signature=state.signature, limit_price=state.input_price)
    planner._active_plans[firm.id] = plan
    return hold_action(plan)

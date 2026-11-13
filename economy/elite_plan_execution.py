"""Firm plan ownership and integration with ordinary supply and market phases."""
from dataclasses import replace, asdict
from world_config import elite_planning_for, gameplay_flags_for
from economy.elite_planning_state import capture_planning_state, derive_goal
from economy.elite_plan_search import plan_goal


def planning_enabled(region):
    flags = gameplay_flags_for(region)
    return flags.elite_planning and flags.local_market and flags.production


def prepare_turn(regions, turn, settings):
    if settings.mode == 'off':
        return
    field = '_trace_elite_budget' if settings.mode == 'shadow' else '_elite_planning_budget'
    previous = getattr(regions[0], field, {}) if regions else {}
    firms = sorted((r.name, a.id) for r in regions if planning_enabled(r)
                   for a in r.agents if a.is_corporation and a.alive)
    start = previous.get('cursor', 0) % max(1, len(firms))
    ordered = firms[start:] + firms[:start]
    remaining, allocations, admitted = settings.world_max_states, {}, 0
    for key in ordered:
        allocations[key] = min(settings.max_states, remaining)
        remaining -= allocations[key]
        admitted += allocations[key] > 0
    budget = {'turn': turn, 'allocations': allocations, 'expanded': 0,
              'cursor': (start + admitted) % max(1, len(firms))}
    for region in regions:
        setattr(region, field, budget)


def search_firm(firm, region, turn):
    settings = elite_planning_for(region)
    field = '_trace_elite_budget' if settings.mode == 'shadow' else '_elite_planning_budget'
    budget = getattr(region, field, None)
    if not budget or budget['turn'] != turn:
        prepare_turn([region], turn, settings)
        budget = getattr(region, field)
    allowed = budget['allocations'].get((region.name, firm.id), 0)
    if not allowed:
        return None, None, 'world_budget_exhausted'
    # Claim this turn's allocation once even if novelty invokes planning again.
    budget['allocations'][region.name, firm.id] = 0
    try:
        state = capture_planning_state(firm, region, turn, settings)
        goal = derive_goal(state)
        if goal is None:
            return state, None, 'no_input_shortage'
        result = plan_goal(state, goal, replace(settings, max_states=allowed))
        budget['expanded'] += result.expanded
        return state, result, result.reason
    except ValueError as error:
        return None, None, str(error)


def review_plan(planner, firm, region, turn):
    settings = elite_planning_for(region)
    if settings.mode == 'off' or not planning_enabled(region) or not getattr(firm, 'is_corporation', False):
        return None
    existing = planner._active_plans.get(firm.id)
    if (existing and existing.get('kind') == 'production_hold' and settings.mode == 'active'
            and existing['deadline'] >= turn and existing['status'] == 'holding'):
        from economy.elite_plan_hold import hold_action
        return hold_action(existing)
    if existing and existing.get('kind') == 'production_chain' and settings.mode == 'active':
        if existing['status'] not in ('completed', 'cancelled'):
            return review_existing(existing, firm, region, turn)
    elif existing and existing.get('proposal_id') is not None:
        proposal = next((p for p in getattr(region, 'supply_proposals', ())
                         if p['id'] == existing['proposal_id']), None)
        if proposal and proposal['status'] in ('proposed', 'countered'):
            return None
    state, result, reason = search_firm(firm, region, turn)
    from economy.elite_plan_hold import hold_reason, create_hold
    hold = hold_reason(state) if state else None
    from run_trace import emit
    emit(region, kind='elite_production_plan', record_class='decision',
         subject={'type': 'agent', 'id': firm.id}, metric_id='ai.elite_economic_decision',
         unit='plan', after=result.status if result else 'unsupported',
         inputs={'mode': settings.mode, 'reason': hold[1] if hold else reason,
                 'snapshot': asdict(state) if state else None,
                 'search': asdict(result) if result else None})
    if settings.mode == 'active' and hold:
        return create_hold(planner, firm, region, turn, state, hold)
    if settings.mode == 'active' and result and result.steps:
        sequence = getattr(planner, '_next_plan_id', 1)
        planner._next_plan_id = sequence + 1
        plan = dict(kind='production_chain', version=1, plan_id=f'{region.name}:{firm.id}:{sequence}',
            firm_id=firm.id, created_turn=turn, review_turn=turn + 1,
            deadline=turn + settings.horizon, status='ready', cursor=0,
            steps=[asdict(step) for step in result.steps], signature=state.signature,
            input_good=state.input_good, output_good=state.output_good,
            reserve=state.payroll + state.liabilities, opening_outputs=state.outputs,
            inputs_remaining=state.inputs, input_per_slot=state.input_per_slot,
            output_produced=0, output_sold=0, input_cost=0, sale_receipts=0, wages_paid=0,
            last_receipt=0, retries=0, forecast=asdict(result))
        set_step(plan, firm)
        planner._active_plans[firm.id] = plan
        return plan_action(plan)
    return None


def set_step(plan, firm):
    step = plan['steps'][plan['cursor']]
    plan.update(purchase_quantity=step['quantity'], input_filled=0,
                target_stock=firm.inv_get(plan['input_good'], 0) + step['quantity'],
                limit_price=step['limit_price'], pending_order=None,
                status='ready' if step['quantity'] else 'waiting_sale')


def plan_action(plan):
    return {'action_taken': 'PRODUCTION_PLAN', 'details': {
        'plan_id': plan['plan_id'], 'cursor': plan['cursor'], 'status': plan['status']}}


def review_existing(plan, firm, region, turn):
    from economy.elite_plan_orders import current_signature
    if (turn > plan['deadline'] or not firm.alive
            or plan['signature'] != current_signature(firm, region)):
        plan.update(status='cancelled', reason='deadline_or_changed_firm', review_turn=turn)
        return plan_action(plan)
    if turn < plan['review_turn']:
        return plan_action(plan)
    if plan['input_filled'] >= plan['purchase_quantity'] and plan['cursor'] < len(plan['steps']) - 1:
        plan['cursor'] += 1
        set_step(plan, firm)
    elif plan['purchase_quantity'] > plan['input_filled']:
        plan['retries'] += 1
        if plan['retries'] > elite_planning_for(region).replans:
            plan.update(status='cancelled', reason='input_fill_retry_limit')
    plan['review_turn'] = turn + 1
    return plan_action(plan)


def maintain_plans(planner, region, turn):
    """Cancel orphaned/disabled instructions while actual contracts still settle."""
    by_id = {a.id: a for a in region.agents if a.alive}
    enabled = planning_enabled(region) and elite_planning_for(region).mode == 'active'
    for ident, plan in planner._active_plans.items():
        if plan.get('kind') in ('production_chain', 'production_hold') and plan['status'] not in ('completed', 'cancelled'):
            from economy.elite_plan_orders import current_signature
            if (plan.get('kind') == 'production_hold' and enabled and ident in by_id
                    and turn > plan['deadline'] and current_signature(by_id[ident], region) == plan['signature']):
                plan.update(status='review_due', reason='hold_review_due')
            elif (not enabled or ident not in by_id or turn > plan['deadline']
                    or current_signature(by_id[ident], region) != plan['signature']):
                plan.update(status='cancelled', reason='disabled_exit_deadline_or_changed_firm', review_turn=turn)

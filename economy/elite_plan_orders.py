"""Data-only plan intents replace ordinary input bids; the market settles them."""
from world_config import elite_planning_for


def active_plan(region, actor):
    from economy.elite_plan_execution import planning_enabled
    if elite_planning_for(region).mode != 'active' or not planning_enabled(region):
        return None
    planner = getattr(region, 'elite_planner', None)
    plan = getattr(planner, '_active_plans', {}).get(actor.id)
    return plan if (plan and plan.get('kind') in ('production_chain', 'production_hold')
                    and plan['status'] not in ('completed', 'cancelled')
                    and plan['deadline'] >= getattr(region, '_last_turn', 0)) else None


def spendable_cash(region, actor):
    plan = active_plan(region, actor)
    reserve = cash_reserve(actor, region) if plan else 0
    return max(0, actor.cash - reserve)


def cash_reserve(actor, region):
    from labor_contract import preview_labor_agreement
    payroll = sum(max(0, preview_labor_agreement(w, actor).pay_rate) for w in actor.employees
                  if w.alive and not w.is_striking and not w.in_revolt)
    claims = sum(amount for _, amount in scheduled_obligations(actor, region, getattr(region, '_last_turn', 0)))
    return payroll + max(0, float(getattr(actor, 'wage_arrears_balance', 0))) + claims


def scheduled_obligations(actor, region, turn):
    from world_config import gameplay_flags_for
    flags = gameplay_flags_for(region)
    return tuple((max(turn, o.due_turn), max(0, float(o.balance)) *
                  (1 + max(0, o.interest_rate) if o.last_accrued_turn < max(turn, o.due_turn) else 1))
                 for o in getattr(region, 'cash_obligations', ())
                 if o.debtor_id == actor.id and o.status == 'active'
                 and (o.origin != 'rent' or flags.land_rent)
                 and (o.origin != 'advance' or flags.crop_credit))


def input_bid(region, actor, good, *, submitted=False):
    plan = active_plan(region, actor)
    if not plan or getattr(good, 'name', str(good)) != plan['input_good']:
        return None
    turn = getattr(region, '_last_turn', 0)
    if plan['kind'] == 'production_hold':
        return 0
    if getattr(actor, 'loans', ()):
        plan.update(status='cancelled', reason='financing_changed')
        return 0
    if (plan['deadline'] < turn or plan.get('signature') != current_signature(actor, region)
            or plan['status'] not in ('ready', 'submitted', 'waiting_input')
            or (plan.get('submission_turn') == turn and not submitted)):
        return 0
    missing = max(0, plan['target_stock'] - actor.inv_get(good, 0))
    quantity = min(plan['purchase_quantity'] - plan['input_filled'], missing)
    cash = min(max(0, getattr(actor, 'remainingCash', actor.cash)), spendable_cash(region, actor))
    return max(0, int(min(quantity, cash // plan['limit_price'])))


def current_signature(actor, region):
    recipe = region.recipes.get(actor.output, {})
    workers = tuple(w.id for w in actor.employees if getattr(w, 'alive', True)
                    and not w.is_striking and not w.in_revolt
                    and w.id not in getattr(region, 'pollution_revolt_ids', ()))
    return (actor.output.name, getattr(recipe.get('input'), 'name', None), recipe.get('numInput'),
            recipe.get('production'), workers,
            max(0, getattr(actor, 'machinery_level', 1) - getattr(actor, 'broken_machinery', 0)),
            tuple(sorted(a.id for a in region.agents if getattr(a, 'company_owned', None) is actor)),
            getattr(actor, 'wage', 0), getattr(actor, 'shift_hours', 8))


def attach_order(region, actor, good, row, turn):
    row['order_id'] = f'{region.name}:{turn}:{actor.id}:{good.name}:buy'
    plan = active_plan(region, actor)
    if plan and good.name == plan['input_good']:
        row.update(plan_id=plan['plan_id'], step_id=plan.get('cursor', 0))
        plan.update(submission_turn=turn, status='waiting_input', pending_order=row['order_id'])


def cap_limit(region, actor, good, quantity, limit):
    plan = active_plan(region, actor)
    if not plan or not quantity:
        return limit
    limit = min(limit, spendable_cash(region, actor) / quantity)
    return min(limit, plan['limit_price']) if good.name == plan['input_good'] else limit

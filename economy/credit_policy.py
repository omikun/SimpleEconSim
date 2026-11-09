"""Common profitability and temporary-loss rules for automatic bank credit."""

from __future__ import annotations


MAX_UNPROFITABLE_BORROW_TURNS = 20
PROFITABILITY_LOOKBACK_TURNS = 3


def actor_result(region, actor_id):
    """Return a recent average operating result, excluding loan proceeds.

    Corporate results use the existing production account's recorded operating
    result. For people and other non-corporate actors, earnings from wages and
    sales are compared with market purchases and recorded household costs.
    This is an intentionally modest cash-profit proxy; it is not a full accrual
    income statement.
    """
    history = list(getattr(region, 'actor_account_history', ()))
    history.extend(getattr(region, 'actor_turn_accounts', ()))
    by_turn = {}
    for row in history:
        if int(row.get('actor_id', -1)) != int(actor_id):
            continue
        turn = int(row.get('turn', -1))
        if turn >= 0:
            by_turn[turn] = row
    recent = [by_turn[turn] for turn in sorted(by_turn)[-PROFITABILITY_LOOKBACK_TURNS:]]
    if not recent:
        return None, 0
    values = [float(row.get('credit_operating_result', 0.0)) for row in recent]
    return sum(values) / len(values), len(recent)


def assessment(region, actor, turn):
    """Describe whether this actor may borrow at this turn."""
    if getattr(actor, 'is_government', False):
        return {'allowed': True, 'profitable': True, 'result': None,
                'borrow_turns_used': 0,
                'borrow_turns_remaining': MAX_UNPROFITABLE_BORROW_TURNS,
                'reason': 'sovereign_fiscal_financing'}

    result, observations = actor_result(region, actor.id) if region is not None else (None, 0)
    profitable = result is not None and result > 1e-9
    used = max(0, int(getattr(actor, 'credit_unprofitable_borrow_turns', 0)))
    same_turn = getattr(actor, 'credit_last_unprofitable_borrow_turn', None) == int(turn)
    if profitable:
        return {'allowed': True, 'profitable': True, 'result': result,
                'observations': observations, 'borrow_turns_used': 0,
                'borrow_turns_remaining': MAX_UNPROFITABLE_BORROW_TURNS,
                'reason': 'recent_operating_profit'}
    allowed = same_turn or used < MAX_UNPROFITABLE_BORROW_TURNS
    return {'allowed': allowed, 'profitable': False, 'result': result,
            'observations': observations, 'borrow_turns_used': used,
            'borrow_turns_remaining': max(0, MAX_UNPROFITABLE_BORROW_TURNS - used),
            'reason': ('temporary_loss_window' if allowed
                       else 'unprofitable_credit_window_exhausted')}


def record_borrow(region, actor, turn, result):
    """Count at most one loss-financed borrowing turn per actor per turn."""
    if result.get('profitable', False) or getattr(actor, 'is_government', False):
        actor.credit_unprofitable_borrow_turns = 0
        return
    turn = int(turn)
    if getattr(actor, 'credit_last_unprofitable_borrow_turn', None) == turn:
        return
    actor.credit_unprofitable_borrow_turns = (
        max(0, int(getattr(actor, 'credit_unprofitable_borrow_turns', 0))) + 1)
    actor.credit_last_unprofitable_borrow_turn = turn


def record_turn_result(actor, result):
    """Reset the temporary-loss counter once the actor becomes profitable."""
    if float(result) > 1e-9:
        actor.credit_unprofitable_borrow_turns = 0

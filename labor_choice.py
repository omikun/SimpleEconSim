"""Shared, side-effect-free job offer evaluation and employment mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LaborDecision:
    worker_id: int
    firm_id: int
    turn: int
    accepted: bool
    reason: str
    reservation_wage: float
    offered_wage: float
    outside_food_estimate: float
    cash_due_estimate: float = 0.0


def _outside_access(worker: Any, region: Any) -> float:
    """Estimate named, usable subsistence access."""
    from livelihood_access import effective_access
    return effective_access(worker, region, 'commons_food')


def evaluate_offer(worker: Any, firm: Any, region: Any, turn: int,
                   wage: float | None = None, tightness: float | None = None) -> LaborDecision:
    """Return whether a worker accepts an offer without mutating simulation state."""
    from goods import Goods
    from region_labor import calculate_labor_market_tightness, evaluate_worker_reservation_wage

    offer = max(0.0, float(getattr(firm, 'wage', 0.0) if wage is None else wage))
    food_price = float(getattr(region, 'recipes', {}).get(Goods.food, {}).get('price', 1.0))
    outside_access = _outside_access(worker, region)
    outside_food = 4.0 * outside_access
    from livelihood_access import due_cash_for
    due_cash = due_cash_for(worker.id, region, turn)
    market_tightness = (calculate_labor_market_tightness(region)
                        if tightness is None else max(0.0, float(tightness)))
    base = evaluate_worker_reservation_wage(worker, region, market_tightness)
    reservation = max(
        0.75 * food_price,
        base + 0.5 * food_price * outside_access
        - min(0.4 * base, 0.05 * max(0.0, due_cash)),
    )

    reason = 'accepted'
    if (not getattr(worker, 'alive', True) or getattr(worker, 'is_trader', False)
            or getattr(worker, 'is_government', False) or getattr(worker, 'is_corporation', False)
            or getattr(worker, 'is_lord', False) or getattr(worker, 'in_workhouse', False)):
        reason = 'unavailable'
    elif getattr(worker, 'employer', None) not in (None, firm):
        reason = 'unavailable'
    elif not getattr(firm, 'alive', True) or not getattr(firm, 'is_corporation', False):
        reason = 'unavailable'
    elif len(getattr(firm, 'employees', [])) >= int(getattr(firm, 'max_employees', 0)):
        reason = 'no_vacancy'
    elif offer <= 0.0 or float(getattr(firm, 'cash', 0.0)) < offer:
        reason = 'unfunded'
    elif offer + 1e-9 < reservation:
        reason = 'insufficient_wage'

    return LaborDecision(
        worker_id=int(worker.id), firm_id=int(firm.id), turn=int(turn),
        accepted=(reason == 'accepted'), reason=reason,
        reservation_wage=reservation, offered_wage=offer,
        outside_food_estimate=outside_food, cash_due_estimate=max(0.0, due_cash),
    )


def attach_worker(worker: Any, firm: Any, turn: int, decision: LaborDecision) -> bool:
    """Apply a previously accepted offer, keeping both employment references aligned."""
    if (not decision.accepted or decision.worker_id != worker.id
            or decision.firm_id != firm.id or decision.turn != turn):
        return False
    if getattr(worker, 'employer', None) is firm:
        return worker in getattr(firm, 'employees', [])
    if (not getattr(worker, 'alive', True) or not getattr(firm, 'alive', True)
            or getattr(worker, 'in_workhouse', False)
            or len(getattr(firm, 'employees', [])) >= int(getattr(firm, 'max_employees', 0))
            or float(getattr(firm, 'cash', 0.0)) < decision.offered_wage):
        return False

    old_employer = getattr(worker, 'employer', None)
    if old_employer is not None:
        old_employees = getattr(old_employer, 'employees', [])
        if worker in old_employees:
            old_employees.remove(worker)
    if worker not in firm.employees:
        firm.employees.append(worker)
    worker.employer = firm
    worker.hired_at = turn
    worker.wage = decision.offered_wage
    worker.shift_hours = getattr(firm, 'shift_hours', 8.0)
    worker.output = firm.output
    worker.last_career_switch = turn
    return True

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
    from foraging import BASE_FORAGE_YIELD
    fertility = float(getattr(region, 'terrain', {}).get(Goods.food, 1.0))
    outside_food = (min(4.0, float(max(1, int(BASE_FORAGE_YIELD * outside_access * fertility))))
                    if outside_access > 0 else 0.0)
    from livelihood_access import due_cash_for
    due_cash = due_cash_for(worker.id, region, turn)
    market_tightness = (calculate_labor_market_tightness(region)
                        if tightness is None else max(0.0, float(tightness)))
    base = evaluate_worker_reservation_wage(worker, region, market_tightness)
    reservation = max(
        0.75 * food_price,
        base + 0.5 * food_price * outside_access
        - min(0.4 * base, 0.05 * max(0.0, due_cash)),
        outside_food * food_price
        - min(0.25 * outside_food * food_price, 0.05 * max(0.0, due_cash)),
    )

    reason = 'accepted'
    if (not getattr(worker, 'alive', True) or getattr(worker, 'is_trader', False)
            or getattr(worker, 'is_government', False) or getattr(worker, 'is_corporation', False)
            or getattr(worker, 'is_lord', False) or getattr(worker, 'in_workhouse', False)
            or getattr(worker, 'social_class', None) == 'constable'
            or getattr(worker, 'military_unit_id', None)):
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


def apply_career_switch(region: Any, worker: Any, new_output: Any, turn: int, *,
                        kind: str = 'career_switch', reason: str = 'career_switch',
                        record_class: str = 'decision', formula_id: str | None = None,
                        inputs: dict | None = None,
                        constraints: dict | None = None) -> bool:
    """Authoritative occupation mutation with tenure tracking and causal trace emission."""
    from goods import Goods
    old_output = getattr(worker, 'output', None)
    old_name = getattr(old_output, 'name', str(old_output)) if old_output is not None else 'none'
    new_name = getattr(new_output, 'name', str(new_output)) if new_output is not None else 'none'
    prev_switch_turn = int(getattr(worker, 'last_career_switch', 0))
    prior_tenure = max(0, int(turn) - prev_switch_turn)
    changed = (old_output != new_output)
    if changed and old_output not in (None, Goods.none, Goods.gov) and hasattr(worker, 'mem_push'):
        worker.mem_push('mem_career_history', old_name)
    worker.output = new_output
    worker.last_career_switch = int(turn)
    if changed and region is not None:
        from run_trace import emit
        age = worker.age(turn) if callable(getattr(worker, 'age', None)) else 0
        payload = {
            'old_profession': old_name,
            'new_profession': new_name,
            'reason': reason,
            'age': int(age),
            'prior_tenure': prior_tenure,
        }
        if inputs:
            payload.update(inputs)
        emit(region, kind=kind, record_class=record_class,
             subject={'type': 'agent', 'id': worker.id,
                      'tile': getattr(region, 'name', 'unknown')},
             metric_id='labor.career_choice', unit='occupation',
             before=old_name, after=new_name,
             formula_id=formula_id, inputs=payload,
             constraints=constraints)
    return changed


def attach_worker(worker: Any, firm: Any, turn: int, decision: LaborDecision,
                  region: Any = None) -> bool:
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
    apply_career_switch(
        region, worker, firm.output, turn,
        kind='firm_hire_career_switch',
        reason='hired_by_firm',
        record_class='outcome',
        formula_id='labor.firm_hire_attachment.v1',
        inputs={
            'firm_id': firm.id,
            'offered_wage': decision.offered_wage,
            'reservation_wage': decision.reservation_wage,
        },
    )
    from labor_contract import ensure_labor_agreement
    agreement = ensure_labor_agreement(worker, firm, turn)
    agreement.start_turn = int(turn)
    agreement.hours = float(getattr(firm, 'shift_hours', 8.0))
    agreement.pay_rate = float(decision.offered_wage)
    agreement.pay_mode = 'scrip' if getattr(firm, 'pay_mode', 'cash') == 'scrip' else 'cash'
    return True


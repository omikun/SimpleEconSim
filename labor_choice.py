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

    is_occupation_change = (
        getattr(firm, 'output', None) not in (None, Goods.none)
        and getattr(worker, 'output', None) not in (None, Goods.none, getattr(firm, 'output', None))
    )
    is_dispossessed = (
        getattr(worker, 'social_class', None) == 'dispossessed'
        or getattr(worker, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0
    )
    is_acute_hunger = getattr(worker, 'hungry_steps', 0) >= 3
    hurdle_mult, min_cooldown, age_factor = career_switch_hurdle_and_cooldown(
        worker, turn, is_emergency=(is_dispossessed or is_acute_hunger)
    )
    if is_occupation_change and not (is_dispossessed or is_acute_hunger) and age_factor > 0.0:
        reservation *= max(1.0, min(2.5, hurdle_mult * 0.90))

    last_switch = int(getattr(worker, 'last_career_switch', 0))
    turns_since_switch = int(turn) - last_switch
    existing_employees = [e for e in getattr(firm, 'employees', []) if e is not worker]
    required_payroll = len(existing_employees) * float(getattr(firm, 'wage', offer)) + offer

    reason = 'accepted'
    if (not getattr(worker, 'alive', True) or getattr(worker, 'is_trader', False)
            or getattr(worker, 'is_government', False) or getattr(worker, 'is_corporation', False)
            or getattr(worker, 'is_lord', False) or getattr(worker, 'in_workhouse', False)
            or getattr(worker, 'social_class', None) == 'constable'
            or getattr(worker, 'military_unit_id', None)):
        reason = 'unavailable'
    elif age_factor <= 0.0:
        reason = 'unavailable'
    elif getattr(worker, 'employer', None) not in (None, firm):
        reason = 'unavailable'
    elif (is_occupation_change and last_switch > 0
          and turns_since_switch < (2 if (is_dispossessed or is_acute_hunger) else min_cooldown)):
        reason = 'unavailable'
    elif not getattr(firm, 'alive', True) or not getattr(firm, 'is_corporation', False):
        reason = 'unavailable'
    elif len(getattr(firm, 'employees', [])) >= int(getattr(firm, 'max_employees', 0)):
        reason = 'no_vacancy'
    elif offer <= 0.0 or float(getattr(firm, 'cash', 0.0)) < required_payroll:
        reason = 'unfunded'
    elif offer + 1e-9 < reservation:
        reason = 'insufficient_wage'

    return LaborDecision(
        worker_id=int(worker.id), firm_id=int(firm.id), turn=int(turn),
        accepted=(reason == 'accepted'), reason=reason,
        reservation_wage=reservation, offered_wage=offer,
        outside_food_estimate=outside_food, cash_due_estimate=max(0.0, due_cash),
    )


def career_lifecycle_age(worker: Any, turn: int) -> int:
    """Return effective lifecycle age in turns for career mobility decisions.

    Founding adults (birth_round == 0) carry a deterministic founding_age_offset
    so the initial population spans young, prime-age, and senior workers without
    altering legacy birth_round == 0 checks elsewhere. Newborns (birth_round > 0)
    progress through childhood (0..13), youth entry (14..24), prime age (25..39),
    mid-career (40..54), and senior age (55+).
    """
    from game_time import agent_elapsed_years
    founding_offset = int(getattr(worker, 'founding_age_offset', 0))
    birth_round = int(getattr(worker, 'birth_round', 0))
    elapsed = agent_elapsed_years(birth_round, turn)
    if getattr(worker, 'is_native_child', False):
        return elapsed
    if birth_round < 0:
        return max(0, int(turn) - birth_round)
    if founding_offset > 0:
        return founding_offset + elapsed
    return 22 + elapsed


def career_mobility_age_factor(worker: Any, turn: int) -> float:
    """Empirical lifecycle occupational mobility multiplier phi(age).

    Calibrated to Topel & Ward (1992) and Kambourov & Manovskii (2008):
    - Childhood (<14, native-born): 0.0 (locked to household trade)
    - Youth exploration (14..24): 1.35 (highest occupational experimentation)
    - Prime working age (25..39): 0.75 (moderate mobility)
    - Mid-career (40..54): 0.35 (established craft attachment)
    - Senior / master (55+): 0.12 (near-zero voluntary switching)
    """
    age = career_lifecycle_age(worker, turn)
    is_native_child = bool(getattr(worker, 'is_native_child', False))
    if is_native_child and age < 14:
        return 0.0
    if age <= 24:
        return 1.35
    if age <= 39:
        return 0.75
    if age <= 54:
        return 0.35
    return 0.12


def career_switch_hurdle_and_cooldown(
    worker: Any, turn: int, *, is_emergency: bool = False
) -> tuple[float, int, float]:
    """Return (hurdle_multiplier, min_cooldown_turns, age_factor) for a worker."""
    age = career_lifecycle_age(worker, turn)
    age_factor = career_mobility_age_factor(worker, turn)
    if age_factor <= 0.0:
        return float('inf'), max(1, 14 - age), 0.0

    ambition = float(getattr(worker, 'ambition', 0.5))
    risk_tol = float(getattr(worker, 'risk_tolerance', 0.5))
    trait_mod = 0.85 + 0.30 * (1.0 - 0.5 * (ambition + risk_tol))
    required_gain = (0.28 / age_factor) * trait_mod
    hurdle_multiplier = 1.0 + required_gain

    birth_round = int(getattr(worker, 'birth_round', 0))
    last_switch = int(getattr(worker, 'last_career_switch', 0))
    # One-time low-friction youth entry when reaching apprenticeship age 14..16
    if getattr(worker, 'is_native_child', False) and 14 <= age <= 16 and last_switch <= birth_round:
        min_cooldown = 0
    elif age <= 24:
        min_cooldown = 4
    elif age <= 39:
        min_cooldown = 6
    elif age <= 54:
        min_cooldown = 8
    else:
        min_cooldown = 10
    return hurdle_multiplier, min_cooldown, age_factor


def occupational_tenure_turns(worker: Any, good: Any, turn: int) -> int:
    """Return effective occupational tenure turns in *good* (continuous or retained)."""
    if getattr(worker, 'output', None) == good:
        last_switch = int(getattr(worker, 'last_career_switch', 0))
        return max(0, int(turn) - last_switch)
    good_name = getattr(good, 'name', str(good))
    history = getattr(worker, 'memory', {}).get('mem_career_history', [])
    prior_episodes = sum(1 for entry in history if entry == good_name)
    return min(4, prior_episodes * 2)


def occupational_tenure_multiplier(worker: Any, good: Any, turn: int) -> float:
    """Return occupation-specific human capital productivity multiplier (Kambourov & Manovskii 2009).

    - Incumbent occupation: +2%/turn continuous tenure up to +20% (1.20x at 10+ turns).
    - Previously practiced occupation in mem_career_history: +4% per prior spell up to +8% (1.08x).
    - Unfamiliar occupation: 1.00x.
    """
    tenure = occupational_tenure_turns(worker, good, turn)
    if getattr(worker, 'output', None) == good:
        return 1.0 + min(0.20, 0.02 * max(0, tenure))
    return 1.0 + min(0.08, 0.02 * max(0, tenure))


def skill_tier_for_good(good: Any) -> int:
    """Classify goods into 3 occupational skill & capital tiers."""
    from goods import Goods
    if good in (Goods.food, Goods.wood):
        return 1
    if good == Goods.furniture:
        return 2
    return 3


def can_enter_independent_trade(
    worker: Any, good: Any, input_cost: float, turn: int = 0
) -> tuple[bool, str]:
    """Check whether *worker* can enter *good* as an independent sole producer."""
    if getattr(worker, 'output', None) == good:
        return True, 'incumbent'
    tier = skill_tier_for_good(good)
    if tier == 1:
        return True, 'tier1_open'
    if tier == 2:
        good_name = getattr(good, 'name', str(good))
        history = getattr(worker, 'memory', {}).get('mem_career_history', [])
        if good_name in history:
            return True, 'prior_craft_experience'
        cash = float(getattr(worker, 'cash', 0.0))
        prod = float(getattr(worker, 'productivity', 0.5))
        age = career_lifecycle_age(worker, turn)
        if cash >= max(6.0, input_cost * 2.0) and prod >= 0.55:
            return True, 'artisan_workshop_capital'
        if 14 <= age <= 24 and prod >= 0.62 and cash >= input_cost * 1.25:
            return True, 'youth_craft_apprenticeship'
        return False, 'artisan tool/skill barrier'
    return False, 'no independent local market'


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
    if not changed:
        return False
    if changed and old_output not in (None, Goods.none, Goods.gov) and hasattr(worker, 'mem_push'):
        worker.mem_push('mem_career_history', old_name)
    worker.output = new_output
    worker.last_career_switch = int(turn)
    if changed and region is not None:
        from run_trace import emit
        age = career_lifecycle_age(worker, turn)
        age_factor = career_mobility_age_factor(worker, turn)
        payload = {
            'old_profession': old_name,
            'new_profession': new_name,
            'reason': reason,
            'age': int(age),
            'age_mobility_factor': round(age_factor, 4),
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
    existing_employees = [e for e in getattr(firm, 'employees', []) if e is not worker]
    required_payroll = len(existing_employees) * float(getattr(firm, 'wage', decision.offered_wage)) + decision.offered_wage
    if (not getattr(worker, 'alive', True) or not getattr(firm, 'alive', True)
            or getattr(worker, 'in_workhouse', False)
            or len(getattr(firm, 'employees', [])) >= int(getattr(firm, 'max_employees', 0))
            or float(getattr(firm, 'cash', 0.0)) < required_payroll):
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

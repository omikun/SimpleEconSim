"""
labor_contract.py — Wage-labor contracts, shift length, machinery stock,
and Marxian surplus value extraction (c, v, s, s/v).

Under competitive market discipline, capitalists NEVER voluntarily reduce shift hours.
Shift hours are only reduced if legally mandated by state legislation (e.g. Ten-Hour Act).
"""

from __future__ import annotations
from dataclasses import dataclass
from goods import Goods
from labor_institutions import LaborAgreement

CUSTOMARY_SHIFT_HOURS = 8.0
MAX_LEGAL_SHIFT_HOURS = 16.0
MIN_SHIFT_HOURS = 4.0


@dataclass
class FirmLaborStats:
    """Surplus value accounting record for one firm in turn t."""
    firm_id: int
    num_workers: int
    shift_hours: float
    safety_investment: float
    machinery_level: int
    broken_machinery: int
    variable_capital: float    # v: wages paid
    constant_capital: float    # c: raw materials cost + safety costs
    gross_output_value: float  # W: market value of produced commodities
    surplus_value: float       # s = max(0, W - c - v)
    rate_of_exploitation: float # s / v (if v > 0 else 0.0)


def calculate_shift_multiplier(shift_hours: float) -> float:
    """Production output multiplier based on daily shift length.

    8.0 hours = 1.0 (customary baseline).
    Above 8.0 hours: linear gains with diminishing returns:
      10.0h -> 1.125x
      12.0h -> 1.25x
      14.0h -> 1.375x
      16.0h -> 1.50x
    Below 8.0 hours: linear drop-off clamped at 0.25x.
    """
    if shift_hours <= 0:
        return 0.0
    if shift_hours >= CUSTOMARY_SHIFT_HOURS:
        # Extra hours yield 50% marginal productivity due to worker fatigue
        extra = (shift_hours - CUSTOMARY_SHIFT_HOURS) / CUSTOMARY_SHIFT_HOURS
        return min(1.50, 1.0 + 0.5 * extra)
    return max(0.25, shift_hours / CUSTOMARY_SHIFT_HOURS)


def ensure_labor_agreement(worker, firm, turn=0):
    agreement = getattr(worker, 'labor_agreement', None)
    if agreement is None or not agreement.active or agreement.firm_id != firm.id:
        agreement = LaborAgreement(worker.id, firm.id, 'wage', int(turn), 0,
                                   float(getattr(firm, 'shift_hours', 8.0)),
                                   'scrip' if getattr(firm, 'pay_mode', 'cash') == 'scrip' else 'cash',
                                   float(getattr(firm, 'wage', 0.0)))
        worker.labor_agreement = agreement
    return agreement


def calculate_work_effort(hours, pace=1.0, nutrition=1.0, fatigue=0.0):
    """Bound actual output by hours, pace, nutrition, and accumulated fatigue."""
    hours = max(0.0, min(float(hours), MAX_LEGAL_SHIFT_HOURS))
    pace = max(0.25, min(2.0, float(pace)))
    nutrition = max(0.25, min(1.0, float(nutrition)))
    fatigue = max(0.0, min(4.0, float(fatigue)))
    hours_factor = calculate_shift_multiplier(hours)
    pace_factor = min(1.25, pace) + max(0.0, pace - 1.25) * 0.15
    fatigue_factor = max(0.4, 1.0 - fatigue * 0.20)
    return hours_factor * pace_factor * nutrition * fatigue_factor


def quit_job(worker, region, turn, penalty=0.0):
    """Detach voluntarily; an enacted quit-penalty law may create a named claim."""
    firm = getattr(worker, 'employer', None)
    if firm is None:
        return {'success': False, 'outcome': 'not employed'}
    law_active = getattr(region, 'labor_laws', {}).get('quit_penalty') == 'enacted'
    claim = None
    if law_active and penalty > 0:
        from livelihood_access import assess_obligation
        from labor_institutions import EnforcementCase
        claim = assess_obligation(region, worker.id, firm.id, 'quit_penalty', penalty,
                                  turn + 1)
        if claim is not None:
            cases = getattr(region, 'enforcement_cases', [])
            case_id = int(getattr(region, '_next_case_id', 1))
            region._next_case_id = case_id + 1
            cases.append(EnforcementCase(case_id, 'quit_penalty', worker.id, None,
                                         claim.id, turn, turn + 1))
            region.enforcement_cases = cases
    if worker in getattr(firm, 'employees', []):
        firm.employees.remove(worker)
    worker.employer = None
    from labor_choice import record_labor_status
    record_labor_status(region, worker, turn, before='employed', after='independent',
                        reason='quit_job', employer_before=firm)
    agreement = getattr(worker, 'labor_agreement', None)
    if agreement is not None:
        agreement.active = False
    event = {'turn': turn, 'worker_id': worker.id, 'firm_id': firm.id,
             'outcome': 'unpaid fine claim' if claim else 'lawful exit',
             'claim_id': claim.id if claim else None}
    region.labor_events = (getattr(region, 'labor_events', []) + [event])[-500:]
    return {'success': True, **event}


def enforce_legal_workday_caps(firm, region):
    """Clamps firm shift hours and safety investment to match legal mandates.

    Corps only reduce shift hours if binding legislation forces them.
    """
    cap = getattr(region, 'workday_cap', getattr(region, 'max_workday_hours', MAX_LEGAL_SHIFT_HOURS))
    current_shift = getattr(firm, 'shift_hours', CUSTOMARY_SHIFT_HOURS)
    if current_shift > cap:
        firm.shift_hours = cap

    # Propagate shift hours to all employees
    for emp in getattr(firm, 'employees', []):
        emp.shift_hours = firm.shift_hours
        agreement = ensure_labor_agreement(emp, firm)
        agreement.hours = float(firm.shift_hours)

    # Safety standards mandate
    mandate = getattr(region, 'safety_mandate', 0.0)
    current_safety = getattr(firm, 'safety_investment', 0.0)
    if current_safety < mandate:
        firm.safety_investment = mandate


def evaluate_firm_contracts(firm, region, t):
    """Step labor contract parameters for a corporate firm.

    Rule: Corps NEVER voluntarily reduce shift hours.
    They ratchet hours upward under competitive pressure up to the legal cap.
    """
    if not getattr(firm, 'is_corporation', False):
        return

    # First enforce any statutory legal maximums
    enforce_legal_workday_caps(firm, region)

    cap = getattr(region, 'workday_cap', getattr(region, 'max_workday_hours', MAX_LEGAL_SHIFT_HOURS))
    cur_shift = getattr(firm, 'shift_hours', CUSTOMARY_SHIFT_HOURS)

    # If below the legal cap, market competition drives shift expansion
    if cur_shift < cap:
        num_workers = len(getattr(firm, 'employees', []))
        payroll = num_workers * getattr(firm, 'wage', 1.0)
        # Pressure factors: low cash cushion, unfilled capacity, or profit drive
        if firm.cash < payroll * 4 or num_workers < getattr(firm, 'max_employees', 10):
            firm.shift_hours = min(cap, cur_shift + 0.5)

    # Ensure all employees share the firm's shift length
    for emp in getattr(firm, 'employees', []):
        emp.shift_hours = firm.shift_hours
        agreement = ensure_labor_agreement(emp, firm)
        agreement.hours = float(firm.shift_hours)


def record_surplus_value(firm, region, output_good, units_produced: int,
                         raw_inputs_cost: float, wages_paid: float) -> FirmLaborStats:
    """Record Marxian surplus value accounting for a corporate production run."""
    price = 1.0
    if hasattr(region, 'recipes') and output_good in region.recipes:
        price = region.recipes[output_good].get('price', 1.0)

    num_workers = len(getattr(firm, 'employees', []))
    shift_hours = getattr(firm, 'shift_hours', CUSTOMARY_SHIFT_HOURS)
    safety_inv = getattr(firm, 'safety_investment', 0.0)
    machinery = getattr(firm, 'machinery_level', 1)
    broken = getattr(firm, 'broken_machinery', 0)

    # Constant capital: raw material inputs + safety expenditures
    constant_capital = raw_inputs_cost + (safety_inv * num_workers)
    # Variable capital: living wages paid
    variable_capital = max(0.0, wages_paid)
    # Gross value of commodities produced
    gross_value = units_produced * price

    # Surplus value: s = max(0, W - c - v)
    surplus_value = max(0.0, gross_value - constant_capital - variable_capital)
    # Rate of exploitation: e = s / v
    rate_of_exploitation = (surplus_value / variable_capital) if variable_capital > 0.0 else 0.0

    stats = FirmLaborStats(
        firm_id=firm.id,
        num_workers=num_workers,
        shift_hours=shift_hours,
        safety_investment=safety_inv,
        machinery_level=machinery,
        broken_machinery=broken,
        variable_capital=variable_capital,
        constant_capital=constant_capital,
        gross_output_value=gross_value,
        surplus_value=surplus_value,
        rate_of_exploitation=rate_of_exploitation
    )

    firm.surplus_value_extracted = surplus_value
    firm.rate_of_exploitation = rate_of_exploitation
    firm._latest_labor_stats = stats
    return stats


def aggregate_tile_surplus(region) -> dict:
    """Compute aggregate surplus value and labor metrics across all firms on a tile."""
    firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
    if not firms:
        return {
            'avg_shift_hours': CUSTOMARY_SHIFT_HOURS,
            'avg_shift_hours_inputs': {
                'firms': [], 'weighted_shift_hours_sum': 0.0,
                'worker_count': 0, 'empty_value': CUSTOMARY_SHIFT_HOURS},
            'total_surplus_value': 0.0,
            'avg_rate_of_exploitation': 0.0,
            'exploitation_inputs': {
                'firms': [], 'total_surplus_value': 0.0,
                'total_variable_capital': 0.0, 'empty_value': 0.0},
            'total_machinery': 0,
            'total_broken_machinery': 0,
            'active_workers': 0,
        }

    total_workers = 0
    weighted_shifts = 0.0
    total_surplus = 0.0
    total_v = 0.0
    total_s = 0.0
    total_machinery = 0
    total_broken = 0
    shift_rows = []
    exploitation_rows = []

    for f in firms:
        w_count = len(getattr(f, 'employees', []))
        total_workers += w_count
        s_hours = getattr(f, 'shift_hours', CUSTOMARY_SHIFT_HOURS)
        weighted_shifts += s_hours * max(1, w_count)
        shift_rows.append({'firm_id': f.id, 'shift_hours': float(s_hours),
                           'worker_count': w_count,
                           'weight': max(1, w_count)})

        total_machinery += getattr(f, 'machinery_level', 1)
        total_broken += getattr(f, 'broken_machinery', 0)

        stats = getattr(f, '_latest_labor_stats', None)
        if stats:
            total_surplus += stats.surplus_value
            total_s += stats.surplus_value
            total_v += stats.variable_capital
            exploitation_rows.append({
                'firm_id': f.id, 'surplus_value': float(stats.surplus_value),
                'variable_capital': float(stats.variable_capital),
                'included_in_rate': True})
        else:
            total_surplus += getattr(f, 'surplus_value_extracted', 0.0)
            exploitation_rows.append({
                'firm_id': f.id,
                'surplus_value_extracted': float(
                    getattr(f, 'surplus_value_extracted', 0.0)),
                'included_in_rate': False,
                'exclusion_reason': 'latest_labor_stats_unavailable'})

    avg_shift = weighted_shifts / max(1, total_workers) if total_workers > 0 else CUSTOMARY_SHIFT_HOURS
    avg_exploitation = (total_s / total_v) if total_v > 0.0 else 0.0

    return {
        'avg_shift_hours': avg_shift,
        'avg_shift_hours_inputs': {
            'firms': shift_rows, 'weighted_shift_hours_sum': weighted_shifts,
            'worker_count': total_workers,
            'empty_value': CUSTOMARY_SHIFT_HOURS if total_workers == 0 else None},
        'total_surplus_value': total_surplus,
        'avg_rate_of_exploitation': avg_exploitation,
        'exploitation_inputs': {
            'firms': exploitation_rows, 'total_surplus_value': total_s,
            'total_variable_capital': total_v,
            'empty_value': 0.0 if total_v <= 0.0 else None},
        'total_machinery': total_machinery,
        'total_broken_machinery': total_broken,
        'active_workers': total_workers,
    }

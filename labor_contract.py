"""
labor_contract.py — Wage-labor contracts, shift length, machinery stock,
and Marxian surplus value extraction (c, v, s, s/v).

Under competitive market discipline, capitalists NEVER voluntarily reduce shift hours.
Shift hours are only reduced if legally mandated by state legislation (e.g. Ten-Hour Act).
"""

from __future__ import annotations
from dataclasses import dataclass
from goods import Goods

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


def enforce_legal_workday_caps(firm, region):
    """Clamps firm shift hours and safety investment to match legal mandates.

    Corps only reduce shift hours if binding legislation forces them.
    """
    cap = getattr(region, 'workday_cap', MAX_LEGAL_SHIFT_HOURS)
    current_shift = getattr(firm, 'shift_hours', CUSTOMARY_SHIFT_HOURS)
    if current_shift > cap:
        firm.shift_hours = cap

    # Propagate shift hours to all employees
    for emp in getattr(firm, 'employees', []):
        emp.shift_hours = firm.shift_hours

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

    cap = getattr(region, 'workday_cap', MAX_LEGAL_SHIFT_HOURS)
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
            'total_surplus_value': 0.0,
            'avg_rate_of_exploitation': 0.0,
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

    for f in firms:
        w_count = len(getattr(f, 'employees', []))
        total_workers += w_count
        s_hours = getattr(f, 'shift_hours', CUSTOMARY_SHIFT_HOURS)
        weighted_shifts += s_hours * max(1, w_count)

        total_machinery += getattr(f, 'machinery_level', 1)
        total_broken += getattr(f, 'broken_machinery', 0)

        stats = getattr(f, '_latest_labor_stats', None)
        if stats:
            total_surplus += stats.surplus_value
            total_s += stats.surplus_value
            total_v += stats.variable_capital
        else:
            total_surplus += getattr(f, 'surplus_value_extracted', 0.0)

    avg_shift = weighted_shifts / max(1, total_workers) if total_workers > 0 else CUSTOMARY_SHIFT_HOURS
    avg_exploitation = (total_s / total_v) if total_v > 0.0 else 0.0

    return {
        'avg_shift_hours': avg_shift,
        'total_surplus_value': total_surplus,
        'avg_rate_of_exploitation': avg_exploitation,
        'total_machinery': total_machinery,
        'total_broken_machinery': total_broken,
        'active_workers': total_workers,
    }

"""
labor_resistance.py — Wildcat strikes, collective withholding, Luddite sabotage,
and physical machinery replacement accounting for REGNUM.

Sabotage physically destroys machinery units that MUST be replaced and paid for
by the firm (cash + physical materials) before factory capacity can recover.
"""

from __future__ import annotations
from dataclasses import dataclass
from goods import Goods
from random_cache import rand

MACHINERY_REPLACEMENT_CASH = 120.0
MACHINERY_WOOD_REQUIRED = 2
MACHINERY_FURNITURE_REQUIRED = 1


@dataclass
class StrikeRecord:
    """Record of an active strike in a corporation."""
    firm_id: int
    turn_started: int
    num_strikers: int
    demand_hours: float
    demand_wage: float


def evaluate_strikes(region, t: int):
    """Evaluate firm-level strike actions and collective bargaining.

    Workers with high class consciousness and alienation vote to strike
    if shifts are grueling (>10h) or wages are below subsistence.
    """
    firms = [a for a in getattr(region, 'agents', [])
             if getattr(a, 'is_corporation', False) and len(getattr(a, 'employees', [])) > 0]

    for firm in firms:
        employees = firm.employees
        if not employees:
            continue

        # Count strike votes among workers
        votes_for_strike = 0
        for emp in employees:
            c = getattr(emp, 'class_consciousness', 0.0)
            alien = getattr(emp, 'alienation', 0.0)
            shift = getattr(emp, 'shift_hours', 8.0)

            # Threshold for collective militancy
            strike_pressure = c * 0.5 + alien * 0.4 + (0.3 if shift > 10.0 else 0.0)
            if strike_pressure > 0.55:
                votes_for_strike += 1

        strike_ratio = votes_for_strike / len(employees)

        # Majority strike vote triggers a walkout
        if strike_ratio >= 0.50:
            for emp in employees:
                emp.is_striking = True
            firm.is_on_strike = True

            # Firm response logic:
            # 1. Concession: If firm has high cash and wants to avoid shutdown, concede
            payroll = len(employees) * firm.wage
            if firm.cash > payroll * 6 and firm.shift_hours > 10.0:
                # Concede to shorter shift or slight wage increase
                firm.shift_hours = max(8.0, firm.shift_hours - 1.0)
                for emp in employees:
                    emp.shift_hours = firm.shift_hours
                    emp.is_striking = False
                firm.is_on_strike = False
        else:
            # Strike fizzles or breaks; workers return
            for emp in employees:
                if getattr(emp, 'is_striking', False):
                    # Starvation discipline forces workers back if hungry
                    if getattr(emp, 'hungry_steps', 0) > 0 or strike_ratio < 0.25:
                        emp.is_striking = False
            firm.is_on_strike = any(getattr(e, 'is_striking', False) for e in employees)


def evaluate_sabotage(region, t: int) -> int:
    """Evaluate nocturnal Luddite machine breaking in factories.

    When workers suffer extreme despair and alienation, or when strikes
    fail, clandestine saboteurs smash physical machinery.
    Returns total units of machinery destroyed across the tile.
    """
    firms = [a for a in getattr(region, 'agents', [])
             if getattr(a, 'is_corporation', False) and getattr(a, 'machinery_level', 1) > 0]
    if not firms:
        return 0

    total_smashed = 0
    for firm in firms:
        employees = getattr(firm, 'employees', [])
        if not employees:
            continue

        avg_despair = sum(getattr(e, 'despair', 0.0) for e in employees) / len(employees)
        avg_alien = sum(getattr(e, 'alienation', 0.0) for e in employees) / len(employees)
        has_strikes = getattr(firm, 'is_on_strike', False)

        # Sabotage risk rises with acute despair and crushed labor conditions
        sabotage_risk = avg_despair * 0.4 + avg_alien * 0.3 + (0.2 if has_strikes else 0.0)
        if sabotage_risk > 0.55 and rand.random() < (sabotage_risk * 0.30):
            # Physical machinery is destroyed!
            current_machinery = getattr(firm, 'machinery_level', 1)
            if current_machinery > 0:
                smashed = 1
                firm.machinery_level = max(0, current_machinery - smashed)
                firm.broken_machinery = getattr(firm, 'broken_machinery', 0) + smashed
                total_smashed += smashed

                # Sabotage boosts local protest energy
                if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
                    region.protest_energy_log[-1] = min(10.0, region.protest_energy_log[-1] + 1.2)

    return total_smashed


def repair_and_replace_machinery(firm, region, t: int):
    """Firms must physically replace and pay for broken machinery.

    Requires cash (MACHINERY_REPLACEMENT_CASH) + wood + furniture/tools.
    Conserves all money and commodities down to the penny.
    """
    broken = getattr(firm, 'broken_machinery', 0)
    if broken <= 0:
        return

    # Check if firm can afford to replace 1 machine
    if firm.cash < MACHINERY_REPLACEMENT_CASH:
        # Firm attempts to borrow from the bank to finance equipment replacement
        bank = getattr(region, 'bank', None)
        if bank is not None:
            bank.Borrow(t, firm, MACHINERY_REPLACEMENT_CASH - firm.cash)

    if firm.cash >= MACHINERY_REPLACEMENT_CASH:
        wood_avail = firm.inv_get(Goods.wood, 0)
        furn_avail = firm.inv_get(Goods.furniture, 0)

        # Purchase materials from local market if needed
        wood_cost = region.recipes.get(Goods.wood, {}).get('price', 3.0)
        furn_cost = region.recipes.get(Goods.furniture, {}).get('price', 10.0)

        needed_cash = MACHINERY_REPLACEMENT_CASH
        if wood_avail < MACHINERY_WOOD_REQUIRED:
            needed_cash += (MACHINERY_WOOD_REQUIRED - wood_avail) * wood_cost
        if furn_avail < MACHINERY_FURNITURE_REQUIRED:
            needed_cash += (MACHINERY_FURNITURE_REQUIRED - furn_avail) * furn_cost

        if firm.cash >= needed_cash:
            # Pay cash replacement fee to local artisans / carpenters (conserved)
            firm.cash -= needed_cash
            carpenters = [a for a in getattr(region, 'agents', [])
                          if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                          and getattr(a, 'output', None) in (Goods.wood, Goods.furniture)
                          and getattr(a, 'employer', None) is None]
            if carpenters:
                split = needed_cash / len(carpenters)
                for c in carpenters:
                    c.cash += split
            elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                region.gov.agent.cash += needed_cash
            else:
                firm.cash += needed_cash  # refund if no recipient exists

            # Deduct physical materials
            firm.inv_add(Goods.wood, -min(wood_avail, MACHINERY_WOOD_REQUIRED))
            firm.inv_add(Goods.furniture, -min(furn_avail, MACHINERY_FURNITURE_REQUIRED))

            # Machine is replaced and restored to service!
            firm.broken_machinery -= 1
            firm.machinery_level = getattr(firm, 'machinery_level', 0) + 1


def step_workplace_resistance(region, t: int) -> dict:
    """Run turn of strikes, sabotage, and machinery repairs on a tile."""
    evaluate_strikes(region, t)
    smashed = evaluate_sabotage(region, t)

    # Attempt repairs for all firms with broken machinery
    firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
    for f in firms:
        repair_and_replace_machinery(f, region, t)

    # Aggregate tile resistance metrics
    total_strikers = sum(1 for a in getattr(region, 'agents', [])
                         if getattr(a, 'is_striking', False) and getattr(a, 'alive', True))
    total_broken = sum(getattr(f, 'broken_machinery', 0) for f in firms)
    active_strikes = sum(1 for f in firms if getattr(f, 'is_on_strike', False))

    return {
        'strikers': total_strikers,
        'active_strikes': active_strikes,
        'smashed_this_turn': smashed,
        'broken_machinery': total_broken,
    }

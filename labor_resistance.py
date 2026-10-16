"""
labor_resistance.py — Wildcat strikes, collective withholding, Luddite sabotage,
and physical machinery replacement accounting for Call of Capital.

Sabotage physically destroys machinery units that MUST be replaced and paid for
by the firm (cash + physical materials) before factory capacity can recover.
"""

from __future__ import annotations
from goods import Goods
from random_cache import rand

MACHINERY_REPLACEMENT_CASH = 120.0
MACHINERY_WOOD_REQUIRED = 2
MACHINERY_FURNITURE_REQUIRED = 1


def evaluate_strikes(region, t: int):
    """Resolve organization and participation for every living corporation."""
    from collective_action import step_collectives
    step_collectives(region, t)


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
            bank.Borrow(t, firm, MACHINERY_REPLACEMENT_CASH - firm.cash,
                        trace_region=region)

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

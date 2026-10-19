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
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(
                        region, 'strike_machinery_repair', turn=t,
                        payer_id=firm.id, recipient_id=c.id, amount=split,
                        detail={'firm_id': firm.id, 'repair_cost': needed_cash})
            elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                region.gov.agent.cash += needed_cash
                from economy.actor_accounts import record as record_economic_event
                record_economic_event(
                    region, 'strike_machinery_repair', turn=t,
                    payer_id=firm.id, recipient_id=region.gov.agent.id,
                    amount=needed_cash,
                    detail={'firm_id': firm.id, 'repair_cost': needed_cash,
                            'recipient': 'treasury'})
            else:
                firm.cash += needed_cash  # refund if no recipient exists

            # Deduct physical materials
            firm.inv_add(Goods.wood, -min(wood_avail, MACHINERY_WOOD_REQUIRED))
            firm.inv_add(Goods.furniture, -min(furn_avail, MACHINERY_FURNITURE_REQUIRED))

            # Machine is replaced and restored to service!
            firm.broken_machinery -= 1
            firm.machinery_level = getattr(firm, 'machinery_level', 0) + 1


def record_workforce_availability(region, t: int):
    """Record employee hours available to each firm before production."""
    from run_trace import emit
    from labor_contract import MAX_LEGAL_SHIFT_HOURS

    trace = getattr(region, '_run_trace', None)
    if trace is None or getattr(region, '_collective_trace_clock', None) is None:
        return {}
    workforce_event_ids = {}
    collective_event_ids = {}
    for event in getattr(region, 'collective_log', ()):
        if event.get('turn') != t or event.get('trace_event_id') is None:
            continue
        collective_event_ids.setdefault(event.get('firm_id'), []).append(
            event['trace_event_id'])
    for firm in getattr(region, 'agents', ()):
        if not getattr(firm, 'is_corporation', False):
            continue
        employees = list(getattr(firm, 'employees', ()))
        working = [employee for employee in employees
                   if not getattr(employee, 'is_striking', False)
                   and not getattr(employee, 'in_revolt', False)]

        def scheduled_hours(employee):
            agreement = getattr(employee, 'labor_agreement', None)
            if (agreement is not None and getattr(agreement, 'active', False)
                    and getattr(agreement, 'firm_id', None) == firm.id):
                hours = float(agreement.hours)
            else:
                hours = float(getattr(employee, 'shift_hours',
                                      getattr(firm, 'shift_hours', 8.0)))
            return max(0.0, hours)

        worker_rows = []
        for employee in employees:
            hours = scheduled_hours(employee)
            status = ('striking' if getattr(employee, 'is_striking', False) else
                      'in_revolt' if getattr(employee, 'in_revolt', False) else
                      'available')
            worker_rows.append({'agent_id': employee.id, 'status': status,
                                'scheduled_hours': hours,
                                'effective_hours': min(MAX_LEGAL_SHIFT_HOURS, hours)
                                if status == 'available' else 0.0})
        scheduled_total = sum(row['scheduled_hours'] for row in worker_rows)
        capped_schedule_total = sum(min(MAX_LEGAL_SHIFT_HOURS, row['scheduled_hours'])
                                    for row in worker_rows)
        available_total = sum(row['effective_hours'] for row in worker_rows)
        cause_ids = collective_event_ids.get(firm.id, [])
        event_id = emit(
            region, kind='labor_workforce_availability', record_class='calculation',
            phase='local',
            subject={'type': 'agent', 'id': firm.id, 'tile': region.name},
            metric_id='labor.available_worker_hours', unit='hours',
            before=capped_schedule_total, after=available_total,
            formula_id='labor.workforce_availability.v1',
            cause_event_ids=cause_ids or None,
            inputs={'firm_id': firm.id,
                    'output_good': getattr(getattr(firm, 'output', None), 'name', None),
                    'employee_count': len(employees),
                    'working_employee_count': len(working),
                    'striking_employee_ids': [employee.id for employee in employees
                                              if getattr(employee, 'is_striking', False)],
                    'revolting_employee_ids': [employee.id for employee in employees
                                               if getattr(employee, 'in_revolt', False)],
                    'worker_hours': worker_rows,
                    'scheduled_worker_hours': scheduled_total,
                    'legally_capped_scheduled_worker_hours': capped_schedule_total,
                    'available_worker_hours': available_total,
                    'withheld_worker_hours': capped_schedule_total - available_total,
                    'wage': float(getattr(firm, 'wage', 0.0)),
                    'machinery_level': int(getattr(firm, 'machinery_level', 0)),
                    'broken_machinery': int(getattr(firm, 'broken_machinery', 0)),
                    'collective_event_ids': cause_ids})
        if event_id is not None:
            workforce_event_ids[firm.id] = event_id
    region._labor_workforce_event_ids = workforce_event_ids
    return workforce_event_ids


def step_workplace_resistance(region, t: int) -> dict:
    """Run turn of strikes, sabotage, and machinery repairs on a tile."""
    evaluate_strikes(region, t)
    smashed = evaluate_sabotage(region, t)

    # Attempt repairs for all firms with broken machinery
    firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
    for f in firms:
        repair_and_replace_machinery(f, region, t)

    workforce_event_ids = record_workforce_availability(region, t)

    # Aggregate tile resistance metrics
    total_strikers = sum(1 for a in getattr(region, 'agents', [])
                         if getattr(a, 'is_striking', False) and getattr(a, 'alive', True))
    total_broken = sum(getattr(f, 'broken_machinery', 0) for f in firms)
    active_strikes = sum(1 for f in firms if getattr(f, 'is_on_strike', False))
    striker_ids = [a.id for a in getattr(region, 'agents', [])
                   if getattr(a, 'is_striking', False)
                   and getattr(a, 'alive', True)]
    from run_trace import emit
    striker_history = getattr(region, 'strikers_log', ())
    emit(region, kind='labor_striker_count_calculation',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='labor.strikers', unit='people',
         before=striker_history[-1] if striker_history else None,
         after=total_strikers,
         formula_id='labor.count_active_strikers.v1',
         inputs={'striking_agent_ids': striker_ids,
                 'active_strike_count': active_strikes,
                 'firm_count': len(firms),
                 'broken_machinery': total_broken,
                 'machinery_smashed_this_turn': smashed})

    return {
        'strikers': total_strikers,
        'active_strikes': active_strikes,
        'workforce_event_ids': workforce_event_ids,
        'smashed_this_turn': smashed,
        'broken_machinery': total_broken,
    }

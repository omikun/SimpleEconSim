"""
Labor market, hiring, firm incorporation, and wage adjustment for a Region.
"""
from treasury_trace import begin_public_change, finish_public_change

from agent import Agent, seed_traits
from goods import Goods
from random_cache import rand
from labor_contract import evaluate_firm_contracts, calculate_shift_multiplier
from labor_choice import evaluate_offer, attach_worker


def cleanup_labor(region):
    """Clean up invalid employee/employer references."""
    living_set = set(region.agents)
    for a in region.agents:
        if a.employer and a.employer not in living_set:
            from labor_choice import record_labor_status
            record_labor_status(region, a, int(getattr(region, '_last_turn', 0) or 0),
                                before='employed', after='independent',
                                reason='employer_removed', employer_before=a.employer)
            a.employer = None
        if a.is_corporation:
            a.employees = [e for e in a.employees if e in living_set and e.employer == a]


def borrow_or_layoff(region, t):
    """Firms borrow to pay payroll or lay off workers if funds are insufficient."""
    for a in region.agents:
        if not a.is_corporation or len(a.employees) == 0:
            continue
        employees_before = len(a.employees)
        cash_before = float(a.cash)
        total_wage = len(a.employees) * a.wage
        payroll_required = total_wage
        liabilities_before = region.bank.total_liabilities
        if a.cash < total_wage:
            region.bank.Borrow(t, a, total_wage - a.cash, trace_region=region)
        while a.cash < total_wage and len(a.employees) > 0:
            e = a.employees.pop()
            e.employer = None
            agreement = getattr(e, 'labor_agreement', None)
            if agreement is not None:
                agreement.active = False
            from labor_choice import record_labor_status
            record_labor_status(region, e, t, before='employed',
                                after='independent', reason='payroll_layoff',
                                employer_before=a)
            total_wage = len(a.employees) * a.wage
        if len(a.employees) == 0 and a.cash <= 20.0:
            from region_finance import liquidate_wage_arrears
            liquidate_wage_arrears(region, t, a, reason='payroll_insolvency')
            a.is_corporation = False
            from run_trace import emit
            emit(region, kind='person_role_conversion', record_class='outcome',
                 phase='labor', subject={'type': 'tile/agent', 'id': str(a.id)},
                 metric_id='people.role', unit='role', before='corporation',
                 after='person', formula_id='labor.firm_dissolution.v1',
                 inputs={'agent_id': a.id, 'tile': region.name,
                         'cash': float(a.cash), 'employees': len(a.employees)})
            if a.owner:
                a.owner.company_owned = None
        from run_trace import emit
        emit(region, kind='corporate_payroll_funding_decision', record_class='outcome',
             subject={'type': 'tile', 'id': region.name, 'firm_id': a.id},
             metric_id='labor.payroll_funding', unit='workers',
             before=employees_before, after=len(a.employees),
             inputs={'cash_before': cash_before, 'cash_after': a.cash,
                     'wage': a.wage, 'payroll_required': payroll_required,
                     'bank_credit_received': region.bank.total_liabilities - liabilities_before,
                     'layoffs': employees_before - len(a.employees),
                     'firm_survives': bool(a.is_corporation)})


def incorporate(region, t):
    """Found new corporations by sole proprietors with sufficient wealth."""
    new_companies = []
    for a in region.agents:
        if (a.employer or a.is_corporation or a.cash <= 400 or a.company_owned
            or getattr(a, 'military_unit_id', None)
            or getattr(a, 'is_government', False) or getattr(a, 'is_lord', False)
            or a.output == Goods.gov):
            continue
        food_price = region.food_price
        company = Agent(t)
        company.is_corporation = True
        seed_traits(company)
        company.output = a.output
        company.owner = a
        company._bank_ref = region.bank
        company.home_currency = region.home_currency
        company.region = region.name
        a.company_owned = company
        for g in region.goods:
            company.inventory[g.value] = a.inv_get(g, 0)
            a.inv_set(g, 0)
        equity = min(a.cash * 0.3, a.cash - 60)
        startup_target = max(300, food_price * 20)
        shortfall = max(0, startup_target - equity)
        loaned = 0.0
        if shortfall > 0:
            loaned = region.bank.Borrow(t, company, shortfall, trace_region=region)
        _public_write = begin_public_change(None, a)
        a.cash -= equity
        finish_public_change(_public_write, 'region_labor:incorporate',
                             inputs={'source_writer': 'region_labor.py:incorporate:5092964921199ae3:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, company)
        company.cash = equity + loaned
        finish_public_change(_public_write, 'region_labor:incorporate',
                             inputs={'source_writer': 'region_labor.py:incorporate:ff54ee622d4579e7:1', 'semantic_operation_id': locals().get('operation_id')})
        if equity > 0:
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(
                region, 'startup_equity', turn=t, payer_id=a.id,
                recipient_id=company.id, amount=equity,
                detail={'company_output': getattr(company.output, 'name', str(company.output))})
        sector_wages = [x.wage for x in region.agents if x.is_corporation and x.output == a.output and x.wage > 0]
        company.wage = max(sector_wages) * 1.05 if sector_wages else max(1.0, food_price * 1.5)
        company.max_employees = rand.randint(10, 25)
        company.machinery_level = 1
        company.broken_machinery = 0
        company.shift_hours = 8.0
        company.safety_investment = getattr(region, 'safety_mandate', 0.0)
        new_companies.append(company)
        from run_trace import emit
        emit(region, kind='corporate_incorporation', record_class='outcome',
             subject={'type': 'tile', 'id': region.name, 'firm_id': company.id},
             metric_id='labor.firm_incorporation', unit='local_currency',
             before=0.0, after=company.cash,
             inputs={'founder_id': a.id,
                     'output_good': getattr(company.output, 'name', str(company.output)),
                     'founder_equity': equity, 'bank_financing': loaned,
                     'startup_target': startup_target, 'food_price': food_price,
                     'initial_wage': company.wage, 'max_employees': company.max_employees})
    return new_companies


def calculate_labor_market_tightness(region) -> float:
    """Labor Tightness Ratio (LTR) = Aggregate Unfilled Vacancies / Active Job Seekers.

    LTR > 1.0 indicates an acute labor shortage (firms compete for workers).
    LTR < 1.0 indicates a labor surplus (workers compete for jobs).
    """
    total_vacancies = 0
    for a in region.agents:
        if getattr(a, 'is_corporation', False) and getattr(a, 'alive', True):
            vacancies = max(0, getattr(a, 'max_employees', 10) - len(getattr(a, 'employees', [])))
            total_vacancies += vacancies

    t = getattr(region, 'turn', 0)
    job_seekers = [
        a for a in region.agents
        if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and not getattr(a, 'is_government', False)
        and not getattr(a, 'is_lord', False)
        and getattr(a, 'employer', None) is None
        and not getattr(a, 'is_trader', False)
        and (getattr(a, 'birth_round', 0) == 0 or (getattr(a, 'age', None)(t) if callable(getattr(a, 'age', None)) else 25) > 20)
    ]

    return total_vacancies / max(1, len(job_seekers))


def calculate_firm_wage_ceiling(firm, region) -> float:
    """Hard economic upper bound on wages: Marginal Revenue Product of Labor (MRPL).

    A firm cannot pay more than the net revenue a worker generates without running
    at an operational loss on every unit of output.
    """
    output_good = getattr(firm, 'output', None)
    if output_good is None or output_good not in region.recipes:
        return 10.0

    recipe = region.recipes[output_good]
    market_price = recipe.get('price', 1.0)

    input_good = recipe.get('input')
    input_cost = region.recipes[input_good]['price'] if (input_good and input_good in region.recipes) else 0.0

    shift_mult = calculate_shift_multiplier(getattr(firm, 'shift_hours', 8.0))
    machinery = getattr(firm, 'machinery_level', 1.0)
    base_prod = max(1.0, recipe.get('production', 1.0))
    units_per_worker = base_prod * shift_mult * machinery

    mrpl = (market_price - input_cost) * units_per_worker

    # Firms cap bids at 90% of MRPL to retain a 10% operating margin, with a minimum floor of 1.0
    return max(1.0, mrpl * 0.90)


def evaluate_worker_reservation_wage(worker, region, tightness: float) -> float:
    """Under labor scarcity, workers refuse starvation wages.

    Reservation wage is driven by subsistence food cost and market tightness.
    """
    food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
    base_subsistence = food_price * 1.25

    if tightness > 1.0:
        scarcity_premium = 1.0 + min(2.0, 0.40 * (tightness - 1.0))
        return base_subsistence * scarcity_premium
    else:
        return base_subsistence * 0.85


def _record_labor_decision(region, decision):
    """Keep the full audit trail of offers accepted or refused."""
    log = getattr(region, 'labor_decision_log', None)
    if log is None:
        region.labor_decision_log = []
        log = region.labor_decision_log
    row = {
        'turn': decision.turn,
        'worker_id': decision.worker_id,
        'firm_id': decision.firm_id,
        'accepted': decision.accepted,
        'reason': decision.reason,
        'offer': round(decision.offered_wage, 4),
        'reservation': round(decision.reservation_wage, 4),
    }
    from collective_trace_clock import stamp
    log.append(stamp(region, row))
    from run_trace import emit
    emit(region, kind='labor_offer_decision', record_class='outcome',
         subject={'type': 'tile', 'id': region.name,
                  'worker_id': decision.worker_id, 'firm_id': decision.firm_id},
         metric_id='labor.hiring_decision', unit='accepted',
         after=1 if decision.accepted else 0,
         inputs={'reason': decision.reason, 'offered_wage': decision.offered_wage,
                 'reservation_wage': decision.reservation_wage,
                 'scenario_owner_policy': bool(getattr(region, 'scenario_owner_policy', False))})


def hire_workers(region, t):
    """Firms hire unemployed workers or poach from competitors based on wage offers."""
    from labor_choice import career_lifecycle_age
    tightness = calculate_labor_market_tightness(region)
    is_statute = getattr(region, 'statute_of_laborers', False)
    wage_cap = getattr(region, 'maximum_wage_cap', None) if is_statute else None

    building_staff_ids = {
        aid for b in getattr(region, 'buildings', [])
        for aid in getattr(b, 'staff_ids', [])
    }

    # Sort firms with vacancies by cash and wage (higher paying firms get hiring priority)
    firms = [a for a in region.agents if getattr(a, 'is_corporation', False) and len(getattr(a, 'employees', [])) < getattr(a, 'max_employees', 10)]
    firms.sort(key=lambda f: (f.wage, f.cash), reverse=True)

    for a in firms:
        rec = getattr(region, 'recipes', {}).get(getattr(a, 'output', None), {})
        num_in = float(rec.get('numInput', 0))
        in_good = rec.get('input')
        if num_in > 0 and in_good is not None and not getattr(region, 'scenario_owner_policy', False):
            avail = float(a.inv_get(in_good, 0))
            effective_cap = min(int(getattr(a, 'max_employees', 10)), max(2, int(avail // num_in) + 2))
        else:
            effective_cap = int(getattr(a, 'max_employees', 10))
        vacancies = effective_cap - len(a.employees)
        if vacancies <= 0:
            continue
        payroll = len(a.employees) * a.wage
        if a.cash <= (payroll + a.wage) * 1.2:
            continue

        mrpl = calculate_firm_wage_ceiling(a, region)
        effective_max = min(mrpl, wage_cap) if wage_cap is not None else mrpl

        candidates = [x for x in region.agents if getattr(x, 'alive', True)
                      and x.employer is None and not x.is_corporation and x != a
                      and not getattr(x, 'is_lord', False)
                      and not getattr(x, 'military_unit_id', None)
                      and (x.id not in building_staff_ids or getattr(x, 'hungry_steps', 0) >= 2)]
        candidates.sort(key=lambda c: (
            0 if getattr(c, 'output', None) == getattr(a, 'output', None) else 1,
            0 if (getattr(c, 'social_class', None) == 'dispossessed' or getattr(c, 'hungry_steps', 0) > 0) else 1,
            career_lifecycle_age(c, t),
        ))

        for c in candidates:
            if len(a.employees) >= effective_cap:
                break
            payroll = len(a.employees) * a.wage
            if a.cash <= (payroll + a.wage) * 1.2:
                break
            decision = evaluate_offer(c, a, region, t, tightness=tightness)
            if (not getattr(region, 'scenario_owner_policy', False) and not decision.accepted
                    and decision.reason == 'insufficient_wage' and tightness > 1.0):
                target_wage = min(effective_max, decision.reservation_wage)
                if target_wage > a.wage and a.cash > (len(a.employees) * target_wage + target_wage) * 1.2:
                    a.wage = target_wage
                    decision = evaluate_offer(c, a, region, t, tightness=tightness)
            _record_labor_decision(region, decision)
            if decision.accepted:
                attach_worker(c, a, t, decision, region=region)

        # If still have vacancies and no unattached candidates, consider poaching
        if len(a.employees) < effective_cap and (not candidates or tightness > 1.2):
            poachable = [e for e in region.agents if getattr(e, 'alive', True) and e.employer and e.employer != a
                         and getattr(e.employer, 'is_corporation', False) and len(e.employer.employees) > 1]
            if poachable:
                target = rand.choice(poachable)
                old_employer = target.employer
                offer_wage = max(old_employer.wage * 1.15, a.wage * 1.08)
                payroll = len(a.employees) * a.wage
                if offer_wage <= effective_max and a.cash > (payroll + offer_wage) * 2:
                    decision = evaluate_offer(target, a, region, t, wage=offer_wage,
                                              tightness=tightness)
                    _record_labor_decision(region, decision)
                    if decision.accepted and attach_worker(target, a, t, decision, region=region):
                        a.wage = max(a.wage, offer_wage)


def adjust_wages(region, t):
    """Adjust firm wages dynamically based on labor tightness, MRPL ceiling, and cash."""
    if getattr(region, 'scenario_owner_policy', False):
        return
    tightness = calculate_labor_market_tightness(region)
    is_statute = getattr(region, 'statute_of_laborers', False)
    wage_cap = getattr(region, 'maximum_wage_cap', None) if is_statute else None

    for a in region.agents:
        if not getattr(a, 'is_corporation', False):
            continue

        current_workers = len(getattr(a, 'employees', []))
        has_vacancies = current_workers < getattr(a, 'max_employees', 10)
        payroll = current_workers * a.wage
        mrpl_ceiling = calculate_firm_wage_ceiling(a, region)
        effective_max = min(mrpl_ceiling, wage_cap) if wage_cap is not None else mrpl_ceiling
        wage_before = float(a.wage)
        decision_reason = 'no_change'

        # 1. ACUTE LABOR SHORTAGE (Tightness > 1.0)
        if tightness > 1.0:
            res_wage = evaluate_worker_reservation_wage(None, region, tightness)
            needs_raise = (a.wage < res_wage) or has_vacancies
            # If firm has enough cash cushion to pay payroll and wage is below ceiling, bid up wages
            if needs_raise and a.cash > max(10.0, payroll * 1.1) and a.wage < effective_max:
                shortage_intensity = min(3.0, tightness - 1.0)
                bid_increment = max(0.10, a.wage * 0.10 * shortage_intensity)
                a.wage = min(effective_max, a.wage + bid_increment)
                decision_reason = 'labor_shortage_raise'
            elif needs_raise:
                decision_reason = 'shortage_raise_blocked_by_cash_or_ceiling'
            else:
                decision_reason = 'shortage_no_raise_needed'
        # 2. PROFITABLE EXPANSION in balanced market
        elif a.cash > payroll * 5 and has_vacancies:
            if a.wage < effective_max:
                a.wage = min(effective_max, a.wage * 1.02)
                decision_reason = 'profitable_vacancy_expansion'
            else:
                decision_reason = 'expansion_at_mrpl_ceiling'
        # 3. LABOR SURPLUS (Tightness < 0.8): Downward pressure only if cash constrained
        elif tightness < 0.8 and a.cash < payroll * 2.5 and current_workers > 0:
            food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
            subsistence_floor = food_price * 1.0
            a.wage = max(subsistence_floor, a.wage * 0.96)
            decision_reason = 'cash_constrained_labor_surplus_cut'

        # 4. Enforce legal maximum wage cap if statute is active
        if wage_cap is not None and a.wage > wage_cap:
            a.wage = wage_cap
            decision_reason = 'statutory_wage_cap'

        from run_trace import emit
        emit(region, kind='corporate_wage_decision', record_class='calculation',
             subject={'type': 'tile', 'id': region.name, 'firm_id': a.id},
             metric_id='labor.corporate_wage', unit='local_currency_per_turn',
             before=wage_before, after=float(a.wage),
             formula_id='labor.tightness_mrpl_cash_policy.v1',
             inputs={'decision_reason': decision_reason,
                     'labor_market_tightness': tightness,
                     'worker_count': current_workers,
                     'vacancies': max(0, a.max_employees - current_workers),
                     'cash': a.cash, 'payroll': payroll,
                     'mrpl_wage_ceiling': mrpl_ceiling,
                     'effective_wage_ceiling': effective_max,
                     'reservation_wage': evaluate_worker_reservation_wage(None, region, tightness),
                     'wage_cap': wage_cap,
                     'food_price': region.recipes.get(Goods.food, {}).get('price', 1.0)})


def run_labour(region, t):
    """Run all labor phases and return any newly founded corporations."""
    cleanup_labor(region)
    borrow_or_layoff(region, t)
    new_companies = incorporate(region, t)
    hire_workers(region, t)
    adjust_wages(region, t)
    for a in region.agents:
        if getattr(a, 'is_corporation', False):
            evaluate_firm_contracts(a, region, t)
            safety_inv = getattr(a, 'safety_investment', 0.0)
            if safety_inv > 0.0 and len(a.employees) > 0 and getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                cost = min(a.cash, len(a.employees) * safety_inv)
                if cost > 0.0:
                    _public_write = begin_public_change(None, a)
                    a.cash -= cost
                    finish_public_change(_public_write, 'region_labor:run_labour',
                                         inputs={'source_writer': 'region_labor.py:run_labour:a9b60996880db755:1', 'semantic_operation_id': locals().get('operation_id')})
                    _public_write = begin_public_change(None, region.gov.agent)
                    region.gov.agent.cash += cost
                    finish_public_change(_public_write, 'region_labor:run_labour',
                                         inputs={'source_writer': 'region_labor.py:run_labour:77a76a323b396f1b:1', 'semantic_operation_id': locals().get('operation_id')})
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(
                        region, 'safety_investment', turn=t,
                        payer_id=a.id, recipient_id=region.gov.agent.id,
                        amount=cost,
                        detail={'workers_covered': len(a.employees),
                                'per_worker_investment': safety_inv})
    return new_companies

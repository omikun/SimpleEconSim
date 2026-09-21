"""
Labor market, hiring, firm incorporation, and wage adjustment for a Region.
"""

from agent import Agent, seed_traits
from goods import Goods
from random_cache import rand
from labor_contract import evaluate_firm_contracts, calculate_shift_multiplier


def cleanup_labor(region):
    """Clean up invalid employee/employer references."""
    living_set = set(region.agents)
    for a in region.agents:
        if a.employer and a.employer not in living_set:
            a.employer = None
        if a.is_corporation:
            a.employees = [e for e in a.employees if e in living_set and e.employer == a]


def borrow_or_layoff(region, t):
    """Firms borrow to pay payroll or lay off workers if funds are insufficient."""
    for a in region.agents:
        if not a.is_corporation or len(a.employees) == 0:
            continue
        total_wage = len(a.employees) * a.wage
        if a.cash < total_wage:
            region.bank.Borrow(t, a, total_wage - a.cash)
        while a.cash < total_wage and len(a.employees) > 0:
            e = a.employees.pop()
            e.employer = None
            total_wage = len(a.employees) * a.wage
        if len(a.employees) == 0 and a.cash <= 20.0:
            a.is_corporation = False
            if a.owner:
                a.owner.company_owned = None


def incorporate(region, t):
    """Found new corporations by sole proprietors with sufficient wealth."""
    new_companies = []
    for a in region.agents:
        if (a.employer or a.is_corporation or a.cash <= 400 or a.company_owned
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
            loaned = region.bank.Borrow(t, company, shortfall)
        a.cash -= equity
        company.cash = equity + loaned
        sector_wages = [x.wage for x in region.agents if x.is_corporation and x.output == a.output and x.wage > 0]
        company.wage = max(sector_wages) * 1.05 if sector_wages else max(1.0, food_price * 1.5)
        company.max_employees = rand.randint(10, 25)
        company.machinery_level = 1
        company.broken_machinery = 0
        company.shift_hours = 8.0
        company.safety_investment = getattr(region, 'safety_mandate', 0.0)
        new_companies.append(company)
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


def hire_workers(region, t):
    """Firms hire unemployed workers or poach from competitors based on wage offers."""
    tightness = calculate_labor_market_tightness(region)
    is_statute = getattr(region, 'statute_of_laborers', False)
    wage_cap = getattr(region, 'maximum_wage_cap', None) if is_statute else None

    # Sort firms with vacancies by cash and wage (higher paying firms get hiring priority)
    firms = [a for a in region.agents if getattr(a, 'is_corporation', False) and len(getattr(a, 'employees', [])) < getattr(a, 'max_employees', 10)]
    firms.sort(key=lambda f: (f.wage, f.cash), reverse=True)

    for a in firms:
        vacancies = getattr(a, 'max_employees', 10) - len(a.employees)
        if vacancies <= 0:
            continue
        payroll = len(a.employees) * a.wage
        if a.cash <= (payroll + a.wage) * 1.2:
            continue

        mrpl = calculate_firm_wage_ceiling(a, region)
        effective_max = min(mrpl, wage_cap) if wage_cap is not None else mrpl

        candidates = [x for x in region.agents if getattr(x, 'alive', True) and x.employer is None and not x.is_corporation and x != a and not getattr(x, 'is_lord', False)]

        for c in candidates[:vacancies]:
            res_wage = evaluate_worker_reservation_wage(c, region, tightness)
            if a.wage >= res_wage:
                c.employer = a
                c.hired_at = t
                c.shift_hours = getattr(a, 'shift_hours', 8.0)
                a.employees.append(c)
                c.output = a.output
            elif tightness > 1.0 and a.wage < effective_max:
                # Firm bids up wage to meet reservation wage if affordable
                target_wage = min(effective_max, res_wage)
                if target_wage > a.wage and a.cash > (payroll + target_wage) * 1.2:
                    a.wage = target_wage
                    c.employer = a
                    c.hired_at = t
                    c.shift_hours = getattr(a, 'shift_hours', 8.0)
                    a.employees.append(c)
                    c.output = a.output

        # If still have vacancies and no unattached candidates, consider poaching
        if len(a.employees) < a.max_employees and (not candidates or tightness > 1.2):
            poachable = [e for e in region.agents if getattr(e, 'alive', True) and e.employer and e.employer != a
                         and getattr(e.employer, 'is_corporation', False) and len(e.employer.employees) > 1]
            if poachable:
                target = rand.choice(poachable)
                old_employer = target.employer
                offer_wage = max(old_employer.wage * 1.15, a.wage * 1.08)
                if offer_wage <= effective_max and a.cash > (payroll + offer_wage) * 2:
                    old_employer.employees.remove(target)
                    target.employer = a
                    target.hired_at = t
                    target.shift_hours = getattr(a, 'shift_hours', 8.0)
                    target.output = a.output
                    a.employees.append(target)
                    a.wage = max(a.wage, offer_wage)


def adjust_wages(region, t):
    """Adjust firm wages dynamically based on labor tightness, MRPL ceiling, and cash."""
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

        # 1. ACUTE LABOR SHORTAGE (Tightness > 1.0)
        if tightness > 1.0:
            res_wage = evaluate_worker_reservation_wage(None, region, tightness)
            needs_raise = (a.wage < res_wage) or has_vacancies
            # If firm has enough cash cushion to pay payroll and wage is below ceiling, bid up wages
            if needs_raise and a.cash > max(10.0, payroll * 1.1) and a.wage < effective_max:
                shortage_intensity = min(3.0, tightness - 1.0)
                bid_increment = max(0.10, a.wage * 0.10 * shortage_intensity)
                a.wage = min(effective_max, a.wage + bid_increment)
        # 2. PROFITABLE EXPANSION in balanced market
        elif a.cash > payroll * 5 and has_vacancies:
            if a.wage < effective_max:
                a.wage = min(effective_max, a.wage * 1.02)
        # 3. LABOR SURPLUS (Tightness < 0.8): Downward pressure only if cash constrained
        elif tightness < 0.8 and a.cash < payroll * 2.5 and current_workers > 0:
            food_price = region.recipes.get(Goods.food, {}).get('price', 1.0)
            subsistence_floor = food_price * 1.0
            a.wage = max(subsistence_floor, a.wage * 0.96)

        # 4. Enforce legal maximum wage cap if statute is active
        if wage_cap is not None and a.wage > wage_cap:
            a.wage = wage_cap


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
                    a.cash -= cost
                    region.gov.agent.cash += cost
    return new_companies

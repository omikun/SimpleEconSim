"""
Labor market, hiring, firm incorporation, and wage adjustment for a Region.
"""

from agent import Agent, seed_traits
from goods import Goods
from random_cache import rand


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
        if len(a.employees) == 0:
            a.is_corporation = False
            if a.owner:
                a.owner.company_owned = None


def incorporate(region, t):
    """Found new corporations by sole proprietors with sufficient wealth."""
    new_companies = []
    for a in region.agents:
        if a.employer or a.is_corporation or a.cash <= 400 or a.company_owned:
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
        new_companies.append(company)
    return new_companies


def hire_workers(region, t):
    """Firms hire unemployed distressed agents or poach workers from competitors."""
    for a in region.agents:
        if not a.is_corporation or len(a.employees) >= a.max_employees:
            continue
        payroll = len(a.employees) * a.wage
        if a.cash <= (payroll + a.wage) * 2:
            continue
        candidates = [x for x in region.agents if x.employer is None and not x.is_corporation and x != a]
        distressed = [c for c in candidates if c.hungry_steps > 0 or c.cash < 40]
        if distressed:
            c = rand.choice(distressed)
            c.employer = a
            c.hired_at = t
            a.employees.append(c)
            c.output = a.output
        else:
            poachable = [e for e in region.agents if e.employer and e.employer != a
                         and e.employer.is_corporation and len(e.employer.employees) > 1]
            if poachable:
                target = rand.choice(poachable)
                old_employer = target.employer
                offer_wage = max(old_employer.wage * 1.1, a.wage * 1.05)
                if a.cash > (payroll + offer_wage) * 2:
                    old_employer.employees.remove(target)
                    target.employer = a
                    target.hired_at = t
                    target.output = a.output
                    a.employees.append(target)
                    a.wage = max(a.wage, offer_wage)


def adjust_wages(region, t):
    """Adjust firm wages upward when profitable or downward when cash constrained."""
    for a in region.agents:
        if not a.is_corporation or len(a.employees) == 0:
            continue
        payroll = len(a.employees) * a.wage
        if a.cash > payroll * 5 and len(a.employees) < a.max_employees:
            a.wage *= 1.02
        elif a.cash < payroll * 3:
            a.wage *= 0.95


def run_labour(region, t):
    """Run all labor phases and return any newly founded corporations."""
    cleanup_labor(region)
    borrow_or_layoff(region, t)
    new_companies = incorporate(region, t)
    hire_workers(region, t)
    adjust_wages(region, t)
    return new_companies

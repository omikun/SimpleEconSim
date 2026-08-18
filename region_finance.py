"""
Corporate wages, profit distributions, owner bailouts, taxation, and consumption multipliers.
"""

import math
import forex as _fx
from logger import loginfo, logwarning


def pay_wages(region, t):
    """Firms pay wages to their employees."""
    for a in region.agents:
        if a.is_corporation and len(a.employees) > 0:
            for e in a.employees:
                wage_to_pay = min(a.cash, a.wage)
                a.cash -= wage_to_pay
                e.cash += wage_to_pay
                e.mem_push('mem_wages', wage_to_pay)


def credit_owner_pay(region, owner, amount):
    """Credit an owner's share, routing through the FX wallet when
    the owner lives on a DIFFERENT (or wilderness) tile so the
    per-currency audit still counts the money."""
    if amount <= 0:
        return
    if getattr(owner, '_bank_ref', None) is region.bank:
        owner.cash += amount
    else:
        if region.home_currency:
            _fx.fx_add(owner, region.home_currency, amount)
        else:
            owner.cash += amount


def repay_owner_loan(region, agent, owner, payroll):
    """Repay debt owed by corporation back to its owner."""
    if agent.owner_loan <= 0:
        return
    repay = min(agent.owner_loan, max(0, agent.cash - payroll * 2))
    if repay > 0:
        agent.cash -= repay
        credit_owner_pay(region, owner, repay)
        agent.owner_loan -= repay


def pay_base_salary(region, agent, owner, payroll):
    """Pay owner's executive base salary if cash reserve allows."""
    if agent.cash > payroll * 2 + agent.wage:
        agent.cash -= agent.wage
        credit_owner_pay(region, owner, agent.wage)


def pay_profit_share(region, agent, owner, payroll):
    """Distribute retained earnings / profit dividends to the owner."""
    if agent.retained_earnings <= 0 or agent.cash <= payroll * 2:
        return
    operating_expenses = payroll * 2
    ratio = agent.retained_earnings / operating_expenses
    share_rate = 0.25 * ratio / (ratio + 5)
    profit_draw = min(share_rate * agent.retained_earnings, max(0, agent.cash - payroll * 2))
    if profit_draw > 0:
        agent.cash -= profit_draw
        credit_owner_pay(region, owner, profit_draw)
        agent.retained_earnings -= profit_draw


def bailout_owner(region, agent, owner, payroll):
    """Owner injects cash into the firm to cover payroll shortfall."""
    if agent.cash >= payroll:
        return
    food_price = region.food_price
    if getattr(owner, '_bank_ref', None) is region.bank:
        avail = max(0.0, owner.cash - food_price * 4)
        inject = min(payroll - agent.cash, avail)
        if inject > 0:
            owner.cash -= inject
            agent.cash += inject
            agent.owner_loan += inject
    else:
        if region.home_currency:
            avail = _fx.fx_balance(owner, region.home_currency)
            inject = min(payroll - agent.cash, max(0.0, avail))
            if inject > 0:
                _fx.fx_add(owner, region.home_currency, -inject)
                agent.cash += inject
                agent.owner_loan += inject


def distribute_profits(region, t):
    """Distribute firm profits to owners, service owner loans, or execute bailouts."""
    for a in region.agents:
        if not a.is_corporation or not a.alive:
            continue
        if a.owner is None or not a.owner.alive:
            continue
        owner = a.owner
        payroll = max(1, len(a.employees) * a.wage)
        repay_owner_loan(region, a, owner, payroll)
        profit = max(0, a._delta_cash + a._delta_deposits)
        if profit > 0 or a.cash > payroll * 2:
            a.retained_earnings += profit
        pay_base_salary(region, a, owner, payroll)
        pay_profit_share(region, a, owner, payroll)
        bailout_owner(region, a, owner, payroll)


def collect_tax(region, t):
    """Budget-balanced taxation with deficit financing."""
    if getattr(region, 'province', None) is not None \
            and not getattr(region, '_seat_gov_agent', True):
        return
    gov = region.gov.agent
    bank = region.bank
    food_price = region.food_price

    # ---- 1. Service existing government debt ----
    for loan in gov.loans[:]:
        remaining = loan.principle - loan.principle_paid
        if remaining <= 0:
            gov.loans.remove(loan)
            if loan in bank.loans:
                bank.loans.remove(loan)
            continue
        amount_due = remaining + loan.getInterest()
        available = gov.cash + bank.deposits.get(gov, 0)
        payment = min(amount_due, available)
        if payment > 0:
            if gov.cash < payment:
                bank.Withdraw(gov, payment - gov.cash)
            gov.cash -= payment
            loan.pay(payment)
        if loan.isPaid():
            gov.loans.remove(loan)
            if loan in bank.loans:
                bank.loans.remove(loan)

    # ---- 2. Compute deficit against target reserve ----
    loans_outstanding = sum(l.principle - l.principle_paid for l in gov.loans)
    net_worth = (gov.cash + bank.deposits.get(gov, 0)
                 + region.gov.food_inventory * food_price - loans_outstanding)
    reserve = region.gov.target_food_reserve * food_price * 2
    deficit = max(0.0, reserve - net_worth)

    # ---- 3. Tax top 10% just enough to cover the deficit ----
    tax_collected = 0.0
    top_count = 0
    if deficit > 0:
        living = [a for a in region.agents if a.alive]
        if len(living) > 10:
            sorted_agents = sorted(living, key=lambda a: a.wealth(), reverse=True)
            top_count = max(1, int(len(sorted_agents) * 0.1))
            top = sorted_agents[:top_count]
            tax_bills = []
            total_taxable = 0.0
            for a in top:
                net_income = a._delta_cash + a._delta_deposits
                taxable = max(0.0, net_income + a.tax_loss_carryforward)
                if hasattr(region.gov, 'compute_child_tax_deduction'):
                    taxable = max(0.0, taxable - region.gov.compute_child_tax_deduction(a))
                tax_bills.append((a, taxable, net_income))
                total_taxable += taxable
            if total_taxable > 0:
                effective_rate = min(region.gov.tax_rate, deficit / total_taxable)
                for a, taxable, net_income in tax_bills:
                    if taxable <= 0:
                        a.tax_loss_carryforward += net_income
                        continue
                    tax_amount = taxable * effective_rate
                    bank_balance = bank.deposits.get(a, 0)
                    actual = min(tax_amount, a.cash + bank_balance)
                    if actual > 0:
                        cash_taken = min(a.cash, actual)
                        a.cash -= cash_taken
                        deposit_taken = min(bank_balance, actual - cash_taken)
                        if deposit_taken > 0:
                            bank.Withdraw(a, deposit_taken)
                            a.cash -= deposit_taken
                    a.tax_loss_carryforward = 0.0
                    region.gov.collect_tax(t, actual)
                    tax_collected += actual

    # ---- 4. If still short, borrow from the bank ----
    gap = max(0.0, deficit - tax_collected)
    region.gov.borrow_log.append(gap)
    if gap > 0.01:
        before_liab = bank.total_liabilities
        bank.Borrow(t, gov, gap)
        borrowed = bank.total_liabilities - before_liab
        if borrowed > 0:
            loginfo(t, f"Government({region.gov.name}) borrowed ${borrowed:.2f} "
                    f"to cover deficit (gap ${gap:.2f})")
        else:
            logwarning(t, f"Government({region.gov.name}) could not borrow "
                          f"${gap:.2f} (bank capacity exhausted)")

    # ---- 5. Re-evaluate tax rate every interval ----
    if (t % region.gov.tax_adjust_interval == 0
            and len(region.gov.borrow_log) >= region.gov.tax_adjust_interval):
        recent_gaps = region.gov.borrow_log[-region.gov.tax_adjust_interval:]
        avg_gap = sum(recent_gaps) / len(recent_gaps)
        if avg_gap > reserve * 0.1:
            new_rate = region.gov.tax_rate * 1.5
        elif avg_gap == 0 and net_worth > reserve * 2:
            new_rate = region.gov.tax_rate * 0.7
        else:
            new_rate = region.gov.tax_rate
        region.gov.tax_rate = max(0.05, min(0.75, new_rate))
        region.gov.tax_rate_log.append((t, region.gov.tax_rate))
        print(f"  Region '{region.name}' fiscal: gov_net=${net_worth:.0f}, "
              f"reserve=${reserve:.0f}, avg_gap=${avg_gap:.2f}, "
              f"tax_rate={region.gov.tax_rate:.2f}")

    if tax_collected > 0 and t % 50 == 0:
        print(f"  Region '{region.name}' TAX: ${tax_collected:.2f} from top "
              f"{top_count}, gov=${region.gov.agent.cash:.2f}, "
              f"debt=${loans_outstanding:.2f}")


def recalculate_multipliers(region):
    """Update consumption multipliers based on agent wealth vs cost of living."""
    cost_of_living = region.cost_of_living
    for a in region.agents:
        if not a.alive or a.is_corporation:
            continue
        wealth = a.wealth()
        a.consumption_multiplier = max(1.0, min(10.0, math.sqrt(wealth / cost_of_living))) if wealth > cost_of_living else 1.0

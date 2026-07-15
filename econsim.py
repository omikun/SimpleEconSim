import sys 
import random
import math
from statistics import mean
import matplotlib.pyplot as plt

import econsim_live as Living
import econsim_states
from econsim_states import *
from goods import Goods
# import econsim_trade as trade
# import econsim_trade_unity as trade
import econsim_trade_money as trade
from logger import *


# =============================================================================
# Agent class
# =============================================================================

class Agent:
    def __init__(self, t):
        self.id = econsim_states.agentid
        econsim_states.agentid += 1
        self.birthRound = t
        self.alive = True
        self.parent = None
        self.descendents = []
        self.bid = 0
        self.ask = 0
        self.output = Goods.none
        self.hungry_steps = 0
        self.cash = 0
        self.inv = {}
        self.cost_basis = {}
        self.lastCareerSwitch = 0
        self.lastRepro = 0
        self.loans = []
        self.employer = None
        self.employees = []
        self.is_corp = False
        self.wage = 0
        self.hiredAt = 0
        self.owner = None
        self.company_owned = None
        self.max_employees = 0
        self.consumption_mult = 1.0
        self.tax_loss_carryforward = 0.0
        self.retained_earnings = 0.0
        self.owner_loan = 0.0
        self._start_cash = 0
        self._start_deposits = 0
        self._delta_cash = 0
        self._delta_deposits = 0

    def name(self):
        return 'agent' + str(self.id) + '-' + profession[self.output]

    def age(self, t):
        return t - self.birthRound

    def wealth(self):
        inv_value = sum(
            amount * recipes[good]['price']
            for good, amount in self.inv.items()
            if good in recipes
        )
        debt_value = sum(loan.principle for loan in self.loans)
        return self.cash + trade.bank.deposits.get(self, 0) + inv_value - debt_value

    def oweThisTurn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)


# =============================================================================
# Module-level initialisation
# =============================================================================

recipes[Goods.food] = {
    'commodity': Goods.food, 'production': 5, 'price': 1, 'numInput': 0,
    'maxtotalprod': 10000, 'maxinv': 20,
}
recipes[Goods.wood] = {
    'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0,
    'maxtotalprod': 3000, 'maxinv': 10,
}
recipes[Goods.furn] = {
    'commodity': Goods.furn, 'production': 1, 'input': Goods.wood,
    'numInput': 2, 'price': 25, 'maxtotalprod': 300, 'maxinv': 5,
}
recipes[Goods.gov] = {
    'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1,
    'maxtotalprod': 0, 'maxinv': 0,
}

for good in goods:
    pop_log[good] = []
    hungry_log[good] = []
    if good != Goods.gov:
        demand_ratio_log[good] = []
        demand_log[good] = []
        supply_log[good] = []
        inv_log[good] = []
        perCapitaInv[good] = []
        production_log[good] = []


# =============================================================================
# Agent initialisation helpers
# =============================================================================

def GetInputCom(agent):
    """Return the input commodity required for *agent*'s output good."""
    recipe = recipes[agent.output]
    return recipe.get('input', Goods.none)


def GetOutputCom(agent):
    return agent.output


def InitAgents(agents):
    for a in range(num_agents):
        agent = agents[a]
        if a < 90:
            output = Goods.food
        elif a < 97:
            output = Goods.wood
        elif a < 99:
            output = Goods.furn
        else:
            output = Goods.gov
        delta = 20
        cash = 120 + random.randint(-delta, delta)
        InitAgent(agent, output, 10, 2, cash)


def InitAgent(agent, output, numInput, numFood, cash, delta=0):
    agent.output = output
    agent.cash = cash
    if agent.output in recipes:
        recipe = recipes[agent.output]
    else:
        logger.error(profession[agent.output], 'not in dictionary', recipes)
    inputCom = recipe.get('input', Goods.none)
    for good in goods:
        agent.inv[good] = 0
    if inputCom != Goods.none:
        agent.inv[inputCom] = numInput
    agent.inv[Goods.food] = numFood
    loginfo('init', agent.output, agent.inv)


for good in goods:
    cash_log[good] = []
    gini_log[good] = []

price_log = {Goods.food: [], Goods.wood: [], Goods.furn: []}

for prof in goods:
    bought_log[prof] = {}
    for good in goods:
        bought_log[prof][good] = [0]


# =============================================================================
# NumAgents
# =============================================================================

def NumAgents(agents, good):
    return sum(agent.output == good for agent in agents)


# =============================================================================
# LABOUR MARKET
# =============================================================================

def RunLaborMarket(t, agents):
    _cleanup_dead_references(agents)
    _borrow_or_layoff(t, agents)
    new_company_agents = _handle_incorporation(t, agents)
    _hire_workers(t, agents)
    _adjust_wages(t, agents)
    return new_company_agents


def _cleanup_dead_references(agents):
    living_agents_set = set(agents)
    for agent in agents:
        if agent.employer and agent.employer not in living_agents_set:
            agent.employer = None
        if agent.is_corp:
            agent.employees = [
                e for e in agent.employees
                if e in living_agents_set and e.employer == agent
            ]


def _borrow_or_layoff(t, agents):
    for agent in agents:
        if not agent.is_corp or len(agent.employees) == 0:
            continue
        total_wage_needed = len(agent.employees) * agent.wage
        if agent.cash < total_wage_needed:
            shortfall = total_wage_needed - agent.cash
            trade.bank.Borrow(t, agent, shortfall)
            loginfo(t, agent.name(), "borrowed $",
                    min(shortfall, trade.bank.total_deposits - trade.bank.total_liabilities),
                    "from bank to cover payroll. cash:", agent.cash)
        while agent.cash < total_wage_needed and len(agent.employees) > 0:
            emp = agent.employees.pop()
            emp.employer = None
            total_wage_needed = len(agent.employees) * agent.wage
            loginfo(t, agent.name(), "laid off", emp.name(),
                    "due to insufficient cash. Remaining:", len(agent.employees))
        if len(agent.employees) == 0:
            agent.is_corp = False
            if agent.owner is not None:
                agent.owner.company_owned = None
                loginfo(t, agent.name(), "dissolved company, owner",
                        agent.owner.name(), "released")


def _handle_incorporation(t, agents):
    new_company_agents = []
    for agent in agents:
        if agent.employer is not None or agent.is_corp or agent.cash <= 400:
            continue
        if agent.company_owned is not None:
            continue
        food_price = recipes[Goods.food]['price']
        company = Agent(t)
        company.is_corp = True
        company.output = agent.output
        company.owner = agent
        agent.company_owned = company
        for good in goods:
            company.inv[good] = agent.inv.get(good, 0)
            agent.inv[good] = 0
        owner_equity = min(agent.cash * 0.3, agent.cash - 60)
        startup_target = max(300, food_price * 20)
        shortfall = max(0, startup_target - owner_equity)
        if shortfall > 0:
            trade.bank.Borrow(t, agent, shortfall)
        agent.cash -= owner_equity
        company.cash = owner_equity + shortfall
        sector_wages = [
            a.wage for a in agents
            if a.is_corp and a.output == agent.output and a.wage > 0
        ]
        if sector_wages:
            company.wage = max(sector_wages) * 1.05
        else:
            company.wage = max(1.0, food_price * 1.5)
        company.max_employees = random.randint(10, 25)
        loginfo(t, agent.name(), "founded company", company.name(),
                "with $", company.cash, "(equity:", owner_equity,
                "borrowed:", shortfall, ") wage:", company.wage)
        new_company_agents.append(company)
    return new_company_agents


def _hire_workers(t, agents):
    for agent in agents:
        if not agent.is_corp:
            continue
        if len(agent.employees) >= agent.max_employees:
            continue
        payroll = len(agent.employees) * agent.wage
        needed_cash_to_hire = (payroll + agent.wage) * 2
        if agent.cash <= needed_cash_to_hire:
            continue
        hired = False
        candidates = [
            a for a in agents
            if a.employer is None and not a.is_corp and a != agent
        ]
        distressed = [c for c in candidates
                      if c.hungry_steps > 0 or c.cash < 40]
        pool = distressed
        if pool:
            candidate = random.choice(pool)
            candidate.employer = agent
            candidate.hiredAt = t
            agent.employees.append(candidate)
            candidate.output = agent.output
            loginfo(t, agent.name(), "hired", candidate.name(),
                    "at wage", agent.wage)
            hired = True
        if not hired:
            poachable = [
                e for e in agents
                if e.employer is not None
                and e.employer != agent
                and e.employer.is_corp
                and len(e.employer.employees) > 1
            ]
            if poachable:
                target = random.choice(poachable)
                old_employer = target.employer
                old_wage = old_employer.wage
                offer_wage = max(old_wage * 1.1, agent.wage * 1.05)
                if agent.cash > (payroll + offer_wage) * 2:
                    old_employer.employees.remove(target)
                    target.employer = None
                    target.employer = agent
                    target.hiredAt = t
                    target.output = agent.output
                    agent.employees.append(target)
                    agent.wage = max(agent.wage, offer_wage)
                    loginfo(t, agent.name(), "poached", target.name(),
                            "from", old_employer.name(),
                            "at wage", agent.wage)


def _adjust_wages(t, agents):
    for agent in agents:
        if not agent.is_corp or len(agent.employees) == 0:
            continue
        payroll = len(agent.employees) * agent.wage
        if agent.cash > payroll * 5 and len(agent.employees) < agent.max_employees:
            agent.wage = agent.wage * 1.02
            loginfo(t, agent.name(), "raised wage to", agent.wage,
                    "(profitable, room to grow)")
        elif agent.cash < payroll * 3:
            agent.wage = agent.wage * 0.95
            loginfo(t, agent.name(), "lowered wage to", agent.wage)


def PayWages(t, agents):
    """Pay wages to employees AFTER production and trade,
    so companies earn revenue before paying out."""
    for agent in agents:
        if agent.is_corp and len(agent.employees) > 0:
            for emp in agent.employees:
                wage_to_pay = min(agent.cash, agent.wage)
                agent.cash -= wage_to_pay
                emp.cash += wage_to_pay
                loginfo(t, agent.name(), "paid wage of", wage_to_pay,
                        "to", emp.name())


# =============================================================================
# PRODUCTION
# =============================================================================

def Produce(t, agents):
    numAgentsPerGoods = {}
    for good in econsim_states.goods:
        numAgentsPerGoods[good] = NumAgents(agents, good)
    totalProd.clear()
    for agent in agents:
        if agent.employer is not None:
            continue
        output = agent.output
        loginfo(t, agent.name(), agent.inv, 'hungry_steps', agent.hungry_steps)
        recipe = recipes[output]
        if agent.is_corp and len(agent.employees) > 0:
            _produce_corp(t, agent, recipe, output, numAgentsPerGoods)
        else:
            _produce_independent(t, agent, recipe, output, numAgentsPerGoods)
    for good in econsim_states.goods:
        if good != Goods.gov:
            production_log[good].append(totalProd[good])
    for good, produced in totalProd.items():
        loginfo(t, numAgentsPerGoods[good], 'produced', produced, good)


def _produce_corp(t, agent, recipe, output, numAgentsPerGoods):
    num_employees = len(agent.employees)
    maxinv = recipe['maxinv'] * (1 + num_employees)
    inv_ratio = agent.inv.get(output, 0) / maxinv if maxinv > 0 else 1
    if inv_ratio >= 1:
        totalProd[output] += 0
        return
    num_slots = num_employees
    if recipe.get('numInput', 0) > 0:
        com = recipe['input']
        available_inputs = agent.inv.get(com, 0)
        inputs_per_slot = recipe['numInput']
        active_slots = int(min(num_slots, available_inputs // inputs_per_slot))
    else:
        active_slots = int(num_slots)
    if active_slots <= 0 or recipe.get('production', 0) <= 0:
        return
    if num_employees >= 12:
        synergy = 1.0 + 0.30 * num_employees
    elif num_employees >= 8:
        synergy = 1.0 + 0.25 * num_employees
    elif num_employees >= 4:
        synergy = 1.0 + 0.20 * num_employees
    else:
        synergy = 1.0 + 0.15 * num_employees
    base_prod = recipe['production']
    prod_per_slot = base_prod * synergy
    chance = 1.0
    if agent.hungry_steps > 0:
        chance *= 1 / (1 + agent.hungry_steps * 0.2)
    if output in (Goods.food, Goods.wood):
        max_per_agent = recipe['maxtotalprod'] / max(1, numAgentsPerGoods[output])
        chance *= min(1.0, max_per_agent / base_prod)
    chance *= max(0, 1 - inv_ratio)
    successful_slots = 0
    for _ in range(active_slots):
        if random.random() < chance:
            successful_slots += 1
    if successful_slots > 0:
        if recipe.get('numInput', 0) > 0:
            agent.inv[recipe['input']] -= successful_slots * recipe['numInput']
        numOutput = int(successful_slots * prod_per_slot)
        if numOutput == 0:
            numOutput = 1
        agent.inv[output] += numOutput
        totalProd[output] += numOutput
        loginfo(t, agent.name(), 'corp built', numOutput, output,
                'slots', successful_slots, 'synergy', synergy)


def _produce_independent(t, agent, recipe, output, numAgentsPerGoods):
    maxinv = recipe['maxinv']
    inv_ratio = agent.inv.get(output, 0) / maxinv if maxinv > 0 else 1
    if inv_ratio >= 1:
        totalProd[output] += 0
        return
    has_inputs = True
    if recipe['numInput'] > 0:
        com = recipe['input']
        if agent.inv.get(com, 0) < recipe['numInput']:
            has_inputs = False
    numOutput = 0
    if has_inputs and recipe.get('production', 0) > 0:
        chance = 1.0
        if agent.hungry_steps > 0:
            chance *= 1 / (1 + agent.hungry_steps * 0.2)
        if output in (Goods.food, Goods.wood):
            max_per_agent = recipe['maxtotalprod'] / max(1, numAgentsPerGoods[output])
            chance *= min(1.0, max_per_agent / recipe['production'])
        chance *= max(0, 1 - inv_ratio)
        if random.random() < chance:
            if recipe['numInput'] > 0:
                agent.inv[recipe['input']] -= recipe['numInput']
            numOutput = recipe['production']
    agent.inv[output] += numOutput
    totalProd[output] += numOutput
    loginfo(t, agent.name(), 'built', numOutput, output, agent.inv)


# =============================================================================
# GINI / CASH helpers
# =============================================================================

def compute_gini(agents, good):
    values = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(values)
    if n == 0:
        return 0
    mean_cash = sum(values) / n
    if mean_cash == 0:
        return 0
    diffsum = 0
    for i in range(n):
        for j in range(n):
            diffsum += abs(values[i] - values[j])
    return diffsum / (2 * n * n * mean_cash)


def getTotalCash(agents):
    bankCash = trade.bank.total_deposits - trade.bank.total_liabilities
    return sum(agent.cash for agent in agents) + bankCash


def RecalculateConsumptionMultipliers(agents):
    """Recalculate consumption_mult for every living agent based on wealth / CoL.
    Formula: sqrt(wealth / CoL), clamped to [1.0, 10.0].
    If wealth <= CoL, multiplier stays at 1.0 (no overconsumption)."""
    food_price = recipes.get(Goods.food, {}).get('price', 1)
    wood_price = recipes.get(Goods.wood, {}).get('price', 1)
    furn_price = recipes.get(Goods.furn, {}).get('price', 1)
    col = 4 * food_price + 1 * wood_price + 0.25 * furn_price
    col = max(0.1, col)
    for agent in agents:
        if not agent.alive or getattr(agent, 'is_corp', False):
            continue
        w = agent.wealth()
        if w > col:
            raw = math.sqrt(w / col)
            agent.consumption_mult = max(1.0, min(10.0, raw))
        else:
            agent.consumption_mult = 1.0


# =============================================================================
# OWNER PROFIT DISTRIBUTION
# =============================================================================

def DistributeOwnerProfits(t, agents):
    """Distribute corporate profits to owners:

    1. Repay owner loan from previous bailouts
    2. Base salary equal to employee wage
    3. Progressive profit share on retained earnings (approaches 25%)
    4. Owner bailout when corp runs low on cash (injects as loan)
    """
    for agent in agents:
        if not agent.is_corp or not agent.alive:
            continue
        if agent.owner is None or not getattr(agent.owner, 'alive', False):
            continue
        owner = agent.owner
        payroll = max(1, len(agent.employees) * agent.wage)
        operating_expenses = payroll * 2
        _repay_owner_loan(t, agent, owner, payroll)
        profit = max(0, agent._delta_cash + agent._delta_deposits)
        if profit > 0 or agent.cash > payroll * 2:
            agent.retained_earnings += profit
        _pay_owner_base_salary(t, agent, owner, payroll)
        _pay_owner_profit_share(t, agent, owner, payroll, operating_expenses)
        _owner_bailout(t, agent, owner, payroll)


def _repay_owner_loan(t, agent, owner, payroll):
    if agent.owner_loan <= 0:
        return
    avail_for_repayment = max(0, agent.cash - payroll * 2)
    repay = min(agent.owner_loan, avail_for_repayment)
    if repay > 0:
        agent.cash -= repay
        owner.cash += repay
        agent.owner_loan -= repay
        loginfo(t, agent.name(), "repaid owner loan $", round(repay, 2),
                "to", owner.name(), "remaining loan $",
                round(agent.owner_loan, 2))


def _pay_owner_base_salary(t, agent, owner, payroll):
    base_wage = agent.wage
    if agent.cash > payroll * 2 + base_wage:
        agent.cash -= base_wage
        owner.cash += base_wage
        loginfo(t, agent.name(), "paid owner base wage $",
                round(base_wage, 2), "to", owner.name())


def _pay_owner_profit_share(t, agent, owner, payroll, operating_expenses):
    if agent.retained_earnings <= 0 or agent.cash <= payroll * 2:
        return
    ratio = agent.retained_earnings / operating_expenses
    share_rate = 0.25 * ratio / (ratio + 5)
    profit_draw = share_rate * agent.retained_earnings
    max_available = max(0, agent.cash - payroll * 2)
    profit_draw = min(profit_draw, max_available)
    if profit_draw > 0:
        agent.cash -= profit_draw
        owner.cash += profit_draw
        agent.retained_earnings -= profit_draw
        loginfo(t, agent.name(), "paid owner profit share $",
                round(profit_draw, 2), "to", owner.name(),
                "(rate=", round(share_rate, 4), ", ratio=",
                round(ratio, 2), ")")
        if not hasattr(owner, 'owner_payouts'):
            owner.owner_payouts = []
        base_wage_paid = agent.wage if agent.cash > payroll * 2 + agent.wage else 0
        owner.owner_payouts.append(base_wage_paid + profit_draw)


def _owner_bailout(t, agent, owner, payroll):
    if agent.cash >= payroll:
        return
    needed = payroll - agent.cash
    food_price = recipes.get(Goods.food, {}).get('price', 1)
    owner_reserve = food_price * 4
    inject = min(needed, max(0, owner.cash - owner_reserve))
    if inject > 0:
        owner.cash -= inject
        agent.cash += inject
        agent.owner_loan += inject
        loginfo(t, agent.name(), "owner", owner.name(),
                "injected $", round(inject, 2), "as loan to cover payroll",
                "total loan $", round(agent.owner_loan, 2))


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    epsilon = 1e-8
    logInit()
    time_steps = int(sys.argv[1])
    agents = [Agent(0) for _ in range(num_agents)]
    import government as govmod
    gov = govmod.create_default_government(0, initial_cash=200)
    agents.append(econsim_states.default_gov.agent)
    InitAgents(agents)
    for agent in agents:
        if hasattr(agent, 'id'):
            gov._add_citizen(agent)
    prevTotalCash = getTotalCash(agents)
    for t in range(time_steps):
        _record_start_of_turn(agents)
        new_company_agents = RunLaborMarket(t, agents)
        if new_company_agents:
            agents.extend(new_company_agents)
        Produce(t, agents)
        trade.Trade(t, agents, recipes, demand_ratio_log, demand_log,
                    supply_log, sold_log, bought_log)
        PayWages(t, agents)
        DistributeOwnerProfits(t, agents)
        _record_delta_income(agents)
        _collect_top_tax(t, agents)
        _log_gdp(agents)
        if t > 0 and t % 10 == 0:
            RecalculateConsumptionMultipliers(agents)
        cash_before_live = getTotalCash(agents)
        agents = Living.Live(t, agents)
        cash_after_live = getTotalCash(agents)
        live_diff = cash_after_live - cash_before_live
        if abs(live_diff) > 5.0:
            print(f"{t}  CASH LEAK: Live() changed total by ${live_diff:.2f}")
        _log_all_metrics(t, agents)
        total_pop.append(sum(log[-1] for log in pop_log.values()))
        bankCash_log.append(trade.bank.total_deposits - trade.bank.total_liabilities)
        totalCash_log.append(getTotalCash(agents))
        _log_pop_change_rate()
        for prof in goods:
            for good in goods:
                bought_log[prof][good].append(0)
        diff = math.fabs(prevTotalCash - totalCash_log[-1])
        if diff > epsilon:
            logwarning(t, "total cash not matching", prevTotalCash,
                       '!=', totalCash_log[-1], 'diff', diff)
        prevTotalCash = totalCash_log[-1]
        if t % 100 == 0:
            circ_cash = sum(a.cash for a in agents)
            bank_dep = trade.bank.total_deposits
            bank_liab = trade.bank.total_liabilities
            ratio = bank_dep / max(1, circ_cash)
            print(f"--- TEST A: Turn {t}: circulating=${circ_cash:.0f}, "
                  f"bank_deposits=${bank_dep:.0f}, "
                  f"bank_liabilities=${bank_liab:.0f}, ratio={ratio:.1f}x")
    _plot_results(agents)


# ---- main() sub-helpers ----------------------------------------------------

def _record_start_of_turn(agents):
    for agent in agents:
        agent._start_cash = agent.cash
        agent._start_deposits = trade.bank.deposits.get(agent, 0)


def _record_delta_income(agents):
    for agent in agents:
        end_cash = agent.cash
        end_deposits = trade.bank.deposits.get(agent, 0)
        agent._delta_cash = end_cash - agent._start_cash
        agent._delta_deposits = end_deposits - agent._start_deposits


def _collect_top_tax(t, agents):
    """Tax the top 10 % wealthiest agents at 50 % of net income."""
    living_agents = [a for a in agents if a.alive]
    if len(living_agents) <= 10:
        return
    sorted_agents = sorted(living_agents, key=lambda a: a.wealth(), reverse=True)
    top_count = max(1, int(len(sorted_agents) * 0.1))
    top_agents = sorted_agents[:top_count]
    total_tax_collected = 0.0
    for agent in top_agents:
        net_income = agent._delta_cash + agent._delta_deposits
        taxable_income = net_income + agent.tax_loss_carryforward
        child_deduction = (
            econsim_states.default_gov.compute_child_tax_deduction(agent)
            if econsim_states.default_gov else 0.0
        )
        taxable_income = max(0.0, taxable_income - child_deduction)
        if taxable_income > 0:
            tax_amount = taxable_income * 0.5
            bank_balance = trade.bank.deposits.get(agent, 0)
            total_available = agent.cash + bank_balance
            actual_tax = min(tax_amount, total_available)
            if actual_tax > 0:
                cash_taken = min(agent.cash, actual_tax)
                agent.cash -= cash_taken
                deposit_taken = min(bank_balance, actual_tax - cash_taken)
                if deposit_taken > 0:
                    trade.bank.Withdraw(agent, deposit_taken)
                    agent.cash -= deposit_taken
            agent.tax_loss_carryforward = 0.0
            if econsim_states.default_gov is not None:
                econsim_states.default_gov.collect_tax(t, actual_tax)
            total_tax_collected += actual_tax
        else:
            agent.tax_loss_carryforward += net_income
    if total_tax_collected > 0 and t % 50 == 0:
        gov_cash = (
            econsim_states.default_gov.agent.cash
            if econsim_states.default_gov else 0
        )
        print(f"  TAX: collected ${total_tax_collected:.2f} from top "
              f"{top_count} agents, govCash=${gov_cash:.2f}")


def _log_gdp(agents):
    total_gdp = 0
    for good in goods:
        if good != Goods.gov:
            gdp_value = production_log[good][-1] * recipes[good]['price']
            total_gdp += gdp_value
            gdp_by_profession_log[good].append(gdp_value)
    gdp_log.append(total_gdp)


def _log_all_metrics(t, agents):
    for good in goods:
        pop_log[good].append(sum(agent.output == good for agent in agents))
        cash_log[good].append(
            sum(agent.cash if agent.output == good else 0 for agent in agents)
        )
        gini_log[good].append(compute_gini(agents, good))
        if good != Goods.gov:
            inv_log[good].append(sum(agent.inv.get(good, 0) for agent in agents))
            newlist = [agent.inv[good] for agent in agents
                       if agent.output != good]
            avgInv = mean(newlist) if newlist else 0
            perCapitaInv[good].append(avgInv)
            price_log[good].append(recipes[good]['price'])


def _log_pop_change_rate():
    if len(total_pop) >= 10:
        pop_10_turns_ago = total_pop[-(10)]
        current_pop = total_pop[-1]
        if pop_10_turns_ago > 0:
            pop_change_pct = (
                (current_pop - pop_10_turns_ago) / pop_10_turns_ago * 100
            )
        else:
            pop_change_pct = 0
    else:
        pop_change_pct = 0
    pop_change_rate_log.append(pop_change_pct)


# =============================================================================
# PLOTTING & FINAL REPORT
# =============================================================================

def _plot_results(agents):
    figure, axis = plt.subplots(5, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(12)
    plt.subplots_adjust(top=0.98, bottom=0.02, hspace=0.05)
    colors = {
        Goods.food: 'green',
        Goods.wood: 'red',
        Goods.furn: 'blue',
        Goods.gov: 'yellow',
    }
    labels = {
        Goods.food: 'Food',
        Goods.wood: 'Wood',
        Goods.furn: 'carp',
        Goods.gov: 'gov',
    }
    axisId = 0
    _plot_population(axis, axisId, colors, labels)
    axisId += 1
    _plot_inventory(axis, axisId, colors, labels)
    axisId += 1
    _plot_gini(axis, axisId, colors, labels)
    axisId += 1
    _plot_demand_ratio(axis, axisId, colors, labels)
    axisId += 1
    _plot_production(axis, axisId, colors, labels)
    axisId += 1
    _plot_per_capita_inv(axis, axisId, colors, labels)
    axisId += 1
    _plot_cash(axis, axisId, colors, labels)
    axisId += 1
    _plot_demand(axis, axisId, colors, labels)
    axisId += 1
    _plot_sold(axis, axisId, colors, labels)
    axisId += 1
    _plot_price(axis, axisId, colors, labels)
    axisId += 1
    _plot_hunger(axis, axisId, colors, labels)
    axisId += 1
    _plot_supply(axis, axisId, colors, labels)
    axisId += 1
    _plot_pop_change_rate(axis, axisId)
    axisId += 1
    _plot_gdp_total(axis, axisId)
    axisId += 1
    _plot_gdp_by_profession(axis, axisId, colors, labels)
    axisId += 1
    _plot_purchases(axis, axisId, colors, labels)
    legend_handles, legend_labels = axis[2].get_legend_handles_labels()
    figure.legend(legend_handles, legend_labels,
                  loc='upper right', ncol=1, fontsize='small')
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
    _print_final_report(agents)
    plt.savefig('sim_output.png')


def _plot_population(axis, axisId, colors, labels):
    axis[axisId].set_title("Population vs time")
    axis[axisId].set_ylabel("Population")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(pop_log[good], label=labels[good], color=colors[good])
    axis[axisId].plot(total_pop, label='total', color='black')
    axis[axisId].plot([-x for x in deadstarve_pop], label='dead', color='purple')


def _plot_inventory(axis, axisId, colors, labels):
    axis[axisId].set_title("Inventory vs time")
    axis[axisId].set_ylabel("Inventory")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(inv_log[good], label=labels[good],
                              color=colors[good])


def _plot_gini(axis, axisId, colors, labels):
    axis[axisId].set_title("Gini coefficient")
    axis[axisId].set_ylabel("Cash")
    rotGoods = [goods[-1]] + goods[:-1]
    for good in rotGoods:
        axis[axisId].plot(gini_log[good], label=labels[good],
                          color=colors[good])


def _plot_demand_ratio(axis, axisId, colors, labels):
    axis[axisId].set_title("Demands Ratio vs time")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_ratio_log[good], label=labels[good],
                              color=colors[good])


def _plot_production(axis, axisId, colors, labels):
    axis[axisId].set_title("Production vs time")
    axis[axisId].set_ylabel("Units Produced per round")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(production_log[good], label=labels[good],
                              color=colors[good])


def _plot_per_capita_inv(axis, axisId, colors, labels):
    axis[axisId].set_title("Inventory Per capita (excluding producers)")
    axis[axisId].set_ylabel("Inventory per capita")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(perCapitaInv[good], label=labels[good],
                              color=colors[good])


def _plot_cash(axis, axisId, colors, labels):
    axis[axisId].set_title("Cash vs time")
    axis[axisId].set_ylabel("Cash")
    for good in goods:
        axis[axisId].plot(cash_log[good], label=labels[good],
                          color=colors[good])
    axis[axisId].plot(totalCash_log, label='total', color='black')
    axis[axisId].plot(bankCash_log, label='bank', color='purple')


def _plot_demand(axis, axisId, colors, labels):
    axis[axisId].set_title("Demand vs time")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_log[good], label=labels[good],
                              color=colors[good])


def _plot_sold(axis, axisId, colors, labels):
    axis[axisId].set_title("Sold vs time")
    axis[axisId].set_ylabel("Sold")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(sold_log[good], label=labels[good],
                              color=colors[good])


def _plot_price(axis, axisId, colors, labels):
    axis[axisId].set_title("Price vs time")
    axis[axisId].set_ylabel("Price")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(price_log[good], label=labels[good],
                              color=colors[good])


def _plot_hunger(axis, axisId, colors, labels):
    axis[axisId].set_title("Hunger vs time")
    axis[axisId].set_ylabel("Num hungry")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(hungry_log[good], label=labels[good],
                          color=colors[good])


def _plot_supply(axis, axisId, colors, labels):
    axis[axisId].set_title("Supply vs time")
    axis[axisId].set_ylabel("Supply (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(supply_log[good], label=labels[good],
                              color=colors[good])


def _plot_pop_change_rate(axis, axisId):
    axis[axisId].set_title("Pop Change Rate (per 10 turns %)")
    axis[axisId].set_ylabel("% change")
    axis[axisId].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    axis[axisId].plot(pop_change_rate_log, color='black')


def _plot_gdp_total(axis, axisId):
    axis[axisId].set_title("GDP vs time (total)")
    axis[axisId].set_ylabel("GDP (value)")
    axis[axisId].set_yscale('log', base=2)
    axis[axisId].plot(gdp_log, color='black')


def _plot_gdp_by_profession(axis, axisId, colors, labels):
    axis[axisId].set_title("GDP vs time (by profession)")
    axis[axisId].set_ylabel("GDP (value)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(gdp_by_profession_log[good],
                              label=labels[good], color=colors[good])


def _plot_purchases(axis, axisId, colors, labels):
    titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
    for i in range(len(titles)):
        axis[axisId + i].set_title(titles[i] + " Purchases")
        axis[axisId + i].set_ylabel("Bought")
    i = 0
    for prof in goods:
        for good in goods:
            if good != Goods.gov:
                axis[axisId + i].plot(bought_log[prof][good],
                                      label=labels[good],
                                      color=colors[good])
        i += 1


def _print_final_report(agents):
    labels = {
        Goods.food: 'Food',
        Goods.wood: 'Wood',
        Goods.furn: 'carp',
        Goods.gov: 'gov',
    }
    print("\n--- Final Evaluation Summary ---")
    for good in goods:
        pop = pop_log.get(good, [0])[-1] if pop_log.get(good) else 0
        price = (price_log.get(good, [1.0])[-1]
                 if good != Goods.gov and price_log.get(good) else 1.0)
        inv = (inv_log.get(good, [0])[-1]
               if good != Goods.gov and inv_log.get(good) else 0)
        cash = cash_log.get(good, [0])[-1] if cash_log.get(good) else 0
        print(f"{profession.get(good, str(good))}: Pop={pop}, "
              f"Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
    print(f"Total Pop: {total_pop[-1] if total_pop else 0}, "
          f"Dead/Starved: {deadstarve_pop[-1] if deadstarve_pop else 0}")
    print("\n--- Demand Metrics (last 10 avg) ---")
    for good in goods:
        if good != Goods.gov:
            last10_dr = (demand_ratio_log.get(good, [])[-10:]
                         if demand_ratio_log.get(good) else [])
            last10_sold = (sold_log.get(good, [])[-10:]
                           if sold_log.get(good) else [])
            avg_dr = sum(last10_dr) / len(last10_dr) if last10_dr else 0
            avg_sold = sum(last10_sold) / len(last10_sold) if last10_sold else 0
            print(f"  {labels[good]}: demand_ratio={avg_dr:.2f}, "
                  f"sold={avg_sold:.0f}")
    num_corps = sum(1 for agent in agents if agent.is_corp)
    total_employees = sum(len(agent.employees) for agent in agents if agent.is_corp)
    print(f"Active Corporations: {num_corps}")
    print(f"Total Employees in Corps: {total_employees}")
    for agent in agents:
        if agent.is_corp:
            print(f"  - {agent.name()}: {len(agent.employees)}/"
                  f"{agent.max_employees} employees, "
                  f"Cash: {agent.cash:.2f}, Wage: {agent.wage}")
    corp_cash = sum(agent.cash for agent in agents if agent.is_corp)
    corp_employee_cash = sum(
        agent.cash for agent in agents
        if getattr(agent, 'employer', None) is not None
    )
    independent_cash = sum(
        agent.cash for agent in agents
        if agent.employer is None and not agent.is_corp
    )
    total_owner_pay = 0
    total_retained = 0
    total_owner_loan = 0
    for agent in agents:
        if agent.is_corp:
            total_retained += agent.retained_earnings
            total_owner_loan += agent.owner_loan
        if hasattr(agent, 'owner_payouts') and agent.owner_payouts:
            total_owner_pay += sum(agent.owner_payouts)
    if total_owner_pay > 0 or total_retained > 0 or total_owner_loan > 0:
        print(f"\n--- Owner Compensation Summary (to {num_corps} corps) ---")
        print(f"Total owner payouts (cumulative):    ${total_owner_pay:.2f}")
        print(f"Total retained earnings (corps):     ${total_retained:.2f}")
        print(f"Total owner loans outstanding:       ${total_owner_loan:.2f}")
        print("--------------------------------")
    print("\n--- Money Distribution ---")
    print(f"Corporations ({num_corps}):             ${corp_cash:.2f}")
    print(f"Corporate employees ({total_employees}):  ${corp_employee_cash:.2f}")
    print(f"Independent agents:                  ${independent_cash:.2f}")
    gov_cash = (econsim_states.default_gov.agent.cash
                if econsim_states.default_gov else 0)
    print(f"Government:                          ${gov_cash:.2f}")
    bank_capital = trade.bank.total_deposits - trade.bank.total_liabilities
    print(f"Bank (deposits - liab):              ${bank_capital:.2f}")
    total_cash = getTotalCash(agents)
    print(f"Total Cash in Economy:               ${total_cash:.2f}")
    print(f"Bank deposits held:                  ${trade.bank.total_deposits:.2f}")
    print(f"Bank liabilities (loans):            ${trade.bank.total_liabilities:.2f}")
    print("--------------------------------")
    print("\n--- Bank Profit & Loss (cumulative) ---")
    print(f"Loan interest earned (cumulative):    "
          f"${trade.bank.total_interest_earned:.2f}")
    print(f"Deposit interest paid (cumulative):   "
          f"${trade.bank.total_deposit_interest_paid:.2f}")
    bank_profit = (trade.bank.total_interest_earned
                   - trade.bank.total_deposit_interest_paid)
    print(f"Net profit:                           ${bank_profit:.2f}")
    if trade.bank.total_deposit_interest_paid > 0:
        ratio = (trade.bank.total_interest_earned
                 / trade.bank.total_deposit_interest_paid)
        print(f"Profit ratio (earned / paid):         {ratio:.2f}x")
    else:
        print("Profit ratio (earned / paid):         N/A (no deposit interest paid)")
    print("--------------------------------\n")
    print("\n--- GDP Summary ---")
    print(f"Total GDP (cumulative):            ${sum(gdp_log):.2f}")
    print(f"Final GDP per turn:                ${gdp_log[-1] if gdp_log else 0:.2f}")
    for good in goods:
        if good != Goods.gov:
            final_gdp = (gdp_by_profession_log[good][-1]
                         if gdp_by_profession_log.get(good) else 0)
            print(f"  {labels[good]} GDP per turn:           ${final_gdp:.2f}")
    print("--------------------------------\n")


if __name__ == "__main__":
    main()
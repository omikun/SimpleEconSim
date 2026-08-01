"""
Single-region economic simulation.

Usage:
    python3 econsim.py [time_steps]
"""

import sys
import random
import math
from statistics import mean
import matplotlib.pyplot as plt

from goods import Goods, profession
from region import compute_gini as region_gini, get_total_cash
from econsim_states import (
    recipes, goods, probability_birth, probability_death, birth_gap,
    max_career_switches, starvation_limit, number_of_agents,
    total_production, agent_id_counter,
    population_log, inventory_log, hungry_log, production_log,
    demand_ratio_log, supply_log, demand_log,
    per_capita_inventory, cash_log, gini_log, total_cash_log, bank_cash_log,
    price_log, sold_log, bought_log, dead_pop, dead_starved_population,
    total_population, population_change_rate_log, gdp_log, gdp_by_profession_log,
    governments, default_government,
)
import econsim_states
from logger import loginfo, logdebug, logwarning, logInit, logerror

from econsim_live import LiveContext
import econsim_live as Living
import econsim_trade_money as trade
from agent import Agent, initialize_agent, get_input_commodity, get_output_commodity


# =============================================================================
# Module-level initialisation
# =============================================================================

for good in goods:
    population_log[good] = []
    hungry_log[good] = []
    if good != Goods.gov:
        demand_ratio_log[good] = []
        demand_log[good] = []
        supply_log[good] = []
        inventory_log[good] = []
        per_capita_inventory[good] = []
        production_log[good] = []


# =============================================================================
# Agent initialisation (uses helpers from agent.py module)
# =============================================================================

def initialize_agents(agents):
    for a in range(number_of_agents):
        agent = agents[a]
        if a < 90:
            output = Goods.food
        elif a < 97:
            output = Goods.wood
        elif a < 99:
            output = Goods.furniture
        else:
            output = Goods.gov
        delta = 20
        cash = 120 + random.randint(-delta, delta)
        initialize_agent(agent, output, 10, 2, cash)


for good in goods:
    cash_log[good] = []
    gini_log[good] = []

price_log = {Goods.food: [], Goods.wood: [], Goods.furniture: [], Goods.transport: []}

for prof in goods:
    bought_log[prof] = {}
    for good in goods:
        bought_log[prof][good] = [0]


# =============================================================================
# LABOUR MARKET
# =============================================================================

def run_labour_market(t, agents):
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
        if agent.is_corporation:
            agent.employees = [
                e for e in agent.employees
                if e in living_agents_set and e.employer == agent
            ]


def _borrow_or_layoff(t, agents):
    for agent in agents:
        if not agent.is_corporation or len(agent.employees) == 0:
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
            agent.is_corporation = False
            if agent.owner is not None:
                agent.owner.company_owned = None
                loginfo(t, agent.name(), "dissolved company, owner",
                        agent.owner.name(), "released")


def _handle_incorporation(t, agents):
    new_company_agents = []
    for agent in agents:
        if agent.employer is not None or agent.is_corporation or agent.cash <= 400:
            continue
        if agent.company_owned is not None:
            continue
        food_price = recipes[Goods.food]['price']
        company = Agent(t)
        company.is_corporation = True
        company.output = agent.output
        company.owner = agent
        agent.company_owned = company
        for good in goods:
            company.inventory[good.value] = agent.inv_get(good, 0)
            agent.inv_set(good, 0)
        owner_equity = min(agent.cash * 0.3, agent.cash - 60)
        startup_target = max(300, food_price * 20)
        shortfall = max(0, startup_target - owner_equity)
        if shortfall > 0:
            trade.bank.Borrow(t, agent, shortfall)
        agent.cash -= owner_equity
        company.cash = owner_equity + shortfall
        sector_wages = [
            a.wage for a in agents
            if a.is_corporation and a.output == agent.output and a.wage > 0
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
        if not agent.is_corporation:
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
            if a.employer is None and not a.is_corporation and a != agent
        ]
        distressed = [c for c in candidates
                      if c.hungry_steps > 0 or c.cash < 40]
        pool = distressed
        if pool:
            candidate = random.choice(pool)
            candidate.employer = agent
            candidate.hired_at = t
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
                and e.employer.is_corporation
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
                    target.hired_at = t
                    target.output = agent.output
                    agent.employees.append(target)
                    agent.wage = max(agent.wage, offer_wage)
                    loginfo(t, agent.name(), "poached", target.name(),
                            "from", old_employer.name(),
                            "at wage", agent.wage)


def _adjust_wages(t, agents):
    for agent in agents:
        if not agent.is_corporation or len(agent.employees) == 0:
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
        if agent.is_corporation and len(agent.employees) > 0:
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
    num_agents_per_good = {}
    for good in goods:
        num_agents_per_good[good] = sum(agent.output == good for agent in agents)
    total_production.clear()
    for agent in agents:
        if agent.employer is not None:
            continue
        output = agent.output
        loginfo(t, agent.name(), agent.inventory, 'hungry_steps', agent.hungry_steps)
        recipe = recipes[output]
        if agent.is_corporation and len(agent.employees) > 0:
            _produce_corporation(t, agent, recipe, output, num_agents_per_good)
        else:
            _produce_independent(t, agent, recipe, output, num_agents_per_good)
    for good in goods:
        if good != Goods.gov:
            production_log[good].append(total_production[good])
    for good, produced in total_production.items():
        loginfo(t, num_agents_per_good[good], 'produced', produced, good)


def _produce_corporation(t, agent, recipe, output, num_agents_per_good):
    num_employees = len(agent.employees)
    max_inventory = recipe['maxinv'] * (1 + num_employees)
    inventory_ratio = agent.inv_get(output, 0) / max_inventory if max_inventory > 0 else 1
    if inventory_ratio >= 1:
        total_production[output] += 0
        return
    num_slots = num_employees
    if recipe.get('numInput', 0) > 0:
        commodity = recipe['input']
        available_inputs = agent.inv_get(commodity, 0)
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
    base_production = recipe['production']
    production_per_slot = base_production * synergy
    chance = 1.0
    if agent.hungry_steps > 0:
        chance *= 1 / (1 + agent.hungry_steps * 0.2)
    if output in (Goods.food, Goods.wood):
        max_per_agent = recipe['maxtotalprod'] / max(1, num_agents_per_good[output])
        chance *= min(1.0, max_per_agent / base_production)
    chance *= max(0, 1 - inventory_ratio)
    successful_slots = 0
    for _ in range(active_slots):
        if random.random() < chance:
            successful_slots += 1
    if successful_slots > 0:
        if recipe.get('numInput', 0) > 0:
            agent.inv_add(recipe['input'], -successful_slots * recipe['numInput'])
        num_output = int(successful_slots * production_per_slot)
        if num_output == 0:
            num_output = 1
        agent.inv_add(output, num_output)
        total_production[output] += num_output
        loginfo(t, agent.name(), 'corp built', num_output, output,
                'slots', successful_slots, 'synergy', synergy)


def _produce_independent(t, agent, recipe, output, num_agents_per_good):
    max_inventory = recipe['maxinv']
    inventory_ratio = agent.inv_get(output, 0) / max_inventory if max_inventory > 0 else 1
    if inventory_ratio >= 1:
        total_production[output] += 0
        return
    has_inputs = True
    if recipe['numInput'] > 0:
        commodity = recipe['input']
        if agent.inv_get(commodity, 0) < recipe['numInput']:
            has_inputs = False
    num_output = 0
    if has_inputs and recipe.get('production', 0) > 0:
        chance = 1.0
        if agent.hungry_steps > 0:
            chance *= 1 / (1 + agent.hungry_steps * 0.2)
        if output in (Goods.food, Goods.wood):
            max_per_agent = recipe['maxtotalprod'] / max(1, num_agents_per_good[output])
            chance *= min(1.0, max_per_agent / recipe['production'])
        chance *= max(0, 1 - inventory_ratio)
        if random.random() < chance:
            if recipe['numInput'] > 0:
                agent.inv_add(recipe['input'], -recipe['numInput'])
            num_output = recipe['production']
    agent.inv_add(output, num_output)
    total_production[output] += num_output
    loginfo(t, agent.name(), 'built', num_output, output, agent.inventory)


# =============================================================================
# GINI / CASH helpers
# =============================================================================



def recalculate_consumption_multipliers(agents):
    """Recalculate consumption_multiplier for every living agent based on wealth / cost of living."""
    food_price = recipes.get(Goods.food, {}).get('price', 1)
    wood_price = recipes.get(Goods.wood, {}).get('price', 1)
    furn_price = recipes.get(Goods.furniture, {}).get('price', 1)
    cost_of_living = 4 * food_price + 1 * wood_price + 0.25 * furn_price
    cost_of_living = max(0.1, cost_of_living)
    for agent in agents:
        if not agent.alive or getattr(agent, 'is_corporation', False):
            continue
        wealth = agent.wealth()
        if wealth > cost_of_living:
            raw = math.sqrt(wealth / cost_of_living)
            agent.consumption_multiplier = max(1.0, min(10.0, raw))
        else:
            agent.consumption_multiplier = 1.0


# =============================================================================
# OWNER PROFIT DISTRIBUTION
# =============================================================================

def distribute_owner_profits(t, agents):
    """Distribute corporate profits to owners."""
    for agent in agents:
        if not agent.is_corporation or not agent.alive:
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
    available_for_repayment = max(0, agent.cash - payroll * 2)
    repay = min(agent.owner_loan, available_for_repayment)
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
    agents = [Agent(0) for _ in range(number_of_agents)]
    import government as govmod
    government = govmod.create_default_government(0, initial_cash=200)
    agents.append(government.agent)
    initialize_agents(agents)
    for agent in agents:
        if hasattr(agent, 'id'):
            government._add_citizen(agent)
    previous_total_cash = get_total_cash(agents, trade.bank)
    for t in range(time_steps):
        _record_start_of_turn(agents)
        new_company_agents = run_labour_market(t, agents)
        if new_company_agents:
            agents.extend(new_company_agents)
        Produce(t, agents)
        trade.Trade(t, agents, recipes, demand_ratio_log, demand_log,
                    supply_log, sold_log, bought_log)
        PayWages(t, agents)
        distribute_owner_profits(t, agents)
        _record_delta_income(agents)
        _collect_top_tax(t, agents)
        _log_gdp(agents)
        if t > 0 and t % 10 == 0:
            recalculate_consumption_multipliers(agents)
        _live_ctx = LiveContext(
            recipes=recipes,
            goods=goods,
            governments=governments,
            default_gov=default_government,
            hungry_log=hungry_log,
            dead_pop=dead_pop,
            deadstarve_pop=dead_starved_population,
            production_log=production_log,
            starve_limit=starvation_limit,
            profession=profession,
            max_career_switches=max_career_switches,
            p_birth=probability_birth,
            birth_gap=birth_gap,
            bank=trade.bank,
            most_demand=Goods.food,
            carrying_capacity=400,
        )
        cash_before_live = get_total_cash(agents, trade.bank)
        agents = Living.Live(t, agents, context=_live_ctx)
        cash_after_live = get_total_cash(agents, trade.bank)
        live_diff = cash_after_live - cash_before_live
        if abs(live_diff) > 5.0:
            print(f"{t}  CASH LEAK: Live() changed total by ${live_diff:.2f}")
        _log_all_metrics(t, agents)
        total_population.append(sum(log[-1] for log in population_log.values()))
        bank_cash_log.append(trade.bank.total_deposits - trade.bank.total_liabilities)
        total_cash_log.append(get_total_cash(agents, trade.bank))
        _log_population_change_rate()
        for prof in goods:
            for good in goods:
                bought_log[prof][good].append(0)
        difference = math.fabs(previous_total_cash - total_cash_log[-1])
        if difference > epsilon:
            logwarning(t, "total cash not matching", previous_total_cash,
                       '!=', total_cash_log[-1], 'diff', difference)
        previous_total_cash = total_cash_log[-1]
        if t % 100 == 0:
            circulating_cash = sum(a.cash for a in agents)
            bank_deposits = trade.bank.total_deposits
            bank_liabilities = trade.bank.total_liabilities
            ratio = bank_deposits / max(1, circulating_cash)
            print(f"--- Bank Health T={t}: circulating=${circulating_cash:.0f}, "
                  f"bank_liabilities=${bank_liabilities:.0f}, ratio={ratio:.1f}x")
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
            econsim_states.default_government.compute_child_tax_deduction(agent)
            if econsim_states.default_government else 0.0
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
            if econsim_states.default_government is not None:
                econsim_states.default_government.collect_tax(t, actual_tax)
            total_tax_collected += actual_tax
        else:
            agent.tax_loss_carryforward += net_income
    if total_tax_collected > 0 and t % 50 == 0:
        gov_cash = (
            econsim_states.default_government.agent.cash
            if econsim_states.default_government else 0
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
        population_log[good].append(sum(agent.output == good for agent in agents))
        cash_log[good].append(
            sum(agent.cash if agent.output == good else 0 for agent in agents)
        )
        gini_log[good].append(region_gini(agents, good))
        if good != Goods.gov:
            inventory_log[good].append(sum(agent.inv_get(good, 0) for agent in agents))
            newlist = [agent.inv_get(good, 0) for agent in agents
                       if agent.output != good]
            avg_inv = mean(newlist) if newlist else 0
            per_capita_inventory[good].append(avg_inv)
            price_log[good].append(recipes[good]['price'])


def _log_population_change_rate():
    if len(total_population) >= 10:
        pop_10_turns_ago = total_population[-(10)]
        current_pop = total_population[-1]
        if pop_10_turns_ago > 0:
            pop_change_pct = (
                (current_pop - pop_10_turns_ago) / pop_10_turns_ago * 100
            )
        else:
            pop_change_pct = 0
    else:
        pop_change_pct = 0
    population_change_rate_log.append(pop_change_pct)


# =============================================================================
# PLOTTING & FINAL REPORT
# =============================================================================

def _smooth(data, window=5):
    """5-turn rolling average. First (window-1) points use raw values."""
    if len(data) < window:
        return data
    result = list(data[:window - 1])
    for i in range(window - 1, len(data)):
        result.append(sum(data[i - window + 1:i + 1]) / window)
    return result


def _plot_results(agents):
    figure, axis = plt.subplots(5, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(12)
    plt.subplots_adjust(top=0.95, bottom=0.04, hspace=0.35, wspace=0.25)
    colors = {
        Goods.food: 'green',
        Goods.wood: 'red',
        Goods.furniture: 'blue',
        Goods.transport: 'purple',
        Goods.gov: 'yellow',
    }
    labels = {
        Goods.food: 'Food',
        Goods.wood: 'Wood',
        Goods.furniture: 'Furniture',
        Goods.transport: 'Transport',
        Goods.gov: 'gov',
    }
    axis_id = 0
    _plot_population(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_inventory(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_gini(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_demand_ratio(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_production(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_per_capita_inv(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_cash(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_demand(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_sold(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_price(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_hunger(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_supply(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_pop_change_rate(axis, axis_id)
    axis_id += 1
    _plot_gdp(axis, axis_id, colors, labels)
    axis_id += 1
    _plot_purchases(axis, axis_id, colors, labels)
    axis_id += 1
    handles, labels_list = [], []
    for ax in axis:
        h, l = ax.get_legend_handles_labels()
        for hi, li in zip(h, l):
            if li not in labels_list:
                handles.append(hi)
                labels_list.append(li)
    figure.legend(handles, labels_list, loc='upper right', ncol=1, fontsize='small')
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
    plt.savefig("sim_output.png")
    plt.close(figure)
    print("Plot saved to sim_output.png")
    _print_final_stats(agents)


def _plot_population(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Population vs time")
    axis[axis_id].set_ylabel("Population")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        axis[axis_id].plot(population_log[good], label=labels[good],
                       color=colors[good])
    axis[axis_id].plot(total_population, label='total', color='black')
    axis[axis_id].plot([-x for x in dead_starved_population], label='dead', color='purple')


def _plot_inventory(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Inventory vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Inventory")
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(_smooth(inventory_log[good]), label=labels[good],
                           color=colors[good])


def _plot_gini(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Gini coefficient")
    axis[axis_id].set_ylabel("Cash")
    for good in goods:
        axis[axis_id].plot(gini_log[good], label=labels[good],
                       color=colors[good])


def _plot_demand_ratio(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Demand Ratio vs time")
    axis[axis_id].set_ylabel("Demand Ratio (log scale)")
    axis[axis_id].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(demand_ratio_log[good], label=labels[good],
                           color=colors[good])


def _plot_production(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Production vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Units/round")
    axis[axis_id].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(_smooth(production_log[good]), label=labels[good],
                           color=colors[good])


def _plot_per_capita_inv(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Inventory Per capita (excl producers)")
    axis[axis_id].set_ylabel("Inv per cap")
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(per_capita_inventory[good], label=labels[good],
                           color=colors[good])


def _plot_cash(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Cash vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Cash")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        axis[axis_id].plot(_smooth(cash_log[good]), label=labels[good],
                       color=colors[good])
    axis[axis_id].plot(_smooth(total_cash_log), label='total', color='black')
    axis[axis_id].plot(_smooth(bank_cash_log), label='bank', color='purple')


def _plot_demand(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Demand vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Demand (log)")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(_smooth(demand_log[good]), label=labels[good],
                           color=colors[good])


def _plot_sold(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Sold vs time")
    axis[axis_id].set_ylabel("Sold (log)")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(sold_log[good], label=labels[good],
                           color=colors[good])


def _plot_price(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Price vs time")
    axis[axis_id].set_ylabel("Price")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(price_log[good], label=labels[good],
                           color=colors[good])


def _plot_hunger(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Hunger vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Num hungry")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        axis[axis_id].plot(_smooth(hungry_log[good]), label=labels[good],
                       color=colors[good])


def _plot_supply(axis, axis_id, colors, labels):
    axis[axis_id].set_title("Supply vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Supply (log)")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(_smooth(supply_log[good]), label=labels[good],
                           color=colors[good])


def _plot_pop_change_rate(axis, axis_id):
    axis[axis_id].set_title("Pop Change Rate (per 10 turns %)")
    axis[axis_id].set_ylabel("% change")
    axis[axis_id].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    axis[axis_id].plot(population_change_rate_log, color='black')


def _plot_gdp(axis, axis_id, colors, labels):
    axis[axis_id].set_title("GDP vs time (5-turn avg)")
    axis[axis_id].set_ylabel("Total GDP (value)")
    axis[axis_id].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axis_id].plot(_smooth(gdp_by_profession_log[good]), label=labels[good],
                           color=colors[good])
    axis[axis_id].plot(_smooth(gdp_log), label='All', color='black')


def _plot_purchases(axis, axis_id, colors, labels):
    titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
    for i in range(len(titles)):
        axis[axis_id + i].set_title(titles[i] + " Purchases")
        axis[axis_id + i].set_ylabel("Bought")
    i = 0
    for prof in goods:
        for good in goods:
            axis[axis_id + i].plot(bought_log[prof][good], label=labels[good],
                               color=colors[good])
        i += 1


def _print_final_stats(agents):
    print("\n" + "=" * 60)
    print("FINAL STATS")
    print("=" * 60)
    print()
    for good in goods:
        pop = population_log[good][-1] if population_log[good] else 0
        price = (price_log[good][-1] if good != Goods.gov and price_log[good]
                 else recipes[good]['price'])
        inv = (inventory_log[good][-1] if good != Goods.gov and inventory_log[good] else 0)
        cash = cash_log[good][-1] if cash_log[good] else 0
        print(f"  {good}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, "
              f"Cash={cash:.2f}")
    print()
    print(f"  Total Population (last): {total_population[-1]}")
    print(f"  Total Dead/Starved: {dead_starved_population[-1]}")
    if gdp_log:
        print(f"  Final GDP/turn: ${gdp_log[-1]:.2f}")
    print()
    print("GDP breakdown per turn:")
    for good in goods:
        if good != Goods.gov:
            gdp_val = (production_log[good][-1] * recipes[good]['price']
                       if production_log[good] else 0)
            print(f"  {Goods(good).name} GDP per turn:\t\t${gdp_val:.2f}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
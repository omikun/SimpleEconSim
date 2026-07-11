import sys 
import random
import math
from statistics import mean
import matplotlib.pyplot as plt

import econsim_live as Living
import econsim_states
from econsim_states import *
from goods import Goods
#import econsim_trade as trade
#import econsim_trade_unity as trade
import econsim_trade_money as trade
from logger import *

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

    def name(self):
        return 'agent'+str(self.id)+'-'+ profession[self.output]
    def age(self, t):
        return t - self.birthRound
    
    def wealth(self):
        inv_value = sum(amount * recipes[good]['price'] for good, amount in self.inv.items() if good in recipes)
        debt_value = sum(loan.principle for loan in self.loans)
        return self.cash + trade.bank.deposits.get(self, 0) + inv_value - debt_value
    
    def oweThisTurn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)

# Initial populations
#agent_template = {'profession': Goods.none,'hungry_steps': 0, 'cash':10, 'inv': {}}
recipes[Goods.food] = {'commodity': Goods.food, 'production': 5, 'price': 1, 'numInput': 0, 'maxtotalprod': 10000, 'maxinv': 20}
recipes[Goods.wood] = {'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0, 'maxtotalprod': 3000, 'maxinv': 10}
recipes[Goods.furn] = {'commodity': Goods.furn, 'production': 1, 'input': Goods.wood, 'numInput': 2, 'price': 25, 'maxtotalprod':300, 'maxinv': 5}
recipes[Goods.gov] = {'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1, 'maxtotalprod':0, 'maxinv': 0}
# Parameters

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

#init
def GetInputCom(agent):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', Goods.none)
    return inputCom
def GetOutputCom(agent):
    return agent.output

def InitAgents(agents):
    for a in range(num_agents):
        agent = agents[a]
        output = Goods.none

        if a < 90:
            output = Goods.food
        elif a < 97:
            output = Goods.wood
        elif a < 99:
            output = Goods.furn
        else:            
            output = Goods.gov

        #init inventory
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

def RunLaborMarket(t, agents):
    # 1. Clean up references of dead agents (self-healing)
    living_agents_set = set(agents)
    for agent in agents:
        if agent.employer and agent.employer not in living_agents_set:
            agent.employer = None
        if agent.is_corp:
            agent.employees = [e for e in agent.employees if e in living_agents_set and e.employer == agent]
            
    # 2. Borrow or layoff due to lack of cash
    for agent in agents:
        if agent.is_corp and len(agent.employees) > 0:
            total_wage_needed = len(agent.employees) * agent.wage
            # Try to borrow from bank before laying off
            if agent.cash < total_wage_needed:
                shortfall = total_wage_needed - agent.cash
                trade.bank.Borrow(t, agent, shortfall)
                loginfo(t, agent.name(), "borrowed $", min(shortfall, trade.bank.total_deposits - trade.bank.total_liabilities), 
                        "from bank to cover payroll. cash:", agent.cash)
            # Still can't pay? Lay off
            while agent.cash < total_wage_needed and len(agent.employees) > 0:
                # Lay off last hired employee
                emp = agent.employees.pop()
                emp.employer = None
                total_wage_needed = len(agent.employees) * agent.wage
                loginfo(t, agent.name(), "laid off", emp.name(), "due to insufficient cash. Remaining:", len(agent.employees))
            
            # If no employees left, dissolve corporation status
            if len(agent.employees) == 0:
                agent.is_corp = False
                if agent.owner is not None:
                    agent.owner.company_owned = None
                    loginfo(t, agent.name(), "dissolved company, owner", agent.owner.name(), "released")
                
    # 3. Incorporation: highly wealthy independent agents spawn company agents
    new_company_agents = []
    for agent in agents:
        if agent.employer is None and not agent.is_corp and agent.cash > 400 and agent.company_owned is None:
            food_price = recipes[Goods.food]['price']
            
            # Create separate company agent
            company = Agent(t)
            company.is_corp = True
            company.output = agent.output
            company.owner = agent
            agent.company_owned = company
            
            # Transfer founder's entire inventory to company
            for good in goods:
                company.inv[good] = agent.inv.get(good, 0)
                agent.inv[good] = 0
            
            # Calculate startup capital
            owner_equity = min(agent.cash * 0.3, agent.cash - 60)  # keep at least 60 for living
            startup_target = max(300, food_price * 20)
            shortfall = max(0, startup_target - owner_equity)
            
            # Founder borrows from bank to fund the company
            if shortfall > 0:
                trade.bank.Borrow(t, agent, shortfall)
            
            # Transfer owner equity to company
            agent.cash -= owner_equity
            company.cash = owner_equity + shortfall
            
            # Fix C: Competitive starting wage (float, not int)
            sector_wages = [a.wage for a in agents if a.is_corp and a.output == agent.output and a.wage > 0]
            if sector_wages:
                company.wage = max(sector_wages) * 1.05  # Beat the competition
            else:
                company.wage = max(1.0, food_price * 1.5)  # No competitors, min $1
            company.max_employees = random.randint(10, 25)
            
            loginfo(t, agent.name(), "founded company", company.name(), 
                    "with $", company.cash, "(equity:", owner_equity, "borrowed:", shortfall,
                    ") wage:", company.wage)
            
            new_company_agents.append(company)
            
    # 4. Hiring
    # Only active corporations with high cash reserves (at least 2 turns of payroll for current + 1 extra) hire
    for agent in agents:
        if agent.is_corp:
            # Max corporation size limit (per-agent adjustable)
            if len(agent.employees) >= agent.max_employees:
                continue
                
            payroll = len(agent.employees) * agent.wage
            needed_cash_to_hire = (payroll + agent.wage) * 2
            
            if agent.cash > needed_cash_to_hire:
                hired = False
                # Find eligible candidates: independent (no employer), not a corporation themselves
                candidates = [a for a in agents if a.employer is None and not a.is_corp and a != agent]
                # Distressed candidates first: hungry or low cash
                distressed = [c for c in candidates if c.hungry_steps > 0 or c.cash < 40]
                # If no distressed candidates, pick from other candidates
                pool = distressed #agents don't look for work unless distressed # if distressed else candidates
                
                if pool:
                    # Pick one candidate
                    candidate = random.choice(pool)
                    candidate.employer = agent
                    candidate.hiredAt = t
                    agent.employees.append(candidate)
                    # Align employee profession with employer
                    candidate.output = agent.output
                    loginfo(t, agent.name(), "hired", candidate.name(), "at wage", agent.wage)
                    hired = True
                    
                # 4b. Poaching: if no independent distressed agents available and still want to grow,
                # offer higher wages to poach employees from other companies
                if not hired:
                    poachable = [e for e in agents if e.employer is not None 
                                 and e.employer != agent 
                                 and e.employer.is_corp 
                                 and len(e.employer.employees) > 1]  # don't dissolve source company
                    if poachable:
                        target = random.choice(poachable)
                        old_employer = target.employer
                        old_wage = old_employer.wage
                        # Offer at least 10% more than their current wage, or 5% more than our own
                        offer_wage = max(old_wage * 1.1, agent.wage * 1.05)
                        
                        if agent.cash > (payroll + offer_wage) * 2:
                            # Employee quits old job
                            old_employer.employees.remove(target)
                            target.employer = None
                            
                            # Joins new company
                            target.employer = agent
                            target.hiredAt = t
                            target.output = agent.output
                            agent.employees.append(target)
                            agent.wage = max(agent.wage, offer_wage)  # match higher wage
                            loginfo(t, agent.name(), "poached", target.name(), 
                                    "from", old_employer.name(), "at wage", agent.wage)
                    
    # 5. Wage dynamic adjustments (WAGE PAYMENTS moved after Trade - called from main())
    for agent in agents:
        if agent.is_corp and len(agent.employees) > 0:
            payroll = len(agent.employees) * agent.wage
            # Fix C: Raise wage when profitable and have room to grow
            if agent.cash > payroll * 5 and len(agent.employees) < agent.max_employees:
                # Raise wage to attract more workers
                agent.wage = agent.wage * 1.02
                loginfo(t, agent.name(), "raised wage to", agent.wage, "(profitable, room to grow)")
            # If cash is getting lower (less than 3 turns of wage bills), reduce wage to prevent layoffs
            elif agent.cash < payroll * 3:
                agent.wage = agent.wage * 0.95
                loginfo(t, agent.name(), "lowered wage to", agent.wage)

    return new_company_agents

def PayWages(t, agents):
    """Pay wages to employees AFTER production and trade,
    so companies earn revenue before paying out."""
    for agent in agents:
        if agent.is_corp and len(agent.employees) > 0:
            for emp in agent.employees:
                wage_to_pay = min(agent.cash, agent.wage)
                agent.cash -= wage_to_pay
                emp.cash += wage_to_pay
                loginfo(t, agent.name(), "paid wage of", wage_to_pay, "to", emp.name())

def Produce(t, agents):
    numAgentsPerGoods = dict()
    for good in econsim_states.goods:
        numAgentsPerGoods[good] = NumAgents(agents, good)

    totalProd.clear()
    for agent in agents:
        if agent.employer is not None:
            # Employees do not produce independently
            continue
            
        output = agent.output
        loginfo(t, agent.name(), agent.inv, 'hungry_steps', agent.hungry_steps)
        recipe = recipes[output]
        
        if agent.is_corp and len(agent.employees) > 0:
            num_employees = len(agent.employees)
            maxinv = recipe['maxinv'] * (1 + num_employees)
            
            inv_ratio = agent.inv.get(output, 0) / maxinv if maxinv > 0 else 1
            if inv_ratio >= 1:
                totalProd[output] += 0
                continue
                
            num_slots = num_employees
            if recipe.get('numInput', 0) > 0:
                com = recipe['input']
                available_inputs = agent.inv.get(com, 0)
                inputs_per_slot = recipe['numInput']
                active_slots = int(min(num_slots, available_inputs // inputs_per_slot))
            else:
                active_slots = int(num_slots)
                
            if active_slots > 0 and recipe.get('production', 0) > 0:
                # Tiered synergy: larger companies get better per-employee production bonuses
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
                    
                if output == Goods.food or output == Goods.wood:
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
                    loginfo(t, agent.name(), 'corp built', numOutput, output, 'slots', successful_slots, 'synergy', synergy)
        else:
            maxinv = recipe['maxinv']
            inv_ratio = agent.inv.get(output, 0) / maxinv if maxinv > 0 else 1
            if inv_ratio >= 1:
                totalProd[output] += 0
                continue
                
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
                    
                if output == Goods.food or output == Goods.wood:
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

    for good in econsim_states.goods:
        if good != Goods.gov:
            production_log[good].append(totalProd[good])
    for good, produced in totalProd.items():
        loginfo(t, numAgentsPerGoods[good],'produced', produced, good)


def NumAgents(agents, good):
    return sum(agent.output == good for agent in agents)

def PrintStats(t, agents):
    msg = ""
    for agent in agents:
        msg += profession[agent.output] + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.food,0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.wood,0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.furn,0), 1)) + ','
    loginfo(msg)


for good in goods:
    cash_log[good] = []
    gini_log[good] = []

for prof in goods:
    bought_log[prof] = dict()
    for good in goods:
        bought_log[prof][good] = [0]

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
    gini = diffsum / (2 * n * n * mean_cash)
    return gini

def getTotalCash(agents):
    # Calculate bank's exact physical reserves at this exact millisecond
    bankCash = trade.bank.total_deposits - trade.bank.total_liabilities
    return sum(agent.cash for agent in agents) + econsim_states.govCash + bankCash

def main():
    epsilon = 1e-8
    logInit()
    time_steps = int(sys.argv[1])
    agents = [Agent(0) for _ in range(num_agents)]
    InitAgents(agents)
    prevTotalCash = (sum(agent.cash for agent in agents) + econsim_states.govCash + (trade.bank.total_deposits - trade.bank.total_liabilities))
    for t in range(time_steps):
        #PrintStats(t, agents)
        new_company_agents = RunLaborMarket(t, agents)
        if new_company_agents:
            agents.extend(new_company_agents)
        Produce(t, agents)
        #trade.Trade(t, agents, recipes)
        trade.Trade(t, agents, recipes, demand_ratio_log, demand_log, supply_log, sold_log, bought_log)
        PayWages(t, agents)  # Pay wages AFTER production and trade

        # --- GDP Logging ---
        total_gdp = 0
        for good in goods:
            if good != Goods.gov:
                gdp_value = production_log[good][-1] * recipes[good]['price']
                total_gdp += gdp_value
                gdp_by_profession_log[good].append(gdp_value)
        gdp_log.append(total_gdp)
        # --------------------

        tempTotalCash = getTotalCash(agents)
        diff = math.fabs(tempTotalCash - prevTotalCash) 
        if diff > epsilon:
            loginfo(t, "post trade total cash", prevTotalCash, '!=', tempTotalCash, diff)
        
        agents = Living.Live(t, agents)

        for good in goods:
            pop_log[good].append(sum(agent.output == good for agent in agents))
            cash_log[good].append(sum(agent.cash if agent.output == good else 0 for agent in agents))
            gini_log[good].append(compute_gini(agents, good))
            if good != Goods.gov:
                inv_log[good].append(sum(agent.inv.get(good, 0) for agent in agents))
                newlist = [agent.inv[good] for agent in agents if agent.output != good]
                avgInv = mean(newlist) if newlist else 0
                perCapitaInv[good].append(avgInv)
                price_log[good].append(recipes[good]['price'])

        total_pop.append(sum(log[-1] for log in pop_log.values()))
        bankCash_log.append(trade.bank.total_deposits - trade.bank.total_liabilities)
        totalCash_log.append(getTotalCash(agents))

        # Compute population change rate per 10 turns
        if len(total_pop) >= 10:
            pop_10_turns_ago = total_pop[-(10)]
            current_pop = total_pop[-1]
            if pop_10_turns_ago > 0:
                pop_change_pct = (current_pop - pop_10_turns_ago) / pop_10_turns_ago * 100
            else:
                pop_change_pct = 0
        else:
            pop_change_pct = 0
        pop_change_rate_log.append(pop_change_pct)

        for prof in goods:
            for good in goods:
                bought_log[prof][good].append(0)
                
        diff = math.fabs(prevTotalCash - totalCash_log[-1])
        if diff > epsilon:
            logwarning(t, "total cash not matching", prevTotalCash, '!=', totalCash_log[-1], 'diff', diff)
            # break
        prevTotalCash = totalCash_log[-1]

    # Plot results
    figure, axis = plt.subplots(5, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(12)
    plt.subplots_adjust(top=0.98, bottom=0.02, hspace=0.05)

    #axis[0].set_title("Phase plot")
    #axis[0].set_xlabel("food Population (x)")
    #axis[0].set_ylabel("wood/carpenter Population (y)")
    #axis[0].plot(food_pop, wood_pop, color='red')
    #axis[0].plot(food_pop, carp_pop, color='blue')
    
    axisId = 0
    axis[axisId].set_title("Population vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Population")
    axis[axisId].set_yscale('log', base=2)
    colors = {Goods.food: 'green',
              Goods.wood: 'red',
              Goods.furn: 'blue',
              Goods.gov:  'yellow'
              }
    labels = {Goods.food: 'Food',
                Goods.wood: 'Wood',
                Goods.furn: 'carp',
                Goods.gov:  'gov'
                }
    for good in goods:
        axis[axisId].plot(pop_log[good], label=labels[good], color=colors[good])
    axis[axisId].plot(total_pop, label='total', color='black')
    axis[axisId].plot([-x for x in deadstarve_pop], label='dead', color='purple')

    axisId += 1
    axis[axisId].set_title("Inventory vs time ")
    #axis[1].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Inventory")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(inv_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Gini coefficient")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Cash")
    
    rotGoods = [goods[-1]] + goods[:-1]
    for good in rotGoods:
        axis[axisId].plot(gini_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Demands Ratio vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_ratio_log[good], label=labels[good], color=colors[good])

    axisId += 1
    #production
    axis[axisId].set_title("Production vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Units Produced per round")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(production_log[good], label=labels[good], color=colors[good])
    
    axisId += 1
    axis[axisId].set_title("Inventory Per capita (excluding producers)")
    #axis[0].set_xlabel("time ")
    axis[axisId].set_ylabel("Inventory per capita")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(perCapitaInv[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Cash vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Cash")
    # axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(cash_log[good], label=labels[good], color=colors[good])
    axis[axisId].plot(totalCash_log, label='total', color='black')
    axis[axisId].plot(bankCash_log, label='bank', color='purple')

    axisId += 1
    axis[axisId].set_title("Demand vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_log[good], label=labels[good], color=colors[good])


    axisId += 1
    axis[axisId].set_title("Sold vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Sold")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(sold_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Price vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Price")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(price_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Hunger vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Num hungry")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(hungry_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Supply vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Supply (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(supply_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Pop Change Rate (per 10 turns %)")
    axis[axisId].set_ylabel("% change")
    axis[axisId].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    axis[axisId].plot(pop_change_rate_log, color='black')
    
    axisId += 1
    # GDP (total)
    axis[axisId].set_title("GDP vs time (total)")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("GDP (value)")
    axis[axisId].set_yscale('log', base=2)
    axis[axisId].plot(gdp_log, color='black')
    
    axisId += 1
    # GDP by profession
    axis[axisId].set_title("GDP vs time (by profession)")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("GDP (value)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(gdp_by_profession_log[good], label=labels[good], color=colors[good])
    
    axisId += 1
    #purchases
    titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
    for i in range(len(titles)):
        axis[axisId+i].set_title(titles[i]+" Purchases")
        axis[axisId+i].set_ylabel("Bought")
        axis[axisId].set_yscale('log', base=2)
    i = 0
    for prof in goods:
        for good in goods:
            if good != Goods.gov:
                axis[axisId+i].plot(bought_log[prof][good], label=labels[good], color=colors[good])
        i += 1
            
    #plt.legend()
    # Get legend handles and labels from one axis (assuming they’re the same across all)
    legend_handles, legend_labels = axis[2].get_legend_handles_labels() #need label in that axis

    # Add a single global legend
    figure.legend(legend_handles, legend_labels, loc='upper right', ncol=1, fontsize='small') 
    
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
        
    print("\n--- Final Evaluation Summary ---")
    for good in goods:
        pop = pop_log.get(good, [0])[-1] if pop_log.get(good) else 0
        price = price_log.get(good, [1.0])[-1] if good != Goods.gov and price_log.get(good) else 1.0
        inv = inv_log.get(good, [0])[-1] if good != Goods.gov and inv_log.get(good) else 0
        cash = cash_log.get(good, [0])[-1] if cash_log.get(good) else 0
        print(f"{profession.get(good, str(good))}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
    print(f"Total Pop: {total_pop[-1] if total_pop else 0}, Dead/Starved: {deadstarve_pop[-1] if deadstarve_pop else 0}")
    
    num_corps = sum(1 for agent in agents if agent.is_corp)
    total_employees = sum(len(agent.employees) for agent in agents if agent.is_corp)
    print(f"Active Corporations: {num_corps}")
    print(f"Total Employees in Corps: {total_employees}")
    for agent in agents:
        if agent.is_corp:
            print(f"  - {agent.name()}: {len(agent.employees)}/{agent.max_employees} employees, Cash: {agent.cash:.2f}, Wage: {agent.wage}")
    
    # --- Money Distribution Report ---
    corp_cash = sum(agent.cash for agent in agents if agent.is_corp)
    corp_employee_cash = sum(agent.cash for agent in agents if getattr(agent, 'employer', None) is not None)
    independent_cash = sum(agent.cash for agent in agents if agent.employer is None and not agent.is_corp)
    print("\n--- Money Distribution ---")
    print(f"Corporations ({num_corps}):             ${corp_cash:.2f}")
    print(f"Corporate employees ({total_employees}):  ${corp_employee_cash:.2f}")
    print(f"Independent agents:                  ${independent_cash:.2f}")
    print(f"Government:                          ${econsim_states.govCash:.2f}")
    bank_capital = trade.bank.total_deposits - trade.bank.total_liabilities
    print(f"Bank (deposits - liab):              ${bank_capital:.2f}")
    total_cash = getTotalCash(agents)
    print(f"Total Cash in Economy:               ${total_cash:.2f}")
    trade_cash_in_bank = sum(trade.bank.deposits.values())
    print(f"Bank deposits held:                  ${trade.bank.total_deposits:.2f}")
    print(f"Bank liabilities (loans):            ${trade.bank.total_liabilities:.2f}")
    print("--------------------------------")
    
    # --- Bank Profit & Loss Report ---
    print("\n--- Bank Profit & Loss (cumulative) ---")
    print(f"Loan interest earned (cumulative):    ${trade.bank.total_interest_earned:.2f}")
    print(f"Deposit interest paid (cumulative):   ${trade.bank.total_deposit_interest_paid:.2f}")
    bank_profit = trade.bank.total_interest_earned - trade.bank.total_deposit_interest_paid
    print(f"Net profit:                           ${bank_profit:.2f}")
    if trade.bank.total_deposit_interest_paid > 0:
        ratio = trade.bank.total_interest_earned / trade.bank.total_deposit_interest_paid
        print(f"Profit ratio (earned / paid):         {ratio:.2f}x")
    else:
        print(f"Profit ratio (earned / paid):         N/A (no deposit interest paid)")
    print("--------------------------------\n")

    # --- GDP Summary ---
    print("\n--- GDP Summary ---")
    print(f"Total GDP (cumulative):            ${sum(gdp_log):.2f}")
    print(f"Final GDP per turn:                ${gdp_log[-1] if gdp_log else 0:.2f}")
    for good in goods:
        if good != Goods.gov:
            final_gdp = gdp_by_profession_log[good][-1] if gdp_by_profession_log.get(good) else 0
            print(f"  {labels[good]} GDP per turn:           ${final_gdp:.2f}")
    print("--------------------------------\n")
    plt.savefig('sim_output.png')
if __name__ == "__main__":
    main()
